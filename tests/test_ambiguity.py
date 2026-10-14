from cadgen import ambiguity as A


def test_exact_prompt_passes():
    r = A.analyze("A mounting plate 100 mm by 60 mm and 6 mm thick with four 5 mm holes.")
    assert r["ok"] and r["issues"] == [] and r["questions"] == []


def test_missing_dims_flagged():
    r = A.analyze("Make me a bracket.")
    assert not r["ok"] and any("dimension" in i for i in r["issues"])
    assert r["questions"] and "mm" in r["questions"][0]


def test_vague_word_flagged():
    r = A.analyze("A normal sized box 20 mm wide.")
    assert not r["ok"] and any("vague" in i for i in r["issues"])


def test_empty_prompt():
    r = A.analyze("   ")
    assert not r["ok"]


def test_clarify_appends_answers():
    out = A.clarify("A box.", ["30 x 20 x 10 mm", ""])
    assert "30 x 20 x 10" in out and "[Clarifications:" in out
    assert A.clarify("A box.", []) == "A box."
