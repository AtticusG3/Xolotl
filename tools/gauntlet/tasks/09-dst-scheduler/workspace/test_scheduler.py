from scheduler import has_conflict

EXISTING = [("2026-06-10T00:00:00Z", "2026-06-10T01:00:00Z")]     # 10:00-11:00 Melbourne (AEST, +10)


def test_simple():
    assert has_conflict(EXISTING, "2026-06-10T10:30", "2026-06-10T11:30")
    assert not has_conflict(EXISTING, "2026-06-10T11:00", "2026-06-10T12:00")   # back to back
