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
- `cadgen/train/sft_mlx.py`: MLX-LM LoRA fine-tuning (Apple-silicon plan)
- `cadgen/cli.py` (`cadgen` command): prompt → generate → execute → retry → `.py`/`.step`/`.stl`
- `benchmark/`: 12-task smoke benchmark + 243-task v1 benchmark (`tasks.jsonl`, automated-quality, ~2.5% error) with `build_v1.py`
- `viewer/`: static three.js STL viewer for CLI outputs (`index.html?model=part.stl`)

## Trained model (v1, 1.5B LoRA — see MODEL_CARD.md)
Zero-shot on the 243-task benchmark: exec **1.000**, geo_pass **0.922** [0.885, 0.955]
(base zero-shot 0.218/0.107, base few-shot 0.650/0.325 — non-overlapping CIs).
```bash
cadgen "a hex nut 14 mm across the corners, 8 mm thick, 8 mm hole" \
  --adapter <adapter-dir> --out ./out --name nut
# → out/nut.{py,step,stl}; open viewer/index.html?model=../out/nut.stl to inspect
```

## Security note
Generated code is untrusted. The static check and resource limits are not a security boundary.
Run large jobs in a locked-down container (see PLAN.md, section 4).
