"""strategies/s9_donchian_trend.py — S9 Donchian-Breakout-Trendfolge.

Klassisches "Turtle"-Archetyp: Breakout aus einem N-Bar-Donchian-Kanal
(Hoch/Tief der letzten ``don_len`` Bars, OHNE die aktuelle Bar — sonst
Lookahead), Entry Market naechste Bar, initialer ATR-Stop, TP bei
``min_rr`` (Default 2.0) x Risiko-Distanz. Das TP ist aber kein harter
Exit: ``meta["tp_converts_to_trail"]=True`` laesst core/backtester.py die
Position bei TP-Beruehrung NICHT schliessen, sondern das TP loeschen und ab
dann per Chandelier-ATR-Trailing-Stop weiterlaufen ("Move-to-Trail") — bei
einem echten Push (Trend haelt) laeuft die Position weiter (bis 1:10R und
mehr moeglich), sonst sichert das Mindest-RR von 1:2 ein ordentliches
Ergebnis, bevor der Trail zurueckfaellt.

Symbol-agnostisch, keine Instrument-spezifischen Annahmen (keine Pips,
keine Session-Fenster) — bewusst so einfach wie moeglich (wenige Parameter
-> guenstig fuer PBO/Params-Gate) fuer den breiten Multi-Symbol-Test.

Optionaler ADX-Trend-Regime-Filter (``adx_min``, Default 0.0 = aus,
rueckwaertskompatibel): auf H1 (s. configs/s9h_donchian_trend_h1.yaml)
erzeugt der rohe Breakout deutlich mehr Fehlausbrueche in Choppy-Phasen
als auf H4 (verifiziert: reports/wfa_s9h_donchian_xauusd_h1, MC-DD 21.4%,
DSR 0.18 vs. H4s 8.9%/0.87). ``adx_min`` filtert Bars mit ADX(``atr_len``)
unter der Schwelle -- kausal (nur abgeschlossene Bars, core/indicators.py
ist die kanonische ADX-Implementierung), je Fold WFO-selektiert statt
hindsight-gesetzt.

Optionaler Session-Filter (``session_filter``, Default "off",
rueckwaertskompatibel): blendet Breakouts ausserhalb der London/NY-
Handelszeit aus (kausale Hypothese: Asian-Session-Breakouts auf XAUUSD H1
haben weniger Liquiditaet hinter sich und reissen haeufiger ab/reverten,
statt zu laufen). Fenster-Default 07:00-21:00 UTC ist NICHT aus dieser
Session abgeleitet, sondern SPEC.md's eigene Konvention (identisch zu S1
"Session 07-17 UTC" / S5 "Session 07-21 UTC") -- wiederverwendet statt neu
gewaehlt, um Hindsight-Tuning zu vermeiden. Nutzt core/time_engine.py
``in_session`` (DST-sicher via zoneinfo, hier session="UTC" also ohne
DST-Verschiebung).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.indicators import adx as _adx
from core.time_engine import in_session as _in_session
from strategies.base import Signal, Strategy, atr as _atr


class S9DonchianTrend(Strategy):
    name = "s9_donchian_trend"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H4")
        self.required_timeframes = [self.primary_tf]

        self.don_len = int(p.get("don_len", 20))
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 3.0))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))
        self.adx_min = float(p.get("adx_min", 0.0))  # 0.0 = aus (Default, rueckwaertskompatibel)

        self.session_filter = str(p.get("session_filter", "off")).strip().lower() in ("on", "true", "yes", "1")
        self.session_start_utc = str(p.get("session_start_utc", "07:00"))
        self.session_end_utc = str(p.get("session_end_utc", "21:00"))

        self._window = max(self.don_len, self.atr_len) + 5

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        if i < self.don_len + self.atr_len:
            return None
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        # Kanal aus den don_len Bars VOR der aktuellen (kausal, kein Lookahead)
        upper = float(win["high"].iloc[-self.don_len - 1 : -1].max())
        lower = float(win["low"].iloc[-self.don_len - 1 : -1].min())
        c = float(win["close"].iloc[-1])

        if c > upper:
            direction = 1
        elif c < lower:
            direction = -1
        else:
            return None

        if self.session_filter and not _in_session(ts, "UTC", self.session_start_utc, self.session_end_utc):
            return None

        atr_series = _atr(win, self.atr_len)
        a = float(atr_series.iloc[-1])
        if not (a > 0):
            return None

        if self.adx_min > 0:
            adx_v = float(_adx(win, self.atr_len)["adx"].iloc[-1])
            if not (adx_v >= self.adx_min):
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
                "don_upper": upper, "don_lower": lower, "atr": a,
            },
            expires_bars=0,
        )
