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
