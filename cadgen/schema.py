"""Canonical record types used everywhere in the project."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Iterator, Optional

# ExecResult.status values (single source of truth)
STATUSES = (
    "ok",                # ran, produced a valid, non-empty solid
    "syntax_error",      # code does not parse
    "forbidden",         # static check rejected imports/names
    "runtime_error",     # raised while executing
    "timeout",           # exceeded wall-clock limit
    "no_result",         # ran but produced no CadQuery object to export
    "empty",             # object exists but has no volume / no solids
    "invalid_geometry",  # OCC says the shape is invalid
    "crash",             # interpreter died (segfault, OOM kill, ...)
)


@dataclass
class Sample:
    """One training / benchmark example: text prompt -> CadQuery code."""
    id: str
    prompt: str
    code: str
    source: str = "unknown"
    license: str = "unknown"
    group: Optional[str] = None   # underlying design id; split on THIS to avoid leakage
    meta: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_dict(d: dict) -> "Sample":
        known = {"id", "prompt", "code", "source", "license", "group", "meta"}
        extra = {k: v for k, v in d.items() if k not in known}
        meta = dict(d.get("meta") or {})
        meta.update(extra)
        return Sample(
            id=str(d["id"]), prompt=d["prompt"], code=d["code"],
            source=d.get("source", "unknown"), license=d.get("license", "unknown"),
            group=d.get("group"), meta=meta,
        )


@dataclass
class ExecResult:
    status: str
    ok: bool = False
    error: str = ""
    is_valid: bool = False
    n_solids: int = 0
    n_faces: int = 0
    volume: float = 0.0
    bbox: Optional[list] = None       # [xlen, ylen, zlen] in model units (mm by convention)
    brep_path: Optional[str] = None
    stl_path: Optional[str] = None
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def read_jsonl(path: str) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: str, rows: Iterable[dict]) -> int:
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)  # fresh clones have no data/ dirs
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n
