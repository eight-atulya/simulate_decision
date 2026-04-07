from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulate_decision.core.pipeline import IterationMode, PipelineConfig
from simulate_decision.core.stages.base import FailureAction, StageConfig


@dataclass
class StoryDecompositionTemplate:
    """A predefined pipeline for decomposing user stories into detailed specifications."""
    name: str
    description: str
    config: PipelineConfig
    use_cases: list[str] = field(default_factory=list)


class StoryPipelineTemplates:
    """Pipeline templates for story decomposition and analysis."""

    USER_STORY_DECOMPOSITION = StoryDecompositionTemplate(
        name="user_story",
        description="Decompose user stories into detailed specifications with stakeholder analysis, gap detection, and actionable requirements",
        config=PipelineConfig(
            name="user_story",
            stages=[
                # Layer 1: Extract core story elements
                StageConfig(
                    name="extract",
                    signature_name="deconstruct",
                    retries=2,
                ),
                # Layer 2: Identify stakeholders and context
                StageConfig(
                    name="stakeholder_analysis",
                    signature_name="expand",
                    retries=1,
                ),
                # Layer 3: Find key questions
                StageConfig(
                    name="question_finding",
                    signature_name="analyze",
                    retries=2,
                ),
                # Layer 4: Map relationships
                StageConfig(
                    name="relationship_mapping",
                    signature_name="compare",
                    retries=1,
                ),
                # Layer 5: Break into atomic requirements
                StageConfig(
                    name="requirement_breakdown",
                    signature_name="deconstruct",
                    retries=2,
                ),
                # Layer 6: Evaluate feasibility
                StageConfig(
                    name="feasibility_check",
                    signature_name="critique",
                    retries=1,
                    on_failure=FailureAction.SKIP,
                ),
                # Layer 7: Find gaps
                StageConfig(
                    name="gap_analysis",
                    signature_name="analyze",
                    retries=1,
                ),
                # Layer 8: Generate specification
                StageConfig(
                    name="specification_design",
                    signature_name="reconstruct",
                    retries=1,
                ),
            ],
            iteration_mode=IterationMode.ADAPTIVE,
            max_iterations=3,
            quality_threshold=0.7,
        ),
        use_cases=["user story analysis", "requirement gathering", "project planning"],
    )

    BUSINESS_ANALYSIS = StoryDecompositionTemplate(
        name="business_analysis",
        description="Comprehensive business analysis: problem discovery, solution design, ROI analysis, and implementation roadmap",
        config=PipelineConfig(
            name="business_analysis",
            stages=[
                StageConfig(name="problem_discovery", signature_name="deconstruct", retries=2),
                StageConfig(name="market_analysis", signature_name="expand", retries=2),
                StageConfig(name="stakeholder_mapping", signature_name="compare", retries=1),
                StageConfig(name="solution_design", signature_name="reconstruct", retries=2),
                StageConfig(name="roi_analysis", signature_name="critique", retries=1, on_failure=FailureAction.SKIP),
                StageConfig(name="risk_assessment", signature_name="analyze", retries=1),
                StageConfig(name="roadmap_generation", signature_name="reconstruct", retries=1),
            ],
            iteration_mode=IterationMode.ADAPTIVE,
            max_iterations=3,
            quality_threshold=0.75,
        ),
        use_cases=["business case development", "strategic planning", "investment analysis"],
    )

    TECHNICAL_DECOMPOSITION = StoryDecompositionTemplate(
        name="technical_story",
        description="Decompose technical requirements into system design, architecture, API specs, and implementation steps",
        config=PipelineConfig(
            name="technical_story",
            stages=[
                StageConfig(name="requirement_extraction", signature_name="deconstruct", retries=2),
                StageConfig(name="use_case_mapping", signature_name="expand", retries=1),
                StageConfig(name="architecture_design", signature_name="abstract", retries=2),
                StageConfig(name="api_specification", signature_name="reconstruct", retries=1),
                StageConfig(name="data_modeling", signature_name="deconstruct", retries=1),
                StageConfig(name="integration_analysis", signature_name="compare", retries=1),
                StageConfig(name="implementation_planning", signature_name="reconstruct", retries=1),
            ],
            iteration_mode=IterationMode.FIXED,
            max_iterations=2,
        ),
        use_cases=["technical requirements", "system design", "API documentation"],
    )

    PROBLEM_ANALYSIS = StoryDecompositionTemplate(
        name="problem_decomposition",
        description="Deep problem analysis: root cause, impact chain, stakeholder effects, and solution pathways",
        config=PipelineConfig(
            name="problem_decomposition",
            stages=[
                StageConfig(name="problem_identification", signature_name="deconstruct", retries=2),
                StageConfig(name="root_cause_analysis", signature_name="analyze", retries=2),
                StageConfig(name="impact_mapping", signature_name="compare", retries=1),
                StageConfig(name="stakeholder_analysis", signature_name="expand", retries=1),
                StageConfig(name="solution_pathways", signature_name="reconstruct", retries=2),
                StageConfig(name="feasibility_evaluation", signature_name="critique", retries=1),
            ],
            iteration_mode=IterationMode.ADAPTIVE,
            max_iterations=3,
            quality_threshold=0.8,
        ),
        use_cases=["root cause analysis", "problem solving", "decision making"],
    )

    DECISION_FRAMEWORK = StoryDecompositionTemplate(
        name="decision_analysis",
        description="Structured decision making: options analysis, criteria weighting, risk assessment, and recommendation",
        config=PipelineConfig(
            name="decision_analysis",
            stages=[
                StageConfig(name="context_extraction", signature_name="deconstruct", retries=1),
                StageConfig(name="options_generation", signature_name="expand", retries=2),
                StageConfig(name="criteria_identification", signature_name="analyze", retries=1),
                StageConfig(name="options_comparison", signature_name="compare", retries=2),
                StageConfig(name="risk_assessment", signature_name="critique", retries=1),
                StageConfig(name="recommendation", signature_name="reconstruct", retries=1),
            ],
            iteration_mode=IterationMode.FIXED,
            max_iterations=2,
        ),
        use_cases=["decision making", "option comparison", "strategic choices"],
    )

    @classmethod
    def get(cls, name: str) -> StoryDecompositionTemplate | None:
        templates = {
            "user_story": cls.USER_STORY_DECOMPOSITION,
            "business_analysis": cls.BUSINESS_ANALYSIS,
            "technical_story": cls.TECHNICAL_DECOMPOSITION,
            "problem_decomposition": cls.PROBLEM_ANALYSIS,
            "decision_framework": cls.DECISION_FRAMEWORK,
        }
        return templates.get(name)

    @classmethod
    def list_templates(cls) -> list[dict[str, Any]]:
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
                cls.USER_STORY_DECOMPOSITION,
                cls.BUSINESS_ANALYSIS,
                cls.TECHNICAL_DECOMPOSITION,
                cls.PROBLEM_ANALYSIS,
                cls.DECISION_FRAMEWORK,
            ]
        ]

    @classmethod
    def create_config(cls, name: str, **overrides) -> PipelineConfig:
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
