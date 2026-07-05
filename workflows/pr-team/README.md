# PR-team workflow

The first nvkit product: an assistant for PR/communications staff that routes
plain-language requests to five specialist agents, one per external API.

```
orchestrator (react_agent)
├── redaction_agent      → Google Cloud DLP        (nvkit-redaction)
├── transcription_agent  → NVIDIA Riva / Parakeet  (nvkit-transcription)
├── tableau_agent        → Tableau REST API        (nvkit-tableau)
├── wordpress_agent      → WordPress REST API      (nvkit-wordpress)
└── meltwater_agent      → Meltwater API           (nvkit-meltwater)
```

## Run it

```bash
export NVIDIA_API_KEY=...        # LLM access via build.nvidia.com
uv run nat run --config_file workflows/pr-team/workflow.yml \
  --input "What's our media coverage on Blackwell this week?"
```

Tools whose credentials aren't set return a placeholder explaining what to
configure, so you can demo the routing before any API access is provisioned.

## Example requests

- "Redact the PII from this statement before we send it out: ..."
- "Transcribe /data/briefings/2026-07-01-analyst-call.wav"
- "Pull the 'Media Impressions Q2' Tableau view and summarize the trend"
- "Draft a WordPress post announcing the developer-conference keynote"
- "Any negative coverage of our earnings in the last 7 days?"

## Design guardrails

- The WordPress agent only creates **drafts** — publishing stays human.
- Transcription uses NVIDIA-hosted ASR so embargoed audio never leaves
  company infrastructure.
- Each specialist agent sees only its own API's tools, so credentials and
  blast radius stay compartmentalized per agent.
