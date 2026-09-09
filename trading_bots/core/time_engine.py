"""core/time_engine.py — Zeitzonen, Sessions, Server-Offset (SPEC §4.4).

Alle Zeitreihen im Framework sind UTC, tz-aware ("UTC-at-ingestion").
Sessions werden ausschließlich via ``zoneinfo`` in der jeweiligen
Börsen-Zeitzone (z. B. "America/New_York", "Europe/London") definiert —
NIEMALS Serverzeit hardcoden (DST-Asynchronwochen US/EU!).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Konvertierung
# ---------------------------------------------------------------------------

def to_utc(ts: "pd.Timestamp | pd.Series | pd.DatetimeIndex", from_tz: str):
    """Konvertiert Zeitstempel nach UTC (tz-aware).

    - Naive Zeitstempel werden als Ortszeit in ``from_tz`` interpretiert
      (tz_localize) und dann nach UTC konvertiert.
    - Bereits tz-aware Zeitstempel werden nach UTC konvertiert
      (``from_tz`` wird dann ignoriert).

    Funktioniert für ``pd.Timestamp``, ``pd.Series`` (datetime64) und
    ``pd.DatetimeIndex``.
    """
    tz = ZoneInfo(from_tz)
    if isinstance(ts, pd.Series):
        if ts.dt.tz is None:
            return ts.dt.tz_localize(tz).dt.tz_convert(UTC)
        return ts.dt.tz_convert(UTC)
    ts = pd.Timestamp(ts)
    if ts.tz is None:
        ts = ts.tz_localize(tz)
    return ts.tz_convert(UTC)


def ny_time(ts_utc: "pd.Timestamp | pd.Series | pd.DatetimeIndex"):
    """Shortcut: UTC -> America/New_York."""
    ny = ZoneInfo("America/New_York")
    if isinstance(ts_utc, pd.Series):
        return ts_utc.dt.tz_convert(ny)
    return pd.Timestamp(ts_utc).tz_convert(ny)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    h, m = hhmm.split(":")
    return int(h), int(m)


def _in_window_minutes(minute_of_day: int, start_min: int, end_min: int) -> bool:
    """Halboffenes Fenster [start, end); end <= start = über Mitternacht."""
    if start_min == end_min:
        return True  # 00:00-00:00 = ganztägig
    if start_min < end_min:
        return start_min <= minute_of_day < end_min
    return minute_of_day >= start_min or minute_of_day < end_min


def in_session(ts_utc: pd.Timestamp, session: str, start_hhmm: str, end_hhmm: str) -> bool:
    """True, wenn ``ts_utc`` (UTC, aware) innerhalb des Session-Fensters liegt.

    Das Fenster wird in der Ortszeit der Zone ``session``
    (z. B. "America/New_York", "Europe/London", "UTC") ausgewertet und ist
    damit automatisch DST-sicher. Fenster wie "22:00"-"02:00" laufen über
    Mitternacht. Grenzen: [start, end) — die End-Minute gehört nicht mehr
    zur Session.
    """
    ts = pd.Timestamp(ts_utc)
    if ts.tz is None:
        raise ValueError("ts_utc muss tz-aware (UTC) sein")
    local = ts.tz_convert(ZoneInfo(session))
    sh, sm = _parse_hhmm(start_hhmm)
    eh, em = _parse_hhmm(end_hhmm)
    return _in_window_minutes(local.hour * 60 + local.minute, sh * 60 + sm, eh * 60 + em)


def session_window_mask(index_utc: pd.DatetimeIndex, tz: str, start: str, end: str) -> np.ndarray:
    """Vektorisierte Variante von ``in_session`` für einen UTC-DatetimeIndex.

    Liefert bool-ndarray (len == len(index_utc)); True = Bar-Zeitstempel
    liegt im Session-Fenster [start, end) in Ortszeit der Zone ``tz``.
    """
    idx = pd.DatetimeIndex(index_utc)
    if idx.tz is None:
        raise ValueError("index_utc muss tz-aware (UTC) sein")
    local = idx.tz_convert(ZoneInfo(tz))
    minute_of_day = np.asarray(local.hour) * 60 + np.asarray(local.minute)
    sh, sm = _parse_hhmm(start)
    eh, em = _parse_hhmm(end)
    start_min, end_min = sh * 60 + sm, eh * 60 + em
    if start_min == end_min:
        return np.ones(len(idx), dtype=bool)
    if start_min < end_min:
        return (minute_of_day >= start_min) & (minute_of_day < end_min)
    return (minute_of_day >= start_min) | (minute_of_day < end_min)


# ---------------------------------------------------------------------------
# Server-Offset
# ---------------------------------------------------------------------------

def estimate_server_offset_utc(tick_time_epoch: int) -> timedelta:
    """Schätzt den Offset Serverzeit − UTC aus einem MT5-Tick-Timestamp.

    MT5 liefert ``symbol_info_tick().time`` als Epoch-Sekunden der
    *Serverzeit* (meist EET/EEST, d. h. UTC+2/+3). Interpretiert man diese
    Epoch-Zahl als UTC, ergibt die Differenz zu "jetzt" den Server-Offset.

    Der Rohewert wird auf volle 15 Minuten gerundet (Typo-/Latenzrobust).
    """
    server_as_utc = datetime.fromtimestamp(int(tick_time_epoch), tz=UTC)
    raw = server_as_utc - datetime.now(UTC)
    quarter_hours = round(raw.total_seconds() / 900.0)
    return timedelta(minutes=15 * quarter_hours)
