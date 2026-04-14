from mcp.server.fastmcp import FastMCP


def register_cadsmith_bd_warehouse_info(app: FastMCP):
    from pathlib import Path
    from typing import Any, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    # Attributes to always skip — build123d internals, large lookup tables,
    # or values already captured in the Part model.
    _SKIP_ATTRS = frozenset(
        {
            # build123d shape internals
            "ancestors",
            "anchestors",
            "children",
            "color",
            "compounds",
            "edges",
            "faces",
            "is_leaf",
            "is_manifold",
            "is_null",
            "is_planar_face",
            "is_root",
            "is_valid",
            "joints",
            "label",
            "location",
            "location_str",
            "matrix_of_inertia",
            "order",
            "parent",
            "principal_properties",
            "separator",
            "shells",
            "size",
            "solids",
            "topo_parent",
            "vertices",
            "wires",
            # Already in Part model
            "area",
            "volume",
            # Internal flags
            "for_construction",
        }
    )

    # Prefixes that indicate OCC/build123d internal lookup tables.
    _SKIP_PREFIXES = (
        "downcast_",
        "geom_",
        "inverse_",
        "shape_",
        "wrapped",
    )

    # Attributes that are full lookup tables (all sizes, not just this instance).
    # Skip these to avoid bloating the response.
    _SKIP_TABLE_ATTRS = frozenset(
        {
            "clearance_hole_data",
            "clearance_hole_drill_sizes",
            "tap_hole_data",
            "tap_hole_drill_sizes",
            "fastener_data",
            "nominal_lengths",
            "nominal_length_range",
        }
    )

    def _extract_attributes(instance: Any) -> dict[str, Any]:
        """Extract useful dimensional attributes from a bd_warehouse instance."""
        attrs: dict[str, Any] = {}
        for name in sorted(dir(instance)):
            if name.startswith("_"):
                continue
            if any(name.startswith(p) for p in _SKIP_PREFIXES):
                continue
            if name in _SKIP_ATTRS or name in _SKIP_TABLE_ATTRS:
                continue
            try:
                val = getattr(instance, name)
            except Exception:
                continue
            if callable(val):
                continue
            # Only keep JSON-serializable scalar/dict/list values.
            if isinstance(val, (str, int, float, bool, type(None))):
                attrs[name] = val
            elif isinstance(val, dict):
                # Only keep dicts whose values are all JSON-serializable.
                if all(
                    isinstance(v, (str, int, float, bool, type(None)))
                    for v in val.values()
                ):
                    attrs[name] = val
            elif isinstance(val, list):
                if all(isinstance(v, (str, int, float, bool, type(None))) for v in val):
                    attrs[name] = val
        return attrs

    @app.tool(
        name="cadsmith_bd_warehouse_info",
        title="Inspect bd_warehouse Part",
        description=(
            "Instantiate a bd_warehouse parametric part (fastener, nut, washer, "
            "etc.) and return its geometric properties and dimensional attributes. "
            "Use this before writing Pass 2 modify-structures scripts to discover "
            "clearance drill sizes, head diameters, nut thickness, and other "
            "dimensions needed for boolean cuts and feature placement. "
            "Optionally exports a STEP file and writes a Part JSON for the GUI."
        ),
        structured_output=True,
    )
    async def cadsmith_bd_warehouse_info(
        generator_class: str,
        generator_params: dict,
        project_dir: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Instantiate a bd_warehouse part and return its properties.

        Args:
            generator_class: bd_warehouse class name, e.g. "HexNut",
                "SocketHeadCapScrew", "HeatSetNut", "PlainWasher", "SetScrew",
                "ButtonHeadScrew", "CounterSunkScrew", "PanHeadScrew".
            generator_params: Constructor keyword arguments, e.g.
                {"size": "M4-0.7", "fastener_type": "iso4032"} for a HexNut, or
                {"size": "M4-0.7", "length": 10, "fastener_type": "iso4762"}
                for a SocketHeadCapScrew.
            project_dir: Optional project root. When provided, exports a STEP
                file to cadsmith/step/ and writes a Part JSON to gui/parts/.
        """
        import bd_warehouse.fastener
        from build123d import Mode, export_step
        from pint import Quantity

        from rocketsmith.cadsmith.models import Part, UnitVector

        # ── Resolve the class ─────────────────────────────────────────
        cls = getattr(bd_warehouse.fastener, generator_class, None)
        if cls is None:
            available = [
                name
                for name in dir(bd_warehouse.fastener)
                if isinstance(getattr(bd_warehouse.fastener, name, None), type)
                and not name.startswith("_")
            ]
            return tool_error(
                f"Unknown bd_warehouse class '{generator_class}'.",
                "INVALID_CLASS",
                generator_class=generator_class,
                available_classes=available,
            )

        # ── Instantiate ───────────────────────────────────────────────
        params = {**generator_params, "simple": True, "mode": Mode.PRIVATE}
        try:
            instance = cls(**params)
        except Exception as e:
            return tool_error(
                f"Failed to instantiate {generator_class}: {e}",
                "INSTANTIATION_FAILED",
                generator_class=generator_class,
                generator_params=generator_params,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # ── Extract geometry ──────────────────────────────────────────
        try:
            bbox = instance.bounding_box()
            com = instance.center()
        except Exception as e:
            return tool_error(
                f"Failed to extract geometry from {generator_class}: {e}",
                "GEOMETRY_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # Build a display name from class + key params.
        size_str = generator_params.get("size", "")
        length_str = generator_params.get("length", "")
        display_parts = [generator_class.replace("_", " ")]
        if size_str:
            display_parts.append(str(size_str))
        if length_str:
            display_parts.append(f"x{length_str}")
        display_name = " ".join(display_parts)

        # Derive a file-safe stem.
        stem = display_name.lower().replace(" ", "_").replace("-", "_")

        part = Part(
            name=stem,
            display_name=display_name,
            source="bd_warehouse",
            generator_class=generator_class,
            generator_params=generator_params,
            volume=Quantity(round(instance.volume, 2), "mm**3"),
            surface_area=Quantity(round(instance.area, 2), "mm**2"),
            bounding_box=UnitVector.from_vector(bbox.size, precision=2),
            center_of_mass=UnitVector.from_vector(com),
        )

        # ── Extract dimensional attributes ────────────────────────────
        attributes = _extract_attributes(instance)

        # ── Optional: export STEP + Part JSON ─────────────────────────
        if project_dir is not None:
            from rocketsmith.gui.layout import PARTS_DIR, STEP_DIR

            resolved_dir = resolve_path(project_dir)

            # Export STEP.
            step_dir = resolved_dir / STEP_DIR
            step_dir.mkdir(parents=True, exist_ok=True)
            step_path = step_dir / f"{stem}.step"
            try:
                export_step(instance, str(step_path))
                part.step_path = str(step_path)
            except Exception as e:
                return tool_error(
                    f"Failed to export STEP for {generator_class}: {e}",
                    "EXPORT_FAILED",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                )

            # Write Part JSON.
            parts_dir = resolved_dir / PARTS_DIR
            parts_dir.mkdir(parents=True, exist_ok=True)
            part_path = parts_dir / f"{stem}.json"
            part_path.write_text(part.model_dump_json(indent=2), encoding="utf-8")

        return tool_success(
            {
                "part": part.model_dump(),
                "attributes": attributes,
            }
        )

    return cadsmith_bd_warehouse_info
