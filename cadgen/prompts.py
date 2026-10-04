"""Prompt format. KEEP IDENTICAL between data prep, training, evaluation and inference:
a mismatch here silently costs more accuracy than most hyperparameters."""

SYSTEM_PROMPT = (
    "You write CadQuery (Python) code that builds the 3D object described by the user. "
    "Use millimetres. Start with `import cadquery as cq`. Assign the final solid to a variable named `result`. "
    "Output only a single ```python code block."
)


def build_messages(prompt: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
