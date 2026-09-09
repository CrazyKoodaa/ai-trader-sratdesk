"""strategies/s21_goldreaper_momentum_stack.py — Aus der echten Trade-Historie
von "Gold Reaper New V2 2" (MQL5-Signal #2265877, Wim Schrynemakers, 855
Trades, 29.10.2024-01.09.2026) rekonstruierte Handelslogik.

Kein Bytecode/keine Produktseite als Quelle — reines Verhaltens-Reverse-
Engineering: jeder Trade-Open-Zeitpunkt wurde gegen unsere eigene XAUUSD-
H1-Historie gelegt und auf Indikator-Zustand zum Entry-Moment geprueft
(855/855 Trades ausgewertet):

  - Trendrichtung H1 EMA200: 93,1% der Trades in Richtung Close>EMA200 (Long)
    bzw. <EMA200 (Short)
  - Kurzfrist-Trend EMA20 vs EMA50: 98,8% in Handelsrichtung ausgerichtet
    (fast zwingende Bedingung)
  - Mittelfrist EMA50 vs EMA200: 80,7% ausgerichtet (weichere Bedingung)
  - RSI(14), richtungsbereinigt: Median 66,7, nur 6,2% < 50 — EINDEUTIG
    ein MOMENTUM-Entry (Kurs+RSI schon in Bewegung), KEIN Pullback-Entry
    (anders als z.B. David V2/S17 in diesem Projekt, das RSI<40 verlangt)
  - Abstand zu EMA20 in ATR, richtungsbereinigt: Median +1.86 ATR (Kurs
    ist der EMA20 bereits vorausgeeilt) — bestaetigt Momentum- statt
    Pullback-Charakter
  - ATR-Perzentil (100-Fenster) bei Entry: Median 0.66 — leichter Bias zu
    ueberdurchschnittlicher Volatilitaet, kein hartes Cutoff
  - N-Bar-Donchian-Breakout-Test (10/20/50): nur 12,7% Trefferquote bei
    allen drei Laengen identisch -> KEIN Kanal-Breakout-System (verworfen)
  - Bis zu 13 gleichzeitig offene Positionen beobachtet, KEINE Lot-
    Eskalation (kein Martingale) -> Mehrfach-Einstiege waehrend eines
    andauernden Trends sind Teil des Designs, kein Fehler. In diesem
    Projekt ueber `risk.max_concurrent` in der Config abgebildet, NICHT
    strategie-intern (die Strategie feuert bewusst bei JEDER qualifizierten
    Bar neu, nicht nur beim ersten Ueberschreiten der Schwelle).
  - Session-Cluster: Haeufungen 02-04 UTC (Asien) und 15-18 UTC
    (London-Close/NY) — als optionaler Filter abgebildet, Default AUS
    (in der Vorab-Pruefung war die Verteilung breit genug, dass ein
    harter Session-Filter eher zufaellige Korrelation als Kausalitaet
    sein koennte -- WFO soll das empirisch entscheiden, nicht wir).

WICHTIGE EINSCHRAENKUNG: das Beobachtungsfenster (Okt 2024 - Sep 2026)
war ein aussergewoehnlicher Gold-Bullenmarkt (~2600 -> ~5300+ USD/oz).
63,9% der 855 Trades waren Long. Ein Teil der realen Performance koennte
schlicht Regime-Rueckenwind sein, nicht Strategie-Skill -- genau das
soll die WFA (mit Folds VOR und WAEHREND dieser Phase) aufdecken.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr, ema as _ema, rsi as _rsi


class S21GoldReaperMomentumStack(Strategy):
    name = "s21_goldreaper_momentum_stack"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H1")
        self.required_timeframes = [self.primary_tf]

        self.ema_fast = int(p.get("ema_fast", 20))
        self.ema_mid = int(p.get("ema_mid", 50))
        self.ema_slow = int(p.get("ema_slow", 200))
        self.rsi_len = int(p.get("rsi_len", 14))
        self.rsi_min = float(p.get("rsi_min", 60.0))      # Median-nahe Beobachtung: 66.7
        self.require_mid_slow_align = bool(p.get("require_mid_slow_align", True))
        self.require_cross = bool(p.get("require_cross", True))
        self.atr_len = int(p.get("atr_len", 14))
        self.atr_vol_lookback = int(p.get("atr_vol_lookback", 100))
        self.atr_vol_min_pct = float(p.get("atr_vol_min_percentile", 0.0))  # Default aus: kein hartes Cutoff
        self.session_start_h = p.get("session_start_h")
        self.session_end_h = p.get("session_end_h")

        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.trail_atr_mult = float(p.get("trail_atr_mult", 3.0))
        self.min_rr = float(p.get("min_rr", 1.5))
        self.risk_pct = float(p.get("risk_pct", 0.003))   # klein: Strategie stapelt bewusst mehrere Positionen

        self._window = max(self.ema_slow * 2, self.atr_vol_lookback + self.atr_len, self.rsi_len * 3) + 10

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        min_i = max(self.ema_slow * 2, self.atr_vol_lookback + self.atr_len) + 5
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
        close = win["close"]

        rsi_series = _rsi(close, self.rsi_len)
        ema_f = _ema(close, self.ema_fast).iloc[-1]
        ema_m = _ema(close, self.ema_mid).iloc[-1]
        ema_s = _ema(close, self.ema_slow).iloc[-1]
        rsi_v = rsi_series.iloc[-1]
        rsi_prev = rsi_series.iloc[-2] if len(rsi_series) > 1 else float("nan")
        a = float(_atr(win, self.atr_len).iloc[-1])
        if any(pd.isna(v) for v in (ema_f, ema_m, ema_s, rsi_v, rsi_prev)) or not (a > 0):
            return None
        c = float(close.iloc[-1])

        # require_cross=True (Default): Signal ist ein EREIGNIS (RSI kreuzt
        # frisch ueber die Schwelle), nicht ein andauernder Zustand -- sonst
        # feuert die Bedingung auf JEDER Bar, solange RSI oben bleibt (~14x
        # mehr Trades als im echten Signal beobachtet, 13996 statt 855 in
        # der Vorab-Probe). Ein frischer Cross pro RSI-Ausschlag bildet die
        # beobachtete Mehrfach-Positionen-waehrend-eines-Trends-Dynamik
        # trotzdem ab, weil RSI waehrend eines Trends wiederholt ueber/unter
        # die Schwelle oszilliert -> mehrere Cross-Events, kein Dauerfeuer.
        long_cross = rsi_prev < self.rsi_min <= rsi_v
        short_cross = rsi_prev > (100.0 - self.rsi_min) >= (100.0 - rsi_v)

        if c > ema_s and ema_f > ema_m and rsi_v >= self.rsi_min and (not self.require_cross or long_cross):
            if self.require_mid_slow_align and not (ema_m > ema_s):
                return None
            direction = 1
        elif c < ema_s and ema_f < ema_m and (100.0 - rsi_v) >= self.rsi_min and (not self.require_cross or short_cross):
            if self.require_mid_slow_align and not (ema_m < ema_s):
                return None
            direction = -1
        else:
            return None

        if self.atr_vol_min_pct > 0:
            atr_series = _atr(win, self.atr_len)
            hist = atr_series.iloc[-self.atr_vol_lookback :]
            if len(hist) >= self.atr_vol_lookback // 2:
                rank = float((hist <= a).mean())
                if rank < self.atr_vol_min_pct:
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
                "rsi": rsi_v, "atr": a,
            },
            expires_bars=0,
        )

    def explain(self, bars: dict[str, pd.DataFrame], i: int) -> dict:
        """Rein lesende Diagnose derselben Gates wie ``on_bar`` — fuer
        menschenlesbares Live-Logging ("Traderbook": warum kein Einstieg?).

        Mutiert KEINEN State (die Strategie ist ohnehin zustandslos je Bar)
        und trifft keine Handelsentscheidung; spiegelt nur, an welchem Gate
        ``on_bar`` gerade steht. ``kind`` markiert das Rueckgabeschema fuer
        ``core.live._format_explain``.
        """
        df = bars[self.primary_tf]
        info: dict = {
            "kind": "rsi_ema_momentum",
            "time": df.index[i] if i < len(df) else None,
            "blocked_by": [],
            "ready": False,
            "rsi": None, "rsi_min": self.rsi_min,
            "trend": None, "direction_bias": None,
            "rsi_points_needed": None,
        }
        min_i = max(self.ema_slow * 2, self.atr_vol_lookback + self.atr_len) + 5
        if i < min_i:
            info["blocked_by"].append("warmup")
            return info

        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]
        close = win["close"]
        rsi_series = _rsi(close, self.rsi_len)
        ema_f = _ema(close, self.ema_fast).iloc[-1]
        ema_m = _ema(close, self.ema_mid).iloc[-1]
        ema_s = _ema(close, self.ema_slow).iloc[-1]
        rsi_v = rsi_series.iloc[-1]
        rsi_prev = rsi_series.iloc[-2] if len(rsi_series) > 1 else float("nan")
        if any(pd.isna(v) for v in (ema_f, ema_m, ema_s, rsi_v, rsi_prev)):
            info["blocked_by"].append("warmup")
            return info
        c = float(close.iloc[-1])
        info["rsi"] = float(rsi_v)

        trend_up = c > ema_s and ema_f > ema_m
        trend_down = c < ema_s and ema_f < ema_m
        info["trend"] = "up" if trend_up else ("down" if trend_down else "flat")

        if trend_up:
            info["direction_bias"] = 1
            info["rsi_points_needed"] = max(0.0, self.rsi_min - rsi_v)
            if self.require_mid_slow_align and not (ema_m > ema_s):
                info["blocked_by"].append("mid_slow_misaligned")
            if rsi_v < self.rsi_min:
                info["blocked_by"].append("rsi_below_threshold")
            elif self.require_cross and not (rsi_prev < self.rsi_min <= rsi_v):
                info["blocked_by"].append("no_fresh_cross")
        elif trend_down:
            info["direction_bias"] = -1
            info["rsi_points_needed"] = max(0.0, rsi_v - (100.0 - self.rsi_min))
            if self.require_mid_slow_align and not (ema_m < ema_s):
                info["blocked_by"].append("mid_slow_misaligned")
            if (100.0 - rsi_v) < self.rsi_min:
                info["blocked_by"].append("rsi_above_threshold")
            elif self.require_cross and not (rsi_prev > (100.0 - self.rsi_min) >= (100.0 - rsi_v)):
                info["blocked_by"].append("no_fresh_cross")
        else:
            info["blocked_by"].append("no_trend_alignment")

        if self.atr_vol_min_pct > 0 and info["direction_bias"] is not None and not info["blocked_by"]:
            atr_series = _atr(win, self.atr_len)
            a = float(atr_series.iloc[-1])
            hist = atr_series.iloc[-self.atr_vol_lookback :]
            if len(hist) >= self.atr_vol_lookback // 2:
                rank = float((hist <= a).mean())
                if rank < self.atr_vol_min_pct:
                    info["blocked_by"].append("atr_vol_filter")

        if self.session_start_h is not None and self.session_end_h is not None:
            ts = df.index[i]
            h = int(ts.hour)
            sh, eh = int(self.session_start_h), int(self.session_end_h)
            in_window = (sh <= h < eh) if sh < eh else (h >= sh or h < eh)
            if not in_window:
                info["blocked_by"].append("outside_session")

        info["ready"] = not info["blocked_by"] and info["direction_bias"] is not None
        return info
