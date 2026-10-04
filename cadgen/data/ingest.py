"""Normalize third-party datasets into canonical Sample JSONL.

    python -m cadgen.data.ingest --format messages --in raw.json --out data/raw/x.jsonl \
        --source cad-coder --license apache-2.0 --group-key model_path
    python -m cadgen.data.ingest --format pairs --in raw.jsonl --out data/raw/y.jsonl \
        --prompt-key prompt --code-key completion

NOTE: field names below are the common conventions; INSPECT the real files first
(`head -c 2000 file`) and adjust the flags. Keep the per-source `license` accurate.
"""
from __future__ import annotations

import argparse
import json

from ..schema import Sample, write_jsonl
from ..textutil import extract_code


def _load_any(path: str):
    with open(path, "r", encoding="utf-8") as f:
        head = f.read(1)
        f.seek(0)
        if head == "[":
            yield from json.load(f)
        else:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def from_messages(rec: dict, i: int, args) -> Sample | None:
    msgs = rec.get("messages") or []
    user = next((m["content"] for m in msgs if m.get("role") == "user"), None)
    asst = next((m["content"] for m in reversed(msgs) if m.get("role") == "assistant"), None)
    if not user or not asst:
        return None
    return Sample(id=f"{args.source}-{i}", prompt=user.strip(), code=extract_code(asst), source=args.source,
                  license=args.license, group=str(rec[args.group_key]) if args.group_key and args.group_key in rec else None)


def from_pairs(rec: dict, i: int, args) -> Sample | None:
    p, c = rec.get(args.prompt_key), rec.get(args.code_key)
    if not p or not c:
        return None
    return Sample(id=f"{args.source}-{i}", prompt=str(p).strip(), code=extract_code(str(c)), source=args.source,
                  license=args.license, group=str(rec[args.group_key]) if args.group_key and args.group_key in rec else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["messages", "pairs"], required=True)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--license", default="unknown")
    ap.add_argument("--prompt-key", default="prompt")
    ap.add_argument("--code-key", default="completion")
    ap.add_argument("--group-key", default=None, help="field identifying the underlying design (for leakage-free splits)")
    args = ap.parse_args()
    fn = from_messages if args.format == "messages" else from_pairs
    rows, skipped = [], 0
    for i, rec in enumerate(_load_any(args.inp)):
        s = fn(rec, i, args)
        if s is None:
            skipped += 1
        else:
            rows.append(json.loads(s.to_json()))
    n = write_jsonl(args.out, rows)
    print(f"wrote {n} samples, skipped {skipped} -> {args.out}")


if __name__ == "__main__":
    main()
