"""Unit-Tests für S2 — VWAPPullback (SPEC §5/S2).

Synthetische OHLCV-Serien inline (numpy, seed-kontrolliert). Die Strategie
wird isoliert mit Dummy-DataFrames getestet; core.*-Imports laufen über die
Fallbacks in strategies.base (Smoke-Test unten als xfail markiert).

Abgedeckt:
- erwartetes Long-/Short-Signal im Fenster 9:45–11:30 ET
- kein Signal außerhalb des Fensters
- DST-Asynchronwochen (März/November, US≠EU) + Winter (EST)
- Max 1 Long/Tag (Daily-Cap)
- RR>=2-Gate (kein Trade, wenn PDH/Fallback < 2R)
- Kausalität (Abschneiden nach Bar i ändert Signal nicht)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.base import Signal, Strategy
from strategies.s2_vwap_pullback import VWAPPullback

NY = "America/New_York"


# --------------------------------------------------------------------------- #
# Synthetische Daten
# --------------------------------------------------------------------------- #

def _mk(idx, o, h, l, c, v=1000.0) -> pd.DataFrame:
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c,
                         "tick_volume": v}, index=idx)


def prev_day(date_utc: str, center: float = 105.5, amp: float = 0.3,
             utc_start: str = "13:30") -> pd.DataFrame:
    """Flacher Vortag (PDH/PDL-Referenz), 78 M5-Bars."""
    rng = np.random.default_rng(42)
    idx = pd.date_range(f"{date_utc} {utc_start}", periods=78, freq="5min",
                        tz="UTC")
    px = center
    o, h, l, c = [], [], [], []
    for _ in range(len(idx)):
        px = max(center - amp, min(center + amp, px + rng.normal(0, 0.05)))
        o.append(px)
        c.append(px + 0.02)
        h.append(px + 0.15)
        l.append(px - 0.15)
    return _mk(idx, o, h, l, c)


LONG_PATTERN = [100.0, 100.6, 101.2,      # 09:30-09:40 VWAP-Aufwärmung
                101.8, 102.4, 102.6,      # 09:45-09:55 >=3 Closes über VWAP
                101.3,                    # 10:00 Pullback: Low touched VWAP
                102.1]                    # 10:05 Trigger: Close über VWAP

SHORT_PATTERN = [107.0, 106.4, 105.8,
                 105.2, 104.8, 104.6,
                 105.7,                   # Pullback: High touched VWAP
                 104.9]                   # Trigger: Close unter VWAP


def pattern_day(date_utc: str, utc_start: str, closes: list[float],
                touches=(6,)) -> pd.DataFrame:
    idx = pd.date_range(f"{date_utc} {utc_start}", periods=len(closes),
                        freq="5min", tz="UTC")
    o, h, l, c = [], [], [], []
    prev = None
    for k, cl in enumerate(closes):
        op = prev if prev is not None else cl - 0.1
        hi = max(op, cl) + 0.3
        lo = min(op, cl) - 0.3
        if k in touches:
            if cl >= (prev if prev is not None else cl):
                lo = cl - 1.2   # Long: Dip bis VWAP
            else:
                hi = cl + 1.2   # Short: Spike bis VWAP
        o.append(op)
        h.append(hi)
        l.append(lo)
        c.append(cl)
        prev = cl
    return _mk(idx, o, h, l, c)


def run_all(strat: Strategy, m5: pd.DataFrame) -> list[Signal]:
    return [s for i in range(len(m5))
            if (s := strat.on_bar({"M5": m5}, i)) is not None]


def make_long_day(day="2024-06-04", prev="2024-06-03", utc_start="13:30",
                  prev_center=105.5, pattern=None) -> pd.DataFrame:
    return pd.concat([prev_day(prev, center=prev_center),
                      pattern_day(day, utc_start, pattern or LONG_PATTERN)])


# --------------------------------------------------------------------------- #
# Erwartete Signale
# --------------------------------------------------------------------------- #

def test_long_signal():
    m5 = make_long_day()
    sigs = run_all(VWAPPullback({}), m5)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == +1
    assert s.time.tz_convert(NY).time() == pd.Timestamp("10:05").time()
    assert s.entry_type == "market" and s.entry_price is None
    assert s.stop_loss < 102.1 < s.take_profit
    assert s.meta["tp_used"] == "pdh"             # TP = Vortages-High
    assert s.take_profit == pytest.approx(105.924, abs=0.01)
    rr = (s.take_profit - 102.1) / (102.1 - s.stop_loss)
    assert rr >= 2.0
    assert s.meta["time_exit"] == "11:30" and s.meta["time_exit_tz"] == NY
    assert s.meta["trail"] is None                # kein Trailing
    assert s.risk_pct == pytest.approx(0.005)
    assert "news_blackout" in s.meta
    assert s.meta["spread_guard_points"] == 2.0


def test_short_signal():
    m5 = pd.concat([prev_day("2024-06-03", center=101.5),
                    pattern_day("2024-06-04", "13:30", SHORT_PATTERN)])
    sigs = run_all(VWAPPullback({}), m5)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == -1
    assert s.stop_loss > 104.9 > s.take_profit
    assert s.meta["tp_used"] == "pdl"             # TP = Vortages-Tief
    rr = (104.9 - s.take_profit) / (s.stop_loss - 104.9)
    assert rr >= 2.0


# --------------------------------------------------------------------------- #
# Fenster / DST
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("day,prev,utc_start,expected_utc", [
    ("2024-06-04", "2024-06-03", "13:30", "14:05"),   # EDT (Sommer)
    ("2024-01-16", "2024-01-15", "14:30", "15:05"),   # EST (Winter)
    ("2024-03-12", "2024-03-11", "13:30", "14:05"),   # DST-Asynchronwoche März
    ("2024-10-30", "2024-10-29", "13:30", "14:05"),   # DST-Asynchronwoche Nov
])
def test_session_window_dst(day, prev, utc_start, expected_utc):
    """Signal landet in allen DST-Konstellationen um 10:05 ET (9:45–11:30)."""
    m5 = make_long_day(day=day, prev=prev, utc_start=utc_start)
    sigs = run_all(VWAPPullback({}), m5)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.time.strftime("%H:%M") == expected_utc
    assert s.time.tz_convert(NY).time() == pd.Timestamp("10:05").time()


def test_no_signal_outside_window():
    """Gleiches Muster, Trigger erst 11:35 ET (> last_trigger 11:25) -> nichts."""
    m5 = make_long_day(day="2024-06-04", prev="2024-06-03", utc_start="14:55")
    # Trigger-Bar = 16:20 UTC = 12:20 ET... Kontext/Fenster prüfen:
    trigger_et = pd.Timestamp("2024-06-04 16:20", tz="UTC").tz_convert(NY)
    assert trigger_et.time() > pd.Timestamp("11:30").time()
    assert run_all(VWAPPullback({}), m5) == []


def test_entry_window_start_guard():
    """Fenster-Beginn ist parametrisiert; Trigger vor entry_start -> nichts.

    (Strukturell kann ohnehin kein Signal vor 9:45 ET entstehen, weil der
    Kontext >=3 Closes seit 9:45 verlangt; hier wird der Fenster-Guard selbst
    getestet, indem entry_start hinter den Trigger gelegt wird.)
    """
    m5 = make_long_day()
    strat = VWAPPullback({"entry_start": "10:30"})
    assert run_all(strat, m5) == []
    # und zur Sicherheit: ohne Verschiebung feuert dasselbe Muster
    assert len(run_all(VWAPPullback({}), m5)) == 1
    # kein Signal vor 9:45 ET im gesamten Datensatz
    for i in range(len(m5)):
        s = VWAPPullback({}).on_bar({"M5": m5}, i)  # frischer State je Aufruf
        if s is not None:
            assert s.time.tz_convert(NY).time() >= pd.Timestamp("09:45").time()


# --------------------------------------------------------------------------- #
# Tages-Limits / RR-Gate / Guards
# --------------------------------------------------------------------------- #

def test_max_one_long_per_day():
    closes = LONG_PATTERN + [101.9, 101.0, 101.8]  # zweites Long-Setup
    m5 = pd.concat([prev_day("2024-06-03"),
                    pattern_day("2024-06-04", "13:30", closes, touches=(6, 9))])
    sigs = run_all(VWAPPullback({}), m5)
    assert len(sigs) == 1
    assert sigs[0].direction == +1


def test_rr_gate_blocks_trade():
    """PDH zu nah und 2×ATR-Fallback < 2R -> kein Trade."""
    m5 = make_long_day(prev_center=102.3)
    assert run_all(VWAPPullback({}), m5) == []


def test_spread_guard_blocks_trade():
    m5 = make_long_day()
    strat = VWAPPullback({"current_spread_points": 3.0})  # > max 2.0
    assert run_all(strat, m5) == []
    strat_ok = VWAPPullback({"current_spread_points": 3.0,
                             "filters": {"spread_guard": False}})
    assert len(run_all(strat_ok, m5)) == 1


def test_news_blackout_blocks_trade():
    m5 = make_long_day()
    strat = VWAPPullback({"news_blackout": True})
    assert run_all(strat, m5) == []


# --------------------------------------------------------------------------- #
# Kausalität
# --------------------------------------------------------------------------- #

def test_causality():
    """Signal bei Bar i unverändert, wenn Daten nach i abgeschnitten werden."""
    m5 = make_long_day()
    sigs_full = run_all(VWAPPullback({}), m5)
    assert len(sigs_full) == 1
    i_star = int(m5.index.get_loc(sigs_full[0].time))

    m5_cut = m5.iloc[: i_star + 1]
    sigs_cut = run_all(VWAPPullback({}), m5_cut)
    assert len(sigs_cut) == 1
    a, b = sigs_full[0], sigs_cut[0]
    assert (a.time, a.direction, a.stop_loss, a.take_profit) == \
           (b.time, b.direction, b.stop_loss, b.take_profit)


# --------------------------------------------------------------------------- #
# Smoke-Test: core-Module importierbar
# --------------------------------------------------------------------------- #

def test_core_imports_smoke():
    from core.indicators import vwap_session, rsi, atr  # noqa: F401
    from core.time_engine import ny_time, in_session  # noqa: F401
