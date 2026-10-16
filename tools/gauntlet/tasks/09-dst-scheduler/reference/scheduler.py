"""Meeting conflicts across time zones and daylight-saving changes (reference)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def to_utc(local, tz, fold=0):
    z = ZoneInfo(tz)
    naive = datetime.fromisoformat(local)
    if naive.tzinfo is not None:
        raise ValueError("expected a naive local time")
    aware = naive.replace(tzinfo=z, fold=fold)
    u = aware.astimezone(timezone.utc)
    if u.astimezone(z).replace(tzinfo=None) != naive:
        raise ValueError(f"{local} does not exist in {tz}")
    other = naive.replace(tzinfo=z, fold=1 - fold).astimezone(timezone.utc)
    if other != u:          # ambiguous: fold 0 must be the earlier instant
        u = min(u, other) if fold == 0 else max(u, other)
    return u


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def has_conflict(existing, start_local, end_local, tz="Australia/Melbourne", fold=0):
    s, e = to_utc(start_local, tz, fold), to_utc(end_local, tz, fold)
    if e <= s:
        raise ValueError("end must be after start")
    return any(_utc(a) < e and s < _utc(b) for a, b in existing)


def free_minutes(existing, day_local, tz="Australia/Melbourne"):
    z = ZoneInfo(tz)
    d = datetime.fromisoformat(day_local).date()
    start = datetime(d.year, d.month, d.day, tzinfo=z).astimezone(timezone.utc)
    nd = d + timedelta(days=1)
    end = datetime(nd.year, nd.month, nd.day, tzinfo=z).astimezone(timezone.utc)
    covered = sorted((max(_utc(a), start), min(_utc(b), end)) for a, b in existing if _utc(a) < end and start < _utc(b))
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
