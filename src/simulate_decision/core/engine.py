from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

import dspy

from simulate_decision.core.config import EngineConfig, get_config
from simulate_decision.core.state import StrategyState
from simulate_decision.core.storage import Storage, create_entry
from simulate_decision.signatures import (
    DeconstructSignature,
    FailureAnalyzerSignature,
    ReconstructSignature,
    VerifySignature,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimulateDecisionCore(dspy.Module):
    _default_strategy: ClassVar[str] = (
        "Identify the core structural elements and strip all human-centric metaphors."
    )

    def __init__(
        self,
        config: EngineConfig | None = None,
        max_iterations: int = 3,
        storage_path: Path | None = None,
    ):
        super().__init__()
        self.config = config or get_config()
        self.max_iterations = max_iterations
        self.state = StrategyState()
        self.storage = Storage(storage_path)

        self.deconstruct = dspy.ChainOfThought(DeconstructSignature)
        self.verify = dspy.ChainOfThought(VerifySignature)
        self.reconstruct = dspy.ChainOfThought(ReconstructSignature)
        self.analyzer = dspy.ChainOfThought(FailureAnalyzerSignature)

import logging
from pathlib import Path
from typing import ClassVar

import dspy

from simulate_decision.core.config import EngineConfig, get_config
from simulate_decision.core.state import StrategyState
from simulate_decision.core.storage import Storage, create_entry
from simulate_decision.signatures import (
    DeconstructSignature,
    FailureAnalyzerSignature,
    ReconstructSignature,
    VerifySignature,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimulateDecisionCore(dspy.Module):
    _default_strategy: ClassVar[str] = (
        "Identify the core structural elements and strip all human-centric metaphors."
    )

    def __init__(
        self,
        config: EngineConfig | None = None,
        max_iterations: int = 3,
        storage_path: Path | None = None,
    ):
        super().__init__()
        self.config = config or get_config()
        self.max_iterations = max_iterations
        self.state = StrategyState()
        self.storage = Storage(storage_path)

        self.deconstruct = dspy.ChainOfThought(DeconstructSignature)
        self.verify = dspy.ChainOfThought(VerifySignature)
        self.reconstruct = dspy.ChainOfThought(ReconstructSignature)
        self.analyzer = dspy.ChainOfThought(FailureAnalyzerSignature)

    def forward(self, concept: str, save_result: bool = True) -> dict[str, object]:
        self.state.concept = concept
        current_strategy = self._default_strategy
        attempts = 0
        success = False
        final_result: dict[str, object] | None = None

        logger.info(_header(f"INITIATING SIMULATE_DECISION ANALYSIS: {concept}"))
        logger.info(f"Max iterations configured: {self.max_iterations}")
        logger.info(f"Signal loss threshold: {self.config.signal_loss_threshold} tokens")

        while attempts < self.max_iterations and not success:
            attempts += 1
            self.state.iteration = attempts
            logger.info(f"\n[ITERATION {attempts}] Strategy: {current_strategy[:80]}...")

            decon = self.deconstruct(
                input_concept=concept, instruction_strategy=current_strategy
            )
            raw_atoms = decon.atomic_atoms
            noise = decon.noise_detected
            tokens_used = self._estimate_tokens(decon)

            logger.info(
                f"[STAGE 1 - DECONSTRUCT] Why: Extracting atomic components using strategy '{current_strategy[:50]}...'"
            )
            logger.info(f"  -> Extracted {len(raw_atoms.split()) if raw_atoms else 0} raw atoms")
            logger.info(f"  -> Noise detected: {len(noise.split()) if noise else 0} tokens (metaphors/analogies to strip)")
            logger.info(f"  -> Reasoning: {decon.reasoning[:200]}..." if len(decon.reasoning) > 200 else f"  -> Reasoning: {decon.reasoning}")
            logger.info(f"  -> Tokens used: ~{tokens_used}")

            verification = self.verify(atomic_atoms=raw_atoms)
            axioms = verification.verified_axioms
            error_signal = verification.rejection_reason
            verify_tokens = self._estimate_tokens(verification)

            logger.info(
                "[STAGE 2 - VERIFY] Why: Filtering atoms to keep only mathematically undeniable axioms"
            )
            logger.info(f"  -> Verified {len(axioms.split()) if axioms else 0} axioms")
            logger.info(f"  -> Rejection reason: {error_signal or 'None (all atoms passed)'}")
            logger.info(f"  -> Reasoning: {verification.reasoning[:200]}..." if len(verification.reasoning) > 200 else f"  -> Reasoning: {verification.reasoning}")
            logger.info(f"  -> Tokens used: ~{verify_tokens}")

            if not axioms or len(axioms.split()) < self.config.signal_loss_threshold:
                logger.warning(
                    f"[!] SIGNAL LOSS DETECTED: Only {len(axioms.split()) if axioms else 0} axioms below threshold {self.config.signal_loss_threshold}"
                )
                logger.info("  -> Why: The verification step rejected too many atoms, triggering policy optimization")

                self.state.record_attempt(
                    iteration=attempts,
                    strategy=current_strategy,
                    atoms_count=len(raw_atoms.split()) if raw_atoms else 0,
                    axioms_count=0,
                    error_signal=error_signal,
                    stage="deconstruct+verify",
                    reasoning=decon.reasoning,
                    tokens_used=tokens_used + verify_tokens,
                    model_name=self.config.model_name,
                    raw_atoms=raw_atoms,
                    noise_detected=noise,
                    verified_atoms="",
                    rejection_reason=error_signal,
                )

                optimization = self.analyzer(
                    error_signal=error_signal, previous_atoms=raw_atoms
                )
                opt_tokens = self._estimate_tokens(optimization)

                logger.info(
                    "[STAGE 3 - OPTIMIZE] Why: Analyzing failure to generate correction strategy"
                )
                logger.info(f"  -> Optimization reasoning: {optimization.reasoning[:200]}..." if len(optimization.reasoning) > 200 else f"  -> Optimization reasoning: {optimization.reasoning}")
                logger.info(f"  -> New strategy: {optimization.new_instruction_strategy[:80]}...")
                logger.info(f"  -> Tokens used: ~{opt_tokens}")

                current_strategy = optimization.new_instruction_strategy
                self.state.update_strategy(current_strategy)
                self.state.record_attempt(
                    iteration=attempts,
                    strategy=current_strategy,
                    atoms_count=0,
                    axioms_count=0,
                    error_signal=None,
                    stage="optimization",
                    reasoning=optimization.reasoning,
                    tokens_used=opt_tokens,
                    model_name=self.config.model_name,
                    optimization_reasoning=optimization.reasoning,
                    new_strategy=optimization.new_instruction_strategy,
                )

                logger.info(f"[OPTIMIZER] New Policy Generated: {current_strategy[:60]}...")
                continue

            final_axioms = axioms
            success = True
            self.state.mark_converged()

            self.state.record_attempt(
                iteration=attempts,
                strategy=current_strategy,
                atoms_count=len(raw_atoms.split()) if raw_atoms else 0,
                axioms_count=len(axioms.split()) if axioms else 0,
                error_signal=None,
                stage="deconstruct+verify+success",
                reasoning=f"{decon.reasoning}\n---\n{verification.reasoning}",
                tokens_used=tokens_used + verify_tokens,
                model_name=self.config.model_name,
                raw_atoms=raw_atoms,
                noise_detected=noise,
                verified_atoms=axioms,
                rejection_reason=error_signal,
            )

            logger.info("[STAGE 3 - RECONSTRUCT] Why: Building technical blueprint from verified axioms")
            blueprint = self._reconstruct_logic(final_axioms)
            blueprint_tokens = self._estimate_tokens(
                dspy.Prediction(
                    reasoning="Reconstruct called",
                    technical_blueprint=blueprint
                )
            )

            logger.info(f"  -> Blueprint generated with {len(blueprint.split())} tokens")
            logger.info(f"  -> Total tokens this iteration: ~{tokens_used + verify_tokens + blueprint_tokens}")

            final_result = {
                "status": "SUCCESS",
                "iterations": attempts,
                "blueprint": blueprint,
                "purified_atoms": final_axioms,
                "strategy_history": self.state.get_policy_history(),
                "metadata": {
                    "concept": concept,
                    "total_iterations": attempts,
                    "total_tokens_used": self.state.total_tokens_used,
                    "converged": True,
                    "initial_strategy": self._default_strategy,
                    "final_strategy": current_strategy,
                    "model_name": self.config.model_name,
                    "signal_loss_threshold": self.config.signal_loss_threshold,
                    "stages_executed": ["deconstruct", "verify", "reconstruct"],
                    "all_reasonings": self.state.all_reasonings,
                    "atoms_before_verification": raw_atoms,
                    "atoms_after_verification": final_axioms,
                    "noise_filtered": noise,
                },
            }

        if not success:
            logger.error(f"Policy failed to converge after {self.max_iterations} iterations")
            final_result = {
                "status": "FAILURE",
                "error": "Policy could not converge on stable axioms.",
                "strategy_history": self.state.get_policy_history(),
                "metadata": {
                    "concept": concept,
                    "total_iterations": attempts,
                    "total_tokens_used": self.state.total_tokens_used,
                    "converged": False,
                    "initial_strategy": self._default_strategy,
                    "model_name": self.config.model_name,
                    "signal_loss_threshold": self.config.signal_loss_threshold,
                    "stages_executed": ["deconstruct", "verify"] * attempts,
                    "all_reasonings": self.state.all_reasonings,
                },
            }

        # Collect DSPy traces
        dspy_traces = dspy.settings.trace.copy()
        dspy.settings.trace = []  # Reset for next run

        # Add traces to result
        if final_result:
            final_result["dspy_traces"] = dspy_traces
            final_result["metadata"]["dspy_trace_count"] = len(dspy_traces)

        # Collect LM history and traces for full observability
        lm = dspy.settings.lm
        lm_history = []
        if lm and hasattr(lm, 'history'):
            lm_history = lm.history.copy() if isinstance(lm.history, list) else []
        
        # Add LM history and other observability data to result
        if final_result:
            final_result["lm_history"] = lm_history
            final_result["dspy_trace_count"] = len(dspy.settings.trace) if hasattr(dspy.settings, 'trace') else 0
            if "metadata" in final_result:
                final_result["metadata"]["lm_calls_count"] = len(lm_history)
                final_result["metadata"]["observability_enabled"] = True

        if save_result:
            entry = create_entry(concept, final_result, final_result["status"])
            self.storage.append(entry)
            logger.info(f"\n[Saved to] {self.storage.storage_path}")

        return final_result if final_result else {"status": "FAILURE", "error": "Unknown error"}

    def _reconstruct_logic(self, axioms: str) -> str:
        res = self.reconstruct(verified_axioms=axioms)
        logger.debug(f"Reconstruct reasoning: {res.reasoning[:200]}...")
        return res.technical_blueprint

    def _estimate_tokens(self, prediction: dspy.Prediction) -> int:
        total = 0
        for field_name in dir(prediction):
            if not field_name.startswith("_"):
                try:
                    value = getattr(prediction, field_name)
                    if isinstance(value, str):
                        total += len(value.split())
                except Exception:
                    pass
        return total


def _header(text: str) -> str:
    return "=" * 60 + f"\n{text}\n" + "=" * 60
