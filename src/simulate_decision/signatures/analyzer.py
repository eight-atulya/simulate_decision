from __future__ import annotations

import dspy


class DeconstructSignature(dspy.Signature):
    """ATOMIC DECONSTRUCTION. Decompose a concept into irreducible atoms."""

    input_concept: str = dspy.InputField(desc="The subject to be atomized.")
    instruction_strategy: str = dspy.InputField(desc="The current strategy for extraction.")
    reasoning: str = dspy.OutputField(desc="${reasoning}")
    atomic_atoms: str = dspy.OutputField(desc="A list of raw structural components.")
    noise_detected: str = dspy.OutputField(desc="List of identified metaphors/analogies to be stripped.")


class VerifySignature(dspy.Signature):
    """AXIOMATIC VALIDATION. Filter atoms to only those true in a vacuum."""

    atomic_atoms: str = dspy.InputField(desc="The raw list of components.")
    reasoning: str = dspy.OutputField(desc="${reasoning}")
    verified_axioms: str = dspy.OutputField(desc="Only the mathematically undeniable atoms.")
    rejection_reason: str = dspy.OutputField(desc="Reason why certain atoms were purged.")


class ReconstructSignature(dspy.Signature):
    """TECHNICAL RECONSTRUCTION. Build blueprint from verified axioms."""

    verified_axioms: str = dspy.InputField(desc="The validated atomic components.")
    reasoning: str = dspy.OutputField(desc="${reasoning}")
    technical_blueprint: str = dspy.OutputField(desc="The technical implementation blueprint.")


class FailureAnalyzerSignature(dspy.Signature):
    """POLICY OPTIMIZATION. Analyze failure and generate correction strategy."""

    error_signal: str = dspy.InputField(desc="The verification failure signal.")
    previous_atoms: str = dspy.InputField(desc="The atoms that failed verification.")
    reasoning: str = dspy.OutputField(desc="${reasoning}")
    new_instruction_strategy: str = dspy.OutputField(desc="The optimized strategy for next iteration.")
