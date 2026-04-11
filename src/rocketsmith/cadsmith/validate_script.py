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
        "pathlib",
        "math",
        "typing",
    }
)

REQUIRED_EXPORTS = frozenset(
    {
        "export_step",
        "export_stl",
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


def validate_script(script_path: Path) -> list[str]:
    """Validate a build123d script before execution.

    Checks:
    1. The script contains calls to both ``export_step`` and ``export_stl``.
    2. All imports come from an allowed set (build123d, pathlib, math, typing).

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

    # ── Export checks ──────────────────────────────────────────────────
    call_names = _collect_call_names(tree)
    missing_exports = REQUIRED_EXPORTS - call_names
    for name in sorted(missing_exports):
        errors.append(
            f"Missing required call to `{name}()`. "
            "The script must export both STEP and STL files."
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
