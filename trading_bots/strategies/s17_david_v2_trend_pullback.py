"""strategies/s17_david_v2_trend_pullback.py — Portierung von "David V2"
(externer Live-Bot, /home/crazyneo/Desktop/tagebuch/David-V2-Ben/) in dieses
Projekts Strategy/Signal-Interface, zur Validierung durch core/validation.py
(WFA + Gates, SPEC §7) — auf Nutzerwunsch ("unterzieh das mal durch den WFA").

Original-Logik (strategies.py/config.py im David-Ordner), 1:1 uebernommen:
  - Trend: Close vs. EMA(trend_len), Neutralzone = trend_buffer_atr * ATR
  - Pullback + Signal: RSI(rsi_len) kreuzt von unten ueber rsi_oversold
    (LONG) bzw. von oben unter (100-rsi_oversold) (SHORT)
  - Filter 1 (ADX): ADX(adx_len) >= adx_min, sonst kein Signal
  - Filter 2 (ATR-Vol-Perzentil): aktueller ATR muss im oberen Bereich der
    letzten atr_vol_lookback Bars liegen (Min/Max-Normalisierung wie im
    Original, monoton aequivalent zu einem echten Perzentil)
  - Filter 3 (MTF): hoeherer Timeframe (H4 fuer H1-Maerkte, D1 fuer XAUUSD)
    muss NICHT gegen die Signalrichtung laufen
  - Stop = ATR(atr_len) * atr_stop_mult, TP = Stop * rr_ratio

BEWUSST NICHT portiert (Limitationen dieser Validierung, s. Bericht):
  - M1-RSI-Spike-Filter: braucht M1-Historie ueber den vollen WFA-Zeitraum
    fuer alle Maerkte; MT5-Terminal-Cap begrenzt M1 auf ~3,5 Monate (s.
    reports/s14_xauusd_squeeze_volume.md Abschnitt "Datenbasis") -- fuer
    eine 11-Jahres-WFA nicht verfuegbar. Der Live-Bot selbst faellt beim
    Fehlen von M1-Daten "fail-open" auf ungefiltert zurueck (config.py-
    Docstring), diese Portierung entspricht also exakt diesem Fallback-Fall.
  - Secure-Profit-Lock (prozentualer Kapital-Trigger/-Lock): anderer
    Mechanismus als der ATR-Chandelier-Trail dieses Projekts (core/
    backtester.py), nicht 1:1 abbildbar ohne neue Engine-Funktion. Diese
    Portierung handelt mit festem SL/TP (RR=rr_ratio), OHNE Trail/Lock.
    Das ist eine eigene, im Original zusaetzliche Ertragsschutz-Regel --
    ihr Fehlen macht das hier getestete Ergebnis eher KONSERVATIVER
    (kein vorzeitiges Sichern, aber auch kein vorzeitiges Aussteigen aus
    Gewinnern, die zurücklaufen), nicht optimistischer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.base import Signal, Strategy, adx as _adx, atr as _atr, ema as _ema, rsi as _rsi


def _atr_percentile(df: pd.DataFrame, atr_len: int, lookback: int) -> pd.Series:
    """1:1 wie strategy.py im Original: Min/Max-Normalisierung statt echtem
    Perzentil (monoton aequivalent, schneller)."""
    a = _atr(df, atr_len)
    roll_min = a.rolling(window=lookback, min_periods=lookback).min()
    roll_max = a.rolling(window=lookback, min_periods=lookback).max()
    rng = (roll_max - roll_min).replace(0, np.nan)
    return ((a - roll_min) / rng).fillna(0.5)


class S17DavidV2TrendPullback(Strategy):
    name = "s17_david_v2_trend_pullback"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "EURUSD")
        self.primary_tf = p.get("primary_tf", "H1")
        self.higher_tf = p.get("higher_tf", "H4")
        self.required_timeframes = [self.primary_tf, self.higher_tf]

        self.trend_len = int(p.get("trend_len", 200))
        self.rsi_len = int(p.get("rsi_len", 14))
        self.rsi_oversold = float(p.get("rsi_oversold", 40))
        self.trend_buffer_atr = float(p.get("trend_buffer_atr", 0.30))
        self.atr_len = int(p.get("atr_len", 14))
        self.atr_stop_mult = float(p.get("atr_stop_mult", 1.5))
        self.rr_ratio = float(p.get("rr_ratio", 2.0))

        self.adx_filter = bool(p.get("adx_filter", True))
        self.adx_len = int(p.get("adx_len", 14))
        self.adx_min = float(p.get("adx_min", 15.0))

        self.mtf_confirm = bool(p.get("mtf_confirm", True))
        self.mtf_trend_len = int(p.get("mtf_trend_len", 50))

        self.atr_vol_filter = bool(p.get("atr_vol_filter", True))
        self.atr_vol_lookback = int(p.get("atr_vol_lookback", 100))
        self.atr_vol_min_pct = float(p.get("atr_vol_min_percentile", 0.10))

        self.trade_long = bool(p.get("trade_long", True))
        self.trade_short = bool(p.get("trade_short", True))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(
            self.trend_len * 2, self.rsi_len + 1, self.atr_len + 1,
            self.adx_len * 2 if self.adx_filter else 0,
            (self.atr_vol_lookback + self.atr_len) if self.atr_vol_filter else 0,
        ) + 5

    def _higher_tf_trend(self, higher: pd.DataFrame) -> str | None:
        if higher is None or len(higher) < self.mtf_trend_len * 2:
            return None
        close = higher["close"]
        ema_h = _ema(close, self.mtf_trend_len)
        atr_h = _atr(higher, self.atr_len)
        puffer = 0.0
        if len(atr_h) and not pd.isna(atr_h.iloc[-1]):
            puffer = float(atr_h.iloc[-1]) * self.trend_buffer_atr
        c, e = close.iloc[-1], ema_h.iloc[-1]
        if pd.isna(c) or pd.isna(e):
            return None
        if c > e + puffer:
            return "up"
        if c < e - puffer:
            return "down"
        return "neutral"

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        if i < self._window:
            return None
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        close = win["close"]
        ema_s = _ema(close, self.trend_len)
        rsi_s = _rsi(close, self.rsi_len)
        atr_s = _atr(win, self.atr_len)

        vals = (close.iloc[-1], ema_s.iloc[-1], rsi_s.iloc[-1], rsi_s.iloc[-2], atr_s.iloc[-1])
        if any(pd.isna(v) for v in vals):
            return None
        c, e, rsi_now, rsi_prev, atr_now = (float(v) for v in vals)
        if atr_now <= 0:
            return None

        puffer = atr_now * self.trend_buffer_atr
        if c > e + puffer:
            trend = "up"
        elif c < e - puffer:
            trend = "down"
        else:
            return None  # Neutralzone

        if self.adx_filter:
            adx_now = float(_adx(win, self.adx_len)["adx"].iloc[-1])
            if pd.isna(adx_now) or adx_now < self.adx_min:
                return None

        if self.atr_vol_filter:
            atr_perc = float(_atr_percentile(win, self.atr_len, self.atr_vol_lookback).iloc[-1])
            if atr_perc < self.atr_vol_min_pct:
                return None

        if self.mtf_confirm:
            higher_trend = self._higher_tf_trend(bars[self.higher_tf])
            if higher_trend is not None:
                if (trend == "up" and higher_trend == "down") or \
                   (trend == "down" and higher_trend == "up"):
                    return None

        stop_dist = atr_now * self.atr_stop_mult
        if stop_dist <= 0:
            return None

        if trend == "up":
            if not self.trade_long:
                return None
            if not (rsi_prev <= self.rsi_oversold < rsi_now):
                return None
            direction = 1
        else:
            if not self.trade_short:
                return None
            ob = 100.0 - self.rsi_oversold
            if not (rsi_prev >= ob > rsi_now):
                return None
            direction = -1

        sl = c - direction * stop_dist
        tp = c + direction * stop_dist * self.rr_ratio
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={"rsi": rsi_now, "atr": atr_now, "trend": trend},
            expires_bars=0,
        )
