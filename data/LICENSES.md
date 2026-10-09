# data/LICENSES.md — every data source, its license, what you may do with it.
# Nothing enters training without an entry here (AGENTS.md non-negotiable 4).

| Source | Location | License | Usable for training? | Notes |
|---|---|---|---|---|
| Seed benchmark (`benchmark/build_seed_benchmark.py` → `seed_tasks.jsonl`) | in-repo | Own / original (prior session hand-written) | Yes | 12 tasks, mechanical/consumer/architectural. Harness smoke test only, not training data. |
| CAD-Coder (`gudo7208/CAD-Coder`: train_high/middle/all, val, test, CoT) | `data/raw/cad-coder/` (gitignored, ~650MB) | Declared Apache-2.0 (LICENSE + README + dataset card, © 2025 CAD-Coder Authors) — BUT synthesized from Text2CAD 1.0, whose lineage is non-commercial | NO — pending escalation | Commercial usability unverified; see ESCALATIONS.md. Filtering/inspection only, no training. |
| Text-to-CadQuery (`ricemonster/NeurIPS11092`: 170k programs via Gemini 2.0 Flash from Text2CAD CSV) | `data/raw/text2cadquery/` (gitignored, ~1.3GB) | No license stated in repo; Text2CAD-derived + Gemini-generated | NO — pending escalation | Assume non-commercial; check Gemini ToS for training use before any reliance. Filtering/inspection only. |
| Own template synthetic (`scripts/build_synth_train.py`, wide dims, gated + decontaminated vs benchmark) | `data/raw/synth_train.jsonl` (gitignored, 7372 rows) | Own / original | Yes — the only source currently cleared for training | mm-native. Trainable regardless of escalation outcome. |

## Pending audit (do NOT train on these until rows above are filled in)
- `gudo7208/CAD-Coder` (HF dataset) — README declares Apache-2.0 but derived from Text2CAD; treat as non-commercial until verified (PLAN.md licensing warning).
- `ricemonster/NeurIPS11092` (Text-to-CadQuery, HF model-type repo) — Text2CAD lineage; assume non-commercial until verified.
- Permissive GitHub CadQuery examples — record each repo + license before use.
- Own synthetic data — check generator provider ToS for training use before relying on it commercially.
