import typer

app = typer.Typer(
    name="openrocket",
    help="Openrocket binding exposed by the `orhelper` package.",
    add_completion=False,
    no_args_is_help=True,
)
