"""Synthetic (prompt, code) generation with a strong LLM, to be passed through data/filter.py.

    python -m cadgen.data.synth --model <model> --base-url <url> --out data/raw/synth.jsonl --n 2000

Diversity comes from the concept grid below; extend it aggressively (this is where non-engineering
objects enter the dataset). Every output MUST go through execute-and-filter before training.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random

from ..llm import ChatClient
from ..schema import Sample
from ..textutil import extract_code

OBJECTS = {
    "mechanical": ["mounting plate", "L-bracket", "spacer", "flange", "hex nut", "washer", "pulley", "standoff",
                   "u-channel", "cable clip", "hinge leaf", "motor mount", "gear blank", "pipe adapter"],
    "consumer": ["pencil holder", "picture frame", "phone stand", "coaster", "soap dish", "desk organizer tray",
                 "planter pot", "bookend", "key hook rack", "cup holder", "small vase", "napkin ring"],
    "toys_games": ["chess pawn", "dice", "building block", "stacking ring toy", "token", "puzzle piece"],
    "architectural": ["stepped pyramid", "arch", "staircase", "simple table", "shelf unit", "column"],
}
STYLES = ["plain description with exact dimensions in mm",
          "casual, as a hobbyist would type it, with a few dimensions",
          "spec-sheet style listing features one per line",
          "only overall size plus one distinctive feature"]

TEMPLATE = """Invent ONE specific 3D-printable object: a {obj}. Write:
1. "prompt": a request phrased as: {style}. Give concrete millimetre dimensions.
2. "code": CadQuery code (import cadquery as cq; final solid in `result`; a single valid solid; millimetres;
   dimensions EXACTLY as in the prompt; only standard CadQuery calls).
Reply with a single JSON object {{"prompt": ..., "code": ...}} and nothing else."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--license", default="synthetic:check-provider-terms")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    grid = [(cat, o, s) for cat, objs in OBJECTS.items() for o in objs for s in STYLES]
    rng.shuffle(grid)
    client = ChatClient(a.model, a.base_url, temperature=1.0, max_tokens=1500)
    n_ok = 0
    with open(a.out, "w", encoding="utf-8") as f:
        for cat, obj, style in itertools.islice(itertools.cycle(grid), a.n):
            try:
                txt = client.complete([{"role": "user", "content": TEMPLATE.format(obj=obj, style=style)}])[0]
                d = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
                s = Sample(id=f"synth-{a.seed}-{n_ok}", prompt=d["prompt"].strip(), code=extract_code(d["code"]),
                           source="synth", license=a.license, group=f"synth:{obj}:{n_ok}",
                           meta={"category": cat, "object": obj, "style": style, "generator": a.model})
                f.write(s.to_json() + "\n")
                n_ok += 1
            except Exception as e:  # noqa: BLE001
                print("skip:", repr(e)[:100])
    print(f"wrote {n_ok} raw synthetic samples -> {a.out}")


if __name__ == "__main__":
    main()
