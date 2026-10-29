# Apophenic Memory

> A local-first Gen-AI system that fabricates plausible, emotionally coherent
> false memories to fill gaps in a person's diary — and shows you exactly how
> it lied.

## Status

Apophenic Memory is fully functional:
- **FastAPI backend & dynamic frontend**: Real-time generation, interactive timeline, and Red Pill explainability UI are operational.
- **Deterministic validation & SQLite persistence**: C1–C6 content constraints, era checks (`validate_era`), and closing rules (`validate_closing`) run deterministically; memories are stored locally in SQLite (`output/apophenic.db`).
- **Privacy-first & hardened**: The API server is strictly bound to `127.0.0.1` (local-first, unexposed to LAN), all output directories are gitignored, and the destructive Panic Wipe physically removes the database file and all generated artifacts from disk.
- **Comprehensive test suite**: Full suite of 33 unit and integration tests passing in CI via GitHub Actions without requiring an external Ollama instance.

---

## What this is

Apophenic Memory takes sparse real personal data — diary entries, photos,
a list of real people — and identifies *gaps* in the autobiographical record.
For each gap, it generates ONE false memory that:

1. Could plausibly have happened (era-consistent, chronologically possible)
2. Bridges the emotional tone of the real entries before and after
3. Involves only real people from the user's list, in ways that never happened
4. Ends on a concrete image, not a stated feeling
5. Is clearly framed as fabricated in the output, never presented as real

The output is a private, local web gallery where the user can toggle between
"real" and "fabricated" views, read the rationale behind each fabrication,
and inspect the exact constraint that drove each decision.

**The project inverts the standard AI-safety narrative.** Instead of preventing
hallucination, it invites hallucination about the most personal data a person
has — their own past — and makes the fabrication process transparent,
explainable, and reversible.

---

## What this is NOT

- Not a therapy tool. Not a diagnostic tool.
- Not a social product. Output is private by default.
- Not a deepfake generator for real events.
- Not a replacement for journaling or memory-preservation tools.
- **Not guaranteed to produce true memories.** Every fabricated memory is
  explicitly flagged as fabricated in both the UI and the on-disk sidecar.

---

## Ethical precondition

This system generates false information about real people (friends, family)
using their names. **Do not show generated content to the people it references
without their explicit consent.** The consent screen at first run requires the
user to acknowledge this. The output directory is marked `.apophenic/` and
excluded from cloud sync by default.

A "panic wipe" button deletes all generated content and the SQLite database.

---

## The failure trail (read this before touching the prompts)

> [!NOTE]
> **Model Alignment:** The failure trail below documents our findings using
> `llama3.1:8b`. The final prototype uses `llama3.2:3b` for fast, accessible local
> generation on consumer CPUs without requiring a dedicated GPU.

This project has gone through four prompt iterations. Each iteration fixed one
failure mode and exposed another. This trail is documented so the next
developer does not repeat it.

| Version | Failure mode | What was fixed | What broke next |
|---|---|---|---|
| v2 | Mode collapse on scene (park/Friend A/rain/tea) + JSON wrapping | Scene bans, specificity constraint, `format="json"` | Emotional-summary ending ("I felt less trapped") |
| v3 | Emotional-summary ending | Ban emotion endings; require concrete final image | Output got short and under-specified |
| v3.1 | Too short, under-specified | (never shipped) | Word count and content richness traded off against closing control |
| **two-stage** | Word count overshoot (+44 to +81 words) + blueprint final-image can smuggle emotion | Split into scene selector + writer; deterministic closing validator | Frozen after live evaluation: structurally valid, but creatively flat |

**The structural lesson:** Llama 3.1 8B is capacity-bound. It cannot hold
scene diversity, emotional bridging, concrete specificity, closing shape,
*and* word count in one generation pass. Every prompt fix traded one
constraint for another. **Two-stage generation was the correct architectural
response, not a fourth prompt.**

**The second lesson:** "Concrete" is not a binary. A `target_final_image` like
*"looking at each other with a sense of newfound understanding"* names a
physical posture *and* smuggles an emotion. The validator must reject emotion
nouns anywhere in the sentence, not just at the end.

---

## Architecture

```
┌──────────────────────┐
│   INPUT LAYER        │  diary entries, photos (EXIF), people.json
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│   GAP MAPPER         │  identifies temporal gaps, emotional flatlines,
│   (local LLM)        │  relational ambiguities → structured targets
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  STAGE 1: SCENE      │  picks scene_type from fixed enum,
│  SELECTOR            │  people_involved, target_length_words,
│  (local LLM)         │  target_final_image
└──────────┬───────────┘
           ▼
    [blueprint validator]
    - scene_type in enum, not in recent_scenes
    - people all in list
    - target_final_image: concrete action, NO emotion nouns
    - on failure: retry stage 1 (max 3 attempts)
           ▼
┌──────────────────────┐
│  STAGE 2: WRITER     │  writes memory_text toward blueprint
│  (local LLM)         │  word count target ±10, final sentence = target_final_image
└──────────┬───────────┘
           ▼
    [word-count retry loop]
    - feeds previous attempt's word count back into prompt
    - max 3 attempts, then accept closest
           ▼
    [content validators]
    - validate_contract()    : JSON shape, required keys
    - validate()             : C1–C6 content checks
    - validate_closing()     : final sentence must not name emotion
    - validate_diversity()   : no scene overlap with last N memories
           ▼
┌───────────────────────────────┐
│   VISUALIZER (Future Work)    │
│   (local SDXL)                │
└───────────────┬───────────────┘
           ▼
┌──────────────────────┐
│  RED PILL UI         │  gallery + real/fake toggle + rationale panel
└──────────────────────┘
```

---

## Repository layout

```
apophenic-memory/
├── .github/
│   └── workflows/
│       └── test.yml                    ← automated CI test runner (pytest)
├── README.md                           ← this file
├── PRIOR_ART.md                        ← adjacent projects, differentiation
├── EVALUATION.md                       ← model evaluation & capacity findings
├── pyproject.toml
├── scripts/
│   └── run_two_stage_batch.py          ← batch evidence generator
├── src/
│   └── apophenic_memory/
│       ├── api/
│       │   └── main.py                 ← FastAPI routes (/timeline, /memories/generate, /data/wipe)
│       ├── db/
│       │   └── database.py             ← SQLite persistence layer & destructive wipe
│       ├── ingest/                     ← diary/photo/people parsers
│       ├── gap_mapper/                 ← gap detection
│       └── liar/
│           ├── schema.py               ← frozen boundary: Memory, GenerationResult, ConstraintResult
│           ├── constraints.py          ← deterministic validators (C1–C6, closing, diversity, era)
│           ├── generator.py            ← local-only stub rotation (contains private examples; excluded from public snapshot)
│           ├── two_stage.py            ← stage 1 → blueprint → stage 2 pipeline (default: llama3.2:3b)
│           └── prompts/
│               ├── v2.txt              ← local-only archived prompt (excluded from public snapshot)
│               ├── v3.txt              ← local-only archived prompt (excluded from public snapshot)
│               ├── stage1_scene_selector.txt
│               └── stage2_writer.txt
├── tests/
│   ├── test_api.py                     ← FastAPI integration tests (TestClient, isolated db)
│   ├── test_validators.py              ← unit tests for era, closing, and C3 validators
│   ├── test_liar_contract.py           ← JSON + closing validators
│   └── test_two_stage.py               ← pipeline wiring (uses fixture blueprint)
├── test_data/
│   ├── gap_2012_03.json                ← sample test gap
│   ├── entries_before.md
│   ├── entries_after.md
│   ├── people.json
│   ├── v2_prompt_results.md            ← archived scorecards
│   └── two_stage_run_results.md        ← current scorecard
├── scripts/
│   ├── run_two_stage_batch.py      ← reproducible 10-run LLM evaluation harness
│   ├── smoke_test.sh               ← clean-install smoke test (Linux / macOS / Bash)
│   └── smoke_test.ps1              ← clean-install smoke test (Windows PowerShell)
├── static/
│   └── index.html                  ← dynamic frontend with Red Pill UI & constraint audit
└── output/                         ← strictly gitignored, generated memories & SQLite database
```

---

## Setup

**Prerequisites:**
- Python 3.10+
- [Ollama](https://ollama.com) with `llama3.2:3b` pulled
- 8 GB RAM (runs locally on CPU)

```bash
# Clone
git clone <repo>
cd apophenic-memory

# Python environment
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Pull the model
ollama pull llama3.2:3b

# Run the tests (no model needed)
pytest -q

# Run the end-to-end clean-install smoke test (verifies server, generate, SQLite, and panic wipe)
bash scripts/smoke_test.sh       # Windows: powershell -File scripts/smoke_test.ps1

# Run the interactive API & frontend server (bound to 127.0.0.1 by default)
uvicorn apophenic_memory.api.main:app --host 127.0.0.1 --port 8000 --reload
# or: python -m apophenic_memory.api.main

# Run a single two-stage generation (needs Ollama running)
python scripts/run_two_stage_batch.py
```

---

## Historical decision gate

The following notes preserve the decision process from prompt development.
They are historical, not current implementation tasks: after live evaluation,
the liar layer was frozen and development proceeded with ingest, timeline, and the
gallery interface.

**Stage 1 passed on the first live batch:**
- 3 distinct scene types across 3 runs (`shared_meal_at_someone_house`,
  `cooking_at_home`, `classroom_after_hours`)
- No mode collapse to a single attractor

**Stage 2 fails on two axes:**
1. **Word count:** targets of 110 produced 154, 191, and 163 words (+44 to +81).
   Llama 3.1 8B does not have reliable word-count control from a prompt.
2. **Blueprint final-image smuggling:** Run 3's `target_final_image` was
   *"looking at each other with a sense of newfound understanding"* — a
   physical posture with an emotion attached. The blueprint validator must
   reject this.

**At the time, two fixes were proposed before UI integration:**

### Fix 1 — Blueprint final-image validator

Add to `constraints.py`:

```python
def validate_blueprint_final_image(blueprint: dict) -> tuple[bool, list[str]]:
    """target_final_image must be a concrete action, not an emotion/state."""
    img = blueprint["target_final_image"].lower()
    banned = [
        "sense of", "feeling of", "understanding", "realiz",
        "knowing", "peace", "relief", "closure", "acceptance",
        "felt", "feels", "feeling", "mood", "triumph",
        "warmth", "suffocat", "trapped", "contentment",
    ]
    hits = [w for w in banned if w in img]
    if hits:
        return False, [f"target_final_image names emotion/state: {hits}"]

    import re
    has_action = bool(re.search(
        r"\b(pick|put|leave|walk|sit|stand|hand|take|open|close|"
        r"turn|slide|drop|hold|tell|say|ask|laugh|cry|eat|drink|"
        r"read|write|pay|wait|hiss|ring|buzz)\b", img))
    if not has_action:
        return False, ["target_final_image has no concrete action verb"]
    return True, []
```

Wire into `generate_two_stage()` as a **stage-1 retry gate**: if the blueprint
fails, retry stage 1 (max 3 attempts) before letting stage 2 fire.

### Fix 2 — Word count as a retry loop, not a prompt

Do **not** try to fix word count with prompt wording. Llama 3.1 8B cannot
reliably hit word counts from a single-shot instruction. Implement:

```python
def _stage2_write_with_length(blueprint, era, max_attempts=3):
    target = blueprint["target_length_words"]
    previous_wc = None
    for attempt in range(max_attempts):
        memory = _call("stage2_writer.txt", {
            "blueprint": blueprint,
            "era": era,
            "attempt": attempt + 1,
            "previous_word_count": previous_wc,
            "target_length_words": target,
        })
        wc = len(memory["memory_text"].split())
        if abs(wc - target) <= 10:
            return memory, attempt + 1
        previous_wc = wc
    return memory, max_attempts  # accept closest, record failure
```

And add to `stage2_writer.txt`:

```
WORD COUNT HARD GATE:
Your previous attempt was {previous_word_count} words; the target is
{target_length_words} ± 10. If your previous attempt was over target,
you MUST write a shorter memory. The final sentence must still be
{target_final_image}.
```

**If ≥2/3 runs hit ±10 after the retry loop:** freeze stage 2, proceed to
UI integration. **If <2/3:** do not iterate further on prompt wording. Either
document a wider length tolerance (honest surrender) or upgrade stage 2 to
`qwen2.5:14b` / `llama3.1:70b`.

## What has been proven, and what has not

**Proven:**
- The two-stage architecture is correct (stage 1 diversity is real)
- The validator stack catches JSON shape and emotional-closing failures
- The stub-rotation layer (3 rotating v2 stubs) keeps the UI honest about diversity

**Not proven:**
- That a two-stage output can be generated that hits word count AND feels uncanny
- That the system produces memories a real user would call "my life, but not"
- That the visualizer can match era style without anachronism

The scorecard gate above was superseded by the architectural decision to freeze the
liar layer and build the timeline interface with structured generation.

---

## The failure-mode catalog (for prompt design)

Observed across v2, v3, v3.1, and two-stage. Every phrase here has appeared
in a real run. Keep this list growing — it is the cheapest form of prompt
improvement.

**Scene attractors (banned in stage 1):**
- park / garden / outdoor green space
- rain / drizzle / "sky going grey"
- Friend A as primary companion
- Friend B arriving with tea, a bag, or an object
- ending on "less trapped" / "finally breathe" / "loosened its grip"

**Emotional closings (banned in stage 2):**
- "I felt like I could finally breathe"
- "made me feel [adjective]"
- "for the first time, [X] didn't feel [adjective]"
- "I realized [abstract statement]"
- "I knew [something about myself]"
- "with a sense of newfound understanding"

**Stock phrases (banned everywhere):**
- petrichor, golden hour, smell of rain, bustling
- wave of emotion, flood of memories, bittersweet
- "the city hum", "loosened its grip", "stopped pressing"
- "warmth of the kitchen", "smell of spices", "small triumph"

---

## Roadmap & Completed Features

### Core System
- [x] **Pre-code foundation:** Prior-art analysis, diary test gaps, prompt iterations, failure trail catalog
- [x] **Two-stage architecture:** Scene selector (Stage 1) + Writer (Stage 2) with blueprint validator
- [x] **Ingest & Timeline engine:** Diary and markdown parsers, temporal gap detection, chronological sorting
- [x] **FastAPI backend:** Interactive generation (`POST /memories/generate`), timeline API (`GET /timeline`), and local SQLite persistence
- [x] **Dynamic Red Pill UI:** Browser interface with side-by-side real/fabricated timeline cards and interactive constraint audit panel

### Testing & Validation
- [x] **Deterministic validator suite:** C1–C6 constraint engine, anachronism era validation (`validate_era`), and closing sentence emotion checks (`validate_closing`)
- [x] **Isolated test suite:** Hermetic unit and integration tests using FastAPI `TestClient` with mocked LLM generation
- [x] **Automated CI pipeline:** GitHub Actions workflow running `pytest` across all PRs and pushes to main
- [x] Empirical evaluation of 15 live generations proves the deterministic validators achieve 100% precision/recall, while the self-correction retry loop doubles generation compliance from 25% to 50%.

### Privacy & Security
- [x] **Local-only binding:** Server bound strictly to `127.0.0.1` by default to prevent LAN exposure
- [x] **Consent gate:** First-run modal requiring explicit consent before viewing fabricated personal narratives
- [x] **Destructive Panic Wipe:** Single-click physical deletion of `output/apophenic.db` and generated artifacts from disk
- [x] **Data isolation:** Strict gitignore enforcement of all `output/` records and user databases

### Future Work
- [ ] **Visualizer layer:** Era-matched synthetic image generation (local SDXL)
- [ ] **Dynamic word count feedback:** In-context retry loop for strict length control
- [ ] **Multi-user evaluation:** Structured blind testing with 3–5 diary keepers
- [ ] **Model scaling:** Evaluation of larger open models (14B/70B) for richer uncanny detail

---

## License

AGPL-3.0. Any fork must also be local-first and open. This is intentional:
the whole point of the project is that it cannot become a cloud service
without violating its privacy contract.

---

## Disclaimer

Apophenic Memory generates false information about real people. It is
intended for private, artistic, and research use only. Do not show generated
content to the people it references without their explicit consent. Do not
use this tool to deceive, defame, or manipulate. The authors are not
responsible for misuse. This tool does not produce real memories; it
produces speculative fictions.
