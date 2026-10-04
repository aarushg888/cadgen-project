"""Geometry comparison metrics. All comparisons happen after normalization
(center on bbox center, scale longest bbox side to 1) unless stated otherwise."""
from __future__ import annotations

import math

import numpy as np


def load_brep(path: str):
    import cadquery as cq
    return cq.Shape.importBrep(path)


def normalize(shape):
    """Return a copy translated to the bbox center and scaled so the longest side is 1."""
    import cadquery as cq
    bb = shape.BoundingBox()
    c = cq.Vector(bb.center.x, bb.center.y, bb.center.z)
    longest = max(bb.xlen, bb.ylen, bb.zlen)
    if longest <= 0:
        raise ValueError("degenerate bounding box")
    return shape.translate(-c).scale(1.0 / longest)


def iou(a, b) -> float:
    """Volume IoU via OCC boolean intersection of normalized shapes. 0.0 if the boolean fails."""
    try:
        a, b = normalize(a), normalize(b)
        va, vb = abs(a.Volume()), abs(b.Volume())
        vi = abs(a.intersect(b).Volume())
        union = va + vb - vi
        return float(vi / union) if union > 0 else 0.0
    except Exception:
        return 0.0


def _points(shape, n: int, seed: int) -> np.ndarray:
    import trimesh
    verts, tris = shape.tessellate(0.001, 0.1)
    v = np.array([[p.x, p.y, p.z] for p in verts], dtype=float)
    mesh = trimesh.Trimesh(vertices=v, faces=np.array(tris), process=False)
    pts, _ = trimesh.sample.sample_surface(mesh, n, seed=seed)
    return np.asarray(pts)


def chamfer(a, b, n_points: int = 4096, seed: int = 0) -> float:
    """Symmetric mean nearest-neighbor distance between normalized surfaces (lower is better).
    Papers differ on squared vs. unsquared and x1000 scaling; report which you use."""
    from scipy.spatial import cKDTree
    # same seed for both shapes -> identical shapes give exactly 0 (no sampling-noise floor between them)
    pa = _points(normalize(a), n_points, seed)
    pb = _points(normalize(b), n_points, seed)
    da, _ = cKDTree(pb).query(pa)
    db, _ = cKDTree(pa).query(pb)
    return float(da.mean() + db.mean())


def bbox_match(bbox_a, bbox_b, tol: float = 0.10) -> bool:
    """Sorted side lengths each within `tol` relative error (orientation-invariant)."""
    if not bbox_a or not bbox_b:
        return False
    sa, sb = sorted(bbox_a), sorted(bbox_b)
    return all(abs(x - y) <= tol * max(y, 1e-9) for x, y in zip(sa, sb))


def volume_match(vol_a: float, vol_b: float, tol: float = 0.15) -> bool:
    return vol_b > 0 and abs(vol_a - vol_b) <= tol * vol_b


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator (Chen et al. 2021): n samples, c correct."""
    if n - c < k:
        return 1.0
    return 1.0 - math.prod(1.0 - k / i for i in range(n - c + 1, n + 1))
