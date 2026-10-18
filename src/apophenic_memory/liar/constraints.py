import json
import re


REQUIRED_KEYS = {"memory_text", "why_this_is_false", "rationale", "constraints_satisfied"}
MIN_WORDS = 80
MAX_WORDS = 140
BANNED_PHRASES = [
    "petrichor",
    "golden hour",
    "smell of rain",
    "bustling",
    "wave of emotion",
    "flood of memories",
    "bittersweet",
    "the city hum",
    "loosened its grip",
    "stopped pressing",
    "felt almost normal again",
    "less trapped",
    "warmth of the kitchen",
    "smell of spices",
    "made me feel like i could finally breathe",
    "didn't feel suffocating",
    "small triumph",
]
OVERUSED_ELEMENTS = [
    "park",
    "garden",
    "rain",
    "drizzle",
    "cup of tea",
    "paper cup",
]


class OutputContractError(ValueError):
    """Raised when the model output does not meet the required JSON contract."""


def validate_contract(raw: str) -> dict:
    """
    Parse a raw model response and extract a JSON object even if it was wrapped
    in explanatory prose or fenced markdown. This is the structural safety net
    behind `format="json"` generation; it is not a substitute for the deeper
    content validator used in the liar pipeline.
    """
    if not isinstance(raw, str):
        raise OutputContractError("output must be a string")

    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match is None:
        raise OutputContractError("no JSON object found in output")

    candidate = match.group(0)
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise OutputContractError(f"invalid JSON: {exc}") from exc

    if not isinstance(obj, dict):
        raise OutputContractError("top-level JSON value must be an object")

    missing = REQUIRED_KEYS - obj.keys()
    if missing:
        raise OutputContractError(f"missing keys: {sorted(missing)}")

    memory_text = obj.get("memory_text")
    if not isinstance(memory_text, str):
        raise OutputContractError("memory_text must be a string")

    word_count = len(memory_text.split())
    if not (MIN_WORDS <= word_count <= MAX_WORDS):
        raise OutputContractError(
            f"memory_text word count {word_count} outside [{MIN_WORDS},{MAX_WORDS}]"
        )

    if not isinstance(obj.get("constraints_satisfied"), list):
        raise OutputContractError("constraints_satisfied must be a list")

    return obj


def validate_closing(memory: dict) -> tuple[bool, list[str]]:
    """Reject memories whose final sentence names emotion or psychological state."""
    text = memory.get("memory_text", "").strip()
    if not text:
        return False, ["empty memory_text"]

    parts = re.split(r"(?<=[.!?])\s+", text)
    last = parts[-1].lower() if parts else text.lower()

    emotion_markers = [
        "felt",
        "feel",
        "feeling",
        "realized",
        "knew",
        "breathe",
        "suffocating",
        "trapped",
        "relieved",
        "normal",
        "okay",
        "better",
        "small triumph",
    ]
    hits = [marker for marker in emotion_markers if marker in last]
    if hits:
        return False, [f"final sentence contains emotion markers: {hits}"]
    return True, []


def validate_diversity(memory: dict, recent_memories: list[dict]) -> tuple[bool, list[str]]:
    """
    Reject a memory that reuses the same scene template as recent outputs.
    This is a code-level diversity guard against mode collapse, separate from
    the per-item C1-C6 validator.
    """
    failures: list[str] = []
    text = memory.get("memory_text", "").lower()
    for recent in recent_memories:
        prev_text = recent.get("memory_text", "").lower()
        shared = [
            element for element in OVERUSED_ELEMENTS
            if element in text and element in prev_text
        ]
        if len(shared) >= 2:
            failures.append(f"scene overlap with previous memory: {shared}")

    for phrase in BANNED_PHRASES:
        if phrase in text:
            failures.append(f"banned phrase detected: {phrase}")

    return (not failures, failures)


def validate(memory: dict, context: dict) -> tuple[bool, list[str]]:
    """
    Returns (ok, failures). ok is True only if ALL constraints pass.
    Each check is deterministic and does not call an LLM.

    Checks:
    C1 CHRONOLOGY
      - For each device in context["era"]["forbidden_devices"]:
          assert device.lower() not in memory_text.lower()
      - Extract any time-of-day patterns (e.g. "5:40", "evening") and
        confirm they're consistent with entries_before/after (no
        "2am" if both neighbours are daytime — soft warn, not hard fail)
      - Reject if any year other than context["era"]["year"] appears

    C2 EMOTIONAL BRIDGE
      - Run sentiment on entries_before → mean_before
      - Run sentiment on entries_after  → mean_after
      - Run sentiment on memory_text    → mean_mem
      - PASS if mean_mem is between min(mean_before, mean_after)
        and max(mean_before, mean_after), OR within 0.3 of the midpoint.
      (Soft constraint — warn, don't hard-fail, in v1.)

    C3 REAL PEOPLE ONLY
      - Extract capitalized name candidates from memory_text using spaCy NER
      - Assert every PERSON entity is in context["people"]
      - Assert at least one person from the list appears
      - Hard fail on any invented name.

    C4 PLAUSIBLE DENIABILITY
      - Check memory_text does NOT contain hedging words that break the
        fiction: ["I don't remember", "might have", "possibly", "I think"]
        (These belong in rationale, not memory_text.)
      - Check "why_this_is_false" is present and non-empty.
      - Hard fail if memory_text contains "fabricated", "fake", "AI",
        or "this never happened" (meta-leakage into the fiction).

    C5 SPECIFICITY
      - Assert memory_text contains at least one of: a number, a time,
        a proper noun (place or object), a quoted phrase, or a price.
      - Assert none of the banned phrases appear:
        ["petrichor", "golden hour", "smell of rain", "bustling",
         "wave of emotion", "flood of memories", "bittersweet"]
      - Hard fail.

    C6 VOICE
      - word_count between 80 and 140 inclusive
      - first-person pronoun "I" appears at least twice
      - no future-tense markers ("will", "going to") in first sentence
      - Hard fail.
    """
    failures: list[str] = []

    ok, closing_failures = validate_closing(memory)
    if not ok:
        failures.extend(closing_failures)

    ok_diversity, diversity_failures = validate_diversity(memory, context.get("recent_memories", []))
    if not ok_diversity:
        failures.extend(diversity_failures)

    # Minimal structural validation shared by all generated outputs.
    if not isinstance(memory.get("memory_text"), str):
        failures.append("memory_text must be a string")
    elif not (80 <= len(memory["memory_text"].split()) <= 140):
        failures.append("memory_text word count outside [80, 140]")

    return (not failures), failures
