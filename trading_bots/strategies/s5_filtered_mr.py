"""strategies/s5_filtered_mr.py — S5 FilteredMR (SPEC §5/S5).

Symbole: XAUUSD + EURUSD, Timeframe H1.

Kontext-Gates (Pflicht, alle auf geschlossener Signal-Bar):
    ADX14 < adx_max (25)
    UND ATR14 <= 20er-Median(ATR14)
    UND EMA200(H1)-Bias: Long nur wenn Close > EMA200, Short nur wenn Close < EMA200
Signal:
    RSI14 kreuzt unter 30 -> Long / kreuzt ueber 70 -> Short
Entry: Market naechste Bar (entry_type="market", entry_price=None).
SL: 1.5 x ATR14 (ab Referenz = Schluss der Signal-Bar; Fill = Open naechste Bar).
TP: 2 x SL-Distanz (1:2 RR). Time-Stop: 48 H1-Bars (via meta, Risk-Engine).
Filter-Layer: News-Filter (Blackout + Tier1-Halt), Session 07-21 UTC (Flag),
    Regime-Filter allow_range als A/B-Arm, Volume-Profile-Konfluenz-Layer
    ``vp_filter`` (dim13 Variante b, Default AUS): F1 Entry am POC/HVN,
    F6 Block in LVN, optional SL hinter VA (``vp_structure_levels``, nur
    weiter weg, nie enger; TP mit gleichem RR umgerechnet).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

try:  # bevorzugt die kanonische Implementierung (SPEC §4.1)
    from strategies.base import Signal, Strategy
except Exception:  # Parallel-Entwicklung: Fallback exakt nach SPEC §4.1

    @dataclass
    class Signal:  # type: ignore[no-redef]
        time: pd.Timestamp
        symbol: str
        direction: int
        entry_type: str
        entry_price: float | None
        stop_loss: float
        take_profit: float | None
        risk_pct: float
        meta: dict
        expires_bars: int = 0

    class Strategy(ABC):  # type: ignore[no-redef]
        name: str
        params: dict

        def __init__(self, params: dict):
            self.params = params

        @abstractmethod
        def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> "Signal | None":
            ...

        def on_trade_closed(self, trade: dict) -> None:
            ...

try:  # Parallel-Entwicklung: core.indicators ggf. noch nicht vorhanden
    from core import indicators as _core_ind
except Exception:  # pragma: no cover
    _core_ind = None

from core.volume_profile import entry_gate, structural_stop, volume_profile


# ------------------------------------------------- Fallback-Indikatoren (Wilder)
# Fallbacks spiegeln core.indicators exakt (Single Source of Truth):
# Wilder-Glättung mit SMA-Seed, DM der ersten Bar = NaN.
def _wilder_smooth(values: pd.Series, n: int) -> pd.Series:
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
    if _core_ind is not None:
        return _core_ind.ema(s, n)
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _rsi(s: pd.Series, n: int) -> pd.Series:
    if _core_ind is not None:
        return _core_ind.rsi(s, n)
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
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    if _core_ind is not None:
        return _core_ind.atr(df, n)
    return _wilder_smooth(_true_range(df), n)


def _adx(df: pd.DataFrame, n: int) -> pd.Series:
    if _core_ind is not None:
        out = _core_ind.adx(df, n)
        return out["adx"] if isinstance(out, pd.DataFrame) else out
    high, low = df["high"], df["low"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    atr_w = _wilder_smooth(_true_range(df), n)
    plus_di = 100.0 * _wilder_smooth(plus_dm, n) / atr_w
    minus_di = 100.0 * _wilder_smooth(minus_dm, n) / atr_w
    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.replace(0.0, np.nan)
    return _wilder_smooth(dx, n)


DEFAULT_PARAMS: dict = {
    "symbol": "XAUUSD",
    "risk_pct": 0.005,
    # Gates
    "adx_len": 14,
    "adx_max": 25.0,
    "atr_len": 14,
    "atr_median_len": 20,
    "ema_len": 200,
    # Signal
    "rsi_len": 14,
    "rsi_oversold": 30.0,
    "rsi_overbought": 70.0,
    # Exits
    "atr_mult": 1.5,          # SL = atr_mult x ATR14
    "rr": 2.0,                # TP = rr x SL-Distanz
    "time_stop_bars": 48,     # H1-Bars
    # Filter-Layer
    "session_filter": True,
    "session_start_utc": 7,
    "session_end_utc": 21,
    "use_news_filter": True,
    "use_tier1_halt": True,
    "use_regime_filter": False,  # A/B-Arm: RegimeFilter.allow_range
    # Volume-Profile-Konfluenz-Layer (dim13, Variante b; A/B, Default AUS).
    # F1: Signal-Close muss innerhalb tolerance_atr x ATR von POC/HVN liegen.
    # F6: Entry blockiert, wenn Signal-Close in einer LVN liegt.
    # vp_structure_levels: SL hinter VA-Low/High (nur weiter weg, nie enger);
    #   TP wird mit gleichem RR auf die neue SL-Distanz umgerechnet.
    "vp_filter": {
        "enabled": False,
        "anchor": "swing",          # "swing" (Video-Variante) | "rolling"
        "lookback_bars": 120,       # WFO {60,120,240}; swing: Obergrenze
        "entry_requires_hvn": True,
        "block_lvn": True,
        "tolerance_atr": 0.25,
        "vp_structure_levels": False,
    },
}


class S5FilteredMR(Strategy):
    name = "s5_filtered_mr"
    required_timeframes = ["H1"]

    def __init__(self, params: dict | None = None):
        merged = {**DEFAULT_PARAMS, **(params or {})}
        merged["vp_filter"] = {**DEFAULT_PARAMS["vp_filter"],
                               **(params or {}).get("vp_filter", {})}
        super().__init__(merged)
        # Meta-Layer-Objekte (SPEC §6) koennen injiziert werden:
        self.news_filter = merged.get("news_filter_obj")
        self.regime = merged.get("regime_obj")
        # Arbeitsfenster: Indikatoren sind Wilder/EMA-Rekursionen — nach
        # 12 x laengster Periode ist der Seed-Einfluss < 1e-10 (numerisch
        # identisch), daher nur den Schwanz der Historie berechnen.
        p = merged
        self._window = max(
            12 * int(p["ema_len"]),
            12 * int(p["rsi_len"]),
            12 * int(p["adx_len"]),
            12 * int(p["atr_len"]) + int(p["atr_median_len"]),
            int(p["vp_filter"].get("lookback_bars", 0)) + 2,
        ) + 5
        self._cache_key: tuple[int, int] | None = None
        self._cache: dict[str, pd.Series] = {}

    # ---------------------------------------------------------- intern
    def _indicators(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        key = (len(df), df.index[-1], float(df["close"].iloc[-1]))
        if self._cache_key != key:
            p = self.params
            atr = _atr(df, int(p["atr_len"]))
            self._cache = {
                "ema": _ema(df["close"], int(p["ema_len"])),
                "rsi": _rsi(df["close"], int(p["rsi_len"])),
                "atr": atr,
                "atr_med": atr.rolling(int(p["atr_median_len"]),
                                       min_periods=int(p["atr_median_len"])).median(),
                "adx": _adx(df, int(p["adx_len"])),
            }
            self._cache_key = key
        return self._cache

    def _session_ok(self, ts: pd.Timestamp) -> bool:
        if not self.params["session_filter"]:
            return True
        start, end = int(self.params["session_start_utc"]), int(self.params["session_end_utc"])
        return start <= ts.hour < end

    def _news_blocked(self, ts: pd.Timestamp) -> bool:
        nf = self.news_filter
        if nf is None or not self.params["use_news_filter"]:
            return False
        if nf.is_blackout(ts, self.params["symbol"]):
            return True
        return bool(self.params["use_tier1_halt"] and nf.tier1_halt(ts))

    # ---------------------------------------------------------- API
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df_full = bars["H1"]
        i0 = max(0, i + 1 - self._window)
        df = df_full.iloc[i0: i + 1]
        j = len(df) - 1
        p = self.params
        warmup = max(int(p["ema_len"]), int(p["atr_len"]) + int(p["atr_median_len"]),
                     2 * int(p["adx_len"]), int(p["rsi_len"])) + 2
        if j < warmup or j < 1:
            return None

        ts = pd.Timestamp(df.index[j])
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        if not self._session_ok(ts):
            return None
        if self._news_blocked(ts):
            return None
        if p["use_regime_filter"] and self.regime is not None \
                and not self.regime.allow_range(i):
            return None

        ind = self._indicators(df)
        close = float(df["close"].iloc[j])
        adx_v = float(ind["adx"].iloc[j])
        atr_v = float(ind["atr"].iloc[j])
        atr_med = float(ind["atr_med"].iloc[j])
        ema_v = float(ind["ema"].iloc[j])
        rsi_prev = float(ind["rsi"].iloc[j - 1])
        rsi_now = float(ind["rsi"].iloc[j])
        if any(np.isnan(v) for v in (adx_v, atr_v, atr_med, ema_v, rsi_prev, rsi_now)):
            return None

        # Kontext-Gates (Pflicht)
        if not adx_v < float(p["adx_max"]):
            return None
        if not atr_v <= atr_med:
            return None

        os_, ob = float(p["rsi_oversold"]), float(p["rsi_overbought"])
        cross_down = rsi_prev >= os_ and rsi_now < os_    # kreuzt unter 30
        cross_up = rsi_prev <= ob and rsi_now > ob        # kreuzt ueber 70

        if cross_down and close > ema_v:                  # EMA200-Bias: Long nur darueber
            direction = +1
        elif cross_up and close < ema_v:                  # Short nur darunter
            direction = -1
        else:
            return None

        # Volume-Profile-Konfluenz-Layer (A/B, dim13 F1/F6) — Gate auf den
        # Signal-Close (Proxy fuer den Fill = Open der naechsten Bar).
        vp = p["vp_filter"]
        vp_meta: dict = {"vp_enabled": bool(vp.get("enabled", False))}
        vp_profile = None
        if vp.get("enabled", False):
            vp_profile = volume_profile(
                df, lookback_bars=int(vp["lookback_bars"]),
                anchor=str(vp["anchor"]))
            allowed, vp_meta = entry_gate(
                vp_profile, close, float(vp["tolerance_atr"]) * atr_v,
                entry_requires_hvn=bool(vp["entry_requires_hvn"]),
                block_lvn=bool(vp["block_lvn"]))
            vp_meta["vp_enabled"] = True
            if not allowed:
                return None

        sl_dist = float(p["atr_mult"]) * atr_v
        if vp_profile is not None and vp.get("vp_structure_levels", False):
            # SL hinter VA-Low/High statt reinem ATR-Stop — NUR wenn weiter
            # weg, nie enger. TP wird unten mit gleichem RR umgerechnet.
            base_sl = close - sl_dist if direction == +1 else close + sl_dist
            sl_struct = structural_stop(vp_profile, direction, base_sl,
                                        buffer=0.1 * atr_v)
            new_dist = abs(close - sl_struct)
            if new_dist > sl_dist:
                sl_dist = new_dist
                vp_meta["vp_sl_structure"] = True
        if direction == +1:
            sl = close - sl_dist
            tp = close + float(p["rr"]) * sl_dist
        else:
            sl = close + sl_dist
            tp = close - float(p["rr"]) * sl_dist

        return Signal(
            time=ts,
            symbol=str(p["symbol"]),
            direction=direction,
            entry_type="market",          # Entry = Open der naechsten Bar (Backtester)
            entry_price=None,
            stop_loss=sl,
            take_profit=tp,
            risk_pct=float(p["risk_pct"]),
            meta={
                "strategy": self.name,
                "ref_price": close,       # SL/TP-Anker; Fill = Open naechste Bar
                "sl_distance": sl_dist,
                "time_stop_bars": int(p["time_stop_bars"]),
                "adx": adx_v,
                "atr": atr_v,
                "atr_median": atr_med,
                "rsi": rsi_now,
                "ema200": ema_v,
                "session_utc": ts.hour,
                "news_filter": bool(p["use_news_filter"]),
                "regime_filter": bool(p["use_regime_filter"]),
                **vp_meta,            # VP-Layer-Info (A/B-Nachweis)
            },
        )
