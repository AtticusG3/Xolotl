"""Semantic Versioning 2.0.0 - parsing and precedence (reference solution)."""
import functools
import re

_ID = re.compile(r"^[0-9A-Za-z-]+$")
_NUM = re.compile(r"^(0|[1-9]\d*)$")


def _ids(part, what, numeric_no_leading_zero):
    ids = tuple(part.split("."))
    for i in ids:
        if not i or not _ID.match(i):
            raise ValueError(f"bad {what} identifier {i!r}")
        if numeric_no_leading_zero and i.isdigit() and not _NUM.match(i):
            raise ValueError(f"leading zero in {what} identifier {i!r}")
    return ids


def parse(version):
    if not isinstance(version, str):
        raise ValueError("not a string")
    core, plus, build = version.partition("+")
    if plus and not build:
        raise ValueError("empty build")
    core, dash, pre = core.partition("-")
    if dash and not pre:
        raise ValueError("empty pre-release")
    nums = core.split(".")
    if len(nums) != 3 or not all(_NUM.match(n) for n in nums):
        raise ValueError(f"bad core {core!r}")
    pre_ids = _ids(pre, "pre-release", True) if dash else ()
    build_ids = _ids(build, "build", False) if plus else ()
    return int(nums[0]), int(nums[1]), int(nums[2]), pre_ids, build_ids


def _cmp_pre(a, b):
    if not a and not b:
        return 0
    if not a:
        return 1
    if not b:
        return -1
    for x, y in zip(a, b):
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            c = (int(x) > int(y)) - (int(x) < int(y))
        elif xn != yn:
            c = -1 if xn else 1
        else:
            c = (x > y) - (x < y)
        if c:
            return c
    return (len(a) > len(b)) - (len(a) < len(b))


def compare(a, b):
    pa, pb = parse(a), parse(b)
    c = (pa[:3] > pb[:3]) - (pa[:3] < pb[:3])
    return c if c else _cmp_pre(pa[3], pb[3])


def sort_versions(versions):
    return sorted(versions, key=functools.cmp_to_key(compare))
