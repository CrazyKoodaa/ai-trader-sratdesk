"""tests/test_s22.py — Unit-Tests fuer S22 SessionCloseDrift.

Deckt: Trigger-Stunde (Signal auf trigger_hour = entry_hour-1, kausal, kein
Lookahead auf die Entry-Bar selbst), Time-Exit-Meta korrekt gesetzt, ATR-SL
korrekt (long-only), Backward-Compat-Defaults, Determinismus.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.base import Signal, Strategy
from strategies.s22_session_close_drift import S22SessionCloseDrift

ATR_LEN = 14
WARMUP = ATR_LEN + 5


def _hourly_df(n: int, start_hour_utc: int = 0, level: float = 100.0,
              wobble: float = 0.3, seed: int = 3) -> pd.DataFrame:
    """n H1-Bars ab ``start_hour_utc`` UTC, kleine Range (fuer stabilen ATR)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(f"2023-01-02 {start_hour_utc:02d}:00", periods=n,
                        freq="1h", tz="UTC")
    close = level + rng.normal(0.0, wobble, n)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + wobble
    low = np.minimum(open_, close) - wobble
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": 1000.0}, index=idx)


def base_params(**overrides) -> dict:
    p = {"symbol": "XAUUSD", "primary_tf": "H1", "entry_hour_utc": 22,
         "hold_hours": 2, "atr_len": ATR_LEN, "sl_atr_mult": 2.0, "risk_pct": 0.005}
    p.update(overrides)
    return p


def test_base_contract():
    strat = S22SessionCloseDrift(base_params())
    assert isinstance(strat, Strategy)
    assert strat.name == "s22_session_close_drift"
    assert strat.required_timeframes == ["H1"]


def test_backward_compatible_defaults():
    strat = S22SessionCloseDrift({})
    assert strat.entry_hour_utc == 22
    assert strat.hold_hours == 2
    assert strat.primary_tf == "H1"


def test_no_signal_before_warmup():
    df = _hourly_df(WARMUP, start_hour_utc=0)
    strat = S22SessionCloseDrift(base_params())
    bars = {"H1": df}
    for i in range(len(df)):
        assert strat.on_bar(bars, i) is None


def test_fires_exactly_on_entry_hour_itself():
    # entry_hour_utc=22 -> Signal auf der Bar MIT hour==22 selbst (nicht
    # hour==21 -- Trigger-Design bewusst robust gegen die dokumentierte
    # Feed-Luecke bei Stunde 21, s. Docstring der Strategie). Fill = Open
    # der naechsten Bar (SPEC "Market-Entry naechste Bar").
    df = _hourly_df(WARMUP + 30, start_hour_utc=0)
    strat = S22SessionCloseDrift(base_params())
    bars = {"H1": df}
    fired_hours = set()
    for i in range(len(df)):
        sig = strat.on_bar(bars, i)
        if sig is not None:
            fired_hours.add(df.index[i].hour)
    assert fired_hours == {22}


def test_signal_long_only_with_atr_sl_no_tp():
    df = _hourly_df(WARMUP + 25, start_hour_utc=0)
    strat = S22SessionCloseDrift(base_params())
    bars = {"H1": df}
    sig = None
    for i in range(len(df)):
        sig = strat.on_bar(bars, i)
        if sig is not None:
            break
    assert isinstance(sig, Signal)
    assert sig.direction == 1
    assert sig.take_profit is None
    c = float(df["close"].iloc[list(df.index).index(sig.time)])
    a = sig.meta["atr"]
    assert sig.stop_loss == pytest.approx(c - 2.0 * a)
    assert sig.meta["time_exit_bars"] == 2
    assert sig.meta["entry_hour_utc"] == 22


def test_custom_entry_hour_and_hold():
    df = _hourly_df(WARMUP + 30, start_hour_utc=0)
    strat = S22SessionCloseDrift(base_params(entry_hour_utc=5, hold_hours=4))
    bars = {"H1": df}
    fired_hours = set()
    sig = None
    for i in range(len(df)):
        s = strat.on_bar(bars, i)
        if s is not None:
            fired_hours.add(df.index[i].hour)
            sig = s
    assert fired_hours == {5}  # trigger = entry_hour_utc selbst
    assert sig.meta["time_exit_bars"] == 4


def test_entry_hour_zero_fires_on_hour_zero_directly():
    df = _hourly_df(WARMUP + 30, start_hour_utc=0)
    strat = S22SessionCloseDrift(base_params(entry_hour_utc=0))
    bars = {"H1": df}
    fired_hours = set()
    for i in range(len(df)):
        s = strat.on_bar(bars, i)
        if s is not None:
            fired_hours.add(df.index[i].hour)
    assert fired_hours == {0}


def test_fires_at_most_once_per_calendar_day():
    # Sicherheitsnetz-Guard: selbst wenn dieselbe Stunde zweimal am selben
    # Tag im View vorkaeme (sollte bei echten stuendlichen Bars nicht
    # passieren), darf nur EIN Signal pro Tag emittiert werden.
    df = _hourly_df(WARMUP + 30, start_hour_utc=0)
    strat = S22SessionCloseDrift(base_params())
    bars = {"H1": df}
    i_hour22 = [i for i in range(len(df)) if df.index[i].hour == 22 and i >= ATR_LEN][0]
    first = strat.on_bar(bars, i_hour22)
    second = strat.on_bar(bars, i_hour22)  # erneuter Aufruf, gleicher Tag/Stunde
    assert first is not None
    assert second is None


def test_deterministic_rerun():
    df = _hourly_df(WARMUP + 25, start_hour_utc=0)
    params = base_params()
    bars = {"H1": df}

    def first_signal(strat):
        for i in range(len(df)):
            sig = strat.on_bar(bars, i)
            if sig is not None:
                return sig
        return None

    s1 = first_signal(S22SessionCloseDrift(params))
    s2 = first_signal(S22SessionCloseDrift(params))
    assert s1 is not None and s2 is not None
    assert s1.stop_loss == s2.stop_loss
    assert s1.meta["atr"] == s2.meta["atr"]
