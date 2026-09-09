"""core/indicators.py — technische Indikatoren (SPEC §4.5).

Alle Funktionen sind kausal (kein Lookahead): Der Wert an Bar i nutzt
ausschließlich Bars <= i. Ausnahme: ``swing_points`` detektiert einen Swing
an Bar i per Definition erst mit ``right`` Folge-Bars; die Sichtbarkeit wird
über die ``*_confirmed_at``-Spalten ausgedrückt (i + right + confirmed_lag).

Keine externen TA-Libs; numpy<2.0-kompatible API.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_OHLC = ("open", "high", "low", "close")


def _check_df(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_OHLC if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame fehlt Spalten: {missing}")


# ---------------------------------------------------------------------------
# Gleitende Durchschnitte
# ---------------------------------------------------------------------------

def ema(s: pd.Series, n: int) -> pd.Series:
    """Exponentieller gleitender Durchschnitt (span=n, adjust=False)."""
    return s.ewm(span=int(n), adjust=False, min_periods=int(n)).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    """Simple gleitender Durchschnitt."""
    return s.rolling(int(n)).mean()


# ---------------------------------------------------------------------------
# Wilder-Glättung (exakt: Seed = SMA der ersten n Werte, dann Rekursion)
# ---------------------------------------------------------------------------

def _wilder_smooth(values: pd.Series, n: int) -> pd.Series:
    """Wilder-Smoothing: out[t] = (out[t-1]*(n-1) + x[t]) / n.

    Der erste Wert ist der SMA der ersten n gültigen (nicht-NaN) Werte.
    NaN-Input erzeugt NaN-Output und lässt den Rekursionszustand unverändert.
    Schnellpfad ohne NaNs nach dem Seed via scipy.signal.lfilter (identische
    Rekursion: y[t] = alpha*x[t] + (1-alpha)*y[t-1], alpha = 1/n).
    """
    n = int(n)
    v = values.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan, dtype="float64")
    valid = np.flatnonzero(~np.isnan(v))
    if len(valid) < n:
        return pd.Series(out, index=values.index, dtype="float64")
    seed_pos = int(valid[n - 1])
    prev = float(np.mean(v[valid[:n]]))
    out[seed_pos] = prev
    tail = v[seed_pos + 1:]
    if len(tail) and not np.isnan(tail).any():
        from scipy.signal import lfilter  # lazy
        alpha = 1.0 / n
        out[seed_pos + 1:] = lfilter(
            [alpha], [1.0, -(1.0 - alpha)], tail,
            zi=[(1.0 - alpha) * prev])[0]
        return pd.Series(out, index=values.index, dtype="float64")
    for t in range(seed_pos + 1, len(v)):
        if np.isnan(v[t]):
            continue
        prev = (prev * (n - 1) + v[t]) / n
        out[t] = prev
    return pd.Series(out, index=values.index, dtype="float64")


# ---------------------------------------------------------------------------
# RSI / ATR / ADX (Wilder)
# ---------------------------------------------------------------------------

def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    """Relative Strength Index nach Wilder.

    Konventionen: avg_loss == 0 und avg_gain > 0 -> 100; avg_gain == 0 und
    avg_loss > 0 -> 0; beide 0 (flat) -> 50.
    """
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = _wilder_smooth(gain, n)
    avg_loss = _wilder_smooth(loss, n)
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(~((avg_loss == 0.0) & (avg_gain > 0.0)), 100.0)
    out = out.where(~((avg_gain == 0.0) & (avg_loss > 0.0)), 0.0)
    out = out.where(~((avg_gain == 0.0) & (avg_loss == 0.0) & avg_gain.notna()), 50.0)
    return out.astype("float64")


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range; erste Bar nutzt high-low (kein Vortages-Close)."""
    _check_df(df)
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.astype("float64")


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range nach Wilder."""
    return _wilder_smooth(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """ADX/DI nach Wilder. Liefert DataFrame[adx, plus_di, minus_di]."""
    _check_df(df)
    n = int(n)
    h, l = df["high"], df["low"]
    up = h.diff()
    down = -l.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    # DM der ersten Bar ist nicht definiert (kein Vorgänger) -> NaN statt 0
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan

    tr_s = _wilder_smooth(true_range(df), n)
    plus_s = _wilder_smooth(plus_dm, n)
    minus_s = _wilder_smooth(minus_dm, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * plus_s / tr_s
        minus_di = 100.0 * minus_s / tr_s
    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.replace(0.0, np.nan)
    adx_s = _wilder_smooth(dx, n)
    return pd.DataFrame(
        {"adx": adx_s, "plus_di": plus_di, "minus_di": minus_di},
        index=df.index,
        dtype="float64",
    )


# ---------------------------------------------------------------------------
# VWAP (Session-Reset)
# ---------------------------------------------------------------------------

def vwap_session(df: pd.DataFrame, session_tz: str = "UTC") -> pd.Series:
    """Session-VWAP (tick_volume-gewichtet, Typical Price (H+L+C)/3).

    Reset an jeder Datumsgrenze in der Ortszeit der Zone ``session_tz``
    (DST-sicher via zoneinfo). Index muss tz-aware UTC sein.
    """
    _check_df(df)
    if df.index.tz is None:
        raise ValueError("Index muss tz-aware UTC sein")
    local_dates = df.index.tz_convert(session_tz).date
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["tick_volume"]
    cum_pv = pv.groupby(local_dates).cumsum()
    cum_v = df["tick_volume"].groupby(local_dates).cumsum()
    return (cum_pv / cum_v.replace(0.0, np.nan)).astype("float64")


# ---------------------------------------------------------------------------
# Donchian-Kanal
# ---------------------------------------------------------------------------

def donchian(df: pd.DataFrame, n: int = 20, shift: int = 0) -> pd.DataFrame:
    """Donchian-Kanal: upper = max(high, n), lower = min(low, n).

    Inklusive aktueller Bar (kausal). Für Breakout-Logik typischerweise
    ``shift=1`` verwenden (Kanal aus den n Bars *vor* der aktuellen).
    """
    _check_df(df)
    upper = df["high"].rolling(int(n)).max()
    lower = df["low"].rolling(int(n)).min()
    if shift:
        upper = upper.shift(int(shift))
        lower = lower.shift(int(shift))
    return pd.DataFrame({"upper": upper, "lower": lower}, index=df.index, dtype="float64")


# ---------------------------------------------------------------------------
# Swing-Punkte (kausal sichtbar)
# ---------------------------------------------------------------------------

def swing_points(df: pd.DataFrame, left: int = 3, right: int = 3,
                 confirmed_lag: int = 0) -> pd.DataFrame:
    """Kausale Swing-High/Low-Erkennung.

    Ein Swing-High-Kandidat an Bar i hat ein strikt höheres High als alle
    Bars in [i-left, i+right] (ausgenommen i selbst); Swing-Low analog.
    Kausal sichtbar ist der Swing erst an Bar ``i + right + confirmed_lag``;
    dieser Zeitpunkt steht in ``swing_high_confirmed_at`` bzw.
    ``swing_low_confirmed_at`` (NaT = innerhalb der vorliegenden Daten noch
    nicht bestätigt). Regel: Nur Swings mit confirmed_at <= aktueller
    Bar-Zeitpunkt dürfen verwendet werden.

    Rückgabe: DataFrame[swing_high, swing_low, swing_high_confirmed_at,
    swing_low_confirmed_at] — Preise stehen an der *Kandidaten*-Bar.
    """
    _check_df(df)
    left, right, confirmed_lag = int(left), int(right), int(confirmed_lag)
    h, l = df["high"], df["low"]
    n = len(df)

    def _candidates(s: pd.Series, is_high: bool) -> pd.Series:
        left_ext = s.shift(1).rolling(left).max() if is_high else s.shift(1).rolling(left).min()
        right_ext = s.shift(-right).rolling(right).max() if is_high else s.shift(-right).rolling(right).min()
        both = pd.concat([left_ext, right_ext], axis=1).max(axis=1) if is_high \
            else pd.concat([left_ext, right_ext], axis=1).min(axis=1)
        # Unvollständige Fenster (Rand) -> kein Kandidat (statt skipna-max!)
        complete = left_ext.notna() & right_ext.notna()
        cond = (s > both) if is_high else (s < both)
        return cond & complete

    is_sh = _candidates(h, True).fillna(False)
    is_sl = _candidates(l, False).fillna(False)

    idx = df.index
    sh_conf = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns, UTC]")
    sl_conf = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns, UTC]")
    lag = right + confirmed_lag
    idx_ns = idx.to_numpy()
    for is_cand, conf in ((is_sh, sh_conf), (is_sl, sl_conf)):
        pos = np.flatnonzero(is_cand.to_numpy())
        pos = pos[pos + lag < n]
        if len(pos):
            conf.iloc[pos] = idx_ns[pos + lag]

    return pd.DataFrame(
        {
            "swing_high": h.where(is_sh),
            "swing_low": l.where(is_sl),
            "swing_high_confirmed_at": sh_conf,
            "swing_low_confirmed_at": sl_conf,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# Fibonacci-Zone
# ---------------------------------------------------------------------------

def fib_zone(df_or_swing: pd.DataFrame, lo: float = 0.382, hi: float = 0.618,
             left: int = 3, right: int = 3, confirmed_lag: int = 0) -> pd.DataFrame:
    """Retracement-Zone (lo–hi, default 38.2–61.8 %) des letzten Impuls-Swings.

    Akzeptiert ein OHLC-DataFrame (Swings werden intern via ``swing_points``
    berechnet) oder ein bereits berechnetes Swing-DataFrame (Spalten
    ``swing_high``/``swing_low`` + ``*_confirmed_at``).

    Pro Bar (kausal: nur bereits bestätigte Swings) wird die Zone aus dem
    jüngsten bestätigten Swing-High/Low-Paar bestimmt:
    - Impuls up (Swing-Low liegt zeitlich vor Swing-High): Zone von
      ``high - hi*range`` bis ``high - lo*range`` gemessen vom High abwärts.
    - Impuls down (Swing-High vor Swing-Low): symmetrisch vom Low aufwärts.

    Rückgabe: DataFrame[fib_lo, fib_hi, ref_swing_high, ref_swing_low,
    direction] (direction +1 = Impuls up, -1 = Impuls down), NaN solange
    kein vollständiges Paar bestätigt ist.
    """
    if {"swing_high", "swing_low"}.issubset(df_or_swing.columns):
        sw = df_or_swing
    else:
        sw = swing_points(df_or_swing, left=left, right=right, confirmed_lag=confirmed_lag)

    idx = sw.index
    n = len(idx)
    pos = {t: k for k, t in enumerate(idx)}

    # Bestätigungs-Bar (Positionsindex) -> Liste neu sichtbarer Kandidaten
    confirmed_at_bar: dict[int, list[tuple[int, str]]] = {}
    for i in range(n):
        ts_h = sw["swing_high_confirmed_at"].iloc[i]
        if not pd.isna(sw["swing_high"].iloc[i]) and not pd.isna(ts_h):
            confirmed_at_bar.setdefault(pos[ts_h], []).append((i, "high"))
        ts_l = sw["swing_low_confirmed_at"].iloc[i]
        if not pd.isna(sw["swing_low"].iloc[i]) and not pd.isna(ts_l):
            confirmed_at_bar.setdefault(pos[ts_l], []).append((i, "low"))

    fib_lo = np.full(n, np.nan)
    fib_hi = np.full(n, np.nan)
    ref_h = np.full(n, np.nan)
    ref_l = np.full(n, np.nan)
    direc = np.full(n, np.nan)

    last_sh_i = last_sl_i = None  # Kandidaten-Positionen der bestätigten Swings
    for j in range(n):
        for i, kind in confirmed_at_bar.get(j, ()):
            if kind == "high":
                last_sh_i = i
            else:
                last_sl_i = i
        if last_sh_i is None or last_sl_i is None:
            continue
        s_high = float(sw["swing_high"].iloc[last_sh_i])
        s_low = float(sw["swing_low"].iloc[last_sl_i])
        rng = s_high - s_low
        if rng <= 0:
            continue
        ref_h[j], ref_l[j] = s_high, s_low
        if last_sl_i < last_sh_i:  # Impuls up: Retracement vom High
            direc[j] = 1.0
            fib_hi[j] = s_high - lo * rng
            fib_lo[j] = s_high - hi * rng
        else:  # Impuls down: Retracement vom Low
            direc[j] = -1.0
            fib_lo[j] = s_low + lo * rng
            fib_hi[j] = s_low + hi * rng

    return pd.DataFrame(
        {
            "fib_lo": fib_lo,
            "fib_hi": fib_hi,
            "ref_swing_high": ref_h,
            "ref_swing_low": ref_l,
            "direction": direc,
        },
        index=idx,
        dtype="float64",
    )


# ---------------------------------------------------------------------------
# Rolling Percentile
# ---------------------------------------------------------------------------

def rolling_percentile(s: pd.Series, n: int) -> pd.Series:
    """Perzentil-Rang des aktuellen Werts innerhalb der letzten n Bars (0–100).

    Kausal: Fenster endet an (inklusive) der aktuellen Bar.
    """
    return s.rolling(int(n)).apply(
        lambda x: 100.0 * float((x <= x[-1]).sum()) / len(x), raw=True
    )
