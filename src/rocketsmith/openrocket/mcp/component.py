from mcp.server.fastmcp import FastMCP


def register_openrocket_component(app: FastMCP):
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace

    @app.tool(
        title="OpenRocket Component",
        description=(
            "Create, read, update, or delete a component in an OpenRocket .ork file. "
            "Use 'action' to specify the operation. "
            "Valid component types for create: nose-cone, body-tube, inner-tube, transition, fin-set, parachute, mass. "
            "inner-tube serves two purposes: motor mount (set motor_mount=true, sized to motor diameter) "
            "and coupler (short tube joining two body sections, OD = body tube ID, no motor_mount flag). "
            "Use axial_offset_m and axial_offset_method to position components precisely within their parent."
        ),
        structured_output=True,
    )
    async def openrocket_component(
        action: Literal["create", "read", "update", "delete"],
        ork_filename: str,
        workspace_name: str | None = None,
        component_name: str | None = None,
        component_type: str | None = None,
        parent: str | None = None,
        name: str | None = None,
        preset_part_no: str | None = None,
        preset_manufacturer: str | None = None,
        material_name: str | None = None,
        material_type: str | None = None,
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
        axial_offset_m: float | None = None,
        axial_offset_method: str | None = None,
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

        Preset and material support (create and update):
            preset_part_no: Part number from openrocket_database (e.g. 'BT-20').
                Loads all geometry and material from the manufacturer preset as a
                baseline. Explicit dimension params override the preset values.
            preset_manufacturer: Optional manufacturer filter when looking up the
                preset, useful if the same part number exists across manufacturers.
            material_name: Material name from openrocket_database (e.g. 'Aluminum',
                'Carbon fiber'). Overrides the preset's material when combined with
                preset_part_no, or sets the material standalone.
            material_type: Narrows material lookup to 'bulk', 'surface', or 'line'.
                Optional — omit to search all types.

        Component-specific properties (all in SI units — metres, kilograms):
            length, diameter, fore_diameter, aft_diameter, thickness, shape
                → nose-cone, body-tube, transition
            count, root_chord, tip_chord, span, sweep, thickness
                → fin-set
            diameter, cd
                → parachute
            mass
                → mass component

        Axial positioning (all component types):
            axial_offset_m: Offset in metres along the parent's axis.
            axial_offset_method: Reference point for the offset. One of:
                "top"      — offset from the fore (top) end of the parent
                "bottom"   — offset from the aft (bottom) end of the parent
                "middle"   — offset from the middle of the parent
                "absolute" — absolute position from the rocket nose
            Always set axial_offset_method before axial_offset_m. For a coupler that
            should protrude half its length past the aft end of its parent, use
            axial_offset_method="bottom" and axial_offset_m=+(coupler_length / 2).

        Args:
            action: One of 'create', 'read', 'update', 'delete'.
            ork_filename: The .ork file in the workspace openrocket/ folder.
            workspace_name: The workspace name.
            component_name: Name of the component to read/update/delete.
            component_type: Type of component to create (e.g. 'nose-cone').
            parent: Named parent component for create (optional).
            name: Display name to assign when creating or renaming a component.
            preset_part_no: Part number to load as a preset baseline (create/update).
            preset_manufacturer: Manufacturer filter for preset lookup (optional).
            material_name: Material to apply by name (create/update).
            material_type: Restrict material search to 'bulk', 'surface', or 'line'.
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from rocketsmith.openrocket.components import (
            create_component,
            read_component,
            update_component,
            delete_component,
        )
        from rocketsmith.openrocket.utils import get_openrocket_path

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        if not ork_filename.endswith(".ork"):
            ork_filename += ".ork"

        ork_path = workspace.path / "openrocket" / ork_filename

        if not ork_path.exists():
            return tool_error(
                f"OpenRocket file not found: {ork_path}",
                "FILE_NOT_FOUND",
                ork_path=str(ork_path),
            )

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            props = {
                k: v
                for k, v in dict(
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
                    axial_offset_m=axial_offset_m,
                    axial_offset_method=axial_offset_method,
                ).items()
                if v is not None
            }

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
                    preset_part_no=preset_part_no,
                    preset_manufacturer=preset_manufacturer,
                    material_name=material_name,
                    material_type=material_type,
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
                    preset_part_no=preset_part_no,
                    preset_manufacturer=preset_manufacturer,
                    material_name=material_name,
                    material_type=material_type,
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
