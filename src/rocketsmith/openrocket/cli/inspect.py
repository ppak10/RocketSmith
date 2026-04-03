import typer

from rich import print as rprint
from rich.tree import Tree
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path
from wa.cli.options import WorkspaceOption
from wa.cli.utils import get_workspace


def register_openrocket_inspect(app: typer.Typer):
    @app.command(name="inspect")
    def openrocket_inspect(
        ork_filename: Annotated[
            str,
            typer.Argument(
                help="Filename of the .ork file in the workspace openrocket/ folder."
            ),
        ],
        workspace_option: WorkspaceOption = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Display the full component tree of an .ork file."""
        from rocketsmith.openrocket.components import inspect_ork

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        workspace = get_workspace(workspace_option)
        ork_path = workspace.path / "openrocket" / ork_filename

        if not ork_path.exists():
            rprint(f"⚠️  [yellow].ork file not found: {ork_path}[/yellow]")
            raise typer.Exit(1)

        try:
            result = inspect_ork(ork_path, jar)
            components = result["components"]
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to inspect .ork: {e}[/yellow]")
            raise typer.Exit(1)

        # ── ASCII side-profile ────────────────────────────────────────────
        from rocketsmith.openrocket.ascii import render_rocket_ascii

        console = Console()
        ascii_art = render_rocket_ascii(
            components,
            cg_x=result.get("cg_x"),
            cp_x=result.get("cp_x"),
            max_diameter=result.get("max_diameter_m"),
        )
        console.print(ascii_art, markup=False)
        console.print()

        # ── Component tree ────────────────────────────────────────────────
        root_label = f"[bold]{ork_filename}[/bold]"
        rich_tree = Tree(root_label)
        stack = [(rich_tree, -1)]  # (node, depth)

        for entry in components:
            depth = entry["depth"]
            type_name = entry["type"]
            name = entry["name"]

            # Format property summary
            props = {
                k: v for k, v in entry.items() if k not in ("depth", "type", "name")
            }
            prop_str = "  ".join(
                f"[dim]{k}=[/dim][cyan]{v}[/cyan]" for k, v in props.items()
            )
            label = (
                f"[bold cyan]{type_name}[/bold cyan] [white]{name}[/white]  {prop_str}"
            )

            while len(stack) > 1 and stack[-1][1] >= depth:
                stack.pop()

            node = stack[-1][0].add(label)
            stack.append((node, depth))

        console.print(rich_tree)

    return openrocket_inspect
