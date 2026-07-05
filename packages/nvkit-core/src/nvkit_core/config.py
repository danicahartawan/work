"""Environment-based credential helpers.

nvkit tools degrade gracefully: when credentials are absent they return an
explanatory placeholder instead of raising, so workflows stay runnable for
demos and local development before any API access is provisioned.
"""

import os


def require_env(*names: str) -> dict[str, str] | None:
    """Return a dict of the named env vars, or None if any is missing/empty."""
    values = {name: os.environ.get(name, "").strip() for name in names}
    if any(not v for v in values.values()):
        return None
    return values


def missing_credentials_message(tool: str, *names: str) -> str:
    missing = [n for n in names if not os.environ.get(n, "").strip()]
    return (
        f"[{tool}] Not configured: set {', '.join(missing)} in your environment "
        f"(see .env.example). Returning placeholder output so the workflow can proceed."
    )
