"""Convert canonical splits into the chat-format JSONL that MLX-LM's LoRA trainer reads.

    python -m cadgen.data.to_mlx --splits data/splits/x --out data/mlx/x

Writes train.jsonl / valid.jsonl (+ test.jsonl) with {"messages": [system, user, assistant]}, using
cadgen.prompts so training matches evaluation. The assistant turn is one fenced python block.
Check `python -m mlx_lm.lora --help` for current flags (e.g. prompt masking) before training.
"""
from __future__ import annotations

import argparse
import json
import os

from ..prompts import build_messages
from ..schema import read_jsonl, write_jsonl


def to_chat(d: dict) -> dict:
    code = d["code"].strip()
    return {"messages": build_messages(d["prompt"]) + [{"role": "assistant", "content": f"```python\n{code}\n```"}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", required=True, help="dir with train.jsonl, val.jsonl, test.jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for src, dst in (("train", "train"), ("val", "valid"), ("test", "test")):
        path = os.path.join(a.splits, f"{src}.jsonl")
        if os.path.exists(path):
            n = write_jsonl(os.path.join(a.out, f"{dst}.jsonl"), (to_chat(d) for d in read_jsonl(path)))
            print(f"{dst}: {n}")


if __name__ == "__main__":
    main()
