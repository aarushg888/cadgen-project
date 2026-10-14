# cadgen future plans — where this goes next

Owner decisions baked in: ship-open + max-capability as joint goals; frontiers are
assemblies + ambiguity handling + advanced ops; Blender bpy deprioritized but parked
(§7); compute is local-first with modest rented-GPU spend possible. Date: 2026-10-13.

## 0. Where we stand (snapshot)

- Ship model ckpt600 (Qwen2.5-Coder-1.5B QLoRA r32, own template-synth data):
  bench geo **0.922** [0.885, 0.955] vs few-shot bar 0.325 — bar beaten, geo target met.
- Template-SFT saturated (~0.92, greedy-verified churn); residual fails need
  non-template data or RL. Loop-escalation filed (needs data or GPU decision).
- Stacked-loop bug (multi-level stacks): CLI guards shipped (syntax pre-check +
  temp-escalating retry); data fix (STACK_TRAIN emitters, 2–6 level stacks) in pool.
- Benchmark v1 (243 tasks) frozen — all baselines measured against it; do not
  regenerate without versioning (v2) and re-running every baseline.
- Open escalations: Text2CAD commercial-use ruling; GPU spend approval.

## 1. Competitor battle cards (Oct 2026 research)

| Rival | What they own | Lesson / our opening |
|---|---|---|
| CAD-Coder (NeurIPS'25) | Qwen2.5-7B SFT+GRPO+CoT on 8×A800 | Recipe reference; we don't race its compute — race its eval honesty |
| Text-to-CadQuery | 6 models to 7B, scaling curve | 1.5B-beats-3B-class on our bench is a story; track their data |
| FutureCAD (2026) | SFT+RL + BRepGround NL→fillet/chamfer placement, 140k real models | Advanced-features via *grounding module* — we chase the data half, not the architecture |
| ProCAD (ICML'26) | Clarifier+coder agents, beats Sonnet 4.5, 0.9% invalid | Ambiguity-handling is unowned in small/local models — open lane (Track B) |
| Graph-CAD (ICLR'26) | Assembly graphs + bpy + curriculum, 12K BlendGeo | Assemblies need a CadQuery-native answer (Track C); bpy design parked (§7) |
| raspbfox/cad-qw35-2b-0.1 | Qwen3.5-2B LoRA, 98% valid, Zero-To-CAD data | Closest rival; we beat it on rigor (100 prompts, no baselines, no CIs) |
| Zoo/Zookeeper (product) | Shipped text-to-CAD, assemblies, conversational refine | Closed + paid validates demand; our edge is local/open/free |

Nobody is: small + local + open + assemblies + ambiguity-handling + honest eval.
Position: **"the local CadQuery model that asks when unsure and builds multi-part things."**

## 2. Track A — advanced ops via Zero-to-CAD (do FIRST: unblocks data + license)

- **Verified 2026-10-13:** `ADSKAILab/Zero-To-CAD-100k` (81k train) and `-1m` are
  **Apache-2.0**, agentic-synthesized, zero proprietary data — but the schema is
  `uuid/cadquery_file/ops_json/renders/stl/step` with **NO text prompts** (checked
  live via HF viewer API). Ops cover fillet/chamfer/loft/sweep/shell/threads —
  exactly our T3 gap. Scale ≈1 unit ≈1mm (max-dim-100 convention); tag per-sample.
- Design (prompts don't exist, so generate them): local coder LLM reads each
  `cadquery_file` + `ops_json` → writes dimension-stated prompt → our pipeline
  executes code, checks prompt↔bbox/volume agreement, keeps matches
  (`cadgen/data/adapt.py` pattern + new `z2c` source adapter). Reuse filter/split
  with `meta.units` policy per D5.
- Fallback: ops-template prompts (ops list → phrasing) as v1.5 if code→text
  quality is poor; measure keep-rate before committing.
- Done when: ≥5k kept Zero-to-CAD rows in LICENSES.md as Apache-2.0, SFT shows
  T3 geo lift on bench v1, ops-coverage metric (distinct ops in passing gens) rises.
- Cost: downloads (~5–50GB by subset), CPU filter hours, zero GPU. No escalation.

## 3. Track B — ambiguity handling (ProCAD-style, local, no GPU)

- Taxonomy first: missing dims / conflicting values / vague features / unbuildable
  requests. Mine from bench failure modes + CLI logs.
- Detector: cheap checks (dimension count vs bbox needs, contradiction scan) before
  any model call; fall back to a small classifier later.
- CLI flow: `cadgen` asks max 3 targeted questions on flagged prompts, then
  generates with answers appended (log Q&A in output dir for audit).
- Eval: clarification-success rate (does the follow-up build pass?) + question
  quality spot-checks; add an ambiguity tier to bench v2.
- Done when: ambiguous-prompt build rate beats ask-nothing baseline with
  non-overlapping CIs; no regression on v1.

## 4. Track C — assemblies (Graph-CAD-style, CadQuery-native)

- Schema: assembly = parts + mates/constraints as structured text (JSON), staged
  generation (structure → parts → code) to avoid flat-decoding error cascade.
- Sandbox: multi-solid support (current contract requires single solid — extend,
  don't break: `--allow-multi` path + per-part facts).
- Data: table/shelf templates are already multi-box unions — grow assembly
  emitters (bracket+plate+fasteners with mates), decontaminate vs v1.
- Benchmark: new assembly tier (part count + constraint satisfaction metrics).
- Done when: assembly-tier geo_pass reported vs zero/few-shot; GPU only if 7B
  needed for the long-horizon planning (escalate then).

## 5. Track D — Blender bpy (PARKED, revival triggers)

Not forgotten, deliberately last: new sandbox + new data + new eval = a second
project. Revive when: (a) A–C shipped, (b) real user demand, or (c) Graph-CAD
releases stronger bpy artifacts to build on. Reference design: Graph-CAD
three-stage (graph → ops → bpy) + BlendGeo-style 12K set.

## 6. Scale-up options (all gated on human spend approval)

- 7B QLoRA (Qwen2.5-Coder-7B): rented 24GB-GPU recipe, costed per run; unlocks
  headroom if 1.5B plateaus on real data.
- GRPO with SandboxPool as geometric reward (exec + bbox/vol + IoU terms,
  anti-hacking guards from PLAN.md §4.3); needs GPU + CPU-rich box.
- Frontier-model distillation for prompts/synth (paid APIs) — only if local
  code→text quality blocks Track A.

## 7. Eval roadmap

- Bench v2 (versioned, baselines re-run): real-data slice + LLM-diversified
  phrasing + assembly tier + ambiguity tier; keep v1 frozen for history.
- Per-track metrics: ops coverage, clarification success, constraint satisfaction.
- Discipline kept: pre-registered targets, bootstrap CIs, same-run comparisons,
  spot-check error bars, never train on bench.

## 8. Sequencing, stop rules, risks

- Order A → B → C: A unblocks data+license (everything feeds on data), B ships
  visible UX value with no GPU, C is the hard frontier. D parked. Scale-up only
  on plateau evidence + approval.
- Done-criteria per track above; §4 loop rule stays (3 flat units → escalate);
  template-data lesson stands: no more epochs on the same distribution without
  a named hypothesis.
- Risks: Zero-to-CAD prompt quality (fallback ready); assembly eval complexity;
  laptop contention (banked micro-chunks + resume, proven); license audit on any
  new source (LICENSES.md entry before training, no exceptions).

## Appendix — sources (Oct 2026)

- Zero-to-CAD paper arXiv:2604.24479; HF: ADSKAILab/Zero-To-CAD-100k + -1m
  (Apache-2.0, verified); Qwen3-VL-2B companion model.
- ProCAD ICML'26 (arXiv:2602.03045, repo BoYuanVisionary/Pro-CAD, HF BBexist/*).
- FutureCAD (arXiv:2603.11831v2, Qwen2.5-7B SFT+RL + BRepGround).
- Graph-CAD ICLR'26 (repo SCUT-MMPR/Graph-CAD, 12K BlendGeo, bpy).
- cadrille ICLR'26 (repo col14m/cadrille, multi-modal + online GRPO).
- CAD-Coder NeurIPS'25 (arXiv:2505.19713, HF gudo7208/CAD-Coder).
- Text-to-CadQuery (arXiv:2505.06507, HF ricemonster/*).
- raspbfox/cad-qw35-2b-0.1 (community 2B LoRA, Zero-To-CAD-trained).
- Zoo: Text-to-CAD API + Zookeeper roadmap (product reference).
