# DECISIONS.md — one line per nontrivial choice and why (append-only).

- 2026-10-04: Use `configs/project.yaml` D1–D6 defaults as-is (standing authorization, AGENTS.md section 1; no reason to deviate before data).
- 2026-10-04: Build venv on system Python 3.14.6 (PLAN.md suggests 3.10–3.12, but `pip install -e ".[dev,llm]"` succeeded with cadquery 2.8.0, so no conda-forge needed).
- 2026-10-04: Add `[tool.pytest.ini_options] testpaths = ["tests"]` to pyproject.toml so `pytest -q` runs the 20 unit tests deterministically and never imports `scripts/smoke_test.py` (its `*_test.py` name matches pytest collection and its import-time asserts flaked once under collection).
- 2026-10-04: Initial success targets exec ≥80% / geo_pass ≥60% + beat few-shot base with non-overlapping CI, written before any baseline numbers (AGENTS.md Stage 1 acceptance); confirm after Stage 5 baselines per PLAN.md.
- 2026-10-04: All work on `agent/stage1-env-setup`, PR into `main`, human merges (AGENTS.md non-negotiable 5).
- 2026-10-04: huggingface-cli is deprecated/non-functional in huggingface_hub 1.33.0 — download via snapshot_download Python API instead (equivalent, no new installs).
- 2026-10-04: t2cq ingest uses --prompt-key input --code-key output (field names differ from ingest.py defaults; verified by head inspection first).
- 2026-10-04: normalize third-party code with cadgen/data/adapt.py (drop export/show_object lines; append `result = <last target>`; keep raw in meta) because workers run at repo cwd (export side effects) and ~85% of samples lack `result`.
- 2026-10-04: pilot 10% pass rate read as dedupe artifact (coarse 0.1-unit geom sig on normalized data), not a data-quality verdict; do not tune the filter against it — fix units first (D5).
