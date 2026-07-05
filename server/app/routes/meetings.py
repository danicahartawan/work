"""REST API: meeting CRUD, transcript access, file transcription, enhancement."""

from __future__ import annotations

import asyncio
import io
import logging

import numpy as np
import soundfile as sf
from fastapi import APIRouter, HTTPException, UploadFile

from .. import config, db
from ..asr.engine import get_engine
from ..models import (
    EnhanceResponse,
    Meeting,
    MeetingCreate,
    MeetingUpdate,
    Segment,
    TranscribeResponse,
)
from ..notes.enhance import enhance_notes

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/meetings", response_model=list[Meeting])
def meetings_list():
    return db.list_meetings()


@router.post("/meetings", response_model=Meeting)
def meetings_create(body: MeetingCreate):
    return db.create_meeting(body.title)


@router.get("/meetings/{meeting_id}", response_model=Meeting)
def meetings_get(meeting_id: str):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(404, "meeting not found")
    return meeting


@router.patch("/meetings/{meeting_id}", response_model=Meeting)
def meetings_update(meeting_id: str, body: MeetingUpdate):
    meeting = db.update_meeting(meeting_id, **body.model_dump(exclude_unset=True))
    if not meeting:
        raise HTTPException(404, "meeting not found")
    return meeting


@router.delete("/meetings/{meeting_id}")
def meetings_delete(meeting_id: str):
    db.delete_meeting(meeting_id)
    (config.AUDIO_DIR / f"{meeting_id}.wav").unlink(missing_ok=True)
    return {"ok": True}


@router.get("/meetings/{meeting_id}/segments", response_model=list[Segment])
def segments_list(meeting_id: str):
    return db.list_segments(meeting_id)


@router.post("/meetings/{meeting_id}/enhance", response_model=EnhanceResponse)
async def meetings_enhance(meeting_id: str):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(404, "meeting not found")
    segments = db.list_segments(meeting_id)
    if not segments:
        raise HTTPException(400, "meeting has no transcript yet")
    markdown, used_llm = await enhance_notes(meeting, segments)
    db.update_meeting(meeting_id, enhanced_notes_md=markdown)
    return EnhanceResponse(enhanced_notes_md=markdown, used_llm=used_llm)


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_upload(file: UploadFile):
    """One-shot transcription of an uploaded audio file (wav/flac/ogg...)."""
    raw = await file.read()
    try:
        audio, rate = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
    except Exception as exc:
        raise HTTPException(400, f"could not decode audio: {exc}") from exc
    mono = audio.mean(axis=1)
    if rate != config.SAMPLE_RATE:
        mono = _resample(mono, rate, config.SAMPLE_RATE)
    loop = asyncio.get_running_loop()
    segments = await loop.run_in_executor(
        None, get_engine().transcribe, mono, config.SAMPLE_RATE
    )
    return TranscribeResponse(
        segments=segments, duration=len(mono) / config.SAMPLE_RATE
    )


def _resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Linear-interpolation resample; fine for speech ASR input."""
    n_out = int(len(audio) * dst / src)
    x_out = np.linspace(0, len(audio) - 1, n_out)
    return np.interp(x_out, np.arange(len(audio)), audio).astype(np.float32)
