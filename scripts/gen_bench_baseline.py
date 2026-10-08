"""Sequential baseline generation for the v1 benchmark (resumable, append mode).

Parallel generation overloads a fanless Air and ollama's OpenAI endpoint ignores
`n`, so: one task at a time, n=1 per task, append to OUT (safe to resume).

    python scripts/gen_bench_baseline.py --tasks benchmark/tasks.jsonl \
        --out runs/ornith_bench_gens.jsonl --model ornith:9B \
        --base-url http://localhost:11434/v1 --offset 0 --limit 60
"""
from __future__ import annotations

import argparse
import json
import time

from cadgen.llm import ChatClient
from cadgen.prompts import build_fewshot_messages, build_messages
from cadgen.schema import read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--think", choices=["true", "false"], default=None,
                    help="native-API thinking toggle (ollama only); bench baseline uses false for speed")
    ap.add_argument("--few-shot-from", default=None)
    ap.add_argument("--few-shot", type=int, default=3)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    tasks = list(read_jsonl(a.tasks))[a.offset:(a.offset + a.limit) if a.limit else None]
    done = set()
    try:
        with open(a.out) as f:
            for line in f:
                if line.strip():
                    done.add(json.loads(line)["id"])
    except FileNotFoundError:
        pass
    client = ChatClient(a.model, a.base_url, temperature=a.temperature,
                        max_tokens=a.max_tokens,
                        think={"true": True, "false": False}.get(a.think))
    examples = list(read_jsonl(a.few_shot_from))[:a.few_shot] if a.few_shot_from else None
    n_new, t0 = 0, time.time()
    with open(a.out, "a") as f:
        for t in tasks:
            if t["id"] in done:
                continue
            msgs = build_fewshot_messages(examples, t["prompt"]) if examples else build_messages(t["prompt"])
            try:
                comp = client.complete(msgs, n=1)[0]
            except Exception as e:  # noqa: BLE001 - timeout etc: record empty, keep going
                print(f"{t['id']} FAILED {type(e).__name__}: {str(e)[:100]}", flush=True)
                comp = ""
            f.write(json.dumps({"id": t["id"], "completion": comp}) + "\n")
            f.flush()
            n_new += 1
            if n_new % 10 == 0:
                print(f"{n_new} new ({t['id']}) {time.time() - t0:.0f}s", flush=True)
    print(f"done: {n_new} new generations -> {a.out}")


if __name__ == "__main__":
    main()
