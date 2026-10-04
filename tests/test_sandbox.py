import pytest
from cadgen.sandbox import SandboxPool, run_code

BOX = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 20, 30)"

@pytest.fixture(scope="module")
def pool():
    with SandboxPool(2) as p:
        yield p

def test_ok_oneshot():
    r = run_code(BOX, timeout=60)
    assert r.ok and r.n_solids == 1 and abs(r.volume - 6000) < 1e-6
    assert sorted(r.bbox) == [10, 20, 30]

def test_ok_pool_and_artifacts(pool, tmp_path):
    r = pool.run(BOX, outdir=str(tmp_path), export_stl=True)
    assert r.ok and (tmp_path / "shape.brep").exists() and (tmp_path / "shape.stl").exists()

def test_fallback_last_object(pool):
    r = pool.run("import cadquery as cq\nfoo = cq.Workplane('XY').box(1,1,1)")
    assert r.ok

@pytest.mark.parametrize("code,status", [
    ("import cadquery as cq\nresult = (", "syntax_error"),
    ("import os\nresult = 1", "forbidden"),
    ("import cadquery as cq\nopen('/etc/passwd')", "forbidden"),
    ("import cadquery as cq\nx = ().__class__", "forbidden"),
    ("import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1).fillet(5)", "runtime_error"),
    ("import cadquery as cq\nx = 1", "no_result"),
    ("import cadquery as cq\nresult = cq.Workplane('XY')", "no_result"),
])
def test_failure_modes(pool, code, status):
    assert pool.run(code).status == status

def test_timeout_then_recovers(pool):
    assert pool.run("import cadquery as cq\nwhile True:\n    pass", timeout=2).status == "timeout"
    assert pool.run(BOX).ok

def test_sys_exit_is_contained(pool):
    r = pool.run("import cadquery as cq\nraise SystemExit(0)")
    assert r.status == "runtime_error"


def test_oneshot_mode_matches_fork_mode(tmp_path):
    """macOS uses this path by default; verify it on any platform."""
    with SandboxPool(2, mode="oneshot") as p:
        assert p.mode == "oneshot"
        r = p.run(BOX, outdir=str(tmp_path))
        assert r.ok and (tmp_path / "shape.brep").exists()
        assert p.run("import os\nresult=1").status == "forbidden"
        assert p.run("import cadquery as cq\nwhile True:\n    pass", timeout=2).status == "timeout"
