#!/usr/bin/env python3
"""
Visualize ALL generated rocket parts by converting STEP files to GLTF
and generating a self-contained HTML viewer.

Run:
  uv run python dataset/visualize_parts.py
  # then open dataset/parts_viewer/index.html in a browser
"""

import json
from pathlib import Path

from build123d import import_step, export_gltf

PARTS_DIR = Path("dataset/parts")
METADATA_FILE = Path("dataset/hf_parts/data/parts.jsonl")
GLTF_DIR = Path("dataset/parts_viewer")
GLTF_DIR.mkdir(exist_ok=True)

parts_for_viewer = []


def convert_step_to_gltf(step_path: Path, gltf_name: str, label: str, category: str, description: str = "") -> bool:
    """Convert a STEP file to GLTF format for web visualization."""
    try:
        # Import the STEP file
        part = import_step(str(step_path))
        
        # Export to GLTF
        gltf_path = GLTF_DIR / f"{gltf_name}.gltf"
        export_gltf(part, str(gltf_path), binary=False)
        
        parts_for_viewer.append({
            "name": gltf_name,
            "label": label,
            "category": category,
            "description": description,
            "file": f"{gltf_name}.gltf",
        })
        print(f"  [OK] {label}")
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


# --- Load parts database and convert all parts ---

print("=" * 60)
print("Converting STEP files to GLTF for visualization")
print("=" * 60)

# Read the parts database
with open(METADATA_FILE, "r") as f:
    parts_data = [json.loads(line) for line in f]

print(f"\nFound {len(parts_data)} parts in database\n")

# Group parts by category for organized display
by_category = {}
for part_data in parts_data:
    meta = part_data.get("metadata", {})
    category = meta.get("category", "unknown")
    if category not in by_category:
        by_category[category] = []
    by_category[category].append(part_data)

# Convert each part
total = 0
success = 0
for category in sorted(by_category.keys()):
    parts_list = by_category[category]
    print(f"\n[{category.upper()}] ({len(parts_list)} parts)")
    
    for part_data in parts_list:
        meta = part_data.get("metadata", {})
        local_path = meta.get("local_path", "")
        
        if not local_path:
            continue
            
        step_path = Path(local_path)
        if not step_path.exists():
            print(f"  [SKIP] File not found: {step_path}")
            continue
        
        # Generate a clean GLTF filename
        gltf_name = step_path.stem.replace(" ", "_")
        subcategory = meta.get("subcategory", "")
        if subcategory:
            gltf_name = f"{subcategory}_{gltf_name}"
        
        # Get metadata for the viewer
        label = meta.get("original_name", step_path.stem)
        description = meta.get("description", "")
        
        total += 1
        if convert_step_to_gltf(step_path, gltf_name, label, category, description):
            success += 1

print(f"\n{'-' * 60}")
print(f"Conversion complete: {success}/{total} parts converted successfully")
print(f"{'-' * 60}\n")

# --- Write index.json for the viewer ---
(GLTF_DIR / "index.json").write_text(json.dumps(parts_for_viewer, indent=2))

# --- Generate self-contained HTML viewer ---
html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RocketSmith Parts Viewer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #111; color: #eee; display: flex; height: 100vh; overflow: hidden; }
    #sidebar { width: 280px; min-width: 280px; background: #1a1a1a; overflow-y: auto; border-right: 1px solid #333; padding: 12px 0; }
    #sidebar h1 { font-size: 13px; font-weight: 700; color: #aaa; text-transform: uppercase; letter-spacing: 1px; padding: 0 16px 8px; border-bottom: 1px solid #333; margin-bottom: 8px; }
    #stats { font-size: 11px; color: #666; padding: 0 16px 12px; border-bottom: 1px solid #333; margin-bottom: 8px; }
    .category { font-size: 11px; font-weight: 700; color: #666; text-transform: uppercase; letter-spacing: 1px; padding: 12px 16px 4px; }
    .part-btn { display: block; width: 100%; text-align: left; background: none; border: none; color: #ccc; font-size: 12px; padding: 6px 16px; cursor: pointer; transition: background 0.1s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .part-btn:hover { background: #2a2a2a; color: #fff; }
    .part-btn.active { background: #1e3a5f; color: #60a5fa; }
    #viewport { flex: 1; position: relative; }
    canvas { display: block; width: 100% !important; height: 100% !important; }
    #info-panel { position: absolute; top: 16px; left: 16px; max-width: 400px; background: rgba(0,0,0,0.8); padding: 12px 16px; border-radius: 8px; pointer-events: none; }
    #info-panel h2 { font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 8px; }
    #info-panel .meta { font-size: 11px; color: #999; margin-bottom: 8px; }
    #info-panel .description { font-size: 13px; color: #ddd; line-height: 1.5; }
    #hint { position: absolute; bottom: 16px; right: 16px; font-size: 11px; color: #666; pointer-events: none; }
    #source-info { position: absolute; bottom: 16px; left: 16px; font-size: 11px; color: #666; background: rgba(0,0,0,0.6); padding: 6px 10px; border-radius: 4px; pointer-events: none; }
  </style>
</head>
<body>
  <div id="sidebar">
    <h1>Parts Viewer</h1>
    <div id="stats">Loading parts...</div>
    <div id="part-list"></div>
  </div>
  <div id="viewport">
    <canvas id="canvas"></canvas>
    <div id="info-panel">
      <h2 id="part-name">Select a part</h2>
      <div id="part-meta" class="meta"></div>
      <div id="part-description" class="description"></div>
    </div>
    <div id="hint">Orbit: left drag &nbsp;|&nbsp; Pan: right drag &nbsp;|&nbsp; Zoom: scroll</div>
    <div id="source-info">Generated with bd_warehouse (ISO/DIN spec) and build123d</div>
  </div>

  <script type="importmap">
    { "imports": { "three": "https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js",
                   "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/" } }
  </script>
  <script type="module">
    import * as THREE from 'three';
    import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

    const canvas = document.getElementById('canvas');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x111111);
    renderer.shadowMap.enabled = true;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir1 = new THREE.DirectionalLight(0xffffff, 1.2);
    dir1.position.set(5, 10, 7);
    scene.add(dir1);
    const dir2 = new THREE.DirectionalLight(0x8888ff, 0.4);
    dir2.position.set(-5, -3, -5);
    scene.add(dir2);

    // Grid
    const grid = new THREE.GridHelper(200, 40, 0x333333, 0x222222);
    scene.add(grid);

    let currentMesh = null;
    const loader = new GLTFLoader();

    function loadPart(file, label, description = '', category = '') {
      document.getElementById('part-name').textContent = label;
      document.getElementById('part-meta').textContent = category ? `Category: ${category}` : '';
      document.getElementById('part-description').textContent = description || 'No description available';
      
      if (currentMesh) { scene.remove(currentMesh); currentMesh = null; }

      loader.load(file, (gltf) => {
        const model = gltf.scene;

        // Apply realistic material based on category
        const materialProps = category === 'fastener' 
          ? { color: 0x8899aa, metalness: 0.9, roughness: 0.2 }  // shiny metal
          : category === 'recovery'
          ? { color: 0xaaaaaa, metalness: 0.7, roughness: 0.3 }  // steel
          : { color: 0x99aa88, metalness: 0.5, roughness: 0.5 }; // other materials

        model.traverse(child => {
          if (child.isMesh) {
            child.material = new THREE.MeshStandardMaterial(materialProps);
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });

        // Center and scale
        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 50 / maxDim;
        model.position.sub(center.multiplyScalar(scale));
        model.scale.setScalar(scale);

        scene.add(model);
        currentMesh = model;

        // Fit camera
        camera.position.set(80, 60, 80);
        controls.target.set(0, 0, 0);
        controls.update();
      }, undefined, (error) => {
        console.error('Error loading part:', error);
        document.getElementById('part-description').textContent = 'Error loading model';
      });
    }

    // Build sidebar from index.json
    fetch('index.json').then(r => r.json()).then(parts => {
      const list = document.getElementById('part-list');
      const stats = document.getElementById('stats');
      
      // Update stats
      const categories = new Set(parts.map(p => p.category));
      stats.textContent = `${parts.length} parts in ${categories.size} categories`;
      
      let lastCat = '';
      parts.forEach((p, i) => {
        if (p.category !== lastCat) {
          const cat = document.createElement('div');
          cat.className = 'category';
          cat.textContent = p.category;
          list.appendChild(cat);
          lastCat = p.category;
        }
        const btn = document.createElement('button');
        btn.className = 'part-btn';
        btn.textContent = p.label;
        btn.title = p.description || p.label;
        btn.dataset.file = p.file;
        btn.dataset.label = p.label;
        btn.dataset.description = p.description || '';
        btn.dataset.category = p.category;
        btn.onclick = () => {
          document.querySelectorAll('.part-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          loadPart(p.file, p.label, p.description, p.category);
        };
        list.appendChild(btn);
        if (i === 0) btn.click();  // load first part automatically
      });
    });

    // Resize handler
    function resize() {
      const vp = document.getElementById('viewport');
      renderer.setSize(vp.clientWidth, vp.clientHeight);
      camera.aspect = vp.clientWidth / vp.clientHeight;
      camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', resize);
    resize();

    // Render loop
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });
  </script>
</body>
</html>"""

(GLTF_DIR / "index.html").write_text(html, encoding="utf-8")

print(f"\n{'=' * 60}")
print(f"Viewer written to: {GLTF_DIR}/index.html")
print(f"{'=' * 60}")
print("\nTo view the parts:")
print(f"  1. cd {GLTF_DIR}")
print(f"  2. python -m http.server 8080")
print(f"  3. Open http://localhost:8080 in your browser")
print(f"\nThe viewer shows:")
print(f"  • All {len(parts_for_viewer)} parts with 3D models")
print(f"  • Part descriptions and metadata")
print(f"  • How each part was generated (bd_warehouse/build123d)")
print(f"  • Interactive 3D view with orbit/pan/zoom controls")
print("=" * 60)
