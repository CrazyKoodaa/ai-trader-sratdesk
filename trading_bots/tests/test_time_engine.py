"""Tests für core/time_engine.py — inkl. US/EU-DST-Asynchronwochen.

DST-Fakten 2026:
- US (America/New_York): DST 08.03.2026 – 01.11.2026 (EDT = UTC-4, sonst EST = UTC-5)
- EU (Europe/London):    DST 29.03.2026 – 25.10.2026 (BST = UTC+1, sonst GMT = UTC+0)
- Asynchron-Wochen: 09.–28.03.2026 (US in DST, EU nicht) und
  26.10.–01.11.2026 (EU nicht mehr, US noch in DST).
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from core.time_engine import (
    estimate_server_offset_utc,
    in_session,
    ny_time,
    session_window_mask,
    to_utc,
)

UTC = timezone.utc
# Montage in den drei relevanten Wochen
ASYNC_MARCH = pd.Timestamp("2026-03-16", tz=UTC)   # US in DST, EU NICHT
SUMMER = pd.Timestamp("2026-06-15", tz=UTC)        # beide in DST
ASYNC_OCT = pd.Timestamp("2026-10-26", tz=UTC)     # EU nicht mehr, US noch in DST
WINTER = pd.Timestamp("2026-01-12", tz=UTC)        # beide nicht in DST


def at(day: pd.Timestamp, hhmm: str) -> pd.Timestamp:
    h, m = map(int, hhmm.split(":"))
    return day + pd.Timedelta(hours=h, minutes=m)


# ---------------------------------------------------------------------------
# to_utc / ny_time
# ---------------------------------------------------------------------------

def test_to_utc_naive_ny_async_week():
    # 16.03.2026: NY in EDT (UTC-4), London noch GMT (UTC+0)
    ts = to_utc(pd.Timestamp("2026-03-16 09:30"), "America/New_York")
    assert ts == pd.Timestamp("2026-03-16 13:30", tz=UTC)


def test_to_utc_naive_london_async_week():
    ts = to_utc(pd.Timestamp("2026-03-16 09:30"), "Europe/London")
    assert ts == pd.Timestamp("2026-03-16 09:30", tz=UTC)  # GMT, kein BST!


def test_to_utc_aware_passthrough_and_series():
    aware = pd.Timestamp("2026-06-15 10:00", tz=UTC)
    assert to_utc(aware, "America/New_York") == aware
    s = pd.Series(pd.to_datetime(["2026-01-12 09:30", "2026-06-15 09:30"]))
    out = to_utc(s, "America/New_York")
    # Januar: EST (UTC-5) -> 14:30; Juni: EDT (UTC-4) -> 13:30
    assert list(out.dt.hour) == [14, 13]
    assert str(out.dt.tz) in ("UTC", "datetime.timezone.utc") or out.dt.tz == UTC


def test_ny_time_shortcut():
    assert ny_time(at(ASYNC_MARCH, "13:30")).hour == 9
    assert ny_time(at(WINTER, "14:30")).hour == 9  # EST im Winter


def test_dst_spring_forward_us():
    # 08.03.2026: 02:00 -> 03:00 in NY (Sprung 07:00 UTC)
    assert ny_time(pd.Timestamp("2026-03-08 06:30", tz=UTC)).utcoffset() == timedelta(hours=-5)
    assert ny_time(pd.Timestamp("2026-03-08 07:30", tz=UTC)).utcoffset() == timedelta(hours=-4)


# ---------------------------------------------------------------------------
# in_session
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "day,utc_time,session,start,end,expected",
    [
        # Asynchron-Woche März: NY 09:30-16:00 EDT -> 13:30 UTC Start
        (ASYNC_MARCH, "13:30", "America/New_York", "09:30", "16:00", True),
        (ASYNC_MARCH, "13:29", "America/New_York", "09:30", "16:00", False),
        (ASYNC_MARCH, "12:30", "America/New_York", "09:30", "16:00", False),  # wäre bei EST drin!
        # London in derselben Woche: GMT -> 08:00 UTC Start
        (ASYNC_MARCH, "08:00", "Europe/London", "08:00", "17:00", True),
        (ASYNC_MARCH, "07:59", "Europe/London", "08:00", "17:00", False),
        # Sommer, beide in DST: London BST -> 08:00 lokal = 07:00 UTC
        (SUMMER, "07:00", "Europe/London", "08:00", "17:00", True),
        (SUMMER, "06:59", "Europe/London", "08:00", "17:00", False),
        (SUMMER, "13:30", "America/New_York", "09:30", "16:00", True),
        # Asynchron-Woche Oktober: EU raus (GMT), US noch EDT
        (ASYNC_OCT, "08:00", "Europe/London", "08:00", "17:00", True),   # GMT
        (ASYNC_OCT, "13:30", "America/New_York", "09:30", "16:00", True),  # EDT
        # Winter: NY EST -> 09:30 = 14:30 UTC
        (WINTER, "14:30", "America/New_York", "09:30", "16:00", True),
        (WINTER, "13:30", "America/New_York", "09:30", "16:00", False),
        # End-Grenze exklusiv
        (ASYNC_MARCH, "20:00", "America/New_York", "09:30", "16:00", False),  # 16:00 EDT
        # Über Mitternacht
        (ASYNC_MARCH, "23:00", "UTC", "22:00", "02:00", True),
        (ASYNC_MARCH, "01:00", "UTC", "22:00", "02:00", True),
        (ASYNC_MARCH, "12:00", "UTC", "22:00", "02:00", False),
    ],
)
def test_in_session(day, utc_time, session, start, end, expected):
    assert in_session(at(day, utc_time), session, start, end) is expected


def test_in_session_rejects_naive():
    with pytest.raises(ValueError):
        in_session(pd.Timestamp("2026-03-16 13:30"), "UTC", "09:00", "10:00")


# ---------------------------------------------------------------------------
# session_window_mask
# ---------------------------------------------------------------------------

def test_session_window_mask_matches_scalar_and_dst():
    idx = pd.date_range("2026-03-16", "2026-03-17", freq="30min", tz=UTC, inclusive="left")
    mask = session_window_mask(idx, "America/New_York", "09:30", "16:00")
    expected = np.array(
        [in_session(ts, "America/New_York", "09:30", "16:00") for ts in idx]
    )
    assert mask.dtype == bool
    assert (mask == expected).all()
    # EDT: 13:30-20:00 UTC, halboffen -> 13:30..19:30 UTC = 13 Bars
    assert mask.sum() == 13
    assert idx[mask][0] == pd.Timestamp("2026-03-16 13:30", tz=UTC)


def test_session_window_mask_overnight():
    idx = pd.date_range("2026-01-12 20:00", "2026-01-13 05:00", freq="h", tz=UTC)
    mask = session_window_mask(idx, "UTC", "22:00", "02:00")
    on = [ts.strftime("%H:%M") for ts in idx[mask]]
    assert on == ["22:00", "23:00", "00:00", "01:00"]


# ---------------------------------------------------------------------------
# estimate_server_offset_utc
# ---------------------------------------------------------------------------

def test_estimate_server_offset_utc():
    import time

    for hours in (2, 3, -5):
        epoch = int(time.time() + hours * 3600)
        assert estimate_server_offset_utc(epoch) == timedelta(hours=hours)


# ---------------------------------------------------------------------------
# DST-Woche End-to-End: NY-Open-Wandlung über die Asynchronwoche
# ---------------------------------------------------------------------------

def test_ny_open_utc_shift_across_dst_transitions():
    # NY 09:30 in UTC: vor US-DST 14:30, Asynchronwoche 13:30, beide DST 13:30,
    # EU raus/US drin 13:30, Winter 14:30
    cases = [
        ("2026-03-02", "14:30"),  # beide Winterzeit
        ("2026-03-16", "13:30"),  # US DST, EU nicht
        ("2026-06-15", "13:30"),  # beide DST
        ("2026-10-26", "13:30"),  # EU Winter, US DST
        ("2026-11-02", "14:30"),  # beide Winterzeit
    ]
    for day, expect_utc in cases:
        ts = to_utc(pd.Timestamp(f"{day} 09:30"), "America/New_York")
        assert ts.strftime("%H:%M") == expect_utc
        assert in_session(ts, "America/New_York", "09:30", "16:00")


def test_london_open_utc_shift_across_dst_transitions():
    cases = [
        ("2026-03-02", "08:00"),   # GMT
        ("2026-03-16", "08:00"),   # noch GMT (US schon DST!)
        ("2026-06-15", "07:00"),   # BST
        ("2026-10-26", "08:00"),   # wieder GMT (US noch DST!)
        ("2026-11-02", "08:00"),   # GMT
    ]
    for day, expect_utc in cases:
        ts = to_utc(pd.Timestamp(f"{day} 08:00"), "Europe/London")
        assert ts.strftime("%H:%M") == expect_utc
        assert in_session(ts, "Europe/London", "08:00", "17:00")
