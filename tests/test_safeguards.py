"""tests/test_safeguards.py

Automated tests for user-facing safety controls, end-to-end safeguards,
and persistence recovery:
1. Static UI Safeguards:
   - Permanent "FABRICATED MEMORY" badge in template.
   - Distinctive warning styling for the badge in CSS.
   - Speculative fiction disclaimer in the footer.
   - Permanent visibility: badge is in card header, outside Red Pill reveal panel.
2. Panic Wipe:
   - Complete file deletion from disk.
   - Idempotency and error handling (requires confirm=True).
   - Deletion of records and sidecars.
3. Database Auto-Reinitialization:
   - Seamless re-creation of schema upon next write/read operation.
"""
from pathlib import Path
import re
import pytest
from fastapi import HTTPException

import apophenic_memory.db.database as db_mod
from apophenic_memory.api.main import WipeRequest, post_wipe, get_timeline
from apophenic_memory.db.database import save_memory, get_memories, wipe_db, init_db


class TestStaticUISafeguards:
    @property
    def html_content(self) -> str:
        html_path = Path(__file__).resolve().parent.parent / "static" / "index.html"
        assert html_path.exists(), f"static/index.html not found at {html_path}"
        return html_path.read_text(encoding="utf-8")

    def test_fabricated_memory_badge_present_in_html(self):
        html = self.html_content
        assert "FABRICATED MEMORY" in html
        assert 'class="badge fabricated-badge"' in html

    def test_fabricated_badge_distinct_styling_in_css(self):
        html = self.html_content
        assert ".badge.fabricated-badge" in html
        assert "#ef4444" in html or "#f87171" in html
        assert "box-shadow" in html

    def test_footer_disclaimer_present(self):
        html = self.html_content
        assert "footer-disclaimer" in html
        assert "All generated memories are speculative fictions. Do not present them as real events." in html

    def test_badge_is_outside_reveal_panel(self):
        html = self.html_content
        # In replaceWithFabricatedMemory, the header with FABRICATED MEMORY is created first
        # and appended directly to gapCard before any reveal panel or toggle is constructed.
        header_snippet = '<span class="badge fabricated-badge">FABRICATED MEMORY</span>'
        idx_badge = html.find(header_snippet)
        assert idx_badge != -1

        # Red Pill toggle is appended subsequently
        idx_toggle = html.find("pillLabel.textContent = 'Red Pill'", idx_badge)
        assert idx_toggle > idx_badge, "Badge must be rendered independently in header before toggle"


class TestPanicWipeAndAutoReinitialization:
    @pytest.fixture(autouse=True)
    def setup_temp_db(self, tmp_path, monkeypatch):
        test_db = tmp_path / "test_apophenic.db"
        monkeypatch.setattr(db_mod, "_OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(db_mod, "_DB_PATH", test_db)
        init_db()
        yield
        wipe_db()

    def test_panic_wipe_requires_confirmation(self):
        with pytest.raises(HTTPException) as excinfo:
            post_wipe(WipeRequest(confirm=False))
        assert excinfo.value.status_code == 400
        assert '{"confirm": true}' in excinfo.value.detail

    def test_panic_wipe_deletes_file_and_clears_records(self):
        # Insert 2 test memories
        save_memory({
            "id": "mem-1",
            "gap_start": "2012-03-02",
            "gap_end": "2012-03-26",
            "memory_text": "First test fabricated memory.",
            "why_this_is_false": "Synthetic record 1",
            "rationale": "Test bridge 1",
        })
        save_memory({
            "id": "mem-2",
            "gap_start": "2012-04-01",
            "gap_end": "2012-04-15",
            "memory_text": "Second test fabricated memory.",
            "why_this_is_false": "Synthetic record 2",
            "rationale": "Test bridge 2",
        })

        assert db_mod._DB_PATH.exists()
        assert len(get_memories()) == 2

        # Trigger Panic Wipe
        res = post_wipe(WipeRequest(confirm=True))
        assert res["status"] == "wiped"
        assert res["rows_deleted"] == 2

        # File must be deleted from disk
        assert not db_mod._DB_PATH.exists()
        assert get_memories() == []

    def test_auto_reinitialization_after_wipe(self):
        # Insert and wipe
        save_memory({
            "id": "mem-1",
            "gap_start": "2012-03-02",
            "gap_end": "2012-03-26",
            "memory_text": "Sample memory.",
            "why_this_is_false": "Synthetic",
            "rationale": "Test",
        })
        post_wipe(WipeRequest(confirm=True))
        assert not db_mod._DB_PATH.exists()

        # Database re-initializes on new save
        save_memory({
            "id": "mem-new",
            "gap_start": "2012-05-01",
            "gap_end": "2012-05-10",
            "memory_text": "Post-wipe recreated memory.",
            "why_this_is_false": "Synthetic post-wipe",
            "rationale": "Post-wipe recovery test",
        })
        assert db_mod._DB_PATH.exists()
        memories = get_memories()
        assert len(memories) == 1
        assert memories[0]["id"] == "mem-new"

    def test_timeline_reads_cleanly_after_wipe(self):
        # Wipe database
        wipe_db()
        assert not db_mod._DB_PATH.exists()

        # get_timeline should return 200 equivalent without error
        timeline = get_timeline()
        assert "entries" in timeline
        assert "gaps" in timeline
        assert timeline["saved_memories"] == []
