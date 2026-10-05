# STATUS.md — cadgen current status (rewrite, don't append)

Last updated: 2026-10-04. Stage: 2 (data) — pilot split done, seed baseline measured. Remaining in Stage 2: 200+ automated benchmark.

## Decisions (D1–D6)
- D1 angle A+B+C+E; D2 permissive-if-audit-allows (NC fallback, escalation open); D3 Qwen2.5-Coder-7B, prototype 1.5B–3B; D4 M4 Air local + rented GPU later; D5 tag-and-separate (normalized tagged, mm for synthetic/benchmark); D6 cadgen
- Pilot split 80/10/10 (not 96/2/2); per-chunk dedupe leakage accepted (group split still clean); seed baseline n=1 (ollama ignores `n`)

## Success targets (pre-baseline, do not move)
- exec ≥ 80%, geo_pass ≥ 60% on the 200+ benchmark; beat few-shot base with non-overlapping CI

## Data
- Sources: CAD-Coder (~650MB) + Text-to-CadQuery (~1.3GB) in `data/raw/`; both in `data/LICENSES.md` with lineage caveats; license escalation open (no training until resolved)
- Ingest → adapt (export-strip + `result` synthesis, 4 tests) → filter (3-decimal geom sig + `--offset`, 3 tests) → split
- Pilot `data/splits/pilot/`: train 5052 / val 624 / test 651 (6327; cc-high 4862@59% + t2cq slice 1465@73%). Zero group overlap across splits. All `meta.units=normalized`.
- Harness green: `pytest -q` 24 passed; smoke PASSED

## Baselines (seed 12-task smoke benchmark — NOT the real benchmark)
- ornith:9B zero-shot, n=1: exec 0.333, geo_pass 0.25, mean IoU 0.28, pass@1 0.25 (`runs/eval_ornith_zero/`)
- Failure modes: hallucinated APIs, Wire/Solid→vector errors, missing `result` ×3, one executes-but-wrong
- Few-shot + fine-tuned comparisons happen in Stage 5 on the real benchmark, same run

## Open questions
- License escalation (commercial use of Text2CAD-derived data) — blocks all training
- D5 mm-track data still missing (needs synthetic 2.5 + permissive GitHub examples)
- Next: 200+ automated-quality benchmark per AGENTS.md (synth → sandbox filter → bbox/vol consistency → decontaminate), then Stage 3 `sft_mlx.py` (needs mlx-lm install + 50-sample overfit)
