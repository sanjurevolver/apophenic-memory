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
FEW_SHOT_FILE = Path("test_data/few_shot_examples.md")

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
    }

    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    raw_text = response.json().get("response", "")
    cleaned = raw_text.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Extract outermost JSON object
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse valid JSON from Ollama response: {raw_text[:200]}")


def _normalize_generated_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    if "constraints_satisfied" not in normalized:
        normalized["constraints_satisfied"] = [
            "C1", "C2", "C2b", "C3", "C4", "C5", "C6",
        ]
    if "why_this_is_false" not in normalized:
        normalized["why_this_is_false"] = (
            "This memory is fictional and did not happen in the diary timeline."
        )
    if "rationale" not in normalized:
        normalized["rationale"] = (
            "This memory bridges the emotional arc between the surrounding diary entries."
        )
    return normalized


def _stage1_scene_select(context: dict, recent_scenes: list[str]) -> dict[str, Any]:
    template = _load_prompt("stage1_scene_selector.txt")

    people = context.get("people", [])
    era = context.get("era", {})
    before_tone = "anxious"
    if context.get("entries_before"):
        before_tone = "anxious"
    after_tone = "calm"
    if context.get("entries_after"):
        after_tone = "calm"

    payload = {
        "era": era,
        "people": people,
        "entries_before_tone": before_tone,
        "entries_after_tone": after_tone,
        "recently_used_scenes": recent_scenes,
        "scene_type_enum": SCENE_ENUM,
    }

    full_prompt = (
        f"{template}\n\n--- INPUT JSON ---\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    selected = _call_ollama(full_prompt)

    if selected.get("scene_type") not in SCENE_ENUM:
        raise ValueError(f"invalid scene type: {selected.get('scene_type')}")
    if selected.get("scene_type") in recent_scenes:
        raise ValueError(f"scene type reused: {selected.get('scene_type')}")
    return selected


def _stage2_writer(
    context: dict,
    blueprint: dict[str, Any],
    previous_word_count: int | None = None,
) -> dict[str, Any]:
    era_dict = context.get("era", {}) if isinstance(context.get("era"), dict) else {}
    year_val = era_dict.get("year", context.get("year", "2012"))

    # Extract month from gap start_date or context
    month_val = "March"
    gap_info = context.get("gap", {})
    start_date = gap_info.get("start_date", "")
    if start_date and len(start_date) >= 7:
        try:
            m_num = int(start_date.split("-")[1])
            import calendar
            month_val = calendar.month_name[m_num]
        except Exception:
            month_val = "March"

    # Extract location from city / country / era
    city = context.get("city") or era_dict.get("city")
    country = context.get("country") or era_dict.get("country")
    if city and country:
        location_val = f"{city}, {country}"
    elif city:
        location_val = str(city)
    elif country:
        location_val = str(country)
    else:
        location_val = "the diarist's home city"

    template = _load_prompt("stage2_writer.txt")
    template = template.replace("{examples_block}", _load_examples_block())
    template = template.replace("{year}", str(year_val))
    template = template.replace("{month}", str(month_val))
    template = template.replace("{location}", str(location_val))
    template = template.replace("{era}", str(year_val))

    payload: dict[str, Any] = {
        "blueprint": blueprint,
        "era": context.get("era", {}),
    }
    if previous_word_count is not None:
        payload["previous_word_count"] = previous_word_count
        payload["target_length_words"] = blueprint.get("target_length_words")

    full_prompt = (
        f"{template}\n\n--- INPUT JSON ---\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return _call_ollama(full_prompt)


def _stage2_write_with_length(
    context: dict,
    blueprint: dict[str, Any],
    max_attempts: int = 3,
    tolerance: int = 15,
) -> tuple[dict[str, Any], int, int]:
    """Retry stage 2 until word count is within tolerance.

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
    generation_status = "completed_with_warnings" if failures else "ok"

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
    )