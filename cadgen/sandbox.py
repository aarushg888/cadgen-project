"""Run untrusted CadQuery code in a subprocess with a timeout and resource limits."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .runner import MARK
from .safety import check_code
from .schema import ExecResult

PKG_ROOT = Path(__file__).resolve().parents[1]


def run_code(code: str, *, timeout: float = 30.0, extra_mem_mb: int = 4096,
             outdir: str | None = None, export_stl: bool = False) -> ExecResult:
    """Execute `code` and return an ExecResult. Never raises for bad model output."""
    t0 = time.time()
    chk = check_code(code)
    if chk.syntax_error:
        return ExecResult(status="syntax_error", error=chk.syntax_error, seconds=time.time() - t0)
    if chk.violations:
        return ExecResult(status="forbidden", error="; ".join(sorted(set(chk.violations)))[:300],
                          seconds=time.time() - t0)

    req = json.dumps({"code": code, "outdir": outdir, "export_stl": export_stl,
                      "extra_mem_mb": extra_mem_mb, "cpu_s": int(timeout) + 5})
    try:
        p = subprocess.run([sys.executable, "-m", "cadgen.runner"], input=req, capture_output=True,
                           text=True, timeout=timeout, cwd=str(PKG_ROOT), start_new_session=True)
    except subprocess.TimeoutExpired:
        return ExecResult(status="timeout", error=f"exceeded {timeout}s", seconds=time.time() - t0)

    for line in reversed(p.stdout.splitlines()):
        if line.startswith(MARK):
            d = json.loads(line[len(MARK):])
            d["seconds"] = time.time() - t0
            return ExecResult(**d)
    tail = (p.stderr or "").strip()[-300:]
    return ExecResult(status="crash", error=f"exit={p.returncode} {tail}", seconds=time.time() - t0)


class SandboxPool:
    """N warm fork-server workers. Thread-safe: call .run() from many threads.

        with SandboxPool(workers=8) as pool:
            res = pool.run(code, timeout=20, outdir="/tmp/x")
    """

    def __init__(self, workers: int = 4, mode: str | None = None):
        """mode: "fork" (warm fork-server; Linux default) or "oneshot" (fresh subprocess per job, ~2 s
        overhead each; macOS default because fork() after loading OCC/OpenMP libs is not safe there).
        Override with mode= or env CADGEN_POOL_MODE."""
        import queue
        import threading
        self.mode = mode or os.environ.get("CADGEN_POOL_MODE") or ("oneshot" if sys.platform == "darwin" else "fork")
        if self.mode not in ("fork", "oneshot"):
            raise ValueError(f"unknown pool mode {self.mode!r}")
        self._sem = threading.BoundedSemaphore(workers)
        self._q: "queue.Queue[subprocess.Popen]" = queue.Queue()
        self._all: list[subprocess.Popen] = []
        if self.mode == "fork":
            for _ in range(workers):
                p = self._spawn()
                self._all.append(p)
                self._q.put(p)

    @staticmethod
    def _spawn() -> subprocess.Popen:
        return subprocess.Popen([sys.executable, "-m", "cadgen.forkserver"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                bufsize=1, cwd=str(PKG_ROOT))

    def run(self, code: str, *, timeout: float = 30.0, extra_mem_mb: int = 4096,
            outdir: str | None = None, export_stl: bool = False) -> ExecResult:
        t0 = time.time()
        chk = check_code(code)
        if chk.syntax_error:
            return ExecResult(status="syntax_error", error=chk.syntax_error, seconds=time.time() - t0)
        if chk.violations:
            return ExecResult(status="forbidden", error="; ".join(sorted(set(chk.violations)))[:300],
                              seconds=time.time() - t0)
        if self.mode == "oneshot":
            with self._sem:  # bound concurrency to `workers`
                return run_code(code, timeout=timeout, extra_mem_mb=extra_mem_mb, outdir=outdir, export_stl=export_stl)
        p = self._q.get()
        try:
            req = {"code": code, "outdir": outdir, "export_stl": export_stl,
                   "extra_mem_mb": extra_mem_mb, "cpu_s": int(timeout) + 5, "timeout": timeout}
            try:
                p.stdin.write(json.dumps(req) + "\n")
                p.stdin.flush()
                line = p.stdout.readline()
            except (BrokenPipeError, OSError):
                line = ""
            if not line:  # worker died: replace it
                try:
                    p.kill()
                except Exception:
                    pass
                self._all.remove(p)
                p = self._spawn()
                self._all.append(p)
                return ExecResult(status="crash", error="worker died", seconds=time.time() - t0)
            return ExecResult(**json.loads(line))
        finally:
            self._q.put(p)

    def close(self):
        for p in self._all:
            try:
                p.stdin.close()
                p.wait(timeout=5)
            except Exception:
                p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
