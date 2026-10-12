"""ADR Forge command-line entry point."""

import typer

from adr_forge.cli.doctor import doctor

app = typer.Typer(
    name="adr-forge",
    help="Local-first architecture decision laboratory.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Run ADR Forge commands."""


app.command()(doctor)


if __name__ == "__main__":
    app()
