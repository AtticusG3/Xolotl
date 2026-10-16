"""Meeting scheduling across time zones and daylight-saving changes.

Two kinds of clock appear here.

  * UTC instants are ISO-8601 strings ending in "Z" to the second, e.g.
    "2026-04-04T15:30:00Z".
  * Local wall-clock times are naive ISO-8601 strings ("YYYY-MM-DDTHH:MM", the
    ":SS" optional) read in an IANA zone such as "Australia/Melbourne". A naive
    string carries no offset; the zone decides the instant.

Melbourne 2026, for reference: the clocks go BACK on Sunday 2026-04-05 (03:00
AEDT +11 -> 02:00 AEST +10, so 02:00-03:00 happens twice and that local day is
25 h long) and FORWARD on Sunday 2026-10-04 (02:00 AEST +10 -> 03:00 AEDT +11,
so 02:00-03:00 does not exist and that local day is 23 h long).

to_utc(local, tz, fold=0) -> aware UTC datetime
    * a local time that does not exist - skipped by a DST change, e.g. 02:30 on
      the morning the clocks go forward - raises ValueError; it is NEVER shifted;
    * a local time that exists twice (the clocks have gone back) is resolved by
      fold: 0 = the first occurrence (the earlier instant), 1 = the second. fold
      is ignored for an unambiguous time;
    * ValueError for a string that is not a naive local wall-clock time.

has_conflict(existing, start_local, end_local, tz="Australia/Melbourne", fold=0) -> bool
    existing is a list of (start, end) UTC "Z" strings. The requested meeting is
    two naive local wall-clock times; fold applies to both endpoints. Intervals
    are half-open [start, end): back-to-back meetings do not conflict. end must
    be later than start as REAL instants, otherwise ValueError - across a DST
    change the wall-clock duration and the real duration differ.

free_minutes(existing, day_local, tz="Australia/Melbourne") -> int
    the real minutes of a LOCAL calendar day (local midnight to the next local
    midnight - 23, 24 or 25 hours long) that no existing meeting covers.

weekly(start_local, count, tz="Australia/Melbourne", fold=0) -> list[str]
    a recurring meeting that keeps the SAME local wall-clock time once every 7
    local days (its first occurrence is start_local). Returns the next `count`
    occurrences as UTC "Z" strings, earliest first: occurrence k is at the local
    date start_local's date + 7k days, at start_local's local time. Each instant
    is that local date recomputed for its own week, NOT the first instant plus
    7*24 real hours - so the UTC time of day MOVES by the offset change across a
    DST change.
    Policy: an occurrence whose local time does not exist (it falls in the
    spring-forward gap) raises ValueError naming that date - a recurrence is
    never silently shifted either. fold resolves an occurrence that falls in a
    repeated (fall-back) hour, with the same meaning as in to_utc.

find_slots(busy, day_local, minutes, count, tz="Australia/Melbourne") -> list[str]
    Working hours: this desk is staffed without a break, so the searchable
    window is the whole LOCAL calendar day (local midnight to the next local
    midnight - 23, 24 or 25 real hours). busy is a list of (start, end)
    meetings; each endpoint is EITHER a UTC "Z" string OR a naive local
    wall-clock string, and the two forms are freely mixed - a local endpoint is
    turned into an instant exactly as to_utc does (fold 0 for a repeated time,
    ValueError for a skipped one). Intervals are half-open [start, end) and are
    clipped to the window. Return the earliest `count` start instants, as UTC
    "Z" strings, at which a meeting of `minutes` REAL minutes fits entirely
    inside a free stretch of the window without overlapping busy time (the
    meeting may end exactly when a busy meeting starts).
    Ordering and tie-break: packing is greedy and tight - a slot starts at the
    earliest legal instant, so it may begin exactly where the previous meeting
    ended and, after a busy interval, exactly when that interval ends; no earlier
    legal start is ever passed over for a later, better-aligned one. If fewer
    than `count` slots fit, only the ones that fit are returned, so an empty list
    means none fits. ValueError for minutes <= 0 and for a busy entry that ends
    before it starts.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def to_utc(local, tz, fold=0):
    z = ZoneInfo(tz)
    naive = datetime.fromisoformat(local)
    if naive.tzinfo is not None:
        raise ValueError("expected a naive local wall-clock time")
    u = naive.replace(tzinfo=z, fold=fold).astimezone(timezone.utc)
    if u.astimezone(z).replace(tzinfo=None) != naive:
        raise ValueError(f"{local} does not exist in {tz} (skipped by a daylight-saving change)")
    other = naive.replace(tzinfo=z, fold=1 - fold).astimezone(timezone.utc)
    if other != u:                      # ambiguous: fold 0 is the earlier instant
        u = min(u, other) if fold == 0 else max(u, other)
    return u


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def has_conflict(existing, start_local, end_local, tz="Australia/Melbourne", fold=0):
    s, e = to_utc(start_local, tz, fold), to_utc(end_local, tz, fold)
    if e <= s:
        raise ValueError("end must be after start")
    return any(_utc(a) < e and s < _utc(b) for a, b in existing)


def free_minutes(existing, day_local, tz="Australia/Melbourne"):
    d = datetime.fromisoformat(day_local).date()
    start = to_utc(f"{d.isoformat()}T00:00", tz)
    nd = d + timedelta(days=1)
    end = to_utc(f"{nd.isoformat()}T00:00", tz)
    covered = sorted((max(_utc(a), start), min(_utc(b), end))
                     for a, b in existing if _utc(a) < end and start < _utc(b))
    busy, cur = timedelta(0), None
    for a, b in covered:
        if cur is None or a > cur[1]:
            if cur:
                busy += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        busy += cur[1] - cur[0]
    return int((end - start - busy).total_seconds() // 60)


def weekly(start_local, count, tz="Australia/Melbourne", fold=0):
    first = datetime.fromisoformat(start_local)
    if first.tzinfo is not None:
        raise ValueError("expected a naive local wall-clock time")
    out = []
    for k in range(count):
        occurrence = first + timedelta(days=7 * k)          # same LOCAL wall-clock time
        out.append(_iso(to_utc(occurrence.isoformat(), tz, fold)))
    return out


def find_slots(busy, day_local, minutes, count, tz="Australia/Melbourne"):
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    d = datetime.fromisoformat(day_local).date()
    start = to_utc(f"{d.isoformat()}T00:00", tz)
    end = to_utc(f"{(d + timedelta(days=1)).isoformat()}T00:00", tz)

    def endpoint(s):
        return _utc(s) if s.endswith("Z") else to_utc(s, tz)

    spans = []
    for a, b in busy:
        a, b = endpoint(a), endpoint(b)
        if b <= a:
            raise ValueError("a busy interval must end after it starts")
        a, b = max(a, start), min(b, end)
        if a < b:
            spans.append((a, b))
    spans.sort()
    merged = []
    for a, b in spans:                       # merge overlaps and touching intervals
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))

    step = timedelta(minutes=minutes)
    slots, cursor = [], start
    while len(slots) < count and cursor + step <= end:
        clash = next((b for a, b in merged if a < cursor + step and cursor < b), None)
        if clash is not None:               # the meeting would overlap: resume at the busy end
            cursor = clash
            continue
        slots.append(cursor)
        cursor += step
    return [_iso(t) for t in slots]
