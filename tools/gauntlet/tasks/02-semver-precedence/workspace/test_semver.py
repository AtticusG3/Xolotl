from semver import compare, parse, sort_versions


def test_basic():
    assert parse("1.2.3") == (1, 2, 3, (), ())
    assert compare("1.0.0", "2.0.0") == -1
    assert compare("1.0.0-alpha", "1.0.0") == -1
    assert sort_versions(["1.0.0", "0.9.0"]) == ["0.9.0", "1.0.0"]
