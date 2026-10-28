from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ConstraintResult:
    """Structured result for a single constraint check."""

    constraint_id: str
    passed: bool
    message: str

    def to_dict(self) -> dict:
        return {
            "constraint_id": self.constraint_id,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass
class Memory:
    id: str
    memory_text: str
    why_this_is_false: str
    rationale: str
    is_fabricated: bool
    gap_id: str
    word_count: int
    # Replaces the old hardcoded constraints_passed: list[str]
    constraint_results: list[dict] = field(default_factory=list)
    generation_status: Literal["ok", "completed_with_warnings"] = "ok"


@dataclass
class GenerationResult:
    memory: Memory
    attempted_runs: int
    failures: list[str] = field(default_factory=list)
