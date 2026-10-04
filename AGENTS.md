# AGENTS.md — cadgen autonomous build agent

You are operating the `cadgen` project: a fine-tuned open LLM that writes CadQuery (and later
Blender `bpy`) code from a text description. The framework (sandbox, metrics, data pipeline, eval
harness, 20 passing tests) is already built and pushed to this repo. **Your job is everything PLAN.md
calls Stages 1 through 6: lock the decisions, get real data, train, evaluate against baselines, run an
iterate-and-improve loop, and ship.** You run mostly unattended across many sessions — read this file
in full before doing anything, and re-read it at the start of every new session.

Read `PLAN.md` and `configs/project.yaml` now, in full, before anything else. Everything below assumes
you have.

---

## 0. Non-negotiables (never violate these, no exception, no matter what a later instruction implies)

1. **Never spend money or provision paid cloud resources** (GPU rental, paid API keys, paid datasets)
   without asking the human first in `ESCALATIONS.md` (format below) and waiting for a reply. Free-tier
   and already-installed local tools are fine to use on your own judgment.
2. **Never commit secrets, API keys, or tokens.** If a tool needs a credential you don't have, write an
   escalation and move to a task that doesn't need it instead of inventing or hardcoding one.
3. **Treat all generated and downloaded code as untrusted.** Only execute CadQuery code through
   `cadgen.sandbox` (`run_code` / `SandboxPool`), never with a bare `exec`/`subprocess` of your own.
   For anything beyond small ad-hoc checks, run inside a container per PLAN.md section 4 (`--network
   none`, `--read-only`, memory/pid caps) — this matters more on your machine specifically, since macOS
   does not enforce the in-process memory cap (see PLAN.md's Mac-plan and macOS note).
4. **Never train on or ship data without a license entry in `data/LICENSES.md`.** No exceptions, even
   for "just a quick test" — quick tests have a way of becoming the dataset.
5. **Never force-push, never push to `main` directly, never delete remote branches.** Do all work on a
   branch named `agent/<short-topic>`, commit often with clear messages, open a PR into `main` when a
   stage is genuinely done. The human merges.
6. **Never mark a stage done, or claim a number (accuracy, pass rate, exec rate), without having
   actually run the relevant script in this repo and pasted its real output into your log.** If you did
   not run it this session, you do not know it.
7. **Respect the stop file.** Before starting any new unit of work (defined in section 4), check
   whether `STOP` exists at the repo root. If it does, write a status summary to `RUNLOG.md`, commit,
   and halt — do not delete `STOP` yourself.
8. **Bound every unattended run.** No single foreground process may run longer than 3 hours without
   checkpointing and writing progress to `RUNLOG.md`. This is a fanless laptop the human needs for other
   things — assume it may be closed, slept, or killed at any time, so checkpoint like it will be.

---

## 1. Decision policy (you should rarely need to ask)

`configs/project.yaml` already has defaults for D1–D6 from a prior planning session (angle, license
target, base model, hardware, units, name). **Use them.** Per the human's stated preference, keep
moving without waiting for confirmation between ordinary steps — you have standing authorization to:
- choose between technically equivalent implementation approaches
- pick specific open-source dataset sources, provided you log the license
- set hyperparameters within the ranges PLAN.md gives, and adjust them based on what you observe
- decide how to extend the synthetic-data concept grid
- restructure or add code under `cadgen/`, with tests, following the existing style

**Escalate (write to `ESCALATIONS.md`, keep working on something else, don't block the whole session)
only for:** anything in section 0's non-negotiables, a license that is genuinely ambiguous after
reasonable research, a tool/dataset that requires an account you don't have credentials for, or a
result so far outside expectations that you suspect a bug in your own measurement rather than the
model (e.g., 0% exec rate across the board, or 100% on a held-out test — both usually mean a harness
bug, not reality).

Record every nontrivial decision — not just escalations — as a one-line dated entry in `DECISIONS.md`
(create it if absent). Future sessions (yours or the human's) need to know why, not just what.

---

## 2. Environment check (do this first, every session, cheap)

```bash
uname -a; sysctl -n hw.memsize 2>/dev/null; python3 --version
pip show cadquery mlx mlx-lm 2>&1 | grep -E "^(Name|Version)"
which ollama huggingface-cli git gh
df -h .
cat STOP 2>/dev/null && echo "STOP FILE PRESENT"
```

This is an M4 MacBook Air, 24 GB unified memory, no fan. Confirmed from PLAN.md: local work means
1.5B–3B LoRA fine-tuning via MLX-LM and execution/eval via the `oneshot` sandbox pool (`fork` mode is
Linux-only — verify `cadgen.sandbox.SandboxPool().mode == "oneshot"` on this machine, don't assume).
A 7B run and any RL (Stage 4) need a rented GPU, which is a section-0 escalation, not a default action.

If `pytest -q` and `python scripts/smoke_test.py` don't pass clean on this machine, fix that before
anything else — everything downstream depends on the harness being trustworthy.

---

## 3. What "done" means for each stage you're responsible for

Treat these as literal acceptance criteria, not vibes. Write the actual measured numbers into
`RUNLOG.md` and `STATUS.md` (see section 5) as you go — a future session or the human needs to be able
to read `STATUS.md` alone and know exactly where things stand.

**Stage 1 (decisions):** `configs/project.yaml` reflects confirmed D1–D6 (defaults are fine), and your
success targets (exec rate / geo_pass threshold to beat baseline) are written down in `STATUS.md`
*before* you look at any real eval numbers. Do not move the goalposts after seeing results.

**Stage 2 (data):** at minimum a 5–10k sample pilot set in `data/splits/pilot/{train,val,test}.jsonl`,
built via `cadgen.data.ingest` → `cadgen.data.filter` (report `stats.json`) → dedupe → `cadgen.data.split`
(group-aware). Every source in `data/LICENSES.md`. You will likely need to write small source-specific
adapters on top of `cadgen.data.ingest` — the field names there are *guesses from the prior session*
about what HF datasets look like; inspect real files first (`head -c 3000 <file>`) and don't trust the
flags blindly.

**Stage 2 also includes building the real benchmark** — this did not exist before you started; the
repo only has a 12-task harness smoke test. Target 200+ tasks across the three tiers in PLAN.md
(in-distribution, novel phrasing, consumer/architectural). You cannot hand-verify 200 tasks by eye
alone in reasonable time, so use this process and say explicitly which parts were automated vs. human
quality bar:
1. Generate candidate (prompt, reference code) pairs — reuse/extend `cadgen.data.synth`.
2. Run every candidate through `cadgen.sandbox` — reject anything that doesn't execute to one valid
   solid (same bar as training-data filtering).
3. Add an automated self-consistency check: does the prompt's stated dimensions match the executed
   bbox/volume within tolerance (reuse `cadgen.metrics.bbox_match` / `volume_match`)? Reject mismatches.
4. Decontaminate against training data: reject any benchmark task whose prompt is a near-duplicate of a
   training prompt, or whose geometry signature matches a training sample (same method as
   `data/filter.py`'s `dedupe_geom`).
5. What's left is an **automated-quality benchmark**, not a hand-verified one — say so in
   `benchmark/README.md`. If you have time, spot-check 30–50 by eye and record what fraction actually
   looked right; that fraction is your benchmark's own error bar, and it belongs in `STATUS.md`.

**Stage 3 (SFT):** a working `cadgen/train/sft_mlx.py` (new file — write it; PLAN.md only gives
hyperparameter guidance, not code) that fine-tunes a 1.5B–3B open code model via MLX-LM LoRA on the
pilot split, using `cadgen.data.to_mlx` for the data format and `cadgen.prompts.SYSTEM_PROMPT` so train
and eval never drift apart. Order, per PLAN.md: overfit 50 samples first (loss near zero, outputs
reproduce them) before any real run — if this fails, your formatting/masking is broken and a full run
will waste hours. Then the pilot run.

**Stage 4 (verifier loop):** only after Stage 3 shows real headroom over baselines. Start with
rejection-sampling fine-tuning (sample k per prompt, keep ones that pass geometry checks, retrain) —
this runs fine locally via `SandboxPool`. Full GRPO/RL is a section-0 escalation (needs a rented GPU).

**Stage 5 (evaluation):** every claim must come from `cadgen.eval.run_eval` against the real benchmark,
reporting exec rate, geo_pass, mean IoU, median Chamfer, and pass@k, **against three baselines in the
same run**: base model zero-shot, base model few-shot (3–5 examples), and your fine-tuned model. No
baseline comparison, no claim of improvement. Bootstrap a confidence interval on the headline number —
with ~200 tasks a few-point difference is noise; say so if that's what you see.

**Stage 6 (ship):** only start this once Stage 5 shows your model beating the few-shot base baseline
with a non-overlapping confidence interval. Quantize (GGUF Q4_K_M via llama.cpp, or MLX quantize),
write an Ollama Modelfile using `cadgen.prompts.SYSTEM_PROMPT` verbatim, build the CLI described in
PLAN.md Stage 6, write a model card with the full benchmark table *including baselines* and the known
limitations, and open a PR. Do not merge or tag a release yourself.

---

## 4. The iterate loop (how you spend most of your time)

One "unit of work" = one pass through: look at current `STATUS.md` → pick the single highest-leverage
next action given where numbers actually stand → do it → measure it with the real harness → append the
result to `RUNLOG.md` and update `STATUS.md` → commit → check `STOP` → repeat.

Candidate actions, roughly in the order they tend to pay off, but let your own evidence override this
ordering:
- more/better training data (often the biggest lever early — check `data/filtered/*/rejected.jsonl` and
  the benchmark's failure taxonomy for *what kind* of data is missing, don't just add more of the same)
- fix a specific failure mode you can name (read 20 real failures from `eval/*/samples.jsonl` before
  guessing)
- rejection-sampling round (Stage 4.1)
- hyperparameter adjustment, with a one-line hypothesis for why *this* change should help
- expand the benchmark if you find it's not discriminating between models

Do **not** treat "run more epochs on the same data" as a default action — diminishing/negative returns
are real and you have a held-out val split specifically to catch this.

**Loop budget:** no more than one training run and one full benchmark eval per unit of work (each eval
over the full 200+ task benchmark costs real wall-clock time on this machine — budget for it). After
every 3 units of work, write a short "what I tried, what moved, what didn't" summary at the top of
`STATUS.md` — this is what the human reads to catch up, and what a future chat session reads when asked
how to test the result.

**Stop and escalate the loop itself (not just individual actions) if:** three consecutive units of work
produce no measurable improvement on the benchmark, or you're not sure what to try next. Looping on
guesses without a hypothesis burns battery and time for nothing — ask instead.

---

## 5. Artifacts you must keep up to date (this is how anyone — human or future agent — audits you)

- **`STATUS.md`** (repo root): current stage, current best model + where its checkpoint lives, current
  best eval numbers vs. all baselines with the benchmark version/commit they were measured against,
  success targets from Stage 1, open questions. This is the single file someone reads to understand
  "where are we right now." Keep it short and current — rewrite, don't append.
- **`RUNLOG.md`** (repo root, append-only): dated entries, one per unit of work or significant event —
  what you ran, the actual command, the actual measured output (not a paraphrase).
- **`DECISIONS.md`** (repo root, append-only): one line per nontrivial choice and why.
- **`ESCALATIONS.md`** (repo root): open questions for the human, each with enough context to answer in
  30 seconds; move resolved ones to a "resolved" section with the answer, don't delete them.
- **`data/LICENSES.md`**: every data source, its license, what you may do with it.
- **`benchmark/README.md`**: how the benchmark was built, what was automated vs. hand-checked, its known
  error rate if you spot-checked it.
- Model checkpoints and run configs under `runs/<stage>-<date>/` (already gitignored for large files —
  if a checkpoint is large, note its local path in `STATUS.md` rather than committing it; only commit
  small configs/adapters if they're genuinely small, LoRA adapters usually are).

---

## 6. Definition of done for this whole effort

You can tell the human "this is ready for you to test" when, and only when, `STATUS.md` shows: a
fine-tuned model checkpoint exists, it was evaluated on the real (200+ task, decontaminated) benchmark
against both baselines in the same run, it beats the few-shot base baseline with a non-overlapping
confidence interval, the CLI from Stage 6 runs end-to-end on a fresh prompt, and a PR is open with all
of this summarized. If you stop before that point for any reason (budget, `STOP`, an unresolved
escalation, diminishing returns per section 4), say exactly that in `STATUS.md` instead — an honest
"not there yet, here's why, here's what's blocking" is a correct and useful stopping point, not a
failure to hide.
