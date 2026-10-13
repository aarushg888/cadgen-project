# Benchmark

## Seed smoke benchmark (current: `seed_tasks.jsonl`, 12 tasks)
- Hand-written in `build_seed_benchmark.py` (prior session): prompt + reference CadQuery per task.
- Categories: mechanical (8), consumer (2: pencil_holder, picture_frame), architectural (1: stepped_pyramid) + 1 more.
- Fully hand-checked by construction (each reference was written alongside its prompt), but tiny — it is a **harness smoke test**, not a measure of model quality.
- Quality bar: `scripts/smoke_test.py` asserts the filter keeps all 12 and rejects 4 deliberately bad samples.

## Real benchmark (Stage 2/5 deliverable — not built yet)
- Target: 200+ tasks across three tiers (in-distribution, novel phrasing, consumer/architectural).
- Planned process per AGENTS.md: synth-generate candidates → sandbox execution filter → bbox/volume self-consistency check → train-set decontamination → **automated-quality** benchmark (stated as such, not hand-verified), plus a 30–50 sample human spot-check recorded as the benchmark's error bar.
