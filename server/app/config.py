"""Server configuration, sourced from environment variables."""

import os
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(int(default))).lower() in ("1", "true", "yes", "on")


# Where meeting audio and the SQLite database live.
DATA_DIR = Path(os.environ.get("PERCH_DATA_DIR", "data")).resolve()
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "perch.db"

# --- ASR (NVIDIA Parakeet, open source) --------------------------------------
# Batch model: best-in-class open ASR on the HF Open ASR leaderboard (CC-BY-4.0).
ASR_MODEL = os.environ.get("PERCH_ASR_MODEL", "nvidia/parakeet-tdt-0.6b-v2")
# Engine selection:
#   auto  - NeMo (GPU-class) if installed, else ONNX (CPU-friendly) if weights
#           are present, else the mock engine
#   nemo  - NVIDIA NeMo + Parakeet from Hugging Face
#   onnx  - sherpa-onnx runtime + Parakeet ONNX weights (see
#           scripts/get_parakeet_onnx.sh); great CPU real-time performance
#   mock  - synthetic transcripts for UI development on any machine
ENGINE = os.environ.get("PERCH_ENGINE", "auto").lower()
# Directory holding encoder/decoder/joiner .onnx + tokens.txt for engine=onnx.
ONNX_DIR = Path(
    os.environ.get("PERCH_ONNX_DIR", "models/parakeet-tdt-0.6b-v2-onnx")
).resolve()
# Back-compat alias for PERCH_ENGINE=mock.
MOCK_ASR = _bool("PERCH_MOCK_ASR", False)
if MOCK_ASR:
    ENGINE = "mock"
# Incremental decode cadence for live transcription (seconds of new audio
# between re-decodes of the open utterance).
STREAM_DECODE_INTERVAL = float(os.environ.get("PERCH_STREAM_DECODE_INTERVAL", "2.0"))
# Energy-based endpointing: an utterance is finalized after this much silence.
STREAM_SILENCE_SEC = float(os.environ.get("PERCH_STREAM_SILENCE_SEC", "0.8"))
# Hard cap on a single utterance before it is force-finalized.
STREAM_MAX_UTTERANCE_SEC = float(os.environ.get("PERCH_STREAM_MAX_UTTERANCE_SEC", "30"))

# --- Diarization (NVIDIA Sortformer, open source) ----------------------------
DIARIZATION_MODEL = os.environ.get("PERCH_DIAR_MODEL", "nvidia/diar_sortformer_4spk-v1")
DIARIZATION_ENABLED = _bool("PERCH_DIARIZATION", True)

# --- Note enhancement (NVIDIA Nemotron open-weights via OpenAI-compatible API)
# Point at any OpenAI-compatible server hosting a Nemotron model:
#   vLLM:   vllm serve nvidia/Llama-3.1-Nemotron-Nano-8B-v1
#   Ollama: ollama run nemotron-mini
# Leave LLM_BASE_URL empty to use the built-in extractive fallback summarizer.
LLM_BASE_URL = os.environ.get("PERCH_LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("PERCH_LLM_MODEL", "nvidia/Llama-3.1-Nemotron-Nano-8B-v1")
LLM_API_KEY = os.environ.get("PERCH_LLM_API_KEY", "not-needed")
LLM_TIMEOUT = float(os.environ.get("PERCH_LLM_TIMEOUT", "120"))

# Audio format expected on the live WebSocket: 16 kHz mono signed 16-bit PCM.
SAMPLE_RATE = 16000

CORS_ORIGINS = os.environ.get("PERCH_CORS_ORIGINS", "*").split(",")


def ensure_dirs() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
