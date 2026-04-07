"""Tests for SimulateDecision Core."""
from simulate_decision.core.config import EngineConfig, get_config
from simulate_decision.core.state import AttemptRecord, StrategyState


def test_strategy_state_initialization():
    state = StrategyState()
    assert state.iteration == 0
    assert state.converged is False
    assert len(state.history) == 0
    assert state.total_tokens_used == 0


def test_strategy_state_record_attempt():
    state = StrategyState()
    state.record_attempt(
        iteration=1,
        strategy="test strategy",
        atoms_count=10,
        axioms_count=5,
        error_signal=None,
        stage="test",
        reasoning="test reasoning",
        tokens_used=100,
        model_name="test-model",
    )
    assert state.iteration == 1
    assert len(state.history) == 1
    assert state.history[0].atoms_count == 10
    assert state.history[0].tokens_used == 100
    assert state.total_tokens_used == 100


def test_strategy_state_update_strategy():
    state = StrategyState()
    new_strategy = "Focus on mathematical foundations"
    state.update_strategy(new_strategy)
    assert state.current_strategy == new_strategy


def test_strategy_state_mark_converged():
    state = StrategyState()
    state.mark_converged()
    assert state.converged is True


def test_strategy_state_reset():
    state = StrategyState()
    state.record_attempt(1, "test", 10, 5, stage="test")
    state.mark_converged()
    state.reset()
    assert state.iteration == 0
    assert state.converged is False
    assert len(state.history) == 0
    assert state.total_tokens_used == 0


def test_engine_config_defaults():
    config = EngineConfig()
    assert config.lm_studio_url == "http://localhost:1234/v1"
    assert config.max_iterations == 3
    assert config.signal_loss_threshold == 3


def test_engine_config_custom_values():
    config = EngineConfig(
        lm_studio_url="http://custom:9999/v1",
        max_iterations=5,
    )
    assert config.lm_studio_url == "http://custom:9999/v1"
    assert config.max_iterations == 5


def test_get_config_returns_engine_config():
    config = get_config()
    assert isinstance(config, EngineConfig)


def test_attempt_record_fields():
    record = AttemptRecord(
        iteration=1,
        strategy="test",
        atoms_count=10,
        axioms_count=5,
        stage="deconstruct",
        reasoning="some reasoning",
        tokens_used=150,
        model_name="gemma-4b",
        raw_atoms="atom1 atom2",
        noise_detected="metaphor1",
        verified_atoms="atom1",
        rejection_reason="too vague",
    )
    assert record.iteration == 1
    assert record.raw_atoms == "atom1 atom2"
    assert record.noise_detected == "metaphor1"
