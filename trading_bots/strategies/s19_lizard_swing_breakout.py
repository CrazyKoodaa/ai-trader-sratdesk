"""strategies/s19_lizard_swing_breakout.py — Eigene Interpretation des
öffentlich beschriebenen "Lizard EA" (MQL5-Marketplace, NeoBull/Marco
Scherer, https://www.mql5.com/en/market/product/172541), NICHT der
tatsächliche, dekompilierte Code — der Bytecode von `Lizard_1.72 MT5.ex5`
lässt sich mit den hier verfügbaren Mitteln (kein IDA/Ghidra/radare2, kein
MQL5-Decompiler) nicht rekonstruieren; die Datei speichert Logik + Ressourcen
komprimiert, nur der unkomprimierte Header (Copyright/Version) ist lesbar.

Nachgebautes KONZEPT aus der öffentlichen Produktbeschreibung:
  "identifiziert Struktur-Levels und platziert Pending-Stop-Orders bei
  kalkulierten Einstiegspunkten", "unterscheidet echte Ausbrüche von
  blossem Kurskontakt (Fake-Breakout-Filter)", "mehrstufiges Exit-System
  mit Breakeven + Trailing", XAUUSD/H1, kein Grid/Martingale, festes SL/TP.

Portierung in dieses Projekt (Signal/Strategy-Interface unterstützt keine
echten Pending-Stop-Orders mit Ablauf — `entry_type="limit"` ist hier
Limit-Semantik, nicht Stop-Semantik, s. core/backtester.py Zeile ~548):
  - Struktur-Level: kausal bestätigte Swing-Hoch/Tief (strategies.base.
    swing_points, identisches Prinzip wie ein "Struktur-Level"-Scan)
  - "Pending Stop" wird als Markt-Order approximiert, ausgelöst auf der
    Bar, die den Level bricht (funktional äquivalent zu einer im Markt
    liegenden Stop-Order, die genau dann triggert)
  - Fake-Breakout-Filter: Schluss muss den Level um mind.
    `breakout_buffer_atr` x ATR überschreiten, nicht nur berühren
  - SL: hinter dem gegenüberliegenden Struktur-Level (bzw. ATR-Fallback)
  - Exit: Mindest-RR, danach Move-to-Trail (Breakeven+Trailing-Analogon)

Dies ist KEIN 1:1-Nachbau des verkauften Produkts (die 6-9 parallelen
Substrategien, das Konto-Groessen-abhaengige "Zone A/B", der NFP-Filter
und der genaue Fake-Breakout-Algorithmus sind nirgends offengelegt) —
sondern ein eigenständiger, plausibler Nachbau des beschriebenen
GRUNDPRINZIPS zum ehrlichen Testen durch die WFA.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S19LizardSwingBreakout(Strategy):
    name = "s19_lizard_swing_breakout"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H1")
        self.required_timeframes = [self.primary_tf]

        self.left = int(p.get("left", 10))
        self.right = int(p.get("right", 10))
        self.atr_len = int(p.get("atr_len", 14))
        self.breakout_buffer_atr = float(p.get("breakout_buffer_atr", 0.1))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 1.5))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 2.5))
        self.min_rr = float(p.get("min_rr", 1.5))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = max(self.left + self.right + 5, self.atr_len + 5)

        # Zustandsbehaftetes Swing-Tracking (wie im Original ein "var" in
        # Pine): pro Bar wird NUR die neu bestaetigte Kandidaten-Bar
        # geprueft (O(left+right)), nicht rueckwaerts das ganze Fenster neu
        # durchsucht. Das war vorher ein echter Performance-Bug (O(n^2)-
        # artige Rueckwaerts-Suche auf JEDER Bar) -- 91 Minuten fuer 72
        # Kombos statt Sekunden. Persistiert korrekt ueber on_bar-Aufrufe
        # hinweg, weil dieselbe Strategie-Instanz den ganzen Backtest laeuft.
        self._last_swing_high: float | None = None
        self._last_swing_low: float | None = None
        self._swing_checked_up_to = -1  # Index der zuletzt geprueften Kandidaten-Bar

    def _update_swings(self, df: pd.DataFrame, i: int) -> None:
        """Prueft alle NEU faelligen Kandidaten-Bars (Index c=i-right) seit
        dem letzten Aufruf und aktualisiert die gecachten Swing-Werte."""
        highs = df["high"]
        lows = df["low"]
        first_c = max(self.left, self._swing_checked_up_to + 1)
        last_c = i - self.right
        for c in range(first_c, last_c + 1):
            seg_h = highs.iloc[c - self.left : c + self.right + 1]
            seg_l = lows.iloc[c - self.left : c + self.right + 1]
            if float(highs.iloc[c]) == seg_h.max():
                self._last_swing_high = float(highs.iloc[c])
            if float(lows.iloc[c]) == seg_l.min():
                self._last_swing_low = float(lows.iloc[c])
        self._swing_checked_up_to = max(self._swing_checked_up_to, last_c)

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        min_i = self.left + self.right + self.atr_len + 5
        if i < min_i:
            return None
        ts = df.index[i]

        self._update_swings(df, i)
        last_swing_high = self._last_swing_high
        last_swing_low = self._last_swing_low
        if last_swing_high is None or last_swing_low is None:
            return None

        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]
        a = float(_atr(win, self.atr_len).iloc[-1])
        if not (a > 0):
            return None
        buf = self.breakout_buffer_atr * a
        c = float(win["close"].iloc[-1])

        if c > last_swing_high + buf:
            direction = 1
            sl = last_swing_low - buf
        elif c < last_swing_low - buf:
            direction = -1
            sl = last_swing_high + buf
        else:
            return None

        # Fallback, falls das gegenueberliegende Struktur-Level zu weit weg
        # liegt (z.B. lange Zeit ohne Gegenbewegung): ATR-Stop statt Struktur.
        risk = abs(c - sl)
        if risk <= 0 or risk > 6 * a:
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
                "swing_high": last_swing_high, "swing_low": last_swing_low, "atr": a,
            },
            expires_bars=0,
        )
