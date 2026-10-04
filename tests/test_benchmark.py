import os, json, pytest
from cadgen.sandbox import SandboxPool
from cadgen.schema import read_jsonl

TASKS = os.path.join(os.path.dirname(__file__), "..", "benchmark", "seed_tasks.jsonl")

def test_all_seed_references_execute_as_single_valid_solids():
    tasks = list(read_jsonl(TASKS))
    assert len(tasks) >= 12
    with SandboxPool(4) as pool:
        for t in tasks:
            r = pool.run(t["code"], timeout=30)
            assert r.ok and r.n_solids == 1, (t["id"], r.status, r.error)


def test_to_mlx_format(tmp_path):
    from cadgen.data.to_mlx import to_chat
    row = to_chat({"prompt": "a cube", "code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1)"})
    roles = [m["role"] for m in row["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert row["messages"][2]["content"].startswith("```python\n") and row["messages"][2]["content"].endswith("\n```")
