"""Batch ASR engines.

The real engine wraps NVIDIA NeMo's Parakeet-TDT-0.6b-v2 — the strongest
open-source (CC-BY-4.0) English ASR model on the Hugging Face Open ASR
leaderboard. A mock engine keeps the whole app usable on machines without
NeMo or a GPU so the UI and extension can be developed anywhere.
"""

from __future__ import annotations

import logging
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


_engine: Optional[ASREngine] = None
_engine_lock = threading.Lock()


def nemo_available() -> bool:
    try:
        import nemo.collections.asr  # noqa: F401

        return True
    except Exception:
        return False


def get_engine() -> ASREngine:
    """Singleton engine: Parakeet when NeMo is installed, mock otherwise."""
    global _engine
    with _engine_lock:
        if _engine is None:
            if not config.MOCK_ASR and nemo_available():
                _engine = NemoParakeetEngine()
            else:
                if not config.MOCK_ASR:
                    log.warning(
                        "NeMo is not installed — falling back to the mock ASR "
                        "engine. Install server/requirements-nemo.txt for real "
                        "transcription."
                    )
                _engine = MockEngine()
        return _engine


def is_mock() -> bool:
    return isinstance(get_engine(), MockEngine)
