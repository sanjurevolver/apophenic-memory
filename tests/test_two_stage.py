from apophenic_memory.liar.two_stage import generate_two_stage


class FakeOllama:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages, format=None, options=None):
        self.calls.append({"model": model, "messages": messages, "format": format, "options": options})
        last_text = messages[-1]["content"]
        if "scene planner" in last_text.lower():
            return {
                "message": {
                    "content": '{"scene_type":"queue_at_shop","setting":"the tea stall by the market","people_involved":["Friend A"],"target_length_words":105,"emotional_move":"relief","target_final_image":"I slid the coins across the counter and waited for the kettle to hiss."}'
                }
            }
        return {
            "message": {
                "content": '{"memory_text":"I waited in the queue outside the tea stall by the market with Friend A after class, still carrying the knot of revision in my chest. We had a list of errands and Friend A held the coins while we counted the change three times. The shop smelled of cardamom and dust, and the kettle hissed on the stove behind the counter. I stood by the counter with my notebook under my arm while Friend A asked for two cups of tea, served in chipped glasses with a little sugar and a spoon. I slid the coins across the counter and waited for the kettle to hiss.","why_this_is_false":"I never stood in that queue with Friend A during the gap; the outing is fictional.","rationale":"This scene moves from the study strain before the gap toward a calmer domestic rhythm after it. The queue, coins, and kettle create a specific period detail set while keeping the memory grounded in a fictional person and era-appropriate objects.","constraints_satisfied":["C1","C2","C2b","C3","C4","C5","C6"]}'
            }
        }


def test_generate_two_stage_returns_json_shape(monkeypatch):
    import apophenic_memory.liar.two_stage as two_stage

    calls = []

    def fake_call_ollama(prompt, model="llama3.2:3b"):
        calls.append({"prompt": prompt, "model": model})
        if "scene planner" in prompt.lower() or "stage 1: scene selector" in prompt.lower():
            return {
                "scene_type": "queue_at_shop",
                "setting": "the tea stall by the market",
                "people_involved": ["Friend A"],
                "target_length_words": 105,
                "emotional_move": "relief",
                "target_final_image": "I slid the coins across the counter and waited for the kettle to hiss.",
            }
        return {
            "memory_text": "I waited in the queue outside the tea stall by the market with Friend A after class, still carrying the knot of revision in my chest. We had a list of errands and Friend A held the coins while we counted the change three times. The shop smelled of cardamom and dust, and the kettle hissed on the stove behind the counter. I stood by the counter with my notebook under my arm while Friend A asked for two cups of tea, served in chipped glasses with a little sugar and a spoon. I slid the coins across the counter and waited for the kettle to hiss.",
            "why_this_is_false": "I never stood in that queue with Friend A during the gap; the outing is fictional.",
            "rationale": "This scene moves from the study strain before the gap toward a calmer domestic rhythm after it. The queue, coins, and kettle create a specific period detail set while keeping the memory grounded in a fictional person and era-appropriate objects.",
            "constraints_satisfied": ["C1", "C2", "C2b", "C3", "C4", "C5", "C6"],
        }

    monkeypatch.setattr(two_stage, "_call_ollama", fake_call_ollama)

    context = {
        "era": {"year": 2012, "city": "Example City", "forbidden_devices": ["smartphone"], "allowed_transport": ["bus"]},
        "people": [
            {"name": "Friend A", "relationship": "friend"},
            {"name": "Friend B", "relationship": "classmate"},
            {"name": "Housemate C", "relationship": "housemate"},
        ],
        "gap": {"start_date": "2012-03-02", "end_date": "2012-03-26"},
        "entries_before": [{"date": "2012-03-01", "text": "I was exhausted and scared of missing lectures."}],
        "entries_after": [{"date": "2012-03-20", "text": "I felt more settled and easier to laugh again."}],
    }

    result = generate_two_stage(context, ["cooking_at_home", "bus_ride_no_destination", "park_outing"])

    assert result.memory.memory_text
    assert result.memory.word_count >= 80
    assert result.memory.word_count <= 140
    assert result.memory.is_fabricated is True
    assert result.attempted_runs >= 1
    assert hasattr(result, "blueprint")
    assert result.blueprint.get("scene_type") == "queue_at_shop"

    # New: constraint_results is a list of dicts with constraint_id / passed / message
    assert isinstance(result.memory.constraint_results, list)
    assert all("constraint_id" in r and "passed" in r and "message" in r
               for r in result.memory.constraint_results)

    # generation_status must be one of the valid values
    assert result.memory.generation_status in ("completed", "ok", "completed_with_warnings")

    # No contract-level or era errors (those are hard failures we care about)
    contract_results = [r for r in result.memory.constraint_results
                        if r["constraint_id"] in ("C_CONTRACT", "C_ERA")]
    assert all(r["passed"] for r in contract_results), (
        f"Contract/era constraint failed: {[r for r in contract_results if not r['passed']]}"
    )

def test_generate_two_stage_retries_on_constraint_failure(monkeypatch):
    import apophenic_memory.liar.two_stage as two_stage

    calls = []

    def fake_call_ollama(prompt, model="llama3.2:3b"):
        calls.append({"prompt": prompt, "model": model})
        if "scene planner" in prompt.lower() or "stage 1: scene selector" in prompt.lower():
            return {
                "scene_type": "queue_at_shop",
                "setting": "the tea stall by the market",
                "people_involved": ["Friend A"],
                "target_length_words": 105,
                "emotional_move": "relief",
                "target_final_image": "I slid the coins across the counter and waited for the kettle to hiss.",
            }
        # Attempt 1 for Stage 2 fails: introduces an unapproved person ("John") and an anachronism (2017)
        if len(calls) == 2:
            return {
                "memory_text": (
                    "In 2017 I waited in line with John and Friend A at the corner shop "
                    "hoping to buy a newspaper before the afternoon train arrived in the station. "
                    "We counted the change carefully and checked our bags while standing quietly on the pavement. "
                    "The seller asked for exact change and we searched through our pockets for extra coins. "
                    "Friend A asked if we had time for tea before heading home to finish revision. "
                    "I slid the coins across the counter and waited for the kettle to hiss."
                ),
                "why_this_is_false": "Fictional memory.",
                "rationale": "Bridges narrative.",
                "constraints_satisfied": ["C1", "C2", "C3", "C4", "C5", "C6"],
            }
        # Attempt 2 fixes the errors: valid 2012 memory, only Friend A, observational closing
        return {
            "memory_text": (
                "In 2012 I waited in line with Friend A at the corner shop "
                "hoping to buy a newspaper before the afternoon train arrived in the station. "
                "We counted the change carefully and checked our bags while standing quietly on the pavement. "
                "The seller asked for exact change and we searched through our pockets for extra coins. "
                "Friend A asked if we had time for tea before heading home to finish revision. "
                "I slid the coins across the counter and waited for the kettle to hiss."
            ),
            "why_this_is_false": "Fictional memory.",
            "rationale": "Bridges narrative.",
            "constraints_satisfied": ["C1", "C2", "C3", "C4", "C5", "C6"],
        }

    monkeypatch.setattr(two_stage, "_call_ollama", fake_call_ollama)

    context = {
        "era": {"year": 2012, "city": "Bangalore", "forbidden_devices": ["smartphone"], "allowed_transport": ["bus"]},
        "people": [
            {"name": "Friend A", "relationship": "friend"},
        ],
        "gap": {"start_date": "2012-03-02", "end_date": "2012-03-26"},
        "entries_before": [{"date": "2012-03-01", "text": "I was exhausted and scared of missing lectures."}],
        "entries_after": [{"date": "2012-03-20", "text": "I felt more settled and easier to laugh again."}],
    }

    result = generate_two_stage(context, recent_scenes=[], max_stage2_attempts=3)

    assert result.attempted_runs == 2
    assert result.memory.generation_status == "completed"
    # Ensure attempt 2 prompt contained CORRECTION REQUIRED feedback
    assert len(calls) == 3
    assert "CORRECTION REQUIRED" in calls[2]["prompt"]
    assert "C_ERA" in calls[2]["prompt"] or "C3" in calls[2]["prompt"]

