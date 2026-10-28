"""SQLite persistence layer for apophenic_memory.

Database file: <project_root>/output/apophenic.db
All functions use a fresh connection per call so the module is safe to import
without side-effects; call init_db() explicitly at startup.
"""
from __future__ import annotations

import gc
import os
import shutil
import sqlite3
from pathlib import Path

# Resolve project root relative to this file: db/ -> apophenic_memory/ -> src/ -> project/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_OUTPUT_DIR = _PROJECT_ROOT / "output"
_DB_PATH = _OUTPUT_DIR / "apophenic.db"


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


def _force_remove(path: Path) -> None:
    """Remove a single file, ignoring errors (used as rmtree error handler)."""
    try:
        os.remove(path)
    except OSError:
        pass


def wipe_db() -> int:
    """Destructively wipe the entire output directory and re-initialise a fresh database.

    Steps:
    1. Count how many memory rows exist (for the return value).
    2. Explicitly close the SQLite connection so Windows releases the file lock.
    3. Delete the .db file (and WAL/SHM sidecar files) directly with os.remove
       before calling shutil.rmtree on the rest of the output directory — this
       avoids the WinError 32 "file in use" error that rmtree raises on Windows
       when the SQLite file is still locked after close().
    4. Delete any remaining files in output/ with rmtree.
    5. Recreate the empty output/ directory.
    6. Call init_db() so the next request finds a clean, schema-ready database.

    Returns the number of rows that were present before the wipe.
    """
    # 1. Count rows — use an explicit connection so we can call .close() ourselves.
    #    Switch to DELETE journal mode first so SQLite flushes the WAL and removes
    #    the -wal / -shm sidecar files before we close — this is the only reliable
    #    way to ensure the .db file is fully self-contained when we delete it on
    #    Windows (which keeps a file lock until all WAL pages are checkpointed).
    row_count = 0
    if _DB_PATH.exists():
        conn = None
        try:
            conn = _connect()
            conn.execute("PRAGMA journal_mode=DELETE")  # flushes WAL, removes -wal/-shm
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            row_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        except Exception:
            row_count = 0
        finally:
            if conn is not None:
                conn.close()
                conn = None
                gc.collect()  # force CPython to release Windows file handle immediately

    # 2. Delete the db file and its WAL/SHM companions explicitly first.
    #    On Windows, rmtree fails with WinError 32 if the file is still locked,
    #    but os.remove succeeds because SQLite releases the lock on close().
    for db_related in (_DB_PATH,
                       _DB_PATH.with_suffix(".db-wal"),
                       _DB_PATH.with_suffix(".db-shm")):
        if db_related.exists():
            try:
                os.remove(db_related)
            except OSError:
                pass  # best-effort; rmtree will retry below

    # 3. Blow away everything else in the output directory.
    if _OUTPUT_DIR.exists():
        shutil.rmtree(_OUTPUT_DIR, onerror=lambda _fn, path, _exc: _force_remove(Path(path)))

    # 4. Recreate the empty directory.
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 5. Re-initialise a fresh, schema-ready database so the app keeps running.
    init_db()

    return row_count
