"""Unit tests for engine-independent ASR logic (no model weights needed)."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from app.asr.diarize import SpeakerTurn, assign_speakers
from app.asr.engine import MockEngine, OnnxParakeetEngine
from app.asr.streaming import StreamingTranscriber
from app.models import Meeting, Segment
from app.notes.enhance import _extractive_fallback, format_transcript


def test_onnx_segment_grouping_splits_on_gaps():
    result = SimpleNamespace(
        text="hello world again",
        tokens=["▁hel", "lo", "▁world", "▁again"],
        timestamps=[0.0, 0.2, 0.5, 2.0],  # 1.5s gap before "again"
    )
    segs = OnnxParakeetEngine._to_segments(result, duration=3.0)
    assert [s.text for s in segs] == ["hello world", "again"]
    assert segs[0].start == 0.0 and segs[1].start == 2.0
    assert segs[1].end <= 3.0


def test_onnx_segment_grouping_without_timestamps():
    result = SimpleNamespace(text="just text", tokens=[], timestamps=[])
    segs = OnnxParakeetEngine._to_segments(result, duration=4.2)
    assert len(segs) == 1 and segs[0].text == "just text" and segs[0].end == 4.2


def test_onnx_empty_result():
    result = SimpleNamespace(text="", tokens=[], timestamps=[])
    assert OnnxParakeetEngine._to_segments(result, duration=1.0) == []


@pytest.fixture(autouse=True)
def mock_engine(monkeypatch):
    engine = MockEngine()
    monkeypatch.setattr("app.asr.streaming.get_engine", lambda: engine)


def _pcm(seconds: float, amplitude: float) -> bytes:
    n = int(16000 * seconds)
    tone = (amplitude * 32767 * np.sin(2 * np.pi * 220 * np.arange(n) / 16000)).astype(
        np.int16
    )
    return tone.tobytes()


def test_streaming_endpoints_on_silence():
    async def run():
        t = StreamingTranscriber()
        events = []
        for blob in (_pcm(3, 0.3), _pcm(1.5, 0.0), _pcm(2, 0.3)):
            events += await t.feed(blob)
        events += await t.flush()
        return events, t.position

    events, position = asyncio.run(run())
    finals = [e for e in events if e.kind == "final"]
    partials = [e for e in events if e.kind == "partial"]
    assert len(finals) == 2, "silence should split two utterances"
    assert partials, "long speech should emit partial updates"
    assert all(f.segment.final for f in finals)
    assert abs(position - 6.5) < 0.1
    # second utterance starts after the silence gap
    assert finals[1].segment.start > finals[0].segment.end - 0.01


def test_streaming_skips_leading_silence():
    async def run():
        t = StreamingTranscriber()
        events = await t.feed(_pcm(2, 0.0))  # nothing but silence
        events += await t.flush()
        return events

    assert asyncio.run(run()) == []


def test_assign_speakers_by_overlap():
    segs = [
        Segment(start=0.0, end=4.0, text="a"),
        Segment(start=4.0, end=8.0, text="b"),
    ]
    turns = [
        SpeakerTurn(0.0, 4.2, "speaker_1"),
        SpeakerTurn(4.2, 8.0, "speaker_0"),
    ]
    out = assign_speakers(segs, turns)
    # relabelled in order of first appearance
    assert out[0].speaker == "Speaker 1" and out[1].speaker == "Speaker 2"


def test_fallback_notes_include_user_notes_and_highlights():
    meeting = Meeting(
        id="m1", title="Sync", created_at="2026-01-01T00:00:00Z", notes_md="- ship it"
    )
    segs = [
        Segment(start=0, end=5, text="we should ship the roadmap next week", speaker="Speaker 1"),
        Segment(start=5, end=6, text="yes", speaker="Speaker 2"),
    ]
    md = _extractive_fallback(meeting, segs)
    assert "ship it" in md and "roadmap" in md and "## Summary" in md
    assert "Speaker 1" in md


def test_format_transcript_timestamps():
    line = format_transcript([Segment(start=65, end=70, text="hi", speaker="S1")])
    assert line == "[1:05] S1: hi"
