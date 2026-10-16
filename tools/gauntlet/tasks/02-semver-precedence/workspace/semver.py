"""Semantic Versioning 2.0.0 - parsing and precedence.

A version is MAJOR.MINOR.PATCH, optionally followed by -PRERELEASE and/or +BUILD:
  * MAJOR, MINOR, PATCH: non-negative integers, no leading zeros ("01" is invalid; "0" is fine).
  * PRERELEASE: dot-separated identifiers, each non-empty, made of [0-9A-Za-z-]; a purely numeric identifier must not
    have leading zeros ("alpha.01" is invalid, "alpha.0a" is fine - it is not purely numeric).
  * BUILD: dot-separated identifiers, each non-empty, made of [0-9A-Za-z-] (leading zeros allowed).
  * Nothing else: no "v" prefix, no whitespace, no missing parts ("1.2" is invalid).

Precedence (compare):
  1. Compare MAJOR, MINOR, PATCH numerically, in that order.
  2. A version WITH a pre-release has LOWER precedence than the same version without one (1.0.0-alpha < 1.0.0).
  3. Two pre-releases: compare identifier by identifier, left to right:
       - both numeric: compare numerically;
       - both alphanumeric: compare in ASCII order;
       - numeric always has lower precedence than alphanumeric;
       - if all shared identifiers are equal, the one with MORE identifiers is higher.
  4. BUILD metadata is ignored for precedence (1.0.0+a and 1.0.0+b compare equal).
"""


def parse(version):
    """Return (major, minor, patch, prerelease_ids: tuple[str, ...], build_ids: tuple[str, ...]); ValueError if invalid."""
    raise NotImplementedError


def compare(a, b):
    """-1 if a < b, 0 if equal precedence, 1 if a > b (strings in, per the rules above); ValueError if either is invalid."""
    raise NotImplementedError


def sort_versions(versions):
    """Return the versions sorted ascending by precedence (stable for equal precedence)."""
    raise NotImplementedError
