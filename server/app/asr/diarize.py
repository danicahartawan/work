"""Speaker diarization with NVIDIA Sortformer (open source, NeMo).

Runs an end-to-end diarization pass over the finished recording and assigns
each transcript segment the speaker whose turns overlap it the most.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from .. import config
from ..models import Segment

log = logging.getLogger(__name__)


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str


class SortformerDiarizer:
    def __init__(self, model_name: str = config.DIARIZATION_MODEL):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            from nemo.collections.asr.models import SortformerEncLabelModel

            log.info("Loading Sortformer diarization model %s ...", self.model_name)
            self._model = SortformerEncLabelModel.from_pretrained(self.model_name)
            self._model.eval()
        return self._model

    def diarize_file(self, wav_path: str) -> list[SpeakerTurn]:
        model = self._load()
        with self._lock:
            outputs = model.diarize(audio=[wav_path], batch_size=1)
        turns: list[SpeakerTurn] = []
        # NeMo returns, per input file, a list of "start end speaker_N" strings.
        for line in outputs[0] if outputs else []:
            try:
                start_s, end_s, spk = str(line).split()
                turns.append(SpeakerTurn(float(start_s), float(end_s), spk))
            except ValueError:
                log.warning("Unparseable diarization line: %r", line)
        return turns


_diarizer: Optional[SortformerDiarizer] = None
_diarizer_lock = threading.Lock()


def get_diarizer() -> Optional[SortformerDiarizer]:
    """Sortformer when available and enabled, otherwise None (skip diarization)."""
    global _diarizer
    if not config.DIARIZATION_ENABLED:
        return None
    with _diarizer_lock:
        if _diarizer is None:
            try:
                from nemo.collections.asr.models import SortformerEncLabelModel  # noqa: F401
            except Exception:
                log.info("NeMo diarization unavailable; speaker labels disabled.")
                return None
            _diarizer = SortformerDiarizer()
        return _diarizer


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> list[Segment]:
    """Label each segment with the most-overlapping speaker turn."""
    if not turns:
        return segments
    for seg in segments:
        overlaps: dict[str, float] = {}
        for turn in turns:
            ov = min(seg.end, turn.end) - max(seg.start, turn.start)
            if ov > 0:
                overlaps[turn.speaker] = overlaps.get(turn.speaker, 0.0) + ov
        if overlaps:
            seg.speaker = max(overlaps, key=overlaps.get)
    _relabel(segments)
    return segments


def _relabel(segments: list[Segment]) -> None:
    """Rename raw speaker ids to Speaker 1..N in order of first appearance."""
    names: dict[str, str] = {}
    for seg in segments:
        if seg.speaker and seg.speaker not in names:
            names[seg.speaker] = f"Speaker {len(names) + 1}"
    for seg in segments:
        if seg.speaker:
            seg.speaker = names[seg.speaker]
