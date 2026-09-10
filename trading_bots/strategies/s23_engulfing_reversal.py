"""strategies/s23_engulfing_reversal.py — S23 Volumen-bestaetigte
Engulfing-Reversal an Donchian-Extremen (XAUUSD).

Neuer Signal-Mechanismus (Kombination bisher NICHT getestet in diesem
Projekt): klassisches 2-Kerzen-Engulfing-Reversal-Muster (Preisaktion),
aber nur gewertet, wenn ES AN EINEM ECHTEN N-Bar-Struktur-Extrem
(Donchian-Kanalgrenze) auftritt UND die Engulfing-Bar durch echtes
MT5-Tick-Volumen ueber dem gleitenden Durchschnitt bestaetigt wird.

Unterschied zu bisherigen Verwandten:
  - S9 (Donchian-Breakout): reine Struktur, KEIN Kerzenmuster, handelt
    die FORTSETZUNG (Trendfolge), nicht die Umkehr.
  - S15 (Volumen-Klimax-Reversal): Ein-Kerzen-Muster (Range-Exhaustion +
    Schluss nahe Extrem GEGEN juengstes Momentum), KEIN Struktur-Extrem-
    Erfordernis, KEIN echtes 2-Kerzen-Engulfing. Scheiterte (PF~0.98,
    s. reports/s14_xauusd_squeeze_volume.md Abschnitt 2 "S15").
  - S23 (hier): verlangt ALLE DREI zusammen -- Struktur-Extrem (Donchian)
    + spezifisches Preisaktions-Muster (Engulfing, kein loseres Kriterium)
    + Volumen-Bestaetigung. Strenger als beide Vorgaenger, daher
    voraussichtlich seltener, aber praeziser.

Kausal (nur geschlossene Bars): Donchian-Kanal aus den ``don_len`` Bars
VOR der aktuellen (Kanal + aktuelle Bar getrennt), Engulfing ist ein reiner
2-Bar-Vergleich (aktuelle vs. Vorbar, beide bereits geschlossen), Volumen-
Durchschnitt aus ``vol_len`` Bars VOR der aktuellen. SL hinter dem
Engulfing-Extrem + ATR-Puffer, TP bei ``min_rr`` (Move-to-Trail wie
S9-S15, ``tp_converts_to_trail``).
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S23EngulfingReversal(Strategy):
    name = "s23_engulfing_reversal"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H4")
        self.required_timeframes = [self.primary_tf]

        self.don_len = int(p.get("don_len", 20))
        self.atr_len = int(p.get("atr_len", 14))
        self.vol_len = int(p.get("vol_len", 20))
        self.vol_mult = float(p.get("vol_mult", 1.5))
        self.sl_atr_buffer = float(p.get("sl_atr_buffer", 0.3))
        self.sl_atr_mult_floor = float(p.get("sl_atr_mult_floor", 1.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 2.5))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(self.don_len, self.atr_len, self.vol_len) + 5

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        if i < self._window:
            return None
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        o, h, l, c = (float(win["open"].iloc[-1]), float(win["high"].iloc[-1]),
                     float(win["low"].iloc[-1]), float(win["close"].iloc[-1]))
        po, pc = float(win["open"].iloc[-2]), float(win["close"].iloc[-2])
        vol = float(win["tick_volume"].iloc[-1])

        # Struktur-Extrem: Donchian-Kanal aus den don_len Bars VOR der
        # aktuellen (kausal, kein Lookahead auf die aktuelle Bar).
        chan_low = float(win["low"].iloc[-self.don_len - 1 : -1].min())
        chan_high = float(win["high"].iloc[-self.don_len - 1 : -1].max())
        at_low_extreme = l <= chan_low
        at_high_extreme = h >= chan_high

        # Klassisches Engulfing: Koerper der aktuellen Bar umschliesst den
        # Koerper der Vorbar VOLLSTAENDIG, UND die Richtung dreht.
        bullish_engulf = c > o and pc < po and c >= po and o <= pc
        bearish_engulf = c < o and pc > po and c <= po and o >= pc

        # Volumen-Bestaetigung: aktuelles Volumen >= vol_mult x Durchschnitt
        # der vol_len Bars VOR der aktuellen (aktuelle Bar selbst NICHT im
        # Durchschnitt, sonst hebt eine Klimax-Bar ihren eigenen Vergleichswert an).
        avg_vol = float(win["tick_volume"].iloc[-self.vol_len - 1 : -1].mean())
        vol_confirmed = avg_vol > 0 and vol >= self.vol_mult * avg_vol

        direction = None
        if at_low_extreme and bullish_engulf and vol_confirmed:
            direction = 1
        elif at_high_extreme and bearish_engulf and vol_confirmed:
            direction = -1
        if direction is None:
            return None

        atr_val = float(_atr(win, self.atr_len).iloc[-1])
        if not (atr_val > 0):
            return None

        extreme = l if direction > 0 else h
        buffer = self.sl_atr_buffer * atr_val
        sl_struct = extreme - direction * buffer
        # Floor: SL darf nicht enger als sl_atr_mult_floor x ATR sein (sonst
        # macht eine sehr enge Engulfing-Bar den Stop unrealistisch knapp).
        sl_floor = c - direction * self.sl_atr_mult_floor * atr_val
        sl = min(sl_struct, sl_floor) if direction > 0 else max(sl_struct, sl_floor)

        risk_dist = abs(c - sl)
        if not (risk_dist > 0):
            return None
        tp = c + direction * self.min_rr * risk_dist

        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "atr": atr_val, "avg_vol": avg_vol, "vol": vol,
            },
            expires_bars=0,
        )
