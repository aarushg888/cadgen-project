"""Own-license mm-native training data from the benchmark's proven templates.

Why: the pilot train split is normalized-unit third-party data under a license
escalation; template synthetic is OWN license (the D2 permissive track) and
mm-native (the D5 mm track). Same emitters as benchmark/build_v1 (different
seed), same gates, plus decontamination against the BENCHMARK (never train on
bench tasks: exact-code + prompt near-dup).

    python scripts/build_synth_train.py --n 8000 --seed 21 --workers 8

Output: data/raw/synth_train.jsonl (units=mm, license=own). Merge/mix with the
pilot split only deliberately (units differ); a mix-ablation belongs to Stage 3.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from benchmark.build_v1 import STYLES3, TIER1, TIER3, _norm_prompt, _tok_jaccard  # noqa: E402
from cadgen.data.filter import _code_hash, run_filter  # noqa: E402
from cadgen.metrics import bbox_match, volume_match  # noqa: E402
from cadgen.schema import read_jsonl  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--bench", default="benchmark/tasks.jsonl")
    ap.add_argument("--out", default="data/raw/synth_train.jsonl")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    cands, meta = [], {}
    pool = [(fn, s) for fn in TIER1 + TIER3 for s in STYLES3]
    for i in range(a.n):
        fn, style = rng.choice(pool)
        try:
            e = fn(rng, style, wide=True)
            compile(e["code"], "<synth>", "exec")
        except Exception as ex:  # noqa: BLE001
            print("emit skip:", fn.__name__, repr(ex)[:80])
            continue
        cid = f"synth-{a.seed}-{i:05d}"
        cands.append({"id": cid, "prompt": e["prompt"], "code": e["code"], "source": "synth-own",
                      "license": "own", "group": f"synth:{fn.__name__}:{i}",
                      "meta": {"units": "mm", "category": e["category"]}})
        meta[cid] = (e["expected_bbox"], e["expected_vol"], fn.__name__)
    tmp = tempfile.mkdtemp(prefix="synthfilter_")
    with open(os.path.join(tmp, "cands.jsonl"), "w") as f:
        for c in cands:
            f.write(json.dumps({k: c[k] for k in ("id", "prompt", "code", "source", "license", "group", "meta")}) + "\n")
    stats = run_filter(os.path.join(tmp, "cands.jsonl"), os.path.join(tmp, "f"), workers=a.workers,
                       dedupe_code=True, dedupe_geom=True)
    print("gate1 exec:", json.dumps(stats["counts"]))
    passed = [json.loads(l) for l in open(os.path.join(tmp, "f", "passed.jsonl"))]

    consistent = []
    for row in passed:
        exp_bbox, exp_vol, _fn = meta[row["id"]]
        ex = row["meta"]["exec"]
        if bbox_match(exp_bbox, ex["bbox"], tol=0.10) and volume_match(ex["volume"], exp_vol, tol=0.25):
            consistent.append(row)
    print(f"gate2 consistency: {len(consistent)}/{len(passed)}")

    bench = list(read_jsonl(a.bench))
    bench_code = {_code_hash(b["code"]) for b in bench}
    bench_prompts = [_norm_prompt(b["prompt"]) for b in bench]
    kept, n_code, n_prompt = [], 0, 0
    for row in consistent:
        if _code_hash(row["code"]) in bench_code:
            n_code += 1
            continue
        np_ = _norm_prompt(row["prompt"])
        if np_ in bench_prompts or max((_tok_jaccard(np_, tp) for tp in bench_prompts), default=0) >= 0.85:
            n_prompt += 1
            continue
        kept.append(row)
    print(f"gate3 decontam-vs-bench: kept {len(kept)} (code-dup {n_code}, prompt-near-dup {n_prompt})")
    with open(a.out, "w") as f:
        for row in kept:
            f.write(json.dumps(row) + "\n")
    from collections import Counter
    print(f"wrote {len(kept)} -> {a.out}",
          dict(Counter(itertools.chain.from_iterable([[r['meta']['category']] for r in kept]))))


if __name__ == "__main__":
    main()
