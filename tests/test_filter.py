from types import SimpleNamespace

from cadgen.data.filter import _geom_sig


def _res(volume, bbox, n_faces=6):
    return SimpleNamespace(volume=volume, bbox=bbox, n_faces=n_faces)


def test_identical_geometry_same_sig():
    assert _geom_sig(_res(0.001234, [0.0408, 0.0408, 0.75])) == _geom_sig(_res(0.001234, [0.75, 0.0408, 0.0408]))


def test_small_distinct_geometries_differ():
    # regression: 1-decimal rounding collapsed normalized-scale parts (0.02-0.75)
    # into shared signatures and mass-rejected good data
    a = _geom_sig(_res(0.001, [0.0408, 0.0408, 0.75]))
    b = _geom_sig(_res(0.002, [0.05, 0.05, 0.8]))
    assert a != b


def test_truly_duplicate_geometry_matches():
    assert _geom_sig(_res(60.0, [60.0, 40.0, 5.0], 8)) == _geom_sig(_res(60.0, [40.0, 5.0, 60.0], 8))
