# STATUS.md — cadgen current status (rewrite, don't append)

Last updated: 2026-10-04. Stage: 2 DONE (data + benchmark); Stage 3 blocked on license escalation.

## Decisions (D1–D6)
- D1 angle A+B+C+E; D2 permissive-if-audit-allows (NC fallback, escalation open); D3 Qwen2.5-Coder-7B, prototype 1.5B–3B; D4 M4 Air local + rented GPU later; D5 tag-and-separate; D6 cadgen
- Pilot 80/10/10; per-chunk dedupe leakage accepted; seed baseline n=1; benchmark v1 template-built (not LLM-synth); splits gitignored (18MB, regenerable)

## Success targets (pre-baseline, do not move)
- exec ≥ 80%, geo_pass ≥ 60% on the 243-task benchmark; beat few-shot base with non-overlapping CI

## Data
- CAD-Coder + Text-to-CadQuery acquired, ingested (8177 + 99236), adapted, filtered; both in `data/LICENSES.md` with caveats; license escalation open — third-party data NOT cleared for training
- Own synthetic mm training pool `data/raw/synth_train.jsonl`: 7372 rows, units=mm, license=own (mech 3876 / consumer 2179 / arch 1317), decontaminated vs benchmark — CLEARED for training whenever Stage 3 starts
- Pilot `data/splits/pilot/`: train 5052 / val 624 / test 651 (all normalized); zero group overlap
- Harness green: `pytest -q` 31 passed; smoke PASSED

## Benchmark v1: `benchmark/tasks.jsonl` — 243 tasks, AUTOMATED-QUALITY
- T1 93 (template mechanical) / T2 70 (novel phrasing) / T3 80 (consumer/arch); 18 families; all `result`, mm, single solid
- Gates all machine-run: exec+dedupe → bbox 10% + volume 25% vs template-expected → decontam vs pilot train (0 rejects)
- Human spot-check 40/243: 39 correct → benchmark error ≈ 2.5% (1 template edge: bolt circle grazing center hole)

## Baselines (v1 243-task benchmark — the numbers that matter)
- ornith-8k zero-shot, n=1, think:false (`runs/eval_bench_ornith8k/`): exec 0.218 [0.165, 0.272], geo 0.107 [0.070, 0.148], mean IoU 0.110
- ornith-8k FEW-SHOT (3 seed examples), same gen config (`runs/eval_bench_ornith8k_fewshot/`, scored in 2 slices + merged): exec 0.650 [0.588, 0.712], geo 0.325 [0.267, 0.383], mean IoU 0.418
- Per tier few-shot (exec/geo): T1 0.699/0.376, T2 0.657/0.400, T3 0.588/0.200
- Zero vs few-shot CIs do not overlap. THE BAR (ship criterion): beat few-shot exec 0.65 / geo 0.33 with non-overlapping CIs. Targets (0.80/0.60) stand.
- Failure modes (few-shot): runtime 74, invalid 8, syntax 2, empty 1

## Env notes (2026-10-07)
- My ollama server is on :11435 (11434 belongs to another user — do not touch); model ornith-8k (9B Q4, ctx 8192)
- Harness green: `pytest -q` 29 passed; smoke PASSED

## Open questions / next
- LICENSE escalation blocks Stage 3 (sft_mlx.py + mlx-lm + 50-sample overfit)
- Unblocked next: Stage 5-style baseline on the 243-task benchmark (ornith zero-shot; needs ~hours: 243 gens × ~45s ≈ 3h sequential — chunk it), few-shot harness support, synthetic mm-track data (2.5)
- Open a PR for the stage-2 branch once the human merges #1 (stacked)
