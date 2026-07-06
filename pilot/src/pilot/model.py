"""Goal spec: load and lint plain-language readiness goals from YAML."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pilot.questions import DIMENSIONS

EVIDENCE_KINDS = ("cmd_ok", "file_exists", "file_contains", "manual")


class SpecError(Exception):
    """Raised when a goals file cannot be parsed into a Spec at all."""


@dataclass
class Evidence:
    kind: str
    cmd: str = ""
    path: str = ""
    text: str = ""
    note: str = ""

    @classmethod
    def parse(cls, raw: object, goal_id: str) -> "Evidence":
        if not isinstance(raw, dict) or len(raw) != 1:
            raise SpecError(
                f"goal '{goal_id}': each evidence item must be a single-key "
                f"mapping like '- cmd_ok: \"brev --version\"', got: {raw!r}"
            )
        kind, value = next(iter(raw.items()))
        if kind == "cmd_ok":
            return cls(kind=kind, cmd=str(value))
        if kind == "file_exists":
            return cls(kind=kind, path=str(value))
        if kind == "file_contains":
            if not isinstance(value, dict) or "path" not in value or "text" not in value:
                raise SpecError(
                    f"goal '{goal_id}': file_contains needs "
                    "{path: ..., text: ...}"
                )
            return cls(kind=kind, path=str(value["path"]), text=str(value["text"]))
        if kind == "manual":
            return cls(kind=kind, note=str(value))
        raise SpecError(
            f"goal '{goal_id}': unknown evidence kind '{kind}' "
            f"(expected one of {', '.join(EVIDENCE_KINDS)})"
        )

    def describe(self) -> str:
        return {
            "cmd_ok": f"`{self.cmd}` exits successfully",
            "file_exists": f"`{self.path}` exists",
            "file_contains": f"`{self.path}` mentions {self.text!r}",
            "manual": self.note,
        }[self.kind]

    def describe_for_instruction(self) -> str | None:
        """Phrasing safe to show the agent.

        `file_contains` text and `manual` criteria are the verifier's
        answers — showing them verbatim turns a recover/understand goal
        into a copy exercise. The agent only sees which artifacts must
        exist and which commands must work.
        """
        if self.kind == "file_contains":
            return f"`{self.path}` exists and records your findings"
        if self.kind == "manual":
            return None
        return self.describe()


@dataclass
class Goal:
    id: str
    dimension: str
    outcome: str
    context: str = ""
    public_info_only: bool = False
    failure_injection: str = ""
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Product:
    name: str
    summary: str = ""
    org: str = "local"
    docs: list[str] = field(default_factory=list)


@dataclass
class Spec:
    product: Product
    goals: list[Goal]
    agent_timeout_sec: float = 900.0
    verifier_timeout_sec: float = 600.0


def load_spec(path: Path) -> Spec:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise SpecError(f"{path}: not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise SpecError(f"{path}: expected a mapping with 'product' and 'goals'")

    raw_product = data.get("product")
    if not isinstance(raw_product, dict) or not raw_product.get("name"):
        raise SpecError(f"{path}: 'product.name' is required")
    product = Product(
        name=str(raw_product["name"]),
        summary=str(raw_product.get("summary", "")).strip(),
        org=str(raw_product.get("org", "local")),
        docs=[str(d) for d in raw_product.get("docs", [])],
    )

    raw_goals = data.get("goals")
    if not isinstance(raw_goals, list) or not raw_goals:
        raise SpecError(f"{path}: 'goals' must be a non-empty list")

    goals: list[Goal] = []
    for i, raw in enumerate(raw_goals):
        if not isinstance(raw, dict) or not raw.get("id"):
            raise SpecError(f"{path}: goals[{i}] needs an 'id'")
        gid = str(raw["id"])
        goals.append(
            Goal(
                id=gid,
                dimension=str(raw.get("dimension", "")),
                outcome=str(raw.get("outcome", "")).strip(),
                context=str(raw.get("context", "")).strip(),
                public_info_only=bool(raw.get("public_info_only", False)),
                failure_injection=str(raw.get("failure_injection", "")).strip(),
                evidence=[Evidence.parse(e, gid) for e in raw.get("evidence", [])],
            )
        )

    defaults = data.get("defaults") or {}
    return Spec(
        product=product,
        goals=goals,
        agent_timeout_sec=float(defaults.get("agent_timeout_sec", 900.0)),
        verifier_timeout_sec=float(defaults.get("verifier_timeout_sec", 600.0)),
    )


@dataclass
class Finding:
    level: str  # "error" | "warning"
    code: str
    where: str
    message: str


# Outcomes should read as outcomes. These patterns catch click-by-click
# phrasing that belongs in the agent's hands, not the goal.
_STEP_BY_STEP = re.compile(
    r"(step \d|^\s*\d+\.\s|\bclick\b|\bthen run\b|\bfirst,.*\bthen\b)",
    re.IGNORECASE | re.MULTILINE,
)


def lint(spec: Spec) -> list[Finding]:
    findings: list[Finding] = []
    seen_ids: set[str] = set()

    for goal in spec.goals:
        where = f"goal '{goal.id}'"
        if goal.id in seen_ids:
            findings.append(Finding("error", "E102", where, "duplicate goal id"))
        seen_ids.add(goal.id)

        if goal.dimension not in DIMENSIONS:
            findings.append(
                Finding(
                    "error", "E101", where,
                    f"dimension must be one of {', '.join(DIMENSIONS)} "
                    f"(got {goal.dimension!r})",
                )
            )
        if not goal.outcome:
            findings.append(Finding("error", "E100", where, "missing 'outcome'"))
        if not goal.evidence:
            findings.append(
                Finding(
                    "error", "E103", where,
                    "no evidence — a goal with no observable success criteria "
                    "compiles to a task that can't be verified",
                )
            )
        if goal.dimension == "recover" and not goal.failure_injection:
            findings.append(
                Finding(
                    "error", "E104", where,
                    "recover goals need 'failure_injection' describing the "
                    "broken state the environment starts in",
                )
            )
        if goal.outcome and _STEP_BY_STEP.search(goal.outcome):
            findings.append(
                Finding(
                    "warning", "W201", where,
                    "outcome reads like step-by-step instructions; state the "
                    "end state and let the agent find the steps",
                )
            )
        if goal.outcome and len(goal.outcome.split()) < 8:
            findings.append(
                Finding(
                    "warning", "W202", where,
                    "outcome is very short — is it specific enough that "
                    "failure would mean something?",
                )
            )
        agent_visible = f"{goal.outcome} {goal.context}".lower()
        for e in goal.evidence:
            if e.kind == "file_contains" and e.text.lower() in agent_visible:
                findings.append(
                    Finding(
                        "warning", "W206", where,
                        f"the verifier greps for {e.text!r} and the agent-"
                        "visible outcome/context contains that string — the "
                        "task grades copying, not understanding",
                    )
                )
        if goal.evidence and all(e.kind == "manual" for e in goal.evidence):
            findings.append(
                Finding(
                    "warning", "W203", where,
                    "all evidence is manual — add at least one deterministic "
                    "check (cmd_ok / file_exists / file_contains) so the task "
                    "can pass in CI without a human",
                )
            )

    covered = {g.dimension for g in spec.goals}
    missing = [d for d in DIMENSIONS if d not in covered]
    if missing:
        findings.append(
            Finding(
                "warning", "W204", "dataset",
                f"no goals for dimension(s): {', '.join(missing)} — an agent "
                "that can execute but not discover (or recover) is not ready",
            )
        )
    if not any(g.public_info_only for g in spec.goals):
        findings.append(
            Finding(
                "warning", "W205", "dataset",
                "no public_info_only goal — add one if you want to compare "
                "against other products on public-info readiness",
            )
        )
    return findings
