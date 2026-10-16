"""Release-stamp ordering - THE TRAP: the natural, unread reading of the spec.

Two plausible mistakes, each invisible to the visible suite:
  * EPOCH compared first, left to right, ascending (it looks like the leading key);
  * channels ranked alphabetically (beta < dev < hotfix < rc < stable) with a
    missing channel treated as the highest of all.
"""
import functools
import re

_CORE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_REVISION = re.compile(r"^(0|[1-9][0-9]*)$")
_REGION = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ALPHABETICAL_RANK = {"beta": 0, "dev": 1, "hotfix": 2, "rc": 3, "stable": 4}
_NO_CHANNEL_RANK = 5


def parse(stamp):
    if not isinstance(stamp, str):
        raise ValueError("a stamp must be a string")
    core, at, region = stamp.partition("@")
    if at and not _REGION.match(region):
        raise ValueError(f"bad region {region!r}")
    core, tilde, tail = core.partition("~")
    channel, revision = None, 0
    if tilde:
        name, dot, rev = tail.partition(".")
        if name not in _ALPHABETICAL_RANK:
            raise ValueError(f"bad channel {name!r}")
        channel = name
        if dot:
            if not _REVISION.match(rev):
                raise ValueError(f"bad revision {rev!r}")
            revision = int(rev)
    m = _CORE.match(core)
    if not m:
        raise ValueError(f"bad core {core!r}")
    return int(m[1]), int(m[2]), int(m[3]), channel, revision, region if at else None


def _key(stamp):
    epoch, major, minor, channel, revision, _ = parse(stamp)
    rank = _NO_CHANNEL_RANK if channel is None else _ALPHABETICAL_RANK[channel]
    return epoch, major, minor, rank, revision


def compare(a, b):
    ka, kb = _key(a), _key(b)
    return (ka > kb) - (ka < kb)


def sort_versions(stamps):
    return sorted(stamps, key=functools.cmp_to_key(compare))
