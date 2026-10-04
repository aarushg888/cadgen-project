# cadgen

Tooling to fine-tune and evaluate an open LLM that writes **CadQuery** code from a text description
(Blender `bpy` later). This repo currently contains the foundation: a fast sandboxed execution harness,
geometry metrics, a data pipeline, and an evaluation harness. Model training comes next.

**Read `PLAN.md` first**: it has the full build order, decisions, risks and tomorrow's checklist.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm]"
pytest -q
python scripts/smoke_test.py
```

## What's here
- `cadgen/sandbox.py`: `run_code()` (one-shot) and `SandboxPool` (warm fork-server workers, many jobs/s)
- `cadgen/metrics.py`: IoU, Chamfer, bbox/volume match, pass@k
- `cadgen/data/`: ingest, execute-and-filter, group-aware split, synthetic generation
- `cadgen/eval/run_eval.py`: benchmark harness (live generation from any OpenAI-compatible server, or scoring saved generations)
- `benchmark/`: 12-task smoke benchmark (a real 200+ task benchmark is a planned deliverable)

## Security note
Generated code is untrusted. The static check and resource limits are not a security boundary.
Run large jobs in a locked-down container (see PLAN.md, section 4).
