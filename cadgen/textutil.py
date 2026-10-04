import re

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text: str) -> str:
    """Return the first fenced code block if present (or an unterminated one), else the stripped text."""
    m = _FENCE.search(text)
    if m:
        return m.group(1).strip()
    if "```" in text:  # unterminated fence (truncated generation)
        return re.sub(r"^```(?:python|py)?\s*\n", "", text.split("```", 1)[1]).strip()
    return text.strip()
