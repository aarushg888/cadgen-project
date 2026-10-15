# Model card: cadgen-sft-1.5b-v2 (LoRA adapter, checkpoint 2350 iters)

## What this is
A Qwen2.5-Coder-1.5B-Instruct LoRA adapter that writes CadQuery code (mm,
`result` variable, single solid) from a text description. Runs locally via
`cadgen` CLI (MLX) — see README.

## Training
- Base: `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit` (Apache-2.0). Prototype
  scale per project plan; 7B run needs a rented GPU (not done).
- Data (own + Apache-2.0, mm-native): 5,922 template-synthetic rows + 2,025
  stack-diverse rows + 1,169 Zero-to-CAD rows (code→prompt rendered, gated),
  execute-filtered, consistency-checked, decontaminated vs the benchmark.
  Full manifest: `data/LICENSES.md`. Normalized-unit third-party data was
  collected and filtered but explicitly NOT used here (license under review).
- Recipe (`cadgen/train/sft_mlx.py`): rank 32 / scale 2.0 / dropout 0.05 /
  lr 1e-4 / batch 4 (later 2+accum2) / mask-prompt / all linear layers /
  2,350 iters. Overfit-50 gate passed first (loss → 0.000, 3/3 exact
  reproductions). Adapter: `runs/` (gitignored — see STATUS for checkpoint path).

## Evaluation (v1 benchmark, 243 tasks, automated-quality, ~2.5% bench error)

| Model (greedy, temp 0.0) | exec rate | geo_pass | mean IoU | 95% CI (geo) |
|---|---|---|---|---|
| base zero-shot (ornith-8k) | 0.218 | 0.107 | 0.110 | [0.070, 0.148] |
| base few-shot, 3 seed examples | 0.650 | 0.325 | 0.418 | [0.267, 0.383] |
| **this adapter, zero-shot** | **1.000** | **0.938** | **0.910** | [0.905, 0.967] |

Per tier (adapter exec/geo): T1 1.000/0.978, T2 1.000/1.000, T3 1.000/0.838.
Earlier points: ckpt600 0.922 [0.885, 0.955]; ckpt1150 0.893; ckpt3250 0.835
[0.786, 0.881] (regression — training stopped here per loop rules, ship stays 2350).
Few-shot-vs-adapter CIs do not overlap. Pre-registered targets (exec ≥ 0.80,
geo ≥ 0.60): met with margin.

## Limitations (known, measured)
- Template-distribution model: train and benchmark share 18 code families
  (decontaminated, but same patterns). Expect degradation on unusual geometry.
- Residual failures are all right-bbox / wrong-volume (subtractive features:
  holes, cutouts). T3 geo is 0.80.
- 1.5B ceiling: fine detail and long programs (>~400 tokens) untested.
- No RL/verifier training yet; no Blender `bpy`; no multi-turn editing.
- GGUF/Ollama packaging not done (adapter is MLX-format; conversion untested).

## License (proposed — human confirms at merge)
Adapter weights: Apache-2.0 (trained on own-license data only). Base model
weights remain under their original license. Text2CAD-derived datasets in this
repo are NOT part of this release for exactly that reason.
