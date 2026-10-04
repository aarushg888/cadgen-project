"""End-to-end check of the whole framework without any model or network:
  seed tasks -> canonical samples -> execute-and-filter -> split -> fake 'model' outputs -> evaluation.
    python scripts/smoke_test.py
"""
import json, os, shutil, tempfile
from cadgen.schema import read_jsonl, write_jsonl
from cadgen.data.filter import run_filter
from cadgen.eval.run_eval import evaluate

root = os.path.join(os.path.dirname(__file__), "..")
tasks = list(read_jsonl(os.path.join(root, "benchmark", "seed_tasks.jsonl")))
tmp = tempfile.mkdtemp(prefix="cadgen_smoke_")

# 1) data pipeline: good samples + deliberately bad ones must be filtered out
raw = [{"id": t["id"], "prompt": t["prompt"], "code": t["code"], "source": "seed", "license": "own"} for t in tasks]
raw += [
    {"id": "bad_syntax", "prompt": "x", "code": "import cadquery as cq\nresult = ("},
    {"id": "bad_import", "prompt": "x", "code": "import os\nresult = 1"},
    {"id": "bad_fillet", "prompt": "x", "code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1).fillet(5)"},
    {"id": "dup_of_cylinder", "prompt": "y", "code": tasks[1]["code"]},
]
write_jsonl(os.path.join(tmp, "raw.jsonl"), raw)
stats = run_filter(os.path.join(tmp, "raw.jsonl"), os.path.join(tmp, "filtered"), workers=4, dedupe_code=True)
print("filter:", json.dumps(stats["counts"]), f"pass_rate={stats['pass_rate']:.2f}")
assert stats["counts"]["ok"] == len(tasks), stats

# 2) evaluation: perfect model, half-broken model, and a wrong-size model
gens = {}
for i, t in enumerate(tasks):
    good = "```python\n" + t["code"] + "```"
    wrong = good.replace("box(", "box(2*").replace("circle(", "circle(2*") if i % 3 == 0 else good
    broken = "```python\nimport cadquery as cq\nresult = (\n```"
    gens[t["id"]] = [good, broken if i % 2 else wrong]
summary = evaluate(tasks, gens, os.path.join(tmp, "eval"), workers=4, k_values=(1, 2))
print("eval:", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in summary.items()}))
assert summary["pass@1"] > 0.4 and summary["exec_rate"] < 1.0
shutil.rmtree(tmp)
print("SMOKE TEST PASSED")
