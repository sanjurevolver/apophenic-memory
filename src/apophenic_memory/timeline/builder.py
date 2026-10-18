from __future__ import annotations

from datetime import date, datetime


def _parse_iso_date(value: str) -> date:
    """Parse YYYY-MM-DD into a date object."""
    return datetime.strptime(value, '%Y-%m-%d').date()


def build_timeline(diary_entries: list, photo_entries: list) -> list[dict]:
    """Merge diary and photo entries and sort them chronologically by date."""
    merged: list[dict] = []
    for entry in diary_entries:
        merged.append({
            'date': entry['date'],
            'type': 'diary',
            'content': entry.get('text', ''),
            'source_path': entry.get('source_path', ''),
        })

    for entry in photo_entries:
        merged.append({
            'date': entry['date'],
            'type': 'photo',
            'content': entry.get('path', ''),
            'source_path': entry.get('path', ''),
        })

    merged.sort(key=lambda item: _parse_iso_date(item['date']))
    return merged


def detect_gaps(timeline: list, min_days: int = 14) -> list[dict]:
    """Find consecutive date gaps in the timeline larger than min_days."""
    if not timeline:
        return []

    sorted_timeline = sorted(timeline, key=lambda item: _parse_iso_date(item['date']))
    gaps: list[dict] = []

    for prev, current in zip(sorted_timeline, sorted_timeline[1:]):
        prev_date = _parse_iso_date(prev['date'])
        current_date = _parse_iso_date(current['date'])
        delta_days = (current_date - prev_date).days

        if delta_days > min_days:
            gaps.append({
                'start_date': prev['date'],
                'end_date': current['date'],
                'gap_days': delta_days,
            })

    return gaps
