import typer

app = typer.Typer(
    name="prusaslicer",
    help="PrusaSlicer CLI tools.",
    add_completion=False,
    no_args_is_help=True,
)
