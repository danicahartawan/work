"""Catalog of nvkit agent workers exposed to the Control Center UI.

Each entry maps a UI "worker" to the underlying nvkit package: the NAT tool
``_type`` it compiles to on export, the env vars that flip it from DEMO to
LIVE mode, and presentation metadata (codename, color, skills).
"""

import os

AGENTS = [
    {
        "id": "meltwater",
        "codename": "Scout",
        "api": "Meltwater",
        "tagline": "Media monitoring — finds every mention before anyone else does",
        "tool_type": "nvkit_meltwater_search",
        "tool_defaults": {"days_back": 7},
        "color": "#3ec6ff",
        "skills": ["coverage search", "sentiment sweep", "outlet tracking"],
        "env": ["MELTWATER_API_TOKEN"],
    },
    {
        "id": "transcription",
        "codename": "Scribe",
        "api": "NVIDIA Riva ASR",
        "tagline": "Turns interviews and briefings into text, on NVIDIA hardware",
        "tool_type": "nvkit_transcribe_audio",
        "tool_defaults": {"language_code": "en-US"},
        "color": "#ffd166",
        "skills": ["audio transcription", "speaker notes", "briefing capture"],
        "env": ["RIVA_SERVER"],
    },
    {
        "id": "redaction",
        "codename": "Cipher",
        "api": "Google Cloud DLP",
        "tagline": "Scrubs PII and embargoed details before anything goes out",
        "tool_type": "nvkit_redact_text",
        "tool_defaults": {},
        "color": "#ef476f",
        "skills": ["PII redaction", "embargo scrub", "release safety"],
        "env": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT"],
    },
    {
        "id": "tableau",
        "codename": "Vizzy",
        "api": "Tableau",
        "tagline": "Pulls the numbers behind any dashboard you can name",
        "tool_type": "nvkit_tableau_view_data",
        "tool_defaults": {"max_rows": 200},
        "color": "#8338ec",
        "skills": ["dashboard data", "metric pulls", "trend summaries"],
        "env": ["TABLEAU_SERVER_URL", "TABLEAU_SITE_ID", "TABLEAU_PAT_NAME", "TABLEAU_PAT_SECRET"],
    },
    {
        "id": "wordpress",
        "codename": "Quill",
        "api": "WordPress",
        "tagline": "Drafts posts for human review — never hits publish",
        "tool_type": "nvkit_wordpress_create_draft",
        "tool_defaults": {},
        "color": "#06d6a0",
        "skills": ["draft posts", "newsroom updates", "release notes"],
        "env": ["WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD"],
    },
]

AGENT_INDEX = {agent["id"]: agent for agent in AGENTS}


def roster() -> list[dict]:
    """Agents plus their current DEMO/LIVE state, for the UI."""
    return [
        {**agent, "live": all(os.environ.get(v, "").strip() for v in agent["env"])}
        for agent in AGENTS
    ]
