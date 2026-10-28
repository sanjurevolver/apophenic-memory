import pytest

from apophenic_memory.liar.constraints import (
    OutputContractError,
    validate,
    validate_closing,
    validate_contract,
    validate_era,
)


def test_validate_contract_extracts_json_from_wrapped_output():
    raw = '''
Here is a fabricated memory that meets the requirements:

```json
{
    "memory_text": "I spent most of the day on March 15th, 2012, walking to campus in my worn-out shoes. Friend A met me there, and we spent hours in the public library studying for our exams. I remember taking a short break to buy a snack from the tea stall near the bus stop. The afternoon sun was warm on my back as I watched the city buses rumble by. Friend B joined us for a bit, but had to leave early, and Friend A and I continued studying until the library closed.",
  "why_this_is_false": "I never spent that day in the library; the memory is a fictional bridge for the gap.",
  "rationale": "It bridges the stress before the gap with the calmer mood after it.",
  "constraints_satisfied": ["C1", "C2", "C3", "C4", "C5", "C6"]
}
```
'''.strip()

    obj = validate_contract(raw)

    assert obj["memory_text"].startswith("I spent most of the day")
    assert obj["constraints_satisfied"] == ["C1", "C2", "C3", "C4", "C5", "C6"]


def test_validate_contract_rejects_invalid_json():
    raw = "This is not JSON at all."

    with pytest.raises(OutputContractError):
        validate_contract(raw)


def test_validate_rejects_emotional_final_sentence():
    memory = {
        "memory_text": (
            "I stood at the counter while Housemate C sorted oranges into a wire basket and said they would take the 6:10 bus with me. "
            "We spoke about the market list and the dry milk packets stacked by the window, and I was glad to be out of my room for an hour. "
            "She paid in coins, wrapped the fruit, and left the shop with the bag swinging from her wrist. "
            "I felt like I could finally breathe."
        ),
        "why_this_is_false": "I never stood at that counter with Housemate C; this is a fictional bridge memory.",
        "rationale": "This scene transitions from the tense mood before the gap to a calmer, more ordinary rhythm after it.",
        "constraints_satisfied": ["C1", "C2", "C2b", "C3", "C4", "C5", "C6"],
    }

    # validate() now returns list[ConstraintResult]
    results = validate(memory, {})

    failed = [r for r in results if not r.passed]
    assert failed, "expected at least one failing constraint"
    assert any(
        "final sentence contains emotion markers" in r.message for r in failed
    )

    # validate_closing() also returns list[ConstraintResult]
    closing_results = validate_closing(memory)
    assert any(not r.passed for r in closing_results)
    assert any("final sentence contains emotion markers" in r.message for r in closing_results)


def test_validate_era_detects_anachronism():
    context = {"era": {"year": 2012}}

    valid_memory = {"memory_text": "I walked around the market in March 2012 with Friend A."}
    results = validate_era(valid_memory, context)
    assert all(r.passed for r in results), "expected no failures for a correct year"

    anachronistic_memory = {"memory_text": "I bought a 2017 recipe book and cooked with Friend A in 2012."}
    results2 = validate_era(anachronistic_memory, context)
    failed = [r for r in results2 if not r.passed]
    assert failed, "expected an era failure"
    assert any("2017" in r.message for r in failed)


def test_validate_era_no_year_in_text():
    context = {"era": {"year": 2012}}
    memory = {"memory_text": "I walked through the market with Friend A on a Tuesday afternoon."}
    results = validate_era(memory, context)
    assert all(r.passed for r in results)
