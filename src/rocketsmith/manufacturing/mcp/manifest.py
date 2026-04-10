from mcp.server.fastmcp import FastMCP


def register_manufacturing_manifest(app: FastMCP):
    import json
    from pathlib import Path
    from typing import Any, Literal, Union

    from rocketsmith.mcp.types import ToolError, ToolSuccess
    from rocketsmith.mcp.utils import resolve_path, tool_error, tool_success

    @app.tool(
        title="Parts Manifest",
        description=(
            "Generate or read a parts manifest for a rocket project. The manifest "
            "is the authoritative handoff from a design-for-X skill to the cadsmith "
            "CAD pipeline and the mass-calibration workflow. Use action='generate' to "
            "produce a new parts_manifest.json from an OpenRocket design file (applies "
            "design-for-additive-manufacturing fusion rules by default). Use "
            "action='read' to load an existing manifest."
        ),
        structured_output=True,
    )
    async def manufacturing_manifest(
        action: Literal["generate", "read"],
        project_root: Path,
        rocket_file_path: Path | None = None,
        method: Literal["additive"] = "additive",
        fusion_overrides: dict[str, str] | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict[str, Any]], ToolError]:
        """
        Generate or read the parts manifest for a rocket project.

        Actions:
            generate: Read the .ork file, apply the chosen manufacturing
                      method's fusion rules, validate against the manifest
                      schema, and write ``<project_root>/parts_manifest.json``.
                      Requires ``rocket_file_path``. Currently only
                      ``method="additive"`` is implemented.
            read:     Load and return the existing manifest at
                      ``<project_root>/parts_manifest.json``. Use before
                      running mass-calibration so you have the authoritative
                      ``component_to_part_map`` for attributing filament
                      weights.

        Args:
            action: One of ``"generate"`` or ``"read"``.
            project_root: Absolute path to the project directory. The
                manifest is written to (or read from) ``parts_manifest.json``
                at this location.
            rocket_file_path: Absolute path to the .ork file. Required for
                ``generate``; ignored for ``read``.
            method: Manufacturing method. Only ``"additive"`` is supported
                today; ``"hybrid"`` and ``"traditional"`` will be added as
                sibling skills land.
            fusion_overrides: Per-decision overrides the agent applies when
                the user has answered an ask-user question. Keys:

                - ``motor_mount_fate``: ``"fuse"`` (default) or ``"separate"``
                - ``coupler_fate``: ``"fuse"`` (default) or ``"separate"``
                - ``retention``: ``"m4_heat_set"`` or ``"friction_fit"``
                  (default is derived from body diameter)

                Omit keys to accept the default.
            openrocket_path: Optional path to the OpenRocket JAR file. If
                not provided, the installed JAR is located automatically.

        Returns:
            The manifest as a dict matching the ``PartsManifest`` schema
            defined in ``rocketsmith.manufacturing.models``.
        """
        project_root = resolve_path(project_root)
        manifest_path = project_root / "parts_manifest.json"

        if action == "read":
            if not manifest_path.exists():
                return tool_error(
                    f"Manifest not found: {manifest_path}",
                    "FILE_NOT_FOUND",
                    manifest_path=str(manifest_path),
                )
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return tool_success(json.load(f))
            except json.JSONDecodeError as e:
                return tool_error(
                    f"Manifest is not valid JSON: {e}",
                    "INVALID_MANIFEST",
                    manifest_path=str(manifest_path),
                    exception_message=str(e),
                )

        # action == "generate"
        if rocket_file_path is None:
            return tool_error(
                "'rocket_file_path' is required for action 'generate'.",
                "MISSING_ARGUMENT",
            )
        rocket_file_path = resolve_path(rocket_file_path)
        if not rocket_file_path.exists():
            return tool_error(
                f"Rocket design file not found: {rocket_file_path}",
                "FILE_NOT_FOUND",
                rocket_file_path=str(rocket_file_path),
            )

        if not project_root.exists():
            project_root.mkdir(parents=True, exist_ok=True)
        if not project_root.is_dir():
            return tool_error(
                f"project_root is not a directory: {project_root}",
                "INVALID_ARGUMENT",
                project_root=str(project_root),
            )

        try:
            if openrocket_path is None:
                from rocketsmith.openrocket.utils import get_openrocket_path

                openrocket_path = get_openrocket_path()

            if method != "additive":
                return tool_error(
                    f"Manufacturing method '{method}' is not yet supported. "
                    "Only 'additive' is implemented today.",
                    "NOT_IMPLEMENTED",
                    method=method,
                )

            from rocketsmith.manufacturing.dfam import generate_dfam_manifest

            manifest = generate_dfam_manifest(
                rocket_file_path=rocket_file_path,
                project_root=project_root,
                fusion_overrides=fusion_overrides,
                jar_path=openrocket_path,
            )

            # Pydantic already validated on construction — serialise and write
            manifest_data = manifest.model_dump(mode="json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)

            return tool_success(manifest_data)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        except Exception as e:
            return tool_error(
                f"Failed to {action} manifest",
                "MANIFEST_FAILED",
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = manufacturing_manifest
