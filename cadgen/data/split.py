"""Leakage-free train/val/test split: split by `group` (underlying design), never by row.

    python -m cadgen.data.split --in data/filtered/x/passed.jsonl --out data/splits/x --val 0.02 --test 0.02
Rows without a group fall back to grouping by their own id (weaker: same design may leak).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

from ..schema import read_jsonl, write_jsonl


def bucket(key: str, seed: int) -> float:
    h = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return int(h[:12], 16) / 16 ** 12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--val", type=float, default=0.02)
    ap.add_argument("--test", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=1234)
    a = ap.parse_args()
    parts = {"train": [], "val": [], "test": []}
    for d in read_jsonl(a.inp):
        b = bucket(str(d.get("group") or d["id"]), a.seed)
        parts["test" if b < a.test else "val" if b < a.test + a.val else "train"].append(d)
    os.makedirs(a.out, exist_ok=True)
    for k, rows in parts.items():
        write_jsonl(os.path.join(a.out, f"{k}.jsonl"), rows)
    print(json.dumps({k: len(v) for k, v in parts.items()}))


if __name__ == "__main__":
    main()
