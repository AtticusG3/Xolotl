import itertools

import pytest

from semver import compare, parse, sort_versions

ORDER = ["1.0.0-0.3.7", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
         "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1-0", "1.0.1", "1.1.0", "1.10.0", "2.0.0-x.7.z.92", "2.0.0"]


def test_total_order():
    for i, j in itertools.combinations(range(len(ORDER)), 2):
        assert compare(ORDER[i], ORDER[j]) == -1, (ORDER[i], ORDER[j])
        assert compare(ORDER[j], ORDER[i]) == 1, (ORDER[j], ORDER[i])


def test_sort_shuffled():
    import random
    xs = ORDER[:]
    random.Random(7).shuffle(xs)
    assert sort_versions(xs) == ORDER


def test_build_ignored_and_stable():
    assert compare("1.0.0+build.1", "1.0.0+exp.sha.5114f85") == 0
    assert compare("1.0.0-alpha+001", "1.0.0-alpha") == 0
    assert sort_versions(["1.0.0+b", "1.0.0+a", "0.1.0"]) == ["0.1.0", "1.0.0+b", "1.0.0+a"]


def test_parse_parts():
    assert parse("1.0.0-alpha.1+build.01") == (1, 0, 0, ("alpha", "1"), ("build", "01"))
    assert parse("10.20.30-0a.1-x+meta-data") == (10, 20, 30, ("0a", "1-x"), ("meta-data",))


@pytest.mark.parametrize("bad", ["1.2", "01.2.3", "1.02.3", "1.2.03", "v1.2.3", "1.2.3-", "1.2.3-alpha..1",
                                 "1.2.3-01", "1.2.3-alpha.01", "1.2.3+", "1.2.3+a..b", "1.2.3-al_pha", " 1.2.3",
                                 "1.2.3.4", "1.2.-3", "1.2.3-+x"])
def test_invalid(bad):
    with pytest.raises(ValueError):
        parse(bad)
    with pytest.raises(ValueError):
        compare(bad, "1.0.0")


def test_numeric_vs_alnum():
    assert compare("1.0.0-1", "1.0.0-a") == -1
    assert compare("1.0.0-10", "1.0.0-9") == 1
    assert compare("1.0.0-a10", "1.0.0-a9") == -1      # alphanumeric: ASCII, not natural order
