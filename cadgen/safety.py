"""Static pre-check of generated code before it is executed.

IMPORTANT: this is a cheap first filter, NOT a security boundary. Model output is
untrusted code. For large-scale runs (data filtering, RL rollouts) run the whole
pipeline inside a container with no network and a read-only filesystem
(see PLAN.md, 'Sandboxing').
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

ALLOWED_IMPORTS = {"cadquery", "math", "numpy", "typing", "itertools", "functools", "collections", "dataclasses"}
FORBIDDEN_NAMES = {
    "exec", "eval", "compile", "open", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "exit", "quit",
}


@dataclass
class CodeCheck:
    syntax_error: str | None = None
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.syntax_error is None and not self.violations


def check_code(code: str) -> CodeCheck:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return CodeCheck(syntax_error=f"{e.msg} (line {e.lineno})")
    except (ValueError, RecursionError, MemoryError) as e:
        return CodeCheck(syntax_error=f"unparseable: {type(e).__name__}")

    out = CodeCheck()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    out.violations.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level or root not in ALLOWED_IMPORTS:
                out.violations.append(f"from {node.module or '.'} import ...")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            out.violations.append(f"name {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            out.violations.append(f"attribute {node.attr}")
    return out
