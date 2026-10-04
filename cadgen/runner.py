"""Subprocess entry point. Executes ONE CadQuery script and prints geometry facts as JSON.

Invoked by cadgen.sandbox as:  python -m cadgen.runner   (request JSON on stdin)
Convention for generated code: define a variable named `result`
(cq.Workplane / cq.Assembly / cq.Shape). If absent, the last such object defined is used.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import time
import traceback

MARK = "<<<CADGEN_RESULT>>>"


def _emit(**kw):
    return kw


def _set_limits(extra_mem_mb: int, cpu_s: int):
    """Best effort. Linux enforces both limits. On macOS RLIMIT_AS is not enforced (and /proc is absent),
    so only the CPU limit and the parent's wall-clock timeout protect you: use a container for big runs."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        if extra_mem_mb:
            vm_kb = 0
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmSize:"):
                        vm_kb = int(line.split()[1])
            cap = vm_kb * 1024 + extra_mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    except Exception:
        pass  # non-Linux or restricted; the parent still enforces wall-clock timeout


def _pick_result(ns: dict, cq):
    types = (cq.Workplane, cq.Assembly, cq.Shape)
    if "result" in ns and isinstance(ns["result"], types):
        return ns["result"]
    for v in reversed(list(ns.values())):
        if isinstance(v, types):
            return v
    return None


def _to_shape(obj, cq):
    if isinstance(obj, cq.Workplane):
        shapes = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            return None
        return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    if isinstance(obj, cq.Assembly):
        return obj.toCompound()
    if isinstance(obj, cq.Shape):
        return obj
    return None


def execute(req: dict, cq) -> dict:
    """Run one request and return a result dict (fields of ExecResult). Applies resource limits
    to the CURRENT process, so call it only in a throwaway process (one-shot runner or forked child)."""
    t0 = time.time()
    _set_limits(int(req.get("extra_mem_mb", 4096)), int(req.get("cpu_s", 60)))

    try:
        tree = compile(req["code"], "<generated>", "exec")
    except SyntaxError as e:
        return _emit(status="syntax_error", error=f"{e.msg} (line {e.lineno})")

    ns: dict = {"__name__": "__cadgen__"}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(tree, ns)
    except MemoryError:
        return _emit(status="runtime_error", error="MemoryError")
    except BaseException as e:  # includes SystemExit from generated code
        tb = traceback.format_exception_only(type(e), e)
        return _emit(status="runtime_error", error="".join(tb).strip()[-500:])

    obj = _pick_result(ns, cq)
    if obj is None:
        return _emit(status="no_result", error="no cadquery object found (define `result`)")
    try:
        shape = _to_shape(obj, cq)
    except Exception as e:
        return _emit(status="no_result", error=f"could not convert result: {e}")
    if shape is None:
        return _emit(status="no_result", error="result holds no shapes")

    try:
        solids = shape.Solids()
        volume = float(shape.Volume())
        valid = bool(shape.isValid())
        n_faces = len(shape.Faces())
        bb = shape.BoundingBox()
        bbox = [float(bb.xlen), float(bb.ylen), float(bb.zlen)]
    except Exception as e:
        return _emit(status="invalid_geometry", error=f"inspection failed: {e}")

    info = dict(is_valid=valid, n_solids=len(solids), n_faces=n_faces, volume=volume, bbox=bbox)
    if not solids or volume <= 1e-9:
        return _emit(status="empty", error="no solids or zero volume", **info)
    if not valid:
        return _emit(status="invalid_geometry", error="OCC isValid() is False", **info)

    outdir = req.get("outdir")
    if outdir:
        import os
        os.makedirs(outdir, exist_ok=True)
        brep = os.path.join(outdir, "shape.brep")
        shape.exportBrep(brep)
        info["brep_path"] = brep
        if req.get("export_stl"):
            stl = os.path.join(outdir, "shape.stl")
            shape.exportStl(stl, tolerance=0.01, angularTolerance=0.1)
            info["stl_path"] = stl
    return _emit(status="ok", ok=True, seconds=time.time() - t0, **info)


def main():
    req = json.loads(sys.stdin.read())
    import cadquery as cq  # import before limiting memory
    res = execute(req, cq)
    sys.__stdout__.write(MARK + json.dumps(res) + "\n")
    sys.__stdout__.flush()


if __name__ == "__main__":
    main()
