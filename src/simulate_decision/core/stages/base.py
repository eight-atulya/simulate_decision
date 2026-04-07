from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import dspy

from simulate_decision.signatures.registry import (
    FailureAction,
    SignatureType,
    get_signature_registry,
)


class StageStatus(Enum):
    """Status of a stage execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class StageResult:
    """Result of executing a stage."""
    status: StageStatus
    output: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    tokens_used: int = 0
    error: str | None = None
    attempts: int = 1
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        return self.status == StageStatus.SUCCESS

    @property
    def is_retryable(self) -> bool:
        return self.status == StageStatus.FAILED and self.attempts < 3


@dataclass
class PipelineContext:
    """Shared context passed between stages."""
    concept: str
    current_strategy: str = ""
    iteration: int = 1
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_output(self, stage_name: str) -> dict[str, Any] | None:
        """Get output from a previous stage."""
        result = self.stage_results.get(stage_name)
        return result.output if result else None

    def get_all_outputs(self) -> dict[str, dict[str, Any]]:
        """Get all stage outputs."""
        return {name: r.output for name, r in self.stage_results.items() if r.is_success}


@dataclass
class StageConfig:
    """Configuration for a single stage in the pipeline."""
    name: str
    signature_name: str
    signature_type: SignatureType = SignatureType.CHAIN_OF_THOUGHT
    enabled: bool = True
    retries: int = 1
    timeout_seconds: int | None = None
    on_failure: FailureAction = FailureAction.RETRY
    custom_instructions: str | None = None
    required: bool = True
    input_mapping: dict[str, str] = field(default_factory=dict)
    condition: str | None = None

    def __post_init__(self) -> None:
        if self.signature_name == "analyze":
            self.on_failure = FailureAction.STOP


class Stage(ABC):
    """Abstract base class for pipeline stages."""

    config: StageConfig

    def __init__(self, config: StageConfig):
        self.config = config
        self._predictor: dspy.Predict | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Stage name identifier."""
        ...

    @property
    def input_fields(self) -> list[str]:
        """List of input field names expected by this stage."""
        return []

    @property
    def output_fields(self) -> list[str]:
        """List of output field names produced by this stage."""
        return []

    def _create_predictor(self) -> dspy.Predict:
        """Create the DSPy predictor for this stage."""
        registry = get_signature_registry()
        predictor = registry.get_predictor(
            self.config.signature_name,
            self.config.signature_type
        )
        if not predictor:
            raise ValueError(f"Unknown signature: {self.config.signature_name}")
        return predictor

    def get_predictor(self) -> dspy.Predict:
        """Get or create the predictor."""
        if self._predictor is None:
            self._predictor = self._create_predictor()
        return self._predictor

    def prepare_inputs(self, context: PipelineContext) -> dict[str, Any]:
        """Prepare inputs for the predictor from context."""
        return {"input_concept": context.concept}

    @abstractmethod
    def execute(self, context: PipelineContext) -> StageResult:
        """Execute the stage with the given context."""
        ...

    def should_retry(self, result: StageResult) -> bool:
        """Determine if stage should be retried."""
        if result.status == StageStatus.FAILED and result.attempts < self.config.retries:
            return True
        return False

    def get_retry_input(self, context: PipelineContext, result: StageResult) -> dict[str, Any]:
        """Prepare inputs for retry (can be overridden)."""
        return self.prepare_inputs(context)

    def on_success(self, context: PipelineContext, result: StageResult) -> None:
        """Hook called after successful execution."""
        pass

    def on_failure(self, context: PipelineContext, result: StageResult) -> FailureAction:
        """Determine what to do on failure."""
        return self.config.on_failure


class StageRegistry:
    """Registry for available stage classes."""

    _stages: dict[str, type[Stage]] = {}
    _instances: dict[str, Stage] = {}

    @classmethod
    def register(cls, name: str, stage_class: type[Stage]) -> None:
        """Register a stage class."""
        cls._stages[name] = stage_class

    @classmethod
    def create(cls, config: StageConfig) -> Stage:
        """Create a stage instance from config."""
        if config.name in cls._instances:
            return cls._instances[config.name]

        stage_class = cls._stages.get(config.signature_name)
        if not stage_class:
            raise ValueError(f"Unknown stage: {config.signature_name}")

        instance = stage_class(config)
        cls._instances[config.name] = instance
        return instance

    @classmethod
    def get(cls, name: str) -> Stage | None:
        """Get a registered stage instance."""
        return cls._instances.get(name)

    @classmethod
    def list_stages(cls) -> list[str]:
        """List all registered stage names."""
        return list(cls._stages.keys())

    @classmethod
    def reset(cls) -> None:
        """Reset all stage instances."""
        cls._instances.clear()


def register_stage(name: str) -> callable:
    """Decorator to register a stage class."""
    def decorator(cls: type[Stage]) -> type[Stage]:
        StageRegistry.register(name, cls)
        return cls
    return decorator
