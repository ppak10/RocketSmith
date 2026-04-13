#!/usr/bin/env python3
"""
Generate STEP files for common rocket hardware parts dataset.

Sources:
  - Standard fasteners: bd_warehouse (ISO/DIN spec, parametric)
  - Custom rocket hardware: build123d (eyebolts, rail buttons, quick links, GoPro mount)

Run:
  uv run python dataset/generate_parts.py
"""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import bd_warehouse
import build123d

from build123d import (
    Align,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    Circle,
    Cylinder,
    Mode,
    Plane,
    Pos,
    Locations,
    RectangleRounded,
    Rot,
    Torus,
    export_step,
    extrude,
    fillet,
    sweep,
)
from bd_warehouse.fastener import (
    ButtonHeadScrew,
    CounterSunkScrew,
    HeatSetNut,
    HexNut,
    PanHeadScrew,
    PlainWasher,
    SetScrew,
    SocketHeadCapScrew,
)

PARTS_DIR = Path("dataset/parts")
METADATA_DIR = Path("dataset/parts/metadata")

records: list[dict] = []

# Source references keyed by generator
SOURCES = {
    "bd_warehouse": {
        "source_url": "https://github.com/gumyr/bd_warehouse",
        "source_page_url": "https://bd-warehouse.readthedocs.io/en/latest/fastener.html",
        "generator": f"bd_warehouse=={bd_warehouse.__version__}",
        "geometry_method": "parametric",
    },
    "build123d": {
        "source_url": "https://github.com/gumyr/build123d",
        "source_page_url": "https://build123d.readthedocs.io/en/latest/",
        "generator": f"build123d=={build123d.__version__}",
        "geometry_method": "parametric",
    },
}

# Standard reference URLs
STANDARD_URLS = {
    "ISO 4762": "https://www.iso.org/standard/75918.html",
    "ISO 7380-1": "https://www.iso.org/standard/63744.html",
    "ISO 1580": "https://www.iso.org/standard/63750.html",
    "ISO 7046": "https://www.iso.org/standard/63753.html",
    "ISO 4026": "https://www.iso.org/standard/63743.html",
    "ISO 4032": "https://www.iso.org/standard/63748.html",
    "ISO 7093": "https://www.iso.org/standard/56664.html",
    "Hilitchi": "https://www.amazon.com/s?k=hilitchi+heat+set+insert",
    "DIN 580": "https://www.fasteners.eu/standards/DIN/580/",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def save(part, rel_path: str, meta: dict, generator: str = "bd_warehouse") -> None:
    path = PARTS_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    export_step(part, str(path))

    standard = meta.get("standard", "")
    record = {
        "local_path": f"dataset/parts/{rel_path}",
        "source_url": SOURCES[generator]["source_url"],
        "source_page_url": SOURCES[generator]["source_page_url"],
        "standard_url": STANDARD_URLS.get(standard, ""),
        "original_name": meta.get("name", ""),
        "extension": ".step",
        "content_type": "application/step",
        "content_length": path.stat().st_size,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": _sha256(path),
        "status": "ok",
        "error": "",
        "generator": SOURCES[generator]["generator"],
        "geometry_method": SOURCES[generator]["geometry_method"],
        **meta,
    }
    records.append(record)
    print(f"  + {rel_path}")


# ---------------------------------------------------------------------------
# Standard Fasteners - bd_warehouse
# ---------------------------------------------------------------------------

def gen_socket_head_cap_screws():
    print("\n[Socket Head Cap Screws - ISO 4762]")
    variants = {
        "M2-0.4": [4, 6, 8],
        "M3-0.5": [6, 8, 10, 12, 16],
        "M4-0.7": [8, 10, 12, 16, 20],
        "M5-0.8": [10, 12, 16, 20],
        "M6-1":   [12, 16, 20, 25],
    }
    for size, lengths in variants.items():
        m = size.split("-")[0]
        for L in lengths:
            part = SocketHeadCapScrew(size, L, "iso4762", simple=True, mode=Mode.PRIVATE)
            save(part, f"fasteners/socket_head_cap_screw/{m}x{L}.step", {
                "name": f"Socket Head Cap Screw {m}x{L}",
                "category": "fastener",
                "subcategory": "socket_head_cap_screw",
                "standard": "ISO 4762",
                "thread": size,
                "length_mm": L,
                "drive": "hex_socket",
                "material": "steel",
                "description": (
                    f"{m} socket head cap screw, {L}mm length. "
                    "Used for structural assembly, fin attachments, avionics bay covers, "
                    "motor retainer screws. High strength, low profile hex socket drive."
                ),
                "use_cases": ["fin_attachment", "avionics_bay", "motor_retainer", "coupler"],
            })


def gen_button_head_screws():
    print("\n[Button Head Screws - ISO 7380-1]")
    variants = {
        "M3-0.5": [6, 8, 10, 12],
        "M4-0.7": [8, 10, 12, 16],
        "M5-0.8": [10, 12, 16, 20],
        "M6-1":   [12, 16, 20],
    }
    for size, lengths in variants.items():
        m = size.split("-")[0]
        for L in lengths:
            part = ButtonHeadScrew(size, L, "iso7380_1", simple=True, mode=Mode.PRIVATE)
            save(part, f"fasteners/button_head_screw/{m}x{L}.step", {
                "name": f"Button Head Screw {m}x{L}",
                "category": "fastener",
                "subcategory": "button_head_screw",
                "standard": "ISO 7380-1",
                "thread": size,
                "length_mm": L,
                "drive": "hex_socket",
                "material": "steel",
                "description": (
                    f"{m} button head screw, {L}mm length. "
                    "Very low profile dome head. Used for access panels, "
                    "payload bay covers, camera mounts. Less snag risk than SHCS."
                ),
                "use_cases": ["access_panel", "payload_bay", "camera_mount"],
            })


def gen_pan_head_screws():
    print("\n[Pan Head Screws - ISO 1580]")
    variants = {
        "M2-0.4": [4, 6, 8],
        "M3-0.5": [6, 8, 10, 12],
        "M4-0.7": [8, 10, 12, 16],
        "M5-0.8": [10, 12, 16],
        "M6-1":   [12, 16, 20],
    }
    for size, lengths in variants.items():
        m = size.split("-")[0]
        for L in lengths:
            part = PanHeadScrew(size, L, "iso1580", simple=True, mode=Mode.PRIVATE)
            save(part, f"fasteners/pan_head_screw/{m}x{L}.step", {
                "name": f"Pan Head Screw {m}x{L}",
                "category": "fastener",
                "subcategory": "pan_head_screw",
                "standard": "ISO 1580",
                "thread": size,
                "length_mm": L,
                "drive": "phillips_or_slotted",
                "material": "steel",
                "description": (
                    f"{m} pan head screw, {L}mm length. "
                    "Wide bearing surface. Used for electronics mounting, "
                    "sled attachment, switch mounts."
                ),
                "use_cases": ["electronics_mount", "avionics_sled", "switch_mount"],
            })


def gen_countersunk_screws():
    print("\n[Countersunk Screws - ISO 7046]")
    variants = {
        "M2-0.4": [4, 6, 8],
        "M3-0.5": [6, 8, 10, 12],
        "M4-0.7": [8, 10, 12, 16],
        "M5-0.8": [10, 12, 16],
        "M6-1":   [12, 16, 20],
    }
    for size, lengths in variants.items():
        m = size.split("-")[0]
        for L in lengths:
            part = CounterSunkScrew(size, L, "iso7046", simple=True, mode=Mode.PRIVATE)
            save(part, f"fasteners/countersunk_screw/{m}x{L}.step", {
                "name": f"Countersunk Screw {m}x{L}",
                "category": "fastener",
                "subcategory": "countersunk_screw",
                "standard": "ISO 7046",
                "thread": size,
                "length_mm": L,
                "drive": "phillips",
                "material": "steel",
                "description": (
                    f"{m} countersunk flat head screw, {L}mm length. "
                    "Sits flush with surface. Used for fin attachment tabs, "
                    "shear pin plates, rail guide mounting. 90-degree countersink."
                ),
                "use_cases": ["fin_tab", "shear_pin_plate", "rail_guide", "flush_mount"],
            })


def gen_set_screws():
    print("\n[Set Screws - ISO 4026]")
    variants = {
        "M3-0.5": [4, 6, 8],
        "M4-0.7": [6, 8, 10],
        "M5-0.8": [6, 8, 10],
        "M6-1":   [8, 10, 12],
    }
    for size, lengths in variants.items():
        m = size.split("-")[0]
        for L in lengths:
            part = SetScrew(size, L, "iso4026", mode=Mode.PRIVATE)
            save(part, f"fasteners/set_screw/{m}x{L}.step", {
                "name": f"Set Screw {m}x{L}",
                "category": "fastener",
                "subcategory": "set_screw",
                "standard": "ISO 4026",
                "thread": size,
                "length_mm": L,
                "drive": "hex_socket",
                "material": "steel",
                "description": (
                    f"{m} cup-point set screw, {L}mm length. Headless. "
                    "Used as motor retainer locking screw, rail button retention, "
                    "shaft/collar locking."
                ),
                "use_cases": ["motor_retainer", "rail_button", "shaft_lock"],
            })


def gen_hex_nuts():
    print("\n[Hex Nuts - ISO 4032]")
    sizes = ["M2-0.4", "M3-0.5", "M4-0.7", "M5-0.8", "M6-1"]
    for size in sizes:
        m = size.split("-")[0]
        part = HexNut(size, "iso4032", simple=True, mode=Mode.PRIVATE)
        save(part, f"fasteners/hex_nut/{m}.step", {
            "name": f"Hex Nut {m}",
            "category": "fastener",
            "subcategory": "hex_nut",
            "standard": "ISO 4032",
            "thread": size,
            "material": "steel",
            "description": (
                f"{m} standard hex nut. Used to lock bolts, "
                "secure eyebolts, attach standoffs."
            ),
            "use_cases": ["general_fastening", "eyebolt_lock", "standoff"],
        })


def gen_heat_set_inserts():
    print("\n[Heat Set Inserts - Hilitchi]")
    sizes = [
        "M2-0.4-3", "M2-0.4-4", "M2-0.4-6",
        "M3-0.5-6", "M3-0.5-8", "M3-0.5-10",
        "M4-0.7-6", "M4-0.7-8", "M4-0.7-10",
        "M5-0.8-6", "M5-0.8-8", "M5-0.8-10",
        "M6-1-10",  "M6-1-12",
    ]
    for size in sizes:
        parts = size.split("-")
        m = parts[0]
        L = parts[-1]
        part = HeatSetNut(size, "Hilitchi", simple=True, mode=Mode.PRIVATE)
        save(part, f"fasteners/heat_set_insert/{m}x{L}.step", {
            "name": f"Heat Set Insert {m}x{L}",
            "category": "fastener",
            "subcategory": "heat_set_insert",
            "standard": "Hilitchi",
            "thread": f"{m}-{parts[1]}",
            "length_mm": int(L),
            "material": "brass",
            "description": (
                f"{m} brass heat set insert, {L}mm length. "
                "Press into 3D printed or composite parts with soldering iron. "
                "Used for avionics bay walls, nosecone shoulder, fin root tabs, "
                "any printed structural connection requiring metal threads."
            ),
            "use_cases": [
                "avionics_bay", "nosecone_shoulder", "fin_root",
                "3d_printed_structure", "composite_panel",
            ],
        })


def gen_plain_washers():
    print("\n[Plain Washers - ISO 7093]")
    sizes = ["M3", "M4", "M5", "M6"]
    for size in sizes:
        part = PlainWasher(size, "iso7093", mode=Mode.PRIVATE)
        save(part, f"fasteners/plain_washer/{size}.step", {
            "name": f"Plain Washer {size}",
            "category": "fastener",
            "subcategory": "plain_washer",
            "standard": "ISO 7093",
            "thread": size,
            "material": "steel",
            "description": (
                f"{size} large plain washer. Distributes load under bolt head or nut. "
                "Used under eyebolts, rail button bases, structural joints."
            ),
            "use_cases": ["eyebolt", "rail_button", "structural_joint"],
        })


# ---------------------------------------------------------------------------
# Custom Rocket Hardware - build123d geometry
# ---------------------------------------------------------------------------

def gen_eyebolts():
    """
    DIN 580 lifting eye bolts - M6, M8, M10, M12.
    Used as recovery attachment points (shock cord anchor to airframe bulkhead).

    DIN 580 dimensions (mm):
      size  d1   d2   d3   d4   b    shank  collar_h
      M6     6   20   36   20   8     16      7
      M8     8   25   45   25   10    20      9
      M10   10   30   54   30   12    25     11
      M12   12   36   63   36   13.5  30     13
    """
    print("\n[Eyebolts - DIN 580]")

    specs = [
        # (size, d1, d2, d3, d4, b, shank_l, collar_h)
        ("M6",  6,  20, 36, 20, 8,    16, 7),
        ("M8",  8,  25, 45, 25, 10,   20, 9),
        ("M10", 10, 30, 54, 30, 12,   25, 11),
        ("M12", 12, 36, 63, 36, 13.5, 30, 13),
    ]

    for size, d1, d2, _d3, d4, b, shank_l, collar_h in specs:
        ring_major = (d4 / 2) + (b / 2)   # torus major radius (center of wire)
        ring_minor = b / 2                  # torus minor radius (wire cross-section)
        ring_center_z = shank_l + collar_h + ring_major

        with BuildPart() as eyebolt:
            # Shank
            Cylinder(radius=d1 / 2, height=shank_l,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Collar
            with Locations(Pos(0, 0, shank_l)):
                Cylinder(radius=d2 / 2, height=collar_h,
                         align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Eye ring - torus rotated 90deg around X so ring is in XZ plane (vertical)
            with Locations(Pos(0, 0, ring_center_z) * Rot(90, 0, 0)):
                Torus(major_radius=ring_major, minor_radius=ring_minor)

        save(eyebolt.part, f"recovery/eyebolt/{size}.step", {
            "name": f"Eyebolt {size} DIN 580",
            "category": "recovery",
            "subcategory": "eyebolt",
            "standard": "DIN 580",
            "thread": size,
            "eye_inner_dia_mm": d4,
            "shank_length_mm": shank_l,
            "collar_dia_mm": d2,
            "material": "steel",
            "description": (
                f"{size} lifting eye bolt per DIN 580. "
                "Screws into bulkhead T-nut or threaded insert. "
                "Primary recovery attachment point for shock cord. "
                f"Eye inner diameter {d4}mm, accepts quick link up to {int(d4 * 0.7)}mm wire."
            ),
            "use_cases": [
                "shock_cord_anchor", "recovery_attachment", "bulkhead_mount", "lifting_point",
            ],
        }, generator="build123d")


def gen_rail_buttons():
    """
    Standard rocket rail buttons for 8020 aluminum extrusion launch rails.

    1010 rail (1in x 1in, T-slot width ~9.5mm):
      Button: 9.0mm wide x 6.25mm tall, 15mm base, M4 clearance hole

    1515 rail (1.5in x 1.5in, T-slot width ~12.7mm):
      Button: 12.0mm wide x 9.0mm tall, 20mm base, M5 clearance hole
    """
    print("\n[Rail Buttons - 1010 / 1515]")

    specs = [
        # (rail_name, slot_w, slot_h, base_r, base_h, screw_r, corner_r)
        ("1010", 9.0,  6.25, 7.5,  3.0, 2.1, 1.5),
        ("1515", 12.0, 9.0,  10.0, 4.0, 2.6, 2.0),
    ]

    for rail, slot_w, slot_h, base_r, base_h, screw_r, corner_r in specs:
        with BuildPart() as btn:
            # Base flange (circular, flush against rocket body)
            Cylinder(radius=base_r, height=base_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Button profile - rounded square that engages the T-slot
            with BuildSketch(Plane(origin=(0, 0, base_h))):
                RectangleRounded(slot_w, slot_w, corner_r)
            extrude(amount=slot_h)
            # Through-hole for mounting screw
            Cylinder(radius=screw_r, height=base_h + slot_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)

        save(btn.part, f"launch/rail_button_{rail}.step", {
            "name": f"Rail Button {rail}",
            "category": "launch",
            "subcategory": "rail_button",
            "rail_size": rail,
            "slot_width_mm": slot_w,
            "slot_height_mm": slot_h,
            "base_diameter_mm": base_r * 2,
            "screw_clearance_mm": screw_r * 2,
            "material": "delrin",
            "description": (
                f"Standard rail button for {rail} 8020 aluminum extrusion launch rail. "
                f"Button width {slot_w}mm fits {rail} T-slot. "
                "Mounted to rocket body tube with single screw through center. "
                "Guides rocket along launch rail, releases cleanly at lift-off."
            ),
            "use_cases": ["launch_rail_guide", "launch_lug_replacement"],
        }, generator="build123d")


def gen_quick_links():
    """
    Oval screw-gate quick links for parachute/shock cord connections.
    Built as a stadium-ring solid (two half-cylinders + box bridge).

    Approximate dimensions (wire dia x inner width x inner length):
      3mm: 11mm x 25mm
      4mm: 13mm x 30mm
      6mm: 18mm x 42mm
    """
    print("\n[Quick Links - oval screw-gate]")

    specs = [
        # (wire_dia, inner_width, inner_length, wll_kg)
        (3,  11, 25,  400),
        (4,  13, 30,  800),
        (6,  18, 42, 1600),
    ]

    for wd, iw, il, wll in specs:
        wr = wd / 2
        sl = il - iw  # straight section length

        with BuildPart() as ql:
            # Outer solid: two end cylinders + middle box, fused
            with Locations(Pos(sl / 2, 0, 0)):
                Cylinder(radius=iw / 2 + wd, height=wd,
                         align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations(Pos(-sl / 2, 0, 0)):
                Cylinder(radius=iw / 2 + wd, height=wd,
                         align=(Align.CENTER, Align.CENTER, Align.MIN))
            Box(sl, iw + wd * 2, wd,
                align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Subtract inner opening: two half-cylinders + middle box
            with Locations(Pos(sl / 2, 0, -0.005)):
                Cylinder(radius=iw / 2, height=wd + 0.01,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
            with Locations(Pos(-sl / 2, 0, -0.005)):
                Cylinder(radius=iw / 2, height=wd + 0.01,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
            Box(sl + 0.01, iw, wd + 0.01,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        save(ql.part, f"recovery/quick_link/{wd}mm.step", {
            "name": f"Quick Link {wd}mm",
            "category": "recovery",
            "subcategory": "quick_link",
            "wire_dia_mm": wd,
            "inner_width_mm": iw,
            "inner_length_mm": il,
            "working_load_limit_kg": wll,
            "material": "stainless_steel",
            "description": (
                f"{wd}mm wire oval quick link (screw-gate). "
                "Connects shock cord to eyebolt, parachute bridle to harness, "
                "or swivel to recovery hardware. "
                f"Working load limit ~{wll}kg. Inner opening {iw}x{il}mm."
            ),
            "use_cases": [
                "shock_cord_to_eyebolt", "parachute_bridle",
                "recovery_harness", "swivel_connection",
            ],
        }, generator="build123d")


def gen_gopro_mount():
    """
    GoPro-compatible 3-prong finger mount for rocket camera bay.

    Standard GoPro finger mount dimensions:
      Prong thickness: 3.0mm
      Gap between prongs: 3.1mm
      Prong depth: 16mm
      Prong height: 14mm
      Pivot hole: 5mm dia (M5 thumb screw)
      Base: 26mm x 20mm x 4mm, M3 mounting holes
    """
    print("\n[GoPro Step Mount]")

    prong_t  = 3.0
    gap      = 3.1
    prong_w  = 16.0
    prong_h  = 14.0
    hole_r   = 2.5   # 5mm dia pivot hole
    base_w   = 26.0
    base_d   = 20.0
    base_h   = 4.0
    total_w  = 3 * prong_t + 2 * gap  # ~15.2mm

    with BuildPart() as mount:
        # Base plate
        Box(base_w, base_d, base_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Three prongs
        for px in [-(prong_t + gap), 0.0, +(prong_t + gap)]:
            with Locations(Pos(px, 0, base_h)):
                Box(prong_t, prong_w, prong_h,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Pivot hole through all prongs (rotated to horizontal)
        pivot_z = base_h + prong_h - 5
        with Locations(Pos(0, 0, pivot_z) * Rot(0, 90, 0)):
            Cylinder(radius=hole_r, height=total_w + 8,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # Base mounting holes (M3 clearance, 4-corner)
        for bx, by in [(-9.0, -6.0), (9.0, -6.0), (-9.0, 6.0), (9.0, 6.0)]:
            with Locations(Pos(bx, by, 0)):
                Cylinder(radius=1.6, height=base_h,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)

    save(mount.part, "camera/gopro_mount.step", {
        "name": "GoPro Step Mount",
        "category": "camera",
        "subcategory": "gopro_mount",
        "standard": "GoPro finger mount",
        "prong_count": 3,
        "prong_thickness_mm": prong_t,
        "gap_mm": gap,
        "pivot_hole_dia_mm": hole_r * 2,
        "base_footprint_mm": [base_w, base_d],
        "mount_screw": "M3",
        "description": (
            "3-prong GoPro-compatible finger mount for rocket camera bay. "
            "Standard GoPro pivoting finger mount geometry. "
            "Accepts GoPro Hero/Session cameras and compatible action cameras. "
            "Base mounts to payload bay step adapter with 4x M3 screws. "
            "Pivot hole accepts M5 thumb screw."
        ),
        "use_cases": ["camera_bay", "nose_cone_camera", "payload_section"],
    }, generator="build123d")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("RocketSmith Parts Dataset Generator")
    print("=" * 60)

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # Standard fasteners (bd_warehouse - exact ISO/DIN spec)
    gen_socket_head_cap_screws()
    gen_button_head_screws()
    gen_pan_head_screws()
    gen_countersunk_screws()
    gen_set_screws()
    gen_hex_nuts()
    gen_heat_set_inserts()
    gen_plain_washers()

    # Custom rocket hardware (build123d geometry)
    gen_eyebolts()
    gen_rail_buttons()
    gen_quick_links()
    gen_gopro_mount()

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- parts.jsonl (one record per line, mirrors files.jsonl format) ---
    jsonl_path = METADATA_DIR / "parts.jsonl"
    with open(jsonl_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # --- parts.csv ---
    csv_path = METADATA_DIR / "parts.csv"
    # Collect all keys, put primary fields first
    primary = [
        "local_path", "original_name", "category", "subcategory",
        "standard", "generator", "source_url", "standard_url",
        "content_length", "sha256", "generated_at", "status",
    ]
    all_keys = primary + [k for k in records[0] if k not in primary]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    # --- parts_summary.json (mirrors crawl_summary.json format) ---
    by_category: dict[str, int] = {}
    by_subcategory: dict[str, int] = {}
    by_generator: dict[str, int] = {}
    by_standard: dict[str, int] = {}
    total_bytes = 0

    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
        by_subcategory[r["subcategory"]] = by_subcategory.get(r["subcategory"], 0) + 1
        by_generator[r["generator"]] = by_generator.get(r["generator"], 0) + 1
        std = r.get("standard", "custom")
        by_standard[std] = by_standard.get(std, 0) + 1
        total_bytes += r["content_length"]

    summary = {
        "generated_at": generated_at,
        "total_parts": len(records),
        "parts_ok": sum(1 for r in records if r["status"] == "ok"),
        "parts_failed": sum(1 for r in records if r["status"] != "ok"),
        "by_category": by_category,
        "by_subcategory": by_subcategory,
        "by_generator": by_generator,
        "by_standard": by_standard,
        "total_bytes": total_bytes,
    }

    summary_path = METADATA_DIR / "parts_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nMetadata written to {METADATA_DIR}/")
    print(f"  parts.jsonl     ({len(records)} records)")
    print(f"  parts.csv       ({len(records)} rows)")
    print(f"  parts_summary.json")
    print(f"\nTotal parts: {len(records)}  |  Total size: {total_bytes / 1024:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
