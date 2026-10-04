# DECISIONS.md — one line per nontrivial choice and why (append-only).

- 2026-10-04: Use `configs/project.yaml` D1–D6 defaults as-is (standing authorization, AGENTS.md section 1; no reason to deviate before data).
- 2026-10-04: Build venv on system Python 3.14.6 (PLAN.md suggests 3.10–3.12, but `pip install -e ".[dev,llm]"` succeeded with cadquery 2.8.0, so no conda-forge needed).
- 2026-10-04: Add `[tool.pytest.ini_options] testpaths = ["tests"]` to pyproject.toml so `pytest -q` runs the 20 unit tests deterministically and never imports `scripts/smoke_test.py` (its `*_test.py` name matches pytest collection and its import-time asserts flaked once under collection).
- 2026-10-04: Initial success targets exec ≥80% / geo_pass ≥60% + beat few-shot base with non-overlapping CI, written before any baseline numbers (AGENTS.md Stage 1 acceptance); confirm after Stage 5 baselines per PLAN.md.
- 2026-10-04: All work on `agent/stage1-env-setup`, PR into `main`, human merges (AGENTS.md non-negotiable 5).
