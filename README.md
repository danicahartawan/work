# 🪶 Perch

Granola-style meeting notes, built entirely on **NVIDIA's open-source AI stack**.
Record a meeting (from the web app or the Chrome extension), watch the live
transcript stream in, type rough notes while you talk — then let the model
rewrite them into polished, structured notes grounded in the transcript.

Everything runs on **your own hardware**. No audio ever leaves your machines.

## The NVIDIA stack (all open source)

| Task | Model | License |
| --- | --- | --- |
| Speech-to-text | [`nvidia/parakeet-tdt-0.6b-v2`](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) — top open-source model on the HF Open ASR leaderboard | CC-BY-4.0 |
| Speaker diarization | [`nvidia/diar_sortformer_4spk-v1`](https://huggingface.co/nvidia/diar_sortformer_4spk-v1) (NeMo Sortformer) | CC-BY-NC-4.0 |
| Note enhancement | Any [Nemotron](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1) open-weights model behind an OpenAI-compatible endpoint (vLLM / Ollama / NIM) | NVIDIA Open Model License |

### ASR engines (`PERCH_ENGINE`)

Perch runs Parakeet through your choice of engine — same NVIDIA weights,
different runtimes:

| Engine | Runtime | Hardware | Setup |
| --- | --- | --- | --- |
| `nemo` | NVIDIA NeMo | GPU (CUDA) | `pip install -r requirements-nemo.txt` |
| `onnx` | [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (open source), int8 export of the same Parakeet model | **CPU**, real-time | `pip install -r requirements-onnx.txt && ./scripts/get_parakeet_onnx.sh` |
| `mock` | — | any | nothing; synthetic transcripts for UI development |

`PERCH_ENGINE=auto` (default) picks `nemo` when installed, else `onnx` when
weights are present, else `mock`. Diarization currently requires the NeMo
engine.

## Repo layout

```
server/     FastAPI backend: live WebSocket transcription, batch re-transcription,
            diarization, note enhancement, SQLite storage       (Python + NeMo)
web/        Granola-style web app: notes editor + live transcript (React + Vite)
extension/  Chrome MV3 extension: capture any meeting tab's audio (+ your mic)
            and stream it to the server
```

## Quick start (no GPU needed — mock ASR)

Try the whole product loop on any machine; the server fakes transcripts until
NeMo is installed:

```bash
# 1. Server
cd server
pip install -r requirements.txt
PERCH_MOCK_ASR=1 uvicorn app.main:app --port 8000

# 2. Web app (separate terminal)
cd web
npm install
npm run dev        # http://localhost:5173 (proxies /api and /ws to :8000)
```

Create a meeting, hit **Record**, allow the mic, talk — segments appear live.
Type rough notes on the left, then **✨ Enhance notes**.

## Real transcription (GPU)

```bash
cd server
pip install -r requirements.txt -r requirements-nemo.txt
uvicorn app.main:app --port 8000
```

or with Docker:

```bash
docker compose up --build      # needs nvidia-container-toolkit
```

The first request downloads Parakeet (~2.4 GB) and Sortformer from Hugging
Face into the cache. `GET /api/health` shows which engine is active.

### AI-written notes with Nemotron

Point Perch at any OpenAI-compatible endpoint serving a Nemotron model:

```bash
# example: vLLM on the same box
vllm serve nvidia/Llama-3.1-Nemotron-Nano-8B-v1 --port 9000

PERCH_LLM_BASE_URL=http://localhost:9000/v1 uvicorn app.main:app --port 8000
```

Without an endpoint, **Enhance notes** falls back to a built-in extractive
summary so the flow still works.

## Chrome extension

1. Open `chrome://extensions`, enable *Developer mode*, **Load unpacked** → pick `extension/`.
2. Open your meeting tab (Google Meet, Zoom web, …).
3. Click the Perch icon → **Record this tab**. Tab audio (everyone else) and
   your mic are mixed and streamed to the server; live captions show in the
   popup, and the full meeting appears in the web app.

## How live transcription works

1. The browser captures mic (+ tab/system audio), resamples to 16 kHz in an
   `AudioContext`, and an `AudioWorklet` converts it to 16-bit PCM.
2. PCM frames stream over `ws://…/ws/meetings/{id}/audio`.
3. The server endpoints utterances by voice activity; each open utterance is
   re-decoded with Parakeet every ~2 s (`partial` events) and committed on
   silence (`final` events).
4. On stop, the whole recording is saved to WAV, re-transcribed in a single
   Parakeet pass for maximum accuracy, and diarized with Sortformer — the live
   transcript is replaced by the polished, speaker-labeled one.
5. **Enhance notes** sends your rough notes + the transcript to Nemotron,
   which rewrites them into structured notes (summary, decisions, action
   items) without inventing facts.

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `PERCH_ASR_MODEL` | `nvidia/parakeet-tdt-0.6b-v2` | NeMo ASR model |
| `PERCH_DIAR_MODEL` | `nvidia/diar_sortformer_4spk-v1` | Diarization model |
| `PERCH_DIARIZATION` | `1` | Disable with `0` |
| `PERCH_MOCK_ASR` | `0` | Force mock engine (auto when NeMo is missing) |
| `PERCH_LLM_BASE_URL` | *(empty)* | OpenAI-compatible endpoint for Nemotron |
| `PERCH_LLM_MODEL` | `nvidia/Llama-3.1-Nemotron-Nano-8B-v1` | Chat model name |
| `PERCH_DATA_DIR` | `data/` | SQLite DB + WAV recordings |
| `PERCH_STREAM_DECODE_INTERVAL` | `2.0` | Seconds between live re-decodes |
| `PERCH_STREAM_SILENCE_SEC` | `0.8` | Silence that finalizes an utterance |

## API sketch

```
GET    /api/health
GET    /api/meetings                     POST /api/meetings
GET    /api/meetings/{id}                PATCH/DELETE /api/meetings/{id}
GET    /api/meetings/{id}/segments
POST   /api/meetings/{id}/enhance        # rewrite notes with Nemotron
POST   /api/transcribe                   # one-shot file upload
WS     /ws/meetings/{id}/audio           # 16 kHz mono PCM16 in, JSON events out
```
