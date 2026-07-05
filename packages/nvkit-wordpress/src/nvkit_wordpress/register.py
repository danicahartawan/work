from pydantic import Field

from nvkit_core import missing_credentials_message, require_env
from nvkit_core.compat import Builder, FunctionBaseConfig, FunctionInfo, register_function

ENV_VARS = ("WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD")

INPUT_SEPARATOR = " :: "


class WordPressCreateDraftConfig(FunctionBaseConfig, name="nvkit_wordpress_create_draft"):
    default_category: str = Field(default="", description="Optional category slug for new drafts")


@register_function(config_type=WordPressCreateDraftConfig)
async def wordpress_create_draft(config: WordPressCreateDraftConfig, builder: Builder):

    async def _create_draft(title_and_content: str) -> str:
        """Create a WordPress draft post. Input format: '<title> :: <content>'."""
        creds = require_env(*ENV_VARS)
        if creds is None:
            return missing_credentials_message("nvkit_wordpress_create_draft", *ENV_VARS)

        title, sep, content = title_and_content.partition(INPUT_SEPARATOR)
        if not sep:
            return (
                "[nvkit_wordpress_create_draft] Input must be formatted as "
                f"'<title>{INPUT_SEPARATOR}<content>'."
            )

        # TODO(nvkit): create the draft with httpx:
        #   POST {WORDPRESS_URL}/wp-json/wp/v2/posts
        #   auth=(WORDPRESS_USER, WORDPRESS_APP_PASSWORD)  # application password
        #   json={"title": title, "content": content, "status": "draft"}
        # Always status="draft" — a human publishes; the agent never does.
        raise NotImplementedError("WordPress REST call not implemented yet — see TODO above.")

    yield FunctionInfo.from_fn(
        _create_draft,
        description=(
            "Create a DRAFT post on the team WordPress site for human review. "
            "Input format: '<title> :: <content>'. Never publishes directly. "
            "Returns the draft's edit URL."
        ),
    )
