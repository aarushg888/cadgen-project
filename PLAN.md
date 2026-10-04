# CadGen: master plan

A fine-tuned open LLM that writes CadQuery (later Blender `bpy`) code from a text description, published on GitHub / Hugging Face. Not a startup, not an agent: prompt in, code out, run locally.

Last updated: 2026-09-27.

---

## 0. Status

**Done (Stage 0, tested):** execution sandbox, geometry metrics, data ingest / filter / split, synthetic-data generator, evaluation harness, 12-task seed benchmark. 18 unit tests plus an end-to-end smoke test pass.

Measured on the build machine with trivial parts: one-shot subprocess execution is about 2 s per sample (mostly importing CadQuery); the warm fork-server pool ran about 23 jobs/s on 4 workers. Real data with heavier geometry will be slower. Measure on your machine before planning big runs.

**Not done / not verified:**
- **All testing so far ran on Linux, not on a Mac.** On macOS the pool defaults to `oneshot` mode (a fresh subprocess per job, about 2 s each) because `fork()` after loading OCC/OpenMP libraries is not safe there. That path is tested on Linux (`CADGEN_POOL_MODE=oneshot`) but not on macOS itself. macOS also does not enforce the per-process memory cap, so only timeouts protect you.
- Everything from Stage 2 onward (real data, training, RL, real benchmark, packaging).
- The dataset field names in `ingest.py` are the common conventions. I could not reach Hugging Face from the build environment, so **inspect the real files before trusting the ingest flags** (checklist in section 7).
- Training hyperparameters below are sensible starting points from general QLoRA practice, not tuned or tested on this task.

---

## 1. Reality check: read this before building

Something close to this already exists. What I found while researching:

- **Text-to-CadQuery** (arXiv 2505.06507): fine-tuned six open LLMs on ~170k CadQuery programs generated from the Text2CAD dataset with Gemini 2.0 Flash; best model reached 69.3% top-1 exact match (up from 58.8%).
- **CAD-Coder** (NeurIPS 2025 poster, arXiv 2505.19713): chain-of-thought plus GRPO with a geometric reward. Dataset on HF: `gudo7208/CAD-Coder`, declared Apache-2.0, derived from Text2CAD. Its README says only the ~8k "high quality" subset (of ~157k synthesized) was used for actual SFT, which is useful evidence that curated small sets work.
- **A community Qwen2.5-Coder-7B CadQuery fine-tune** (MLX 4-bit) exists. Its card reports execution rate 80% vs 28% for the base model, but on only 25 test prompts, and it is CC-BY-NC-SA-4.0 because of Text2CAD lineage.
- **Products:** Zoo, Adam, Leo AI (all LLM-plus-workflow, as you noted).

So "fine-tune a 7B on CadQuery" is not novel by itself. It is still a worthwhile GitHub project, but pick an angle so it is not a fourth copy. Candidate angles (defaults I'd choose are marked):

| Angle | Why it could matter | Cost |
|---|---|---|
| **A. Consumer / non-engineering coverage** (default) | Existing data is DeepCAD-style engineering parts (sketch-extrude). Household objects, toys, decor, simple architecture in mm are underserved. | Needs synthetic data (Stage 2.5) |
| **B. Clean license** (default if achievable) | Text2CAD lineage is non-commercial. A model trained on permissive + your own synthetic data can be Apache-2.0 / MIT. | Must audit every source; check LLM provider terms for synthetic data |
| **C. Verifier-in-the-loop training** (default, Stage 4) | Reward from actually executing and comparing geometry beats imitation alone. | CPU throughput for rollouts |
| **D. Small and local** | A 1.5B–3B model that runs on a laptop via Ollama. | Lower ceiling |
| **E. A better public benchmark** (default) | The 25-prompt evaluation above shows the gap. A trustworthy 200+ task benchmark is a contribution by itself. | Hand-checking time |
| F. Blender `bpy` extension | Different ecosystem, different data. | Stage 7 |

**Decision D1 (tomorrow):** confirm A + B + C + E, or change.

**Licensing warning:** treat any dataset derived from Text2CAD as non-commercial until you verify otherwise, even if a derived repo declares a permissive license. Record every source in a license manifest (Stage 2.8).

---

## 2. Repo map

```
cadgen/
  schema.py        Sample / ExecResult dataclasses, jsonl helpers, status list
  safety.py        AST pre-check (allowed imports, forbidden names). NOT a security boundary
  runner.py        executes ONE script, applies resource limits, reports geometry facts
  forkserver.py    warm worker: imports CadQuery once, forks a throwaway child per job
  sandbox.py       run_code() one-shot; SandboxPool for high throughput (thread-safe)
  metrics.py       IoU, Chamfer, bbox/volume match, pass@k
  prompts.py       SYSTEM_PROMPT + build_messages(): the single prompt format for everything
  textutil.py      extract_code() from model output
  llm.py           OpenAI-compatible chat client (OpenAI, vLLM, Ollama, llama.cpp, LM Studio)
  data/ingest.py   third-party datasets -> canonical Sample JSONL
  data/filter.py   execute-and-filter, dedupe, stats
  data/split.py    split by design group (no leakage)
  data/synth.py    synthetic (prompt, code) generation from a strong LLM
  eval/run_eval.py benchmark harness
benchmark/         seed benchmark builder + seed_tasks.jsonl (12 smoke tasks)
scripts/smoke_test.py   end-to-end check, no model or network needed
tests/             sandbox, metrics, benchmark references
configs/project.yaml    the frozen output contract and decisions
```

Design principle: **one execution harness serves three jobs**: filtering training data, scoring evaluations, and (later) computing RL rewards. That is why it is built and tested first.

Output contract (also in `configs/project.yaml`): millimetres; code starts with `import cadquery as cq`; final object assigned to `result`; one valid solid; only `cadquery`, `math`, `numpy` and a few stdlib imports; single fenced Python block. The prompt format must be **identical** in data prep, training, evaluation and inference.

---

## 3. Stages

### Stage 0: Foundations (done)
Deliverable: the repo above. Done-when: `pytest -q` and `python scripts/smoke_test.py` pass on your machine.

Known limits to remember:
- `safety.py` and the fork server reduce accidents; they do not stop a determined malicious script. See section 4.
- IoU and Chamfer are computed after normalizing both shapes to unit size, so they are **scale-invariant**. A part that is the right shape at the wrong size scores IoU ≈ 1. That is why `geo_pass` also requires absolute bbox and volume matches. Never report IoU alone.
- IoU uses OCC boolean intersection, which can fail on messy geometry (returns 0.0). Watch how often that happens.
- Bbox match uses sorted side lengths, so it ignores orientation. Two parts with the same size but different pose can pass; IoU is computed in the shared canonical frame, so pose errors show up there.

### Stage 1: Scope and decisions (about 1–2 hours)
Tasks:
1. Resolve decisions D1–D6 (section 6).
2. Freeze the output contract and units policy. If you mix datasets with normalized coordinates and mm-based ones, the model learns an ambiguous scale. Pick one policy: rescale, tag and separate, or drop.
3. Write success targets *before* seeing results, e.g. "exec rate ≥ X% and geo_pass ≥ Y% on the 200-task benchmark, and beat the base model with non-overlapping confidence intervals." Choose X and Y after you see baseline numbers in Stage 5, then do not move them.

Done-when: `configs/project.yaml` reflects your final decisions.

### Stage 2: Data (about 2–4 days)
Goal: `data/splits/{train,val,test}.jsonl` with clean provenance.

**2.1 Acquire** (commands in section 7). Sources to start with:
- CAD-Coder dataset (`gudo7208/CAD-Coder`): files include `cad_data_train_high.json` (8,177 samples), `cad_data_train_middle.json` (66,534), `cad_data_train_all.json` (156,954), validation and test files, plus a CoT set. Format is `messages` with a `model_path` field.
- Text-to-CadQuery data (`ricemonster/NeurIPS11092` on HF, a *model*-type repo that holds `data/data_{train,val,test}.jsonl`, a zip of the 170k programs, and the Text2CAD CSV).
- Permissive GitHub CadQuery examples (search the CadQuery org and community repos; record each repo's license).
- Your own synthetic data (2.5).

**2.2 Ingest and inspect.** Run `cadgen.data.ingest`, then *read 30 samples by eye*. Check: units (normalized vs mm), whether prompts are sketch-level instructions ("draw a circle at x, y…") or object-level ("a pencil holder…"), prompt length, code style. Object-level vs sketch-level prompts are very different tasks; decide what you want. My expectation is that the DeepCAD-derived data skews sketch-level and that matters for angle A.

**2.3 Execute-and-filter.** `python -m cadgen.data.filter --dedupe-code --dedupe-geom`. Look at `stats.json`. The rejection rate is unknown until you run it; treat a very high or very low pass rate as a signal to inspect, not to celebrate. Sample `rejected.jsonl` by status.

**2.4 Dedupe.** Exact-code and geometry-signature dedupe are built in. Add near-duplicate *prompt* detection (normalized text or embeddings). Templated datasets contain thousands of near-identical prompts, which inflates benchmark scores.

**2.5 Synthetic data** (`data/synth.py`).
- Extend the concept grid a lot: 100+ object types across mechanical, consumer, toys, architecture, tools, furniture, enclosures.
- Vary phrasing style and dimension density (already in `STYLES`).
- Add a cheap prompt-code agreement check on top of execution: extract numbers from the prompt and verify plausible matches against bbox dimensions and volume. It will not catch everything; it removes a lot of confidently wrong samples.
- Optionally have a second LLM review a sample of outputs and score prompt-code faithfulness.
- Check the generator provider's terms of service for training use before you rely on the data commercially.

**2.6 Mixing.** Starting mix to test (a hypothesis, not a result): about 45% real-derived object-level samples, 45% synthetic consumer/architectural, 10% permissive GitHub examples. Ablate it in Stage 3 rather than trusting it.

**2.7 Split and decontaminate.** `data.split` splits by `group` (design id) so multiple prompts for one design cannot straddle train and test. Decontaminate the benchmark: remove any benchmark task whose prompt is a near-duplicate of a training prompt *or* whose geometry signature matches a training sample.

**2.8 License manifest.** `data/LICENSES.md`: per source, its license, where it came from, what you may do with derivatives. Nothing enters training without an entry.

Pilot size: start with 5–10k clean samples. Scale only after the first eval shows what is limiting you.

Pitfalls: mixing units silently; training on samples whose code passes execution but does not match the prompt; benchmark contamination; forgetting the license audit.

### Stage 3: Supervised fine-tuning (about 2–3 days)
**Base model.** Prior work used Qwen2.5-Coder-7B; that is a reasonable default. Check what strong open code models exist now before committing (this space moves fast and my knowledge may be stale). Iterate on a 1.5B–3B model first for speed, then repeat the best recipe on 7B.

**Stack.** Hugging Face TRL `SFTTrainer` + PEFT + bitsandbytes (QLoRA), or Unsloth / Axolotl / LLaMA-Factory. On an Apple-silicon Mac use MLX-LM LoRA.

**Starting hyperparameters** (heuristics; tune):
- 4-bit NF4 base, LoRA r=32, alpha=64, dropout 0.05, all linear layers
- learning rate 2e-4, cosine schedule, 3% warmup
- effective batch size 32, 2–3 epochs
- max sequence length 2048 (plot the token-length histogram of your data first and pick from it)
- **completion-only loss**: mask the system/user tokens
- bf16, gradient checkpointing
- apply the model's own chat template; make sure it learns to emit EOS

**Run order:**
1. Overfit 50 samples. Loss should go near zero and outputs should reproduce them. If not, your formatting or masking is broken.
2. Pilot run on 5k samples. Evaluate immediately (Stage 5 harness).
3. Scale data or model only if the eval says that is the bottleneck.

**Baselines you must report next to your model:** base model zero-shot; base model with 3–5 few-shot examples; a frontier model zero-shot; and, if licensing allows, the community fine-tune above. If your model does not beat the few-shot base on your benchmark, the fine-tune is not adding value yet.

**Compute.** A 7B QLoRA run fits on a single 24 GB GPU. Estimate time by measuring tokens/second over the first ~50 steps and extrapolating (tokens ≈ samples × avg tokens × epochs). Rented 24 GB-class GPUs are typically a low number of dollars per hour; check current prices. Keep CPU cores available for the sandbox pool, which becomes the bottleneck in Stage 4.

**Mac plan (M4 Air, 24 GB).** What I expect, from general knowledge of Apple-silicon training; measure everything before trusting it:
- Local use: build and debug the whole pipeline, run baselines through Ollama, and fine-tune a **1.5B–3B** model with MLX-LM LoRA/QLoRA on the pilot set (5k samples). 7B QLoRA may fit in 24 GB with batch size 1, short sequences and gradient checkpointing, but macOS, the browser and the sandbox workers share that memory, so treat it as a stretch, not the plan.
- The Air has no fan, so long runs throttle. Plug in, run in shorter chunks, checkpoint often, and time the first 50 steps before committing to a schedule.
- Rent a CUDA GPU (24-48 GB class) for: the main 7B SFT run, Stage 4 rollouts and GRPO. RL needs fast generation plus many CPU cores for the sandbox; a fanless laptop is the wrong machine for it.
- Shipping is fine locally: a 4-bit 7B runs on 24 GB through Ollama/llama.cpp or MLX, so the final tool will work on your machine.
- Data export: `python -m cadgen.data.to_mlx --splits data/splits/x --out data/mlx/x` writes MLX-LM chat-format files. Check `python -m mlx_lm.lora --help` for current flags and confirm the model repo names (or let mlx_lm convert/quantize the base model itself).
- Sandbox throughput in `oneshot` mode is roughly 0.5 jobs/s per worker from my Linux timing; on a 10-core Air with ~8 workers that is on the order of a few jobs/s. Filtering the ~8k "high" subset is about an hour or less; filtering 150k+ samples is many hours. Filter a subset first, or run the big filter on a rented CPU box (Linux, where `fork` mode is ~10x faster).

Pitfalls: prompt-format mismatch between train and eval; loss on prompt tokens; runaway generation from missing EOS; overfitting to templated phrasing (test on the novel-phrasing tier); silently truncated long samples.

### Stage 4: Verifier-driven improvement (about 3–5 days, only if Stage 3 shows headroom)
**4.1 Rejection-sampling fine-tuning (start here, low risk).** For each training prompt, sample k=8–16 completions at temperature ≈ 0.8 from your SFT model, execute them, keep those that pass geometry checks against the reference, add them to the dataset, retrain. This uses `SandboxPool` directly.

**4.2 GRPO / RL with a geometric reward.** CAD-Coder reports gains from a geometric reward; read the paper for their exact recipe before designing yours (I have not verified the details). Sketch of a reward: 0 if it does not execute; a base credit for a valid single solid; plus similarity terms (IoU and Chamfer on normalized shapes) **and** an absolute-dimension term (bbox and volume error) so the model cannot ignore scale.

**4.3 Guard against reward hacking:** degenerate shapes that score partial credit, timeouts used as an escape, code that exploits the fallback "last object" picker (require `result` during RL), and very short trivial outputs.

Throughput is the constraint: rollouts per second ≈ your sandbox pool's jobs/s. Put the pool on a CPU-rich machine.

### Stage 5: Evaluation (start in Stage 2, about 2 days total)
**Benchmark:** 200+ hand-verified tasks (the 12 seed tasks are a harness smoke test only), in three tiers:
1. In-distribution / template-like prompts
2. Novel phrasing of the same object types
3. Consumer / architectural objects unlike any training template

**Metrics** (all implemented): exec rate, geo_pass (executes + bbox + volume), mean IoU with failures counted as 0, median Chamfer on successful runs, pass@k for k>1.

**Statistics:** report bootstrap confidence intervals and use paired comparisons against each baseline on the same tasks. With 25 tasks a 10-point difference is noise.

**Human check:** render 50 random outputs from your model and each baseline; rate 1–5 for "is this what the prompt asked for". Automatic metrics miss features in the wrong place that still have the right volume.

**Failure taxonomy:** for a few hundred failures, label: hallucinated CadQuery API, wrong feature placement, wrong dimensions, wrong units, invalid boolean/fillet, ignored part of the prompt. This tells you what to fix next (data vs training vs reward).

### Stage 6: Ship (about 2–3 days)
- Hugging Face: LoRA adapter and merged weights; model card with data lineage, license, limitations, and the benchmark table *including baselines*.
- Quantize: merge the LoRA, convert to GGUF (Q4_K_M) with llama.cpp, add an Ollama Modelfile using `SYSTEM_PROMPT`.
- CLI: `cadgen "a pencil holder…"` → generate → execute → on failure, resample up to N times (a plain retry loop, not an agent) → write `.py`, `.step`, `.stl`.
- Viewer: a single HTML page that loads the STL with three.js so people can see results without installing CAD.
- Repo hygiene: README with 3–4 example outputs, benchmark table, license, CITATION.cff, GitHub Actions running `pytest`.
- Release only what your license manifest allows.

### Stage 7: Extensions
- **Blender:** headless `bpy` execution (sandbox differs; validity checks become watertight mesh, bbox, non-degenerate faces). Separate dataset and adapter.
- **PCB:** code-based flows (KiCad scripting or a code-first PCB tool) plus design-rule checks as the verifier. Hard, with scarce data; do it last.
- Multi-turn editing ("make the holes bigger"), image-to-CAD.

---

## 4. Sandboxing at scale

Model output is untrusted code. `safety.py` blocks obvious things and the fork server enforces timeouts and memory caps, but neither is a security boundary. For large runs (data filtering from unknown sources, RL rollouts, or any public demo), run everything in a container:

- `--network none`, `--read-only`, tmpfs for the output directory
- non-root user, `--pids-limit`, `--memory`, `--cpus`
- default seccomp profile
- one container per batch, discard after

macOS note: the memory cap in `runner.py` does nothing on macOS. On the Mac, treat the timeout as the only guard and keep generated-code experiments small, or run inside Docker Desktop with `--memory` set.

---

## 5. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Not better than existing fine-tunes | Real | Pick angle in D1; report honest baselines; benchmark contribution still stands |
| License contamination (Text2CAD lineage) | Real | License manifest; separate NC and permissive releases if needed |
| Benchmark contamination inflating results | Real | Group splits; near-duplicate and geometry decontamination |
| Synthetic data is confidently wrong | Likely | Execution filter + prompt-number check + LLM review sample + human spot checks |
| Frontier models simply overtake a 7B | Real | Emphasize local, free, offline, and your benchmark; avoid claiming general superiority |
| Sandbox throughput limits RL | Likely | Warm pool, many CPU cores, cache references |
| Time sink on infrastructure | Moderate | Pilot at 5–10k samples, 1.5B–3B model first |

---

## 6. Decisions to make (defaults in bold)

- **D1 Angle:** **A + B + C + E** (consumer coverage, clean license, verifier training, better benchmark)
- **D2 License target:** **permissive (Apache-2.0/MIT) if the data audit allows, otherwise release as non-commercial and say so**
- **D3 Base model:** **Qwen2.5-Coder-7B-Instruct, prototyped on a 1.5B–3B sibling first** (check for newer open coder models)
- **D4 Hardware: RESOLVED.** M4 MacBook Air, 24 GB unified memory, fanless. Prototype locally with MLX; rent a CUDA GPU for the 7B run and for Stage 4 (see 'Mac plan' in Stage 3)
- **D5 Units policy:** **millimetres only; rescale or drop normalized-unit samples**
- **D6 Name/repo:** working name `cadgen`

---

## 7. Tomorrow's checklist (in order)

```bash
# 1. setup and verify the framework on your machine
cd cadgen-project
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm]"
pytest -q                          # 20 tests
python scripts/smoke_test.py       # end-to-end, no network needed

# 2. download data (I could not verify these commands from the build environment)
huggingface-cli download gudo7208/CAD-Coder --repo-type dataset --local-dir data/raw/cad-coder
huggingface-cli download ricemonster/NeurIPS11092 --local-dir data/raw/text2cadquery   # model-type repo

# 3. LOOK at the raw files before ingesting
head -c 3000 data/raw/cad-coder/cad_data_train_high.json
ls data/raw/text2cadquery/data

# 4. ingest (adjust flags to what you actually saw)
python -m cadgen.data.ingest --format messages --in data/raw/cad-coder/cad_data_train_high.json \
    --out data/raw/cad_coder_high.jsonl --source cad-coder --license apache-2.0 --group-key model_path

# 5. execute-and-filter a 2,000-sample slice first; read stats.json and 30 rejects
python -m cadgen.data.filter --in data/raw/cad_coder_high.jsonl --out data/filtered/cad_coder_pilot \
    --limit 2000 --workers 8 --dedupe-code --dedupe-geom

# 6. baseline: score the base model on the seed benchmark via any local server (Ollama shown)
python -m cadgen.eval.run_eval --tasks benchmark/seed_tasks.jsonl --model qwen2.5-coder:7b \
    --base-url http://localhost:11434/v1 -n 4 --out runs/eval_base
```

Mac setup notes: create the venv with a current Python 3.10-3.12 and `pip install -e ".[dev,llm]"`. If `cadquery` fails to install from pip on your Python version, use a conda-forge environment (miniforge) instead; I could not test installation on Apple silicon. Also `brew install ollama` (or the app) and `pip install mlx-lm` when you reach Stage 3.

Then: resolve D1–D5, read 30 samples per source, and write down what you found. Do not start training until you have looked at the data and have a baseline number.
