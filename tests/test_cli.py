import json
import os

from cadgen import cli as C


def _good(prompt):
    return "```python\nimport cadquery as cq\nresult = cq.Workplane('XY').box(10, 20, 30)\n```"


def _bad(prompt):
    return "```python\nimport cadquery as cq\nresult = (\n```"


def test_retry_until_success(tmp_path):
    calls = []
    def gen(p):
        calls.append(p)
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


def test_step_stl_match_executed_geometry(tmp_path):
    s = C.run("a box", _good, str(tmp_path), "b", tries=1)
    assert s["ok"] and abs(s["volume"] - 10 * 20 * 30) / (10 * 20 * 30) < 0.01
    code = open(os.path.join(str(tmp_path), "b.py")).read()
    assert "result" in code and json.dumps(s["bbox"])
