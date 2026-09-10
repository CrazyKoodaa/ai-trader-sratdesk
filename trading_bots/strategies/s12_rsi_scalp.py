"""strategies/s12_rsi_scalp.py — S12 RSI-Extrem-Scalp (M5).

Klassischer Mean-Reversion-Scalp: kurzes RSI (Wilder) faellt unter
``rsi_oversold`` -> Long, steigt ueber ``rsi_overbought`` -> Short. Fixer
ATR-Stop/Take-Profit (kein Trailing — das Gegenteil von S9-S11: viele
kleine, schnelle Trades statt seltene grosse), plus Time-Exit als
Sicherheitsnetz (``time_exit_bars``), falls die Reversion ausbleibt.

Performance: ALLE Kennzahlen inkrementell (O(1)/O(rsi_len) pro Bar) wie in
S8 — bei M5-Symbolen mit oft >100k Bars waere eine Pandas-Rolling-Neu-
berechnung pro Bar in der WFA (viele Folds x Kombos) nicht mehr praktikabel.
"""
from __future__ import annotations

import logging
from collections import deque

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

from strategies.base import Signal, Strategy


class _WilderRSI:
    """Inkrementelle RSI nach Wilder (SMA-Seed von Gain/Loss, dann O(1))."""

    def __init__(self, n: int):
        self.n = n
        self._seed_gain: list[float] = []
        self._seed_loss: list[float] = []
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self._prev_close: float | None = None

    def update(self, c: float) -> float | None:
        if self._prev_close is None:
            self._prev_close = c
            return None
        delta = c - self._prev_close
        self._prev_close = c
        gain, loss = max(delta, 0.0), max(-delta, 0.0)
        if self._avg_gain is not None:
            self._avg_gain = (self._avg_gain * (self.n - 1) + gain) / self.n
            self._avg_loss = (self._avg_loss * (self.n - 1) + loss) / self.n
        else:
            self._seed_gain.append(gain)
            self._seed_loss.append(loss)
            if len(self._seed_gain) < self.n:
                return None
            self._avg_gain = sum(self._seed_gain) / self.n
            self._avg_loss = sum(self._seed_loss) / self.n
        if self._avg_loss == 0:
            return 100.0 if self._avg_gain > 0 else 50.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - 100.0 / (1.0 + rs)


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


class S12RsiScalp(Strategy):
    name = "s12_rsi_scalp"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "EURJPY")
        self.primary_tf = p.get("primary_tf", "M5")
        self.required_timeframes = [self.primary_tf]

        self.rsi_len = int(p.get("rsi_len", 5))
        self.rsi_oversold = float(p.get("rsi_oversold", 20.0))
        self.rsi_overbought = float(p.get("rsi_overbought", 80.0))
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 1.0))
        self.tp_atr_mult = float(p.get("tp_atr_mult", 1.2))
        self.time_exit_bars = int(p.get("time_exit_bars", 12))
        self.cooldown_bars = int(p.get("cooldown_bars", 3))
        self.risk_pct = float(p.get("risk_pct", 0.005))
        # Optional Break-Even/Trail (core/backtester.py meta["be_at_r"]/
        # ["trail_atr_mult"], Default 0.0 = aus, rueckwaertskompatibel):
        # laesst Gewinner laufen statt am fixen tp_atr_mult-Ziel zu kappen.
        self.be_at_r = float(p.get("be_at_r", 0.0))
        self.be_buffer_atr = float(p.get("be_buffer_atr", 0.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 0.0))

        self._rsi = _WilderRSI(self.rsi_len)
        self._atr = _WilderATR(self.atr_len)
        self._last_rsi: float | None = None
        self._cool_until: pd.Timestamp | None = None
        self._bar_minutes_val = self._TF_MINUTES[self.primary_tf]

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        row = df.iloc[i]
        ts = df.index[i]
        rsi_val = self._rsi.update(float(row["close"]))
        atr_val = self._atr.update(float(row["high"]), float(row["low"]), float(row["close"]))

        prev_rsi = self._last_rsi
        self._last_rsi = rsi_val
        if rsi_val is None or atr_val is None or not (atr_val > 0) or prev_rsi is None:
            return None

        # Cooldown ueber Zeit statt Bar-Index (kein direkter Bar-Zugriff im
        # Hook noetig) — kurzer Abstand nach jedem Signal, um nicht jede Bar
        # direkt neu zu feuern, solange RSI im Extrembereich verharrt.
        if self._cool_until is not None and ts < self._cool_until:
            return None

        direction = None
        if prev_rsi >= self.rsi_oversold > rsi_val:
            direction = 1
        elif prev_rsi <= self.rsi_overbought < rsi_val:
            direction = -1
        if direction is None:
            return None

        c = float(row["close"])
        sl = c - direction * self.sl_atr_mult * atr_val
        tp = c + direction * self.tp_atr_mult * atr_val
        self._cool_until = ts + pd.Timedelta(minutes=self._bar_minutes_val * self.cooldown_bars)
        meta = {"time_exit_bars": self.time_exit_bars, "rsi": rsi_val, "atr": atr_val}
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

    _TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
