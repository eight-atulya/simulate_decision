from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulate_decision.core.pipeline import IterationMode, PipelineConfig
from simulate_decision.core.stages.base import FailureAction, StageConfig


@dataclass
class PipelineTemplate:
    """A predefined pipeline configuration template."""
    name: str
    description: str
    config: PipelineConfig
    use_cases: list[str] = field(default_factory=list)


class PipelineTemplates:
    """Collection of predefined pipeline templates."""

    BASIC = PipelineTemplate(
        name="basic",
        description="Simple two-stage pipeline: deconstruct then reconstruct",
        config=PipelineConfig(
            name="basic",
            stages=[
                StageConfig(
                    name="deconstruct",
                    signature_name="deconstruct",
                    retries=2,
                ),
                StageConfig(
                    name="reconstruct",
                    signature_name="reconstruct",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.FIXED,
            max_iterations=2,
        ),
        use_cases=["quick analysis", "simple concepts"],
    )

    STANDARD = PipelineTemplate(
        name="standard",
        description="Standard three-stage pipeline: deconstruct, verify, reconstruct",
        config=PipelineConfig(
            name="standard",
            stages=[
                StageConfig(
                    name="deconstruct",
                    signature_name="deconstruct",
                    retries=2,
                ),
                StageConfig(
                    name="verify",
                    signature_name="verify",
                    retries=2,
                ),
                StageConfig(
                    name="reconstruct",
                    signature_name="reconstruct",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.FIXED,
            max_iterations=3,
            signal_loss_threshold=3,
        ),
        use_cases=["general analysis", "research", "deep dive"],
    )

    FULL_ANALYSIS = PipelineTemplate(
        name="full",
        description="Complete analysis with all stages including critique",
        config=PipelineConfig(
            name="full",
            stages=[
                StageConfig(
                    name="deconstruct",
                    signature_name="deconstruct",
                    retries=3,
                ),
                StageConfig(
                    name="verify",
                    signature_name="verify",
                    retries=2,
                ),
                StageConfig(
                    name="critique",
                    signature_name="critique",
                    retries=1,
                    on_failure=FailureAction.SKIP,
                ),
                StageConfig(
                    name="reconstruct",
                    signature_name="reconstruct",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.ADAPTIVE,
            max_iterations=5,
            quality_threshold=0.8,
        ),
        use_cases=["critical analysis", "quality assurance", "peer review"],
    )

    SYNTHESIS = PipelineTemplate(
        name="synthesis",
        description="Expand and synthesize concepts into unified understanding",
        config=PipelineConfig(
            name="synthesis",
            stages=[
                StageConfig(
                    name="deconstruct",
                    signature_name="deconstruct",
                    retries=1,
                ),
                StageConfig(
                    name="expand",
                    signature_name="expand",
                    retries=2,
                ),
                StageConfig(
                    name="abstract",
                    signature_name="abstract",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.FIXED,
            max_iterations=2,
        ),
        use_cases=["concept synthesis", "theory building", "generalization"],
    )

    COMPARATIVE = PipelineTemplate(
        name="comparative",
        description="Analyze and compare multiple concepts",
        config=PipelineConfig(
            name="comparative",
            stages=[
                StageConfig(
                    name="deconstruct",
                    signature_name="deconstruct",
                    retries=2,
                ),
                StageConfig(
                    name="abstract",
                    signature_name="abstract",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.FIXED,
            max_iterations=2,
        ),
        use_cases=["comparison", "relationship analysis", "taxonomy"],
    )

    ITERATIVE = PipelineTemplate(
        name="iterative",
        description="Iterative refinement with automatic strategy optimization",
        config=PipelineConfig(
            name="iterative",
            stages=[
                StageConfig(
                    name="deconstruct",
                    signature_name="deconstruct",
                    retries=3,
                ),
                StageConfig(
                    name="verify",
                    signature_name="verify",
                    retries=2,
                ),
                StageConfig(
                    name="analyze",
                    signature_name="analyze",
                    retries=1,
                    on_failure=FailureAction.STOP,
                ),
                StageConfig(
                    name="reconstruct",
                    signature_name="reconstruct",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.CONDITIONAL,
            max_iterations=5,
            signal_loss_threshold=3,
        ),
        use_cases=["complex problems", "refinement", "self-correction"],
    )

    @classmethod
    def get(cls, name: str) -> PipelineTemplate | None:
        """Get a template by name."""
        templates = {
            "basic": cls.BASIC,
            "standard": cls.STANDARD,
            "full": cls.FULL_ANALYSIS,
            "synthesis": cls.SYNTHESIS,
            "comparative": cls.COMPARATIVE,
            "iterative": cls.ITERATIVE,
        }
        return templates.get(name)

    @classmethod
    def list_templates(cls) -> list[dict[str, Any]]:
        """List all available templates."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "use_cases": t.use_cases,
                "stages": [s.name for s in t.config.stages],
                "max_iterations": t.config.max_iterations,
                "iteration_mode": t.config.iteration_mode.value,
            }
            for t in [
                cls.BASIC,
                cls.STANDARD,
                cls.FULL_ANALYSIS,
                cls.SYNTHESIS,
                cls.COMPARATIVE,
                cls.ITERATIVE,
            ]
        ]

    @classmethod
    def create_config(cls, name: str, **overrides) -> PipelineConfig:
        """Create a pipeline config from a template with optional overrides."""
        template = cls.get(name)
        if not template:
            raise ValueError(f"Unknown template: {name}")

        config = PipelineConfig(
            name=template.config.name,
            stages=template.config.stages.copy(),
            iteration_mode=template.config.iteration_mode,
            max_iterations=template.config.max_iterations,
            signal_loss_threshold=template.config.signal_loss_threshold,
            quality_threshold=template.config.quality_threshold,
        )

        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
            elif key == "stages" and isinstance(value, list):
                config.stages = value

        return config
