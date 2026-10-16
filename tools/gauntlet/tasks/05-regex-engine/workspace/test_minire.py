from minire import fullmatch


def test_basics():
    assert fullmatch("abc", "abc")
    assert not fullmatch("abc", "abcd")
    assert fullmatch("a*b", "aaab")
    assert fullmatch("(ab|cd)+", "abcdab")
    assert fullmatch("[a-c]x?", "b")
    assert not fullmatch("[^a-c]", "b")
