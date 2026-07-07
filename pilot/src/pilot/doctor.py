"""Preflight checks for a team's first run — the #1 onboarding failure is a
half-set-up environment, so surface it before the wizard, not during.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    level: str  # "required" | "recommended"
    detail: str
    fix: str = ""


def _harbor_version() -> str | None:
    exe = shutil.which("harbor")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--version", "--no-check-latest"],
            capture_output=True, text=True, timeout=30,
        )
        return (out.stdout + out.stderr).strip().splitlines()[0] if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def run_checks() -> list[Check]:
    checks: list[Check] = []

    py_ok = sys.version_info >= (3, 12)
    checks.append(Check(
        "python >= 3.12", py_ok, "required",
        f"found {sys.version_info.major}.{sys.version_info.minor}",
        fix="Harbor requires Python 3.12+; use uv/pyenv to get it.",
    ))

    hv = _harbor_version()
    checks.append(Check(
        "harbor CLI installed", hv is not None, "required",
        hv or "not on PATH",
        fix="uv tool install harbor  (or: pip install harbor)",
    ))

    docker = shutil.which("docker") is not None
    checks.append(Check(
        "docker available", docker, "recommended",
        "found" if docker else "not on PATH",
        fix="Install Docker to execute tasks locally later; not needed to author them.",
    ))

    return checks


def summarize(checks: list[Check]) -> tuple[int, int]:
    """Return (blocking_failures, warnings)."""
    blocking = sum(1 for c in checks if not c.ok and c.level == "required")
    warnings = sum(1 for c in checks if not c.ok and c.level == "recommended")
    return blocking, warnings
