from __future__ import annotations

import dspy


class DeconstructSignature(dspy.Signature):
    """STREAM INGESTOR (SI). Perform bit-wise deconstruction of input sequence into discrete packets."""

    input_concept: str = dspy.InputField(desc="The input bitstream sequence to be processed.")
    instruction_strategy: str = dspy.InputField(desc="The current state transition strategy.")
    reasoning: str = dspy.OutputField(desc="${reasoning} - SDA transition logic")
    atomic_atoms: str = dspy.OutputField(desc="Discrete bit packets b_i ∈ {0, 1} from deconstruction.")
    noise_detected: str = dspy.OutputField(desc="Non-deterministic entropy sources to be filtered.")


class VerifySignature(dspy.Signature):
    """STATE REGISTER (Σ). Validate and update internal configuration state."""

    atomic_atoms: str = dspy.InputField(desc="Incoming bit packets for state transition.")
    reasoning: str = dspy.OutputField(desc="${reasoning} - Deterministic state update")
    verified_axioms: str = dspy.OutputField(desc="Validated state σ_{t+1} after transition.")
    rejection_reason: str = dspy.OutputField(desc="Invalid transitions violating determinism constraints.")


class ReconstructSignature(dspy.Signature):
    """LOGIC TRANSFORMATION UNIT (LTU). Execute deterministic transition function δ(σ_t, b_{t+1})."""

    verified_axioms: str = dspy.InputField(desc="Current state σ_t and input bit b_{t+1}.")
    reasoning: str = dspy.OutputField(desc="${reasoning} - Zero-entropy transition")
    technical_blueprint: str = dspy.OutputField(desc="Result state σ_{t+1} and final output y after EOS.")


class FailureAnalyzerSignature(dspy.Signature):
    """POLICY OPTIMIZATION. Analyze failure and generate correction strategy."""

    error_signal: str = dspy.InputField(desc="The verification failure signal.")
    previous_atoms: str = dspy.InputField(desc="The atoms that failed verification.")
    reasoning: str = dspy.OutputField(desc="${reasoning}")
    new_instruction_strategy: str = dspy.OutputField(desc="The optimized strategy for next iteration.")
