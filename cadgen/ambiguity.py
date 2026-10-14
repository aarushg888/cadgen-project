"""Ambiguity detection for build prompts (Track B, ProCAD-style, local, no GPU).

Underspecified prompts are the top avoidable failure class: the model either
hallucinates dimensions or loops. This module gives a cheap deterministic first
pass — missing dimensions, conflicting values, vague size words — and produces
targeted clarification questions. The CLI asks them (interactively or via
--answers) and appends the answers to the prompt before generation.
"""
from __future__ import annotations

import re

_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(mm|cm|m|in|inch|cm)?", re.IGNORECASE)
_VAGUE = re.compile(r"\b(normal|regular|standard|medium(-sized)?|average|typical|about|roughly|small|large|big|tiny|huge)\b",
                    re.IGNORECASE)
# dimension slots and the words that bind a number to them
_SLOTS = (
    ("length", re.compile(r"\b(long|length|x\b.*?(\d))", re.IGNORECASE)),
    ("width", re.compile(r"\b(wide|width|diameter|across|dia\b)", re.IGNORECASE)),
    ("height", re.compile(r"\b(tall|high|height|thick|thickness|deep|depth)\b", re.IGNORECASE)),
    ("diameter", re.compile(r"\b(diameter|dia\b|radius|r=)\b", re.IGNORECASE)),
    ("hole", re.compile(r"\b(hole|bore|slot|cutout)\b", re.IGNORECASE)),
)


def _numbers(prompt: str) -> list[float]:
    return [float(m.group(1)) for m in _NUM.finditer(prompt)]


def analyze(prompt: str) -> dict:
    """Return {'ok': bool, 'issues': [...], 'questions': [...]}. Deterministic."""
    issues, questions = [], []
    text = (prompt or "").strip()
    if not text:
        return {"ok": False, "issues": ["empty prompt"],
                "questions": ["What object should I build? Describe it with dimensions in mm."]}
    nums = _numbers(text)
    if len(nums) < 2:
        issues.append(f"only {len(nums)} dimension(s) stated; builders need at least length/width/height or diameter/height")
        questions.append("What are the overall dimensions in mm (e.g. length x width x height, or diameter x height)?")
    vague = sorted(set(m.group(1).lower() for m in _VAGUE.finditer(text)))
    if vague:
        issues.append(f"vague size words: {', '.join(vague)}")
        questions.append(f"You said '{vague[0]}' — what exact size in mm did you mean?")
    # conflict scan: same slot word bound to two different numbers, e.g. "20 mm tall ... 30 mm tall"
    for slot, rx in _SLOTS:
        vals = set()
        for m in rx.finditer(text):
            before = text[max(0, m.start() - 18):m.end() + 18]
            for nm in _NUM.finditer(before):
                vals.add(float(nm.group(1)))
            if len(vals) > 3:
                break
        if len(vals) > 3:
            issues.append(f"conflicting values near '{slot}': {sorted(vals)[:4]}")
            questions.append(f"Which value is right for {slot} (mm)?")
    return {"ok": not issues, "issues": issues, "questions": questions[:3]}


def clarify(prompt: str, answers: list[str]) -> str:
    """Append user answers to the prompt for generation. Logged by the caller."""
    extra = "; ".join(a.strip() for a in answers if a and a.strip())
    return f"{prompt.strip()} [Clarifications: {extra}]" if extra else prompt
