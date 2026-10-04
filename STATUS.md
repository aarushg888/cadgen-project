# STATUS.md — cadgen current status (rewrite, don't append)

Last updated: 2026-10-04. Stage: 2 (data) — sources acquired, ingested, 2k pilot filtered.

## Decisions (D1–D6, confirmed from `configs/project.yaml` defaults)
- D1 angle: A+B+C+E; D2 license: permissive if audit allows; D3 base: Qwen2.5-Coder-7B (prototype 1.5B–3B); D4 hw: M4 Air local + rented GPU later; D5 units: mm only; D6 name: cadgen
- New since Stage 1: source adapter policy (strip export calls, synthesize `result` var, keep raw in meta) — see DECISIONS.md

## Success targets (written before any real baseline numbers — do not move after seeing results)
- exec rate ≥ 80% and geo_pass ≥ 60% on the 200+ task benchmark
- beat the few-shot base baseline with a non-overlapping bootstrap confidence interval

## Data (real runs this session)
- Acquired: CAD-Coder (8177 high + 66k middle + 157k all + val/test/CoT, ~650MB) and Text-to-CadQuery (99k train + val/test, ~1.3GB) in `data/raw/` (gitignored).
- Ingested: 8,177 cc-high + 99,236 t2cq samples. Both sources violate the contract raw (no `result`, t2cq writes `./stlcq/*.stl`); normalized via `cadgen/data/adapt.py` (4 tests pass).
- Pilot filter (cc-high adapted, n=2000, 8 workers, 817s): ok=200 (10%), dup_geometry=1577, multi_solid=126, dup_code=81, invalid=12, empty=4. Zero syntax/forbidden/timeout. **The 10% is a dedupe artifact** (0.1-unit geom signature vs 0.02–0.75-unit data), not exec quality (exec failures 7%).
- Harness (Stage 1, still green): `pytest -q` 20 passed → now 24 with adapt tests; smoke_test PASSED.

## Best model / eval numbers
- None yet. No real benchmark, no baselines measured.

## Open questions
- D5 pending: rescale normalized data to mm vs drop — blocks the 5–10k pilot split (escalation filed on license; units decision is mine, leaning rescale-then-dedupe).
- License escalation open: commercial-use rights for Text2CAD-derived sources (see ESCALATIONS.md). No training until resolved.
- Next: rescale policy + dedupe-after-rescale → 5–10k pilot split → t2cq slice → ollama baselines on seed tasks.
