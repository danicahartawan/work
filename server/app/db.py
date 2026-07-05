"""SQLite persistence for meetings and transcript segments."""

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import config
from .models import Meeting, Segment

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    duration REAL NOT NULL DEFAULT 0,
    notes_md TEXT NOT NULL DEFAULT '',
    enhanced_notes_md TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    start REAL NOT NULL,
    end REAL NOT NULL,
    speaker TEXT,
    text TEXT NOT NULL,
    final INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_segments_meeting ON segments(meeting_id, start);
"""


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.ensure_dirs()
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def _row_to_meeting(row: sqlite3.Row) -> Meeting:
    return Meeting(**{k: row[k] for k in row.keys()})


def _row_to_segment(row: sqlite3.Row) -> Segment:
    d = {k: row[k] for k in row.keys()}
    d["final"] = bool(d["final"])
    return Segment(**d)


def create_meeting(title: str) -> Meeting:
    meeting = Meeting(
        id=uuid.uuid4().hex[:12],
        title=title,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with _lock:
        connect().execute(
            "INSERT INTO meetings (id, title, created_at, status) VALUES (?, ?, ?, ?)",
            (meeting.id, meeting.title, meeting.created_at, meeting.status),
        )
        connect().commit()
    return meeting


def list_meetings() -> list[Meeting]:
    rows = connect().execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
    return [_row_to_meeting(r) for r in rows]


def get_meeting(meeting_id: str) -> Optional[Meeting]:
    row = connect().execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    return _row_to_meeting(row) if row else None


def update_meeting(meeting_id: str, **fields) -> Optional[Meeting]:
    fields = {k: v for k, v in fields.items() if v is not None}
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        with _lock:
            connect().execute(
                f"UPDATE meetings SET {cols} WHERE id = ?", (*fields.values(), meeting_id)
            )
            connect().commit()
    return get_meeting(meeting_id)


def delete_meeting(meeting_id: str) -> None:
    with _lock:
        connect().execute("DELETE FROM segments WHERE meeting_id = ?", (meeting_id,))
        connect().execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        connect().commit()


def add_segment(seg: Segment) -> Segment:
    with _lock:
        cur = connect().execute(
            "INSERT INTO segments (meeting_id, start, end, speaker, text, final)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (seg.meeting_id, seg.start, seg.end, seg.speaker, seg.text, int(seg.final)),
        )
        connect().commit()
    seg.id = cur.lastrowid
    return seg


def list_segments(meeting_id: str) -> list[Segment]:
    rows = connect().execute(
        "SELECT * FROM segments WHERE meeting_id = ? ORDER BY start", (meeting_id,)
    ).fetchall()
    return [_row_to_segment(r) for r in rows]


def replace_segments(meeting_id: str, segments: list[Segment]) -> list[Segment]:
    """Swap live segments for the polished full-pass transcript."""
    with _lock:
        conn = connect()
        conn.execute("DELETE FROM segments WHERE meeting_id = ?", (meeting_id,))
        for seg in segments:
            seg.meeting_id = meeting_id
            cur = conn.execute(
                "INSERT INTO segments (meeting_id, start, end, speaker, text, final)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (meeting_id, seg.start, seg.end, seg.speaker, seg.text, int(seg.final)),
            )
            seg.id = cur.lastrowid
        conn.commit()
    return segments
