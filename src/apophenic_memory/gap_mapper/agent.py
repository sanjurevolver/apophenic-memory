from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apophenic_memory.ingest.diary_parser import parse_diary_text


@dataclass
class GapDescriptor:
    start_date: str
    end_date: str
    reason: str
    intensity: str = "moderate"


def detect_gap_descriptors(source: str, min_gap_days: int = 4) -> list[GapDescriptor]:
    entries = parse_diary_text(source)
    if len(entries) < 2:
        return []

    gaps: list[GapDescriptor] = []
    for previous, current in zip(entries, entries[1:]):
        previous_date = previous["date"]
        current_date = current["date"]
        difference = (datetime.strptime(current_date, "%Y-%m-%d") - datetime.strptime(previous_date, "%Y-%m-%d")).days
        if difference < min_gap_days:
            continue

        intensity = "moderate"
        if difference >= 10:
            intensity = "high"
        if difference >= 20:
            intensity = "extreme"

        gaps.append(
            GapDescriptor(
                start_date=previous_date,
                end_date=current_date,
                reason=f"{difference}-day gap between entries; a missing autobiographical segment likely exists between {previous_date} and {current_date}.",
                intensity=intensity,
            )
        )

    return gaps
