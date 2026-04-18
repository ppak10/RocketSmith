"""Pre-execution validation for build123d scripts.

Parses the script's AST to catch common authoring mistakes before
spending time on a subprocess invocation.
"""

from __future__ import annotations

import ast
from pathlib import Path

ALLOWED_IMPORTS = frozenset(
    {
        "build123d",
        "bd_warehouse",
        "pathlib",
        "math",
        "typing",
    }
)

REQUIRED_EXPORTS = frozenset(
    {
        "export_step",
    }
)


def _collect_call_names(tree: ast.Module) -> set[str]:
    """Return the set of function names invoked anywhere in the AST."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _collect_imported_modules(tree: ast.Module) -> set[str]:
    """Return the set of top-level module names imported in the AST."""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


def _collect_cadsmith_paths(manifest_path: Path) -> set[str]:
    """Return the set of expected script stems from component_tree.json.

    Walks stages[].components[] recursively and collects the stem (filename
    without extension) of every non-null cadsmith_path.  Returns an empty
    set if the manifest cannot be read or has no annotated parts yet.
    """
    import json

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    stems: set[str] = set()

    def _walk(components: list) -> None:
        for comp in components:
            cp = comp.get("cadsmith_path")
            if cp:
                stems.add(Path(cp).stem)
            _walk(comp.get("children", []))

    for stage in data.get("stages", []):
        _walk(stage.get("components", []))

    return stems


def validate_script(script_path: Path, manifest_path: Path | None = None) -> list[str]:
    """Validate a build123d script before execution.

    Checks:
    1. The script filename matches a cadsmith_path in component_tree.json
       (only enforced when the manifest exists and has annotated parts).
    2. The script contains a call to ``export_step``.
    3. All imports come from an allowed set (build123d, pathlib, math, typing).

    Returns:
        A list of human-readable error strings. An empty list means the
        script passed all checks.
    """
    source = script_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source, filename=str(script_path))
    except SyntaxError as e:
        return [f"Syntax error at line {e.lineno}: {e.msg}"]

    errors: list[str] = []

    # ── Manifest part-name check ───────────────────────────────────────
    if manifest_path is not None and manifest_path.exists():
        valid_stems = _collect_cadsmith_paths(manifest_path)
        if valid_stems and script_path.stem not in valid_stems:
            errors.append(
                f"Script '{script_path.name}' does not match any part in "
                f"component_tree.json. Valid names: "
                f"{', '.join(sorted(s + '.py' for s in valid_stems))}. "
                "Edit the existing part script instead of creating a new one, "
                "or add the part to the manifest first via manufacturing_annotate_tree."
            )

    # ── Export checks ──────────────────────────────────────────────────
    call_names = _collect_call_names(tree)
    missing_exports = REQUIRED_EXPORTS - call_names
    for name in sorted(missing_exports):
        errors.append(
            f"Missing required call to `{name}()`. "
            "The script must export a STEP file."
        )

    # ── Import allowlist ───────────────────────────────────────────────
    imported = _collect_imported_modules(tree)
    disallowed = imported - ALLOWED_IMPORTS
    for name in sorted(disallowed):
        errors.append(
            f"Disallowed import `{name}`. "
            f"Only {', '.join(sorted(ALLOWED_IMPORTS))} are permitted "
            "in the isolated execution environment."
        )

    return errors
