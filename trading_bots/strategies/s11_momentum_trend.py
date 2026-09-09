"""strategies/s11_momentum_trend.py — S11 Time-Series-Momentum-Trendfolge.

Drittes, wieder unabhaengiges Trendfolge-Archetyp: klassisches Time-Series-
Momentum (Vorzeichen der ``lookback``-Bar-Rendite bestimmt die Richtung),
periodisch neu geprueft (alle ``rebalance_bars`` Bars, nicht jede Bar) statt
kontinuierlich — kostenschonender, passt zur "wenige, dafuer echte Trades"-
Philosophie. Gleicher Exit-Mechanismus wie S9/S10: initialer ATR-Stop, TP
bei ``min_rr`` x Risiko-Distanz mit Move-to-Trail (Chandelier-ATR-Trailing-
Stop uebernimmt bei TP-Beruehrung statt zu schliessen, s. S9-Docstring).
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S11MomentumTrend(Strategy):
    name = "s11_momentum_trend"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H4")
        self.required_timeframes = [self.primary_tf]

        self.lookback = int(p.get("lookback", 60))
        self.rebalance_bars = int(p.get("rebalance_bars", 5))
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 3.0))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(self.lookback, self.atr_len) + 5

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        if i < self.lookback + self.atr_len:
            return None
        if i % self.rebalance_bars != 0:
            return None
        df = bars[self.primary_tf]
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        c = float(win["close"].iloc[-1])
        c_prev = float(win["close"].iloc[-1 - self.lookback])
        if c == c_prev:
            return None
        direction = 1 if c > c_prev else -1

        atr_series = _atr(win, self.atr_len)
        a = float(atr_series.iloc[-1])
        if not (a > 0):
            return None

        sl = c - direction * self.sl_atr_mult * a
        tp = c + direction * self.min_rr * self.sl_atr_mult * a
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "momentum_ret": (c - c_prev) / c_prev, "atr": a,
            },
            expires_bars=0,
        )
