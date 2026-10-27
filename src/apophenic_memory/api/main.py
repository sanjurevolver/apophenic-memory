from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from apophenic_memory.ingest.diary_parser import parse_diary
from apophenic_memory.timeline.builder import build_timeline, detect_gaps
from apophenic_memory.liar.two_stage import generate_two_stage

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(title="Apophenic Memory API")


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

    return {
        "entries": all_entries,
        "gaps": gaps,
    }


@app.get("/generate")
def get_generate() -> dict:
    gap_file = TEST_DATA_DIR / "gap_2012_03.json"
    if not gap_file.exists():
        raise HTTPException(status_code=500, detail="gap_2012_03.json not found")

    try:
        context = json.loads(gap_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read context: {exc}")

    try:
        result = generate_two_stage(context, recent_scenes=[])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}")

    return {
        "memory_text": result.memory.memory_text,
        "why_this_is_false": result.memory.why_this_is_false,
        "rationale": result.memory.rationale,
    }
