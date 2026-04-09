import typer

app = typer.Typer(help="Dependency setup commands.")


@app.command(name="check")
def setup_check() -> None:
    """Check that required dependencies (Java, OpenRocket, PrusaSlicer) are installed.

    Output is plain text suitable for injection into agent context via a SessionStart hook.
    """
    from rocketsmith.mcp.setup import _check

    status = _check()

    lines = [
        "# rocketsmith dependency status",
        f"java: {status.java}",
        f"openrocket: {status.openrocket}",
        f"prusaslicer: {status.prusaslicer}",
    ]

    if status.ready:
        lines.append("status: ready — all tools available")
    else:
        missing = [
            dep
            for dep, val in [
                ("java", status.java),
                ("openrocket", status.openrocket),
                ("prusaslicer", status.prusaslicer),
            ]
            if "not found" in val
        ]
        lines.append(
            f"status: NOT READY — missing: {', '.join(missing)}. "
            "Call rocketsmith_setup(action='install') to install."
        )

    print("\n".join(lines))
