from mcp.server.fastmcp import FastMCP


def register_openrocket_component(app: FastMCP):
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        title="OpenRocket Component",
        description=(
            "Create, read, update, or delete a component in an OpenRocket .ork file. "
            "Use 'action' to specify the operation. "
            "Valid component types for create: nose-cone, body-tube, transition, fin-set, parachute, mass."
        ),
        structured_output=True,
    )
    async def openrocket_component(
        action: Literal["create", "read", "update", "delete"],
        ork_path: Path,
        component_name: str | None = None,
        component_type: str | None = None,
        parent: str | None = None,
        name: str | None = None,
        length: float | None = None,
        diameter: float | None = None,
        fore_diameter: float | None = None,
        aft_diameter: float | None = None,
        thickness: float | None = None,
        shape: str | None = None,
        count: int | None = None,
        root_chord: float | None = None,
        tip_chord: float | None = None,
        span: float | None = None,
        sweep: float | None = None,
        cd: float | None = None,
        mass: float | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Perform a CRUD operation on a single rocket component.

        Actions:
            create: Add a new component. Requires 'component_type'. Use 'parent' to
                    specify a named parent; otherwise a sensible default is chosen.
            read:   Return properties of a named component. Requires 'component_name'.
            update: Modify properties of a named component. Requires 'component_name'.
                    Only the provided properties are changed; others are left as-is.
            delete: Remove a named component. Requires 'component_name'.

        Component-specific properties (all in SI units — metres, kilograms):
            length, diameter, fore_diameter, aft_diameter, thickness, shape
                → nose-cone, body-tube, transition
            count, root_chord, tip_chord, span, sweep
                → fin-set
            diameter, cd
                → parachute
            mass
                → mass component

        Args:
            action: One of 'create', 'read', 'update', 'delete'.
            ork_path: Path to the OpenRocket .ork design file.
            component_name: Name of the component to read/update/delete.
            component_type: Type of component to create (e.g. 'nose-cone').
            parent: Named parent component for create (optional).
            name: Display name to assign when creating or renaming a component.
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from rocketsmith.openrocket.components import (
            create_component,
            read_component,
            update_component,
            delete_component,
        )
        from rocketsmith.openrocket.utils import get_openrocket_path

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            props = {k: v for k, v in dict(
                name=name,
                length=length,
                diameter=diameter,
                fore_diameter=fore_diameter,
                aft_diameter=aft_diameter,
                thickness=thickness,
                shape=shape,
                count=count,
                root_chord=root_chord,
                tip_chord=tip_chord,
                span=span,
                sweep=sweep,
                cd=cd,
                mass=mass,
            ).items() if v is not None}

            if action == "create":
                if component_type is None:
                    return tool_error(
                        "'component_type' is required for action 'create'.",
                        "MISSING_ARGUMENT",
                    )
                result = create_component(
                    ork_path=ork_path,
                    component_type=component_type,
                    jar_path=openrocket_path,
                    parent_name=parent,
                    **props,
                )
                return tool_success(result)

            elif action == "read":
                if component_name is None:
                    return tool_error(
                        "'component_name' is required for action 'read'.",
                        "MISSING_ARGUMENT",
                    )
                result = read_component(
                    ork_path=ork_path,
                    component_name=component_name,
                    jar_path=openrocket_path,
                )
                return tool_success(result)

            elif action == "update":
                if component_name is None:
                    return tool_error(
                        "'component_name' is required for action 'update'.",
                        "MISSING_ARGUMENT",
                    )
                result = update_component(
                    ork_path=ork_path,
                    component_name=component_name,
                    jar_path=openrocket_path,
                    **props,
                )
                return tool_success(result)

            elif action == "delete":
                if component_name is None:
                    return tool_error(
                        "'component_name' is required for action 'delete'.",
                        "MISSING_ARGUMENT",
                    )
                deleted_name = delete_component(
                    ork_path=ork_path,
                    component_name=component_name,
                    jar_path=openrocket_path,
                )
                return tool_success({"deleted": deleted_name})

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                ork_path=str(ork_path),
                exception_type=type(e).__name__,
            )

        except ValueError as e:
            return tool_error(
                str(e),
                "INVALID_ARGUMENT",
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                f"Failed to {action} component",
                "COMPONENT_FAILED",
                ork_path=str(ork_path),
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_component
