"""strategies/s15_volume_climax_reversion.py — S15 Volumen-Klimax-
Erschoepfungs-Reversal (XAUUSD-Forschung, 3. Weg, Variante B).

Gegenstueck zu S14: statt Ausbrueche AUS ruhigen Phasen zu handeln, wird
hier das Gegenteil gesucht — eine Erschoepfungs-Bar INNERHALB einer bereits
lebhaften Marktphase (ADX ueber Schwelle = kein totes Choppy-Regime, aber
auch kein Squeeze), erkennbar an:

  1. VOLUMEN-KLIMAX: tick_volume der Bar >= ``vol_mult``x dem gleitenden
     Durchschnitt (Panik-/Euphorie-Spitze, ungewoehnlich hohe Teilnahme).
  2. GROSSE RANGE: True Range der Bar >= ``range_mult``x ATR (die Bar
     "verbraucht" ueberproportional viel Bewegung in kurzer Zeit).
  3. SCHLUSS NAHE AM EXTREM GEGEN DIE JUENGSTE RICHTUNG: bei einer Bar,
     die stark GEFALLEN ist (close nahe Tief der Bar) UND die vorherigen
     ``mom_len`` Bars per Saldo abwaerts liefen, wird auf Erschoepfung des
     Abwaertsdrucks gewettet (LONG-Reversal), und umgekehrt.

Diese Kombination (Volumen-Klimax + Range-Exhaustion + Gegen-Momentum) ist
ein klassisches Order-Flow-Muster ("Climax Reversal" / "Selling Climax"),
das in diesem Projekt bisher NICHT getestet wurde — alle bisherigen
Strategien (S1-S13) sind entweder reine Trendfolge (folgen der Bewegung)
oder Pullback/VWAP-Fade OHNE Volumen-Bestaetigung. Hier ist Volumen die
PRIMAERE Eintritts-Bedingung, nicht nur ein Gewichtungsfaktor wie beim
VWAP.

Exit: enger ATR-Stop (Erschoepfungs-Wetten brauchen straffe Kontrolle,
falls die Erschoepfung ausbleibt), Mindest-RR, danach Move-to-Trail wie
S9-S14.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S15VolumeClimaxReversion(Strategy):
    name = "s15_volume_climax_reversion"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H4")
        self.required_timeframes = [self.primary_tf]

        self.atr_len = int(p.get("atr_len", 14))
        self.vol_len = int(p.get("vol_len", 20))
        self.vol_mult = float(p.get("vol_mult", 2.0))
        self.range_mult = float(p.get("range_mult", 1.8))
        self.mom_len = int(p.get("mom_len", 5))
        self.close_extreme_frac = float(p.get("close_extreme_frac", 0.30))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 1.5))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 2.5))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(self.atr_len, self.vol_len, self.mom_len) + 5

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        min_i = max(self.atr_len, self.vol_len, self.mom_len) + 2
        if i < min_i:
            return None
        ts = df.index[i]
        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]

        vol = win["tick_volume"] if "tick_volume" in win.columns else win.get("volume")
        if vol is None:
            return None
        vol_avg = float(vol.iloc[-self.vol_len - 1 : -1].mean())
        vol_now = float(vol.iloc[-1])
        if not (vol_avg > 0) or vol_now < self.vol_mult * vol_avg:
            return None

        atr_series = _atr(win, self.atr_len)
        a = float(atr_series.iloc[-2])  # ATR VOR der Klimax-Bar (nicht durch sie selbst aufgeblaeht)
        if not (a > 0):
            return None

        o, h, l, c = (float(win[x].iloc[-1]) for x in ("open", "high", "low", "close"))
        bar_range = h - l
        if bar_range <= 0 or bar_range < self.range_mult * a:
            return None  # keine ueberdurchschnittlich grosse Bar

        # juengstes Momentum VOR der Klimax-Bar (kausal: bis inkl. i-1)
        mom_win = win["close"].iloc[-self.mom_len - 1 : -1]
        mom = float(mom_win.iloc[-1] - mom_win.iloc[0])

        close_pos = (c - l) / bar_range  # 0 = Schluss am Tief, 1 = Schluss am Hoch

        if mom < 0 and close_pos <= self.close_extreme_frac:
            # Abwaerts-Klimax, Schluss nahe Tief -> Verkaufsdruck erschoepft -> LONG
            direction = 1
        elif mom > 0 and close_pos >= 1.0 - self.close_extreme_frac:
            # Aufwaerts-Klimax, Schluss nahe Hoch -> Kaufdruck erschoepft -> SHORT
            direction = -1
        else:
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
                "atr": a, "vol_ratio": vol_now / vol_avg, "bar_range_atr": bar_range / a,
                "mom": mom, "close_pos": close_pos,
            },
            expires_bars=0,
        )
