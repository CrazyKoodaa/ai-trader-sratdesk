"""Unit-Tests für S1 — TrendPullback (SPEC §5/S1) + Base-Kontrakt (SPEC §4.1).

Synthetische OHLCV-Serien werden inline erzeugt (numpy, deterministisch).
Die Strategie-Logik wird isoliert getestet: Dummy-DataFrames werden direkt
übergeben; Imports aus core.* laufen über die Fallbacks in strategies.base,
solange core parallel gebaut wird (Smoke-Test unten als xfail markiert).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.base import Signal, Strategy
from strategies.s1_trend_pullback import TrendPullback

TRIGGER_TIME = pd.Timestamp("2023-09-19 12:00", tz="UTC")  # H4-Bar 45
N_H4 = 46


# --------------------------------------------------------------------------- #
# Synthetische Daten
# --------------------------------------------------------------------------- #

def make_d1(mode: str = "up") -> pd.DataFrame:
    """260 D1-Bars. 'up': stabiler Aufwärtstrend (Close>SMA200, DI+, ADX>=20).
    'down': stabiler Abwärtstrend (Short-Bias)."""
    idx = pd.date_range("2023-01-02", periods=260, freq="D", tz="UTC")
    if mode == "up":
        close = 1500 + np.arange(260) * 1.5
    elif mode == "down":
        close = 2200 - np.arange(260) * 1.5
    else:
        raise ValueError(mode)
    return pd.DataFrame(
        {"open": close - 1.0, "high": close + 4.0, "low": close - 4.0,
         "close": close, "tick_volume": 1000.0}, index=idx)


def make_h4(start: str = "2023-09-12 00:00",
            bullish_trigger: bool = True) -> pd.DataFrame:
    """H4: Aufwärtstrend -> Impuls 1977→2050 -> Pullback in Fib/EMA-Zone ->
    Trigger-Bar (Index 45, 12:00 UTC bzw. verschiebbar über `start`)."""
    closes = list(np.linspace(1950, 1982, 31)[1:])     # A: Trend
    closes += [1980.0, 1978.0, 1977.0]                  # B: Swing-Tief 1976
    closes += list(np.linspace(1977, 2050, 9)[1:])      # C: Impuls -> 2050
    closes += [2040.0, 2028.0, 2018.0, 2011.0]          # D: Pullback in Zone
    closes += [2014.0 if bullish_trigger else 2009.0]   # E: Trigger
    closes = np.asarray(closes)
    n = len(closes)
    idx = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    o = np.empty(n)
    h = np.empty(n)
    lo = np.empty(n)
    prev = closes[0] - 0.5
    for k in range(n):
        o[k] = prev
        if closes[k] >= o[k]:
            h[k] = closes[k] + 1.0
            lo[k] = o[k] - 0.4
        else:
            h[k] = o[k] + 0.4
            lo[k] = closes[k] - 1.0
        prev = closes[k]
    return pd.DataFrame(
        {"open": o, "high": h, "low": lo, "close": closes,
         "tick_volume": 1000.0}, index=idx)


def run_all(strat: Strategy, bars: dict[str, pd.DataFrame]) -> list[Signal]:
    return [s for i in range(len(bars["H4"]))
            if (s := strat.on_bar(bars, i)) is not None]


# --------------------------------------------------------------------------- #
# Base-Kontrakt (SPEC §4.1)
# --------------------------------------------------------------------------- #

def test_base_contract():
    strat = TrendPullback({})
    assert isinstance(strat, Strategy)
    assert strat.required_timeframes == ["H4", "D1"]
    assert strat.name == "s1_trend_pullback"
    assert isinstance(strat.params, dict)
    strat.on_trade_closed({"pnl": 1.0})  # optionaler Hook, kein State nötig
    sig_fields = set(Signal.__dataclass_fields__)
    assert sig_fields == {"time", "symbol", "direction", "entry_type",
                          "entry_price", "stop_loss", "take_profit",
                          "risk_pct", "meta", "expires_bars"}


# --------------------------------------------------------------------------- #
# V5 — erwartetes Signal
# --------------------------------------------------------------------------- #

def test_v5_long_signal():
    sigs = run_all(TrendPullback({}), {"H4": make_h4(), "D1": make_d1("up")})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.time == TRIGGER_TIME
    assert s.direction == +1
    assert s.entry_type == "market" and s.entry_price is None
    # SL: max(1.5*ATR14, hinter Swing-Extrem) -> hier Swing-Tief 1976.0
    assert s.stop_loss == pytest.approx(1976.0)
    ref = 2014.0  # Signal-Close
    r_dist = ref - s.stop_loss
    assert s.take_profit == pytest.approx(ref + 2.0 * r_dist)   # TP1 = 2R
    assert s.risk_pct == pytest.approx(0.005)
    assert s.meta["variant"] == "v5"
    assert s.meta["tp1_close_pct"] == 0.5
    assert s.meta["runner_trail"] == "h4_pivot"
    assert s.meta["time_exit_bars"] == 30
    assert "news_blackout" in s.meta and "regime_filter" in s.meta


def test_v5_no_signal_bearish_trigger():
    """Kein Reversal-Close in Bias-Richtung -> kein Signal."""
    sigs = run_all(TrendPullback({}),
                   {"H4": make_h4(bullish_trigger=False), "D1": make_d1("up")})
    assert sigs == []


def test_v5_no_signal_without_d1_bias():
    """D1-Abwärtstrend + Long-Pattern -> kein Signal (Bias-Gate)."""
    sigs = run_all(TrendPullback({}), {"H4": make_h4(), "D1": make_d1("down")})
    assert sigs == []


def mirror_h4(h4: pd.DataFrame, pivot: float = 4000.0) -> pd.DataFrame:
    """Spiegelt OHLC an `pivot` (Long-Szene -> Short-Szene); high/low tauschen."""
    out = pd.DataFrame(index=h4.index)
    out["open"] = pivot - h4["open"]
    out["close"] = pivot - h4["close"]
    out["high"] = pivot - h4["low"]
    out["low"] = pivot - h4["high"]
    out["tick_volume"] = h4["tick_volume"]
    return out


def test_v5_sl_tp_geometry_long_and_short():
    """SL/TP-Geometrie (SPEC §5/S1): Long -> SL < Ref < TP, Short -> TP < Ref < SL;
    TP1-Distanz = tp1_r x SL-Distanz (Ref = Signal-Close, Entry nächste Bar)."""
    tp1_r = 2.0  # Default tp1_r
    # --- Long ---
    (s_long,) = run_all(TrendPullback({}), {"H4": make_h4(), "D1": make_d1("up")})
    ref_l = 2014.0  # Signal-Close (Trigger-Bar)
    assert s_long.direction == +1
    assert s_long.stop_loss < ref_l < s_long.take_profit
    assert (s_long.take_profit - ref_l) == \
        pytest.approx(tp1_r * (ref_l - s_long.stop_loss))
    # --- Short (gespiegelte H4-Daten + Short-Bias) ---
    sigs = run_all(TrendPullback({}),
                   {"H4": mirror_h4(make_h4()), "D1": make_d1("down")})
    assert len(sigs) == 1
    s_short = sigs[0]
    ref_s = 4000.0 - ref_l
    assert s_short.direction == -1
    assert s_short.time == s_long.time          # Szene exakt gespiegelt
    assert s_short.take_profit < ref_s < s_short.stop_loss
    assert (ref_s - s_short.take_profit) == \
        pytest.approx(tp1_r * (s_short.stop_loss - ref_s))
    # Spiegel-Symmetrie: SL hinter gespiegeltem Swing-Extrem (1976 -> 2024)
    assert s_short.stop_loss == pytest.approx(4000.0 - s_long.stop_loss)
    assert s_short.take_profit == pytest.approx(4000.0 - s_long.take_profit)


def test_v5_session_filter_ab_flag():
    """Trigger um 02:00 UTC: mit session_filter kein Signal, ohne schon."""
    h4_late = make_h4(start="2023-09-11 14:00")  # Bar 45 = 02:00 UTC
    assert h4_late.index[45].hour == 2
    d1 = make_d1("up")
    assert run_all(TrendPullback({}), {"H4": h4_late, "D1": d1}) == []
    sigs = run_all(TrendPullback({"filters": {"session_filter": False}}),
                   {"H4": h4_late, "D1": d1})
    assert len(sigs) == 1 and sigs[0].direction == +1


def test_v5_causality():
    """Signal bei Bar i ist unverändert, wenn Daten nach i abgeschnitten
    werden (kein Lookahead)."""
    h4, d1 = make_h4(), make_d1("up")
    bars_full = {"H4": h4, "D1": d1}
    sigs_full = run_all(TrendPullback({}), bars_full)
    assert len(sigs_full) == 1
    i_star = int(h4.index.get_loc(sigs_full[0].time))

    bars_cut = {"H4": h4.iloc[: i_star + 1], "D1": d1}
    sigs_cut = run_all(TrendPullback({}), bars_cut)
    assert len(sigs_cut) == 1
    a, b = sigs_full[0], sigs_cut[0]
    assert (a.time, a.direction, a.stop_loss, a.take_profit) == \
           (b.time, b.direction, b.stop_loss, b.take_profit)


# --------------------------------------------------------------------------- #
# V1 — Vergleichsarm (DI-Cross D1 pur, SL 2×ATR, TP 2:1)
# --------------------------------------------------------------------------- #

def make_d1_di_cross() -> tuple[pd.DataFrame, pd.Timestamp]:
    """200 Abwärtstage, dann 40 starke Aufwärtstage -> +DI kreuzt über -DI.
    Rückgabe: (D1-DataFrame, Cross-Tag)."""
    n1, n2 = 200, 40
    c1 = 2000 - np.arange(n1) * 2.0
    c2 = c1[-1] + np.arange(1, n2 + 1) * 6.0
    close = np.concatenate([c1, c2])
    idx = pd.date_range("2023-01-02", periods=len(close), freq="D", tz="UTC")
    d1 = pd.DataFrame({"open": close - 1, "high": close + 4, "low": close - 4,
                       "close": close, "tick_volume": 1000.0}, index=idx)
    from strategies.base import adx
    ax = adx(d1, 14)
    cross = ((ax["plus_di"] > ax["minus_di"])
             & (ax["plus_di"].shift(1) <= ax["minus_di"].shift(1)))
    cross_days = d1.index[cross.fillna(False)]
    assert len(cross_days) == 1, "Testdaten sollen genau einen DI-Cross haben"
    return d1, cross_days[0]


def test_v1_di_cross_signal():
    d1, cross_day = make_d1_di_cross()
    h4_idx = pd.date_range(cross_day + pd.Timedelta(days=1), periods=6,
                           freq="4h", tz="UTC")
    px = float(d1.loc[cross_day, "close"])
    h4 = pd.DataFrame({"open": px, "high": px + 2, "low": px - 2,
                       "close": px, "tick_volume": 1000.0}, index=h4_idx)
    sigs = run_all(TrendPullback({"variant": "v1"}), {"H4": h4, "D1": d1})
    assert len(sigs) == 1          # genau 1 Signal pro Cross (Dedup)
    s = sigs[0]
    assert s.direction == +1
    assert s.meta["variant"] == "v1"
    assert s.meta["d1_cross_time"] == cross_day
    atr_d1 = s.meta["atr_d1"]
    assert s.stop_loss == pytest.approx(px - 2.0 * atr_d1)   # SL 2×ATR
    assert s.take_profit == pytest.approx(px + 4.0 * atr_d1)  # TP 2:1


# --------------------------------------------------------------------------- #
# Volume-Profile-Konfluenz-Layer (dim13 Variante b, A/B — Default AUS)
# --------------------------------------------------------------------------- #

def _h4_vp_cluster_at_entry() -> pd.DataFrame:
    """Volumen-Cluster am Pullback/Entry (~2011–2014): POC am Signal-Close.
    Preise unverändert -> Bias/Zone/Trigger/SL-Geometrie identisch."""
    h4 = make_h4()
    h4["tick_volume"] = (h4["high"] - h4["low"]) * 1000.0   # flache Basis-Dichte
    h4.iloc[42:46, h4.columns.get_loc("tick_volume")] = 2_000_000.0
    return h4


def _h4_lvn_at_entry() -> pd.DataFrame:
    """Hohe Volumen-Dichte überall, aber der Signal-Close (2014.0) wird nur
    von Niedrig-Volumen-Bars überdeckt -> Entry liegt in einer LVN (F6)."""
    h4 = make_h4()
    h4["tick_volume"] = (h4["high"] - h4["low"]) * 1e6
    entry = float(h4["close"].iloc[45])                     # 2014.0 (Trigger)
    covers = (h4["low"] <= entry) & (h4["high"] >= entry)
    h4.loc[covers, "tick_volume"] = 1.0
    return h4


def test_vp_filter_disabled_identical_and_poc_allows():
    """Default/explizit aus -> unverändert; enabled + POC am Entry -> Signal
    mit identischem SL/TP (Gate passiert; A/B-Nachweis in meta)."""
    h4, d1 = _h4_vp_cluster_at_entry(), make_d1("up")
    bars = {"H4": h4, "D1": d1}
    base = run_all(TrendPullback({}), bars)
    off = run_all(TrendPullback({"vp_filter": {"enabled": False}}), bars)
    on = run_all(TrendPullback({"vp_filter": {"enabled": True,
                                              "anchor": "rolling"}}), bars)
    assert len(base) == len(off) == len(on) == 1
    b, o = base[0], on[0]
    assert (b.time, b.direction, b.stop_loss, b.take_profit) == \
           (o.time, o.direction, o.stop_loss, o.take_profit)
    assert b.meta["vp_enabled"] is False
    assert o.meta["vp_enabled"] and o.meta["vp_allowed"]
    assert o.meta["vp_near_poc"] or o.meta["vp_near_hvn"]
    assert o.meta["vp_anchor"] == "rolling"


def test_vp_filter_blocks_entry_in_lvn():
    """F6: Signal-Close in LVN -> kein Signal; gleiche Daten ohne den Layer
    -> Signal (Block kommt nachweislich aus dem VP-Gate)."""
    h4, d1 = _h4_lvn_at_entry(), make_d1("up")
    bars = {"H4": h4, "D1": d1}
    assert len(run_all(TrendPullback({}), bars)) == 1       # Layer aus -> Signal
    # nur F6 aktiv (entry_requires_hvn aus) -> Block kommt aus der LVN
    blocked = run_all(TrendPullback({"vp_filter": {
        "enabled": True, "anchor": "rolling",
        "entry_requires_hvn": False, "block_lvn": True}}), bars)
    assert blocked == []


# --------------------------------------------------------------------------- #
# Smoke-Test: core-Module importierbar
# --------------------------------------------------------------------------- #

def test_core_imports_smoke():
    from core.indicators import (  # noqa: F401
        ema, sma, rsi, atr, adx, vwap_session, swing_points,
    )
    from core.time_engine import in_session, ny_time  # noqa: F401
