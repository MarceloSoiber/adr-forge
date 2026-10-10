"""Smoke tests for the installable setup skeleton."""

from typer.testing import CliRunner

from adr_forge import __version__
from adr_forge.cli.main import app


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_displays_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "architecture decision laboratory" in result.stdout.lower()
