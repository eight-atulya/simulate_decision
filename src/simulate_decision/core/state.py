from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AttemptRecord:
    iteration: int
    strategy: str
    atoms_count: int
    axioms_count: int
    error_signal: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    stage: str = "unknown"
    reasoning: str = ""
    tokens_used: int = 0
    model_name: str = ""
    raw_atoms: str = ""
    noise_detected: str = ""
    verified_atoms: str = ""
    rejection_reason: str = ""
    optimization_reasoning: str = ""
    new_strategy: str = ""


@dataclass
class StrategyState:
    current_strategy: str = "Identify the core structural elements and strip all human-centric metaphors."
    iteration: int = 0
    history: list[AttemptRecord] = field(default_factory=list)
    converged: bool = False
    last_updated: datetime = field(default_factory=datetime.now)
    concept: str = ""
    total_tokens_used: int = 0
    all_reasonings: list[str] = field(default_factory=list)

    def record_attempt(
        self,
        iteration: int,
        strategy: str,
        atoms_count: int,
        axioms_count: int,
        error_signal: str | None = None,
        stage: str = "unknown",
        reasoning: str = "",
        tokens_used: int = 0,
        model_name: str = "",
        raw_atoms: str = "",
        noise_detected: str = "",
        verified_atoms: str = "",
        rejection_reason: str = "",
        optimization_reasoning: str = "",
        new_strategy: str = "",
    ) -> None:
        self.iteration = iteration
        self.last_updated = datetime.now()
        self.total_tokens_used += tokens_used
        if reasoning:
            self.all_reasonings.append(reasoning)

        record = AttemptRecord(
            iteration=iteration,
            strategy=strategy,
            atoms_count=atoms_count,
            axioms_count=axioms_count,
            error_signal=error_signal,
            stage=stage,
            reasoning=reasoning,
            tokens_used=tokens_used,
            model_name=model_name,
            raw_atoms=raw_atoms,
            noise_detected=noise_detected,
            verified_atoms=verified_atoms,
            rejection_reason=rejection_reason,
            optimization_reasoning=optimization_reasoning,
            new_strategy=new_strategy,
            timestamp=self.last_updated.isoformat(),
        )
        self.history.append(record)

    def update_strategy(self, new_strategy: str) -> None:
        self.current_strategy = new_strategy
        self.last_updated = datetime.now()

    def mark_converged(self) -> None:
        self.converged = True

    def get_policy_history(self) -> list[dict[str, Any]]:
        return [
            {
                "iteration": r.iteration,
                "strategy": r.strategy,
                "atoms_count": r.atoms_count,
                "axioms_count": r.axioms_count,
                "error_signal": r.error_signal,
                "timestamp": r.timestamp,
                "stage": r.stage,
                "reasoning": r.reasoning,
                "tokens_used": r.tokens_used,
                "model_name": r.model_name,
                "raw_atoms": r.raw_atoms,
                "noise_detected": r.noise_detected,
                "verified_atoms": r.verified_atoms,
                "rejection_reason": r.rejection_reason,
                "optimization_reasoning": r.optimization_reasoning,
                "new_strategy": r.new_strategy,
            }
            for r in self.history
        ]

    def reset(self) -> None:
        self.current_strategy = "Identify the core structural elements and strip all human-centric metaphors."
        self.iteration = 0
        self.history = []
        self.converged = False
        self.last_updated = datetime.now()
        self.concept = ""
        self.total_tokens_used = 0
        self.all_reasonings = []
