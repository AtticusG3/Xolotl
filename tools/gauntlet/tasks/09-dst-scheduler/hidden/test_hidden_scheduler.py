from datetime import datetime, timedelta

import pytest

from scheduler import find_slots, free_minutes, has_conflict, to_utc, weekly

MEL = "Australia/Melbourne"
# 2026-04-05: clocks go back 03:00 AEDT -> 02:00 AEST (02:00-03:00 happens twice; a 25 h day)
# 2026-10-04: clocks go forward 02:00 AEST -> 03:00 AEDT (02:00-03:00 does not exist; a 23 h day)
SECOND_230 = [("2026-04-04T16:30:00Z", "2026-04-04T16:50:00Z")]     # 02:30-02:50 local, the SECOND time round


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---- to_utc: fold and skipped times ------------------------------------------

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
    assert free_minutes(busy, "2026-04-05", MEL) == 25 * 60 - 240       # overlapping meetings counted once


def test_other_zone():
    with pytest.raises(ValueError):
        to_utc("2026-03-08T02:30", "America/New_York")
    assert to_utc("2026-11-01T01:30", "America/New_York", 1).isoformat() == "2026-11-01T06:30:00+00:00"


# ---- weekly: same LOCAL wall-clock time, so the UTC instant moves with the offset ----

def test_recurrence_shifts_across_fallback():
    # a Wednesday 09:00 series: the 04-05 fall-back moves the UTC instant from 22:00Z to 23:00Z
    assert weekly("2026-04-01T09:00", 3) == ["2026-03-31T22:00:00Z", "2026-04-07T23:00:00Z", "2026-04-14T23:00:00Z"]
    a, b, c = (_t(s) for s in weekly("2026-04-01T09:00", 3))
    assert (b - a) == timedelta(hours=169)                 # the fall-back week is one real hour longer
    assert (c - b) == timedelta(hours=168)


def test_recurrence_shifts_across_spring_forward():
    assert weekly("2026-09-27T01:30", 3) == ["2026-09-26T15:30:00Z", "2026-10-03T15:30:00Z", "2026-10-10T14:30:00Z"]
    a, b, c = (_t(s) for s in weekly("2026-09-27T01:30", 3))
    assert (b - a) == timedelta(hours=168)
    assert (c - b) == timedelta(hours=167)                 # the 10-04 gap shortens a week


def test_recurrence_over_skipped_hour_raises():
    # the 2026-10-04 occurrence of a Sunday 02:30 series does not exist -> policy: raise, never shift
    with pytest.raises(ValueError):
        weekly("2026-09-27T02:30", 2)
    assert weekly("2026-10-04T03:30", 1) == ["2026-10-03T16:30:00Z"]     # exists, just after the gap


# ---- find_slots --------------------------------------------------------------

def test_slots_day_length():
    assert len(find_slots([], "2026-10-04", 60, 30)) == 23        # a 23-hour day holds 23 whole hours
    assert len(find_slots([], "2026-04-05", 60, 30)) == 25
    assert len(find_slots([], "2026-06-10", 60, 30)) == 24
    assert find_slots([], "2026-10-04", 1400, 1) == []            # 23 h < 1400 min: nothing fits
    assert find_slots([], "2026-04-05", 1400, 1) == ["2026-04-04T13:00:00Z"]


def test_slots_normalise_mixed_busy_and_the_gap():
    # the two endpoints name the SAME meeting (UTC and local forms); on the gap day it covers
    # 01:30-03:30 local, which is ONE real hour, so the next slot resumes at 16:30Z.
    busy = [("2026-10-03T15:30:00Z", "2026-10-03T16:30:00Z"), ("2026-10-04T01:30", "2026-10-04T03:30")]
    assert find_slots(busy, "2026-10-04", 30, 4) == ["2026-10-03T14:00:00Z", "2026-10-03T14:30:00Z",
                                                      "2026-10-03T15:00:00Z", "2026-10-03T16:30:00Z"]


def test_slots_pack_tightly_and_resume_at_the_busy_end():
    busy = [("2026-06-10T02:00:00Z", "2026-06-10T03:00:00Z")]          # 12:00-13:00 local
    assert find_slots(busy, "2026-06-10", 90, 10) == [
        "2026-06-09T14:00:00Z", "2026-06-09T15:30:00Z", "2026-06-09T17:00:00Z", "2026-06-09T18:30:00Z",
        "2026-06-09T20:00:00Z", "2026-06-09T21:30:00Z", "2026-06-09T23:00:00Z", "2026-06-10T00:30:00Z",
        "2026-06-10T03:00:00Z", "2026-06-10T04:30:00Z"]


def test_slots_ignore_outside_and_clip_busy():
    outside = [("2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z")]       # another day entirely
    assert find_slots(outside, "2026-06-10", 60, 1) == ["2026-06-09T14:00:00Z"]
    # a busy meeting that straddles local midnight is clipped to the window
    midnight = [("2026-06-09T23:00", "2026-06-10T01:00")]
    assert find_slots(midnight, "2026-06-10", 60, 1) == ["2026-06-09T15:00:00Z"]


def test_slots_reject_bad_input():
    with pytest.raises(ValueError):
        find_slots([("2026-10-04T02:30", "2026-10-04T02:45")], "2026-10-04", 30, 1)   # skipped local start
    with pytest.raises(ValueError):
        find_slots([], "2026-06-10", 0, 1)
    with pytest.raises(ValueError):
        find_slots([("2026-06-10T03:00:00Z", "2026-06-10T02:00:00Z")], "2026-06-10", 30, 1)
