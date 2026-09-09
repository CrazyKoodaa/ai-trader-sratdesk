"""strategies/s20_sgh_momentum_breakout.py — Platzhalter-Interpretation von
"Smart Gold Hunter" (MQL5-Marketplace, Barbaros Bulent Kortarla,
https://www.mql5.com/en/market/product/170050), NICHT der tatsächliche,
dekompilierte Code.

WICHTIGER UNTERSCHIED zu S19 (Lizard-Nachbau): Für Smart Gold Hunter gibt
es — anders als bei Lizard — in KEINER öffentlichen Quelle (offizielle
MQL5-Produktseite, Drittanbieter-Reviews wie fxtoolsai.com, Foren) auch
nur eine einzige konkrete Angabe zu Indikatoren, Entry-/Exit-Bedingungen
oder Parameterwerten. Alles, was öffentlich bekannt ist: "XAUUSD, M15,
Single-Entry ohne Grid/Martingale, festes SL/TP, 6 waehlbare Profile
(Striker/Ultimate Scalper/Swinger/Prop Scalper/PRR Scalping/Custom) mit
unterschiedlicher Handelsfrequenz/Haltedauer/Risikoprofil".

Diese Datei ist deshalb KEIN Nachbau einer recherchierten Logik (die
existiert oeffentlich nicht), sondern ein bewusst einfacher, generischer
Platzhalter-Mechanismus (Donchian-Momentum-Breakout + ATR-Volatilitaets-
Filter, wie bereits bei S9/S14 in diesem Projekt etabliert), dessen
Parameter die BESCHRIEBENEN Profile nachbildet (kurzer Kanal + kleines RR
= "Ultimate Scalper", langer Kanal + grosses RR = "Swinger", usw.) — rein
um die Nutzeranfrage ("beide Strategien mit allen Einstellungen durch die
WFA") technisch zu erfuellen. Jedes Ergebnis dieser Datei sagt NICHTS
darueber aus, ob das echte, verkaufte Produkt profitabel ist oder nicht.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


def _atr_percentile(df: pd.DataFrame, atr_len: int, lookback: int) -> float:
    a = _atr(df, atr_len)
    window = a.iloc[-lookback:]
    if window.isna().all():
        return 0.5
    last = float(a.iloc[-1])
    rng = window.max() - window.min()
    if rng <= 0 or pd.isna(rng):
        return 0.5
    return float((last - window.min()) / rng)


class S20SghMomentumBreakout(Strategy):
    name = "s20_sgh_momentum_breakout"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "M15")
        self.required_timeframes = [self.primary_tf]

        self.range_len = int(p.get("range_len", 20))          # "Profil"-Dial: 8=Scalper .. 50=Swinger
        self.atr_len = int(p.get("atr_len", 14))
        self.atr_vol_lookback = int(p.get("atr_vol_lookback", 100))
        self.atr_vol_min_pct = float(p.get("atr_vol_min_percentile", 0.20))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 1.5))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 2.5))
        self.min_rr = float(p.get("min_rr", 2.0))              # "Profil"-Dial: 1.0=Scalper .. 3.0=Swinger
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(self.range_len, self.atr_vol_lookback + self.atr_len) + 10

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        min_i = max(self.range_len, self.atr_vol_lookback + self.atr_len) + 5
        if i < min_i:
            return None
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        upper = float(win["high"].iloc[-self.range_len - 1 : -1].max())
        lower = float(win["low"].iloc[-self.range_len - 1 : -1].min())
        c = float(win["close"].iloc[-1])
        if c > upper:
            direction = 1
        elif c < lower:
            direction = -1
        else:
            return None

        a = float(_atr(win, self.atr_len).iloc[-1])
        if not (a > 0):
            return None
        # "Nicht am schlafenden Markt handeln" -- analog zum oeffentlich
        # beschriebenen Konzept anderer Gold-EAs dieser Kategorie.
        vol_pct = _atr_percentile(win, self.atr_len, self.atr_vol_lookback)
        if vol_pct < self.atr_vol_min_pct:
            return None

        sl = c - direction * self.sl_atr_mult * a
        risk = abs(c - sl)
        if risk <= 0:
            return None
        tp = c + direction * risk * self.min_rr

        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "range_upper": upper, "range_lower": lower, "atr": a, "vol_pct": vol_pct,
            },
            expires_bars=0,
        )
