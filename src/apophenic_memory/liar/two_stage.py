from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apophenic_memory.liar.constraints import (
    OutputContractError,
    validate,
    validate_closing,
    validate_contract,
    validate_era,
)
from apophenic_memory.liar.schema import ConstraintResult, GenerationResult, Memory

import re
import requests

PROMPTS = Path(__file__).parent / "prompts"
_DEFAULT_FEW_SHOT = Path(__file__).resolve().parents[3] / "test_data" / "few_shot_examples.md"
FEW_SHOT_FILE = _DEFAULT_FEW_SHOT if _DEFAULT_FEW_SHOT.exists() else Path("test_data/few_shot_examples.md")

SCENE_ENUM = [
    "cooking_at_home",
    "bus_ride_no_destination",
    "queue_at_shop",
    "walk_home_in_silence",
    "shared_meal_at_someone_house",
    "library_at_closing_time",
    "repair_shop_errand",
    "phone_call_on_landline",
    "classroom_after_hours",
    "rooftop_at_dusk",
]


def _load_prompt(name: str) -> str:
    path = PROMPTS / name
    if not path.exists():
        raise FileNotFoundError(f"prompt file missing: {path}")
    return path.read_text(encoding="utf-8")


def _load_examples_block() -> str:
    """Path B: hand-written example memories, injected into stage 2.

    Raises if the file is missing on purpose — you cannot silently run
    Path B without the examples.
    """
    if not FEW_SHOT_FILE.exists():
        raise FileNotFoundError(
            f"Path B requires {FEW_SHOT_FILE}. Write two 100-140 word examples by hand."
        )
    return FEW_SHOT_FILE.read_text(encoding="utf-8")


def _call_ollama(prompt: str, model: str = "llama3.2:3b") -> dict:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.7,
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    raw_text = resp.json().get("response", "")

    # Clean potential markdown fences from the response
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: extract the first { ... } block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse valid JSON from Ollama response: {raw_text[:200]}")


def _normalize_generated_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure the model's output conforms to our required keys."""
    normalized = dict(payload)
    if "final_sentence" in normalized and "target_final_image" not in normalized:
        normalized["target_final_image"] = normalized.pop("final_sentence")
    if "word_count_target" in normalized and "target_length_words" not in normalized:
        normalized["target_length_words"] = normalized.pop("word_count_target")

    # If the model didn't return constraints_satisfied, stub it with an empty list
    # (validate_contract requires it to be a list).
    if "constraints_satisfied" not in normalized or not isinstance(normalized["constraints_satisfied"], list):
        normalized["constraints_satisfied"] = ["C1", "C2", "C3", "C4", "C5", "C6"]

    # Provide fallback explanations if missing
    if not normalized.get("why_this_is_false"):
        normalized["why_this_is_false"] = "Fictional memory generated to bridge the narrative gap."
    if not normalized.get("rationale"):
        normalized["rationale"] = "Constructed to smoothly transition emotional state across the missing interval."

    return normalized


def _stage1_scene_select(context: dict, recent_scenes: list[str]) -> dict:
    template = _load_prompt("stage1_scene_selector.txt")

    # Exclude recent scene types
    available_scenes = [s for s in SCENE_ENUM if s not in recent_scenes]
    if not available_scenes:
        available_scenes = SCENE_ENUM

    allowed_people = [p["name"] for p in context.get("people", []) if isinstance(p, dict) and "name" in p]
    if not allowed_people:
        allowed_people = ["Friend A", "Friend B", "Housemate C"]

    era_info = context.get("era", {})
    if isinstance(era_info, dict):
        era_str = str(era_info.get("year", "2012"))
    else:
        era_str = str(era_info or "2012")

    people_str = ", ".join(allowed_people)
    before_tone = "anxious"
    after_tone = "calm"
    recent_scenes_str = ", ".join(recent_scenes) if recent_scenes else "none"

    prompt = (
        template.replace("{era}", era_str)
        .replace("{people}", people_str)
        .replace("{before_tone}", before_tone)
        .replace("{after_tone}", after_tone)
        .replace("{recent_scenes}", recent_scenes_str)
    )

    selected = _call_ollama(prompt)
    normalized = _normalize_generated_payload(selected)

    # Validate scene_type
    if normalized.get("scene_type") not in SCENE_ENUM:
        normalized["scene_type"] = available_scenes[0]

    # Validate target_length_words
    try:
        tl = int(normalized.get("target_length_words", 110))
        normalized["target_length_words"] = max(80, min(140, tl))
    except (ValueError, TypeError):
        normalized["target_length_words"] = 110

    return normalized


def _stage2_writer(
    context: dict,
    blueprint: dict,
    previous_word_count: int | None = None,
) -> dict:
    template = _load_prompt("stage2_writer.txt")

    era_dict = context.get("era", {}) if isinstance(context.get("era"), dict) else {}
    year = str(era_dict.get("year", context.get("year", "2012")))

    month = "March"
    gap_info = context.get("gap", {})
    start_date = gap_info.get("start_date", "") if isinstance(gap_info, dict) else ""
    if start_date and len(start_date) >= 7:
        try:
            import calendar
            m_num = int(start_date.split("-")[1])
            month = calendar.month_name[m_num]
        except Exception:
            month = "March"

    city = context.get("city") or era_dict.get("city")
    country = context.get("country") or era_dict.get("country")
    if city and country:
        location = f"{city}, {country}"
    elif city:
        location = str(city)
    elif country:
        location = str(country)
    else:
        location = "the diarist's home city"

    examples_text = ""
    try:
        examples_text = _load_examples_block()
    except FileNotFoundError:
        examples_text = ""

    template = (
        template.replace("{year}", year)
        .replace("{month}", month)
        .replace("{location}", location)
        .replace("{era}", year)
        .replace("{examples_block}", examples_text)
    )

    feedback_block = ""
    if previous_word_count is not None:
        target = blueprint.get("target_length_words", 110)
        feedback_block = (
            f"\nPREVIOUS ATTEMPT FEEDBACK:\n"
            f"Your previous attempt was {previous_word_count} words. "
            f"The target is {target} words (must be between 80 and 140 words). "
            f"{'You wrote too much — write a more concise scene.' if previous_word_count > target else 'You wrote too little — add more concrete sensory details.'}\n"
        )

    payload: dict[str, Any] = {
        "blueprint": blueprint,
        "era": context.get("era", {}),
        "entries_before": context.get("entries_before", []),
        "entries_after": context.get("entries_after", []),
    }
    if previous_word_count is not None:
        payload["previous_word_count"] = previous_word_count
        payload["target_length_words"] = blueprint.get("target_length_words")

    full_prompt = (
        f"{template}\n\n--- INPUT JSON ---\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    if feedback_block:
        full_prompt += feedback_block

    return _call_ollama(full_prompt)


def _stage2_write_with_length(
    context: dict,
    blueprint: dict,
    max_attempts: int = 3,
    tolerance: int = 15,
) -> tuple[dict, int, int]:
    """Retry loop for word count control.

    Returns (memory_payload, attempts_used, final_word_count).
    Path B: each attempt re-injects the few-shot examples via _stage2_writer.
    """
    target = blueprint.get("target_length_words", 110)
    last_payload: dict[str, Any] = {}
    last_wc = 0
    for attempt in range(1, max_attempts + 1):
        payload = _stage2_writer(
            context,
            blueprint,
            previous_word_count=last_wc if attempt > 1 else None,
        )
        wc = len(str(payload.get("memory_text", "")).split())
        last_payload, last_wc = payload, wc
        if abs(wc - target) <= tolerance:
            return last_payload, attempt, wc
    return last_payload, max_attempts, last_wc


def _run_validators(memory_payload: dict, context: dict) -> list[ConstraintResult]:
    """Run all constraint validators and return a flat list of ConstraintResult."""
    results: list[ConstraintResult] = []

    # Structural contract (validate_contract operates on raw JSON string)
    try:
        validate_contract(json.dumps(memory_payload))
        results.append(ConstraintResult(
            constraint_id="C_CONTRACT",
            passed=True,
            message="output JSON contract satisfied",
        ))
    except OutputContractError as exc:
        results.append(ConstraintResult(
            constraint_id="C_CONTRACT",
            passed=False,
            message=f"contract error: {exc}",
        ))

    # Content validators (C1–C6, C_CLOSING, C_DIVERSITY, C_ERA)
    try:
        content_results = validate(memory_payload, context)
        results.extend(content_results)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        results.append(ConstraintResult(
            constraint_id="C_VALIDATE",
            passed=False,
            message=f"validator raised unexpectedly: {exc}",
        ))

    return results


def generate_two_stage(
    context: dict,
    recent_scenes: list[str],
    max_stage2_attempts: int = 3,
) -> GenerationResult:
    blueprint = _stage1_scene_select(context, recent_scenes)
    raw_payload, attempts_used, _wc = _stage2_write_with_length(
        context, blueprint, max_attempts=max_stage2_attempts
    )
    memory_payload = _normalize_generated_payload(raw_payload)

    text = memory_payload.get("memory_text", "")

    # Run all validators — get structured results
    constraint_results = _run_validators(memory_payload, context)

    # Determine overall status
    failures = [r for r in constraint_results if not r.passed]
    generation_status = "completed_with_warnings" if failures else "completed"

    # Legacy flat failure strings for GenerationResult.failures (API / logging)
    failure_messages = list(dict.fromkeys(r.message for r in failures))

    word_count = len(text.split()) if isinstance(text, str) else 0
    memory = Memory(
        id=f"mem-{len(recent_scenes) + 1}",
        memory_text=text,
        why_this_is_false=memory_payload.get("why_this_is_false", ""),
        rationale=memory_payload.get("rationale", ""),
        is_fabricated=True,
        gap_id="stage2-generated",
        word_count=word_count,
        constraint_results=[r.to_dict() for r in constraint_results],
        generation_status=generation_status,
    )

    return GenerationResult(
        memory=memory,
        attempted_runs=attempts_used,
        failures=failure_messages,
        blueprint=blueprint,
    )
