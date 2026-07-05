"""Perch server — Granola-style meeting transcription on NVIDIA's open stack.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db
from .asr.engine import engine_name, is_mock
from .routes import live, meetings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Perch", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings.router)
app.include_router(live.router)


@app.on_event("startup")
def startup() -> None:
    config.ensure_dirs()
    db.connect()


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "asr_engine": engine_name(),
        "diarization": config.DIARIZATION_ENABLED and not is_mock(),
        "llm_configured": bool(config.LLM_BASE_URL),
    }
