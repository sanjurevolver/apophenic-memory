from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from apophenic_memory.ingest.diary_parser import parse_diary
from apophenic_memory.timeline.builder import build_timeline, detect_gaps
from apophenic_memory.liar.two_stage import generate_two_stage
from apophenic_memory.db.database import init_db, save_memory, get_memories, wipe_db

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(title="Apophenic Memory API")


# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Body for POST /memories/generate.

    gap_start and gap_end are optional — if omitted the default gap file is used.
    """
    gap_start: Optional[str] = None
    gap_end: Optional[str] = None


class WipeRequest(BaseModel):
    """Body for POST /data/wipe.

    Must include ``{"confirm": true}`` — any other value returns 400.
    """
    confirm: bool


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup_event() -> None:
    """Initialise the SQLite database on server startup."""
    init_db()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_file = STATIC_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="static/index.html not found")
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/timeline")
def get_timeline() -> dict:
    entries_before_path = TEST_DATA_DIR / "entries_before.md"
    entries_after_path = TEST_DATA_DIR / "entries_after.md"

    if not entries_before_path.exists() or not entries_after_path.exists():
        raise HTTPException(status_code=500, detail="Test diary entry files not found")

    entries_before = parse_diary(entries_before_path)
    entries_after = parse_diary(entries_after_path)
    all_entries = entries_before + entries_after

    timeline = build_timeline(all_entries, [])
    gaps = detect_gaps(timeline)

    # Fetch all persisted memories so the frontend can pre-fill already-generated gaps
    saved = get_memories()

    return {
        "entries": all_entries,
        "gaps": gaps,
        "saved_memories": saved,
    }


@app.post("/memories/generate")
def post_generate(body: GenerateRequest) -> dict:
    """Generate a fabricated memory for a gap.

    Accepts an optional ``gap_start`` / ``gap_end`` pair.  When omitted, falls
    back to the default ``gap_2012_03.json`` test-data file.
    """
    gap_file = TEST_DATA_DIR / "gap_2012_03.json"
    if not gap_file.exists():
        raise HTTPException(status_code=500, detail="gap_2012_03.json not found")

    try:
        context = json.loads(gap_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read context: {exc}")

    # Override gap dates if the caller supplied them
    if body.gap_start or body.gap_end:
        context.setdefault("gap", {})
        if body.gap_start:
            context["gap"]["start_date"] = body.gap_start
        if body.gap_end:
            context["gap"]["end_date"] = body.gap_end

    try:
        result = generate_two_stage(context, recent_scenes=[])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}")

    gap = context.get("gap", {})
    memory_id = str(uuid.uuid4())

    save_memory(
        {
            "id": memory_id,
            "gap_start": gap.get("start_date", ""),
            "gap_end": gap.get("end_date", ""),
            "memory_text": result.memory.memory_text,
            "why_this_is_false": result.memory.why_this_is_false,
            "rationale": result.memory.rationale,
        }
    )

    return {
        "id": memory_id,
        "memory_text": result.memory.memory_text,
        "why_this_is_false": result.memory.why_this_is_false,
        "rationale": result.memory.rationale,
        "gap_start": gap.get("start_date", ""),
        "gap_end": gap.get("end_date", ""),
        "generation_status": result.memory.generation_status,
        "constraint_results": result.memory.constraint_results,
    }


@app.post("/data/wipe")
def post_wipe(body: WipeRequest) -> dict:
    """Wipe all persisted memories.

    Requires ``{"confirm": true}`` in the request body.
    Returns 400 if confirm is False.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Wipe not confirmed. Send {\"confirm\": true} to proceed.",
        )

    rows_deleted = wipe_db()
    return {
        "status": "wiped",
        "rows_deleted": rows_deleted,
        "message": "All data wiped. Please refresh the page.",
    }
