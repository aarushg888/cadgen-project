# data/LICENSES.md — every data source, its license, what you may do with it.
# Nothing enters training without an entry here (AGENTS.md non-negotiable 4).

| Source | Location | License | Usable for training? | Notes |
|---|---|---|---|---|
| Seed benchmark (`benchmark/build_seed_benchmark.py` → `seed_tasks.jsonl`) | in-repo | Own / original (prior session hand-written) | Yes | 12 tasks, mechanical/consumer/architectural. Harness smoke test only, not training data. |

## Pending audit (do NOT train on these until rows above are filled in)
- `gudo7208/CAD-Coder` (HF dataset) — README declares Apache-2.0 but derived from Text2CAD; treat as non-commercial until verified (PLAN.md licensing warning).
- `ricemonster/NeurIPS11092` (Text-to-CadQuery, HF model-type repo) — Text2CAD lineage; assume non-commercial until verified.
- Permissive GitHub CadQuery examples — record each repo + license before use.
- Own synthetic data — check generator provider ToS for training use before relying on it commercially.
