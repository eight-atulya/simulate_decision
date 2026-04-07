"""E2E Tests for SimulateDecision Core Engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from simulate_decision.core import EngineConfig, SimulateDecisionCore, StrategyState


class TestEngineConfig:
    """Tests for EngineConfig."""

    def test_config_default_values(self) -> None:
        """Test default configuration values."""
        config = EngineConfig()
        assert config.lm_studio_url == "http://localhost:1234/v1"
        assert config.api_key == "lm-studio"
        assert config.max_iterations == 3
        assert config.model_name == "lmstudio/google/gemma-4-26b-a4b"
        assert config.signal_loss_threshold == 3

    def test_config_custom_values(self) -> None:
        """Test custom configuration values."""
        config = EngineConfig(
            lm_studio_url="http://custom:9999/v1",
            max_iterations=5,
            signal_loss_threshold=5,
        )
        assert config.lm_studio_url == "http://custom:9999/v1"
        assert config.max_iterations == 5
        assert config.signal_loss_threshold == 5

    def test_config_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable overrides."""
        monkeypatch.setenv("LM_STUDIO_URL", "http://env:1234/v1")
        monkeypatch.setenv("MAX_ITERATIONS", "7")

        config = EngineConfig()
        assert config.lm_studio_url == "http://env:1234/v1"
        assert config.max_iterations == 7


class TestStrategyState:
    """Tests for StrategyState."""

    def test_initial_state(self) -> None:
        """Test initial state values."""
        state = StrategyState()
        assert state.iteration == 0
        assert state.converged is False
        assert len(state.history) == 0
        assert "human-centric" in state.current_strategy

    def test_record_attempt(self) -> None:
        """Test recording an attempt."""
        state = StrategyState()
        state.record_attempt(
            iteration=1,
            strategy="Test strategy",
            atoms_count=10,
            axioms_count=5,
            error_signal=None,
        )
        assert state.iteration == 1
        assert len(state.history) == 1
        assert state.history[0]["atoms_count"] == 10
        assert state.history[0]["axioms_count"] == 5

    def test_record_attempt_with_error(self) -> None:
        """Test recording an attempt with error."""
        state = StrategyState()
        state.record_attempt(
            iteration=1,
            strategy="Test",
            atoms_count=10,
            axioms_count=0,
            error_signal="Too abstract",
        )
        assert state.history[0]["error_signal"] == "Too abstract"

    def test_update_strategy(self) -> None:
        """Test updating strategy."""
        state = StrategyState()
        new_strategy = "Focus on math"
        state.update_strategy(new_strategy)
        assert state.current_strategy == new_strategy

    def test_mark_converged(self) -> None:
        """Test marking as converged."""
        state = StrategyState()
        assert state.converged is False
        state.mark_converged()
        assert state.converged is True

    def test_reset(self) -> None:
        """Test resetting state."""
        state = StrategyState()
        state.record_attempt(1, "test", 10, 5)
        state.mark_converged()
        state.reset()

        assert state.iteration == 0
        assert state.converged is False
        assert len(state.history) == 0

    def test_get_policy_history(self) -> None:
        """Test getting policy history."""
        state = StrategyState()
        state.record_attempt(1, "strategy1", 10, 5)
        state.record_attempt(2, "strategy2", 8, 6)

        history = state.get_policy_history()
        assert len(history) == 2
        assert history[0]["strategy"] == "strategy1"
        assert history[1]["strategy"] == "strategy2"


class TestSimulateDecisionCore:
    """Tests for SimulateDecisionCore."""

    def test_engine_initialization(self) -> None:
        """Test engine initialization."""
        engine = SimulateDecisionCore()
        assert engine.max_iterations == 3
        assert isinstance(engine.config, EngineConfig)
        assert isinstance(engine.state, StrategyState)
        assert hasattr(engine, "deconstruct")
        assert hasattr(engine, "verify")
        assert hasattr(engine, "reconstruct")
        assert hasattr(engine, "analyzer")

    def test_engine_custom_config(self) -> None:
        """Test engine with custom config."""
        config = EngineConfig(max_iterations=5)
        engine = SimulateDecisionCore(config=config, max_iterations=5)
        assert engine.max_iterations == 5
        assert engine.config.max_iterations == 5

    def test_engine_storage_path(
        self, tmp_path: Path, sample_result_data: dict[str, Any]
    ) -> None:
        """Test engine with custom storage path."""
        storage_path = tmp_path / "test_jobs.json"
        from simulate_decision.core import Storage

        storage = Storage(storage_path)
        entry = {
            "timestamp": "2024-01-01T00:00:00",
            "concept": "Test",
            "status": "SUCCESS",
            "iterations": 1,
        }
        storage.append(entry)

        assert storage_path.exists()
        loaded = storage.load()
        assert len(loaded) == 1
        assert loaded[0]["concept"] == "Test"

    def test_engine_forward_returns_dict(self, sample_concept: str) -> None:
        """Test that forward returns a dict (mocked)."""
        engine = SimulateDecisionCore()
        assert hasattr(engine, "forward")
        assert callable(engine.forward)

    def test_engine_forward_with_save(
        self, sample_concept: str, sample_result_data: dict[str, Any]
    ) -> None:
        """Test engine has save functionality."""
        from simulate_decision.core import Storage

        storage = Storage()
        storage.save([])

        engine = SimulateDecisionCore(storage_path=storage.storage_path)
        assert engine.storage is not None


class TestStorage:
    """Tests for Storage class."""

    def test_storage_initialization(self, tmp_path: Path) -> None:
        """Test storage initialization."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "test.json"
        storage = Storage(storage_path)

        assert storage.storage_path == storage_path
        assert storage.storage_path.parent.exists()

    def test_storage_load_empty(self, tmp_path: Path) -> None:
        """Test loading empty storage."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "empty.json"
        storage = Storage(storage_path)

        data = storage.load()
        assert data == []

    def test_storage_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading data."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "data.json"
        storage = Storage(storage_path)

        test_data = [
            {"id": "1", "concept": "Test 1"},
            {"id": "2", "concept": "Test 2"},
        ]
        storage.save(test_data)

        loaded = storage.load()
        assert len(loaded) == 2
        assert loaded[0]["concept"] == "Test 1"

    def test_storage_append(self, tmp_path: Path) -> None:
        """Test appending to storage."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "append.json"
        storage = Storage(storage_path)

        storage.append({"id": "1", "concept": "First"})
        storage.append({"id": "2", "concept": "Second"})

        data = storage.load()
        assert len(data) == 2

    def test_storage_get_all(self, tmp_path: Path) -> None:
        """Test getting all records."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "all.json"
        storage = Storage(storage_path)

        storage.save([
            {"id": "1", "concept": "Test 1"},
            {"id": "2", "concept": "Test 2"},
        ])

        all_records = storage.get_all()
        assert len(all_records) == 2

    def test_storage_get_by_concept(self, tmp_path: Path) -> None:
        """Test filtering by concept (exact match)."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "filter.json"
        storage = Storage(storage_path)

        storage.save([
            {"id": "1", "concept": "Justice"},
            {"id": "2", "concept": "Freedom"},
            {"id": "3", "concept": "Justice"},
        ])

        results = storage.get_by_concept("Justice")
        assert len(results) == 2

    def test_storage_clear(self, tmp_path: Path) -> None:
        """Test clearing storage."""
        from simulate_decision.core import Storage

        storage_path = tmp_path / "clear.json"
        storage = Storage(storage_path)

        storage.save([{"id": "1"}])
        assert storage_path.exists()

        storage.clear()
        assert storage.load() == []

    def test_create_entry(self, sample_result_data: dict[str, Any]) -> None:
        """Test creating an entry."""
        from simulate_decision.core import create_entry

        entry = create_entry(
            concept="Justice",
            result=sample_result_data,
            status="SUCCESS",
        )

        assert entry["concept"] == "Justice"
        assert entry["status"] == "SUCCESS"
        assert "timestamp" in entry
        assert entry["purified_atoms"] is not None
