# nvkit Missions

The platform layer of nvkit: a **mobile app (installable PWA)** where knowledge
workers build their own agent workflows by **tapping pixel "workers" to recruit
them onto a mission squad**, briefing each one, and watching them report back —
Composio-style API building blocks, but with a specialized AI agent per API and
a game-like squad app on top.

Three tabs: **SQUAD** (tap a worker to recruit), **MISSION** (brief each step,
reorder, deploy), **REPORT** (live log + final report). A status strip shows
whichever worker is currently deployed, bouncing while it works.

**Install on a phone:** deploy the server (any container host — it's one
process on `$NVKIT_PORT`), open the URL in Safari/Chrome, and use
*Add to Home Screen*. It launches full-screen with its own pixel icon like a
native app (manifest + service worker included). Want it in the app stores
later? Wrap it with Capacitor — no code change needed. It also works fine in
a desktop browser as a centered phone-style column.

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

Open http://localhost:8100 (or the installed home-screen app) and:

1. **One-tap preset** — on MISSION, tap `★ Briefing → Blog`, then
   `▶ RUN MISSION`. It jumps to REPORT: watch Scribe transcribe, Cipher
   *actually redact* the phone number and email in the transcript (real regex
   redaction, even in demo mode), and Quill produce a draft with an edit link.
2. **Build from scratch** — on SQUAD, tap **Scout** to recruit it, then
   **Cipher**. On MISSION, brief Scout "negative coverage of GPU supply
   chain" and deploy. Each worker hands its report to the next.
3. **Remix a preset** — load `★ Coverage Digest`, reorder steps with
   ▲ UP / ▼ DOWN, change the mission brief to your own topic, run, then
   `✚ SAVE PRESET` so it becomes a one-tap chip for next time.
4. **Ship it to engineering** — `⬇ NAT YAML` downloads the exact same
   pipeline as a NeMo Agent Toolkit `workflow.yml`, runnable with
   `nat run --config_file <file> --input "..."` once the nvkit packages'
   API calls are live. The squad app and the NAT runtime are two views
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
