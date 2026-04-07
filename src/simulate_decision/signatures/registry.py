from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import dspy


class SignatureType(Enum):
    """Types of DSPy predictors for signatures."""
    CHAIN_OF_THOUGHT = "cot"
    CHAIN_OF_VERIFY = "cov"
    CHAIN_OF_REASONING = "cor"
    PREDICT = "predict"
    BASIC = "basic"


class FailureAction(Enum):
    """Action to take when a stage fails."""
    RETRY = "retry"
    SKIP = "skip"
    STOP = "stop"
    CUSTOM = "custom"


@dataclass
class InputField:
    """Definition of an input field for a signature template."""
    name: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class OutputField:
    """Definition of an output field for a signature template."""
    name: str
    description: str
    reasoning_field: str | None = None


@dataclass
class SignatureTemplate:
    """Template for creating signatures programmatically."""
    name: str
    description: str
    instruction_template: str
    inputs: list[InputField]
    outputs: list[OutputField]
    signature_type: SignatureType = SignatureType.CHAIN_OF_THOUGHT

    def create_signature_class(self) -> type[dspy.Signature]:
        """Create a DSPy Signature class from this template."""
        input_fields = {}
        output_fields = {}

        for inp in self.inputs:
            input_fields[inp.name] = dspy.InputField(desc=inp.description)

        for out in self.outputs:
            if out.reasoning_field:
                output_fields[out.reasoning_field] = dspy.OutputField(desc="${reasoning}")
            output_fields[out.name] = dspy.OutputField(desc=out.description)

        return type(
            self.name,
            (dspy.Signature,),
            {"__doc__": self.description, **input_fields, **output_fields}
        )

    def create_predictor(self) -> dspy.Predict:
        """Create a DSPy Predictor using this template."""
        sig_class = self.create_signature_class()

        if self.signature_type == SignatureType.CHAIN_OF_THOUGHT:
            return dspy.ChainOfThought(sig_class)
        elif self.signature_type == SignatureType.CHAIN_OF_VERIFY:
            return dspy.ChainOfVerify(sig_class)
        elif self.signature_type == SignatureType.CHAIN_OF_REASONING:
            return dspy.ChainOfReasoning(sig_class)
        else:
            return dspy.Predict(sig_class)


class SignatureRegistry:
    """Registry for all available signature templates."""

    _instance: SignatureRegistry | None = None
    _templates: dict[str, SignatureTemplate] = {}
    _custom_factories: dict[str, Callable[[], type[dspy.Signature]]] = {}

    def __new__(cls) -> SignatureRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_builtins()
        return cls._instance

    def _initialize_builtins(self) -> None:
        """Initialize with built-in signatures."""
        self._templates = {
            "deconstruct": SignatureTemplate(
                name="DeconstructSignature",
                description="ATOMIC DECONSTRUCTION. Decompose a concept into irreducible atoms.",
                instruction_template="Decompose the input concept into its fundamental atomic components using the provided strategy. Strip all human-centric metaphors and identify the core structural elements.",
                inputs=[
                    InputField("input_concept", "The subject to be atomized."),
                    InputField("instruction_strategy", "The current strategy for extraction."),
                ],
                outputs=[
                    OutputField("atomic_atoms", "A list of raw structural components.", "reasoning"),
                    OutputField("noise_detected", "List of identified metaphors/analogies to be stripped.", None),
                ],
            ),
            "verify": SignatureTemplate(
                name="VerifySignature",
                description="AXIOMATIC VALIDATION. Filter atoms to only those true in a vacuum.",
                instruction_template="Filter the provided atoms to keep only those that are mathematically undeniable and true regardless of context. Reject anything that requires assumption.",
                inputs=[
                    InputField("atomic_atoms", "The raw list of components."),
                ],
                outputs=[
                    OutputField("verified_axioms", "Only the mathematically undeniable atoms.", "reasoning"),
                    OutputField("rejection_reason", "Reason why certain atoms were purged.", None),
                ],
            ),
            "reconstruct": SignatureTemplate(
                name="ReconstructSignature",
                description="TECHNICAL RECONSTRUCTION. Build blueprint from verified axioms.",
                instruction_template="Using the verified axioms, construct a technical implementation blueprint that represents the pure structural essence of the concept.",
                inputs=[
                    InputField("verified_axioms", "The validated atomic components."),
                ],
                outputs=[
                    OutputField("technical_blueprint", "The technical implementation blueprint.", "reasoning"),
                ],
            ),
            "analyze": SignatureTemplate(
                name="AnalyzeSignature",
                description="POLICY OPTIMIZATION. Analyze failure and generate correction strategy.",
                instruction_template="Analyze the verification failure signal and the previous atoms. Generate a corrected strategy that addresses the identified issues.",
                inputs=[
                    InputField("error_signal", "The verification failure signal."),
                    InputField("previous_atoms", "The atoms that failed verification."),
                ],
                outputs=[
                    OutputField("new_instruction_strategy", "The optimized strategy for next iteration.", "reasoning"),
                ],
            ),
            "synthesize": SignatureTemplate(
                name="SynthesizeSignature",
                description="SYNTHESIS. Merge multiple inputs into a unified whole.",
                instruction_template="Synthesize the provided inputs into a coherent, unified output that captures the essence of all inputs.",
                inputs=[
                    InputField("inputs", "Multiple inputs to synthesize."),
                ],
                outputs=[
                    OutputField("synthesized_output", "The unified result.", "reasoning"),
                ],
            ),
            "critique": SignatureTemplate(
                name="CritiqueSignature",
                description="CRITIQUE. Evaluate quality and provide feedback.",
                instruction_template="Critically evaluate the provided content and provide constructive feedback on its quality, accuracy, and completeness.",
                inputs=[
                    InputField("content", "The content to critique."),
                ],
                outputs=[
                    OutputField("score", "Quality score (0-1).", None),
                    OutputField("feedback", "Constructive feedback.", "reasoning"),
                ],
            ),
            "compare": SignatureTemplate(
                name="CompareSignature",
                description="COMPARISON. Compare two concepts and identify relationships.",
                instruction_template="Compare the two provided concepts and identify their similarities, differences, and relationships.",
                inputs=[
                    InputField("concept_a", "First concept to compare."),
                    InputField("concept_b", "Second concept to compare."),
                ],
                outputs=[
                    OutputField("similarities", "Key similarities.", "reasoning"),
                    OutputField("differences", "Key differences.", None),
                ],
            ),
            "expand": SignatureTemplate(
                name="ExpandSignature",
                description="EXPANSION. Elaborate on a concept with more detail.",
                instruction_template="Expand on the given concept with additional detail, examples, and elaboration while maintaining the core meaning.",
                inputs=[
                    InputField("concept", "The concept to expand."),
                    InputField("depth", "Level of detail (shallow, medium, deep).", required=False, default="medium"),
                ],
                outputs=[
                    OutputField("expanded_content", "Elaborated content.", "reasoning"),
                ],
            ),
            "abstract": SignatureTemplate(
                name="AbstractSignature",
                description="ABSTRACTION. Generalize a specific concept to its abstract form.",
                instruction_template="Extract the abstract essence from the specific content, identifying the universal principles and patterns.",
                inputs=[
                    InputField("specific_content", "The specific content to abstract."),
                ],
                outputs=[
                    OutputField("abstract_form", "The generalized abstract form.", "reasoning"),
                ],
            ),
        }

    def register(self, name: str, template: SignatureTemplate) -> None:
        """Register a new signature template."""
        self._templates[name] = template

    def register_factory(self, name: str, factory: Callable[[], type[dspy.Signature]]) -> None:
        """Register a custom signature factory."""
        self._custom_factories[name] = factory

    def get(self, name: str) -> SignatureTemplate | None:
        """Get a signature template by name."""
        return self._templates.get(name)

    def get_signature_class(self, name: str) -> type[dspy.Signature] | None:
        """Get the DSPy Signature class for a template."""
        template = self._templates.get(name)
        if template:
            return template.create_signature_class()
        if name in self._custom_factories:
            return self._custom_factories[name]()
        return None

    def get_predictor(self, name: str, signature_type: SignatureType | None = None) -> dspy.Predict | None:
        """Get a predictor for a signature."""
        template = self._templates.get(name)
        if not template:
            return None

        sig_type = signature_type or template.signature_type

        if sig_type == SignatureType.CHAIN_OF_THOUGHT:
            return dspy.ChainOfThought(template.create_signature_class())
        elif sig_type == SignatureType.CHAIN_OF_VERIFY:
            return dspy.ChainOfVerify(template.create_signature_class())
        else:
            return dspy.Predict(template.create_signature_class())

    def list_templates(self) -> list[str]:
        """List all available signature templates."""
        return list(self._templates.keys())

    def get_template_info(self, name: str) -> dict[str, Any] | None:
        """Get information about a template."""
        template = self._templates.get(name)
        if not template:
            return None

        return {
            "name": template.name,
            "description": template.description,
            "inputs": [{"name": i.name, "description": i.description} for i in template.inputs],
            "outputs": [{"name": o.name, "description": o.description} for o in template.outputs],
            "signature_type": template.signature_type.value,
        }


def get_signature_registry() -> SignatureRegistry:
    """Get the global signature registry."""
    return SignatureRegistry()
