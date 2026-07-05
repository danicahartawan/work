"""nvkit Control Center server.

Serves the drag-and-drop mission builder UI and the API behind it:
agent roster, saved workflows (missions), runs, and NAT YAML export.

    uv run nvkit-platform          # or: python -m nvkit_platform.app
    open http://localhost:8100
"""

import asyncio
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nvkit_platform import engine, registry

app = FastAPI(title="nvkit Control Center", version="0.1.0")


class StepSpec(BaseModel):
    agent_id: str
    instruction: str = ""


class WorkflowSpec(BaseModel):
    name: str = "Untitled mission"
    input: str = ""
    steps: list[StepSpec] = Field(default_factory=list)


# In-memory stores. Fine for a single-user control center; swap for a DB when
# this grows multi-user.
RUNS: dict[str, dict] = {}
WORKFLOWS: dict[str, dict] = {}


def _seed_presets() -> None:
    presets = [
        WorkflowSpec(
            name="Coverage Digest",
            input="NVIDIA Q2 earnings",
            steps=[
                StepSpec(agent_id="meltwater", instruction="Scan the last 7 days of coverage on NVIDIA Q2 earnings"),
                StepSpec(agent_id="tableau", instruction="Pull the 'Media Impressions Q2' view and add the numbers"),
                StepSpec(agent_id="wordpress", instruction="Draft an internal digest post: Weekly Coverage Digest :: <summary>"),
            ],
        ),
        WorkflowSpec(
            name="Briefing → Blog",
            input="/data/briefings/2026-07-01-analyst-call.wav",
            steps=[
                StepSpec(agent_id="transcription", instruction="Transcribe the analyst briefing audio"),
                StepSpec(agent_id="redaction", instruction="Redact PII and embargoed details from the transcript"),
                StepSpec(agent_id="wordpress", instruction="Draft a recap post from the clean transcript"),
            ],
        ),
        WorkflowSpec(
            name="Crisis Watch",
            input="supply chain rumors",
            steps=[
                StepSpec(agent_id="meltwater", instruction="Find negative coverage mentioning supply chain rumors"),
                StepSpec(agent_id="redaction", instruction="Scrub PII before circulating the alert"),
            ],
        ),
    ]
    for spec in presets:
        wf_id = uuid.uuid4().hex[:8]
        WORKFLOWS[wf_id] = {"id": wf_id, "preset": True, **spec.model_dump()}


_seed_presets()


def _validate(spec: WorkflowSpec) -> None:
    if not spec.steps:
        raise HTTPException(422, "Mission needs at least one step — drag an agent in.")
    for step in spec.steps:
        if step.agent_id not in registry.AGENT_INDEX:
            raise HTTPException(422, f"Unknown agent: {step.agent_id}")


@app.get("/api/agents")
def get_agents() -> list[dict]:
    return registry.roster()


@app.get("/api/workflows")
def list_workflows() -> list[dict]:
    return list(WORKFLOWS.values())


@app.post("/api/workflows")
def save_workflow(spec: WorkflowSpec) -> dict:
    _validate(spec)
    wf_id = uuid.uuid4().hex[:8]
    WORKFLOWS[wf_id] = {"id": wf_id, "preset": False, **spec.model_dump()}
    return WORKFLOWS[wf_id]


@app.delete("/api/workflows/{wf_id}")
def delete_workflow(wf_id: str) -> dict:
    if wf_id not in WORKFLOWS:
        raise HTTPException(404, "No such workflow")
    if WORKFLOWS[wf_id]["preset"]:
        raise HTTPException(403, "Presets can't be deleted")
    del WORKFLOWS[wf_id]
    return {"deleted": wf_id}


@app.post("/api/runs")
async def start_run(spec: WorkflowSpec) -> dict:
    _validate(spec)
    run = engine.new_run(spec)
    RUNS[run["id"]] = run
    asyncio.get_running_loop().create_task(engine.execute(run))
    return {"run_id": run["id"]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "No such run")
    return run


@app.post("/api/export", response_class=PlainTextResponse)
def export_yaml(spec: WorkflowSpec) -> str:
    _validate(spec)
    return engine.to_nat_yaml(spec)


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")


def main() -> None:
    import uvicorn

    port = int(os.environ.get("NVKIT_PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
