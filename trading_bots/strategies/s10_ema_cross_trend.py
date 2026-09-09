"""strategies/s10_ema_cross_trend.py — S10 EMA-Cross-Trendfolge.

Zweites einfaches Trendfolge-Archetyp: Doppel-EMA-Crossover (klassisch,
z.B. 20/55) als Richtungssignal, Entry Market naechste Bar, initialer
ATR-Stop, TP bei ``min_rr`` x Risiko-Distanz mit Move-to-Trail (s. S9-
Docstring: TP-Beruehrung loescht das TP und uebergibt an den Chandelier-
ATR-Trailing-Stop statt zu schliessen). Signal nur AM Kreuzungs-Bar (nicht
jede Bar neu), damit nicht staendig re-signalisiert wird, solange der Trend
haelt.

Bewusst so unabhaengig von S9 wie moeglich (andere Signalquelle: Trend-
Zustand statt Range-Ausbruch) fuer den breiten Multi-Symbol-Test.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr, ema as _ema


class S10EmaCrossTrend(Strategy):
    name = "s10_ema_cross_trend"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H4")
        self.required_timeframes = [self.primary_tf]

        self.ema_fast = int(p.get("ema_fast", 20))
        self.ema_slow = int(p.get("ema_slow", 55))
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 3.0))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(self.ema_slow * 3, self.atr_len) + 5

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        if i < self.ema_slow * 3:
            return None
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        ef = _ema(win["close"], self.ema_fast)
        es = _ema(win["close"], self.ema_slow)
        if ef.iloc[-1] != ef.iloc[-1] or es.iloc[-1] != es.iloc[-1]:  # NaN-Guard
            return None
        if len(ef) < 2 or ef.iloc[-2] != ef.iloc[-2] or es.iloc[-2] != es.iloc[-2]:
            return None

        now_up = ef.iloc[-1] > es.iloc[-1]
        prev_up = ef.iloc[-2] > es.iloc[-2]
        if now_up == prev_up:
            return None  # kein frischer Cross auf dieser Bar
        direction = 1 if now_up else -1

        atr_series = _atr(win, self.atr_len)
        a = float(atr_series.iloc[-1])
        if not (a > 0):
            return None

        c = float(win["close"].iloc[-1])
        sl = c - direction * self.sl_atr_mult * a
        tp = c + direction * self.min_rr * self.sl_atr_mult * a
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "ema_fast": float(ef.iloc[-1]), "ema_slow": float(es.iloc[-1]), "atr": a,
            },
            expires_bars=0,
        )

    def explain(self, bars: dict[str, pd.DataFrame], i: int) -> dict:
        """Rein lesende Diagnose derselben Gates wie ``on_bar`` — fuer
        menschenlesbares Live-Logging ("Traderbook": warum kein Einstieg?).
        Zustandslos wie on_bar selbst, mutiert nichts."""
        df = bars[self.primary_tf]
        info: dict = {
            "kind": "ema_cross",
            "time": df.index[i] if i < len(df) else None,
            "blocked_by": [], "ready": False,
            "ema_fast": None, "ema_slow": None, "trend": None, "gap_pct": None,
        }
        if i < self.ema_slow * 3:
            info["blocked_by"].append("warmup")
            return info

        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]
        ef = _ema(win["close"], self.ema_fast)
        es = _ema(win["close"], self.ema_slow)
        if (pd.isna(ef.iloc[-1]) or pd.isna(es.iloc[-1]) or len(ef) < 2
                or pd.isna(ef.iloc[-2]) or pd.isna(es.iloc[-2])):
            info["blocked_by"].append("warmup")
            return info

        now_up = ef.iloc[-1] > es.iloc[-1]
        prev_up = ef.iloc[-2] > es.iloc[-2]
        c = float(win["close"].iloc[-1])
        info["ema_fast"] = float(ef.iloc[-1])
        info["ema_slow"] = float(es.iloc[-1])
        info["trend"] = "up" if now_up else "down"
        info["gap_pct"] = abs(ef.iloc[-1] - es.iloc[-1]) / c * 100.0 if c else None

        if now_up == prev_up:
            info["blocked_by"].append("no_fresh_cross")
        else:
            info["ready"] = True
        return info
