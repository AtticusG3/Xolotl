"""Meeting conflicts across time zones and daylight-saving changes.

existing meetings are stored in UTC as ISO strings with a Z suffix: ("2026-04-04T15:30:00Z", "2026-04-04T16:00:00Z").
A requested meeting is given as naive LOCAL wall-clock times "YYYY-MM-DDTHH:MM" in an IANA zone (zoneinfo).

to_utc(local, tz, fold=0) -> aware UTC datetime
    * a local time that does not exist (skipped by a DST change, e.g. 02:30 on the morning clocks go forward) raises
      ValueError - never silently shift it;
    * a local time that exists twice (clocks go back) is resolved with fold: 0 = the FIRST occurrence (the earlier
      instant), 1 = the second.  fold is ignored for unambiguous times.
has_conflict(existing, start_local, end_local, tz="Australia/Melbourne", fold=0) -> bool
    fold applies to both endpoints.  Intervals are half-open [start, end): back-to-back meetings do not conflict.
    end must be later than start as real instants, otherwise ValueError (note: across a DST change the wall-clock
    duration and the real duration differ).
free_minutes(existing, day_local, tz="Australia/Melbourne") -> int
    the number of real minutes on that LOCAL calendar day (local midnight to the next local midnight - 23, 24 or 25
    hours long) not covered by any existing meeting.
"""


def to_utc(local, tz, fold=0):
    raise NotImplementedError


def has_conflict(existing, start_local, end_local, tz="Australia/Melbourne", fold=0):
    raise NotImplementedError


def free_minutes(existing, day_local, tz="Australia/Melbourne"):
    raise NotImplementedError
