"""S4 — LondonBreakout (USDJPY, H1). SPEC §5/S4 (verbindlich).

Regelwerk (rein kausal, nur geschlossene H1-Bars):
  Range: 00:00–06:59 UTC (H1). Entry: Market am H1-Close jenseits der Range
  im Fenster 07:00–16:59 UTC. 1 Trade/Tag (erste Seite). SL = Range-Gegenseite.
  TP = 1.5R–2R (Param). EOD-Flat 21:00 UTC (via Meta an Risk-Engine).
  Archetyp B (entry_mode=retest): Limit an Range-Grenze, SL dahinter.

Filter-Layer (einzeln schaltbar, SPEC §5/S4):
  atr_filter : ATR14(D1) > 20d-Median(ATR14)
  ema_filter : H4-EMA200-Alignment (Long nur ueber EMA200, Short nur darunter)
  range_band : range_min_pips <= Range <= range_max_adr x ADR20
  skip_monday: kein Trade montags (UTC)
  news_filter: Meta-Layer (engine-seitig), Default on

Nutzt core.indicators / core.time_engine per SPEC-Signatur, sofern vorhanden
(parallele Entwicklung); sonst lokale kausale Fallbacks.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# core-Imports mit Fallback (SPEC §4.1/§4.5 — parallele Entwicklung)
# ---------------------------------------------------------------------------
try:  # SPEC §4.1
    from strategies.base import Signal, Strategy, as_flag  # type: ignore
except ImportError:  # Fallback exakt nach SPEC §4.1

    def as_flag(value, default: bool = False) -> bool:  # type: ignore[no-redef]
        """Fallback-Spiegel von strategies.base.as_flag (s. dort fuer den
        YAML on/off-Bool-Bug, den diese Funktion behebt)."""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in ("on", "true", "yes", "1")


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

try:  # SPEC §4.5
    from core.indicators import atr as _core_atr, ema as _core_ema  # type: ignore
except ImportError:
    _core_atr = None
    _core_ema = None


def _wilder_atr(df: pd.DataFrame, n: int) -> pd.Series:
    """Fallback fuer core.indicators.atr — identische Semantik:
    Seed = SMA der ersten n TR-Werte, danach Wilder-Rekursion."""
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    v = tr.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan, dtype="float64")
    if len(v) >= n:
        prev = float(np.mean(v[:n]))
        out[n - 1] = prev
        for t in range(n, len(v)):
            prev = (prev * (n - 1) + v[t]) / n
            out[t] = prev
    return pd.Series(out, index=df.index, dtype="float64")


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    if _core_atr is not None:
        return _core_atr(df, n)
    return _wilder_atr(df, n)


def _ema(s: pd.Series, n: int) -> pd.Series:
    if _core_ema is not None:
        return _core_ema(s, n)
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _hhmm_to_hour(hhmm: str) -> int:
    return int(hhmm.split(":")[0])


# ---------------------------------------------------------------------------
# Strategie
# ---------------------------------------------------------------------------
class S4LondonBreakout(Strategy):
    name = "s4_london_breakout"
    required_timeframes = ["H1", "H4", "D1"]

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "USDJPY")
        self.risk_pct = float(p.get("risk_pct", 0.005))
        self.pip_size = float(p.get("pip_size", 0.01))  # USDJPY: 1 Pip = 0.01
        # Range / Fenster (UTC, SPEC §5/S4)
        self.range_start_h = _hhmm_to_hour(p.get("range_start", "00:00"))
        self.range_end_h = _hhmm_to_hour(p.get("range_end", "07:00"))  # exklusiv
        self.entry_start_h = _hhmm_to_hour(p.get("entry_start", "07:00"))
        self.entry_end_h = _hhmm_to_hour(p.get("entry_end", "17:00"))  # exklusiv
        self.require_full_range = bool(p.get("require_full_range", True))
        self.eod_flat_utc = p.get("eod_flat_utc", "21:00")
        # TP / Entry
        self.tp_r = float(p.get("tp_r", 2.0))
        self.entry_mode = p.get("entry_mode", "close")  # close | retest
        self.retest_sl_pips = float(p.get("retest_sl_pips", 10.0))
        self.retest_expiry_bars = int(p.get("retest_expiry_bars", 6))
        # Filter-Flags (einzeln schaltbar)
        self.atr_filter = as_flag(p.get("atr_filter"), default=False)
        self.atr_len = int(p.get("atr_len", 14))
        self.atr_med_len = int(p.get("atr_med_len", 20))
        self.ema_filter = as_flag(p.get("ema_filter"), default=False)
        self.ema_len = int(p.get("ema_len", 200))
        self.range_band = as_flag(p.get("range_band"), default=False)
        self.range_min_pips = float(p.get("range_min_pips", 20.0))
        self.range_max_adr = float(p.get("range_max_adr", 0.5))
        self.adr_len = int(p.get("adr_len", 20))
        self.skip_monday = as_flag(p.get("skip_monday"), default=False)
        # State
        self._day = None
        self._traded_today = False

    # -- Tages-Range ----------------------------------------------------------
    def _day_range(
        self, df: pd.DataFrame, i: int, day
    ) -> tuple[float, float] | None:
        """Range 00:00–06:59 UTC des aktuellen UTC-Tages (nur geschlossene Bars)."""
        idx = df.index[: i + 1]
        mask = (
            (idx.date == day)
            & (idx.hour >= self.range_start_h)
            & (idx.hour < self.range_end_h)
        )
        if not mask.any():
            return None
        n_expected = self.range_end_h - self.range_start_h
        if self.require_full_range and mask.sum() < n_expected:
            return None
        seg = df.iloc[: i + 1][mask]
        return float(seg["high"].max()), float(seg["low"].min())

    # -- Filter ----------------------------------------------------------------
    def _d1_history(self, bars: dict[str, pd.DataFrame], day) -> pd.DataFrame | None:
        """Nur vor heute abgeschlossene D1-Bars (kausal)."""
        d1 = bars.get("D1")
        if d1 is None or len(d1) == 0:
            return None
        return d1[d1.index.date < day]

    def _passes_atr_filter(self, bars, day) -> bool:
        d1 = self._d1_history(bars, day)
        if d1 is None or len(d1) < self.atr_len + self.atr_med_len:
            return False
        a = _atr(d1, self.atr_len).dropna()
        if len(a) < self.atr_med_len + 1:
            return False
        med = float(a.iloc[-(self.atr_med_len + 1) : -1].median())
        return float(a.iloc[-1]) > med

    def _passes_range_band(self, bars, day, range_size: float) -> bool:
        range_pips = range_size / self.pip_size
        if range_pips < self.range_min_pips:
            return False
        d1 = self._d1_history(bars, day)
        if d1 is None or len(d1) < self.adr_len:
            return False
        adr = float((d1["high"] - d1["low"]).iloc[-self.adr_len :].mean())
        if adr <= 0:
            return False
        return range_size <= self.range_max_adr * adr

    def _passes_ema_filter(
        self, bars, ts_close: pd.Timestamp, direction: int
    ) -> bool:
        h4 = bars.get("H4")
        if h4 is None:
            return False
        # nur H4-Bars, die zum aktuellen H1-Close geschlossen sind (kausal)
        h4 = h4[h4.index + pd.Timedelta(hours=4) <= ts_close]
        if len(h4) < self.ema_len:
            return False
        e = float(_ema(h4["close"], self.ema_len).iloc[-1])
        c = float(h4["close"].iloc[-1])
        return c > e if direction == 1 else c < e

    # -- Hauptlogik -------------------------------------------------------------
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars["H1"]
        ts = df.index[i]  # UTC, Bar-Open; Bar gerade geschlossen
        ts_close = ts + pd.Timedelta(hours=1)
        day = ts.date()
        if self._day != day:
            self._day = day
            self._traded_today = False

        # Entry-Fenster 07:00–16:59 UTC
        if not (self.entry_start_h <= ts.hour < self.entry_end_h):
            return None
        if self._traded_today:
            return None

        rng = self._day_range(df, i, day)
        if rng is None:
            return None
        range_high, range_low = rng
        range_size = range_high - range_low
        if range_size <= 0:
            return None

        c = float(df["close"].iloc[i])
        if c > range_high:
            direction = 1
        elif c < range_low:
            direction = -1
        else:
            return None

        # -- Filter-Stack (einzeln schaltbar) ------------------------------------
        if self.skip_monday and ts.dayofweek == 0:
            return None
        if self.atr_filter and not self._passes_atr_filter(bars, day):
            return None
        if self.range_band and not self._passes_range_band(bars, day, range_size):
            return None
        if self.ema_filter and not self._passes_ema_filter(bars, ts_close, direction):
            return None

        # -- Entry / SL / TP -------------------------------------------------------
        meta = {
            "range_high": range_high,
            "range_low": range_low,
            "range_pips": range_size / self.pip_size,
            "tp_r": self.tp_r,
            "entry_mode": self.entry_mode,
            "eod_flat_utc": self.eod_flat_utc,
            "filters": {
                "atr_filter": self.atr_filter,
                "ema_filter": self.ema_filter,
                "range_band": self.range_band,
                "skip_monday": self.skip_monday,
            },
        }
        self._traded_today = True  # 1 Trade/Tag (erste Seite)

        if self.entry_mode == "retest":
            # Archetyp B: Limit an Range-Grenze, SL dahinter
            if direction == 1:
                entry = range_high
                sl = entry - self.retest_sl_pips * self.pip_size
                tp = entry + self.tp_r * (entry - sl)
            else:
                entry = range_low
                sl = entry + self.retest_sl_pips * self.pip_size
                tp = entry - self.tp_r * (sl - entry)
            return Signal(
                time=ts,
                symbol=self.symbol,
                direction=direction,
                entry_type="limit",
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                risk_pct=self.risk_pct,
                meta=meta,
                expires_bars=self.retest_expiry_bars,
            )

        # entry_mode == "close": Market am H1-Close jenseits der Range
        if direction == 1:
            sl = range_low  # SL = Range-Gegenseite
            tp = c + self.tp_r * (c - sl)
        else:
            sl = range_high
            tp = c - self.tp_r * (sl - c)
        return Signal(
            time=ts,
            symbol=self.symbol,
            direction=direction,
            entry_type="market",
            entry_price=None,  # Engine: Open der naechsten Bar
            stop_loss=sl,
            take_profit=tp,
            risk_pct=self.risk_pct,
            meta=meta,
            expires_bars=0,
        )

    # -- Diagnose (Live-Logging: "warum kein Signal?") ---------------------------
    def explain(self, bars: dict[str, pd.DataFrame], i: int) -> dict:
        """Rein lesende Diagnose derselben Gates wie ``on_bar`` — fuer
        menschenlesbares Live-Logging ("Traderbook": warum kein Einstieg?).

        Mutiert KEINEN State (``_traded_today`` bleibt unberuehrt) und trifft
        keine Handelsentscheidung; sie spiegelt nur, an welchem Gate ``on_bar``
        gerade steht. Rueckgabe immer ein dict mit mind. ``blocked_by`` (Liste
        der gerissenen Gates, leer + ``ready=True`` wenn ``on_bar`` ein Signal
        liefern wuerde) und ``ready`` (bool).
        """
        df = bars["H1"]
        ts = df.index[i]
        ts_close = ts + pd.Timedelta(hours=1)
        day = ts.date()
        traded_today = self._traded_today if self._day == day else False

        info: dict = {
            "time": ts,
            "day": day,
            "in_entry_window": self.entry_start_h <= ts.hour < self.entry_end_h,
            "already_traded_today": traded_today,
            "range_high": None,
            "range_low": None,
            "range_pips": None,
            "breakout_direction": None,
            "blocked_by": [],
            "ready": False,
        }
        if not info["in_entry_window"]:
            info["blocked_by"].append("outside_entry_window")
            return info
        if traded_today:
            info["blocked_by"].append("already_traded_today")
            return info

        rng = self._day_range(df, i, day)
        if rng is None:
            info["blocked_by"].append("range_not_ready")
            return info
        range_high, range_low = rng
        range_size = range_high - range_low
        info["range_high"], info["range_low"] = range_high, range_low
        info["range_pips"] = range_size / self.pip_size if self.pip_size else None
        if range_size <= 0:
            info["blocked_by"].append("degenerate_range")
            return info

        c = float(df["close"].iloc[i])
        if c > range_high:
            direction = 1
        elif c < range_low:
            direction = -1
        else:
            info["blocked_by"].append("inside_range")
            return info
        info["breakout_direction"] = direction

        if self.skip_monday and ts.dayofweek == 0:
            info["blocked_by"].append("skip_monday")
        if self.atr_filter and not self._passes_atr_filter(bars, day):
            info["blocked_by"].append("atr_filter")
        if self.range_band and not self._passes_range_band(bars, day, range_size):
            info["blocked_by"].append("range_band")
        if self.ema_filter and not self._passes_ema_filter(bars, ts_close, direction):
            info["blocked_by"].append("ema_filter")

        info["ready"] = len(info["blocked_by"]) == 0
        return info
