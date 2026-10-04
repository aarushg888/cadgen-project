"""Long-lived worker: imports CadQuery ONCE, then forks a throwaway child per job.

Cuts per-sample overhead from ~2 s (interpreter + OCC import) to tens of ms, which matters for
filtering 100k+ samples and for RL rollouts. Protocol: one JSON request per stdin line,
one JSON result per stdout line. Requests carry `timeout` (seconds, enforced here with SIGKILL).
"""
from __future__ import annotations

import json
import os
import select
import signal
import sys
import time


def _child(req: dict, cq, wfd: int):
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)   # keep OCC/C-level prints off the protocol channel
    os.dup2(devnull, 2)
    from .runner import execute
    try:
        res = execute(req, cq)
    except BaseException as e:  # noqa: BLE001
        res = {"status": "crash", "error": repr(e)[:300]}
    payload = json.dumps(res).encode()
    view = memoryview(payload)
    while view:
        n = os.write(wfd, view)
        view = view[n:]
    os._exit(0)


def serve():
    import cadquery as cq  # warm import, shared by all forked children
    out = sys.__stdout__
    for line in sys.stdin:
        req = json.loads(line)
        timeout = float(req.get("timeout", 30))
        t0 = time.time()
        rfd, wfd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(rfd)
            _child(req, cq, wfd)
        os.close(wfd)
        data, timed_out = b"", False
        deadline = t0 + timeout
        while True:
            rem = deadline - time.time()
            if rem <= 0:
                timed_out = True
                break
            ready, _, _ = select.select([rfd], [], [], rem)
            if not ready:
                timed_out = True
                break
            chunk = os.read(rfd, 65536)
            if not chunk:
                break
            data += chunk
        if timed_out:
            os.kill(pid, signal.SIGKILL)
        _, status = os.waitpid(pid, 0)
        os.close(rfd)
        if timed_out:
            res = {"status": "timeout", "error": f"exceeded {timeout}s"}
        elif data:
            res = json.loads(data)
        else:
            res = {"status": "crash", "error": f"child died (wait status {status})"}
        res["seconds"] = time.time() - t0
        out.write(json.dumps(res) + "\n")
        out.flush()


if __name__ == "__main__":
    serve()
