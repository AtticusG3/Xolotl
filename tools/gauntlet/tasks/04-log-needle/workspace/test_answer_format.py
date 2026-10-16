import re


def test_answer_format():
    """ANSWER.txt: one 8-hex-digit request id per line, sorted ascending, no duplicates."""
    lines = open("ANSWER.txt").read().splitlines()
    assert lines, "ANSWER.txt must list at least one request id"
    assert all(re.fullmatch(r"[0-9a-f]{8}", ln) for ln in lines), \
        "every line must be exactly one request id (8 hex digits)"
    assert lines == sorted(set(lines)), "one id per line, sorted ascending, no duplicates"
