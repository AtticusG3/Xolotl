"""Release-stamp ordering - the artifact-naming spec of this build system.

A release stamp has the shape

    EPOCH "." MAJOR "." MINOR [ "~" CHANNEL [ "." REVISION ] ] [ "@" REGION ]

written entirely in lower-case ASCII. Nothing else is allowed: no "v" prefix, no
whitespace, no character outside the shape, no missing field.

  * EPOCH, MAJOR, MINOR: decimal integers with no leading zero - "0" and "7" are
    fine, "01" and "007" are not.
  * CHANNEL: exactly one of the five names dev, beta, rc, stable, hotfix. No
    other channel name exists, so "alpha", "nightly" and "RC" are invalid.
  * REVISION: a decimal integer with no leading zero. It may appear ONLY
    together with a channel, and a channel written without a REVISION carries
    REVISION 0 - so "1.2.0~beta" and "1.2.0~beta.0" have the same REVISION.
  * REGION: one or more characters from [a-z0-9-], starting with a letter or a
    digit and containing no "." - "us-east-1" is fine, "-x", "us.", "us@eu" and
    "US" are not.

Precedence. compare() applies these keys in order and the first difference
decides; every key outranks all the keys listed below it:

  1. MAJOR, numerically: a larger MAJOR is later.
  2. MINOR, numerically: a larger MINOR is later.
  3. CHANNEL, by the fixed rank table below. This is NOT the alphabetical order
     of the five names, and a stamp with NO channel ranks between "stable" and
     "hotfix" - omitting the channel beats writing "stable":

         dev(0) < beta(1) < rc(2) < stable(3) < (no channel, 4) < hotfix(5)

  4. REVISION, numerically: a larger REVISION is later.
  5. EPOCH, inverted: only when every key above is equal, the stamp with the
     LARGER epoch is the EARLIER one. EPOCH is the last key, never the first,
     and it is compared backwards.

REGION never takes part in precedence: "1.2.0@us" and "1.2.0@eu" compare equal.
sort_versions() is stable, so stamps of equal precedence keep their input order.

ValueError is raised for any string that does not match the shape and the field
rules - for instance "1.2" (no MINOR), "01.0.0" (leading zero), "1.0.0~" (no
channel name), "1.0.0~alpha" (no such channel), "1.0.0~beta." (empty REVISION),
"1.0.0~beta.01" (leading zero), "1.0.0@us~beta" ("@" before "~"), "1.0.0@US"
(upper case) - and compare() raises it for any argument that is not a valid
stamp string.
"""


def parse(stamp):
    """Return (epoch, major, minor, channel, revision, region): the three numbers and
    the revision as ints, channel and region as the strings as written (None when the
    stamp omits them, revision 0 when it omits it). ValueError if the stamp is invalid.
    """
    raise NotImplementedError


def compare(a, b):
    """-1 if a precedes b, 0 if they have equal precedence, 1 if a follows b.
    ValueError if either argument is not a valid stamp string (see the module docstring).
    """
    raise NotImplementedError


def sort_versions(stamps):
    """Return the stamps sorted ascending by precedence, stable for equal precedence
    (stamps that compare equal keep their input order)."""
    raise NotImplementedError
