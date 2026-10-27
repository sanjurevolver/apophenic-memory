"""SQLite persistence layer for apophenic_memory.

Database file: <project_root>/output/apophenic.db
All functions use a fresh connection per call so the module is safe to import
without side-effects; call init_db() explicitly at startup.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Resolve project root relative to this file: db/ -> apophenic_memory/ -> src/ -> project/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = _PROJECT_ROOT / "output" / "apophenic.db"


def _connect() -> sqlite3.Connection:
    """Return a connection with row_factory set to dict-like Row."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the memories table if it doesn't already exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id          TEXT PRIMARY KEY,
                gap_start   TEXT NOT NULL,
                gap_end     TEXT NOT NULL,
                memory_text TEXT NOT NULL,
                why_this_is_false TEXT,
                rationale   TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def save_memory(memory_data: dict) -> None:
    """Insert a single memory record.

    Expected keys: id, gap_start, gap_end, memory_text,
                   why_this_is_false, rationale.
    Silently ignores duplicate ids (INSERT OR IGNORE).
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO memories
                (id, gap_start, gap_end, memory_text, why_this_is_false, rationale)
            VALUES
                (:id, :gap_start, :gap_end, :memory_text, :why_this_is_false, :rationale)
            """,
            {
                "id": memory_data.get("id", ""),
                "gap_start": memory_data.get("gap_start", ""),
                "gap_end": memory_data.get("gap_end", ""),
                "memory_text": memory_data.get("memory_text", ""),
                "why_this_is_false": memory_data.get("why_this_is_false", ""),
                "rationale": memory_data.get("rationale", ""),
            },
        )
        conn.commit()


def get_memories() -> list[dict]:
    """Return all saved memories as a list of plain dicts, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def wipe_db() -> int:
    """Delete every row from the memories table. Returns the row count removed."""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM memories")
        conn.commit()
        return cursor.rowcount
