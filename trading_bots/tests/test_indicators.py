"""Tests für core/indicators.py + core/fixtures.py (OHLC-Konsistenz,
Anti-Repaint)."""

import numpy as np
import pandas as pd
import pytest

from core.fixtures import make_synthetic_ohlcv
from core.indicators import (
    adx,
    atr,
    donchian,
    ema,
    fib_zone,
    rolling_percentile,
    rsi,
    sma,
    swing_points,
    true_range,
    vwap_session,
)


def _df(high, low, close, open_=None, vol=None):
    n = len(close)
    idx = pd.date_range("2021-01-01", periods=n, freq="h", tz="UTC")
    if open_ is None:
        open_ = [close[0]] + list(close[:-1])
    if vol is None:
        vol = [100.0] * n
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "tick_volume": vol},
        index=idx, dtype="float64",
    )


# ---------------------------------------------------------------------------
# Fixtures: Daten-Kontrakt + OHLC-Konsistenz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["random", "trend_up", "trend_down", "range", "breakout"])
@pytest.mark.parametrize("timeframe", ["M1", "M5", "M15", "H1", "H4", "D1"])
def test_fixtures_ohlc_contract(kind, timeframe):
    df = make_synthetic_ohlcv(kind=kind, n=120, seed=7, timeframe=timeframe)
    assert list(df.columns) == ["open", "high", "low", "close", "tick_volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) in ("UTC", "datetime.timezone.utc")
    assert df.index.is_monotonic_increasing
    assert (df.dtypes == "float64").all()
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
    assert (df["high"] >= df["low"]).all()
    assert (df["tick_volume"] > 0).all()


def test_fixtures_deterministic_and_invalid():
    a = make_synthetic_ohlcv("trend_up", 100, 123, "H1")
    b = make_synthetic_ohlcv("trend_up", 100, 123, "H1")
    pd.testing.assert_frame_equal(a, b)
    with pytest.raises(ValueError):
        make_synthetic_ohlcv("nope", 100, 1, "H1")
    with pytest.raises(ValueError):
        make_synthetic_ohlcv("random", 100, 1, "M7")


# ---------------------------------------------------------------------------
# ema / sma
# ---------------------------------------------------------------------------

def test_sma_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert out.iloc[:2].isna().all()
    np.testing.assert_allclose(out.iloc[2:], [2.0, 3.0, 4.0])


def test_ema_known_values():
    # span=3, adjust=False -> alpha=0.5: 1, 1.5, 2.25, 3.125 (min_periods=3)
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = ema(s, 3)
    assert out.iloc[:2].isna().all()
    np.testing.assert_allclose(out.iloc[2:], [2.25, 3.125])


# ---------------------------------------------------------------------------
# RSI (Wilder)
# ---------------------------------------------------------------------------

def test_rsi_wilder_known_values():
    # 14 konstante Gewinne von 1, dann ein Verlust von 1
    close = list(range(1, 16)) + [14]
    s = pd.Series([float(x) for x in close])
    out = rsi(s, 14)
    assert out.iloc[:14].isna().all()
    assert out.iloc[14] == pytest.approx(100.0)  # avg_loss = 0
    # Wilder: avg_gain=(13*1+0)/14, avg_loss=(0*13+1)/14 -> rs=13
    assert out.iloc[15] == pytest.approx(100.0 * 13.0 / 14.0)


def test_rsi_bounds_and_flat():
    df = make_synthetic_ohlcv("random", 300, 3, "M15")
    out = rsi(df["close"], 14)
    assert ((out.dropna() >= 0) & (out.dropna() <= 100)).all()
    flat = pd.Series([5.0] * 30)
    assert rsi(flat, 14).iloc[-1] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# ATR / ADX (Wilder)
# ---------------------------------------------------------------------------

def test_true_range_and_atr_known_values():
    df = _df(high=[10, 11, 12, 13], low=[9, 9.5, 10, 11],
             close=[9.5, 10.5, 11.0, 12.0])
    tr = true_range(df)
    # TR0 = 10-9 = 1; TR1 = max(1.5, |11-9.5|, |9.5-9.5|)=1.5;
    # TR2 = max(2, 1.5, 0.5)=2; TR3 = max(2, 2, 0)=2
    np.testing.assert_allclose(tr, [1.0, 1.5, 2.0, 2.0])
    out = atr(df, 2)
    assert out.iloc[0:1].isna().all()
    assert out.iloc[1] == pytest.approx((1.0 + 1.5) / 2)          # SMA-Seed
    assert out.iloc[2] == pytest.approx((out.iloc[1] * 1 + 2.0) / 2)
    assert out.iloc[3] == pytest.approx((out.iloc[2] * 1 + 2.0) / 2)


def test_adx_structure_and_trend():
    n = 80
    close_up = [100.0 + i * 0.5 for i in range(n)]
    close_down = [100.0 - i * 0.5 for i in range(n)]
    df_up = _df(high=[c + 0.1 for c in close_up], low=[c - 0.1 for c in close_up], close=close_up)
    df_down = _df(high=[c + 0.1 for c in close_down], low=[c - 0.1 for c in close_down], close=close_down)
    for df, di_dom in ((df_up, "plus_di"), (df_down, "minus_di")):
        out = adx(df, 14)
        assert list(out.columns) == ["adx", "plus_di", "minus_di"]
        assert out["adx"].dropna().between(0, 100).all()
        assert out[di_dom].iloc[-1] > out[
            "minus_di" if di_dom == "plus_di" else "plus_di"
        ].iloc[-1]
        assert out["adx"].iloc[-1] > 25  # perfekter synthetischer Trend


# ---------------------------------------------------------------------------
# VWAP (Session-Reset in lokaler TZ)
# ---------------------------------------------------------------------------

def test_vwap_session_resets_utc_daily():
    idx = pd.date_range("2021-01-01", periods=4, freq="12h", tz="UTC")
    df = pd.DataFrame(
        {"open": [10, 20, 30, 40], "high": [10, 20, 30, 40],
         "low": [10, 20, 30, 40], "close": [10, 20, 30, 40],
         "tick_volume": [1.0, 3.0, 1.0, 1.0]},
        index=idx, dtype="float64",
    )
    out = vwap_session(df, "UTC")
    # Tag 1: (10*1 + 20*3)/4 = 17.5 an Bar 2; Tag 2: Reset -> 30, dann (30+40)/2
    np.testing.assert_allclose(out, [10.0, 17.5, 30.0, 35.0])


def test_vwap_session_tz_aware_reset():
    # 2021-01-01 23:00 UTC = 18:00 ET (Tag 1); 2021-01-02 02:00 UTC = 21:00 ET
    # (immer noch Tag 1!); 2021-01-02 05:00 UTC = 00:00 ET (Tag 2 -> Reset)
    idx = pd.DatetimeIndex(["2021-01-01 23:00", "2021-01-02 02:00", "2021-01-02 05:00"], tz="UTC")
    df = pd.DataFrame(
        {"open": [10, 20, 99], "high": [10, 20, 99], "low": [10, 20, 99],
         "close": [10, 20, 99], "tick_volume": [1.0, 1.0, 1.0]},
        index=idx, dtype="float64",
    )
    out = vwap_session(df, "America/New_York")
    np.testing.assert_allclose(out, [10.0, 15.0, 99.0])


# ---------------------------------------------------------------------------
# Donchian
# ---------------------------------------------------------------------------

def test_donchian_known_and_shift():
    df = _df(high=[1, 3, 2, 5, 4], low=[0, 1, 0.5, 2, 1],
             close=[1, 2, 1, 3, 2])
    out = donchian(df, 3)
    assert out.iloc[:2].isna().all().all()
    assert out["upper"].iloc[2] == 3.0
    assert out["upper"].iloc[3] == 5.0  # inkl. aktueller Bar
    assert out["lower"].iloc[2] == 0.0
    shifted = donchian(df, 3, shift=1)
    assert shifted["upper"].iloc[3] == 3.0  # max(high[0..2]), ohne Bar 3
    assert shifted["lower"].iloc[3] == 0.0


# ---------------------------------------------------------------------------
# Swing-Punkte: Bestätigungs-Lag + Kausalität
# ---------------------------------------------------------------------------

def _swing_df():
    # klarer Swing-High an i=4 (high 5), Swing-Low an i=4 kommt nicht vor
    high = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 3, 2]
    low = [h - 0.8 for h in high]
    close = [(h + l) / 2 for h, l in zip(high, low)]
    return _df(high=high, low=low, close=close)


def test_swing_points_detection_and_confirmation():
    df = _swing_df()
    sw = swing_points(df, left=2, right=2, confirmed_lag=1)
    assert sw["swing_high"].iloc[4] == 5.0
    # sichtbar erst an i + right + confirmed_lag = 4+2+1 = 7
    assert sw["swing_high_confirmed_at"].iloc[4] == df.index[7]
    assert sw["swing_high"].dropna().index.tolist() == [df.index[4], df.index[11]]
    # zweiter Peak (i=11): mit confirmed_lag=1 läge Bestätigung an Bar 14
    # (ausserhalb der Daten) -> NaT; ohne Lag an Bar 13 (= 11 + right)
    assert pd.isna(sw["swing_high_confirmed_at"].iloc[11])
    sw0 = swing_points(df, left=2, right=2)
    assert sw0["swing_high_confirmed_at"].iloc[11] == df.index[13]


def test_swing_points_confirmation_nat_beyond_data():
    df = _swing_df()
    sw = swing_points(df.iloc[:7], left=2, right=2)  # i=4 braucht Bar 6 zur Bestätigung
    assert sw["swing_high"].iloc[4] == 5.0
    assert sw["swing_high_confirmed_at"].iloc[4] == df.index[6]
    sw2 = swing_points(df.iloc[:6], left=2, right=2)  # Bestätigung läge bei 6 (außerhalb)
    assert pd.isna(sw2["swing_high_confirmed_at"].iloc[4])


def test_swing_points_low():
    high = [5, 4, 3, 2, 1, 2, 3, 4, 5]
    low = [h - 0.8 for h in high]
    df = _df(high=high, low=low, close=[(h + l) / 2 for h, l in zip(high, low)])
    sw = swing_points(df, left=2, right=2)
    assert sw["swing_low"].iloc[4] == pytest.approx(0.2)
    assert sw["swing_low_confirmed_at"].iloc[4] == df.index[6]


# ---------------------------------------------------------------------------
# Fib-Zone
# ---------------------------------------------------------------------------

def test_fib_zone_up_impulse():
    # Swing-Low (i=2) vor Swing-High (i=8) -> Impuls up, Zone vom High abwärts
    high = [2, 2, 2.2, 3, 4, 5, 6, 6.5, 7, 6.5, 6, 5.5, 5, 4.5]
    low = [1.5, 1.2, 1.0, 1.5, 2.5, 3.5, 4.5, 5.5, 6.0, 5.5, 5.0, 4.5, 4.0, 3.8]
    df = _df(high=high, low=low, close=[(h + l) / 2 for h, l in zip(high, low)])
    sw = swing_points(df, left=2, right=2)
    assert sw["swing_low"].iloc[2] == 1.0
    assert sw["swing_high"].iloc[8] == 7.0
    fz = fib_zone(df, lo=0.382, hi=0.618, left=2, right=2)
    # beide Swings bestätigt spätestens an Bar 10 (8+2)
    row = fz.iloc[10]
    rng = 7.0 - 1.0
    assert row["direction"] == 1.0
    assert row["fib_hi"] == pytest.approx(7.0 - 0.382 * rng)
    assert row["fib_lo"] == pytest.approx(7.0 - 0.618 * rng)
    assert fz.iloc[:4][["fib_lo", "fib_hi"]].isna().all().all()


def test_fib_zone_accepts_swing_frame():
    df = _swing_df()
    sw = swing_points(df, left=2, right=2)
    fz1 = fib_zone(sw)
    fz2 = fib_zone(df, left=2, right=2)
    pd.testing.assert_frame_equal(fz1, fz2)


# ---------------------------------------------------------------------------
# Rolling Percentile
# ---------------------------------------------------------------------------

def test_rolling_percentile_known():
    s = pd.Series([1.0, 3.0, 2.0, 2.0])
    out = rolling_percentile(s, 2)
    assert np.isnan(out.iloc[0])
    # [1,3]: 3 ist max -> 100; [3,2]: 1 von 2 <= 2 -> 50; [2,2]: beide <= 2 -> 100
    np.testing.assert_allclose(out.iloc[1:], [100.0, 50.0, 100.0])


# ---------------------------------------------------------------------------
# Anti-Repaint: Anhängen späterer Bars ändert frühere Werte nicht
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn", ["ema", "sma", "rsi", "atr", "donchian", "rolling_percentile"])
def test_anti_repaint_indicators(fn):
    df = make_synthetic_ohlcv("random", 300, 5, "H1")
    k = 200
    full = _apply(fn, df)
    part = _apply(fn, df.iloc[:k])
    if isinstance(full, pd.DataFrame):
        pd.testing.assert_frame_equal(full.iloc[:k], part)
    else:
        pd.testing.assert_series_equal(full.iloc[:k], part)


def _apply(fn, df):
    return {
        "ema": lambda: ema(df["close"], 20),
        "sma": lambda: sma(df["close"], 20),
        "rsi": lambda: rsi(df["close"], 14),
        "atr": lambda: atr(df, 14),
        "donchian": lambda: donchian(df, 20),
        "rolling_percentile": lambda: rolling_percentile(df["close"], 20),
    }[fn]()


def test_anti_repaint_adx_vwap_swings_fib():
    df = make_synthetic_ohlcv("trend_up", 300, 9, "H1")
    k = 200
    pd.testing.assert_frame_equal(adx(df, 14).iloc[:k], adx(df.iloc[:k], 14))
    pd.testing.assert_series_equal(
        vwap_session(df, "UTC").iloc[:k], vwap_session(df.iloc[:k], "UTC")
    )
    sw_full = swing_points(df, 3, 3)
    sw_part = swing_points(df.iloc[:k], 3, 3)
    # Preiswerte identisch; confirmed_at darf im Prefix höchstens NaT statt
    # Zeitpunkt haben (Bestätigungs-Bar fehlt), nie umgekehrt
    pd.testing.assert_series_equal(sw_full["swing_high"].iloc[:k], sw_part["swing_high"])
    pd.testing.assert_series_equal(sw_full["swing_low"].iloc[:k], sw_part["swing_low"])
    conf_full = sw_full["swing_high_confirmed_at"].iloc[:k]
    conf_part = sw_part["swing_high_confirmed_at"]
    both = conf_full.notna() & conf_part.notna()
    assert (conf_full[both] == conf_part[both]).all()
    cp = conf_part.dropna()
    assert (cp <= df.index[k - 1]).all()
    fz_full = fib_zone(df, left=3, right=3).iloc[:k]
    fz_part = fib_zone(df.iloc[:k], left=3, right=3)
    mask = fz_full["fib_lo"].notna() & fz_part["fib_lo"].notna()
    pd.testing.assert_frame_equal(fz_full[mask], fz_part[mask])
