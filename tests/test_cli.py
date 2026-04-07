"""Tests for SimulateDecision CLI."""
from typer.testing import CliRunner

from simulate_decision.cli.main import app

runner = CliRunner()


def test_config_show():
    result = runner.invoke(app, ["config-show"])
    assert result.exit_code == 0
    assert "LM Studio URL" in result.stdout
    assert "Max Iterations" in result.stdout


def test_analyze_help():
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "concept" in result.stdout.lower()


def test_history_command():
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
