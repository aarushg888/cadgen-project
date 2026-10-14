from cadgen.data.adapt import adapt_code


def test_result_present_untouched():
    code = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 20, 30)\n"
    new, notes = adapt_code(code)
    assert new == code and notes == []


def test_appends_result_from_last_assign():
    code = ("import cadquery as cq\npart_1 = cq.Workplane('XY').box(10, 20, 30)\n"
            "assembly = part_1\n")
    new, notes = adapt_code(code)
    assert new.rstrip().endswith("result = assembly")
    assert any("result = assembly" in n for n in notes)


def test_strips_export_calls_but_keeps_comments():
    code = ("import cadquery as cq\nresult = cq.Workplane('XY').box(10, 20, 30)\n"
            "#show_object(result)\n"
            "cq.exporters.export(result, './stlcq/0072/x.stl')\n")
    new, notes = adapt_code(code)
    assert "exporters.export" not in new
    assert "#show_object(result)" in new  # comment lines are harmless, keep them
    assert new.rstrip().splitlines()[-2].startswith("result =")


def test_unparseable_passes_through():
    code = "import cadquery as cq\nr = ("
    new, notes = adapt_code(code)
    assert new == code and any("unparseable" in n for n in notes)
