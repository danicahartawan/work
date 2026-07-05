# nvkit Control Center

The platform layer of nvkit: a web app where knowledge workers build their own
agent workflows by **dragging pixel "workers" into a mission lane**, briefing
each one, and watching them report back — Composio-style API building blocks,
but with a specialized AI agent per API and a game-like control center on top.

Every worker maps to an nvkit package:

| Worker | API | Package |
|---|---|---|
| **Scout** | Meltwater media monitoring | `nvkit-meltwater` |
| **Scribe** | NVIDIA Riva ASR transcription | `nvkit-transcription` |
| **Cipher** | Google Cloud DLP redaction | `nvkit-redaction` |
| **Vizzy** | Tableau dashboards | `nvkit-tableau` |
| **Quill** | WordPress drafting | `nvkit-wordpress` |

## Run it

```bash
pip install -e packages/nvkit-platform   # or: uv sync
nvkit-platform                            # serves http://localhost:8100
```

No credentials needed — every worker runs in **DEMO mode** with realistic
simulated output so people can build and feel whole workflows immediately.
Setting a worker's env vars (see `.env.example`) flips its badge to **LIVE**.

## Demos to try

Open http://localhost:8100 and:

1. **One-click preset** — click `★ Briefing → Blog`, then `▶ RUN MISSION`.
   Watch Scribe transcribe, Cipher *actually redact* the phone number and
   email in the transcript (real regex redaction, even in demo mode), and
   Quill produce a draft with an edit link.
2. **Build from scratch** — drag **Scout** into the lane, brief it
   "negative coverage of GPU supply chain", drag **Cipher** below it, hit run.
   Each worker hands its report to the next.
3. **Remix a preset** — load `★ Coverage Digest`, reorder steps with ▲▼,
   change the mission brief to your own topic, run, then `✚ SAVE AS PRESET`
   so it becomes a one-click chip for next time.
4. **Ship it to engineering** — `⬇ EXPORT NAT YAML` downloads the exact same
   pipeline as a NeMo Agent Toolkit `workflow.yml`, runnable with
   `nat run --config_file <file> --input "..."` once the nvkit packages'
   API calls are live. The visual builder and the NAT runtime are two views
   of one workflow.

Fun bits: workers level up (LV badge) each time they complete a mission, and
the roster animates whoever is currently deployed.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/agents` | roster + DEMO/LIVE state |
| `GET/POST /api/workflows` | saved missions (3 presets seeded) |
| `POST /api/runs` → `GET /api/runs/{id}` | launch + poll a mission |
| `POST /api/export` | compile a pipeline to NAT `workflow.yml` |

## Architecture notes

- `registry.py` — the worker catalog; adding a sixth API = one nvkit package
  plus one entry here, and it appears in the roster automatically.
- `engine.py` — mission runner. Demo simulators pass context step-to-step
  today; live execution slots into the same loop once the `TODO(nvkit)` API
  calls in each package land.
- The server is stateless-ish (in-memory runs/workflows) by design — you said
  deployment is handled, so persistence is the obvious first hardening step.
