from pydantic import Field

from nvkit_core import missing_credentials_message, require_env
from nvkit_core.compat import Builder, FunctionBaseConfig, FunctionInfo, register_function

ENV_VARS = ("TABLEAU_SERVER_URL", "TABLEAU_SITE_ID", "TABLEAU_PAT_NAME", "TABLEAU_PAT_SECRET")


class TableauViewDataConfig(FunctionBaseConfig, name="nvkit_tableau_view_data"):
    api_version: str = Field(default="3.24", description="Tableau REST API version")
    max_rows: int = Field(default=200, description="Maximum data rows to return", ge=1)


@register_function(config_type=TableauViewDataConfig)
async def tableau_view_data(config: TableauViewDataConfig, builder: Builder):

    async def _view_data(view_name: str) -> str:
        """Fetch the underlying data of a named Tableau view/dashboard as CSV."""
        creds = require_env(*ENV_VARS)
        if creds is None:
            return missing_credentials_message("nvkit_tableau_view_data", *ENV_VARS)

        # TODO(nvkit): Tableau REST flow with httpx:
        #   1. POST {TABLEAU_SERVER_URL}/api/{api_version}/auth/signin
        #      with personalAccessTokenName/Secret + site contentUrl -> token
        #   2. GET  /api/{ver}/sites/{site}/views?filter=name:eq:{view_name}
        #   3. GET  /api/{ver}/sites/{site}/views/{view_id}/data  (CSV)
        #   4. Truncate to config.max_rows and return.
        raise NotImplementedError("Tableau REST call not implemented yet — see TODO above.")

    yield FunctionInfo.from_fn(
        _view_data,
        description=(
            "Fetch the underlying data of a Tableau view or dashboard by name "
            "(e.g. media metrics, campaign performance). Returns CSV rows."
        ),
    )
