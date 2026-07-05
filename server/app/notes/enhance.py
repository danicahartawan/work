"""Granola-style note enhancement.

Takes the user's rough in-meeting notes plus the full transcript and produces
polished structured notes. Uses an NVIDIA Nemotron open-weights model served
behind any OpenAI-compatible endpoint (vLLM, Ollama, NIM). When no endpoint is
configured, a dependency-free extractive fallback still produces useful notes.
"""

from __future__ import annotations

import logging

import httpx

from .. import config
from ..models import Meeting, Segment

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a meticulous meeting-notes assistant. You receive a meeting transcript
and the user's rough notes typed during the meeting. Produce polished notes in
Markdown that:
- Keep every point from the user's rough notes, expanded/corrected using the transcript.
- Add a short "Summary" section (2-4 sentences) at the top.
- Add "Decisions" and "Action items" sections (with owners when identifiable).
- Attribute key points to speakers when speaker labels exist.
- Never invent facts that are in neither the notes nor the transcript.
Return only the Markdown notes."""


def format_transcript(segments: list[Segment]) -> str:
    lines = []
    for seg in segments:
        who = f"{seg.speaker}: " if seg.speaker else ""
        lines.append(f"[{_ts(seg.start)}] {who}{seg.text}")
    return "\n".join(lines)


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


async def enhance_notes(meeting: Meeting, segments: list[Segment]) -> tuple[str, bool]:
    """Return (enhanced_markdown, used_llm)."""
    transcript = format_transcript(segments)
    if config.LLM_BASE_URL:
        try:
            return await _enhance_with_nemotron(meeting, transcript), True
        except Exception:
            log.exception("Nemotron enhancement failed; using extractive fallback")
    return _extractive_fallback(meeting, segments), False


async def _enhance_with_nemotron(meeting: Meeting, transcript: str) -> str:
    user_prompt = (
        f"Meeting title: {meeting.title}\n\n"
        f"## User's rough notes\n{meeting.notes_md or '(none)'}\n\n"
        f"## Transcript\n{transcript}"
    )
    async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as client:
        resp = await client.post(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={
                "model": config.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def _extractive_fallback(meeting: Meeting, segments: list[Segment]) -> str:
    """No-LLM notes: metadata, the user's notes, and the longest utterances."""
    speakers = sorted({s.speaker for s in segments if s.speaker})
    duration = max((s.end for s in segments), default=0.0)
    highlights = sorted(segments, key=lambda s: len(s.text), reverse=True)[:8]
    highlights.sort(key=lambda s: s.start)

    out = [f"# {meeting.title}", "", "## Summary"]
    out.append(
        f"Meeting of {_ts(duration)} with "
        f"{', '.join(speakers) if speakers else 'unlabeled speakers'}. "
        "(Configure PERCH_LLM_BASE_URL with a Nemotron endpoint for AI-written notes.)"
    )
    if meeting.notes_md.strip():
        out += ["", "## Your notes", meeting.notes_md.strip()]
    out += ["", "## Highlights from the transcript"]
    for seg in highlights:
        who = f"**{seg.speaker}** — " if seg.speaker else ""
        out.append(f"- [{_ts(seg.start)}] {who}{seg.text}")
    return "\n".join(out)
