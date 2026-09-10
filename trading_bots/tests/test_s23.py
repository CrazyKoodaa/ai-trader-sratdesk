"""tests/test_s23.py — Unit-Tests fuer S23 EngulfingReversal.

Deckt: Struktur-Extrem-Erfordernis (Donchian, kausal), echtes 2-Kerzen-
Engulfing (nicht nur "grosse Bar"), Volumen-Bestaetigung, alle drei
zusammen noetig (jedes einzelne Kriterium fehlend -> kein Signal),
Long/Short, Backward-Compat-Defaults, Determinismus.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.base import Signal, Strategy
from strategies.s23_engulfing_reversal import S23EngulfingReversal

DON_LEN = 20
ATR_LEN = 14
VOL_LEN = 20
WARMUP = max(DON_LEN, ATR_LEN, VOL_LEN) + 5


def _flat_range_df(n: int, level: float = 100.0, wobble: float = 0.3,
                   base_vol: float = 1000.0, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=n, freq="4h", tz="UTC")
    close = level + rng.normal(0.0, wobble, n)
    open_ = np.empty(n)
    open_[0] = level
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) + wobble
    low = np.minimum(open_, close) - wobble
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": base_vol}, index=idx)


def _append_bar(df: pd.DataFrame, o: float, h: float, l: float, c: float, v: float) -> pd.DataFrame:
    next_ts = df.index[-1] + pd.Timedelta(hours=4)
    row = pd.DataFrame({"open": [o], "high": [h], "low": [l], "close": [c],
                        "tick_volume": [v]}, index=[next_ts])
    return pd.concat([df, row])


def base_params(**overrides) -> dict:
    p = {"symbol": "XAUUSD", "primary_tf": "H4", "don_len": DON_LEN,
         "atr_len": ATR_LEN, "vol_len": VOL_LEN, "vol_mult": 1.5,
         "sl_atr_buffer": 0.3, "min_rr": 2.0, "risk_pct": 0.005}
    p.update(overrides)
    return p


def _make_long_setup(vol_mult_ok: bool = True, engulf_ok: bool = True,
                     at_extreme: bool = True) -> pd.DataFrame:
    """Range-Bars, dann eine Bar, die (je nach Flags) das Donchian-Tief
    NICHT/DOCH beruehrt, mit/ohne echtes bullisches Engulfing, mit/ohne
    Volumen-Klimax -- fuer die vorletzte Bar (Vorbar des Engulfing-Musters)."""
    df = _flat_range_df(WARMUP + 5)
    chan_low = float(df["low"].iloc[-DON_LEN:].min())

    # Vorbar: kleiner bearischer Koerper knapp ueber dem Kanal-Tief
    prev_low_level = chan_low + 1.0 if at_extreme else chan_low + 5.0
    df = _append_bar(df, o=prev_low_level + 0.5, h=prev_low_level + 0.6,
                     l=prev_low_level - 0.1, c=prev_low_level, v=1000.0)

    if engulf_ok:
        # Bullische Bar, die den Koerper der Vorbar (prev_low_level..prev_low_level+0.5) umschliesst
        eo, ec = prev_low_level - 0.2, prev_low_level + 1.0
    else:
        # Bullisch, aber KEIN echtes Engulfing (Koerper kleiner als Vorbar)
        eo, ec = prev_low_level + 0.1, prev_low_level + 0.3

    low_touch = chan_low - 0.5 if at_extreme else prev_low_level - 1.0
    vol = 2000.0 if vol_mult_ok else 500.0  # avg_vol ~1000 (Range-Bars) -> 2000=2x, 500=0.5x
    df = _append_bar(df, o=eo, h=ec + 0.2, l=low_touch, c=ec, v=vol)
    return df


class TestBaseContract:
    def test_base_contract(self):
        strat = S23EngulfingReversal(base_params())
        assert isinstance(strat, Strategy)
        assert strat.name == "s23_engulfing_reversal"
        assert strat.required_timeframes == ["H4"]

    def test_backward_compatible_defaults(self):
        strat = S23EngulfingReversal({})
        assert strat.don_len == 20
        assert strat.primary_tf == "H4"
        assert strat.vol_mult == pytest.approx(1.5)


class TestLongEngulfingReversal:
    def test_fires_when_all_three_conditions_met(self):
        df = _make_long_setup(vol_mult_ok=True, engulf_ok=True, at_extreme=True)
        strat = S23EngulfingReversal(base_params())
        sig = strat.on_bar({"H4": df}, len(df) - 1)
        assert isinstance(sig, Signal)
        assert sig.direction == 1
        assert sig.meta["tp_converts_to_trail"] is True

    def test_no_signal_without_structure_extreme(self):
        df = _make_long_setup(vol_mult_ok=True, engulf_ok=True, at_extreme=False)
        strat = S23EngulfingReversal(base_params())
        assert strat.on_bar({"H4": df}, len(df) - 1) is None

    def test_no_signal_without_true_engulfing(self):
        df = _make_long_setup(vol_mult_ok=True, engulf_ok=False, at_extreme=True)
        strat = S23EngulfingReversal(base_params())
        assert strat.on_bar({"H4": df}, len(df) - 1) is None

    def test_no_signal_without_volume_confirmation(self):
        df = _make_long_setup(vol_mult_ok=False, engulf_ok=True, at_extreme=True)
        strat = S23EngulfingReversal(base_params())
        assert strat.on_bar({"H4": df}, len(df) - 1) is None


class TestShortEngulfingReversal:
    def _make_short_setup(self) -> pd.DataFrame:
        df = _flat_range_df(WARMUP + 5)
        chan_high = float(df["high"].iloc[-DON_LEN:].max())
        prev_high_level = chan_high - 1.0
        df = _append_bar(df, o=prev_high_level - 0.5, h=prev_high_level,
                         l=prev_high_level - 0.6, c=prev_high_level - 0.1, v=1000.0)
        # Baerische Bar, die die Vorbar umschliesst + Kanal-Hoch beruehrt
        eo, ec = prev_high_level + 0.2, prev_high_level - 1.0
        high_touch = chan_high + 0.5
        df = _append_bar(df, o=eo, h=high_touch, l=ec - 0.2, c=ec, v=2000.0)
        return df

    def test_fires_short_when_all_conditions_met(self):
        df = self._make_short_setup()
        strat = S23EngulfingReversal(base_params())
        sig = strat.on_bar({"H4": df}, len(df) - 1)
        assert isinstance(sig, Signal)
        assert sig.direction == -1


class TestDeterminism:
    def test_deterministic_rerun(self):
        df = _make_long_setup(vol_mult_ok=True, engulf_ok=True, at_extreme=True)
        params = base_params()
        s1 = S23EngulfingReversal(params).on_bar({"H4": df}, len(df) - 1)
        s2 = S23EngulfingReversal(params).on_bar({"H4": df}, len(df) - 1)
        assert s1 is not None and s2 is not None
        assert s1.stop_loss == s2.stop_loss
        assert s1.take_profit == s2.take_profit
