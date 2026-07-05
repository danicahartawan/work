# nvkit

Reusable AI-agent building blocks for NVIDIA knowledge workers, built on the
[NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit) (NAT).

One monorepo, many installable packages. Each package wraps a single external
API as NAT tools plus a specialist agent. Workflows compose the packages into
products for a specific team — the first is the **PR-team workflow**.

## Repository layout

```
nvkit/
├── packages/
│   ├── nvkit-core/           Shared helpers: env/credential handling, NAT compat shims
│   ├── nvkit-redaction/      Google DLP-based text/document redaction
│   ├── nvkit-transcription/  Audio transcription via NVIDIA Riva / Parakeet NIM
│   ├── nvkit-tableau/        Tableau REST API (view data, dashboards)
│   ├── nvkit-wordpress/      WordPress REST API (draft posts)
│   ├── nvkit-meltwater/      Meltwater media-monitoring API
│   └── nvkit-platform/       Control Center: drag-and-drop workflow builder UI
└── workflows/
    └── pr-team/              Orchestrator + 5 specialist agents for the PR team
```

## Control Center (start here)

The fastest way to experience nvkit is the Control Center — a web app where
each API is a pixel "worker" you drag into a mission lane, brief, and deploy.
Missions run instantly in demo mode (no credentials needed) and export to
real NAT `workflow.yml` files.

```bash
pip install -e packages/nvkit-platform
nvkit-platform            # open http://localhost:8100
```

See [`packages/nvkit-platform/README.md`](packages/nvkit-platform/README.md)
for demos to try.

Every package registers its tools through NAT entry points, so any team can
`pip install nvkit-tableau` (or reference it in a uv workspace) and wire the
tools into their own `workflow.yml` — or serve any agent as an MCP/A2A server
for teams that don't want to install anything.

## Quickstart

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install everything (workspace-aware)
uv sync

# 2. Configure credentials — copy and fill in what you have.
#    Tools without credentials return a clear placeholder instead of failing,
#    so the workflow is runnable end-to-end from day one.
cp .env.example .env

# 3. Run the PR-team workflow
export NVIDIA_API_KEY=...   # for the NIM-hosted LLMs
uv run nat run --config_file workflows/pr-team/workflow.yml \
  --input "Search recent media coverage of NVIDIA earnings and draft a WordPress summary post"
```

## Adding a new package

1. Copy an existing package under `packages/` (e.g. `nvkit-meltwater` is the smallest).
2. Rename the project in its `pyproject.toml`, add it to the root `pyproject.toml`
   dependencies and `[tool.uv.sources]`.
3. Define a config class + tool function in `register.py`, and point the
   `nat.plugins.functions` entry point at it.
4. Reference the tool's `_type` in any `workflow.yml`.

## Version note

Imports and entry-point groups follow the NAT v1.8 (mid-2026) plugin API
(`nat.plugin_api`, `nat.plugins.functions`). `nvkit-core` ships a compat shim
(`nvkit_core.compat`) that falls back to the older v1.x import paths, and each
package registers under both the new and legacy entry-point groups. If you pin
a different NAT version and something fails to load, check
`packages/nvkit-core/src/nvkit_core/compat.py` first.
