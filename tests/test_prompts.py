from cadgen.prompts import build_fewshot_messages


def test_fewshot_message_shape():
    ex = [{"prompt": "p1", "code": "import cadquery as cq\nresult = 1"},
          {"prompt": "p2", "code": "import cadquery as cq\nresult = 2"}]
    m = build_fewshot_messages(ex, "final")
    assert [x["role"] for x in m] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert m[-1]["content"] == "final"
    assert m[2]["content"].startswith("```python\n") and "result = 1" in m[2]["content"]


def test_fewshot_empty_examples_is_zero_shot_plus():
    m = build_fewshot_messages([], "q")
    assert [x["role"] for x in m] == ["system", "user"] and m[1]["content"] == "q"
