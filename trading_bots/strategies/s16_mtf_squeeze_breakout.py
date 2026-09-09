"""strategies/s16_mtf_squeeze_breakout.py — S16 Multi-Timeframe Squeeze-
Breakout (XAUUSD-Forschung, echtes MTF, nicht nur reskalierte Parameter).

Unterschied zu S14 (gleiche Grundidee, ein einziger Timeframe) und zum
gescheiterten H1-Reskalierungs-Test von vorhin (dort lief die KOMPLETTE
S14-Logik nur mit x4-skalierten Parametern auf H1 — im Kern immer noch
dieselbe Ein-Timeframe-Strategie, nur feiner gerastert):

  - REGIME (H4): Squeeze-Erkennung (ATR-Perzentil niedrig) laeuft auf
    geschlossenen H4-Bars — genau die Ebene, auf der S14 nachweislich
    funktioniert (PF ~1.5 Voll-Historie).
  - ENTRY (H1): Donchian-Breakout + Volumen-Bestaetigung laeuft auf H1 —
    feineres Timing, mehr Gelegenheiten INNERHALB eines bestaetigten
    H4-Squeeze-Fensters, ohne auf den vollen H4-Bar-Abschluss warten zu
    muessen. Ziel: mehr OOS-Trades (das Kernproblem von S14) bei
    aehnlicher Signalqualitaet, weil die Regime-Guete weiterhin von H4
    kommt, nicht von der (nachweislich schwaecheren) H1-Eigenlogik.

Kausalitaet: die H4-Historie wird bei jeder H1-Bar auf "echt bereits
geschlossene" H4-Bars gefiltert (Index + 4h <= aktuelle H1-Zeit) — keine
Bar, die zum Zeitpunkt t noch offen waere, fliesst in die Regime-Erkennung
ein.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S16MtfSqueezeBreakout(Strategy):
    name = "s16_mtf_squeeze_breakout"
    required_timeframes = ["H1", "H4"]

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")

        # H4-Regime (Squeeze)
        self.atr_len_h4 = int(p.get("atr_len_h4", 14))
        self.squeeze_lookback = int(p.get("squeeze_lookback", 100))
        self.squeeze_pct = float(p.get("squeeze_pct", 0.35))

        # H1-Entry (Breakout + Volumen)
        self.don_len = int(p.get("don_len", 24))       # H1-Bars (24h Kanal als Default)
        self.atr_len_h1 = int(p.get("atr_len_h1", 14))
        self.vol_len = int(p.get("vol_len", 50))
        self.vol_mult = float(p.get("vol_mult", 1.0))

        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 3.0))
        self.min_rr = float(p.get("min_rr", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window_h1 = max(self.don_len, self.atr_len_h1, self.vol_len) + 5
        self._min_h4_needed = self.atr_len_h4 + self.squeeze_lookback + 2

    def _h4_squeeze_ok(self, h4: pd.DataFrame) -> bool:
        """True, wenn die bereits geschlossenen H4-Bars eine Kompressions-
        phase zeigen (identische Perzentil-Logik wie S14).

        ``h4`` kommt aus ``bars["H4"]`` — der Backtester schneidet das schon
        auf genau die zum aktuellen H1-Bar bereits geschlossenen H4-Bars zu
        (SPEC: ``close_tf <= close_primary``, core/backtester.py). Ein
        zusaetzlicher Zeit-Refilter hier waere nicht nur redundant, sondern
        (bei wachsendem ``h4`` ueber 68k H1-Bars) ein echtes O(n)-pro-Bar-
        Performance-Problem -- daher direkt die letzten Bars nehmen."""
        if len(h4) < self._min_h4_needed:
            return False
        atr4 = _atr(h4.iloc[-(self.squeeze_lookback + self.atr_len_h4 + 5):], self.atr_len_h4)
        prior_atr = float(atr4.iloc[-1])
        if not (prior_atr > 0):
            return False
        atr_hist = atr4.iloc[-self.squeeze_lookback - 1 : -1].dropna()
        if len(atr_hist) < self.squeeze_lookback // 2:
            return False
        rank = float((atr_hist <= prior_atr).mean())
        return rank <= self.squeeze_pct

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        h1 = bars["H1"]
        h4 = bars["H4"]
        min_i = max(self.don_len, self.atr_len_h1, self.vol_len) + 2
        if i < min_i:
            return None
        ts = h1.index[i]

        if not self._h4_squeeze_ok(h4):
            return None

        lo = max(0, i + 1 - self._window_h1)
        win = h1.iloc[lo : i + 1]

        upper = float(win["high"].iloc[-self.don_len - 1 : -1].max())
        lower = float(win["low"].iloc[-self.don_len - 1 : -1].min())
        c = float(win["close"].iloc[-1])
        if c > upper:
            direction = 1
        elif c < lower:
            direction = -1
        else:
            return None

        a1 = float(_atr(win, self.atr_len_h1).iloc[-1])
        if not (a1 > 0):
            return None

        vol = win["tick_volume"] if "tick_volume" in win.columns else win.get("volume")
        if vol is None:
            return None
        vol_avg = float(vol.iloc[-self.vol_len - 1 : -1].mean())
        vol_now = float(vol.iloc[-1])
        if not (vol_avg > 0) or vol_now < self.vol_mult * vol_avg:
            return None

        sl = c - direction * self.sl_atr_mult * a1
        tp = c + direction * self.min_rr * self.sl_atr_mult * a1
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len_h1,
                "tp_converts_to_trail": True,
                "don_upper": upper, "don_lower": lower, "atr_h1": a1,
                "vol_ratio": vol_now / vol_avg,
            },
            expires_bars=0,
        )
