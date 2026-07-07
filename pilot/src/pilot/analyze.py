"""Turn a product's docs and user sentiment into draft readiness goals.

Deterministic, dependency-light heuristics — no LLM required, so the wizard
runs offline and its suggestions are reproducible (an onboarding tool a team
can't predict is one they won't trust). Every function here is pure and
unit-tested; an LLM backend can later replace `analyze_docs` /
`analyze_sentiment` behind the same signatures without touching the wizard.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# --- docs --------------------------------------------------------------------

# Ordered most-specific-first: the first match wins as the "install command".
_INSTALL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("curl-installer", re.compile(r"curl\s+[^\n|]*\|\s*(?:sudo\s+)?(?:ba)?sh", re.I)),
    ("uv-tool", re.compile(r"uv\s+tool\s+install\s+([\w.-]+)", re.I)),
    ("uv-pip", re.compile(r"uv\s+pip\s+install\s+([\w.-]+)", re.I)),
    ("pipx", re.compile(r"pipx\s+install\s+([\w.-]+)", re.I)),
    ("pip", re.compile(r"pip3?\s+install\s+([\w.-]+)", re.I)),
    ("brew", re.compile(r"brew\s+install\s+(?:[\w-]+/[\w-]+/)?([\w.-]+)", re.I)),
    ("npm", re.compile(r"npm\s+(?:install|i)\s+-g\s+([\w./@-]+)", re.I)),
    ("go", re.compile(r"go\s+install\s+([\w./@-]+)", re.I)),
    ("pixi", re.compile(r"pixi\s+global\s+install\s+([\w.-]+)", re.I)),
    ("cargo", re.compile(r"cargo\s+install\s+([\w.-]+)", re.I)),
]

_CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)


@dataclass
class DocSignals:
    install_command: str = ""
    install_kind: str = ""
    binary: str = ""
    actions: list[str] = field(default_factory=list)  # top CLI subcommands seen
    sources: list[str] = field(default_factory=list)


def _binary_from(kind: str, pkg: str, fallback: str) -> str:
    if kind in ("curl-installer",):
        return fallback
    if kind == "go":  # github.com/org/foo-cli@latest -> foo-cli
        return re.split(r"[@]", pkg)[0].rstrip("/").split("/")[-1]
    if kind == "npm":
        return pkg.split("/")[-1]
    return pkg


def analyze_docs(text: str, product_slug: str = "") -> DocSignals:
    """Extract an install command and the product's common CLI actions."""
    sig = DocSignals()

    for kind, pat in _INSTALL_PATTERNS:
        m = pat.search(text)
        if m:
            sig.install_kind = kind
            sig.install_command = m.group(0).strip()
            pkg = m.group(1).strip() if m.groups() else product_slug
            sig.binary = _binary_from(kind, pkg, product_slug) or product_slug
            break
    if not sig.binary:
        sig.binary = product_slug

    # Collect command lines from code blocks once, then figure out which
    # binary they invoke. A curl-installer yields no package name, so the
    # binary is often only discoverable from the usage examples: take the
    # most common leading token that isn't a shell builtin.
    _SHELL = {"cd", "export", "sudo", "source", "curl", "wget", "echo", "cat",
              "ls", "mkdir", "rm", "cp", "mv", "chmod", "git", "pip", "pip3",
              "uv", "npm", "go", "brew", "bash", "sh", "python", "python3"}
    cmd_lines: list[list[str]] = []
    lead: Counter[str] = Counter()
    for block in _CODE_BLOCK.findall(text):
        for line in block.splitlines():
            line = line.strip().lstrip("$ ").strip()
            toks = line.split()
            if len(toks) >= 2 and re.fullmatch(r"[a-z][\w-]+", toks[0]):
                cmd_lines.append(toks)
                if toks[0] not in _SHELL:
                    lead[toks[0]] += 1

    bin_guess = sig.binary or product_slug
    # If the guessed binary never appears as a command, trust the examples.
    if bin_guess not in lead and lead:
        bin_guess = lead.most_common(1)[0][0]
        sig.binary = bin_guess

    verbs: Counter[str] = Counter()
    for toks in cmd_lines:
        if toks[0] == bin_guess and len(toks) >= 2:
            sub = toks[1]
            if re.fullmatch(r"[a-z][\w-]+", sub) and sub not in (
                "--help", "-h", "--version", "help"
            ):
                verbs[sub] += 1
    sig.actions = [v for v, _ in verbs.most_common(5)]
    return sig


# --- sentiment ---------------------------------------------------------------

# theme -> (matched keywords, readiness dimension the pain maps to)
_THEMES: dict[str, tuple[tuple[str, ...], str]] = {
    "install/setup": (("install", "setup", "download", "not found", "path", "binary"), "discover"),
    "auth/access": (("login", "auth", "token", "credential", "403", "forbidden", "permission", "unauthorized"), "understand"),
    "errors/crashes": (("error", "crash", "fail", "broken", "traceback", "exception", "500"), "recover"),
    "hangs/timeouts": (("hang", "timeout", "stuck", "freeze", "never returns", "waiting"), "recover"),
    "confusion/docs": (("confusing", "unclear", "how do i", "no docs", "undocumented", "which command"), "understand"),
    "networking": (("proxy", "network", "connection", "vpn", "firewall", "dns"), "recover"),
}

_NEGATIVE = re.compile(
    r"\b(can'?t|cannot|won'?t|fail(?:s|ed|ing)?|error|broken|bug|stuck|"
    r"confus\w*|useless|frustrat\w*|impossible|doesn'?t work|hate|annoying)\b",
    re.I,
)


@dataclass
class PainPoint:
    theme: str
    dimension: str
    count: int
    examples: list[str] = field(default_factory=list)


def load_sentiment(path: Path) -> list[str]:
    """Read sentiment items from JSON array, JSONL, or one-per-line text."""
    raw = path.read_text().strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x.get("title", x)) if isinstance(x, dict) else str(x) for x in data]
    except json.JSONDecodeError:
        pass
    return [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("#")]


def analyze_sentiment(items: list[str]) -> list[PainPoint]:
    """Cluster negative signals by theme, ranked by frequency."""
    hits: dict[str, PainPoint] = {}
    for item in items:
        low = item.lower()
        negative = bool(_NEGATIVE.search(low))
        for theme, (keywords, dim) in _THEMES.items():
            if any(k in low for k in keywords):
                pp = hits.setdefault(theme, PainPoint(theme, dim, 0))
                # weight explicitly negative mentions higher
                pp.count += 2 if negative else 1
                if len(pp.examples) < 3:
                    pp.examples.append(item.strip())
    return sorted(hits.values(), key=lambda p: p.count, reverse=True)


# --- task drafting -----------------------------------------------------------

@dataclass
class GoalDraft:
    id: str
    dimension: str
    outcome: str
    evidence: list[dict]
    public_info_only: bool = False
    context: str = ""
    failure_injection: str = ""
    rationale: str = ""  # why the wizard suggested this; not written to YAML


def suggest_tasks(
    product_name: str,
    docs: DocSignals,
    pains: list[PainPoint],
) -> list[GoalDraft]:
    """Propose exactly three starter tasks spanning discover/understand/recover."""
    binary = docs.binary or _slug(product_name)
    drafts: list[GoalDraft] = []

    # 1. discover — can an agent find and install it from public info?
    install_note = (
        f"docs show `{docs.install_command}`" if docs.install_command
        else "no install command detected in the docs provided — that gap is itself a finding"
    )
    drafts.append(GoalDraft(
        id="discover-install",
        dimension="discover",
        public_info_only=True,
        outcome=(
            f"Starting from nothing but public internet access, an agent can find, "
            f"install, and prove that {product_name} runs on a clean Linux box."
        ),
        context="Measures whether public docs/registries are findable enough to bootstrap.",
        evidence=[
            {"cmd_ok": f"{binary} --version"},
            {"file_exists": "/app/notes/install-source.md"},
            {"manual": "install-source.md cites an official source, not a third-party blog."},
        ],
        rationale=f"From docs: {install_note}.",
    ))

    # 2. understand — pick the most common documented action, else generic.
    action = docs.actions[0] if docs.actions else ""
    if action:
        outcome = (
            f"From public documentation alone, an agent can determine how to "
            f"'{action}' with {product_name} and record the exact command it would "
            f"run, with a one-line justification."
        )
        rationale = f"'{action}' is the most frequent CLI action in the docs."
    else:
        outcome = (
            f"From public documentation alone, an agent can determine the single "
            f"correct command for {product_name}'s core outcome and record it with "
            f"a justification."
        )
        rationale = "No dominant CLI action detected; generic understand goal."
    drafts.append(GoalDraft(
        id=f"understand-{_slug(action) or 'core-action'}",
        dimension="understand",
        public_info_only=True,
        outcome=outcome,
        context="Measures whether the docs specify one correct way, not three conflicting ones.",
        evidence=[
            {"file_exists": "/app/notes/command.md"},
            {"manual": "the recorded command is valid per current docs and cites its source."},
        ],
        rationale=rationale,
    ))

    # 3. recover — driven by the top user pain point.
    if pains:
        top = pains[0]
        outcome = (
            f"When an agent hits the '{top.theme}' failure that {product_name} users "
            f"most commonly report, it can diagnose the problem from the error output "
            f"alone and write a recovery plan that names the documented remediation "
            f"instead of retrying blindly."
        )
        failure = (
            f"The environment starts in the broken state behind the most-reported "
            f"'{top.theme}' complaints. Representative user reports: "
            + "; ".join(f'"{e}"' for e in top.examples[:2])
        )
        gid = f"recover-{_slug(top.theme)}"
        rationale = f"Top user pain point ({top.count} weighted mentions): {top.theme}."
        dim_note = top.dimension
    else:
        outcome = (
            f"When the first {product_name} command an agent runs fails, it can "
            f"diagnose the failure from the error output and write a recovery plan "
            f"that names the documented remediation."
        )
        failure = (
            "No sentiment source provided — replace this with the failure new users "
            "most commonly hit (e.g. missing credentials, wrong flag)."
        )
        gid = "recover-first-failure"
        rationale = "No sentiment data; generic recover goal seeded for you to refine."
        dim_note = "recover"

    drafts.append(GoalDraft(
        id=gid,
        dimension="recover",
        failure_injection=failure,
        outcome=outcome,
        evidence=[
            {"file_exists": "/app/notes/recovery.md"},
            {"manual": "recovery plan quotes the actual error observed; matches current docs."},
        ],
        rationale=rationale + (f" (maps to {dim_note})" if dim_note != "recover" else ""),
    ))

    return drafts


def drafts_to_goals_yaml(
    product_name: str,
    org: str,
    docs: DocSignals,
    drafts: list[GoalDraft],
) -> str:
    """Serialize into the goals.yaml shape that load_spec/lint consume."""
    goals: list[dict] = []
    for d in drafts:
        g: dict = {"id": d.id, "dimension": d.dimension}
        if d.public_info_only:
            g["public_info_only"] = True
        if d.failure_injection:
            g["failure_injection"] = d.failure_injection
        g["outcome"] = d.outcome.strip()
        if d.context:
            g["context"] = d.context
        g["evidence"] = d.evidence
        goals.append(g)

    doc = {
        "product": {
            "name": product_name,
            "org": org,
            "summary": "",
            "docs": docs.sources,
        },
        "goals": goals,
    }
    header = (
        "# Generated by `pilot wizard` from your docs and user sentiment.\n"
        "# These are STARTING POINTS — review every outcome and replace each\n"
        "# `manual:` line with a real check before trusting results.\n"
        "# Run `pilot lint` next.\n\n"
    )
    return header + yaml.dump(doc, sort_keys=False, width=88, allow_unicode=True)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
