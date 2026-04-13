# Parts Visualization Workflow

This document explains the complete workflow for how the parts database is created and visualized.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Parts Generation Pipeline                     │
└─────────────────────────────────────────────────────────────────┘

Step 1: Generate Geometry
├── bd_warehouse (fasteners)
│   └── ISO/DIN parametric models → STEP files
└── build123d (custom parts)
    └── Parametric CAD models → STEP files

Step 2: Store with Metadata
└── STEP files + JSON metadata → dataset/parts/

Step 3: Visualization
├── STEP → GLTF conversion
├── Generate HTML viewer
└── Web server → Interactive 3D browser

Step 4: Quality Control
└── Visual inspection for accuracy
```

## Data Flow

```
generate_parts.py
    ↓
dataset/parts/*.step (115 files)
    +
dataset/hf_parts/data/parts.jsonl (metadata)
    ↓
visualize_parts.py
    ↓
dataset/parts_viewer/*.gltf (115 files)
    +
dataset/parts_viewer/index.json (catalog)
    +
dataset/parts_viewer/index.html (viewer app)
    ↓
python -m http.server 8080
    ↓
http://localhost:8080 (browser)
```

## Script Breakdown

### 1. `generate_parts.py`

**Purpose**: Generate all rocket hardware parts as STEP files

**How it works**:
- Imports `bd_warehouse` for standard fasteners (ISO/DIN specs)
- Imports `build123d` for custom rocket hardware
- Creates parametric 3D models for each part
- Exports to STEP format (CAD standard)
- Generates comprehensive metadata (JSONL, CSV, summary)

**Example - Socket Head Cap Screws**:
```python
def gen_socket_head_cap_screws():
    variants = {
        "M2-0.4": [4, 6, 8],
        "M3-0.5": [6, 8, 10, 12, 16],
        # ... more sizes
    }
    for size, lengths in variants.items():
        for length in lengths:
            # Create the screw using bd_warehouse
            part = SocketHeadCapScrew(size, length, "iso4762", 
                                      simple=True, mode=Mode.PRIVATE)
            
            # Save as STEP file with metadata
            save(part, f"fasteners/socket_head_cap_screw/M{size.split('-')[0]}x{length}.step", {
                "name": f"Socket Head Cap Screw M{size.split('-')[0]}x{length}",
                "category": "fastener",
                "standard": "ISO 4762",
                # ... more metadata
            })
```

**Example - Custom Eyebolts**:
```python
def gen_eyebolts():
    specs = [
        # (size, d1, d2, d3, d4, b, shank_l, collar_h)
        ("M6",  6,  20, 36, 20, 8,    16, 7),
        ("M8",  8,  25, 45, 25, 10,   20, 9),
        # ... more sizes
    ]
    
    for size, d1, d2, _d3, d4, b, shank_l, collar_h in specs:
        # Calculate torus dimensions
        ring_major = (d4 / 2) + (b / 2)
        ring_minor = b / 2
        
        # Build the eyebolt using build123d primitives
        with BuildPart() as eyebolt:
            # Threaded shank
            Cylinder(radius=d1/2, height=shank_l, ...)
            
            # Collar base
            with Locations(Pos(0, 0, shank_l)):
                Cylinder(radius=d2/2, height=collar_h, ...)
            
            # Lifting ring
            with Locations(Pos(0, 0, ring_center_z) * Rot(90, 0, 0)):
                Torus(major_radius=ring_major, minor_radius=ring_minor)
        
        save(eyebolt.part, f"recovery/eyebolt/{size}.step", {...})
```

**Output**:
- 115 STEP files in `dataset/parts/`
- `dataset/parts/metadata/parts.jsonl` - One JSON record per part
- `dataset/parts/metadata/parts.csv` - Spreadsheet view
- `dataset/parts/metadata/parts_summary.json` - Statistics

### 2. `visualize_parts.py` (COMPLETED)

**Purpose**: Convert STEP files to web-viewable GLTF and create interactive viewer

**How it works**:

#### Phase 1: Load Database
```python
# Read all parts from the metadata
with open("dataset/hf_parts/data/parts.jsonl") as f:
    parts_data = [json.loads(line) for line in f]

# Organize by category
by_category = {}
for part_data in parts_data:
    meta = part_data["metadata"]
    category = meta["category"]
    by_category[category].append(part_data)
```

#### Phase 2: Convert STEP → GLTF
```python
def convert_step_to_gltf(step_path, gltf_name, label, category, description):
    # Import STEP file using build123d
    part = import_step(str(step_path))
    
    # Export to GLTF (web format)
    gltf_path = f"dataset/parts_viewer/{gltf_name}.gltf"
    export_gltf(part, gltf_path, binary=False)
    
    # Add to viewer catalog
    parts_for_viewer.append({
        "name": gltf_name,
        "label": label,
        "category": category,
        "description": description,
        "file": f"{gltf_name}.gltf",
    })
```

#### Phase 3: Generate HTML Viewer
```python
# Write catalog
with open("dataset/parts_viewer/index.json", "w") as f:
    json.dump(parts_for_viewer, f, indent=2)

# Generate self-contained HTML with:
# - Three.js 3D rendering
# - Sidebar with part list
# - Interactive camera controls
# - Part metadata display
with open("dataset/parts_viewer/index.html", "w") as f:
    f.write(html_template)
```

**Key Features**:
- **Automatic conversion**: Reads from metadata, no manual part list
- **Category organization**: Groups parts by type (fastener, recovery, etc.)
- **Rich metadata**: Shows descriptions, standards, use cases
- **Material variants**: Different materials per category (metallic, matte, etc.)
- **Error handling**: Gracefully handles missing/corrupt files

**Output**:
- 115 GLTF files in `dataset/parts_viewer/`
- `dataset/parts_viewer/index.json` - Catalog for web app
- `dataset/parts_viewer/index.html` - Complete viewer application
- `dataset/parts_viewer/README.md` - Documentation

## How Parts Are Generated from bd_warehouse

bd_warehouse uses parametric models based on exact ISO/DIN specifications:

### Example: ISO 4762 Socket Head Cap Screw

```python
from bd_warehouse.fastener import SocketHeadCapScrew
from build123d import Mode

# Create M3x10 screw per ISO 4762
screw = SocketHeadCapScrew(
    size="M3-0.5",           # M3 thread, 0.5mm pitch
    length=10,               # 10mm nominal length
    fastener_type="iso4762", # ISO 4762 standard
    simple=True,             # Simplified (no thread detail)
    mode=Mode.PRIVATE        # Don't add to scene
)

# The library looks up ISO 4762 table for M3:
# - Head diameter: 5.5mm
# - Head height: 3.0mm
# - Socket size: 2.5mm hex
# - Socket depth: 1.5mm
# - Shank diameter: 3.0mm

# Then generates exact geometry matching the spec
```

### What `simple=True` does:
- **Simplified geometry**: Smooth cylinder for threads (no helix)
- **Faster export**: 10x smaller STEP files
- **Correct dimensions**: Nominal thread diameter per standard
- **Visualization focus**: Perfect for visual checking

### Standard references used:
- ISO 4762: Socket Head Cap Screws
- ISO 7380-1: Button Head Screws
- ISO 1580: Pan Head Screws
- ISO 7046: Countersunk Screws
- ISO 4026: Set Screws (cup point)
- ISO 4032: Hex Nuts
- ISO 7093: Large Plain Washers
- Hilitchi: Heat Set Insert dimensions

## Using the Viewer for Quality Control

### 1. Visual Inspection
- Click through each part in the sidebar
- Verify overall shape and proportions
- Check that features are present (heads, holes, threads)

### 2. Dimensional Verification
- Compare relative sizes within a category
- Verify M3 is smaller than M4, M5, M6
- Check length progression (6mm < 8mm < 10mm)

### 3. Standard Compliance
- Read the description to see which ISO/DIN standard
- Verify head shapes match standard types:
  - Socket head: cylindrical with hex socket
  - Button head: low dome with hex socket
  - Pan head: wide flat dome
  - Countersunk: flat flush 90° cone

### 4. Category Accuracy
- **Fasteners**: Should be metallic, precise geometry
- **Recovery**: Eyebolts have lifting rings, quick links are oval
- **Launch**: Rail buttons have T-slot profiles
- **Camera**: GoPro mount has 3-prong finger pattern

## Running the Complete Pipeline

```bash
# From repository root

# Step 1: Generate STEP files (if needed)
uv run python dataset/generate_parts.py
# Output: 115 STEP files + metadata

# Step 2: Create visualization
uv run python dataset/visualize_parts.py
# Output: 115 GLTF files + HTML viewer

# Step 3: Launch viewer
cd dataset/parts_viewer
python -m http.server 8080

# Step 4: Open in browser
# Visit: http://localhost:8080
```

## Troubleshooting

### Parts don't load in viewer
- Check browser console for errors
- Verify GLTF files exist: `ls dataset/parts_viewer/*.gltf | wc -l` (should be 115)
- Ensure server is running on port 8080

### STEP conversion fails
- Verify build123d is installed: `uv pip list | grep build123d`
- Check STEP file exists and isn't corrupted
- Look at error message in conversion output

### Geometry looks wrong
1. Check the source STEP file in CAD software (FreeCAD, Fusion 360)
2. Verify dimensions in metadata match standard
3. Review generation code in `generate_parts.py`

## File Formats Explained

### STEP (.step, .stp)
- **Purpose**: CAD interchange format (ISO 10303)
- **Content**: Exact 3D geometry + metadata
- **Size**: 20-50 KB per fastener
- **Use**: Manufacturing, 3D printing, CAD import

### GLTF (.gltf)
- **Purpose**: Web 3D graphics format
- **Content**: Mesh geometry + materials + scene graph
- **Size**: 15-40 KB per part (JSON + embedded)
- **Use**: Web visualization, Three.js rendering

### JSONL (.jsonl)
- **Purpose**: Streaming JSON (one object per line)
- **Content**: Part metadata (name, category, dimensions, etc.)
- **Use**: Database import, search indexing

## Next Steps

1. **Extend the database**: Add more part types (bearings, springs, electronics)
2. **Improve visualization**: Add dimension overlays, cross-sections
3. **Export formats**: Generate STL for 3D printing, DXF for laser cutting
4. **Search functionality**: Filter by size, standard, use case
5. **Comparison mode**: View multiple parts side-by-side

## Credits

- **bd_warehouse**: https://github.com/gumyr/bd_warehouse
- **build123d**: https://github.com/gumyr/build123d
- **Three.js**: https://threejs.org/
- **ISO/DIN Standards**: International Organization for Standardization
