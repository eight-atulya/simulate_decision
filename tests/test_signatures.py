"""Tests for SimulateDecision Signatures."""
from simulate_decision.signatures import (
    DeconstructSignature,
    FailureAnalyzerSignature,
    ReconstructSignature,
    VerifySignature,
)


def test_deconstruct_signature_has_fields():
    fields = set(DeconstructSignature.model_fields)
    assert "input_concept" in fields
    assert "instruction_strategy" in fields
    assert "atomic_atoms" in fields
    assert "noise_detected" in fields


def test_verify_signature_has_fields():
    fields = set(VerifySignature.model_fields)
    assert "atomic_atoms" in fields
    assert "verified_axioms" in fields
    assert "rejection_reason" in fields


def test_reconstruct_signature_has_fields():
    fields = set(ReconstructSignature.model_fields)
    assert "verified_axioms" in fields
    assert "technical_blueprint" in fields


def test_failure_analyzer_signature_has_fields():
    fields = set(FailureAnalyzerSignature.model_fields)
    assert "error_signal" in fields
    assert "previous_atoms" in fields
    assert "new_instruction_strategy" in fields
