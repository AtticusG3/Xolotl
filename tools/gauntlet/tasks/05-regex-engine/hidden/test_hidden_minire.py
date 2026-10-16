import random
import re
import signal

import pytest

from minire import fullmatch


class _Slow(Exception):
    pass


def _alarm(sig, frame):
    raise _Slow()


def timed(fn, seconds=2):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)


def gen(r, depth=0):
    """A random pattern in the spec's grammar (no doubled quantifiers)."""
    kind = r.random()
    if depth > 3 or kind < 0.35:
        atom = r.choice(["a", "b", "c", ".", "[ab]", "[^a]", "[a-c]", "\\.", "\\*"])
    elif kind < 0.6:
        atom = "(" + gen(r, depth + 1) + ")"
    elif kind < 0.8:
        return gen(r, depth + 1) + gen(r, depth + 1)
    else:
        return gen(r, depth + 1) + "|" + gen(r, depth + 1)
    return atom + r.choice(["", "", "*", "+", "?"])


def test_fuzz_against_re():
    r = random.Random(1337)
    alphabet = "abc.*"
    checked = 0
    for _ in range(400):
        pat = gen(r)
        for _ in range(6):
            text = "".join(r.choice(alphabet) for _ in range(r.randint(0, 7)))
            want = re.fullmatch(pat, text, re.S) is not None
            got = timed(lambda: fullmatch(pat, text))
            assert got == want, (pat, text, want)
            checked += 1
    assert checked == 2400


@pytest.mark.parametrize("pat,text,want", [
    ("", "", True), ("", "a", False), ("a|", "", True), ("a|", "a", True), ("(|b)c", "c", True),
    ("[]a]", "]", True), ("[\\]]", "]", True), ("[a\\-z]", "-", True), ("[a-]", "-", True), ("[^]]", "a", True),
    ("a.c", "a\nc", True), ("\\(a\\)", "(a)", True), ("(a|ab)(c|bcd)(d*)", "abcd", True), ("x*", "", True),
    ("(a*)+", "aaa", True), ("(a?)*b", "b", True)])
def test_edge_cases(pat, text, want):
    assert timed(lambda: fullmatch(pat, text)) == want


@pytest.mark.parametrize("bad", ["(", "a)", "*a", "[a", "a|*", "(?", "\\"])
def test_malformed(bad):
    with pytest.raises(ValueError):
        fullmatch(bad, "a")


@pytest.mark.parametrize("pat,text", [("(a*)*b", "a" * 40), ("(a|aa)*c", "a" * 60), ("(a*)*(b*)*c", "ab" * 25),
                                      ("((a+)+)+d", "a" * 35), ("(.*)*x", "y" * 50)])
def test_no_catastrophic_backtracking(pat, text):
    assert timed(lambda: fullmatch(pat, text), 2) is False


def test_does_not_use_re():
    import os
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "minire.py")).read()
    assert "import re" not in src and "from re" not in src and "import regex" not in src
