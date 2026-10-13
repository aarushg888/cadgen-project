# Model card: cadgen-sft-1.5b-v1 (LoRA adapter, checkpoint ckpt600)

## What this is
A Qwen2.5-Coder-1.5B-Instruct LoRA adapter that writes CadQuery code (mm,
`result` variable, single solid) from a text description. Runs locally via
`cadgen` CLI (MLX) — see README.

## Training
- Base: `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit` (Apache-2.0). Prototype
  scale per project plan; 7B run needs a rented GPU (not done).
- Data (own license, mm-native, trainable regardless of third-party audit):
  5,922 template-synthetic rows (18 mechanical/consumer/architectural families),
  execute-filtered, self-consistency-checked (prompt dims vs bbox 10% + analytic
  volume 25%), decontaminated vs the benchmark (exact-code + prompt Jaccard).
  Full manifest: `data/LICENSES.md`. Normalized-unit third-party data was
  collected and filtered but explicitly NOT used here (license under review).
- Recipe (`cadgen/train/sft_mlx.py`): rank 32 / scale 2.0 / dropout 0.05 /
  lr 1e-4 / batch 4 / mask-prompt (completion-only loss) / all linear layers /
  600 iters (~0.4 epochs). Overfit-50 gate passed first (loss → 0.000, 3/3 exact
  reproductions). Adapter: `runs/` (gitignored — see STATUS for checkpoint path).

## Evaluation (v1 benchmark, 243 tasks, automated-quality, ~2.5% bench error)

| Model (n=1, temp 0.2) | exec rate | geo_pass | mean IoU | 95% CI (geo) |
|---|---|---|---|---|
| base zero-shot (ornith-8k) | 0.218 | 0.107 | 0.110 | [0.070, 0.148] |
| base few-shot, 3 seed examples | 0.650 | 0.325 | 0.418 | [0.267, 0.383] |
| **this adapter, zero-shot** | **1.000** | **0.922** | **0.910** | [0.885, 0.955] |

Per tier (adapter exec/geo): T1 template 1.000/1.000, T2 novel phrasing
1.000/0.957, T3 consumer/architectural 1.000/0.800. Few-shot-vs-adapter CIs do
not overlap. Pre-registered targets (exec ≥ 0.80, geo ≥ 0.60): met.

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
