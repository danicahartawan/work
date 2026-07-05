"""Mission engine: runs pipelines built in the Control Center.

Two execution paths:

- **Demo mode** (always available): each agent has a simulator that produces
  realistic output and passes it as context to the next step, so users can
  build and feel a whole workflow before any API credential exists. The
  redaction simulator does real regex redaction on the incoming context.
- **Live mode**: agents whose env vars are set will eventually call the real
  nvkit tools. Until those TODO(nvkit) API calls land, live agents also run
  their simulator, minus the demo banner.

Every pipeline can also be compiled to a NAT ``workflow.yml`` via
:func:`to_nat_yaml`, so anything built visually is runnable with ``nat run``.
"""

import asyncio
import random
import re
import time
import uuid

import yaml

from nvkit_platform.registry import AGENT_INDEX

# Mirrors nvkit_redaction's fallback patterns (not imported: the platform
# stays runnable without NAT installed).
REDACTION_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

DEMO_OUTLETS = ["Reuters", "Bloomberg", "The Verge", "TechCrunch", "WSJ", "CNBC", "Axios"]


def _topic(instruction: str, context: str) -> str:
    words = re.findall(r"[A-Za-z0-9'&-]+", instruction or context or "")
    return " ".join(words[:8]) or "the assigned topic"


def _demo_banner(agent: dict) -> str:
    return f"[demo data — set {', '.join(agent['env'])} to go live]"


def _sim_meltwater(instruction: str, context: str) -> str:
    topic = _topic(instruction, context)
    rng = random.Random(topic)  # stable per topic, varied across topics
    outlets = rng.sample(DEMO_OUTLETS, 4)
    pos, neg = rng.randint(45, 70), rng.randint(5, 20)
    lines = [
        f"Scout report — coverage scan: \"{topic}\" (last 7 days)",
        "",
        f"- {outlets[0]}: \"{topic.title()} draws analyst attention\" — https://example.com/a1",
        f"- {outlets[1]}: \"What {topic} means for the industry\" — https://example.com/a2",
        f"- {outlets[2]}: \"Five takeaways on {topic}\" — https://example.com/a3",
        f"- {outlets[3]}: \"Opinion: the quiet story behind {topic}\" — https://example.com/a4",
        "",
        f"Volume: {rng.randint(30, 90)} articles. Sentiment: {pos}% positive / "
        f"{100 - pos - neg}% neutral / {neg}% negative.",
    ]
    return "\n".join(lines)


def _sim_transcription(instruction: str, context: str) -> str:
    topic = _topic(instruction, context)
    return (
        f"Scribe transcript — {topic}\n\n"
        "[00:00] HOST: Thanks everyone for joining on short notice.\n"
        f"[00:12] SPEAKER 1: The headline is simple — {topic} exceeded our internal targets, "
        "and we're ready to talk about it publicly next week.\n"
        "[01:04] SPEAKER 2: Press inquiries should route through comms — my direct line is "
        "415-555-0142 and email is jdoe@example.com until then.\n"
        "[01:40] HOST: We'll circulate the embargoed notes right after this call.\n\n"
        "(2 speakers + host, 1m52s, punctuation on)"
    )


def _sim_redaction(instruction: str, context: str) -> str:
    source = context or instruction
    redacted, hits = source, 0
    for pattern in REDACTION_PATTERNS.values():
        redacted, n = pattern.subn("[REDACTED]", redacted)
        hits += n
    return (
        f"Cipher report — {hits} sensitive item(s) redacted "
        "(emails, phone numbers, SSNs)\n\n" + redacted
    )


def _sim_tableau(instruction: str, context: str) -> str:
    topic = _topic(instruction, context)
    rng = random.Random(topic)
    base = rng.randint(800, 2200)
    rows = "\n".join(
        f"| Week {i + 1} | {base + rng.randint(-150, 400) * (i + 1):,} | {rng.randint(58, 92)}% |"
        for i in range(4)
    )
    return (
        f"Vizzy pull — view matching \"{topic}\"\n\n"
        "| Period | Impressions (k) | Positive share |\n"
        "|---|---|---|\n" + rows + "\n\n"
        "Trend: impressions climbing week-over-week; positive share stable."
    )


def _sim_wordpress(instruction: str, context: str) -> str:
    title = _topic(instruction, context).title()
    excerpt = (context or "Draft body goes here.").strip()
    if len(excerpt) > 400:
        excerpt = excerpt[:400] + " …"
    post_id = random.randint(1000, 9999)
    return (
        f"Quill report — DRAFT created (never auto-published)\n\n"
        f"Title: {title}\n"
        f"Status: draft, awaiting human review\n"
        f"Edit: https://newsroom.example.com/wp-admin/post.php?post={post_id}&action=edit\n\n"
        f"--- excerpt ---\n{excerpt}"
    )


SIMULATORS = {
    "meltwater": _sim_meltwater,
    "transcription": _sim_transcription,
    "redaction": _sim_redaction,
    "tableau": _sim_tableau,
    "wordpress": _sim_wordpress,
}


# ---------------------------------------------------------------- run engine

def new_run(spec) -> dict:
    return {
        "id": uuid.uuid4().hex[:8],
        "name": spec.name,
        "input": spec.input,
        "status": "queued",
        "steps": [
            {
                "agent_id": s.agent_id,
                "instruction": s.instruction,
                "status": "queued",
                "output": "",
            }
            for s in spec.steps
        ],
        "log": [],
        "report": "",
    }


def _log(run: dict, msg: str) -> None:
    run["log"].append({"t": time.strftime("%H:%M:%S"), "msg": msg})


async def execute(run: dict) -> None:
    run["status"] = "running"
    _log(run, f"Mission '{run['name']}' launched — {len(run['steps'])} step(s)")
    context = run["input"]
    for step in run["steps"]:
        agent = AGENT_INDEX[step["agent_id"]]
        step["status"] = "working"
        brief = step["instruction"] or agent["tagline"]
        _log(run, f"{agent['codename']} deployed → {brief[:80]}")
        await asyncio.sleep(random.uniform(1.2, 2.4))  # let the UI breathe
        try:
            live = all(_env_set(v) for v in agent["env"])
            output = SIMULATORS[agent["id"]](step["instruction"], context)
            if not live:
                output += "\n\n" + _demo_banner(agent)
            step["output"] = output
            step["status"] = "done"
            _log(run, f"{agent['codename']} reported back ({'LIVE' if live else 'demo'})")
            context = output
        except Exception as exc:  # surface, don't crash the server
            step["status"] = "failed"
            step["output"] = f"{agent['codename']} failed: {exc}"
            run["status"] = "failed"
            _log(run, f"{agent['codename']} FAILED: {exc}")
            return
    run["report"] = context
    run["status"] = "complete"
    _log(run, "Mission complete ✓ — final report ready")


def _env_set(name: str) -> bool:
    import os

    return bool(os.environ.get(name, "").strip())


# ---------------------------------------------------------------- NAT export

def to_nat_yaml(spec) -> str:
    """Compile a Control Center pipeline into a runnable NAT workflow.yml."""
    llms = {
        "orchestrator_llm": {
            "_type": "nim",
            "model_name": "meta/llama-3.3-70b-instruct",
            "temperature": 0.0,
            "max_tokens": 2048,
        },
        "worker_llm": {
            "_type": "nim",
            "model_name": "meta/llama-3.3-70b-instruct",
            "temperature": 0.0,
            "max_tokens": 2048,
        },
    }
    functions: dict = {}
    agent_names: list[str] = []
    for idx, step in enumerate(spec.steps, start=1):
        agent = AGENT_INDEX[step.agent_id]
        tool_name = f"{agent['id']}_tool"
        functions[tool_name] = {"_type": agent["tool_type"], **agent["tool_defaults"]}
        agent_name = f"step{idx}_{agent['id']}_agent"
        functions[agent_name] = {
            "_type": "tool_calling_agent",
            "description": step.instruction or agent["tagline"],
            "tool_names": [tool_name],
            "llm_name": "worker_llm",
            "verbose": True,
            "handle_tool_errors": True,
        }
        agent_names.append(agent_name)
    config = {
        "llms": llms,
        "functions": functions,
        "workflow": {
            "_type": "react_agent",
            "llm_name": "orchestrator_llm",
            "tool_names": agent_names,
            "verbose": True,
            "handle_parsing_errors": True,
            "max_retries": 2,
        },
    }
    header = (
        f"# Exported from nvkit Control Center — mission: {spec.name}\n"
        f"# Run with: nat run --config_file <this file> --input \"{spec.input or '...'}\"\n"
    )
    return header + yaml.safe_dump(config, sort_keys=False)
