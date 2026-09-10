"""strategies/s13_vwap_fade_scalp.py — S13 VWAP-Abweichungs-Fade-Scalp (M5).

Zweiter, unabhaengiger Scalp-Archetyp: Preis weicht mehr als
``dev_atr_mult`` x ATR vom taeglich verankerten VWAP ab -> Fade zurueck
Richtung VWAP. Fixer ATR-Stop/Take-Profit + Time-Exit, kein Trailing —
wie S12 auf viele kleine, schnelle Trades ausgelegt statt seltene grosse.

VWAP faellt bei fehlendem Handelsvolumen automatisch auf TWAP zurueck
(tick_volume=0 bei allen M5-Reihen in diesem Projekt, s. S8-Docstring) —
gleiche, bereits dokumentierte Abweichung vom Original-Konzept.

Performance: inkrementeller Zustand (O(1) pro Bar) wie S8/S12 — kein
Pandas-Rolling ueber wachsendes Fenster bei M5-Bar-Zahlen.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

from strategies.base import Signal, Strategy

_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


class _WilderATR:
    def __init__(self, n: int):
        self.n = n
        self._seed_buf: list[float] = []
        self._prev_close: float | None = None
        self.value: float | None = None

    def update(self, h: float, l: float, c: float) -> float | None:
        tr = (h - l) if self._prev_close is None else max(
            h - l, abs(h - self._prev_close), abs(l - self._prev_close)
        )
        self._prev_close = c
        if self.value is not None:
            self.value = (self.value * (self.n - 1) + tr) / self.n
            return self.value
        self._seed_buf.append(tr)
        if len(self._seed_buf) >= self.n:
            self.value = sum(self._seed_buf) / len(self._seed_buf)
        return self.value


class S13VwapFadeScalp(Strategy):
    name = "s13_vwap_fade_scalp"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "EURJPY")
        self.primary_tf = p.get("primary_tf", "M5")
        self.required_timeframes = [self.primary_tf]

        self.dev_atr_mult = float(p.get("dev_atr_mult", 1.5))
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 1.0))
        self.tp_atr_mult = float(p.get("tp_atr_mult", 1.0))
        self.time_exit_bars = int(p.get("time_exit_bars", 12))
        self.cooldown_bars = int(p.get("cooldown_bars", 3))
        self.sess_start = p.get("sess_start", "07:00")
        self.sess_end = p.get("sess_end", "20:00")
        self.risk_pct = float(p.get("risk_pct", 0.005))
        # Optional Break-Even/Trail (core/backtester.py meta["be_at_r"]/
        # ["trail_atr_mult"], Default 0.0 = aus, rueckwaertskompatibel):
        # laesst Gewinner laufen statt am fixen tp_atr_mult-Ziel zu kappen.
        self.be_at_r = float(p.get("be_at_r", 0.0))
        self.be_buffer_atr = float(p.get("be_buffer_atr", 0.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 0.0))

        self._atr = _WilderATR(self.atr_len)
        self._day = None
        self._cum_pv = 0.0
        self._cum_v = 0.0
        self._cool_until: pd.Timestamp | None = None
        self._bar_minutes = _TF_MINUTES[self.primary_tf]

    def _in_sess(self, ts: pd.Timestamp) -> bool:
        sh, sm = map(int, self.sess_start.split(":"))
        eh, em = map(int, self.sess_end.split(":"))
        mod = ts.hour * 60 + ts.minute
        return sh * 60 + sm <= mod < eh * 60 + em

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        row = df.iloc[i]
        ts = df.index[i]
        h, l, c, vol = float(row["high"]), float(row["low"]), float(row["close"]), float(row["tick_volume"])

        day = ts.date()
        if day != self._day:
            self._day = day
            self._cum_pv = 0.0
            self._cum_v = 0.0
        w = vol if vol > 0 else 1.0  # TWAP-Fallback ohne Volumen (s. Docstring)
        tp_price = (h + l + c) / 3.0
        self._cum_pv += tp_price * w
        self._cum_v += w
        vwap = self._cum_pv / self._cum_v if self._cum_v > 0 else None

        atr_val = self._atr.update(h, l, c)

        if vwap is None or atr_val is None or not (atr_val > 0):
            return None
        if not self._in_sess(ts):
            return None
        if self._cool_until is not None and ts < self._cool_until:
            return None

        dev = (c - vwap) / atr_val
        if dev <= -self.dev_atr_mult:
            direction = 1
        elif dev >= self.dev_atr_mult:
            direction = -1
        else:
            return None

        sl = c - direction * self.sl_atr_mult * atr_val
        tp = c + direction * self.tp_atr_mult * atr_val
        self._cool_until = ts + pd.Timedelta(minutes=self._bar_minutes * self.cooldown_bars)
        meta = {"time_exit_bars": self.time_exit_bars, "vwap": vwap, "dev_atr": dev, "atr": atr_val}
        if self.be_at_r > 0:
            meta["be_at_r"] = self.be_at_r
            meta["be_buffer"] = self.be_buffer_atr * atr_val
        if self.trail_atr_mult > 0:
            meta["trail_atr_mult"] = self.trail_atr_mult
            meta["trail_atr_len"] = self.atr_len
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta=meta,
            expires_bars=0,
        )
