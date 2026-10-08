"""Prompt format. KEEP IDENTICAL between data prep, training, evaluation and inference:
a mismatch here silently costs more accuracy than most hyperparameters."""

SYSTEM_PROMPT = (
    "You write CadQuery (Python) code that builds the 3D object described by the user. "
    "Use millimetres. Start with `import cadquery as cq`. Assign the final solid to a variable named `result`. "
    "Output only a single ```python code block."
)


def build_messages(prompt: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]


def build_fewshot_messages(examples: list[dict], prompt: str) -> list[dict]:
    """Zero-shot messages with N demonstration turns inserted after the system
    prompt. Each example needs `prompt` and `code` keys; code is sent fenced so
    the model sees the exact output contract. Examples must come from OUTSIDE
    the eval set (e.g. seed tasks when evaluating the v1 benchmark)."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex in examples:
        msgs.append({"role": "user", "content": ex["prompt"]})
        msgs.append({"role": "assistant", "content": "```python\n" + ex["code"].strip() + "\n```"})
    msgs.append({"role": "user", "content": prompt})
    return msgs
