"""Strategy-Basis gemäß SPEC §4.1.

Enthält:
- ``Signal``-Dataclass (exakt Felder laut SPEC §4.1)
- ``Strategy``-ABC mit ``on_bar`` (rein kausal) und ``on_trade_closed``
- Fallback-Implementierungen der Indikator-/Zeitfunktionen aus
  ``core.indicators`` / ``core.time_engine`` (SPEC §4.4/§4.5).

Die Strategien importieren die Indikator-/Zeitfunktionen gemäß SPEC aus
``core.indicators`` bzw. ``core.time_engine``. Solange die Core-Module von
einem parallelen Agenten gebaut werden (oder in isolierten Unit-Tests nicht
verfügbar sind), greifen die hier definierten Fallbacks mit identischen
Signaturen und äquivalenter (vektorisierter, kausaler) Semantik:
Wilder-Glättung für RSI/ATR/ADX, close[1]-Prinzip (nur geschlossene Bars).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# SPEC §4.1 — Signal
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    time: pd.Timestamp          # UTC, Signal-Bar (geschlossen)
    symbol: str
    direction: int              # +1 long, -1 short
    entry_type: str             # "market" | "limit"
    entry_price: float | None   # None bei market
    stop_loss: float
    take_profit: float | None   # None = nur Time/Structure-Exit
    risk_pct: float             # i.d.R. 0.005
    meta: dict = field(default_factory=dict)  # Filter-Infos, Regime, News-State
    expires_bars: int = 0       # für limit-Orders


# ---------------------------------------------------------------------------
# SPEC §4.1 — Strategy-ABC
# ---------------------------------------------------------------------------


class Strategy(ABC):
    """Basisklasse aller Strategien.

    ``on_bar`` ist REIN kausal: ``bars[tf]`` enthält ausschließlich
    geschlossene Bars bis inkl. Index ``i`` des primären (niedrigsten)
    Timeframes. Höhere Timeframes werden von der Engine zeit-aligniert
    geliefert; Strategien müssen zusätzlich sicherstellen, dass nur Bars
    verwendet werden, deren Close-Zeit <= Zeit der aktuellen Primär-Bar ist
    (höhere-TF-Bars werden daher zeitbasiert gefiltert).
    """

    name: str = "base"
    required_timeframes: list[str] = []

    def __init__(self, params: dict):
        self.params: dict = dict(params or {})

    @abstractmethod
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Optional[Signal]:
        """bars: {'M5': df, 'H1': df, ...} bis inkl. Index i (nur geschlossene
        Bars). Gibt Signal oder None. REIN kausal."""
        raise NotImplementedError

    def on_trade_closed(self, trade: dict) -> None:
        """Optionaler State-Hook; Default: kein State."""
        return None


# ---------------------------------------------------------------------------
# Indikator-Import gemäß SPEC §4.5 mit Fallback (solange core parallel entsteht)
# ---------------------------------------------------------------------------
# Die Fallbacks spiegeln die core-Implementierungen (Single Source of Truth)
# exakt: Wilder-Glättung mit SMA-Seed, min_periods=n bei EMA, Swing-Preise an
# der Kandidaten-Bar + *_confirmed_at-Spalten, VWAP-Reset je lokalem Datum.


def _wilder_smooth(values: pd.Series, n: int) -> pd.Series:
    """Wie core.indicators._wilder_smooth: Seed = SMA der ersten n gültigen
    Werte, danach out[t] = (out[t-1]*(n-1) + x[t]) / n."""
    n = int(n)
    v = values.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan, dtype="float64")
    valid = np.flatnonzero(~np.isnan(v))
    if len(valid) < n:
        return pd.Series(out, index=values.index, dtype="float64")
    seed_pos = int(valid[n - 1])
    prev = float(np.mean(v[valid[:n]]))
    out[seed_pos] = prev
    for t in range(seed_pos + 1, len(v)):
        if np.isnan(v[t]):
            continue
        prev = (prev * (n - 1) + v[t]) / n
        out[t] = prev
    return pd.Series(out, index=values.index, dtype="float64")


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _rsi(s: pd.Series, n: int) -> pd.Series:
    """RSI nach Wilder (Konventionen wie core.indicators.rsi)."""
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


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    """ATR nach Wilder (SMA-Seed, wie core.indicators.atr)."""
    return _wilder_smooth(_true_range(df), n)


def _adx(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """ADX/+DI/-DI nach Wilder → DataFrame[adx, plus_di, minus_di]
    (Semantik wie core.indicators.adx: DM der ersten Bar = NaN)."""
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    atr_s = _wilder_smooth(_true_range(df), n)
    sm_plus = _wilder_smooth(plus_dm, n)
    sm_minus = _wilder_smooth(minus_dm, n)
    plus_di = 100.0 * sm_plus / atr_s
    minus_di = 100.0 * sm_minus / atr_s
    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.replace(0.0, np.nan)
    adx_s = _wilder_smooth(dx, n)
    return pd.DataFrame(
        {"adx": adx_s, "plus_di": plus_di, "minus_di": minus_di}, index=df.index
    )


def _vwap_session(df: pd.DataFrame, session_tz: str) -> pd.Series:
    """Session-VWAP (tick_volume-gewichtet, Typical Price), Reset an jeder
    Datumsgrenze in Ortszeit der Zone ``session_tz`` (wie core.indicators).
    Für Slices, die erst ab Session-Start beginnen (so verwendet S2),
    identisch mit kumulativem Session-VWAP."""
    local_dates = df.index.tz_convert(session_tz).date
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["tick_volume"]
    cum_pv = pv.groupby(local_dates).cumsum()
    cum_v = df["tick_volume"].groupby(local_dates).cumsum()
    return cum_pv / cum_v.replace(0.0, np.nan)


def _swing_points(df: pd.DataFrame, left: int, right: int,
                  confirmed_lag: int = 0) -> pd.DataFrame:
    """Kausale Swing-High/Low-Serien (Format wie core.indicators.swing_points).

    Preise stehen an der *Kandidaten*-Bar; die Sichtbarkeit (Position
    ``p + right + confirmed_lag``) steht in den Spalten
    ``swing_high_confirmed_at`` / ``swing_low_confirmed_at`` (NaT = noch
    nicht bestätigt). Strikte Extrembedingung gegenüber allen Bars in
    [p-left, p+right] (ausgenommen p selbst).
    """
    n = len(df)
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    idx = df.index
    sh = np.full(n, np.nan)
    sl = np.full(n, np.nan)
    sh_conf = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns, UTC]")
    sl_conf = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns, UTC]")
    for p in range(left, n - right):
        confirm_at = p + right + confirmed_lag
        win_h = highs[p - left: p + right + 1]
        if highs[p] == win_h.max() and highs[p] > np.delete(win_h, left).max():
            sh[p] = highs[p]
            if confirm_at < n:
                sh_conf.iloc[p] = idx[confirm_at]
        win_l = lows[p - left: p + right + 1]
        if lows[p] == win_l.min() and lows[p] < np.delete(win_l, left).min():
            sl[p] = lows[p]
            if confirm_at < n:
                sl_conf.iloc[p] = idx[confirm_at]
    return pd.DataFrame(
        {
            "swing_high": sh,
            "swing_low": sl,
            "swing_high_confirmed_at": sh_conf,
            "swing_low_confirmed_at": sl_conf,
        },
        index=idx,
    )


def _in_session(ts_utc: pd.Timestamp, session: str, start_hhmm: str,
                end_hhmm: str) -> bool:
    """Wie core.time_engine.in_session: Minuten-Auflösung in Ortszeit,
    halboffen [start, end), über-Mitternacht-fähig, start == end = ganztägig."""
    local = pd.Timestamp(ts_utc).tz_convert(ZoneInfo(session))
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    start_min, end_min = sh * 60 + sm, eh * 60 + em
    minute_of_day = local.hour * 60 + local.minute
    if start_min == end_min:
        return True
    if start_min < end_min:
        return start_min <= minute_of_day < end_min
    return minute_of_day >= start_min or minute_of_day < end_min


def as_flag(value, default: bool = False) -> bool:
    """Normalisiert on/off-Config-Parameter robust.

    PyYAML (YAML 1.1) wandelt unquoted ``on``/``off`` in den Configs
    automatisch in Python-``bool`` um — ein Vergleich wie
    ``p.get("x", "off") == "on"`` ist dann IMMER False, auch wenn die YAML
    ``x: on`` sagt (echter Bug, gefunden in S4/S3: alle vier Filter-Flags
    liefen live faktisch immer aus). Diese Funktion behandelt echte
    Booleans direkt und Strings case-insensitiv gegen die uebliche
    on/off-Wortliste — robust gegen beide Ladewege (YAML-Datei vs. Tests,
    die Params direkt als Python-Dict mit String-Werten bauen)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("on", "true", "yes", "1")


def _ny_time(ts_utc: pd.Timestamp) -> pd.Timestamp:
    return ts_utc.tz_convert("America/New_York")


try:  # pragma: no cover — abhängig vom parallelen core-Agenten
    from core.indicators import (  # noqa: F401
        ema, sma, rsi, atr, adx, vwap_session, swing_points,
    )
    from core.time_engine import in_session, ny_time  # noqa: F401

    CORE_AVAILABLE = True
except Exception:  # core.indicators / core.time_engine noch nicht vorhanden
    ema = _ema
    sma = _sma
    rsi = _rsi
    atr = _atr
    adx = _adx
    vwap_session = _vwap_session
    swing_points = _swing_points
    in_session = _in_session
    ny_time = _ny_time
    CORE_AVAILABLE = False


__all__ = [
    "Signal",
    "Strategy",
    "CORE_AVAILABLE",
    "as_flag",
    "ema",
    "sma",
    "rsi",
    "atr",
    "adx",
    "vwap_session",
    "swing_points",
    "in_session",
    "ny_time",
]
