from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".simulatedecision" / "history.json"
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, records: list[dict[str, Any]]) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def append(self, entry: dict[str, Any]) -> None:
        records = self.load()
        records.append(entry)
        self.save(records)

    def get_all(self) -> list[dict[str, Any]]:
        return self.load()

    def get_by_concept(self, concept: str) -> list[dict[str, Any]]:
        return [r for r in self.load() if r.get("concept") == concept]

    def clear(self) -> None:
        if self.storage_path.exists():
            self.storage_path.unlink()


def create_entry(
    concept: str,
    result: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    metadata = result.get("metadata", {})
    return {
        "timestamp": datetime.now().isoformat(),
        "concept": concept,
        "status": status,
        "iterations": result.get("iterations"),
        "purified_atoms": result.get("purified_atoms"),
        "blueprint": result.get("blueprint"),
        "error": result.get("error"),
        "strategy_history": result.get("strategy_history", []),
        "metadata": {
            "total_tokens_used": metadata.get("total_tokens_used", 0),
            "converged": metadata.get("converged", False),
            "initial_strategy": metadata.get("initial_strategy", ""),
            "final_strategy": metadata.get("final_strategy", ""),
            "model_name": metadata.get("model_name", ""),
            "signal_loss_threshold": metadata.get("signal_loss_threshold", 0),
            "stages_executed": metadata.get("stages_executed", []),
            "all_reasonings": metadata.get("all_reasonings", []),
            "atoms_before_verification": metadata.get("atoms_before_verification", ""),
            "atoms_after_verification": metadata.get("atoms_after_verification", ""),
            "noise_filtered": metadata.get("noise_filtered", ""),
        },
    }
