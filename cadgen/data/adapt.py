"""Source-specific adapters: normalize third-party code to the output contract.

Raw third-party samples systematically violate the contract in `configs/project.yaml`:
- no `result` variable (CAD-Coder uses `r`, Text-to-CadQuery uses `assembly`/`part_1`, ...)
- file-writing export calls (`cq.exporters.export(...)` with repo-relative paths that
  would land in the worker cwd during filtering)

Usage:
    python -m cadgen.data.adapt --in data/raw/cad_coder_high.jsonl --out data/raw/cad_coder_high_adapted.jsonl

The original code is kept in `meta["raw_code"]`; applied fixes in `meta["adapted"]`.
Everything downstream (filter/train/eval) uses the adapted `code`.
"""
from __future__ import annotations

import argparse
import ast
import json
import re

from ..schema import read_jsonl, write_jsonl

# call patterns whose whole line is dropped (side effects irrelevant to geometry)
_DROP_PATTERNS = ("exporters.export", ".exportStl(", ".exportBrep(", "show_object(")

_HAS_RESULT = re.compile(r"^result\s*=", re.MULTILINE)


def _strip_comment_free(line: str) -> str:
    """Return the line with trailing comments removed (best effort, # inside strings may confuse)."""
    try:
        # tokenize-free heuristic is enough for the known patterns; keep it simple
        idx = line.find("#")
        return line[:idx] if idx != -1 else line
    except Exception:
        return line


def adapt_code(code: str) -> tuple[str, list[str]]:
    """Return (adapted_code, notes). Never raises: unparseable input passes through + note."""
    notes: list[str] = []
    lines = []
    for line in code.splitlines():
        code_part = _strip_comment_free(line)
        if any(p in code_part for p in _DROP_PATTERNS):
            notes.append(f"dropped line: {line.strip()[:80]}")
            continue
        lines.append(line)
    adapted = "\n".join(lines)
    if code.endswith("\n") and not adapted.endswith("\n"):
        adapted += "\n"

    if _HAS_RESULT.search(adapted):
        return adapted, notes

    try:
        tree = ast.parse(adapted)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        notes.append("unparseable: left as-is")
        return adapted, notes

    last_target: str | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id != "result":
                last_target = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id != "result":
                last_target = node.target.id

    if last_target is None:
        notes.append("no result var and no assign target found: left as-is")
        return adapted, notes

    adapted = adapted.rstrip() + f"\nresult = {last_target}\n"
    notes.append(f"appended `result = {last_target}`")
    return adapted, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--units", default="unknown",
                    help="unit tag for all rows (e.g. normalized, mm); stored in meta")
    args = ap.parse_args()
    rows, changed = [], 0
    for d in read_jsonl(args.inp):
        new_code, notes = adapt_code(d["code"])
        if notes:
            changed += 1
        meta = dict(d.get("meta") or {})
        meta.update({"raw_code": d["code"], "adapted": notes, "units": args.units})
        rows.append({**d, "code": new_code, "meta": meta})
    n = write_jsonl(args.out, rows)
    print(f"wrote {n} samples ({changed} adapted, units={args.units}) -> {args.out}")


if __name__ == "__main__":
    main()
