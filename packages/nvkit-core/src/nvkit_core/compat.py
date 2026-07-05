"""Single import point for NAT symbols used by every nvkit package.

NAT's plugin API moved between releases (v1.8 exposes ``nat.plugin_api``;
earlier v1.x spread the same symbols across submodules). All nvkit packages
import from here so a NAT version bump is a one-file change.
"""

try:
    from nat.plugin_api import FunctionBaseConfig, FunctionInfo, register_function
    from nat.builder.workflow_builder import Builder
except ImportError:  # NAT < 1.8
    from nat.builder.builder import Builder
    from nat.builder.function_info import FunctionInfo
    from nat.cli.register_workflow import register_function
    from nat.data_models.function import FunctionBaseConfig

__all__ = ["Builder", "FunctionBaseConfig", "FunctionInfo", "register_function"]
