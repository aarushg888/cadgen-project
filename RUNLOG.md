# RUNLOG.md — append-only. One entry per unit of work with the real command + real output.

## 2026-10-04 — session start, AGENTS.md adopted
- Copied `~/Downloads/AGENTS.md` to repo root (`AGENTS.md`). Read `PLAN.md` + `configs/project.yaml` in full.
- Branch: `agent/stage1-env-setup` (created from `main` at 8910ac0). No STOP file present.

## 2026-10-04 — environment check (AGENTS.md section 2)
- Command: `uname -a; sysctl -n hw.memsize; python3 --version; which ollama huggingface-cli git gh; df -h .`
- Output: Darwin 27.0.0 ARM64; memsize 25769803776 (~24GB); Python 3.14.6 (system); ollama yes, huggingface-cli no (system), git yes, gh yes; disk 87% used (55Gi avail). No STOP file.
- `SandboxPool().mode` = `oneshot` (confirmed via `python3 -c "from cadgen.sandbox import SandboxPool; print(SandboxPool().mode)"` — system python; re-confirm under venv in next entry).

## 2026-10-04 — built venv, installed deps
- Commands: `python3 -m venv .venv && ./.venv/bin/pip install --upgrade pip && ./.venv/bin/pip install -e ".[dev,llm]"`
- Output: success on Python 3.14.6 — cadquery 2.8.0, cadquery-ocp 7.9.3.1.1, numpy 2.5.3, scipy 1.18.1, trimesh 5.1.1, pytest 9.1.1, openai, datasets, huggingface_hub (provides `.venv/bin/huggingface-cli`). mlx/mlx-lm NOT installed (Stage 3 per PLAN.md).
- `ollama list`: `ornith:9B` (5.6GB) available locally.

## 2026-10-04 — harness verification
- `./.venv/bin/python -m pytest tests/ -q` → `20 passed in 49.72s` (repeated: `20 passed in 102.30s`, `20 passed in 41.92s` after pyproject fix).
- `./.venv/bin/python scripts/smoke_test.py` → SMOKE TEST PASSED (3 consecutive runs). Last output:
  - `filter: {"ok": 12, "syntax_error": 1, "forbidden": 1, "runtime_error": 1, "dup_code": 1} pass_rate=0.75`
  - `eval: {"n_tasks": 12, "n_samples": 24, "exec_rate": 0.75, "bbox_acc": 0.667, "volume_acc": 0.667, "geo_pass_rate": 0.667, "mean_iou": 0.697, "median_chamfer_on_ok": 0.0, "status_counts": {"ok": 18, "syntax_error": 6}, "pass@1": 0.667, "pass@2": 1.0}`
- Flake observed once: bare `pytest -q` (system python run and one venv run) collected `scripts/smoke_test.py` (matches `*_test.py`) and its import-time asserts failed with 4 timeouts (`ok: 8` vs 12, 33s). Standalone smoke passed immediately before/after. Attributed to cold-start contention, not a harness bug. Fix: `[tool.pytest.ini_options] testpaths = ["tests"]` in pyproject.toml; after fix `pytest -q` → `20 passed in 41.92s` deterministically.

## 2026-10-04 — Stage 2.1: downloaded + inspected real data
- `./.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('gudo7208/CAD-Coder', repo_type='dataset', local_dir='data/raw/cad-coder')"` → 9 files (~650MB): train_high (17M), train_middle (146M), train_all (402M), val, test_cot, train_cot, LICENSE (Apache-2.0), README. Note: `huggingface-cli` binary is deprecated/non-functional in huggingface_hub 1.33.0 — used the Python API instead.
- `snapshot_download('ricemonster/NeurIPS11092', local_dir='data/raw/text2cadquery')` → 7 files (~1.3GB): data/{data_train,data_val,data_test}.jsonl, CadQuery.zip (98M), text2cad_v1.1.csv (1.2G), README (no license stated).
- Raw inspection (`head -c 3000`): CAD-Coder = JSON array of `{messages:[user,assistant], model_path}` — matches ingest `--format messages --group-key model_path` guess. Prompts are sketch-level (Euler angles, loops) as PLAN predicted; dims normalized (0.02–0.75 units, NOT mm); sample 0 assigns `r = cylinder` (no `result`). t2cq = JSONL `{input, output}` — needs `--prompt-key input --code-key output`; every output ends with `cq.exporters.export(assembly, "./stlcq/...stl")` (repo-relative file write!) and uses `assembly`/`part_1` (no `result`).

## 2026-10-04 — ingest (both sources)
- `python -m cadgen.data.ingest --format messages --in data/raw/cad-coder/cad_data_train_high.json --out data/raw/cad_coder_high.jsonl --source cad-coder-high --license "apache-2.0-declared;Text2CAD-derived-commercial-use-unverified" --group-key model_path` → wrote 8177, skipped 0.
- `python -m cadgen.data.ingest --format pairs --in data/raw/text2cadquery/data/data_train.jsonl --out data/raw/t2cq_train.jsonl --source t2cq --license "unknown;Text2CAD-derived-assume-non-commercial" --prompt-key input --code-key output` → wrote 99236, skipped 0.
- 200-sample probe: cc-high 33/200 mention `result`, 0 exports; t2cq 84/200 mention `result`, 200/200 contain `export`.

## 2026-10-04 — adapter (`cadgen/data/adapt.py`, new) + tests
- Why: workers run with cwd=repo root, so t2cq's `exporters.export(./stlcq/...)` would write junk into the repo or fail; and ~85% of samples lack the `result` variable the contract requires. Adapter drops export/show_object lines and appends `result = <last-assign-target>` (AST, top-level only); original kept in `meta.raw_code`, notes in `meta.adapted`.
- `pytest tests/test_adapt.py` → 4 passed (2 initial failures fixed: trailing-newline preservation, bad unparseable test case).
- `python -m cadgen.data.adapt`: cc-high 8174/8177 adapted; t2cq 99236/99236 adapted.

## 2026-10-04 — pilot filter (cc-high adapted, 2k slice)
- Command: `python -m cadgen.data.filter --in data/raw/cad_coder_high_adapted.jsonl --out data/filtered/cad_coder_pilot --limit 2000 --workers 8 --dedupe-code --dedupe-geom`
- Output: total 2000, ok=200, dup_geometry=1577, multi_solid=126, dup_code=81, invalid_geometry=12, empty=4; pass_rate=0.10; 817s (~2.4 jobs/s at 8 workers). Zero syntax/forbidden/timeout statuses.
- Reading: pass rate is a dedupe artifact, not exec quality (exec failures only 142/2000 = 7%). `_geom_sig` rounds to 0.1 units but this data lives at 0.02–0.75 units, so near-identical signatures collide en masse (rejects start at id 7, consecutive). Passed sample bbox e.g. [0.0408, 0.0408, 0.75] confirms normalized units — D5 rescale-or-drop still open. multi_solid=126 are DeepCAD multi-body parts the single-solid contract rejects.
- Next: decide rescale-to-mm policy + dedupe-after-rescale (or finer sig) before the 5–10k pilot; then t2cq slice; then baselines via ollama.

## 2026-10-04 — dup_geometry diagnosis (false collisions, not true dups)
- Probed 6 dup_geometry rejects: all distinct code hashes, 0/1577 share exact code with another dup row. Root cause: `_geom_sig` rounded volume/bbox to 1 decimal while cc-high lives at 0.02–0.75 units → mass false collisions (rejects began at id 7, consecutive).
- Fix: `_geom_sig` now rounds to 3 decimals + comment; new `tests/test_filter.py` (3 tests: identical→same, small-distinct→differ, true-dup→match). `pytest tests/test_filter.py tests/test_adapt.py` → 7 passed.
- D5 decision (recorded in DECISIONS.md, project.yaml updated): tag-and-separate. Rescaling code numbers without touching prompt numbers teaches scale mismatch; rewriting prompt numbers risks corrupting counts/angles. Normalized sources tagged `meta.units=normalized` (new `--units` flag on adapt); mm-only contract enforced for synthetic + benchmark. Nothing trained yet, so the deliberate D5 change is safe.
- Re-ran adapt from originals with `--units normalized`, re-ran 2k pilot slice: ok=1297 (0.65), dup_geometry=480, multi_solid=126, dup_code=81, invalid=12, empty=4, 1156s. Remaining 480 dups have distinct groups (no group overlap with passed) — distinct designs with near-identical normalized geometry; acceptable to exclude (near-dup prompt detection is separate future work per PLAN 2.4).
- Launched full cc-high filter in background: `--workers 8 --dedupe-code --dedupe-geom`, out `data/filtered/cc_high_full`, nohup PID 53734, log `data/filtered/cc_high_full.log`.

## 2026-10-04 — environment lesson: background exec starves, foreground works
- Launched full cc-high filter (8177) via nohup/background: after 10min wall only 0:04 CPU, 0 bytes out, workers spawned but starved. Killed it (and strays), removed partials. Lesson: this environment suspends background process groups between tool calls — all heavy runs must be foreground with generous timeouts.
- Added `--offset` to `cadgen.data.filter` (skip-first-N) for chunked/resumable runs; verified offset=2000 starts at cad-coder-high-2000. smoke_test caller uses keywords — unaffected.

## 2026-10-04 — cc-high full filter (3 foreground chunks, 8 workers, dedupe-code+geom)
- c1 (0–2800): ok=1691, dup_geom=747, multi=182, dup_code=159, invalid=17, empty=4; 1841s
- c2 (2800–5600): ok=1657, dup_geom=790, multi=153, dup_code=186, invalid=11, empty=1, runtime=1, syntax=1; 1844s
- c3 (5600–8177): ok=1514, dup_geom=664, multi=156, dup_code=224, invalid=17, empty=2; 1431s
- Total: 4862/8177 passed (59.5%). Note: dedupe sets reset per chunk, so cross-chunk dups leak — group-aware split (model_path) still prevents train/test leakage; benchmark decontamination uses the same geom method at build time.
- Next: t2cq 2k slice → merge chunks → group-aware pilot split → ollama baselines.

## 2026-10-04 — t2cq 2k slice + pilot split (Stage 2 data acceptance met)
- `python -m cadgen.data.filter --in data/raw/t2cq_train_adapted.jsonl --out data/filtered/t2cq_slice --limit 2000 --workers 8 --dedupe-code --dedupe-geom` → ok=1465 (0.73), multi_solid=271, dup_geom=136, dup_code=83, invalid=21, runtime=14, empty=9, forbidden=1; 1210s. Different profile vs cc-high: more multi-body, fewer dups.
- Reject sampling: `forbidden` = `import os` (correct rejection, not adapter-stripped by design); runtimes = hallucinated APIs (`cutHole`, `fuse` method, `addLoft`, `hole(center=)`), invalid booleans (`BRep_API: command not done`), empty-stack errors. Filter works as designed — taxonomy noted for Stage 4.
- Merged cc-high chunks → `data/filtered/cc_high_full/` (passed 4862, rejected 3315, stats.json recomputed with cross-chunk-dedupe caveat).
- Pool 6327 (4862 cc-high + 1465 t2cq) → `python -m cadgen.data.split --val 0.1 --test 0.1 --seed 1234` → `data/splits/pilot/`: train 5052 / val 624 / test 651. Group overlap across splits: 0 (verified). Split ratio 80/10/10 chosen over default 96/2/2: 2% val (~120) too thin to catch overfitting in Stage 3. t2cq rows have no design key (id-bucketed, weaker) — noted; geometry dedupe already applied pre-split.

## 2026-10-04 — zero-shot baseline: ornith:9B on seed tasks (n=1 effective)
- Ollama serves `ornith:9B` (qwen35 9B Q4_K_M). First try (4 parallel × n=4 via run_eval --model) died with openai.APITimeoutError — 9B+thinking on a fanless Air cannot take parallel load. Single probe: 42.7s, correct cylinder code.
- Fell back to sequential generation (12 tasks × n=4 requested) → discovered ollama's OpenAI endpoint ignores `n` and returns 1 choice. Result: runs/ornith_zero_gens.jsonl has 12 rows (1/task). Fences present in only 9/12 task outputs; extract_code whole-text fallback handled the rest.
- `python -m cadgen.eval.run_eval --tasks benchmark/seed_tasks.jsonl --generations runs/ornith_zero_gens.jsonl --out runs/eval_ornith_zero` → n=12, exec_rate 0.333 (4/12), geo_pass 0.25 (3/12), mean_iou 0.28, pass@1 0.25. Statuses: ok 4, runtime_error 5, no_result 3.
- Failure taxonomy (zero-shot, feeds Stage 4): hallucinated APIs (Solid.union, Workplane.moveZ, `python` NameError from prose leak), Wire/Solid→vector conversion errors, no `result` variable ×3, one executes-but-wrong (hex_nut IoU 0.36).

## 2026-10-04 — benchmark v1 built (Stage 2 acceptance: 243 tasks)
- Chose template-generated over LLM-synth (documented in README + DECISIONS): 300 local generations ≈ 4h for ~15% end yield; templates emit exact (prompt, code, expected-geometry) in seconds and still pass every gate.
- Wrote `benchmark/build_v1.py`: 18 emitters (10 mechanical, 8 consumer/arch), 4 phrasing styles, analytic bbox+volume per template; gates = sandbox filter (dedupe) → bbox_match 10% + volume_match 25% vs expected → decontam vs pilot train (prompt exact/Jaccard 0.85/geom-sig).
- Debugging found by gates (all fixed, verified by measurement): polygon(6,d) circumscribes (AF = across corners; measured bbox [14, 12.12, 6], vol 763.8); shelf had an invalid leading-dot continuation (syntax_error → 0 survivors before fix).
- Full run `--n-per-tier 120 --seed 7`: 360 candidates → gate1 ok 243 (+2 multi, 113 dup_code, 2 dup_geom) → gate2 243/243 → decontam 0 rejects → final 243 (T1 93 / T2 70 / T3 80, all 18 families). `benchmark/tasks.jsonl` + `benchmark/report.json`.
- Spot-check 40/243 by eye: 39 correct (1 template edge: bolt circle grazing center hole, bench-1-008) → benchmark error ≈ 2.5%, recorded in STATUS.md.

## 2026-10-07 — infra fight: ollama 256k-ctx wedged, moved to :11435 + think:false
- Symptom: gens slowed 43s → 2.6min, then HF pull + probes hung. Root causes found: (1) ornith:9B loaded with 262144 ctx → llama-server held 13.4GB/53% RAM, swap thrash; (2) backend wedged in "Stopping..." (swap-thrash victim).
- Recovery: `ollama stop` hung → killed worker; old `ollama serve` (mine, Sunday) replaced. NOTE: port 11434 is now held by sridhargutha108's server — mine runs on 11435 (`OLLAMA_HOST=127.0.0.1:11435`). Do NOT kill their process. The old server's ornith:9B/8k manifests are gone with it; recreated ornith-8k (num_ctx 8192) from the surviving GGUF blob in ~/.ollama via FROM-local-file (deleted 5.2GB /tmp copy after).
- Speed fix: native-API `think:false` → 56 tokens in 3.6s eval (30x). Extended `ChatClient(think=...)` (native /api/chat when set; OpenAI path otherwise) + `tests/test_llm.py` (2 tests) + script flags `--think/--max-tokens`. Baseline config: ornith-8k, temp 0.2, max_tokens 1024, think false. DIFFERS from seed n=1 baseline (thinking-enabled) — noted, not mixed.

## 2026-10-07 — 243-task zero-shot baseline (ornith-8k, think:false, n=1)
- 3 sequential chunks (80/80/83): runs/ornith8k_bench_gens.jsonl (243 rows) → `run_eval --workers 8` → runs/eval_bench_ornith8k/.
- Summary: exec 0.218 [0.165, 0.272], geo_pass 0.107 [0.070, 0.148] (bootstrap 10k), mean IoU 0.110, pass@1 0.107. Statuses: runtime 178, ok 53, forbidden 8 (all `__import__`), syntax 4 (long/truncated).
- Per tier: T1 exec 0.280/geo 0.151, T2 0.214/0.157, T3 0.150/0.013 — tiers discriminate as designed (consumer/arch crushes zero-shot).
- Failure modes: TypeError 70, ValueError 43, NameError 35 (incl. `show_object` leaks), AttributeError 28 (hallucinated APIs). Targets (0.80/0.60) sit far above baseline upper bounds — headroom confirmed.

## 2026-10-08 — few-shot baseline on 243-bench (3 seed examples, same gen config)
- Full-run scoring kept dying at the 60-min tool timeout: NOT a hang (verified piece by piece + 82-task instrumented run) — few-shot outputs are longer/more complex, ~9-40s/task end-to-end. Scored in 2 slices (122 + 121) and merged with identical formulas + bootstrap 10k.
- Merged (`runs/eval_bench_ornith8k_fewshot/`): exec 0.650 [0.588, 0.712], geo_pass 0.325 [0.267, 0.383], mean IoU 0.418. Statuses: ok 158, runtime 74, invalid 8, syntax 2, empty 1.
- Per tier (exec/geo): T1 0.699/0.376, T2 0.657/0.400, T3 0.588/0.200 (T3 geo 0.013 → 0.200 with examples).
- vs zero-shot (0.218 [0.165,0.272] / 0.107 [0.070,0.148]): non-overlapping CIs — the bar for Stage 5 is the FEW-SHOT number (exec 0.65 / geo 0.33), a much tougher target that reframes headroom.
