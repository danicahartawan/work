"""Live transcription over a stream of 16 kHz mono PCM16 audio.

Strategy: energy-based endpointing splits the stream into utterances. While
an utterance is open, the current utterance buffer is re-decoded every
``STREAM_DECODE_INTERVAL`` seconds and emitted as a *partial* segment (its
text may still change). When silence closes the utterance — or it hits the
max length — one last decode emits the *final* segment. This trades a couple
of seconds of latency for full Parakeet accuracy on every utterance, and it
works identically with the mock engine.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import numpy as np

from .. import config
from ..models import Segment
from .engine import get_engine

# Frames quieter than this RMS (on int16-normalized floats) count as silence.
SILENCE_RMS = 0.010
FRAME_SEC = 0.05  # endpointing granularity


@dataclass
class TranscriptEvent:
    segment: Segment
    kind: str  # "partial" | "final"


@dataclass
class StreamingTranscriber:
    """Feed PCM16 bytes in, get partial/final transcript events out."""

    sample_rate: int = config.SAMPLE_RATE
    _pending: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    _utterance: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    _utterance_start: float = 0.0  # stream-relative seconds
    _stream_pos: float = 0.0
    _silence: float = 0.0
    _since_decode: float = 0.0
    _heard_speech: bool = False

    async def feed(self, pcm16: bytes) -> list[TranscriptEvent]:
        """Consume raw PCM16 bytes; return any new transcript events."""
        samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        self._pending = np.concatenate([self._pending, samples])

        events: list[TranscriptEvent] = []
        frame_len = int(FRAME_SEC * self.sample_rate)
        while len(self._pending) >= frame_len:
            frame, self._pending = self._pending[:frame_len], self._pending[frame_len:]
            events.extend(await self._push_frame(frame))
        return events

    async def flush(self) -> list[TranscriptEvent]:
        """Finalize whatever is buffered (stream ended)."""
        if len(self._pending):
            self._utterance = np.concatenate([self._utterance, self._pending])
            self._stream_pos += len(self._pending) / self.sample_rate
            self._pending = np.zeros(0, dtype=np.float32)
        return await self._finalize()

    @property
    def position(self) -> float:
        return self._stream_pos

    async def _push_frame(self, frame: np.ndarray) -> list[TranscriptEvent]:
        rms = float(np.sqrt(np.mean(frame**2)))
        is_silence = rms < SILENCE_RMS

        if not self._heard_speech and is_silence and len(self._utterance) == 0:
            # Leading silence: skip it entirely so timestamps stay tight.
            self._stream_pos += FRAME_SEC
            self._utterance_start = self._stream_pos
            return []

        self._heard_speech = self._heard_speech or not is_silence
        self._utterance = np.concatenate([self._utterance, frame])
        self._stream_pos += FRAME_SEC
        self._silence = self._silence + FRAME_SEC if is_silence else 0.0
        self._since_decode += FRAME_SEC

        utt_sec = len(self._utterance) / self.sample_rate
        if self._heard_speech and (
            self._silence >= config.STREAM_SILENCE_SEC
            or utt_sec >= config.STREAM_MAX_UTTERANCE_SEC
        ):
            return await self._finalize()
        if self._heard_speech and self._since_decode >= config.STREAM_DECODE_INTERVAL:
            self._since_decode = 0.0
            seg = await self._decode()
            return [TranscriptEvent(seg, "partial")] if seg else []
        return []

    async def _decode(self) -> Segment | None:
        audio = self._utterance
        if len(audio) < self.sample_rate * 0.3:  # too short to bother
            return None
        loop = asyncio.get_running_loop()
        segments = await loop.run_in_executor(
            None, get_engine().transcribe, audio, self.sample_rate
        )
        text = " ".join(s.text for s in segments).strip()
        if not text:
            return None
        return Segment(
            start=round(self._utterance_start, 2),
            end=round(self._utterance_start + len(audio) / self.sample_rate, 2),
            text=text,
            final=False,
        )

    async def _finalize(self) -> list[TranscriptEvent]:
        seg = await self._decode()
        self._utterance = np.zeros(0, dtype=np.float32)
        self._utterance_start = self._stream_pos
        self._silence = 0.0
        self._since_decode = 0.0
        self._heard_speech = False
        if seg is None:
            return []
        seg.final = True
        return [TranscriptEvent(seg, "final")]
