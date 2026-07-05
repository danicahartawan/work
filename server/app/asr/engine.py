"""Batch ASR engines.

The real engine wraps NVIDIA NeMo's Parakeet-TDT-0.6b-v2 — the strongest
open-source (CC-BY-4.0) English ASR model on the Hugging Face Open ASR
leaderboard. A mock engine keeps the whole app usable on machines without
NeMo or a GPU so the UI and extension can be developed anywhere.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional, Protocol

import numpy as np

from .. import config
from ..models import Segment

log = logging.getLogger(__name__)


class ASREngine(Protocol):
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> list[Segment]:
        """Transcribe mono float32 audio into timestamped segments."""
        ...


class NemoParakeetEngine:
    """Parakeet-TDT batch transcription with word/segment timestamps."""

    def __init__(self, model_name: str = config.ASR_MODEL):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            import nemo.collections.asr as nemo_asr  # heavyweight; import lazily

            log.info("Loading NeMo ASR model %s ...", self.model_name)
            self._model = nemo_asr.models.ASRModel.from_pretrained(
                model_name=self.model_name
            )
            self._model.eval()
        return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> list[Segment]:
        assert sample_rate == config.SAMPLE_RATE, "engine expects 16 kHz audio"
        model = self._load()
        # NeMo decode is not thread-safe; serialize calls.
        with self._lock:
            outputs = model.transcribe([audio], timestamps=True)
        return self._to_segments(outputs)

    @staticmethod
    def _to_segments(outputs) -> list[Segment]:
        segments: list[Segment] = []
        if not outputs:
            return segments
        hyp = outputs[0]
        stamps = (getattr(hyp, "timestamp", None) or {}).get("segment") or []
        for st in stamps:
            text = (st.get("segment") or st.get("text") or "").strip()
            if text:
                segments.append(
                    Segment(start=float(st["start"]), end=float(st["end"]), text=text)
                )
        if not segments:
            text = (getattr(hyp, "text", "") or "").strip()
            if text:
                segments.append(Segment(start=0.0, end=0.0, text=text))
        return segments


class MockEngine:
    """Deterministic fake transcripts for GPU-less development."""

    _WORDS = (
        "okay so let's get started with the roadmap review for this quarter "
        "the main goal is shipping the transcription pipeline and the web app "
        "we still need to finalize diarization and the note enhancement flow "
        "action item alice will benchmark parakeet on the meeting corpus "
        "bob takes the chrome extension audio capture and the websocket client"
    ).split()

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> list[Segment]:
        duration = len(audio) / sample_rate
        # ~2.5 words per second of audio, wrapped into ~8-word segments.
        n_words = max(1, int(duration * 2.5))
        words = [self._WORDS[i % len(self._WORDS)] for i in range(n_words)]
        segments = []
        per_word = duration / n_words
        for i in range(0, n_words, 8):
            chunk = words[i : i + 8]
            segments.append(
                Segment(
                    start=round(i * per_word, 2),
                    end=round(min((i + len(chunk)) * per_word, duration), 2),
                    text=" ".join(chunk),
                )
            )
        return segments


class OnnxParakeetEngine:
    """Parakeet-TDT-0.6b-v2 via the open-source sherpa-onnx runtime.

    Same NVIDIA weights as the NeMo engine, exported to ONNX (int8) — runs in
    real time on CPU. Fetch the model with scripts/get_parakeet_onnx.sh.
    """

    def __init__(self, model_dir=None):
        import sherpa_onnx
        from pathlib import Path

        d = Path(model_dir or config.ONNX_DIR)
        log.info("Loading Parakeet ONNX model from %s ...", d)
        self._rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(next(d.glob("encoder*.onnx"))),
            decoder=str(next(d.glob("decoder*.onnx"))),
            joiner=str(next(d.glob("joiner*.onnx"))),
            tokens=str(d / "tokens.txt"),
            num_threads=os.cpu_count() or 4,
            model_type="nemo_transducer",
        )
        self._lock = threading.Lock()

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> list[Segment]:
        stream = self._rec.create_stream()
        stream.accept_waveform(sample_rate, audio)
        with self._lock:
            self._rec.decode_stream(stream)
        result = stream.result
        return self._to_segments(result, len(audio) / sample_rate)

    @staticmethod
    def _to_segments(result, duration: float, gap: float = 0.8) -> list[Segment]:
        """Group decoded tokens into segments, splitting on silent gaps."""
        tokens = list(getattr(result, "tokens", []) or [])
        stamps = list(getattr(result, "timestamps", []) or [])
        text = (result.text or "").strip()
        if not text:
            return []
        if len(tokens) != len(stamps) or not stamps:
            return [Segment(start=0.0, end=round(duration, 2), text=text)]

        segments: list[Segment] = []
        cur_tokens: list[str] = [tokens[0]]
        cur_start = prev = stamps[0]
        for tok, ts in zip(tokens[1:], stamps[1:]):
            if ts - prev > gap:
                segments.append(_bpe_segment(cur_tokens, cur_start, prev))
                cur_tokens, cur_start = [], ts
            cur_tokens.append(tok)
            prev = ts
        segments.append(_bpe_segment(cur_tokens, cur_start, min(prev + 0.3, duration)))
        return [s for s in segments if s.text]


def _bpe_segment(tokens: list[str], start: float, end: float) -> Segment:
    text = "".join(tokens).replace("▁", " ").strip()
    return Segment(start=round(start, 2), end=round(end, 2), text=text)


_engine: Optional[ASREngine] = None
_engine_lock = threading.Lock()


def nemo_available() -> bool:
    try:
        import nemo.collections.asr  # noqa: F401

        return True
    except Exception:
        return False


def onnx_available() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
    except Exception:
        return False
    return config.ONNX_DIR.is_dir() and any(config.ONNX_DIR.glob("encoder*.onnx"))


def _build_engine() -> ASREngine:
    choice = config.ENGINE
    if choice == "auto":
        if nemo_available():
            choice = "nemo"
        elif onnx_available():
            choice = "onnx"
        else:
            log.warning(
                "No real ASR available — using the mock engine. Install "
                "requirements-nemo.txt (GPU) or run scripts/get_parakeet_onnx.sh "
                "and `pip install sherpa-onnx` (CPU)."
            )
            choice = "mock"
    if choice == "nemo":
        return NemoParakeetEngine()
    if choice == "onnx":
        return OnnxParakeetEngine()
    return MockEngine()


def get_engine() -> ASREngine:
    """Singleton engine chosen by PERCH_ENGINE (auto: nemo > onnx > mock)."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = _build_engine()
        return _engine


def is_mock() -> bool:
    return isinstance(get_engine(), MockEngine)


def engine_name() -> str:
    engine = get_engine()
    if isinstance(engine, NemoParakeetEngine):
        return f"nemo:{config.ASR_MODEL}"
    if isinstance(engine, OnnxParakeetEngine):
        return "onnx:nvidia/parakeet-tdt-0.6b-v2 (sherpa-onnx)"
    return "mock"
