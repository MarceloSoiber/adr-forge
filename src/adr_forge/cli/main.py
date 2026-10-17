"""ADR Forge command-line entry point."""

import typer

from adr_forge.cli.artifacts import artifacts_list, artifacts_prune
from adr_forge.cli.benchmark_report import benchmark_report
from adr_forge.cli.benchmark_run import benchmark_run
from adr_forge.cli.database import database_backup
from adr_forge.cli.dataset import dataset_build, dataset_validate
from adr_forge.cli.doctor import doctor
from adr_forge.cli.train import train_sft

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

dataset = typer.Typer(help="Validate and build governed training datasets.")
dataset.command("validate")(dataset_validate)
dataset.command("build")(dataset_build)
app.add_typer(dataset, name="dataset")

train = typer.Typer(help="Run guarded local model training.")
train.command("sft")(train_sft)
app.add_typer(train, name="train")

database = typer.Typer(help="Create verified local SQLite backups.")
database.command("backup")(database_backup)
app.add_typer(database, name="database")

artifacts = typer.Typer(help="Inspect and safely prune local artifacts.")
artifacts.command("list")(artifacts_list)
artifacts.command("prune")(artifacts_prune)
app.add_typer(artifacts, name="artifacts")


if __name__ == "__main__":
    app()
