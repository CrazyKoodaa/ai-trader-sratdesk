"""Unit-Tests für S9 — DonchianTrend (strategies/s9_donchian_trend.py).

Bisher ohne dedizierte Test-Datei, obwohl S9 seit dem H1-Pivot (docstring
der Strategie, reports/wfa_s9h_donchian_xauusd_h1 ff.) der aktuell
aussichtsreichste XAUUSD-Kandidat dieser Session ist (7/10 Gates in
reports/wfa_s9k_donchian_xauusd_h1_wide2). Deckt den Donchian-Breakout-
Kern, die kausale Kanalberechnung (kein Lookahead auf die aktuelle Bar)
und den optionalen ADX-Regime-Filter (``adx_min``) ab.

Synthetische OHLCV-Serien werden hier bewusst hand-konstruiert (wie
tests/test_s1.py), nicht über core/fixtures.py, weil der genaue Bar-Index
und die genaue Kanal-Range für die Lookahead- und ADX-Assertions exakt
kontrollierbar sein müssen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.indicators import adx as _adx
from strategies.base import Signal, Strategy
from strategies.s9_donchian_trend import S9DonchianTrend

DON_LEN = 20
ATR_LEN = 14
WARMUP = DON_LEN + ATR_LEN  # on_bar()'s `i < don_len + atr_len` guard


def _flat_range_df(n: int, level: float = 100.0, wobble: float = 0.3,
                    seed: int = 7) -> pd.DataFrame:
    """n H1-Bars in enger Range um ``level`` (kein Trend, kleine OHLC-
    Bandbreite) -- Basis für einen kontrollierten Breakout am Ende."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=n, freq="1h", tz="UTC")
    close = level + rng.normal(0.0, wobble, n)
    open_ = np.empty(n)
    open_[0] = level
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) + wobble
    low = np.minimum(open_, close) - wobble
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": 1000.0}, index=idx)


def _append_bar(df: pd.DataFrame, o: float, h: float, l: float, c: float) -> pd.DataFrame:
    """Haengt eine einzelne Bar (naechste Stunde) an ``df`` an."""
    next_ts = df.index[-1] + pd.Timedelta(hours=1)
    row = pd.DataFrame({"open": [o], "high": [h], "low": [l], "close": [c],
                        "tick_volume": [1000.0]}, index=[next_ts])
    return pd.concat([df, row])


def make_long_breakout(don_len: int = DON_LEN) -> pd.DataFrame:
    """Range-Bars, dann eine Bar, die klar ueber den Kanal (letzte
    don_len Bars VOR der aktuellen) schliesst."""
    df = _flat_range_df(don_len + ATR_LEN + 5)
    chan_upper = float(df["high"].iloc[-don_len:].max())
    return _append_bar(df, o=chan_upper - 0.1, h=chan_upper + 3.0,
                       l=chan_upper - 0.2, c=chan_upper + 2.0)


def make_short_breakout() -> pd.DataFrame:
    df = _flat_range_df(WARMUP + 5)
    chan_lower = float(df["low"].iloc[-DON_LEN:].min())
    return _append_bar(df, o=chan_lower + 0.1, h=chan_lower + 0.2,
                       l=chan_lower - 3.0, c=chan_lower - 2.0)


def base_params(**overrides) -> dict:
    p = {"symbol": "XAUUSD", "primary_tf": "H1", "don_len": DON_LEN,
         "atr_len": ATR_LEN, "sl_atr_mult": 2.0, "trail_atr_mult": 3.0,
         "min_rr": 2.0, "risk_pct": 0.005}
    p.update(overrides)
    return p


# --------------------------------------------------------------------------- #
# Base-Kontrakt (SPEC §4.1)
# --------------------------------------------------------------------------- #

def test_base_contract():
    strat = S9DonchianTrend(base_params())
    assert isinstance(strat, Strategy)
    assert strat.name == "s9_donchian_trend"
    assert strat.required_timeframes == ["H1"]


def test_backward_compatible_defaults():
    """adx_min fehlt in params -> 0.0 (aus), primary_tf fehlt -> H4
    (urspruenglicher S9-Default, s. configs/s9_donchian_trend.yaml)."""
    strat = S9DonchianTrend({})
    assert strat.adx_min == 0.0
    assert strat.primary_tf == "H4"


# --------------------------------------------------------------------------- #
# Warmup
# --------------------------------------------------------------------------- #

def test_no_signal_before_warmup():
    df = _flat_range_df(WARMUP)  # letzter gueltiger Index waere WARMUP-1
    strat = S9DonchianTrend(base_params())
    bars = {"H1": df}
    for i in range(len(df)):
        assert strat.on_bar(bars, i) is None


# --------------------------------------------------------------------------- #
# Breakout-Signal (Long/Short) + kausale Kanalberechnung
# --------------------------------------------------------------------------- #

def test_long_breakout_signal():
    df = make_long_breakout()
    strat = S9DonchianTrend(base_params())
    bars = {"H1": df}
    i = len(df) - 1
    sig = strat.on_bar(bars, i)
    assert isinstance(sig, Signal)
    assert sig.direction == 1
    assert sig.entry_type == "market"
    assert sig.entry_price is None
    assert sig.symbol == "XAUUSD"
    assert sig.expires_bars == 0
    assert sig.risk_pct == pytest.approx(0.005)
    assert sig.meta["tp_converts_to_trail"] is True
    assert sig.meta["trail_atr_mult"] == pytest.approx(3.0)
    a = sig.meta["atr"]
    c = float(df["close"].iloc[-1])
    assert sig.stop_loss == pytest.approx(c - 2.0 * a)
    assert sig.take_profit == pytest.approx(c + 2.0 * 2.0 * a)  # min_rr * sl_atr_mult
    # Kanal-Grenzen muessen exakt aus den DON_LEN Bars VOR der aktuellen
    # stammen (Ausschluss der aktuellen Bar -- Lookahead-Check unten
    # verifiziert das Verhalten, hier nur die gemeldeten Werte):
    expected_upper = float(df["high"].iloc[-(DON_LEN + 1):-1].max())
    expected_lower = float(df["low"].iloc[-(DON_LEN + 1):-1].min())
    assert sig.meta["don_upper"] == pytest.approx(expected_upper)
    assert sig.meta["don_lower"] == pytest.approx(expected_lower)


def test_short_breakout_signal():
    df = make_short_breakout()
    strat = S9DonchianTrend(base_params())
    sig = strat.on_bar({"H1": df}, len(df) - 1)
    assert isinstance(sig, Signal)
    assert sig.direction == -1
    a = sig.meta["atr"]
    c = float(df["close"].iloc[-1])
    assert sig.stop_loss == pytest.approx(c + 2.0 * a)
    assert sig.take_profit == pytest.approx(c - 2.0 * 2.0 * a)


def test_no_signal_inside_channel():
    """Close bleibt innerhalb des Kanals -> kein Trade."""
    df = _flat_range_df(WARMUP + 5)
    strat = S9DonchianTrend(base_params())
    bars = {"H1": df}
    for i in range(WARMUP, len(df)):
        assert strat.on_bar(bars, i) is None


def test_current_bar_excluded_from_channel_no_lookahead():
    """Kernanforderung SPEC §1 ('close[1]-Prinzip', kein Lookahead):
    ``upper``/``lower`` duerfen NICHT die aktuelle Bar einschliessen.
    Konstruktion: die aktuelle Bar hat selbst einen sehr hohen High
    (wuerde den Kanal massiv anheben, wenn sie mitgezaehlt wuerde), aber
    ihr Close liegt nur knapp ueber dem WAHREN (Vorbar-)Kanal-High. Ein
    Lookahead-Bug (Kanal inkl. aktueller Bar) wuerde ``upper`` auf den
    eigenen Wick dieser Bar hochziehen -> close > upper waere dann FALSCH
    und kein Signal entstuende. Korrektes (kausales) Verhalten: Signal
    feuert trotzdem, weil der Kanal ausschliesslich aus den DON_LEN Bars
    VOR der aktuellen Bar gebildet wird."""
    df = _flat_range_df(WARMUP + 5)
    true_upper = float(df["high"].iloc[-DON_LEN:].max())
    # Aktuelle Bar: riesiger High-Wick (weit ueber true_upper), aber Close
    # nur knapp darueber -- ein Kanal INKLUSIVE dieser Bar wuerde upper
    # auf den Wick heben und close waere darunter.
    df = _append_bar(df, o=true_upper - 0.1, h=true_upper + 50.0,
                     l=true_upper - 0.2, c=true_upper + 0.5)
    strat = S9DonchianTrend(base_params())
    sig = strat.on_bar({"H1": df}, len(df) - 1)
    assert sig is not None, "Kanal darf die aktuelle Bar nicht einschliessen (Lookahead)"
    assert sig.direction == 1
    assert sig.meta["don_upper"] == pytest.approx(true_upper)


# --------------------------------------------------------------------------- #
# ADX-Regime-Filter (adx_min)
# --------------------------------------------------------------------------- #

def test_adx_filter_off_by_default_fires_regardless_of_regime():
    df = make_long_breakout()
    strat = S9DonchianTrend(base_params(adx_min=0.0))
    assert strat.on_bar({"H1": df}, len(df) - 1) is not None


# ADX(Wilder) braucht wegen der doppelten Glaettung deutlich mehr als
# atr_len Bars, um NICHT NaN zu sein (Faustregel ~2x). don_len=20 (Default
# oben) ergibt ein window von nur 25 Bars -- zu knapp fuer ein stabiles
# ADX(14). Die ADX-spezifischen Tests nutzen daher einen groesseren
# don_len (wie es auch alle H1-Configs ab s9h tun, s. configs/s9*_h1*.yaml:
# don_len >= 80), damit adx_v hier tatsaechlich eine Zahl statt NaN ist.
ADX_DON_LEN = 40


def _adx_window(df: pd.DataFrame, don_len: int) -> pd.DataFrame:
    """Repliziert Strategy._window/lo-Berechnung fuer die letzte Bar von df."""
    window = max(don_len, ATR_LEN) + 5
    i = len(df) - 1
    lo = max(0, i + 1 - window)
    return df.iloc[lo : i + 1]


def test_adx_filter_blocks_when_below_threshold():
    df = make_long_breakout(don_len=ADX_DON_LEN)
    win = _adx_window(df, ADX_DON_LEN)
    actual_adx = float(_adx(win, ATR_LEN)["adx"].iloc[-1])
    assert np.isfinite(actual_adx), "Test-Fixture muss ein stabiles (nicht-NaN) ADX liefern"
    strat = S9DonchianTrend(base_params(don_len=ADX_DON_LEN, adx_min=actual_adx + 10.0))
    assert strat.on_bar({"H1": df}, len(df) - 1) is None


def test_adx_filter_allows_when_above_threshold():
    df = make_long_breakout(don_len=ADX_DON_LEN)
    win = _adx_window(df, ADX_DON_LEN)
    actual_adx = float(_adx(win, ATR_LEN)["adx"].iloc[-1])
    assert np.isfinite(actual_adx)
    threshold = max(0.1, actual_adx - 5.0)
    strat = S9DonchianTrend(base_params(don_len=ADX_DON_LEN, adx_min=threshold))
    sig = strat.on_bar({"H1": df}, len(df) - 1)
    assert sig is not None
    assert sig.direction == 1


# --------------------------------------------------------------------------- #
# Session-Filter (session_filter) -- London/NY-Fenster, kausal via
# core/time_engine.in_session (s. Docstring der Strategie)
# --------------------------------------------------------------------------- #

def _shift_to_hour(df: pd.DataFrame, target_hour: int) -> pd.DataFrame:
    """Verschiebt den gesamten Index um volle Stunden, sodass die LETZTE Bar
    exakt auf ``target_hour`` UTC faellt (OHLC/Deltas bleiben unveraendert --
    nur die absolute Uhrzeit der Serie wird gedreht)."""
    last_hour = df.index[-1].hour
    delta_hours = (target_hour - last_hour) % 24
    return df.set_axis(df.index + pd.Timedelta(hours=int(delta_hours)))


def test_session_filter_off_by_default():
    strat = S9DonchianTrend(base_params())
    assert strat.session_filter is False


def test_session_filter_off_fires_regardless_of_hour():
    df = _shift_to_hour(make_long_breakout(), 2)  # 02:00 UTC -- ausserhalb 07:00-21:00
    strat = S9DonchianTrend(base_params())  # session_filter default aus
    assert strat.on_bar({"H1": df}, len(df) - 1) is not None


def test_session_filter_on_blocks_outside_window():
    df = _shift_to_hour(make_long_breakout(), 2)  # 02:00 UTC (Asian-Session)
    strat = S9DonchianTrend(base_params(session_filter="on"))
    assert strat.on_bar({"H1": df}, len(df) - 1) is None


def test_session_filter_on_allows_inside_window():
    df = _shift_to_hour(make_long_breakout(), 14)  # 14:00 UTC (London/NY-Overlap)
    strat = S9DonchianTrend(base_params(session_filter="on"))
    sig = strat.on_bar({"H1": df}, len(df) - 1)
    assert sig is not None
    assert sig.direction == 1


def test_session_filter_custom_window():
    df = _shift_to_hour(make_long_breakout(), 9)  # 09:00 UTC
    strat = S9DonchianTrend(base_params(
        session_filter="on", session_start_utc="10:00", session_end_utc="18:00"))
    assert strat.on_bar({"H1": df}, len(df) - 1) is None  # 09:00 < 10:00 Start


# --------------------------------------------------------------------------- #
# Determinismus (SPEC §1)
# --------------------------------------------------------------------------- #

def test_deterministic_rerun():
    df = make_long_breakout(don_len=ADX_DON_LEN)
    params = base_params(don_len=ADX_DON_LEN, adx_min=0.0)
    s1 = S9DonchianTrend(params).on_bar({"H1": df}, len(df) - 1)
    s2 = S9DonchianTrend(params).on_bar({"H1": df}, len(df) - 1)
    assert s1 is not None and s2 is not None
    assert s1.stop_loss == s2.stop_loss
    assert s1.take_profit == s2.take_profit
    assert s1.meta["atr"] == s2.meta["atr"]
