from cadgen.data.z2c import _code_params, _eval_const, render_prompt
import ast


def test_eval_const_arithmetic():
    assert _eval_const(ast.parse("2*3+1").body[0].value, {}) == 7.0
    assert _eval_const(ast.parse("x/2").body[0].value, {"x": 10.0}) == 5.0
    assert _eval_const(ast.parse("foo(1)").body[0].value, {}) is None


def test_plain_assignments():
    code = "rail_width = 80.0\nrail_height = 30.0\nx = rail_width / 2\n"
    params = _code_params(code)
    assert ("rail_width", 80.0) in params and ("x", 40.0) in params


def test_measures_block():
    code = "from types import SimpleNamespace as Measures\nm = Measures(width=70.0, hole=Measures(diameter=4.0))\n"
    params = _code_params(code)
    assert ("m.width", 70.0) in params and ("m.hole.diameter", 4.0) in params


def test_render_needs_two_dims():
    assert render_prompt([], "x = 1.0\n") is None
    p = render_prompt([{"function": "x.hole"}], "a = 10.0\nb = 20.0\n")
    assert p is not None and "10mm" in p and "20mm" in p and "hole" in p
