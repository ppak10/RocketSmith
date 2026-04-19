from mcp.server.fastmcp import FastMCP


def register_openrocket_component(app: FastMCP):
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        title="OpenRocket or RockSim Component",
        description=(
            "Create, read, update, or delete a component in an OpenRocket .ork or RockSim .rkt file. "
            "Use 'action' to specify the operation. "
            "Valid component types for create: nose-cone, body-tube, inner-tube, transition, tube-coupler, "
            "fin-set, parachute, streamer, shock-cord, mass, rail-button, launch-lug, centering-ring, "
            "bulkhead, engine-block. "
            "inner-tube serves two purposes: motor mount (set motor_mount=true, sized to motor diameter) "
            "and coupler (short tube joining two body sections, OD = body tube ID, no motor_mount flag). "
            "Use axial_offset_m and axial_offset_method to position components precisely within their parent. "
            "After create, update, or delete, the full component tree is regenerated automatically. "
            "A read with no component_name returns the full hierarchical "
            "component tree (dimensions in mm, stability, ASCII profile) — use this instead of "
            "generating the tree separately."
        ),
        structured_output=True,
    )
    async def openrocket_component(
        action: Literal["create", "read", "update", "delete"],
        rocket_file_path: Path,
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
        inner_diameter: float | None = None,
        fore_diameter: float | None = None,
        aft_diameter: float | None = None,
        thickness: float | None = None,
        width: float | None = None,
        shape: str | None = None,
        count: int | None = None,
        root_chord: float | None = None,
        tip_chord: float | None = None,
        span: float | None = None,
        sweep: float | None = None,
        cd: float | None = None,
        mass: float | None = None,
        motor_mount: bool | None = None,
        axial_offset_m: float | None = None,
        axial_offset_method: str | None = None,
        override_mass_kg: float | None = None,
        override_mass_enabled: bool | None = None,
        openrocket_path: Path | None = None,
        out_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Perform a CRUD operation on a single rocket component in an .ork or .rkt file.

        Actions:
            create: Add a new component. Requires 'component_type'. Use 'parent' to
                    specify a named parent; otherwise a sensible default is chosen.
                    Regenerates component_tree.json as a side effect.
            read:   With 'component_name', return properties of that component.
                    Without 'component_name', generate and return the full
                    hierarchical component tree. The tree includes typed dimensions
                    in mm, per-component mass/material, agent annotations, static
                    stability (CG/CP/calibers), and an ASCII side profile.
                    Writes component_tree.json to the project directory.
            update: Modify properties of a named component. Requires 'component_name'.
                    Only the provided properties are changed; others are left as-is.
                    Regenerates component_tree.json as a side effect.
            delete: Remove a named component. Requires 'component_name'.
                    Regenerates component_tree.json as a side effect.

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
            length, width
                → streamer
            length
                → shock-cord (cord length)
            mass
                → mass component
            diameter, inner_diameter, length
                → centering-ring, bulkhead, engine-block, launch-lug
            diameter, inner_diameter, count
                → rail-button (count = number of button instances)

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

            Coupler sign gotcha: when ``axial_offset_method="bottom"``,
            ``axial_offset_m`` must be **positive** to push the coupler past
            the parent's aft end. A negative value will pull it back inside
            the parent and produce an invalid geometry that may still save
            without error.

        Mass overrides (create and update):
            override_mass_kg: Pin this component's mass to a measured value
                in **kilograms** (NOT grams — divide filament_used_g by 1000
                when feeding in a prusaslicer_slice result). Setting this
                implicitly enables the override unless
                override_mass_enabled=False is also passed.
            override_mass_enabled: Toggle the override flag. When
                override_mass_kg is set, this defaults to True.

            Persistence gotcha: OpenRocket only serializes the
            ``<overridemass>`` tag when the override is enabled. Disabling
            with override_mass_enabled=False and saving will drop the stored
            value on the next reload. To keep a calibration around while
            comparing a baseline vs. overridden simulation, either leave the
            override enabled and re-enable it each run, or track the
            measured weight outside the .ork file.

        Args:
            action: One of 'create', 'read', 'update', 'delete'.
            rocket_file_path: Path to the .ork or .rkt design file.
            component_name: Name of the component to read/update/delete.
            component_type: Type of component to create (e.g. 'nose-cone').
            parent: Named parent component for create (optional).
            name: Display name to assign when creating or renaming a component.
            preset_part_no: Part number to load as a preset baseline (create/update).
            preset_manufacturer: Manufacturer filter for preset lookup (optional).
            material_name: Material to apply by name (create/update).
            material_type: Restrict material search to 'bulk', 'surface', or 'line'.
            openrocket_path: Optional path to the OpenRocket JAR file.
            out_path: Optional path to write component_tree.json. Defaults to
                ``<project_dir>/gui/component_tree.json``.
        """
        from rocketsmith.openrocket.components import (
            create_component,
            read_component,
            update_component,
            delete_component,
        )
        from rocketsmith.openrocket.generate_tree import generate_tree
        from rocketsmith.openrocket.utils import get_openrocket_path

        from rocketsmith.mcp.utils import get_project_dir
        from rocketsmith.gui.layout import TREE_FILE

        def _resolve_tree_path() -> Path:
            if out_path is not None:
                return resolve_path(out_path)
            return get_project_dir() / TREE_FILE

        def _write_tree() -> None:
            """Generate and write component_tree.json as a side-effect."""
            tree_path = _resolve_tree_path()
            tree, ascii_art = generate_tree(
                rocket_file_path=rocket_file_path,
                project_dir=tree_path.parent.parent,
                jar_path=openrocket_path,
            )
            tree_path.parent.mkdir(parents=True, exist_ok=True)
            tree_path.write_text(tree.model_dump_json(indent=2), encoding="utf-8")

        def _generate_tree() -> dict:
            """Generate, write, and return the full tree payload for ``read``."""
            tree_path = _resolve_tree_path()
            tree, ascii_art = generate_tree(
                rocket_file_path=rocket_file_path,
                project_dir=tree_path.parent.parent,
                jar_path=openrocket_path,
            )
            tree_path.parent.mkdir(parents=True, exist_ok=True)
            tree_path.write_text(tree.model_dump_json(indent=2), encoding="utf-8")
            return {
                "tree": tree.model_dump(mode="json"),
                "ascii_art": ascii_art,
                "tree_path": str(tree_path),
            }

        rocket_file_path = resolve_path(rocket_file_path)
        if not rocket_file_path.exists():
            return tool_error(
                f"Design file not found: {rocket_file_path}",
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
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
                    inner_diameter=inner_diameter,
                    fore_diameter=fore_diameter,
                    aft_diameter=aft_diameter,
                    thickness=thickness,
                    width=width,
                    shape=shape,
                    count=count,
                    root_chord=root_chord,
                    tip_chord=tip_chord,
                    span=span,
                    sweep=sweep,
                    cd=cd,
                    mass=mass,
                    motor_mount=motor_mount,
                    axial_offset_m=axial_offset_m,
                    axial_offset_method=axial_offset_method,
                    override_mass_kg=override_mass_kg,
                    override_mass_enabled=override_mass_enabled,
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
                    path=rocket_file_path,
                    component_type=component_type,
                    jar_path=openrocket_path,
                    parent_name=parent,
                    preset_part_no=preset_part_no,
                    preset_manufacturer=preset_manufacturer,
                    material_name=material_name,
                    material_type=material_type,
                    **props,
                )
                _write_tree()
                return tool_success(result)

            elif action == "read":
                if component_name is not None:
                    result = read_component(
                        path=rocket_file_path,
                        component_name=component_name,
                        jar_path=openrocket_path,
                    )
                    return tool_success(result)

                # No component_name — return the full component tree.
                return tool_success(_generate_tree())

            elif action == "update":
                if component_name is None:
                    return tool_error(
                        "'component_name' is required for action 'update'.",
                        "MISSING_ARGUMENT",
                    )
                result = update_component(
                    path=rocket_file_path,
                    component_name=component_name,
                    jar_path=openrocket_path,
                    preset_part_no=preset_part_no,
                    preset_manufacturer=preset_manufacturer,
                    material_name=material_name,
                    material_type=material_type,
                    **props,
                )
                _write_tree()
                return tool_success(result)

            elif action == "delete":
                if component_name is None:
                    return tool_error(
                        "'component_name' is required for action 'delete'.",
                        "MISSING_ARGUMENT",
                    )
                deleted_name = delete_component(
                    path=rocket_file_path,
                    component_name=component_name,
                    jar_path=openrocket_path,
                )
                _write_tree()
                return tool_success({"deleted": deleted_name})

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
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
                file_path=str(rocket_file_path),
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_component
