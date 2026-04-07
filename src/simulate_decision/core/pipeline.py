from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import dspy

from simulate_decision.core.config import EngineConfig, get_config
from simulate_decision.core.stages.builtin import (
    AnalyzeStage,
    DeconstructStage,
    PipelineContext,
    ReconstructStage,
    Stage,
    StageConfig,
    StageResult,
    StageStatus,
    VerifyStage,
)
from simulate_decision.core.state import StrategyState
from simulate_decision.core.storage import Storage, create_entry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IterationMode(Enum):
    """How to handle iterations."""
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    CONDITIONAL = "conditional"


class PipelineStatus(Enum):
    """Status of pipeline execution."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class PipelineConfig:
    """Configuration for a complete pipeline."""
    name: str = "default"
    stages: list[StageConfig] = field(default_factory=list)
    iteration_mode: IterationMode = IterationMode.FIXED
    max_iterations: int = 3
    signal_loss_threshold: int = 3
    quality_threshold: float | None = None
    stop_on_first_success: bool = True

    def __post_init__(self) -> None:
        if not self.stages:
            self.stages = self._default_stages()

    def _default_stages(self) -> list[StageConfig]:
        return [
            StageConfig(name="deconstruct", signature_name="deconstruct", retries=2),
            StageConfig(name="verify", signature_name="verify", retries=2),
            StageConfig(name="reconstruct", signature_name="reconstruct", retries=1),
        ]


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    status: PipelineStatus
    concept: str
    iterations: int
    stage_results: dict[str, StageResult]
    final_output: dict[str, Any]
    metadata: dict[str, Any]
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


STAGE_CLASSES = {
    "deconstruct": DeconstructStage,
    "verify": VerifyStage,
    "reconstruct": ReconstructStage,
    "analyze": AnalyzeStage,
    "expand": "ExpandStage",
    "abstract": "AbstractStage",
    "critique": "CritiqueStage",
    "compare": "CompareStage",
}


class Pipeline:
    """Runs a configurable pipeline of stages."""

    def __init__(
        self,
        config: PipelineConfig,
        engine_config: EngineConfig | None = None,
    ):
        self.config = config
        self.engine_config = engine_config or get_config()
        self._stages: dict[str, Stage] = {}
        self._context: PipelineContext | None = None
        self._progress_callback = None

    def set_progress_callback(self, callback) -> None:
        self._progress_callback = callback

    def _ensure_stage(self, stage_config: StageConfig) -> Stage:
        if stage_config.name not in self._stages:
            stage_class = STAGE_CLASSES.get(stage_config.signature_name)
            if isinstance(stage_class, str):
                from simulate_decision.core.stages.builtin import (
                    AbstractStage,
                    CompareStage,
                    CritiqueStage,
                    ExpandStage,
                )
                stage_class_map = {
                    "ExpandStage": ExpandStage,
                    "AbstractStage": AbstractStage,
                    "CritiqueStage": CritiqueStage,
                    "CompareStage": CompareStage,
                }
                stage_class = stage_class_map.get(stage_class, DeconstructStage)

            if stage_class:
                self._stages[stage_config.name] = stage_class(stage_config)
            else:
                raise ValueError(f"Unknown stage: {stage_config.signature_name}")
        return self._stages[stage_config.name]

    def execute(
        self,
        concept: str,
        initial_strategy: str = "Identify the core structural elements and strip all human-centric metaphors.",
    ) -> PipelineResult:
        logger.info(f"Starting pipeline '{self.config.name}' for concept: {concept}")

        self._context = PipelineContext(
            concept=concept,
            current_strategy=initial_strategy,
        )

        all_stage_results: dict[str, list[StageResult]] = {}
        total_tokens = 0
        converged = False
        final_output: dict[str, Any] = {}

        for iteration in range(1, self.config.max_iterations + 1):
            self._context.iteration = iteration
            logger.info(f"=== Iteration {iteration}/{self.config.max_iterations} ===")

            iteration_success = True
            completed_stages = 0

            for stage_config in self.config.stages:
                if not stage_config.enabled:
                    continue

                if stage_config.name == "analyze":
                    verify_result = self._context.stage_results.get("verify")
                    if not verify_result or verify_result.is_success:
                        continue

                stage = self._ensure_stage(stage_config)

                if stage_config.name not in all_stage_results:
                    all_stage_results[stage_config.name] = []

                logger.info(f"  [Stage: {stage_config.name}] (stage {completed_stages + 1}/{len(self.config.stages)})")

                if self._progress_callback:
                    self._progress_callback(stage_config.name, "started")

                stage_result = self._execute_stage(stage, stage_config)

                all_stage_results[stage_config.name].append(stage_result)
                self._context.stage_results[stage_config.name] = stage_result

                total_tokens += stage_result.tokens_used

                if stage_result.is_success:
                    completed_stages += 1
                    self._update_context_from_result(stage_result)

                if not stage_result.is_success:
                    if stage_config.on_failure == "stop":
                        logger.warning(f"  Stage {stage_config.name} failed, stopping pipeline")
                        iteration_success = False
                        break

            if iteration_success and self._check_success_criteria():
                converged = True
                logger.info(f"Pipeline converged at iteration {iteration}")
                final_output = self._collect_final_output()
                break

            if completed_stages == len(self.config.stages):
                logger.info(f"Completed all {completed_stages} stages in iteration {iteration}")

        if not final_output:
            final_output = self._collect_final_output()

        status = self._determine_status(converged, all_stage_results)

        return PipelineResult(
            status=status,
            concept=concept,
            iterations=self._context.iteration,
            stage_results={k: v[-1] for k, v in all_stage_results.items()},
            final_output=final_output,
            metadata={
                "total_iterations": self._context.iteration,
                "total_tokens_used": total_tokens,
                "converged": converged,
                "iteration_mode": self.config.iteration_mode.value,
                "all_stage_results": {
                    k: [{"status": r.status, "attempts": r.attempts} for r in v]
                    for k, v in all_stage_results.items()
                },
            },
        )

    def _execute_stage(self, stage: Stage, config: StageConfig) -> StageResult:
        if self._context is None:
            return StageResult(status=StageStatus.FAILED, error="No context")

        import time
        start_time = time.time()

        for attempt in range(1, config.retries + 1):
            logger.info(f"    Attempt {attempt}/{config.retries}")
            result = stage.execute(self._context)
            result.attempts = attempt
            elapsed = time.time() - start_time

            if result.is_success:
                logger.info(f"    Stage completed in {elapsed:.1f}s")
                output_keys = list(result.output.keys())
                logger.info(f"    Output keys: {output_keys}")
                for key in output_keys:
                    val = result.output.get(key, "")
                    if val:
                        preview = str(val)[:100].replace("\n", " ")
                        logger.debug(f"    {key}: {preview}...")
                if self._progress_callback:
                    self._progress_callback(stage_config.name, "completed")
                return result

            logger.warning(f"    Stage failed: {result.error or result.status} (elapsed: {elapsed:.1f}s)")

            if attempt < config.retries:
                logger.info(f"    Retrying... (attempt {attempt + 1}/{config.retries})")

        total_time = time.time() - start_time
        logger.error(f"    Stage failed after {total_time:.1f}s, {config.retries} attempts")
        return result

    def _update_context_from_result(self, result: StageResult) -> None:
        if self._context is None:
            return

        if "new_instruction_strategy" in result.output:
            self._context.current_strategy = result.output["new_instruction_strategy"]

    def _check_success_criteria(self) -> bool:
        verify_result = self._context.stage_results.get("verify") if self._context else None

        if not verify_result or not verify_result.is_success:
            stage_results = self._context.stage_results if self._context else {}
            if stage_results:
                successful_stages = sum(1 for r in stage_results.values() if r.is_success)
                total_stages = len(self.config.stages)
                logger.info(f"    Convergence check: {successful_stages}/{total_stages} stages succeeded")
                if successful_stages >= total_stages * 0.7:
                    return True
            return False

        verified = verify_result.output.get("verified_axioms", "")
        if not verified:
            return False

        axiom_count = len(verified.split())
        if axiom_count < self.config.signal_loss_threshold:
            return False

        return True

    def _collect_final_output(self) -> dict[str, Any]:
        if self._context is None:
            return {}

        output = {}
        for stage_name, result in self._context.stage_results.items():
            if result.is_success:
                output[stage_name] = result.output

        return output

    def _determine_status(
        self,
        converged: bool,
        all_results: dict[str, list[StageResult]],
    ) -> PipelineStatus:
        if converged:
            return PipelineStatus.SUCCESS

        has_failures = any(
            not r.is_success
            for results in all_results.values()
            for r in results
        )

        has_successes = any(
            r.is_success
            for results in all_results.values()
            for r in results
        )

        if has_failures and has_successes:
            return PipelineStatus.PARTIAL
        elif has_failures:
            return PipelineStatus.FAILED
        else:
            return PipelineStatus.NOT_STARTED


class SimulateDecision(dspy.Module):
    """Main SimulateDecision with configurable pipeline support."""

    _default_strategy: str = (
        "Identify the core structural elements and strip all human-centric metaphors."
    )

    def __init__(
        self,
        config: EngineConfig | None = None,
        pipeline_config: PipelineConfig | None = None,
        max_iterations: int = 3,
        storage_path: Path | None = None,
        progress_callback: callable | None = None,
    ):
        super().__init__()
        self.config = config or get_config()
        self.pipeline_config = pipeline_config or PipelineConfig(max_iterations=max_iterations)
        self.max_iterations = max_iterations
        self.state = StrategyState()
        self.storage = Storage(storage_path)
        self.progress_callback = progress_callback

    def forward(
        self,
        concept: str,
        save_result: bool = True,
        initial_strategy: str | None = None,
    ) -> dict[str, object]:
        self.state.concept = concept
        strategy = initial_strategy or self._default_strategy

        logger.info(_header(f"INITIATING SIMULATE_DECISION: {concept}"))
        logger.info(f"Pipeline: {self.pipeline_config.name}")
        logger.info(f"Stages: {[s.name for s in self.pipeline_config.stages]}")
        logger.info(f"Max iterations: {self.max_iterations}")

        pipeline = Pipeline(
            config=self.pipeline_config,
            engine_config=self.config,
        )
        pipeline.set_progress_callback(self.progress_callback)

        result = pipeline.execute(concept, initial_strategy=strategy)

        final_result = self._build_result(result, strategy)

        if save_result:
            entry = create_entry(concept, final_result, final_result["status"])
            self.storage.append(entry)
            logger.info(f"\n[Saved to] {self.storage.storage_path}")

        return final_result

    def _build_result(
        self,
        pipeline_result: PipelineResult,
        initial_strategy: str,
    ) -> dict[str, object]:
        if pipeline_result.status == PipelineStatus.SUCCESS:
            blueprint = ""
            atoms = ""
            if "reconstruct" in pipeline_result.final_output:
                blueprint = pipeline_result.final_output["reconstruct"].get("technical_blueprint", "")
            if "verify" in pipeline_result.final_output:
                atoms = pipeline_result.final_output["verify"].get("verified_axioms", "")

            return {
                "status": "SUCCESS",
                "iterations": pipeline_result.iterations,
                "blueprint": blueprint,
                "purified_atoms": atoms,
                "strategy_history": self.state.get_policy_history(),
                "metadata": {
                    "concept": pipeline_result.concept,
                    "total_iterations": pipeline_result.iterations,
                    "total_tokens_used": pipeline_result.metadata.get("total_tokens_used", 0),
                    "converged": pipeline_result.metadata.get("converged", False),
                    "initial_strategy": initial_strategy,
                    "pipeline_name": self.pipeline_config.name,
                    "stages_executed": list(pipeline_result.stage_results.keys()),
                    "final_output": pipeline_result.final_output,
                },
            }
        else:
            return {
                "status": "FAILURE",
                "error": pipeline_result.error or "Pipeline did not converge",
                "iterations": pipeline_result.iterations,
                "strategy_history": self.state.get_policy_history(),
                "metadata": {
                    "concept": pipeline_result.concept,
                    "total_iterations": pipeline_result.iterations,
                    "pipeline_name": self.pipeline_config.name,
                    "stages_executed": list(pipeline_result.stage_results.keys()),
                },
            }


def _header(text: str) -> str:
    return "=" * 60 + f"\n{text}\n" + "=" * 60
