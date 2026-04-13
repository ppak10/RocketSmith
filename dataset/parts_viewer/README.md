# RocketSmith Parts Viewer

An interactive 3D viewer for all rocket hardware parts in the RocketSmith parts database.

## Overview

This viewer displays **115 rocket hardware parts** organized into categories:
- **Fasteners** (105 parts): Screws, nuts, washers, heat-set inserts
- **Recovery** (7 parts): Eyebolts and quick links  
- **Launch** (2 parts): Rail buttons for 1010 and 1515 rails
- **Camera** (1 part): GoPro mounting bracket

## Quick Start

### View the Parts

1. Start the local web server:
   ```bash
   cd dataset/parts_viewer
   python -m http.server 8080
   ```

2. Open your browser to: **http://localhost:8080**

3. Browse the parts by category in the left sidebar
4. Click any part to view its 3D model

### Navigation Controls

- **Orbit**: Left-click and drag
- **Pan**: Right-click and drag  
- **Zoom**: Scroll wheel

## How Parts Are Generated

The parts in this database come from two sources:

### 1. **bd_warehouse** (Standard Fasteners)
- **Source**: https://github.com/gumyr/bd_warehouse
- **Geometry**: Parametric models based on exact ISO/DIN specifications
- **Parts**: All screws, nuts, washers, and heat-set inserts
- **Standards**:
  - ISO 4762: Socket Head Cap Screws
  - ISO 7380-1: Button Head Screws
  - ISO 1580: Pan Head Screws
  - ISO 7046: Countersunk Screws
  - ISO 4026: Set Screws
  - ISO 4032: Hex Nuts
  - ISO 7093: Plain Washers
  - Hilitchi: Heat Set Inserts

**Example** - Socket Head Cap Screw M3x10:
```python
from bd_warehouse.fastener import SocketHeadCapScrew
from build123d import Mode

screw = SocketHeadCapScrew(
    size="M3-0.5",      # M3 thread, 0.5mm pitch
    length=10,          # 10mm length
    fastener_type="iso4762",  # ISO 4762 standard
    simple=True,        # Simplified geometry (no threads)
    mode=Mode.PRIVATE   # Don't add to global context
)
```

### 2. **build123d** (Custom Rocket Hardware)
- **Source**: https://github.com/gumyr/build123d
- **Geometry**: Parametric CAD models designed specifically for rocketry
- **Parts**: Eyebolts, quick links, rail buttons, camera mounts

**Example** - Eyebolt M8 (DIN 580):
```python
from build123d import BuildPart, Cylinder, Torus, Align, Locations, Pos, Rot

# DIN 580 M8 dimensions (mm)
shank_dia = 8
collar_dia = 25
collar_height = 9
shank_length = 20
ring_outer_dia = 25
ring_wire_dia = 10

ring_major = (ring_outer_dia / 2) + (ring_wire_dia / 2)
ring_minor = ring_wire_dia / 2

with BuildPart() as eyebolt:
    # Threaded shank
    Cylinder(
        radius=shank_dia / 2, 
        height=shank_length,
        align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    
    # Collar base
    with Locations(Pos(0, 0, shank_length)):
        Cylinder(
            radius=collar_dia / 2, 
            height=collar_height,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
    
    # Lifting ring (torus rotated 90° to be vertical)
    ring_center_z = shank_length + collar_height + ring_major
    with Locations(Pos(0, 0, ring_center_z) * Rot(90, 0, 0)):
        Torus(major_radius=ring_major, minor_radius=ring_minor)
```

## File Format Pipeline

```
STEP (.step) → GLTF (.gltf) → Web Viewer (Three.js)
```

### Why STEP?
- Industry-standard 3D CAD format (ISO 10303)
- Preserves exact geometry and dimensions
- Compatible with all CAD software
- Used in manufacturing and 3D printing

### Why GLTF?
- Optimized for web visualization
- Native support in Three.js
- Smaller file size than STEP
- Fast loading in browsers

### Conversion Process
```python
from build123d import import_step, export_gltf

# Import STEP file
part = import_step("dataset/parts/fasteners/socket_head_cap_screw/M3x10.step")

# Export to GLTF for web viewing
export_gltf(part, "dataset/parts_viewer/socket_head_cap_screw_M3x10.gltf", binary=False)
```

## Metadata

Each part includes comprehensive metadata:
- **Name**: Human-readable part name
- **Category/Subcategory**: Organizational hierarchy
- **Standard**: ISO/DIN specification (if applicable)
- **Dimensions**: Thread size, length, diameter, etc.
- **Material**: Steel, brass, stainless steel, or Delrin
- **Description**: Use cases and application notes
- **Generator**: Which library was used to create the geometry
- **Source URLs**: Links to specifications and documentation

Example metadata for Socket Head Cap Screw M3x10:
```json
{
  "name": "Socket Head Cap Screw M3x10",
  "category": "fastener",
  "subcategory": "socket_head_cap_screw",
  "standard": "ISO 4762",
  "thread": "M3-0.5",
  "length_mm": 10,
  "drive": "hex_socket",
  "material": "steel",
  "description": "M3 socket head cap screw, 10mm length. Used for structural assembly, fin attachments, avionics bay covers, motor retainer screws. High strength, low profile hex socket drive.",
  "use_cases": ["fin_attachment", "avionics_bay", "motor_retainer", "coupler"],
  "generator": "bd_warehouse==0.2.0",
  "geometry_method": "parametric",
  "source_url": "https://github.com/gumyr/bd_warehouse",
  "standard_url": "https://www.iso.org/standard/75918.html"
}
```

## Regenerating the Viewer

To regenerate the viewer after adding new parts:

```bash
# 1. Generate new STEP files (if needed)
uv run python dataset/generate_parts.py

# 2. Convert STEP files to GLTF and build HTML viewer
uv run python dataset/visualize_parts.py

# 3. Start the viewer
cd dataset/parts_viewer
python -m http.server 8080
```

## Technical Details

### Web Technologies
- **Three.js 0.165.0**: 3D rendering engine
- **GLTFLoader**: Loads 3D models
- **OrbitControls**: Interactive camera controls
- **WebGL**: Hardware-accelerated 3D graphics

### Rendering Features
- Physically-based rendering (PBR) materials
- Dynamic lighting (ambient + 2 directional lights)
- Real-time shadows
- Anti-aliasing
- Adaptive scaling (parts auto-fit to viewport)

### Materials by Category
- **Fasteners**: Metallic steel (metalness: 0.9, roughness: 0.2)
- **Recovery**: Matte steel (metalness: 0.7, roughness: 0.3)  
- **Launch/Camera**: Hybrid materials (metalness: 0.5, roughness: 0.5)

## File Structure

```
dataset/parts_viewer/
├── index.html              # Main viewer application (self-contained)
├── index.json              # Parts catalog metadata
├── README.md               # This file
└── [115 .gltf files]       # 3D models for each part
```

## Part Naming Convention

GLTF files are named using the pattern: `{subcategory}_{part_id}.gltf`

Examples:
- `socket_head_cap_screw_M3x10.gltf`
- `eyebolt_M8.gltf`
- `rail_button_1010.gltf`
- `gopro_mount.gltf`

## Accuracy & Quality Control

Use this viewer to:
1. **Verify geometry**: Check that parts match specifications
2. **Inspect dimensions**: Ensure proper proportions and sizing
3. **Validate standards compliance**: Confirm ISO/DIN conformance
4. **Review for errors**: Catch any generation issues

All fasteners use `simple=True` mode, which provides:
- Clean geometry without thread detail
- Faster rendering
- Smaller file sizes
- Standard outer dimensions per specifications

Thread details are omitted for visualization but the nominal dimensions (major diameter, pitch, length) are exact per the standard.

## Browser Compatibility

Tested on:
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

Requires WebGL support.

## License

Parts database and viewer code are part of the RocketSmith project.

External dependencies:
- **bd_warehouse**: MIT License
- **build123d**: Apache 2.0 License
- **Three.js**: MIT License
