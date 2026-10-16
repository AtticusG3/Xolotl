import re


def test_answer_file():
    text = open("ANSWER.txt").read().strip()
    assert re.fullmatch(r"[0-9a-f]{8}", text), "ANSWER.txt must hold exactly one request id (8 hex digits)"
