# STATUS.md — cadgen current status (rewrite, don't append)

Last updated: 2026-10-04. Stage: 2 DONE (data + benchmark); Stage 3 blocked on license escalation.

## Decisions (D1–D6)
- D1 angle A+B+C+E; D2 permissive-if-audit-allows (NC fallback, escalation open); D3 Qwen2.5-Coder-7B, prototype 1.5B–3B; D4 M4 Air local + rented GPU later; D5 tag-and-separate; D6 cadgen
- Pilot 80/10/10; per-chunk dedupe leakage accepted; seed baseline n=1; benchmark v1 template-built (not LLM-synth); splits gitignored (18MB, regenerable)

## Success targets (pre-baseline, do not move)
- exec ≥ 80%, geo_pass ≥ 60% on the 243-task benchmark; beat few-shot base with non-overlapping CI

## Data
- CAD-Coder + Text-to-CadQuery acquired, ingested (8177 + 99236), adapted, filtered; both in `data/LICENSES.md` with caveats; license escalation open — NO TRAINING until resolved
- Pilot `data/splits/pilot/`: train 5052 / val 624 / test 651 (all normalized); zero group overlap
- Harness green: `pytest -q` 27 passed (incl. adapt 4 + filter 3); smoke PASSED

## Benchmark v1: `benchmark/tasks.jsonl` — 243 tasks, AUTOMATED-QUALITY
- T1 93 (template mechanical) / T2 70 (novel phrasing) / T3 80 (consumer/arch); 18 families; all `result`, mm, single solid
- Gates all machine-run: exec+dedupe → bbox 10% + volume 25% vs template-expected → decontam vs pilot train (0 rejects)
- Human spot-check 40/243: 39 correct → benchmark error ≈ 2.5% (1 template edge: bolt circle grazing center hole)

## Baselines (seed 12-task smoke — real-benchmark eval is Stage 5)
- ornith:9B zero-shot n=1: exec 0.333, geo_pass 0.25, mean IoU 0.28

## Open questions / next
- LICENSE escalation blocks Stage 3 (sft_mlx.py + mlx-lm + 50-sample overfit)
- Unblocked next: Stage 5-style baseline on the 243-task benchmark (ornith zero-shot; needs ~hours: 243 gens × ~45s ≈ 3h sequential — chunk it), few-shot harness support, synthetic mm-track data (2.5)
- Open a PR for the stage-2 branch once the human merges #1 (stacked)
