"""Tests für core/smc.py — Kausalität (kein Lookahead) im Fokus."""

import numpy as np
import pandas as pd
import pytest

from core.indicators import atr, swing_points
from core.smc import (
    equal_highs_lows,
    fair_value_gaps,
    liquidity_sweep,
    order_blocks,
    swing_structure,
)


def _df(high, low, close, open_=None):
    n = len(close)
    idx = pd.date_range("2021-01-01", periods=n, freq="h", tz="UTC")
    if open_ is None:
        open_ = [close[0]] + list(close[:-1])
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": [100.0] * n},
        index=idx, dtype="float64",
    )


# ---------------------------------------------------------------------------
# Fair Value Gaps
# ---------------------------------------------------------------------------

def test_fvg_bullish_bearish_and_confirmation():
    # Bar 2: low 10.5 > high[0] 10.0 -> bullisher FVG [10.0, 10.5]
    # Bar 5: high 9.5 < low[3] 10.1  -> bearisher FVG [9.5, 10.1]
    # (alle übrigen Bars überlappen -> keine unbeabsichtigten FVGs)
    high = [10.0, 10.2, 11.0, 10.8, 10.6, 9.5, 9.3]
    low = [9.5, 9.9, 10.5, 10.1, 9.2, 9.0, 8.8]
    close = [9.8, 10.0, 10.8, 10.2, 9.6, 9.2, 9.0]
    open_ = [9.8, 9.9, 10.6, 10.7, 10.3, 9.4, 9.2]
    df = _df(high, low, close, open_)
    out = fair_value_gaps(df, min_size_atr=0.0, atr=atr(df, 3))

    bull = out[out["direction"] == 1]
    assert len(bull) == 1
    assert bull["formed_at"].iloc[0] == df.index[2]
    assert bull["fvg_bottom"].iloc[0] == 10.0
    assert bull["fvg_top"].iloc[0] == 10.5
    # confirmed_at = formed + 1 Bar (SPEC §4.6)
    assert bull["confirmed_at"].iloc[0] == df.index[3]

    bear = out[out["direction"] == -1]
    assert len(bear) == 1
    assert bear["formed_at"].iloc[0] == df.index[5]
    assert bear["fvg_top"].iloc[0] == 10.1
    assert bear["fvg_bottom"].iloc[0] == 9.5
    assert bear["confirmed_at"].iloc[0] == df.index[6]


def test_fvg_min_size_filter_and_nat_confirmation():
    high = [10.0, 10.2, 11.0]
    low = [9.5, 9.8, 10.5]
    close = [9.8, 10.0, 10.8]
    df = _df(high, low, close)
    a = atr(df, 2)
    out = fair_value_gaps(df, min_size_atr=0.0, atr=a)
    assert len(out) == 1
    assert pd.isna(out["confirmed_at"].iloc[0])  # formed an letzter Bar
    # Größe 0.5; ATR ~ > 0 -> riesiger Filter entfernt die Lücke
    out_big = fair_value_gaps(df, min_size_atr=100.0, atr=a)
    assert out_big.empty
    assert list(out_big.columns) == ["fvg_top", "fvg_bottom", "direction", "formed_at", "confirmed_at"]


def test_fvg_anti_repaint():
    high = [10.0, 10.2, 11.0, 9.5, 9.2, 8.5, 8.8, 9.5, 10.0, 9.0]
    low = [9.5, 9.8, 10.5, 9.0, 8.8, 8.0, 8.2, 9.0, 9.2, 8.5]
    close = [9.8, 10.0, 10.8, 9.2, 9.0, 8.2, 8.5, 9.2, 9.6, 8.8]
    df = _df(high, low, close)
    full = fair_value_gaps(df, 0.0, atr(df, 3))
    k = 6
    part = fair_value_gaps(df.iloc[:k], 0.0, atr(df.iloc[:k], 3))
    # gleiche Events im Prefix; confirmed_at darf im Prefix höchstens NaT sein
    assert len(part) == len(full[full["formed_at"] < df.index[k]])
    merged = full.loc[part.index, ["fvg_top", "fvg_bottom", "direction", "formed_at"]]
    pd.testing.assert_frame_equal(
        merged, part[["fvg_top", "fvg_bottom", "direction", "formed_at"]]
    )
    both = full["confirmed_at"].notna() & part["confirmed_at"].notna()
    both = both[both].index.intersection(part.index)
    assert (full.loc[both, "confirmed_at"] == part.loc[both, "confirmed_at"]).all()


# ---------------------------------------------------------------------------
# Swing-Struktur: BOS / CHoCH
# ---------------------------------------------------------------------------

def _structure_df():
    """Aufwärtstrend (BOS up an Bar 9), dann Umkehr (CHoCH down an Bar 20).

    Swing-High 13.0 an Bar 2 (bestätigt Bar 4), Swing-Low 10.0 an Bar 5
    (bestätigt Bar 7), Swing-High 16.0 an Bar 12 (bestätigt Bar 14),
    Swing-Low 13.0 an Bar 16 (bestätigt Bar 18). left=right=2.
    """
    high = [10.0, 11.0, 13.0, 12.0, 12.0, 11.5, 12.0, 12.5, 12.8, 13.5,
            14.0, 15.0, 16.0, 15.0, 14.5, 14.0, 14.0, 14.5, 15.0, 14.0, 13.5, 13.0]
    low = [8.0, 9.0, 10.0, 11.0, 10.5, 10.0, 10.5, 11.0, 11.5, 12.0,
           13.0, 13.5, 14.0, 14.0, 14.0, 13.5, 13.0, 13.5, 14.0, 13.0, 12.5, 12.0]
    close = [9.0, 10.0, 11.0, 11.5, 11.0, 10.5, 11.0, 12.0, 12.5, 13.2,
             13.8, 14.5, 15.0, 14.5, 14.2, 13.8, 13.5, 14.0, 14.5, 13.2, 12.8, 12.5]
    return _df(high, low, close)


def test_swing_structure_bos_then_choch():
    df = _structure_df()
    ev = swing_structure(df, left=2, right=2)
    assert len(ev) == 2
    first, second = ev.iloc[0], ev.iloc[1]
    # BOS up: Close 13.2 > Swing-High 13.0 an Bar 9
    assert ev.index[0] == df.index[9]
    assert first["kind"] == "BOS"
    assert first["direction"] == 1
    assert first["level"] == 13.0
    assert first["swing_time"] == df.index[2]
    # CHoCH down: Close 12.8 < Swing-Low 13.0 an Bar 20 (Trend war up)
    assert ev.index[1] == df.index[20]
    assert second["kind"] == "CHoCH"
    assert second["direction"] == -1
    assert second["level"] == 13.0
    assert second["swing_time"] == df.index[16]


def test_swing_structure_causality_no_event_before_swing_confirmation():
    df = _structure_df()
    ev = swing_structure(df, left=2, right=2)
    sw = swing_points(df, left=2, right=2)
    for t, row in ev.iterrows():
        swing_t = row["swing_time"]
        if row["direction"] == 1:
            conf = sw.loc[swing_t, "swing_high_confirmed_at"]
        else:
            conf = sw.loc[swing_t, "swing_low_confirmed_at"]
        # Event erst nach ( streng: > ) der Swing-Bestätigung
        assert conf < t


def test_swing_structure_anti_repaint():
    df = _structure_df()
    full = swing_structure(df, left=2, right=2)
    k = 15  # vor dem CHoCH, nach dem BOS
    part = swing_structure(df.iloc[:k], left=2, right=2)
    assert len(part) == 1
    pd.testing.assert_series_equal(part.iloc[0], full.iloc[0])
    assert part.index[0] == full.index[0]


def test_swing_structure_empty_columns():
    df = _df([2, 2.1, 2.2, 2.3], [1, 1.1, 1.2, 1.3], [1.5, 2, 2.1, 2.2])
    ev = swing_structure(df, left=2, right=2)
    assert ev.empty
    assert list(ev.columns) == ["kind", "direction", "level", "swing_time"]


# ---------------------------------------------------------------------------
# Liquidity Sweep
# ---------------------------------------------------------------------------

def test_liquidity_sweep_above_and_below():
    # Bar 1: Wick über 10.0 (high 10.6), Close zurück auf 9.8 -> Sweep oben
    # Bar 2: berührt Level nur -> kein Sweep (kein Exzess >= 0.3)
    # Bar 3: Wick unter 10.0 (low 9.3), Close zurück auf 10.2 -> Sweep unten
    high = [9.9, 10.6, 10.1, 10.0]
    low = [9.5, 9.7, 9.8, 9.3]
    close = [9.8, 9.8, 10.0, 10.2]
    df = _df(high, low, close)
    out = liquidity_sweep(df, level=10.0, wick_excess_min=0.3)
    assert len(out) == 2
    assert out.loc[df.index[1], "side"] == 1
    assert out.loc[df.index[1], "wick_excess"] == pytest.approx(0.6)
    assert out.loc[df.index[3], "side"] == -1
    only_above = liquidity_sweep(df, level=10.0, wick_excess_min=0.3, direction="above")
    assert (only_above["side"] == 1).all()
    with pytest.raises(ValueError):
        liquidity_sweep(df, level=10.0, direction="sideways")


# ---------------------------------------------------------------------------
# Order Blocks
# ---------------------------------------------------------------------------

def test_order_blocks_from_structure_events():
    df = _structure_df()
    ev = swing_structure(df, left=2, right=2)
    obs = order_blocks(df, ev, max_lookback=20)
    assert len(obs) == 2
    # Bullishes Event an Bar 9: letzte bearishe Bar davor (nicht vor dem
    # gebrochenen Swing an Bar 2) ist Bar 5 (open 11.0 -> close 10.5)
    bull = obs[obs["direction"] == 1].iloc[0]
    assert bull["formed_at"] == df.index[5]
    assert bull["ob_bottom"] == 10.0
    assert bull["ob_top"] == 11.5
    assert bull["event_time"] == df.index[9]
    # Bearishes Event an Bar 20: letzte bullishe Bar davor ist Bar 18
    bear = obs[obs["direction"] == -1].iloc[0]
    assert bear["formed_at"] == df.index[18]
    assert bear["ob_bottom"] == 14.0
    assert bear["ob_top"] == 15.0


def test_order_blocks_requires_columns():
    df = _df([2, 3], [1, 1.5], [1.5, 2.5])
    with pytest.raises(ValueError):
        order_blocks(df, pd.DataFrame({"direction": [1]}))


# ---------------------------------------------------------------------------
# Equal Highs / Lows
# ---------------------------------------------------------------------------

def test_equal_highs_lows():
    n = 20
    high = [10.0] * 10 + [12.0] + [10.5] * 4 + [12.05] + [10.5] * 4
    low = [9.9] * n
    close = [9.95] * n
    df = _df(high, low, close)
    out = equal_highs_lows(df, tolerance_atr=0.5, lookback=10, atr_n=14)
    assert list(out.columns) == ["equal_high", "equal_low", "eq_high_level", "eq_low_level"]
    assert out["equal_high"].iloc[15]  # Double-Top 12.05 vs 12.0
    assert out["eq_high_level"].iloc[15] == pytest.approx(12.0)
    assert not out["equal_high"].iloc[11]  # 10.5 weit weg von 12.0
    # tiefe konstante Lows -> equal_low praktisch überall nach Warm-up
    assert out["equal_low"].iloc[15]


def test_equal_lows_double_bottom():
    n = 20
    low = [10.0] * 10 + [9.0] + [9.9] * 4 + [9.04] + [9.9] * 4
    high = [l + 0.2 for l in low]
    close = [l + 0.1 for l in low]
    df = _df(high, low, close)
    out = equal_highs_lows(df, tolerance_atr=0.5, lookback=10, atr_n=14)
    assert out["equal_low"].iloc[15]
    assert out["eq_low_level"].iloc[15] == pytest.approx(9.0)
    assert not out["equal_low"].iloc[12]
