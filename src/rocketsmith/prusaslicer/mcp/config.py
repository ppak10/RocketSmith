from mcp.server.fastmcp import FastMCP

from pathlib import Path
from typing import Union


def register_prusaslicer_config(app: FastMCP):
    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error
    from rocketsmith.prusaslicer.models import (
        ConfigAction,
        ConfigEntry,
        ConfigListResult,
        ConfigSettings,
        ConfigType,
    )
    from rocketsmith.prusaslicer.config import (
        DEFAULT_CONFIG_PATH,
        create_config,
        delete_config,
        list_configs,
        set_config,
        show_config,
    )

    @app.tool(
        name="prusaslicer_config",
        title="Manage PrusaSlicer Configs",
        description=(
            "Manage PrusaSlicer configuration files (.ini) for printer, filament, and print "
            "profiles stored locally in the project under prusaslicer/configs/. "
            "Actions: list — enumerate configs; show — read all settings; "
            "create — write a new config from a settings dict; "
            "set — upsert specific keys in an existing config (creates if absent); "
            "delete — remove a config file. "
            "The path returned by show/create/set can be passed directly to "
            "prusaslicer_slice as config_path."
        ),
        structured_output=True,
    )
    async def prusaslicer_config(
        action: ConfigAction,
        config_type: ConfigType | None = None,
        config_name: str | None = None,
        settings: dict[str, str] | None = None,
        prusaslicer_config_path: Path | None = None,
    ) -> Union[
        ToolSuccess[ConfigListResult],
        ToolSuccess[ConfigSettings],
        ToolSuccess[ConfigEntry],
        ToolError,
    ]:
        """
        Manage PrusaSlicer .ini config files stored in the project.

        Args:
            action: Operation to perform — list, show, create, set, or delete.
            config_type: Profile category — printer, filament, or print.
                         Required for all actions except list (where it filters results).
            config_name: Name of the config (filename without .ini extension).
                         Required for show, create, set, and delete.
            settings: Key-value pairs to write. Required for create and set.
                      For set, only the provided keys are updated; others are preserved.
            prusaslicer_config_path: Root directory for config storage.
                                     Defaults to prusaslicer/configs/ in the working directory.
        """
        base = (
            prusaslicer_config_path
            if prusaslicer_config_path is not None
            else DEFAULT_CONFIG_PATH
        )

        # Validate required args per action
        needs_type = action in ("show", "create", "set", "delete")
        needs_name = action in ("show", "create", "set", "delete")
        needs_settings = action in ("create", "set")

        if needs_type and config_type is None:
            return tool_error(
                f"config_type is required for action '{action}'",
                "MISSING_ARGUMENT",
                action=action,
            )
        if needs_name and config_name is None:
            return tool_error(
                f"config_name is required for action '{action}'",
                "MISSING_ARGUMENT",
                action=action,
            )
        if needs_settings and not settings:
            return tool_error(
                f"settings is required for action '{action}'",
                "MISSING_ARGUMENT",
                action=action,
            )

        try:
            if action == "list":
                result = list_configs(base, config_type)
                return tool_success(result)

            elif action == "show":
                result = show_config(base, config_type, config_name)
                return tool_success(result)

            elif action == "create":
                result = create_config(base, config_type, config_name, settings)
                return tool_success(result)

            elif action == "set":
                result = set_config(base, config_type, config_name, settings)
                return tool_success(result)

            elif action == "delete":
                result = delete_config(base, config_type, config_name)
                return tool_success(result)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "NOT_FOUND",
                action=action,
                config_type=config_type,
                config_name=config_name,
            )
        except FileExistsError as e:
            return tool_error(
                str(e),
                "ALREADY_EXISTS",
                action=action,
                config_type=config_type,
                config_name=config_name,
            )
        except Exception as e:
            return tool_error(
                f"Config operation failed: {e}",
                "CONFIG_FAILED",
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = prusaslicer_config
