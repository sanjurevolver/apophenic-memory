"""tests/test_api.py

Integration tests for the FastAPI application.
Uses FastAPI's TestClient (backed by httpx) and monkeypatches
`generate_two_stage` so no Ollama instance is needed.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apophenic_memory.liar.schema import ConstraintResult, GenerationResult, Memory


# ---------------------------------------------------------------------------
# Helpers — build a deterministic fake GenerationResult
# ---------------------------------------------------------------------------

FAKE_MEMORY_TEXT = (
    "I waited in the queue outside the tea stall with Friend A after class. "
    "We counted the coins and I slid them across the counter."
)

FAKE_CONSTRAINT_RESULTS = [
    ConstraintResult(constraint_id="C1", passed=True,  message="ok"),
    ConstraintResult(constraint_id="C2", passed=True,  message="ok"),
    ConstraintResult(constraint_id="C2b", passed=True, message="ok"),
    ConstraintResult(constraint_id="C3", passed=True,  message="ok"),
    ConstraintResult(constraint_id="C4", passed=True,  message="ok"),
    ConstraintResult(constraint_id="C5", passed=True,  message="ok"),
    ConstraintResult(constraint_id="C6", passed=True,  message="ok"),
]


def make_fake_generation_result() -> GenerationResult:
    memory = Memory(
        id=str(uuid.uuid4()),
        memory_text=FAKE_MEMORY_TEXT,
        why_this_is_false="This outing never happened.",
        rationale="Bridges the gap from stressed to calm.",
        is_fabricated=True,
        gap_id="gap-2012-03-02-2012-03-26",
        word_count=len(FAKE_MEMORY_TEXT.split()),
        constraint_results=[cr.to_dict() for cr in FAKE_CONSTRAINT_RESULTS],
        generation_status="ok",
    )
    return GenerationResult(memory=memory, attempted_runs=1, failures=[])


# ---------------------------------------------------------------------------
# Fixture — TestClient with mocked DB so tests are hermetic
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """
    Return a TestClient with:
    - generate_two_stage mocked (no Ollama)
    - SQLite database redirected to a temp directory
    - init_db / save_memory / get_memories / wipe_db using the temp db
    """
    import apophenic_memory.db.database as db_mod
    import apophenic_memory.api.main as main_mod

    # Redirect the database to a temp dir so tests are isolated
    monkeypatch.setattr(db_mod, "_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(db_mod, "_DB_PATH", tmp_path / "apophenic.db")

    # Re-initialise the schema in the temp db
    db_mod.init_db()

    # Mock generate_two_stage
    monkeypatch.setattr(
        main_mod, "generate_two_stage",
        lambda *args, **kwargs: make_fake_generation_result(),
    )

    from apophenic_memory.api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /timeline
# ---------------------------------------------------------------------------

class TestGetTimeline:
    def test_returns_200(self, client):
        r = client.get("/timeline")
        assert r.status_code == 200

    def test_response_has_required_keys(self, client):
        r = client.get("/timeline")
        body = r.json()
        assert "entries" in body
        assert "gaps" in body
        assert "saved_memories" in body

    def test_entries_is_a_list(self, client):
        r = client.get("/timeline")
        assert isinstance(r.json()["entries"], list)

    def test_saved_memories_empty_on_fresh_db(self, client):
        r = client.get("/timeline")
        assert r.json()["saved_memories"] == []


# ---------------------------------------------------------------------------
# POST /memories/generate
# ---------------------------------------------------------------------------

class TestPostGenerate:
    def test_returns_200_with_empty_body(self, client):
        r = client.post("/memories/generate", json={})
        assert r.status_code == 200

    def test_returns_200_with_gap_dates(self, client):
        r = client.post(
            "/memories/generate",
            json={"gap_start": "2012-03-02", "gap_end": "2012-03-26"},
        )
        assert r.status_code == 200

    def test_response_contains_memory_text(self, client):
        r = client.post("/memories/generate", json={})
        body = r.json()
        assert body["memory_text"] == FAKE_MEMORY_TEXT

    def test_response_contains_required_fields(self, client):
        r = client.post("/memories/generate", json={})
        body = r.json()
        for key in ("id", "memory_text", "why_this_is_false",
                    "rationale", "gap_start", "gap_end",
                    "generation_status", "constraint_results"):
            assert key in body, f"Missing field: {key}"

    def test_constraint_results_is_list_of_dicts(self, client):
        r = client.post("/memories/generate", json={})
        results = r.json()["constraint_results"]
        assert isinstance(results, list)
        assert len(results) > 0
        for item in results:
            assert "constraint_id" in item
            assert "passed" in item
            assert "message" in item

    def test_generation_status_is_ok(self, client):
        r = client.post("/memories/generate", json={})
        assert r.json()["generation_status"] == "ok"

    def test_memory_is_saved_to_db(self, client):
        client.post("/memories/generate", json={})
        timeline = client.get("/timeline").json()
        assert len(timeline["saved_memories"]) == 1

    def test_successive_generates_accumulate(self, client):
        client.post("/memories/generate", json={})
        client.post("/memories/generate", json={})
        timeline = client.get("/timeline").json()
        assert len(timeline["saved_memories"]) == 2


# ---------------------------------------------------------------------------
# POST /data/wipe
# ---------------------------------------------------------------------------

class TestPostWipe:
    def test_confirm_true_returns_200(self, client):
        r = client.post("/data/wipe", json={"confirm": True})
        assert r.status_code == 200

    def test_confirm_false_returns_400(self, client):
        r = client.post("/data/wipe", json={"confirm": False})
        assert r.status_code == 400

    def test_missing_confirm_field_returns_400(self, client):
        r = client.post("/data/wipe", json={})
        assert r.status_code == 400

    def test_wipe_response_has_expected_keys(self, client):
        r = client.post("/data/wipe", json={"confirm": True})
        body = r.json()
        assert "status" in body
        assert "rows_deleted" in body
        assert "message" in body

    def test_wipe_status_is_wiped(self, client):
        r = client.post("/data/wipe", json={"confirm": True})
        assert r.json()["status"] == "wiped"

    def test_wipe_clears_saved_memories(self, client):
        # First generate a memory
        client.post("/memories/generate", json={})
        assert len(client.get("/timeline").json()["saved_memories"]) == 1

        # Wipe
        client.post("/data/wipe", json={"confirm": True})

        # Memories should be gone
        assert len(client.get("/timeline").json()["saved_memories"]) == 0

    def test_wipe_returns_correct_row_count(self, client):
        client.post("/memories/generate", json={})
        client.post("/memories/generate", json={})
        r = client.post("/data/wipe", json={"confirm": True})
        assert r.json()["rows_deleted"] == 2

    def test_wipe_deletes_database_file_from_disk(self, client):
        import apophenic_memory.db.database as db_mod

        # Ensure a memory was saved so the database file exists on disk
        client.post("/memories/generate", json={})
        assert db_mod._DB_PATH.exists()

        # Perform panic wipe
        r = client.post("/data/wipe", json={"confirm": True})
        assert r.status_code == 200

        # Assert output/apophenic.db no longer exists on disk
        assert not db_mod._DB_PATH.exists()
