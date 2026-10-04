import cadquery as cq
from cadgen import metrics as M

def box(a, b, c):
    return cq.Workplane("XY").box(a, b, c).val()

def test_identical_iou_and_chamfer():
    assert M.iou(box(10, 20, 30), box(10, 20, 30)) > 0.999
    assert M.chamfer(box(10, 20, 30), box(10, 20, 30)) < 1e-6

def test_scale_invariance():
    assert M.iou(box(10, 20, 30), box(20, 40, 60)) > 0.999

def test_different_shapes_score_lower():
    cyl = cq.Workplane("XY").circle(10).extrude(30).val()
    assert M.iou(box(20, 20, 30), cyl) < 0.9
    assert M.chamfer(box(20, 20, 30), cyl) > M.chamfer(box(20, 20, 30), box(20, 20, 30))

def test_bbox_and_volume_match():
    assert M.bbox_match([10, 20, 30], [30, 10, 20])
    assert not M.bbox_match([10, 20, 30], [10, 20, 40])
    assert M.volume_match(100, 110) and not M.volume_match(100, 200)

def test_pass_at_k():
    assert M.pass_at_k(10, 0, 1) == 0.0 and M.pass_at_k(10, 10, 1) == 1.0
    assert abs(M.pass_at_k(10, 5, 1) - 0.5) < 1e-9
