"""Zero-to-CAD (Apache-2.0) ingestion: code params -> dimension-stated prompts.

The dataset ships code but no text prompts. Its code carries literal
dimensions two ways: `Measures(...)` blocks or plain `name = 80.0`
assignments with descriptive names (rail_width, tap_diameter, ...). Prompts
are rendered from those (AST, constants-only arithmetic), plus feature words
mined from the ops list. Every row still passes the standard gates.

    python -m cadgen.data.z2c --in data/raw/z2c --out data/raw/z2c_prompts.jsonl --limit 10000
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os

_FEATURE_WORDS = ("hole", "fillet", "chamfer", "pocket", "boss", "rib", "thread",
                  "shell", "slot", "groove", "flange", "tap", "counterbore")


def _eval_const(node, env: dict) -> float | None:
    """Tiny safe evaluator: literals, names bound in env, +-*/ on those."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        l, r = _eval_const(node.left, env), _eval_const(node.right, env)
        if l is None or r is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                return l + r
            if isinstance(node.op, ast.Sub):
                return l - r
            if isinstance(node.op, ast.Mult):
                return l * r
            return l / r if r else None
        except (ArithmeticError, ValueError):
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval_const(node.operand, env)
        return v if v is None else (-v if isinstance(node.op, ast.USub) else v)
    return None


def _code_params(code: str) -> list[tuple[str, float]]:
    """Top-level NAME = number/arithmetic pairs, in order. Also unwraps a
    `m = Measures(...)` call into its keywords (incl. one nested level)."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    env: dict[str, float] = {}
    out: list[tuple[str, float]] = []

    def add(name, val):
        if val is not None and abs(val) < 1e9:
            env[name] = val
            out.append((name, val))

    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if isinstance(node.value, ast.Call):
                for kw in node.value.keywords:
                    if kw.arg and not isinstance(kw.value, ast.Call):
                        add(f"{name}.{kw.arg}", _eval_const(kw.value, env))
                    elif kw.arg and isinstance(kw.value, ast.Call):
                        for kw2 in kw.value.keywords:
                            if kw2.arg:
                                add(f"{name}.{kw.arg}.{kw2.arg}", _eval_const(kw2.value, env))
            else:
                add(name, _eval_const(node.value, env))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            add(node.target.id, _eval_const(node.value, env))
    return out


def render_prompt(ops: list, code: str) -> str | None:
    """Spec-style prompt from code params + ops feature words. None if <2 dims."""
    params = [(n, v) for n, v in _code_params(code) if not n.startswith("_")]
    if len(params) < 2:
        return None
    shown = "; ".join(f"{n.replace('_', ' ')} {v:g}mm" for n, v in params[:14])
    feat_hits = sorted({w for o in ops for w in _FEATURE_WORDS if w in str(o.get("function", "")).lower()})
    tail = f" Features: {', '.join(feat_hits)}." if feat_hits else ""
    return f"Part defined by: {shown}.{tail}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--license", default="apache-2.0 (ADSKAILab/Zero-To-CAD, verified)")
    args = ap.parse_args()
    import pandas as pd
    files = sorted(glob.glob(os.path.join(args.inp, "data/train/*.parquet")))
    rows, n_seen = [], 0
    for f in files:
        df = pd.read_parquet(f, columns=["uuid", "cadquery_file", "cadquery_ops_json"])
        for _, r in df.iterrows():
            if args.limit and n_seen >= args.limit:
                break
            n_seen += 1
            try:
                ops = json.loads(r["cadquery_ops_json"])
                code = bytes(r["cadquery_file"]).decode("utf-8", "replace")
            except Exception:
                continue
            prompt = render_prompt(ops, code)
            if not prompt:
                continue
            rows.append({"id": f"z2c-{r['uuid'][:8]}", "prompt": prompt, "code": code,
                         "source": "z2c", "license": args.license, "group": r["uuid"],
                         "meta": {"units": "mm", "ops_count": len(ops)}})
        if args.limit and n_seen >= args.limit:
            break
    from ..schema import write_jsonl
    n = write_jsonl(args.out, rows)
    print(f"scanned {n_seen}, wrote {n} (skipped {n_seen - n} prompt-less) -> {args.out}")


if __name__ == "__main__":
    main()
