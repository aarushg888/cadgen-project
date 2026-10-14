"""Ship CLI: prompt in, CAD files out.

    cadgen "a pencil holder 80 mm in diameter and 100 mm tall" \\
        --adapter runs/eval_ckpt_600 --out ./out --name holder

Generates (MLX adapter or any OpenAI-compatible endpoint), executes each try
through cadgen.sandbox, keeps the first that yields a valid solid (plain retry
loop, not an agent), and writes {name}.py / {name}.step / {name}.stl.
Prompt format matches training and eval (cadgen.prompts).
"""
from __future__ import annotations

import argparse
import json
import os

from .prompts import build_messages
from .sandbox import run_code
from .textutil import extract_code


def _mlx_generate(model_path, adapter_path, messages, temperature, max_tokens):
    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler
    from mlx_lm.tokenizer_utils import TokenizerWrapper
    model, tok = load(model_path, adapter_path=adapter_path)
    if isinstance(tok, TokenizerWrapper):
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return generate(model, tok, prompt=prompt, max_tokens=max_tokens,
                    sampler=make_sampler(temp=temperature), verbose=False)


def _api_generate(model, base_url, messages, temperature, max_tokens):
    from .llm import ChatClient
    return ChatClient(model, base_url, temperature=temperature, max_tokens=max_tokens).complete(messages, n=1)[0]


def _export_files(code: str, exec_info, out_dir: str, name: str) -> dict:
    import cadquery as cq
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    py_path = os.path.join(out_dir, name + ".py")
    with open(py_path, "w") as f:
        f.write(code if code.endswith("\n") else code + "\n")
    paths["py"] = py_path
    shape = cq.Shape.importBrep(exec_info.brep_path)
    step_path = os.path.join(out_dir, name + ".step")
    shape.exportStep(step_path)
    paths["step"] = step_path
    stl_path = os.path.join(out_dir, name + ".stl")
    shape.exportStl(stl_path, tolerance=0.01, angularTolerance=0.1)
    paths["stl"] = stl_path
    return paths


def run(prompt: str, generate_fn, out_dir: str, name: str, tries: int = 3,
        timeout: float = 30.0, temperatures=(0.2, 0.6, 1.0)) -> dict:
    """Try up to `tries` generations; return summary. generate_fn(prompt, temperature) -> str.
    Guards: unparseable code (e.g. the stacked-loop truncation class) fails fast
    without sandbox cost; temperature escalates per try to break deterministic loops."""
    import ast
    import tempfile
    attempts = []
    for i in range(max(1, tries)):
        temp = temperatures[min(i, len(temperatures) - 1)]
        try:
            completion = generate_fn(prompt, temperature=temp)
        except Exception as e:  # noqa: BLE001 - backend hiccup: counted, retried
            attempts.append({"try": i, "status": "generate_error", "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        code = extract_code(completion)
        try:
            compile(code, "<cli>", "exec")
        except (SyntaxError, ValueError) as e:
            attempts.append({"try": i, "status": "syntax_error", "error": f"unparseable ({e})"[:200],
                             "temperature": temp})
            continue
        work = tempfile.mkdtemp(prefix="cadgen_cli_")
        res = run_code(code, timeout=timeout, outdir=work)
        attempts.append({"try": i, "status": res.status, "error": res.error[:200]})
        if res.ok:
            paths = _export_files(code, res, out_dir, name)
            return {"ok": True, "tries_used": i + 1, "volume": res.volume, "bbox": res.bbox,
                    "n_faces": res.n_faces, "files": paths, "attempts": attempts}
    return {"ok": False, "tries_used": len(attempts), "files": {}, "attempts": attempts}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cadgen")
    ap.add_argument("prompt")
    ap.add_argument("--out", default="out")
    ap.add_argument("--name", default="part")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--clarify", action="store_true",
                    help="analyze the prompt for ambiguity first; ask up to 3 questions")
    ap.add_argument("--answers", default=None,
                    help="non-interactive clarifications, ';'-separated (implies --clarify)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--adapter", help="MLX adapter dir (with --model)")
    src.add_argument("--model-endpoint", help="model name for an OpenAI-compatible endpoint (with --base-url)")
    ap.add_argument("--model", default="data/raw/models/qwen25coder15b-4bit")
    ap.add_argument("--base-url", default=None)
    a = ap.parse_args(argv)
    if a.adapter:
        def gen(p, temperature=0.2, _m=a.model, _ad=a.adapter, _n=a.max_tokens):
            return _mlx_generate(_m, _ad, build_messages(p), temperature, _n)
    else:
        def gen(p, temperature=0.2, _m=a.model_endpoint, _b=a.base_url, _n=a.max_tokens):
            return _api_generate(_m, _b, build_messages(p), temperature, _n)
    temps = (a.temperature, min(1.0, a.temperature + 0.4), 1.0)
    prompt, qa_log = a.prompt, []
    if a.clarify or a.answers:
        from .ambiguity import analyze, clarify
        rep = analyze(a.prompt)
        if not rep["ok"]:
            if a.answers:
                answers = [x for x in a.answers.split(";")]
            else:
                print("Clarifying questions (empty line to skip):")
                answers = [input(f"  {q} ") for q in rep["questions"]]
            prompt = clarify(a.prompt, answers)
            qa_log = [{"q": q, "a": ans} for q, ans in zip(rep["questions"], answers)]
    summary = run(prompt, gen, a.out, a.name, tries=a.tries, timeout=a.timeout,
                  temperatures=temps)
    summary["clarifications"] = qa_log
    print(json.dumps({k: v for k, v in summary.items() if k != "attempts"}, indent=2))
    if not summary["ok"]:
        raise SystemExit(f"all {summary['tries_used']} tries failed: "
                         + "; ".join(x.get("error", x["status"]) for x in summary["attempts"]))
    return summary


if __name__ == "__main__":
    main()
