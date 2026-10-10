"""SFT via MLX-LM LoRA on the pilot/overfit splits (Apple-silicon plan, PLAN.md Stage 3).

Prompt format comes from cadgen.data.to_mlx (single source with eval), and
--mask-prompt gives completion-only loss. Rank/scale/dropout go through a YAML
config (mlx-lm uses `scale`, not PEFT `alpha`; scale=20 is the mlx default the
library was tuned around — the 50-sample overfit is the empirical check).

    # 1. overfit first: loss must go near zero or formatting/masking is broken
    python -m cadgen.train.sft_mlx --overfit --data data/mlx/overfit50 --adapter runs/overfit50/adapter
    # 2. pilot run (epochs over train split)
    python -m cadgen.train.sft_mlx --data data/mlx/synth --adapter runs/sft-synth-v1/adapter --epochs 2

Checkpoints live under runs/ (gitignored); only the command + loss tail go to RUNLOG.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# NOTE (2026-10-09): scale=20 (mlx default) + lr 2e-4 NaN'd at iter 20 with rank 32;
# scale=2.0 + lr=1e-4 is stable (30-iter probe: 1.48 -> 0.10). Culprit (scale vs lr)
# unisolated; this working point is what the overfit validated.
PLAN_DEFAULTS = dict(
    rank=32, scale=2.0, dropout=0.05,        # LoRA (scale is mlx's alpha knob)
    lr=1e-4, batch_size=4, max_seq_length=2048,
    num_layers=-1,                           # all linear layers per PLAN
)


def build_cmd(a) -> tuple[list[str], dict]:
    # mlx-lm takes LoRA rank/scale/dropout ONLY as nested `lora_parameters`
    # (flat keys are silently ignored — verified against LORA.py CONFIG_DEFAULTS)
    cfg_text = ("lora_parameters:\n"
                f"  rank: {a.rank}\n"
                f"  scale: {a.scale}\n"
                f"  dropout: {a.dropout}\n")
    os.makedirs(a.adapter, exist_ok=True)
    cfg_path = os.path.join(a.adapter, "lora_config.yaml")
    with open(cfg_path, "w") as f:
        f.write(cfg_text)
    if a.overfit:
        iters, eval_every, val_batches = a.iters or 300, 0, 0
    else:
        n_train = sum(1 for _ in open(os.path.join(a.data, "train.jsonl")))
        iters = a.iters or max(1, int(a.epochs * n_train / a.batch_size))
        eval_every, val_batches = a.steps_per_eval, -1
    cmd = [sys.executable, "-m", "mlx_lm", "lora",
           "--model", a.model, "--data", a.data, "--train",
           "--mask-prompt", "--fine-tune-type", "lora",
           "--num-layers", str(a.num_layers), "--batch-size", str(a.batch_size),
           "--iters", str(iters), "--learning-rate", str(a.lr),
           "--max-seq-length", str(a.max_seq_length),
           "--adapter-path", a.adapter, "--seed", str(a.seed),
           "--save-every", str(a.save_every), "--steps-per-report", str(a.steps_per_report),
           "--config", cfg_path]
    if a.grad_checkpoint:
        cmd.append("--grad-checkpoint")
    if a.resume:
        cmd += ["--resume-adapter-file", a.resume]
    if eval_every:
        cmd += ["--steps-per-eval", str(eval_every), "--val-batches", str(val_batches)]
    return cmd, {"iters": iters, "rank": a.rank, "scale": a.scale, "dropout": a.dropout}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="data/raw/models/qwen25coder15b-4bit")
    ap.add_argument("--data", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--overfit", action="store_true", help="50-sample smoke: iters=300, no eval")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--iters", type=int, default=None)
    ap.add_argument("--lr", type=float, default=PLAN_DEFAULTS["lr"])
    ap.add_argument("--batch-size", type=int, default=PLAN_DEFAULTS["batch_size"])
    ap.add_argument("--max-seq-length", type=int, default=PLAN_DEFAULTS["max_seq_length"])
    ap.add_argument("--num-layers", type=int, default=PLAN_DEFAULTS["num_layers"])
    ap.add_argument("--rank", type=int, default=PLAN_DEFAULTS["rank"])
    ap.add_argument("--scale", type=float, default=PLAN_DEFAULTS["scale"])
    ap.add_argument("--dropout", type=float, default=PLAN_DEFAULTS["dropout"])
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--save-every", type=int, default=100)
    ap.add_argument("--steps-per-report", type=int, default=10)
    ap.add_argument("--steps-per-eval", type=int, default=50)
    ap.add_argument("--grad-checkpoint", action="store_true")
    ap.add_argument("--resume", default=None, help="adapter .safetensors to resume from (chunked long runs)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cmd, info = build_cmd(a)
    print(json.dumps({"cmd": cmd, **info}, indent=2))
    if a.dry_run:
        return
    r = subprocess.run(cmd, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
