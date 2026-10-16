import os


def test_the_violating_requests():
    """ANSWER.txt must be exactly the violating request ids under every documented rule."""
    want = open(os.path.join(os.path.dirname(__file__), "answer.txt")).read().split()
    got = open("ANSWER.txt").read().split()
    assert got == want, (
        f"ANSWER.txt must list exactly the {len(want)} violating request ids, sorted, one per line: "
        f"missing {sorted(set(want) - set(got))}, extra {sorted(set(got) - set(want))}")
