from scheduler import find_slots, has_conflict, to_utc, weekly

EXISTING = [("2026-06-10T00:00:00Z", "2026-06-10T01:00:00Z")]     # 10:00-11:00 Melbourne (AEST, +10)


def test_simple():
    assert has_conflict(EXISTING, "2026-06-10T10:30", "2026-06-10T11:30")
    assert not has_conflict(EXISTING, "2026-06-10T11:00", "2026-06-10T12:00")   # back to back


def test_to_utc_plain_day():
    assert to_utc("2026-06-10T09:00", "Australia/Melbourne").isoformat() == "2026-06-09T23:00:00+00:00"


def test_weekly_plain_week():
    assert weekly("2026-06-03T09:00", 2) == ["2026-06-02T23:00:00Z", "2026-06-09T23:00:00Z"]


def test_find_slots_plain_day():
    busy = [("2026-06-10T00:00:00Z", "2026-06-10T01:00:00Z")]      # 10:00-11:00 local
    assert find_slots(busy, "2026-06-10", 60, 3) == ["2026-06-09T14:00:00Z",
                                                      "2026-06-09T15:00:00Z",
                                                      "2026-06-09T16:00:00Z"]
