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
