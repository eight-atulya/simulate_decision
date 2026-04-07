"""E2E Tests for DSPy Signatures."""
from __future__ import annotations

from simulate_decision.signatures import (
    DeconstructSignature,
    FailureAnalyzerSignature,
    ReconstructSignature,
    VerifySignature,
)


class TestDeconstructSignature:
    """Tests for DeconstructSignature."""

    def test_signature_has_required_fields(self) -> None:
        """Test signature has all required fields."""
        fields = set(DeconstructSignature.model_fields)
        assert "input_concept" in fields
        assert "instruction_strategy" in fields
        assert "atomic_atoms" in fields
        assert "noise_detected" in fields

    def test_signature_instructions(self) -> None:
        """Test signature has proper instructions."""
        assert hasattr(DeconstructSignature, "instructions")
        assert "DECONSTRUCTION" in DeconstructSignature.instructions
        assert "atom" in DeconstructSignature.instructions.lower()


class TestVerifySignature:
    """Tests for VerifySignature."""

    def test_signature_has_required_fields(self) -> None:
        """Test signature has all required fields."""
        fields = set(VerifySignature.model_fields)
        assert "atomic_atoms" in fields
        assert "verified_axioms" in fields
        assert "rejection_reason" in fields

    def test_signature_instructions(self) -> None:
        """Test signature has proper instructions."""
        assert hasattr(VerifySignature, "instructions")
        assert "VALIDATION" in VerifySignature.instructions


class TestReconstructSignature:
    """Tests for ReconstructSignature."""

    def test_signature_has_required_fields(self) -> None:
        """Test signature has all required fields."""
        fields = set(ReconstructSignature.model_fields)
        assert "verified_axioms" in fields
        assert "technical_blueprint" in fields

    def test_signature_instructions(self) -> None:
        """Test signature has proper instructions."""
        assert hasattr(ReconstructSignature, "instructions")
        assert "RECONSTRUCTION" in ReconstructSignature.instructions


class TestFailureAnalyzerSignature:
    """Tests for FailureAnalyzerSignature."""

    def test_signature_has_required_fields(self) -> None:
        """Test signature has all required fields."""
        fields = set(FailureAnalyzerSignature.model_fields)
        assert "error_signal" in fields
        assert "previous_atoms" in fields
        assert "new_instruction_strategy" in fields

    def test_signature_instructions(self) -> None:
        """Test signature has proper instructions."""
        assert hasattr(FailureAnalyzerSignature, "instructions")
        assert "POLICY" in FailureAnalyzerSignature.instructions
        assert "OPTIMIZATION" in FailureAnalyzerSignature.instructions


class TestSignatureExports:
    """Tests for signature exports."""

    def test_all_signatures_exported(self) -> None:
        """Test all signatures are properly exported."""
        from simulate_decision.signatures import (
            DeconstructSignature,
            FailureAnalyzerSignature,
            ReconstructSignature,
            VerifySignature,
        )

        assert DeconstructSignature is not None
        assert VerifySignature is not None
        assert ReconstructSignature is not None
        assert FailureAnalyzerSignature is not None

    def test_signatures_are_distinct(self) -> None:
        """Test signatures are distinct classes."""
        signatures = [
            DeconstructSignature,
            VerifySignature,
            ReconstructSignature,
            FailureAnalyzerSignature,
        ]

        for i, sig1 in enumerate(signatures):
            for sig2 in signatures[i + 1 :]:
                assert sig1 is not sig2
