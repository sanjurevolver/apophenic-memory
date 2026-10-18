from __future__ import annotations

import json
from pathlib import Path


def load_people(path: Path) -> list[dict]:
    """Load a people.json file and validate each person entry.

    Expected format is a JSON array of objects with keys like:
        {"name": "Friend A", "relationship": "friend"}
    """
    if not isinstance(path, Path):
        path = Path(path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, list):
        raise ValueError('people.json must contain a list of person objects')

    people: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('each person entry must be an object')

        name = item.get('name')
        relationship = item.get('relationship')

        if not isinstance(name, str) or not name.strip():
            raise ValueError('each person must have a non-empty name')
        if not isinstance(relationship, str) or not relationship.strip():
            raise ValueError('each person must have a non-empty relationship')

        people.append({"name": name.strip(), "relationship": relationship.strip()})

    return people
