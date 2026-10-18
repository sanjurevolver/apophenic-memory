from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Memory:
    id: str
    memory_text: str
    why_this_is_false: str
    rationale: str
    is_fabricated: bool
    gap_id: str
    word_count: int
    constraints_passed: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    memory: Memory
    attempted_runs: int
    failures: list[str] = field(default_factory=list)
