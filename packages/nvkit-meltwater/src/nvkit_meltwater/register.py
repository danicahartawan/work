from pydantic import Field

from nvkit_core import missing_credentials_message, require_env
from nvkit_core.compat import Builder, FunctionBaseConfig, FunctionInfo, register_function

ENV_VARS = ("MELTWATER_API_TOKEN",)


class MeltwaterSearchConfig(FunctionBaseConfig, name="nvkit_meltwater_search"):
    days_back: int = Field(default=7, description="How many days of coverage to search", ge=1)
    max_results: int = Field(default=25, description="Maximum articles to return", ge=1)


@register_function(config_type=MeltwaterSearchConfig)
async def meltwater_search(config: MeltwaterSearchConfig, builder: Builder):

    async def _search(query: str) -> str:
        """Search recent media coverage for a topic and return headlines with outlets and links."""
        creds = require_env(*ENV_VARS)
        if creds is None:
            return missing_credentials_message("nvkit_meltwater_search", *ENV_VARS)

        # TODO(nvkit): Meltwater Export/Search API with httpx:
        #   POST https://api.meltwater.com/v3/search
        #   headers={"apikey": creds["MELTWATER_API_TOKEN"]}
        #   body: query string, date range (now - days_back), limit=config.max_results
        #   Return "- {source}: {title} ({url})" per hit.
        raise NotImplementedError("Meltwater API call not implemented yet — see TODO above.")

    yield FunctionInfo.from_fn(
        _search,
        description=(
            "Search recent media coverage (news, social) for a topic or brand via Meltwater. "
            "Returns headlines with outlet names and links."
        ),
    )
