from release_order import compare, parse, sort_versions


def test_parse_basic():
    assert parse("1.4.2~stable@us-east") == (1, 4, 2, "stable", 0, "us-east")
    assert parse("0.9.0") == (0, 9, 0, None, 0, None)


def test_compare_major_and_minor():
    assert compare("1.0.0~dev", "1.2.0~dev") == -1
    assert compare("1.2.0~dev", "1.0.9~dev") == 1
    assert compare("1.2.0~dev", "1.2.0~dev") == 0


def test_sort_basic():
    assert sort_versions(["1.1.0~stable", "1.0.5~stable"]) == ["1.0.5~stable", "1.1.0~stable"]
