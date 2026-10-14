"""ADR Forge command-line entry point."""

import typer

from adr_forge.cli.benchmark_report import benchmark_report
from adr_forge.cli.benchmark_run import benchmark_run
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
benchmark = typer.Typer(help="Execute and report reproducible benchmarks.")
benchmark.command("run")(benchmark_run)
benchmark.command("report")(benchmark_report)
app.add_typer(benchmark, name="benchmark")


if __name__ == "__main__":
    app()
