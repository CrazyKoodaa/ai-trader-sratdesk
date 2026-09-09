"""strategies/s14_squeeze_volume_breakout.py — S14 Volatilitaets-Squeeze +
Volumen-bestaetigter Breakout (XAUUSD-Forschung, 3. Weg).

Idee (bewusst anders als S9-S11, die alle reine Preis-Trendfolge ohne
Volumen- oder Regime-Filter sind):

  1. REGIME-FILTER: ATR(atr_len) muss auf den letzten ``squeeze_lookback``
     Bars historisch NIEDRIG stehen (Perzentil <= ``squeeze_pct``) —
     eine "Kompressionsphase" (Bollinger-Squeeze-Analogon auf ATR-Basis).
     Trendfolge (S9-S11) handelt JEDES Signal unabhaengig vom Vola-Regime;
     hier wird bewusst nur der Ausbruch AUS einer ruhigen Phase gehandelt,
     weil dort das Chance/Risiko-Verhaeltnis (wenig Fehlausbrueche in
     bereits volatilen Phasen) strukturell anders ist.

  2. BREAKOUT: Preis bricht aus einem kurzen ``don_len``-Bar-Kanal aus
     (kausal, ohne aktuelle Bar im Kanal).

  3. VOLUMEN-BESTAETIGUNG: die Breakout-Bar muss ECHTES MT5-Volumen
     (tick_volume) von mind. ``vol_mult``x dem gleitenden Durchschnitt
     der letzten ``vol_len`` Bars zeigen — ein Filter, den keine der
     bisherigen S1-S13-Strategien nutzt (die meisten Datenquellen vor der
     MT5-Nachladung hatten kein echtes Volumen, nur TWAP-Fallback).
     Ohne Volumen-Bestaetigung werden viele Ausbrueche aus Kompression
     sofort wieder eingesammelt (Fakeouts); das Volumen soll echte
     institutionelle Teilnahme von duennen Broker-Kerzen unterscheiden.

  Exit wie S9-S11: ATR-Stop, Mindest-RR (min_rr) sichert Gewinn, danach
  Move-to-Trail (tp_converts_to_trail) per Chandelier-ATR-Trail.

Symbol-agnostisch nutzbar, aber fuer diese Untersuchung explizit fuer
XAUUSD entworfen (Gold zeigt ausgepraegte Kompressions-/Expansionszyklen
um Session-Uebergaenge und Makro-Events).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S14SqueezeVolumeBreakout(Strategy):
    name = "s14_squeeze_volume_breakout"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H4")
        self.required_timeframes = [self.primary_tf]

        self.don_len = int(p.get("don_len", 10))
        self.atr_len = int(p.get("atr_len", 14))
        self.squeeze_lookback = int(p.get("squeeze_lookback", 100))
        self.squeeze_pct = float(p.get("squeeze_pct", 0.25))
        self.vol_len = int(p.get("vol_len", 20))
        self.vol_mult = float(p.get("vol_mult", 1.5))
        # require_volume=False: Volumen-Bestaetigung ueberspringen (fuer
        # Datenquellen ohne echtes Volumen, z.B. TWAP-Fallback-Historie mit
        # tick_volume==0 durchgehend -- reiner Squeeze+Breakout-Vergleich).
        from strategies.base import as_flag
        self.require_volume = as_flag(p.get("require_volume", True), default=True)
        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 3.0))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        # Optionales Session-Zeitfenster (UTC-Stunden, halboffen [start,end)):
        # nur Ausbrueche handeln, deren Bar-Zeit in dieses Fenster faellt.
        # "session"-Preset haelt das WFO-Grid niedrig-dimensional (1 statt 2
        # Keys); session_start_h/session_end_h bleiben als direkter,
        # praeziser Override moeglich (haben Vorrang, falls beide gesetzt).
        _SESSION_PRESETS = {
            "none": (None, None), "asia": (0, 8), "london": (7, 16),
            "ny_overlap": (12, 17), "london_ny": (7, 21), "ny": (13, 21),
        }
        sh, eh = _SESSION_PRESETS.get(p.get("session", "none"), (None, None))
        self.session_start_h = p.get("session_start_h", sh)
        self.session_end_h = p.get("session_end_h", eh)

        self._window = max(self.don_len, self.atr_len, self.squeeze_lookback, self.vol_len) + 5

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        min_i = max(self.don_len, self.atr_len + self.squeeze_lookback, self.vol_len) + 2
        if i < min_i:
            return None
        ts = df.index[i]
        if self.session_start_h is not None and self.session_end_h is not None:
            h = int(ts.hour)
            sh, eh = int(self.session_start_h), int(self.session_end_h)
            in_window = (sh <= h < eh) if sh < eh else (h >= sh or h < eh)
            if not in_window:
                return None
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        # Donchian-Kanal aus den don_len Bars VOR der aktuellen (kausal)
        upper = float(win["high"].iloc[-self.don_len - 1 : -1].max())
        lower = float(win["low"].iloc[-self.don_len - 1 : -1].min())
        c = float(win["close"].iloc[-1])

        if c > upper:
            direction = 1
        elif c < lower:
            direction = -1
        else:
            return None

        # --- Regime-Filter: war die Vola VOR dem Ausbruch niedrig? ---
        atr_series = _atr(win, self.atr_len)
        a = float(atr_series.iloc[-1])
        if not (a > 0):
            return None
        # Perzentil der ATR-VORBAR (i-1) gegen die letzten squeeze_lookback
        # ATR-Werte (schliesst die expandierende Ausbruchs-Bar bewusst aus,
        # sonst wird die Kompression durch den eigenen Ausbruch verdeckt).
        atr_hist = atr_series.iloc[-self.squeeze_lookback - 1 : -1].dropna()
        if len(atr_hist) < self.squeeze_lookback // 2:
            return None
        prior_atr = float(atr_series.iloc[-2])
        if not (prior_atr > 0):
            return None
        rank = float((atr_hist <= prior_atr).mean())
        if rank > self.squeeze_pct:
            return None  # keine Kompressionsphase -> kein Setup

        # --- Volumen-Bestaetigung: Ausbruchs-Bar mit ueberdurchschnittlichem Volumen ---
        vol_ratio = None
        if self.require_volume:
            vol = win["tick_volume"] if "tick_volume" in win.columns else win.get("volume")
            if vol is None:
                return None
            vol_avg = float(vol.iloc[-self.vol_len - 1 : -1].mean())
            vol_now = float(vol.iloc[-1])
            if not (vol_avg > 0) or vol_now < self.vol_mult * vol_avg:
                return None
            vol_ratio = vol_now / vol_avg

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
                "squeeze_rank": rank, "vol_ratio": vol_ratio,
            },
            expires_bars=0,
        )
