# cadgen

An open LLM that writes **CadQuery** code from a text description — harness, data
pipeline, 243-task benchmark, a fine-tuned 1.5B LoRA, and a CLI that turns prompts
into `.py` / `.step` / `.stl`. Details: `PLAN.md` (build order), `STATUS.md`
(current state), `MODEL_CARD.md` (model + benchmark table), `AGENTS.md` (agent guide).

## Test in 5 minutes (framework — no model, no network)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm]"
pytest -q                      # 34 unit tests
python scripts/smoke_test.py   # end-to-end harness check, prints SMOKE TEST PASSED
```

## Try the CLI (generate real parts)

Pick one backend:

**A. Any Ollama model (easiest, no weights needed):**
```bash
ollama pull qwen2.5-coder:1.5b
cadgen "a flat washer with 20 mm outer diameter, 10 mm inner diameter and 2 mm thickness." \
  --model-endpoint qwen2.5-coder:1.5b --base-url http://localhost:11434/v1 \
  --out ./out --name washer --tries 3
```

**B. Our fine-tuned adapter (best quality, Apple silicon):**
```bash
pip install mlx mlx-lm   # once
cadgen "a hexagonal standoff, 15 mm across the corners, 22 mm tall, with a 6 mm through hole." \
  --adapter runs/eval_ckpt_600 --out ./out --name standoff15 --tries 3
```
(`runs/` adapters are local build artifacts, gitignored — see STATUS.md for paths.
Train your own with `cadgen/train/sft_mlx.py`; start with the 50-sample overfit.)

**Look at the part** (needs http, not `file://`):
```bash
cp out/standoff15.stl viewer/ && (cd viewer && python -m http.server 8123)
# open http://localhost:8123/index.html?model=standoff15.stl
```

## Reproduce the results

```bash
python benchmark/build_v1.py --n-per-tier 120 --seed 7   # 243-task benchmark
# baseline generations (any Ollama model; limit 5 for a quick check):
python scripts/gen_bench_baseline.py --tasks benchmark/tasks.jsonl --out runs/gens.jsonl \
  --model qwen2.5-coder:1.5b --base-url http://localhost:11434/v1 --limit 5
python -m cadgen.eval.run_eval --tasks benchmark/tasks.jsonl --generations runs/gens.jsonl --out runs/eval_x
# training data (no network needed) then overfit gate:
python scripts/build_synth_train.py --n 4000 --seed 21 --out data/raw/synth_train.jsonl
python -m cadgen.data.split --in data/raw/synth_train.jsonl --out data/splits/synth --val 0.1 --test 0.1
python -m cadgen.data.to_mlx --splits data/splits/synth --out data/mlx/synth
mkdir -p data/mlx/overfit50 && head -n 50 data/mlx/synth/train.jsonl > data/mlx/overfit50/train.jsonl \
  && head -n 10 data/mlx/synth/valid.jsonl > data/mlx/overfit50/valid.jsonl
python -m cadgen.train.sft_mlx --overfit --data data/mlx/overfit50 --adapter runs/overfit50/adapter
```

## What's here

- `cadgen/sandbox.py`: `run_code()` (one-shot) and `SandboxPool` (warm fork-server workers; `oneshot` on macOS)
- `cadgen/metrics.py`: IoU, Chamfer, bbox/volume match, pass@k
- `cadgen/data/`: ingest, adapt, execute-and-filter, group-aware split, synthetic generation
- `cadgen/eval/run_eval.py`: benchmark harness (zero/few-shot, live or saved generations)
- `cadgen/train/sft_mlx.py`: MLX-LM LoRA fine-tuning
- `cadgen/cli.py` (`cadgen` command): prompt → generate → execute → retry → files
- `benchmark/`: 12-task smoke test + 243-task v1 benchmark (automated-quality, ~2.5% error)
- `viewer/`: static three.js STL viewer

## Benchmark (v1, 243 tasks — full table in MODEL_CARD.md)

| Model (zero-shot unless noted) | exec | geo_pass |
|---|---|---|
| base zero-shot | 0.218 | 0.107 |
| base few-shot (3 examples) | 0.650 | 0.325 |
| **fine-tuned 1.5B LoRA** | **1.000** | **0.922** |

## Security note

Generated code is untrusted. The static check and resource limits are not a security boundary.
Run large jobs in a locked-down container (see PLAN.md, section 4). On macOS the memory cap
is not enforced — timeouts are the only guard; keep generated-code runs small or use Docker.
