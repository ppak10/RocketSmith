"""Generate a ComponentTree from an OpenRocket .ork or .rkt file.

Reads the component hierarchy, converts dimensions to millimetres,
parses comment fields for agent annotations, computes static stability,
and renders an ASCII side profile.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pint import Quantity

from rocketsmith.manufacturing.models import (
    Component,
    ComponentTree,
    Stage,
    AgentAnnotation,
    default_category,
    parse_comment,
)
from rocketsmith.openrocket.models import (
    NoseConeDimensions,
    TubeDimensions,
    TransitionDimensions,
    FinSetDimensions,
    RingDimensions,
    RecoveryDimensions,
    GenericDimensions,
)


# ── Metre → mm conversion ─────────────────────────────────────────────────────

_METRE_FIELDS = {
    "length_m",
    "outer_diameter_m",
    "inner_diameter_m",
    "fore_diameter_m",
    "aft_diameter_m",
    "thickness_m",
    "root_chord_m",
    "tip_chord_m",
    "span_m",
    "sweep_m",
    "diameter_m",
    "axial_offset_m",
    "position_x_m",
}


def _to_mm(value: Any) -> float:
    """Convert a metre value to millimetres."""
    return round(float(value) * 1000.0, 4)


# ── Dimension model builders ──────────────────────────────────────────────────


def _build_dimensions(comp: dict[str, Any]) -> Any:
    """Create a typed Dimensions model from a flat component dict."""
    comp_type = comp.get("type", "")

    if comp_type == "NoseCone":
        return NoseConeDimensions(
            shape=comp.get("shape", "ogive"),
            length=_to_mm(comp.get("length_m", 0)),
            base_od=_to_mm(comp.get("aft_diameter_m", 0)),
            wall=(
                Quantity(_to_mm(comp["thickness_m"]), "mm")
                if comp.get("thickness_m")
                else None
            ),
        )

    if comp_type == "Transition":
        return TransitionDimensions(
            shape=comp.get("shape", "conical"),
            length=_to_mm(comp.get("length_m", 0)),
            fore_od=_to_mm(comp.get("fore_diameter_m", 0)),
            aft_od=_to_mm(comp.get("aft_diameter_m", 0)),
            wall=(
                Quantity(_to_mm(comp["thickness_m"]), "mm")
                if comp.get("thickness_m")
                else None
            ),
        )

    if comp_type in ("BodyTube", "InnerTube", "TubeCoupler"):
        return TubeDimensions(
            length=_to_mm(comp.get("length_m", 0)),
            od=_to_mm(comp.get("outer_diameter_m", 0)),
            id=_to_mm(comp.get("inner_diameter_m", 0)),
            motor_mount=bool(comp.get("motor_mount", False)),
        )

    if comp_type in ("TrapezoidFinSet", "EllipticalFinSet", "FreeformFinSet"):
        return FinSetDimensions(
            fin_type=comp_type.replace("FinSet", "").lower(),
            count=int(comp.get("fin_count", 3)),
            root_chord=_to_mm(comp.get("root_chord_m", 0)),
            tip_chord=_to_mm(comp.get("tip_chord_m", 0)),
            span=_to_mm(comp.get("span_m", 0)),
            sweep=_to_mm(comp.get("sweep_m", 0)),
            thickness=_to_mm(comp.get("thickness_m", 0)),
        )

    if comp_type in ("CenteringRing", "BulkHead"):
        return RingDimensions(
            od=_to_mm(comp.get("outer_diameter_m", 0)),
            id=_to_mm(comp.get("inner_diameter_m", 0)),
            thickness=_to_mm(comp.get("thickness_m", comp.get("length_m", 0))),
        )

    if comp_type in ("Parachute", "Streamer", "ShockCord"):
        return RecoveryDimensions(
            diameter=(
                Quantity(_to_mm(comp["diameter_m"]), "mm")
                if comp.get("diameter_m")
                else None
            ),
            length=(
                Quantity(_to_mm(comp["length_m"]), "mm")
                if comp.get("length_m")
                else None
            ),
        )

    # Fallback
    return GenericDimensions(
        length=(
            Quantity(_to_mm(comp["length_m"]), "mm") if comp.get("length_m") else None
        ),
        mass=Quantity(comp["mass_kg"], "kg") if comp.get("mass_kg") else None,
    )


# ── Flat list → hierarchy ─────────────────────────────────────────────────────


def _build_component(comp: dict[str, Any]) -> Component:
    """Convert a flat component dict to a Component model."""
    human_notes, agent = parse_comment(comp.get("comment"))

    mass = Quantity(comp["mass_kg"], "kg") if comp.get("mass_kg") else None
    override_mass = (
        Quantity(comp["override_mass_kg"], "kg")
        if comp.get("override_mass_kg")
        else None
    )
    material_density = (
        Quantity(comp["material_density_kg_m3"], "kg/m**3")
        if comp.get("material_density_kg_m3")
        else None
    )

    return Component(
        type=comp["type"],
        name=comp["name"],
        category=default_category(comp["type"]),
        dimensions=_build_dimensions(comp),
        mass=mass,
        override_mass=override_mass,
        override_mass_enabled=comp.get("override_mass_enabled", False),
        material=comp.get("material"),
        material_density=material_density,
        human_notes=human_notes,
        agent=agent,
    )


def _build_hierarchy(flat_components: list[dict[str, Any]]) -> list[Stage]:
    """Convert a depth-tagged flat list into a hierarchical Stage/Component tree.

    The flat list is a pre-order traversal where:
    - depth 0 = Rocket (skipped)
    - depth 1 = AxialStage → becomes a Stage
    - depth 2+ = components nested by depth
    """
    stages: list[Stage] = []
    # Stack of (depth, Component) for building parent-child relationships
    stack: list[tuple[int, Component]] = []

    for comp in flat_components:
        depth = comp.get("depth", 0)
        comp_type = comp.get("type", "")

        # Skip the root Rocket node
        if comp_type == "Rocket":
            continue

        # AxialStage becomes a Stage container
        if comp_type == "AxialStage":
            stages.append(Stage(name=comp.get("name", "Stage")))
            stack.clear()
            continue

        if not stages:
            continue

        node = _build_component(comp)

        # Pop stack back to find the parent at depth-1
        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            # Attach as child of the top of stack
            stack[-1][1].children.append(node)
        else:
            # Top-level component within the stage
            stages[-1].components.append(node)

        stack.append((depth, node))

    return stages


# ── Public API ─────────────────────────────────────────────────────────────────


def generate_tree(
    rocket_file_path: Path,
    project_dir: Path,
    jar_path: Path | None = None,
) -> tuple[ComponentTree, str]:
    """Generate a ComponentTree and ASCII art from an .ork/.rkt file.

    Args:
        rocket_file_path: Path to the .ork or .rkt design file.
        project_dir: Project root directory (stored in the tree).
        jar_path: Optional path to the OpenRocket JAR.

    Returns:
        (tree, ascii_art) — the ComponentTree model and an ASCII side
        profile string.
    """
    from rocketsmith.openrocket.components import inspect_rocket_file
    from rocketsmith.openrocket.ascii import render_rocket_ascii
    from rocketsmith.openrocket.stability import barrowman_stability

    raw = inspect_rocket_file(rocket_file_path, jar_path=jar_path)
    flat_components = raw["components"]

    # Build hierarchy
    stages = _build_hierarchy(flat_components)

    # Compute stability and attach to stages
    # (currently single-stage; stability values come from the full rocket)
    stability_cal = raw.get("stability_cal")
    cg_m = raw.get("cg_x")
    cp_m = raw.get("cp_x")
    max_d_m = raw.get("max_diameter_m")

    for stage in stages:
        if cg_m is not None:
            stage.cg = Quantity(round(cg_m * 1000, 2), "mm")
        if cp_m is not None:
            stage.cp = Quantity(round(cp_m * 1000, 2), "mm")
        stage.stability_cal = stability_cal
        if max_d_m is not None:
            stage.max_diameter = Quantity(round(max_d_m * 1000, 2), "mm")

    # Derive rocket name from root component or filename
    rocket_name = rocket_file_path.stem
    for comp in flat_components:
        if comp.get("type") == "Rocket":
            rocket_name = comp.get("name", rocket_name)
            break

    tree = ComponentTree(
        source_ork=str(rocket_file_path),
        project_root=str(project_dir),
        rocket_name=rocket_name,
        stages=stages,
    )

    # Render ASCII art
    ascii_art = render_rocket_ascii(
        flat_components,
        cg_x=cg_m,
        cp_x=cp_m,
        max_diameter=max_d_m,
    )

    return tree, ascii_art
