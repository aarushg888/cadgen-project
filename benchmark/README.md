# Benchmark

## Seed smoke benchmark (`seed_tasks.jsonl`, 12 tasks)
Hand-written in `build_seed_benchmark.py` (prior session). Harness smoke test only.

## v1 benchmark (`tasks.jsonl`, 243 tasks) — AUTOMATED-QUALITY, not hand-verified
Built by `benchmark/build_v1.py --n-per-tier 120 --seed 7` (300 candidates → 243 kept):
- Tier 1 (93): template-like mechanical prompts, exact dims
- Tier 2 (70): same geometries, novel phrasing (casual / spec-sheet / minimal)
- Tier 3 (80): consumer/architectural objects (holder, frame, planter, coaster,
  bookend, table, shelf, stepped vase) — the D1 angle-A coverage
- 18 template families; all reference code defines `result`, mm, single solid.

Gates (all machine-run): (1) sandbox exec → valid single solid, dedupe code+geom;
(2) self-consistency — prompt dims vs executed bbox (10%) and analytic volume
(25%); (3) decontamination vs pilot train — prompt normalized-exact / token
Jaccard ≥ 0.85 / geometry-signature match (0 rejects: mm templates don't collide
with normalized-unit train).

Human spot-check (2026-10-04): 40/243 read by eye, 39 correct → estimated
benchmark error ~2.5%. One known template edge: small bolt circles can graze the
center hole (e.g. bench-1-008) — valid solid, dims as stated. LLM-generated
references (more diverse phrasing/geometry) are a future v2; templates were
chosen because ~4h of local generation for ~15% yield was infeasible here.
