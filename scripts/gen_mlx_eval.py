"""Generate benchmark completions from a fine-tuned MLX adapter (resumable).

    python scripts/gen_mlx_eval.py --tasks benchmark/tasks.jsonl \
        --out runs/sft_synth_v1_gens.jsonl --model data/raw/models/qwen25coder15b-4bit \
        --adapter runs/sft-synth-v1/adapter/0000600_adapters.safetensors \
        --offset 0 --limit 80 --temp 0.2 --max-tokens 400
"""
from __future__ import annotations

import argparse
import json
import time

from cadgen.prompts import build_messages
from cadgen.schema import read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--temp", type=float, default=0.2)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--k", type=int, default=1, help="completions per task (rejection sampling)")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler
    model, tok = load(a.model, adapter_path=a.adapter)
    sampler = make_sampler(temp=a.temp)
    tasks = list(read_jsonl(a.tasks))[a.offset:(a.offset + a.limit) if a.limit else None]
    done = set()
    try:
        with open(a.out) as f:
            for line in f:
                if line.strip():
                    done.add(json.loads(line)["id"])
    except FileNotFoundError:
        pass
    n_new, t0 = 0, time.time()
    with open(a.out, "a") as f:
        for t in tasks:
            if t["id"] in done:
                continue
            prompt = tok.apply_chat_template(build_messages(t["prompt"]), tokenize=False,
                                             add_generation_prompt=True)
            for _ in range(max(1, a.k)):
                try:
                    comp = generate(model, tok, prompt=prompt, max_tokens=a.max_tokens,
                                    sampler=sampler, verbose=False)
                except Exception as e:  # noqa: BLE001
                    print(f"{t['id']} FAILED {type(e).__name__}", flush=True)
                    comp = ""
                f.write(json.dumps({"id": t["id"], "completion": comp}) + "\n")
                f.flush()
                n_new += 1
            if n_new % 20 == 0:
                print(f"{n_new} new ({t['id']}) {time.time() - t0:.0f}s", flush=True)
    print(f"done: {n_new} new -> {a.out}")


if __name__ == "__main__":
    main()
