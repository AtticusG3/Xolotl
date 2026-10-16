import os


def test_the_violating_request():
    want = open(os.path.join(os.path.dirname(__file__), "answer.txt")).read().strip()
    assert open("ANSWER.txt").read().strip() == want
