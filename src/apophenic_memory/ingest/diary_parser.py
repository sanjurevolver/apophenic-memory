from __future__ import annotations

import re
from pathlib import Path


def parse_diary(path: Path) -> list[dict]:
    """Read a diary file and return date-based entries.

    Supports entries in the format used by the project fixture:
        2012-02-28: I stayed up too late...

    Returns a list of dictionaries shaped like:
        [{"date": "YYYY-MM-DD", "text": "entry content"}, ...]
    """
    if not isinstance(path, Path):
        path = Path(path)

    text = path.read_text(encoding='utf-8')
    return parse_diary_text(text)


def parse_diary_text(text: str) -> list[dict]:
    """Parse date-prefixed entries from diary text."""
    if not text.strip():
        return []

    entries: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        match = re.match(r'^(\d{4}-\d{2}-\d{2})\s*:\s*(.*)$', line)
        if not match:
            continue

        date_part, text_part = match.groups()
        cleaned_text = ' '.join(text_part.split())
        if cleaned_text:
            entries.append({"date": date_part, "text": cleaned_text})

    return entries
