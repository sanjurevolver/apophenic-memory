from __future__ import annotations

import json
import re

from apophenic_memory.liar.schema import ConstraintResult


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

# Hedging / meta-leakage phrases that break the fiction (C4)
_C4_HEDGES = ["i don't remember", "might have", "possibly", "i think"]
_C4_META = [
    "fabricated",
    "false memory",
    "as an ai",
    "language model",
    "in this simulation",
    "fake",
    "this never happened",
]
_C4_AI_REGEX = re.compile(r"\bai\b|\ba\.i\.(?!\w)", re.IGNORECASE)

# C3: Common title words and grammar exempt from person checking
_COMMON_TITLE_WORDS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "the", "it", "he", "she", "they", "we", "i", "you", "my", "our", "your",
    "his", "her", "their", "there", "here", "this", "that", "these", "those",
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "and", "but", "or", "so", "for", "yet", "nor", "in", "on", "at", "to",
    "from", "by", "with", "about", "after", "before", "during", "without",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "first", "second", "third", "fourth", "fifth",
    "hometown", "meanwhile", "suddenly", "finally", "instead", "yesterday",
    "today", "tomorrow", "tonight", "morning", "afternoon", "evening", "night",
    "noon", "midnight", "walking", "looking", "standing", "sitting", "waiting",
    "listening", "watching", "remembering", "thinking", "feeling", "coming", "going",
    "leaving", "arriving", "turning", "reaching", "holding", "carrying", "opening",
    "closing", "crossing", "stepping", "stopping", "starting",
    "street", "road", "avenue", "lane", "station", "market", "campus", "library",
    "hall", "room", "floor", "building", "gate", "block", "house", "shop", "stall",
    "corner", "center", "centre", "bridge", "park", "garden", "lake", "river",
    "hostel", "canteen", "cafe", "coffee", "tea", "hotel", "city", "town", "college",
    "university", "school", "class", "classroom", "kitchen", "bus", "train", "taxi",
}

_COMMON_PERSON_NAMES = {
    "john", "priya", "suresh", "ramesh", "rahul", "amit", "anita", "david", "michael",
    "sarah", "emily", "mohammed", "ali", "kumar", "singh", "sharma", "patel", "gupta",
    "neha", "pooja", "deepak", "vikram", "raj", "arun", "kavita", "sunita", "meera",
    "maya", "rohan", "alex", "chris", "sam", "emma", "daniel", "james", "mary",
}

_PERSON_PRE_MARKERS = {
    "with", "and", "told", "asked", "said", "called", "met", "saw", "beside",
    "to", "from", "by", "hugged", "followed", "watched", "accompanied",
}
_PERSON_POST_MARKERS = {
    "said", "told", "asked", "and", "looked", "smiled", "walked", "stood", "sat",
    "came", "held", "called",
}


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


# ---------------------------------------------------------------------------
# Individual validators — all return list[ConstraintResult]
# ---------------------------------------------------------------------------

def validate_closing(memory: dict) -> list[ConstraintResult]:
    """C_CLOSING: final sentence must not name an emotional/psychological state."""
    text = memory.get("memory_text", "").strip()
    if not text:
        return [ConstraintResult(
            constraint_id="C_CLOSING",
            passed=False,
            message="memory_text is empty",
        )]

    parts = re.split(r"(?<=[.!?])\s+", text)
    last = parts[-1].lower() if parts else text.lower()

    emotion_markers = [
        "felt", "feel", "feeling", "realized", "knew",
        "breathe", "suffocating", "trapped", "relieved",
        "normal", "okay", "better", "small triumph",
    ]
    hits = [m for m in emotion_markers if m in last]
    if hits:
        return [ConstraintResult(
            constraint_id="C_CLOSING",
            passed=False,
            message=f"final sentence contains emotion markers: {hits}",
        )]
    return [ConstraintResult(
        constraint_id="C_CLOSING",
        passed=True,
        message="final sentence is observational",
    )]


def validate_diversity(memory: dict, recent_memories: list[dict]) -> list[ConstraintResult]:
    """C_DIVERSITY: no scene-element overlap with recent memories; no banned phrases."""
    results: list[ConstraintResult] = []
    text = memory.get("memory_text", "").lower()

    for recent in recent_memories:
        prev_text = recent.get("memory_text", "").lower()
        shared = [el for el in OVERUSED_ELEMENTS if el in text and el in prev_text]
        if len(shared) >= 2:
            results.append(ConstraintResult(
                constraint_id="C_DIVERSITY",
                passed=False,
                message=f"scene overlap with previous memory: {shared}",
            ))

    for phrase in BANNED_PHRASES:
        if phrase in text:
            results.append(ConstraintResult(
                constraint_id="C_DIVERSITY",
                passed=False,
                message=f"banned phrase detected: '{phrase}'",
            ))

    if not results:
        results.append(ConstraintResult(
            constraint_id="C_DIVERSITY",
            passed=True,
            message="no banned phrases or scene overlap detected",
        ))
    return results


def validate_era(memory: dict, context: dict) -> list[ConstraintResult]:
    """C_ERA: no year other than the target era year may appear in memory_text."""
    era_info = context.get("era", {})
    if isinstance(era_info, dict):
        target_year = era_info.get("year", context.get("year"))
    else:
        target_year = context.get("year")

    if target_year is None:
        return [ConstraintResult(
            constraint_id="C_ERA",
            passed=True,
            message="no target year configured — skipped",
        )]

    text = memory.get("memory_text", "")
    if not isinstance(text, str):
        return [ConstraintResult(
            constraint_id="C_ERA",
            passed=False,
            message="memory_text must be a string",
        )]

    full_matches = [m.group(0) for m in re.finditer(r"\b(?:19|20)\d{2}\b", text)]
    bad = [yr for yr in full_matches if str(yr) != str(target_year)]
    if bad:
        return [ConstraintResult(
            constraint_id="C_ERA",
            passed=False,
            message=f"anachronism: found year(s) {bad}, expected {target_year}",
        )]
    return [ConstraintResult(
        constraint_id="C_ERA",
        passed=True,
        message=f"era {target_year} confirmed — no anachronisms",
    )]


def validate(memory: dict, context: dict) -> list[ConstraintResult]:
    """
    Run all content validators and return a flat list of ConstraintResult objects.

    Checks performed:
      C1  CHRONOLOGY — forbidden devices; era year (delegates to validate_era)
      C2  EMOTIONAL BRIDGE — word-count proxy (sentiment lib not available)
      C3  REAL PEOPLE ONLY — no invented proper names beyond the people list
      C4  PLAUSIBLE DENIABILITY — no hedge / meta-leakage phrases
      C5  SPECIFICITY — at least one anchor; no banned phrases (via validate_diversity)
      C6  VOICE — word count, first-person pronoun, no future tense in opener
      C_CLOSING — final sentence observational
      C_DIVERSITY — no scene overlap / banned phrases
    """
    results: list[ConstraintResult] = []
    text = memory.get("memory_text", "") or ""
    text_lower = text.lower()

    # ---- C1: CHRONOLOGY — forbidden devices --------------------------------
    era_info = context.get("era", {}) if isinstance(context.get("era"), dict) else {}
    forbidden = [d.lower() for d in context.get("forbidden_devices", [])]
    forbidden += [d.lower() for d in era_info.get("forbidden_devices", [])]
    found_devices = [d for d in forbidden if d in text_lower]
    results.append(ConstraintResult(
        constraint_id="C1",
        passed=not found_devices,
        message=(
            f"forbidden device(s) mentioned: {found_devices}" if found_devices
            else "no forbidden devices detected"
        ),
    ))

    # ---- C2: VOICE (word count proxy for emotional bridge) -----------------
    wc = len(text.split())
    results.append(ConstraintResult(
        constraint_id="C2",
        passed=(MIN_WORDS <= wc <= MAX_WORDS),
        message=(
            f"word count {wc} is within [{MIN_WORDS},{MAX_WORDS}]"
            if MIN_WORDS <= wc <= MAX_WORDS
            else f"word count {wc} outside [{MIN_WORDS},{MAX_WORDS}]"
        ),
    ))

    # ---- C3: REAL PEOPLE ONLY ----------------------------------------------
    allowed_names = set()
    for p in context.get("people", []):
        if isinstance(p, dict) and "name" in p:
            n = str(p["name"]).strip().lower()
            if n:
                allowed_names.add(n)
                for part in n.split():
                    if len(part) > 1:
                        allowed_names.add(part)
        elif isinstance(p, str):
            n = p.strip().lower()
            if n:
                allowed_names.add(n)
                for part in n.split():
                    if len(part) > 1:
                        allowed_names.add(part)

    era_info = context.get("era", {}) if isinstance(context.get("era"), dict) else {}
    exempt_texts = [
        str(context.get("city", "")),
        str(context.get("country", "")),
        str(era_info.get("city", "")),
        str(era_info.get("country", "")),
        str(context.get("setting", "")),
        str(context.get("target_final_image", "")),
        str(memory.get("target_final_image", "")),
    ]
    if isinstance(context.get("blueprint"), dict):
        bp = context["blueprint"]
        exempt_texts.extend([
            str(bp.get("setting", "")),
            str(bp.get("target_final_image", "")),
            str(bp.get("scene_type", "")),
        ])

    context_words = set()
    for txt in exempt_texts:
        for w in re.findall(r"\b[A-Za-z]+\b", txt):
            context_words.add(w.lower())

    obvious_persons = []
    borderline = []

    for m in re.finditer(r"\b([A-Z][a-z]+)\b", text):
        word = m.group(1)
        w_lower = word.lower()
        if w_lower in allowed_names or w_lower in context_words:
            continue

        preceding = text[:m.start()].rstrip()
        is_sentence_start = not preceding or bool(re.search(r"[.!?\n]['\"]?\s*$", preceding))

        if w_lower in _COMMON_TITLE_WORDS:
            continue

        # Check person context around word
        pre_tokens = [re.sub(r"[^a-z]", "", t.lower()) for t in text[:m.start()].split()[-2:]]
        post_tokens = [re.sub(r"[^a-z]", "", t.lower()) for t in text[m.end():].split()[:2]]

        is_pre_marked = any(t in _PERSON_PRE_MARKERS for t in pre_tokens)
        is_post_marked = any(t in _PERSON_POST_MARKERS for t in post_tokens)
        is_known_name = w_lower in _COMMON_PERSON_NAMES

        if is_known_name or is_pre_marked or is_post_marked:
            obvious_persons.append(word)
        elif not is_sentence_start:
            borderline.append(word)

    if obvious_persons:
        c3_passed = False
        c3_msg = f"possible invented name(s): {obvious_persons[:5]}"
    elif borderline:
        c3_passed = True
        c3_msg = f"warning: potential entity or location: {borderline[:5]}"
    else:
        c3_passed = True
        c3_msg = "no unapproved proper names detected"

    results.append(ConstraintResult(
        constraint_id="C3",
        passed=c3_passed,
        message=c3_msg,
    ))

    # ---- C4: PLAUSIBLE DENIABILITY -----------------------------------------
    hedge_hits = [h for h in _C4_HEDGES if h in text_lower]
    meta_hits = [m for m in _C4_META if m in text_lower]
    ai_hits = [m.group(0) for m in _C4_AI_REGEX.finditer(text)]
    c4_fails = hedge_hits + meta_hits + ai_hits
    results.append(ConstraintResult(
        constraint_id="C4",
        passed=not c4_fails,
        message=(
            f"hedging/meta-leakage phrases: {c4_fails}" if c4_fails
            else "no hedging or meta-leakage phrases detected"
        ),
    ))

    # ---- C5: SPECIFICITY ---------------------------------------------------
    has_number = bool(re.search(r"\b\d+\b", text))
    has_time = bool(re.search(r"\b\d{1,2}:\d{2}\b|\b(morning|afternoon|evening|noon|midnight)\b", text_lower))
    has_quote = '"' in text or "'" in text
    c5_passed = has_number or has_time or has_quote
    results.append(ConstraintResult(
        constraint_id="C5",
        passed=c5_passed,
        message=(
            "at least one specific anchor found (number / time / quote)"
            if c5_passed
            else "no specific anchor (number, time, or quoted phrase) found"
        ),
    ))

    # ---- C6: VOICE ---------------------------------------------------------
    first_person_count = len(re.findall(r"\bI\b", text))
    first_sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0].lower() if text else ""
    future_tense = bool(re.search(r"\bwill\b|\bgoing to\b", first_sentence))
    c6_ok = first_person_count >= 2 and not future_tense
    c6_msg_parts = []
    if first_person_count < 2:
        c6_msg_parts.append(f"'I' appears only {first_person_count} time(s) (need ≥2)")
    if future_tense:
        c6_msg_parts.append("future tense in opening sentence")
    results.append(ConstraintResult(
        constraint_id="C6",
        passed=c6_ok,
        message=("; ".join(c6_msg_parts) if c6_msg_parts else "first-person voice confirmed"),
    ))

    # ---- delegate to specialised validators --------------------------------
    results.extend(validate_closing(memory))
    results.extend(validate_diversity(memory, context.get("recent_memories", [])))
    results.extend(validate_era(memory, context))

    return results
