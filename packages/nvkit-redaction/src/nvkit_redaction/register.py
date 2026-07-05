import re

from pydantic import Field

from nvkit_core import missing_credentials_message, require_env
from nvkit_core.compat import Builder, FunctionBaseConfig, FunctionInfo, register_function

ENV_VARS = ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT")

# Local fallback patterns used only when Google DLP is not configured.
FALLBACK_PATTERNS = {
    "EMAIL_ADDRESS": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "PHONE_NUMBER": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
}


class RedactTextConfig(FunctionBaseConfig, name="nvkit_redact_text"):
    info_types: list[str] = Field(
        default=["PERSON_NAME", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SOCIAL_SECURITY_NUMBER"],
        description="Google DLP infoTypes to redact",
    )
    replacement: str = Field(default="[REDACTED]", description="Replacement text for findings")


@register_function(config_type=RedactTextConfig)
async def redact_text(config: RedactTextConfig, builder: Builder):

    async def _redact(text: str) -> str:
        """Redact sensitive information (names, emails, phone numbers, SSNs) from text."""
        creds = require_env(*ENV_VARS)
        if creds is None:
            # Local regex fallback keeps demos safe-ish and the workflow runnable,
            # but is NOT a substitute for DLP — the notice below makes that clear.
            redacted = text
            for pattern in FALLBACK_PATTERNS.values():
                redacted = pattern.sub(config.replacement, redacted)
            notice = missing_credentials_message("nvkit_redact_text", *ENV_VARS)
            return f"{notice}\n\n{redacted}"

        # TODO(nvkit): call Google Cloud DLP deidentifyContent, e.g.
        #   POST https://dlp.googleapis.com/v2/projects/{GOOGLE_CLOUD_PROJECT}/content:deidentify
        #   inspectConfig.infoTypes = config.info_types
        #   deidentifyConfig -> replaceConfig with config.replacement
        # Auth: OAuth token from the service account in GOOGLE_APPLICATION_CREDENTIALS
        # (use google-auth or google-cloud-dlp client library).
        raise NotImplementedError("Google DLP call not implemented yet — see TODO above.")

    yield FunctionInfo.from_fn(
        _redact,
        description=(
            "Redact sensitive information (PII such as names, emails, phone numbers, SSNs) "
            "from the given text before external release. Returns the redacted text."
        ),
    )
