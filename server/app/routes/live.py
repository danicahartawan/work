"""Live transcription WebSocket.

Protocol (client -> server):
  binary frames : 16 kHz mono signed 16-bit little-endian PCM
  text frames   : JSON control messages, currently {"type": "stop"}

Server -> client JSON events:
  {"type": "partial", "segment": {...}}   in-progress utterance (text may change)
  {"type": "final",   "segment": {...}}   utterance committed to the transcript
  {"type": "status",  "status": "recording" | "processing" | "done"}
  {"type": "segments_replaced"}           full-pass transcript is ready; refetch

After "stop" (or disconnect) the recording is saved to WAV and, when NeMo is
available, re-transcribed in one pass with Parakeet and diarized with
Sortformer for a polished, speaker-labeled transcript.
"""

from __future__ import annotations

import asyncio
import json
import logging

import numpy as np
import soundfile as sf
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import config, db
from ..asr import diarize
from ..asr.engine import get_engine, is_mock
from ..asr.streaming import StreamingTranscriber

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/meetings/{meeting_id}/audio")
async def live_audio(ws: WebSocket, meeting_id: str):
    await ws.accept()
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        await ws.close(code=4404, reason="meeting not found")
        return

    db.update_meeting(meeting_id, status="recording")
    await ws.send_text(json.dumps({"type": "status", "status": "recording"}))

    transcriber = StreamingTranscriber()
    chunks: list[bytes] = []
    stopped_by_client = False
    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if (data := message.get("bytes")) is not None:
                chunks.append(data)
                for event in await transcriber.feed(data):
                    await _send_event(ws, event)
            elif (text := message.get("text")) is not None:
                if json.loads(text).get("type") == "stop":
                    stopped_by_client = True
                    break
    except WebSocketDisconnect:
        pass
    finally:
        for event in await transcriber.flush():
            if stopped_by_client:
                await _send_event(ws, event, best_effort=True)
            else:  # socket gone; just persist
                _persist(meeting_id, event)
        await _finish(ws if stopped_by_client else None, meeting_id, chunks, transcriber)


async def _send_event(ws: WebSocket, event, best_effort: bool = False) -> None:
    if event.kind == "final":
        _persist(ws.path_params["meeting_id"], event)
    payload = {"type": event.kind, "segment": event.segment.model_dump()}
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:
        if not best_effort:
            raise


def _persist(meeting_id: str, event) -> None:
    event.segment.meeting_id = meeting_id
    db.add_segment(event.segment)


async def _finish(
    ws: WebSocket | None,
    meeting_id: str,
    chunks: list[bytes],
    transcriber: StreamingTranscriber,
) -> None:
    duration = transcriber.position
    db.update_meeting(meeting_id, status="processing", duration=duration)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "status", "status": "processing"}))
        except Exception:
            ws = None

    wav_path = _save_wav(meeting_id, chunks)
    replaced = False
    if wav_path and not is_mock():
        try:
            replaced = await _full_pass(meeting_id, wav_path)
        except Exception:
            log.exception("Full-pass transcription failed; keeping live segments")

    db.update_meeting(meeting_id, status="done")
    if ws:
        try:
            if replaced:
                await ws.send_text(json.dumps({"type": "segments_replaced"}))
            await ws.send_text(json.dumps({"type": "status", "status": "done"}))
            await ws.close()
        except Exception:
            pass


def _save_wav(meeting_id: str, chunks: list[bytes]) -> str | None:
    if not chunks:
        return None
    config.ensure_dirs()
    pcm = np.frombuffer(b"".join(chunks), dtype=np.int16)
    path = config.AUDIO_DIR / f"{meeting_id}.wav"
    sf.write(path, pcm, config.SAMPLE_RATE, subtype="PCM_16")
    return str(path)


async def _full_pass(meeting_id: str, wav_path: str) -> bool:
    """Polish the transcript: batch Parakeet decode + Sortformer speakers."""
    loop = asyncio.get_running_loop()
    audio, _ = sf.read(wav_path, dtype="float32")
    segments = await loop.run_in_executor(
        None, get_engine().transcribe, audio, config.SAMPLE_RATE
    )
    if not segments:
        return False
    diarizer = diarize.get_diarizer()
    if diarizer:
        turns = await loop.run_in_executor(None, diarizer.diarize_file, wav_path)
        diarize.assign_speakers(segments, turns)
    db.replace_segments(meeting_id, segments)
    return True
