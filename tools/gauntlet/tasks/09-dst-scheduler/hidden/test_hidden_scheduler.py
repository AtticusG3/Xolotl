import pytest

from scheduler import free_minutes, has_conflict, to_utc

MEL = "Australia/Melbourne"
# 2026-04-05: clocks go back 03:00 AEDT -> 02:00 AEST (02:00-03:00 happens twice)
# 2026-10-04: clocks go forward 02:00 AEST -> 03:00 AEDT (02:00-03:00 does not exist)
SECOND_230 = [("2026-04-04T16:30:00Z", "2026-04-04T16:50:00Z")]     # 02:30-02:50 local, the SECOND time round


def test_ambiguous_fold():
    assert to_utc("2026-04-05T02:30", MEL, 0).isoformat() == "2026-04-04T15:30:00+00:00"
    assert to_utc("2026-04-05T02:30", MEL, 1).isoformat() == "2026-04-04T16:30:00+00:00"
    assert not has_conflict(SECOND_230, "2026-04-05T02:30", "2026-04-05T02:45", MEL, fold=0)
    assert has_conflict(SECOND_230, "2026-04-05T02:30", "2026-04-05T02:45", MEL, fold=1)


@pytest.mark.parametrize("t", ["2026-10-04T02:00", "2026-10-04T02:30", "2026-10-04T02:59"])
def test_nonexistent(t):
    with pytest.raises(ValueError):
        to_utc(t, MEL)
    with pytest.raises(ValueError):
        has_conflict([], t, "2026-10-04T04:00", MEL)


def test_across_gap_real_duration():
    # 01:30 -> 03:30 on the spring-forward day is ONE real hour
    meet = [("2026-10-03T15:00:00Z", "2026-10-03T15:20:00Z")]           # 01:00-01:20 AEST
    assert not has_conflict(meet, "2026-10-04T01:30", "2026-10-04T03:30", MEL)
    assert has_conflict([("2026-10-03T16:15:00Z", "2026-10-03T16:20:00Z")], "2026-10-04T01:30", "2026-10-04T03:30", MEL)


def test_end_before_start_after_fallback():
    # 02:40 (first, AEDT) -> 02:10 (fold applies to both: first occurrence) is backwards -> ValueError
    with pytest.raises(ValueError):
        has_conflict([], "2026-04-05T02:40", "2026-04-05T02:10", MEL, fold=0)


def test_day_lengths():
    assert free_minutes([], "2026-04-05", MEL) == 25 * 60
    assert free_minutes([], "2026-10-04", MEL) == 23 * 60
    assert free_minutes([], "2026-06-10", MEL) == 24 * 60
    busy = [("2026-04-04T14:00:00Z", "2026-04-04T17:00:00Z"), ("2026-04-04T16:00:00Z", "2026-04-04T18:00:00Z")]
    assert free_minutes(busy, "2026-04-05", MEL) == 25 * 60 - 240        # overlapping meetings counted once


def test_other_zone():
    with pytest.raises(ValueError):
        to_utc("2026-03-08T02:30", "America/New_York")
    assert to_utc("2026-11-01T01:30", "America/New_York", 1).isoformat() == "2026-11-01T06:30:00+00:00"
