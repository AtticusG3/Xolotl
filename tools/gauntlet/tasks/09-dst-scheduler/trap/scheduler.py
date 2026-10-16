"""THE TRAP: the obvious zoneinfo code. A skipped local time is silently shifted instead of
raising, a local day is assumed to be 24 h, a weekly occurrence is the first UTC instant plus
7*24 real hours (so its UTC time of day never moves across a DST change), and busy intervals are
not normalised. Passes the visible suite, fails the hidden one."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def to_utc(local, tz, fold=0):
    return datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(tz), fold=fold).astimezone(timezone.utc)


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def has_conflict(existing, start_local, end_local, tz="Australia/Melbourne", fold=0):
    s, e = to_utc(start_local, tz, fold), to_utc(end_local, tz, fold)
    if e <= s:
        raise ValueError("end must be after start")
    return any(_utc(a) < e and s < _utc(b) for a, b in existing)


def free_minutes(existing, day_local, tz="Australia/Melbourne"):
    start = to_utc(day_local[:10] + "T00:00", tz)
    end = start + timedelta(hours=24)
    busy = sum(((min(_utc(b), end) - max(_utc(a), start)).total_seconds() for a, b in existing
                if _utc(a) < end and start < _utc(b)), 0.0)
    return int((end - start).total_seconds() - busy) // 60


def weekly(start_local, count, tz="Australia/Melbourne", fold=0):
    first = to_utc(start_local, tz, fold)                      # collapse to a real instant first
    return [(first + timedelta(weeks=k)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in range(count)]


def find_slots(busy, day_local, minutes, count, tz="Australia/Melbourne"):
    start = to_utc(day_local[:10] + "T00:00", tz)
    end = start + timedelta(hours=24)
    spans = sorted((_utc(a) if a.endswith("Z") else to_utc(a, tz),
                    _utc(b) if b.endswith("Z") else to_utc(b, tz)) for a, b in busy)
    step = timedelta(minutes=minutes)
    slots, cursor = [], start
    while len(slots) < count and cursor + step <= end:
        clash = next((b for a, b in spans if a < cursor + step and cursor < b), None)
        if clash is not None:
            cursor = clash
            continue
        slots.append(cursor)
        cursor += step
    return [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in slots]
