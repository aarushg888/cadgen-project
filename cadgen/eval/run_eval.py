"""Benchmark harness.

    # score generations you already have (JSONL: {"id": ..., "completion": "..."} , repeat id for n>1)
    python -m cadgen.eval.run_eval --tasks benchmark/seed_tasks.jsonl --generations runs/gens.jsonl --out runs/eval_x

    # or generate live from any OpenAI-compatible endpoint (OpenAI, vLLM, Ollama, llama.cpp server)
    python -m cadgen.eval.run_eval --tasks benchmark/seed_tasks.jsonl --model qwen2.5-coder:7b \
        --base-url http://localhost:11434/v1 -n 4 --out runs/eval_base

Per-sample metrics: status, bbox_match, volume_match, iou, chamfer. "geo_pass" = executes AND bbox AND volume match
(a cheap proxy for correctness; report IoU/Chamfer too, and read some outputs by eye).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from .. import metrics as M
from ..prompts import build_messages
from ..sandbox import SandboxPool
from ..schema import read_jsonl
from ..textutil import extract_code


def load_generations(path: str) -> dict[str, list[str]]:
    out = defaultdict(list)
    for d in read_jsonl(path):
        out[str(d["id"])].append(d["completion"])
    return out


def generate_live(tasks, model, base_url, n, temperature) -> dict[str, list[str]]:
    from ..llm import ChatClient
    client = ChatClient(model, base_url, temperature=temperature)
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda t: client.complete(build_messages(t["prompt"]), n=n), tasks))
    return {str(t["id"]): r for t, r in zip(tasks, res)}


def evaluate(tasks: list[dict], gens: dict[str, list[str]], out_dir: str, workers: int = 4,
             timeout: float = 20.0, k_values=(1,)) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="cadgen_eval_")
    rows, per_task_pass = [], defaultdict(list)
    with SandboxPool(workers) as pool:
        refs = {}
        for t in tasks:
            r = pool.run(t["code"], timeout=timeout, outdir=os.path.join(work, f"ref_{t['id']}"))
            if not r.ok:
                raise RuntimeError(f"reference for task {t['id']} failed: {r.status} {r.error}")
            refs[str(t["id"])] = r
        for t in tasks:
            tid = str(t["id"])
            ref = refs[tid]
            ref_shape = M.load_brep(ref.brep_path)
            for j, comp in enumerate(gens.get(tid, [])):
                code = extract_code(comp)
                r = pool.run(code, timeout=timeout, outdir=os.path.join(work, f"{tid}_{j}"))
                row = {"id": tid, "sample": j, "status": r.status, "error": r.error[:200],
                       "category": t.get("category"), "bbox_match": False, "volume_match": False,
                       "iou": 0.0, "chamfer": None, "code": code}
                if r.ok:
                    row["bbox_match"] = M.bbox_match(r.bbox, ref.bbox)
                    row["volume_match"] = M.volume_match(r.volume, ref.volume)
                    shape = M.load_brep(r.brep_path)
                    row["iou"] = M.iou(shape, ref_shape)
                    try:
                        row["chamfer"] = M.chamfer(shape, ref_shape)
                    except Exception:
                        pass
                row["geo_pass"] = bool(r.ok and row["bbox_match"] and row["volume_match"])
                per_task_pass[tid].append(row["geo_pass"])
                rows.append(row)

    with open(os.path.join(out_dir, "samples.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    n = max(1, len(rows))
    cds = [r["chamfer"] for r in rows if r["chamfer"] is not None]
    summary = {
        "n_tasks": len(tasks), "n_samples": len(rows),
        "exec_rate": sum(r["status"] == "ok" for r in rows) / n,
        "bbox_acc": sum(r["bbox_match"] for r in rows) / n,
        "volume_acc": sum(r["volume_match"] for r in rows) / n,
        "geo_pass_rate": sum(r["geo_pass"] for r in rows) / n,
        "mean_iou": sum(r["iou"] for r in rows) / n,          # failures count as 0
        "median_chamfer_on_ok": statistics.median(cds) if cds else None,
        "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
    }
    for k in k_values:
        vals = [M.pass_at_k(len(p), sum(p), k) for p in per_task_pass.values() if len(p) >= k]
        if vals:
            summary[f"pass@{k}"] = sum(vals) / len(vals)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--generations")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("-n", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    tasks = list(read_jsonl(a.tasks))
    if a.generations:
        gens = load_generations(a.generations)
    elif a.model:
        gens = generate_live(tasks, a.model, a.base_url, a.n, a.temperature)
    else:
        ap.error("give --generations or --model")
    ks = tuple(k for k in (1, 4, 8) if k <= max(1, a.n))
    print(json.dumps(evaluate(tasks, gens, a.out, a.workers, k_values=ks), indent=2))


if __name__ == "__main__":
    main()
