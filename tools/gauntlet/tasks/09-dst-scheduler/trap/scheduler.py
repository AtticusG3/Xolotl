"""THE TRAP: the obvious zoneinfo code - no nonexistent-time check, and the day length assumed to be 24 h."""
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
