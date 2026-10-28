"""tests/test_validators.py

Unit tests for constraint validators in constraints.py.
No Ollama or LLM instance is required.
"""
import pytest

from apophenic_memory.liar.constraints import validate, validate_closing, validate_era


def test_validate_era_valid_2012():
    context = {"era": {"year": 2012}}
    memory = {"memory_text": "I walked to campus on 14 March 2012."}
    results = validate_era(memory, context)
    assert all(r.passed for r in results)


def test_validate_era_anachronism_2017():
    context = {"era": {"year": 2012}}
    memory = {"memory_text": "I bought a 2017 recipe book in 2012."}
    results = validate_era(memory, context)
    failed = [r for r in results if not r.passed]
    assert failed
    assert any("2017" in r.message for r in failed)


def test_validate_closing_concrete_action():
    memory = {"memory_text": "I slid the coins across the counter."}
    results = validate_closing(memory)
    assert all(r.passed for r in results)


def test_validate_closing_fails_on_i_felt_happy():
    memory = {"memory_text": "I stood at the counter. I felt happy."}
    results = validate_closing(memory)
    failed = [r for r in results if not r.passed]
    assert failed
    assert any("final sentence" in r.message.lower() for r in failed)


def test_validate_c3_fails_when_invented_name_passed():
    context = {"people": [{"name": "Ramesh"}]}
    memory = {
        "memory_text": "I walked to the tea stall with Suresh and bought some tea.",
        "why_this_is_false": "fictional",
        "rationale": "bridge",
        "constraints_satisfied": [],
    }
    results = validate(memory, context)
    c3_results = [r for r in results if r.constraint_id == "C3"]
    assert c3_results
    assert any(not r.passed for r in c3_results)
    assert any("Suresh" in r.message for r in c3_results if not r.passed)
