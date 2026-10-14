import json
import os

from cadgen import cli as C


def _good(prompt, temperature=0.2):
    return "```python\nimport cadquery as cq\nresult = cq.Workplane('XY').box(10, 20, 30)\n```"


def _bad(prompt, temperature=0.2):
    return "```python\nimport cadquery as cq\nresult = (\n```"


def test_retry_until_success(tmp_path):
    calls = []
    def gen(p, temperature=0.2):
        calls.append((p, temperature))
        return _bad(p) if len(calls) < 3 else _good(p)
    s = C.run("a box", gen, str(tmp_path), "part", tries=5)
    assert s["ok"] and s["tries_used"] == 3 and len(calls) == 3
    for ext in ("py", "step", "stl"):
        p = os.path.join(str(tmp_path), f"part.{ext}")
        assert os.path.exists(p) and os.path.getsize(p) > 0
    assert s["bbox"] is not None and s["volume"] > 0


def test_all_fail_returns_summary(tmp_path):
    s = C.run("x", _bad, str(tmp_path), "p", tries=2)
    assert not s["ok"] and s["tries_used"] == 2 and s["files"] == {}
    assert all(a["status"] == "syntax_error" for a in s["attempts"])


def test_step_stl_match_executed_geometry(tmp_path):
    s = C.run("a box", _good, str(tmp_path), "b", tries=1)
    assert s["ok"] and abs(s["volume"] - 10 * 20 * 30) / (10 * 20 * 30) < 0.01
    code = open(os.path.join(str(tmp_path), "b.py")).read()
    assert "result" in code and json.dumps(s["bbox"])


def test_temperature_escalates_per_try(tmp_path):
    seen = []
    def gen(p, temperature=0.2):
        seen.append(temperature)
        return _bad(p)
    C.run("x", gen, str(tmp_path), "p", tries=3, temperatures=(0.2, 0.6, 1.0))
    assert seen == [0.2, 0.6, 1.0]
