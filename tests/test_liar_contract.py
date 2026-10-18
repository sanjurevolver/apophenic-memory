import pytest

from apophenic_memory.liar.constraints import (
    OutputContractError,
    validate,
    validate_closing,
    validate_contract,
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

    ok, failures = validate(memory, {})

    assert not ok
    assert any("final sentence contains emotion markers" in failure for failure in failures)

    ok2, failures2 = validate_closing(memory)
    assert not ok2
    assert failures2
