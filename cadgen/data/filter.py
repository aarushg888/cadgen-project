"""Execute-and-filter: keep only samples whose code runs and yields a valid solid.

    python -m cadgen.data.filter --in data/raw/x.jsonl --out data/filtered/x --workers 8 \
        --dedupe-code --dedupe-geom

Outputs in --out: passed.jsonl (adds `exec` facts), rejected.jsonl (adds `status`,`error`), stats.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from ..sandbox import SandboxPool
from ..schema import Sample, read_jsonl


def _code_hash(code: str) -> str:
    norm = re.sub(r"#.*", "", code)
    norm = re.sub(r"\s+", "", norm)
    return hashlib.md5(norm.encode()).hexdigest()


def _geom_sig(r) -> tuple:
    # 3-decimal precision: 1-decimal rounding collapses distinct small
    # (e.g. normalized-unit) parts into one signature and mass-rejects good
    # data (2026-10-04 pilot: 1577/2000 false dup_geometry). Exact duplicates
    # still match; near-duplicate *prompt* detection is separate future work.
    return (round(r.volume, 3), tuple(sorted(round(x, 3) for x in r.bbox)), r.n_faces)


def run_filter(inp: str, out_dir: str, workers: int = 4, timeout: float = 20.0, limit: int | None = None,
               offset: int = 0,
               dedupe_code: bool = False, dedupe_geom: bool = False, require_single_solid: bool = True) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    samples = []
    for i, d in enumerate(read_jsonl(inp)):
        if i < offset:
            continue
        if limit and len(samples) >= limit:
            break
        samples.append(Sample.from_dict(d))

    seen_code, seen_geom = set(), set()
    counts, t0 = Counter(), time.time()
    pf = open(os.path.join(out_dir, "passed.jsonl"), "w", encoding="utf-8")
    rf = open(os.path.join(out_dir, "rejected.jsonl"), "w", encoding="utf-8")
    try:
        with SandboxPool(workers) as pool, ThreadPoolExecutor(workers * 2) as ex:
            def work(s: Sample):
                if dedupe_code:
                    h = _code_hash(s.code)
                    if h in seen_code:
                        return s, None, "dup_code"
                    seen_code.add(h)
                return s, pool.run(s.code, timeout=timeout), None

            for n, (s, r, early) in enumerate(ex.map(work, samples), 1):
                row = json.loads(s.to_json())
                if early:
                    counts[early] += 1
                    row.update(status=early)
                    rf.write(json.dumps(row) + "\n")
                    continue
                status = r.status
                if status == "ok" and require_single_solid and r.n_solids != 1:
                    status = "multi_solid"
                if status == "ok" and dedupe_geom:
                    sig = _geom_sig(r)
                    if sig in seen_geom:
                        status = "dup_geometry"
                    seen_geom.add(sig)
                counts[status] += 1
                if status == "ok":
                    row["meta"] = {**row.get("meta", {}), "exec": {"volume": r.volume, "bbox": r.bbox,
                                                                   "n_faces": r.n_faces, "n_solids": r.n_solids}}
                    pf.write(json.dumps(row) + "\n")
                else:
                    row.update(status=status, error=r.error)
                    rf.write(json.dumps(row) + "\n")
                if n % 500 == 0:
                    print(f"{n}/{len(samples)}  ok={counts['ok']}  {n / (time.time() - t0):.1f}/s", flush=True)
    finally:
        pf.close()
        rf.close()
    stats = {"total": len(samples), "counts": dict(counts), "pass_rate": counts["ok"] / max(1, len(samples)),
             "seconds": time.time() - t0}
    with open(os.path.join(out_dir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0, help="skip first N input rows (chunked/resumable runs)")
    ap.add_argument("--dedupe-code", action="store_true")
    ap.add_argument("--dedupe-geom", action="store_true")
    ap.add_argument("--allow-multi-solid", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run_filter(a.inp, a.out, a.workers, a.timeout, a.limit, a.offset, a.dedupe_code,
                                a.dedupe_geom, not a.allow_multi_solid), indent=2))


if __name__ == "__main__":
    main()
