"""ADR Forge command-line entry point."""

import typer

app = typer.Typer(
    name="adr-forge",
    help="Local-first architecture decision laboratory.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Run ADR Forge commands."""


if __name__ == "__main__":
    app()
