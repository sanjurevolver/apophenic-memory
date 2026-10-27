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

    def fake_call_ollama(prompt, model="llama3.1:8b"):
        calls.append({"prompt": prompt, "model": model})
        if "scene planner" in prompt.lower():
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
        "people": [{"name": "Friend A", "relationship": "friend"}],
        "entries_before": [{"date": "2012-03-01", "text": "I was exhausted and scared of missing lectures."}],
        "entries_after": [{"date": "2012-03-20", "text": "I felt more settled and easier to laugh again."}],
    }

    result = generate_two_stage(context, ["cooking_at_home", "bus_ride_no_destination", "park_outing"])

    assert result.memory.memory_text
    assert result.memory.word_count >= 80
    assert result.memory.word_count <= 140
    assert result.memory.is_fabricated is True
    assert result.attempted_runs >= 1
    assert result.failures == []
