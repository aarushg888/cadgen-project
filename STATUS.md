# STATUS.md — cadgen current status (rewrite, don't append)

Last updated: 2026-10-04. Stage: 1 (decisions) done, entering Stage 2 (data).

## Decisions (D1–D6, confirmed from `configs/project.yaml` defaults)
- D1 angle: A+B+C+E (consumer coverage, clean license, verifier training, better benchmark)
- D2 license: permissive (Apache-2.0/MIT) if data audit allows, else non-commercial
- D3 base model: Qwen2.5-Coder-7B-Instruct, prototype on 1.5B–3B first; re-check newer coders before committing
- D4 hardware: M4 MacBook Air 24GB, prototype 1.5B–3B locally with MLX; rent CUDA GPU for 7B SFT + RL (escalation)
- D5 units: mm only; rescale or drop normalized-unit samples
- D6 name: cadgen

## Success targets (written before any real baseline numbers — do not move after seeing results)
- exec rate ≥ 80% and geo_pass ≥ 60% on the 200+ task benchmark
- beat the few-shot base baseline with a non-overlapping bootstrap confidence interval
- Confirm/adjust thresholds after Stage 5 baselines per PLAN.md (any change recorded in DECISIONS.md)

## Harness (verified this session, real runs)
- `pytest -q`: 20 passed (tests/ only; `testpaths=["tests"]` added — see DECISIONS.md)
- `python scripts/smoke_test.py`: PASSED — filter ok 12/16 (pass_rate 0.75); eval exec_rate 0.75, geo_pass 0.667, mean_iou 0.697, pass@1 0.667, pass@2 1.0
- `SandboxPool().mode == "oneshot"` on this Mac (fork is Linux-only) — confirmed
- Env: Darwin ARM64, 24GB RAM, venv Python 3.14.6, cadquery 2.8.0; ollama has `ornith:9B`; mlx/mlx-lm not installed yet (Stage 3)

## Best model / eval numbers
- None yet. No real benchmark (only 12-task seed smoke test), no baselines measured.

## Open questions
- None blocking. Anticipated escalation: paid GPU rental for 7B SFT + Stage 4 RL (needs human approval).
- Next: Stage 2 — acquire real data (CAD-Coder + Text-to-CadQuery), inspect raw files, 2k pilot filter slice.
