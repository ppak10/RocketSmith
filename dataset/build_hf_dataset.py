#!/usr/bin/env python3
"""
Build the Hugging Face dataset structure for rocketsmith/RocketParts.

Mirrors the layout of rocketsmith/RocketReviews:
  data/<config>.jsonl       - one record per part (id, document, metadata)
  source/parts/
    metadata/               - parts_summary.json
    files/step/             - STEP geometry files (git-lfs tracked)

Run:
  uv run python dataset/build_hf_dataset.py

Then push:
  cd dataset/hf_parts
  git init
  huggingface-cli repo create rocketsmith/RocketParts --type dataset
  git remote add origin https://huggingface.co/datasets/rocketsmith/RocketParts
  git add .
  git commit -m "Initial dataset"
  git push origin main
"""

import json
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PARTS_JSONL   = Path("dataset/parts/metadata/parts.jsonl")
PARTS_SUMMARY = Path("dataset/parts/metadata/parts_summary.json")
STEP_ROOT     = Path("dataset/parts")

HF_ROOT       = Path("dataset/hf_parts")
HF_DATA       = HF_ROOT / "data"
HF_SOURCE     = HF_ROOT / "source/parts"


# ---------------------------------------------------------------------------
# Document builder
# ---------------------------------------------------------------------------

def make_document(r: dict) -> str:
    """
    Produce a rich text string suitable for embedding.
    Format mirrors RocketReviews: "<Name>: <description> <key facts>"
    """
    parts = [f"{r['name']}:"]
    parts.append(r["description"])

    # Append key structured facts for retrieval
    facts = []
    if "standard" in r and r["standard"]:
        facts.append(f"Standard: {r['standard']}.")
    if "thread" in r:
        facts.append(f"Thread: {r['thread']}.")
    if "length_mm" in r:
        facts.append(f"Length: {r['length_mm']}mm.")
    if "drive" in r:
        facts.append(f"Drive: {r['drive'].replace('_', ' ')}.")
    if "material" in r:
        facts.append(f"Material: {r['material'].replace('_', ' ')}.")
    if "wire_dia_mm" in r:
        facts.append(f"Wire diameter: {r['wire_dia_mm']}mm.")
    if "inner_width_mm" in r:
        facts.append(f"Inner opening: {r['inner_width_mm']}x{r['inner_length_mm']}mm.")
    if "working_load_limit_kg" in r:
        facts.append(f"Working load limit: {r['working_load_limit_kg']}kg.")
    if "eye_inner_dia_mm" in r:
        facts.append(f"Eye inner diameter: {r['eye_inner_dia_mm']}mm.")
    if "rail_size" in r:
        facts.append(f"Rail size: {r['rail_size']}.")
    if "use_cases" in r:
        uc = ", ".join(u.replace("_", " ") for u in r["use_cases"])
        facts.append(f"Use cases: {uc}.")
    if "generator" in r:
        facts.append(f"Geometry source: {r['generator']}.")

    if facts:
        parts.append(" ".join(facts))

    return " ".join(parts)


def make_id(r: dict) -> str:
    """Build a stable slug-style id from the local path."""
    # e.g. dataset/parts/fasteners/socket_head_cap_screw/M3x10.step
    #  ->  parts:fasteners/socket_head_cap_screw/M3x10
    rel = r["local_path"].replace("dataset/parts/", "").replace(".step", "")
    return f"parts:{rel}"


def make_step_dest(r: dict) -> Path:
    """Map local_path to the HF source tree destination."""
    rel = r["local_path"].replace("dataset/parts/", "")  # e.g. fasteners/socket_head_cap_screw/M3x10.step
    return HF_SOURCE / "files/step" / rel


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    print("=" * 60)
    print("Building rocketsmith/RocketParts HF dataset")
    print("=" * 60)

    # Load all records
    records = []
    with open(PARTS_JSONL) as f:
        for line in f:
            records.append(json.loads(line))

    print(f"Loaded {len(records)} part records")

    # Setup output dirs
    HF_DATA.mkdir(parents=True, exist_ok=True)
    (HF_SOURCE / "metadata").mkdir(parents=True, exist_ok=True)
    (HF_SOURCE / "files/step").mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------------
    # Build HF records
    # ---------------------------------------------------------------------------
    hf_records = []
    for r in records:
        hf_records.append({
            "id":       make_id(r),
            "document": make_document(r),
            "metadata": {k: v for k, v in r.items() if k not in ("error",)},
        })

    # ---------------------------------------------------------------------------
    # Write data/<config>.jsonl files
    # ---------------------------------------------------------------------------
    configs = {
        "parts":      hf_records,                                                         # all (default)
        "fasteners":  [x for x in hf_records if x["metadata"]["category"] == "fastener"],
        "recovery":   [x for x in hf_records if x["metadata"]["category"] == "recovery"],
        "launch":     [x for x in hf_records if x["metadata"]["category"] == "launch"],
        "camera":     [x for x in hf_records if x["metadata"]["category"] == "camera"],
    }

    print("\n[Writing data/ JSONL configs]")
    for name, rows in configs.items():
        out = HF_DATA / f"{name}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print(f"  + data/{name}.jsonl  ({len(rows)} rows)")

    # ---------------------------------------------------------------------------
    # Copy STEP files into source/parts/files/step/
    # ---------------------------------------------------------------------------
    print("\n[Copying STEP files to source/]")
    for r in records:
        src  = STEP_ROOT / r["local_path"].replace("dataset/parts/", "")
        dest = make_step_dest(r)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    print(f"  Copied {len(records)} STEP files")

    # ---------------------------------------------------------------------------
    # Copy metadata
    # ---------------------------------------------------------------------------
    shutil.copy2(PARTS_SUMMARY, HF_SOURCE / "metadata/parts_summary.json")
    print("  Copied parts_summary.json")

    # ---------------------------------------------------------------------------
    # .gitattributes (git-lfs for STEP files)
    # ---------------------------------------------------------------------------
    gitattributes = (
        "*.step filter=lfs diff=lfs merge=lfs -text\n"
        "*.parquet filter=lfs diff=lfs merge=lfs -text\n"
    )
    (HF_ROOT / ".gitattributes").write_text(gitattributes)
    print("\n  + .gitattributes (LFS for .step and .parquet)")

    # ---------------------------------------------------------------------------
    # README.md dataset card
    # ---------------------------------------------------------------------------
    with open(PARTS_SUMMARY) as f:
        summary = json.load(f)

    by_sub = summary["by_subcategory"]
    by_gen = summary["by_generator"]
    by_std = summary["by_standard"]
    total_mb = summary["total_bytes"] / 1_048_576

    readme = f"""---
license: mit
task_categories:
- text-generation
- question-answering
tags:
- rocketry
- aerospace
- hardware
- cad
- step
- rag
configs:
- config_name: default
  data_files:
  - split: train
    path: data/parts.jsonl
- config_name: parts
  data_files:
  - split: train
    path: data/parts.jsonl
- config_name: fasteners
  data_files:
  - split: train
    path: data/fasteners.jsonl
- config_name: recovery
  data_files:
  - split: train
    path: data/recovery.jsonl
- config_name: launch
  data_files:
  - split: train
    path: data/launch.jsonl
- config_name: camera
  data_files:
  - split: train
    path: data/camera.jsonl
---

A structured dataset of rocket hardware parts with STEP geometry files, for use in AI/ML pipelines, RAG systems, and vector databases.

Generated by [RocketSmith](https://github.com/ppak10/RocketSmith).

---

## Configs

| Config | Rows | Description |
|--------|------|-------------|
| `default` / `parts` | {len(hf_records)} | All hardware parts |
| `fasteners` | {len(configs['fasteners'])} | Screws, nuts, washers, heat set inserts |
| `recovery` | {len(configs['recovery'])} | Eyebolts, quick links |
| `launch` | {len(configs['launch'])} | Rail buttons |
| `camera` | {len(configs['camera'])} | Camera mounts |

---

## Schema

Each record has three fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier — `parts:<category>/<subcategory>/<name>` |
| `document` | string | Rich text description for embedding/RAG retrieval |
| `metadata` | dict | Full structured metadata (dimensions, standard, source, sha256, etc.) |

### Metadata fields

| Field | Description |
|-------|-------------|
| `name` | Human-readable part name |
| `category` | Top-level category (`fastener`, `recovery`, `launch`, `camera`) |
| `subcategory` | Part type (e.g. `socket_head_cap_screw`, `eyebolt`) |
| `standard` | ISO/DIN standard (e.g. `ISO 4762`, `DIN 580`) |
| `generator` | Library used to generate geometry (e.g. `bd_warehouse==0.2.0`) |
| `source_url` | URL of geometry source library |
| `standard_url` | URL of the governing standard specification |
| `local_path` | Path to STEP file within `source/parts/files/step/` |
| `content_length` | STEP file size in bytes |
| `sha256` | SHA-256 hash of STEP file for integrity verification |
| `generated_at` | ISO 8601 UTC timestamp of generation |
| `description` | Full text description |
| `use_cases` | List of intended use cases within a rocket |
| `material` | Part material (steel, brass, delrin, stainless_steel) |

---

## Parts Breakdown

### By subcategory

| Subcategory | Count |
|-------------|-------|
""" + \
    "\n".join(f"| `{k}` | {v} |" for k, v in sorted(by_sub.items(), key=lambda x: -x[1])) + \
    f"""

### By geometry source

| Generator | Count |
|-----------|-------|
""" + \
    "\n".join(f"| `{k}` | {v} |" for k, v in by_gen.items()) + \
    f"""

### By standard

| Standard | Count |
|----------|-------|
""" + \
    "\n".join(f"| `{k}` | {v} |" for k, v in sorted(by_std.items(), key=lambda x: -x[1])) + \
    f"""

---

## Geometry Sources

| Source | Description |
|--------|-------------|
| [bd_warehouse](https://github.com/gumyr/bd_warehouse) | Parametric ISO/DIN standard fasteners — exact spec geometry |
| [build123d](https://github.com/gumyr/build123d) | Custom parametric geometry for rocket-specific hardware |

Standard fasteners (screws, nuts, washers, heat set inserts) are generated from `bd_warehouse`
against their governing ISO/DIN standard, making them spec-correct for any vendor.

Custom parts (DIN 580 eyebolts, 1010/1515 rail buttons, oval quick links, GoPro mount) are
modeled directly in `build123d` from published dimension tables.

---

## Source Layout

```
source/
  parts/
    metadata/
      parts_summary.json
    files/
      step/
        fasteners/
          socket_head_cap_screw/
          button_head_screw/
          pan_head_screw/
          countersunk_screw/
          set_screw/
          hex_nut/
          heat_set_insert/
          plain_washer/
        recovery/
          eyebolt/
          quick_link/
        launch/
        camera/
```

Total STEP file size: {total_mb:.1f} MB across {summary['total_parts']} files.
All STEP files tracked via git-lfs.

---

## Regenerating

```bash
git clone https://github.com/ppak10/RocketSmith
cd RocketSmith
uv run python dataset/generate_parts.py   # regenerate STEP files
uv run python dataset/build_hf_dataset.py  # rebuild HF structure
```
"""

    (HF_ROOT / "README.md").write_text(readme, encoding="utf-8")
    print("  + README.md")

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print(f"""
Done.
  HF dataset written to: {HF_ROOT}/
  Total records: {len(hf_records)}
  Total STEP size: {total_mb:.1f} MB

To push to Hugging Face:

  cd {HF_ROOT}
  git init
  huggingface-cli repo create rocketsmith/RocketParts --type dataset
  git remote add origin https://huggingface.co/datasets/rocketsmith/RocketParts
  git lfs install
  git add .
  git commit -m "Initial dataset: {len(hf_records)} rocket hardware parts with STEP geometry"
  git push origin main
""")


if __name__ == "__main__":
    build()
