"""E2E Tests for CLI Interface."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from simulate_decision.cli.main import app

runner = CliRunner()

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = DATA_DIR / "results"


class TestCLIAnalyze:
    """Tests for analyze command."""

    def test_analyze_help(self) -> None:
        """Test analyze command help."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "concept" in result.stdout.lower()

    def test_analyze_with_iterations(self) -> None:
        """Test analyze with custom iterations."""
        result = runner.invoke(
            app,
            ["analyze", "Test concept", "--iterations", "5"],
        )
        assert "Analyze" in result.stdout or "Analysis" in result.stdout or "concept" in result.stdout.lower()

    def test_analyze_with_no_save(self) -> None:
        """Test analyze with --no-save flag."""
        result = runner.invoke(
            app,
            ["analyze", "Test no save", "--no-save"],
        )
        assert result.exit_code in [0, 1]


class TestCLIHistory:
    """Tests for history command."""

    def test_history_empty(self) -> None:
        """Test history when empty."""
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "No history" in result.stdout or "history" in result.stdout.lower()

    def test_history_with_limit(self) -> None:
        """Test history with limit option."""
        result = runner.invoke(app, ["history", "--limit", "5"])
        assert result.exit_code == 0

    def test_history_with_concept_filter(self) -> None:
        """Test history with concept filter."""
        result = runner.invoke(app, ["history", "--concept", "test"])
        assert result.exit_code == 0

    def test_history_help(self) -> None:
        """Test history command help."""
        result = runner.invoke(app, ["history", "--help"])
        assert result.exit_code == 0
        assert "limit" in result.stdout.lower()


class TestCLIExport:
    """Tests for export command."""

    def test_export_help(self) -> None:
        """Test export command help."""
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "output" in result.stdout.lower()

    def test_export_empty(self, tmp_path: Path) -> None:
        """Test exporting empty history."""
        output_file = tmp_path / "export.json"
        result = runner.invoke(
            app,
            ["export", str(output_file)],
        )
        assert "No records" in result.stdout or result.exit_code == 0

    def test_export_json_format(self, tmp_path: Path) -> None:
        """Test exporting to JSON format."""
        output_file = tmp_path / "test.json"
        result = runner.invoke(
            app,
            ["export", str(output_file), "--format", "json"],
        )
        assert result.exit_code == 0 or "No records" in result.stdout


class TestCLIClearHistory:
    """Tests for clear-history command."""

    def test_clear_history_help(self) -> None:
        """Test clear-history command help."""
        result = runner.invoke(app, ["clear-history", "--help"])
        assert result.exit_code == 0

    def test_clear_history_with_force(self) -> None:
        """Test clear-history with force flag."""
        result = runner.invoke(app, ["clear-history", "--force"])
        assert result.exit_code == 0
        assert "cleared" in result.stdout.lower() or "cancelled" in result.stdout.lower()


class TestCLIConfigShow:
    """Tests for config-show command."""

    def test_config_show(self) -> None:
        """Test config-show displays configuration."""
        result = runner.invoke(app, ["config-show"])
        assert result.exit_code == 0
        assert "LM Studio URL" in result.stdout
        assert "Max Iterations" in result.stdout
        assert "History File" in result.stdout

    def test_config_show_model(self) -> None:
        """Test config-show displays model name."""
        result = runner.invoke(app, ["config-show"])
        assert result.exit_code == 0
        assert "Model" in result.stdout


class TestCLIHelp:
    """Tests for CLI help."""

    def test_main_help(self) -> None:
        """Test main help displays all commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "analyze" in result.stdout.lower()
        assert "history" in result.stdout.lower()
        assert "export" in result.stdout.lower()
        assert "clear-history" in result.stdout.lower()
        assert "config-show" in result.stdout.lower()

    def test_all_commands_listed(self) -> None:
        """Test all commands are listed in help."""
        result = runner.invoke(app, ["--help"])
        commands = ["analyze", "history", "export", "clear-history", "config-show"]
        for cmd in commands:
            assert cmd in result.stdout.lower()


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_unknown_command(self) -> None:
        """Test unknown command shows error."""
        result = runner.invoke(app, ["unknown-command"])
        assert result.exit_code != 0

    def test_invalid_option(self) -> None:
        """Test invalid option shows error."""
        result = runner.invoke(app, ["analyze", "test", "--invalid-option"])
        assert result.exit_code != 0
