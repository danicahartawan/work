"""Pydantic schemas shared by the REST and WebSocket APIs."""

from typing import Literal, Optional

from pydantic import BaseModel


class Segment(BaseModel):
    """One utterance of the transcript."""

    id: Optional[int] = None
    meeting_id: Optional[str] = None
    start: float
    end: float
    speaker: Optional[str] = None
    text: str
    final: bool = True


class Meeting(BaseModel):
    id: str
    title: str
    created_at: str
    status: Literal["idle", "recording", "processing", "done"] = "idle"
    duration: float = 0.0
    notes_md: str = ""
    enhanced_notes_md: str = ""


class MeetingCreate(BaseModel):
    title: str = "Untitled meeting"


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    notes_md: Optional[str] = None
    enhanced_notes_md: Optional[str] = None


class EnhanceResponse(BaseModel):
    enhanced_notes_md: str
    used_llm: bool


class TranscribeResponse(BaseModel):
    segments: list[Segment]
    duration: float
