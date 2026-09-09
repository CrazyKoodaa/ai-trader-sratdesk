"""strategies/analyze_98946a741100.py — Portierung von "Universal Aggressive
Trend MACD v3.3 - Trailing TP" (Pine-Script/TradingView-Strategie, extern
eingereicht, s. reports/analyze_98946a741100.md fuer den Vorab-Review).

Handelsidee (Original): Trendfolge auf MACD(14/39/9)-Basis mit "Arming"
(ein MACD-Cross bleibt ``macd_valid_bars`` Kerzen lang guelltig, damit Trend-
/ADX-/Volumen-Filter nicht exakt zeitgleich mit dem Cross erfuellt sein
muessen) plus Continuation-Einstiegen (Breakout ueber/unter ein kleines
N-Bar-Hoch/Tief, waehrend MACD bereits in Trendrichtung steht). Gefiltert
durch Trend-EMA(99)+Slope, ADX(11)>20, Volumen>SMA(22)*0.6. Exit im Original
primaer ueber einen "Trailing Take-Profit" (Rueckfall vom bisherigen
Peak-Profit-%, gemessen auf Schlusskursbasis), ATR(18)*2.5-Stop nur als
Notbremse.

WICHTIGE ANNAHMEN / VEREINFACHUNGEN gegenueber dem Original
=============================================================
1. **Kein Prozent-Equity-Trailing-TP** — die Engine (core/backtester.py)
   kennt keinen "Rueckfall vom Peak-Profit-%"-Exit, nur einen initialen
   SL/TP plus optionalen ATR-Chandelier-Trail (``trail_atr_mult`` +
   ``tp_converts_to_trail``, s. S9/S11/S21 in diesem Projekt). Der Trailing-
   TP wird daher durch das dort etablierte Move-to-Trail-Muster ersetzt:
   TP bei ``min_rr`` x initialem ATR-Risiko -> bei Beruehrung KEIN Close,
   sondern SL wird auf TP-Niveau gezogen (Lock-in) und ab dann laeuft ein
   ATR(``atr_len``)-Chandelier-Trail mit Multiplikator ``trail_atr_mult``.
   Das ist konzeptionell verwandt (beides "lauf dem Trend hinterher, sichere
   Gewinn"), aber NICHT identisch: kein Prozentsatz-vom-Peak-Verhalten, kein
   ``trailingTpMinProfit``-Schwellwert, keine zwei Modi (Relativ/Prozent-
   punkte). ``trail_atr_mult`` ist die freie Naeherung fuer den Original-
   Parameter ``trailingTpGiveback``.
2. **Initialer Stop-Loss ab Entry (Risk-Sizing-Pflicht)** — das Original
   hat KEINEN Stop zum Entry-Zeitpunkt (100% Equity ohne Risikobezug, der
   Emergency-Stop wird erst NACH dem Fill gesetzt). Diese Engine verlangt
   ``Signal.stop_loss`` fuer die Lot-Berechnung nach ``risk_pct`` (SPEC-
   Risk-Modell). Der initiale SL ist daher ``close -/+ atr_len*emergency_
   mult`` (Original-Emergency-Distanz), aber ab Entry aktiv statt danach —
   das behebt bewusst den im Quick-Check genannten Sizing-Fehler, ist aber
   eine Abweichung vom Originalverhalten.
3. **``useOppositeExit`` (MACD-Gegencross schliesst Position) NICHT
   portiert** — Default im Original ist ``false``; um die Zahl der
   Freiheitsgrade fuer die WFO klein zu halten (Overfitting-Risiko laut
   Quick-Check), wird nur der Trailing/Emergency-Exit-Pfad abgebildet.
4. **Volumen-Filter nutzt ``tick_volume``** (Broker-Tick-Volumen, MT5-
   Konvention dieses Projekts) statt echtem Volumen — bei Forex/Metallen
   ohnehin die einzig verfuegbare Volumengroesse (wie in allen anderen
   Strategien hier, z.B. S14/S15).
5. **Cooldown** ist Bar-basiert (wie im Original) und wird ueber simplen
   Instanz-State (``self._last_entry_bar``) gehalten — die Engine ruft
   dieselbe Strategie-Instanz sequenziell je Bar auf (kein Multi-Symbol-
   Sharing), analog zum Cooldown-Muster in S12/S13.
6. **Keine Pine-Dashboard-/Visualisierungslogik** portiert (nur Handels-
   logik: Entries, initialer SL, TP-mit-Move-to-Trail).
7. **MACD/EMA/ADX-Berechnung** nutzt die projekteigenen kausalen
   Implementierungen aus ``strategies.base`` (Wilder-ADX/ATR statt Pine's
   ``ta.dmi``/``ta.atr`` — beide sind Wilder-basiert, sollten sich nur in
   Rundungsdetails unterscheiden). Fenster-basierte Rueckrechnung wie in
   S9/S11/S21 (kein Full-History-Replay je Bar) — bei sehr langer Slow-EMA
   (39) plus grossem Trend-EMA (99) leicht andere Einschwingwerte als ein
   Cold-Start-EMA seit Datenbeginn; Praxis-Konvention dieses Projekts.
8. Die vom Quick-Check bereits benannten "krummen" Parameter (14/39/9,
   ADX 11, Vol-SMA 22, ATR 18) werden 1:1 uebernommen (Ausgangspunkt fuer
   die WFO), aber im ``configs/analyze_98946a741100.yaml``-param_space
   bewusst nur mit 2-3 groben Kandidaten variiert statt weiter fein-
   optimiert.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, adx as _adx, atr as _atr, ema as _ema, sma as _sma


class AnalyzeUniversalMacdTrend(Strategy):
    name = "analyze_98946a741100"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H1")
        self.required_timeframes = [self.primary_tf]

        # MACD
        self.fast_len = int(p.get("fast_len", 14))
        self.slow_len = int(p.get("slow_len", 39))
        self.signal_len = int(p.get("signal_len", 9))

        # Entry-Timing
        self.use_macd_arming = bool(p.get("use_macd_arming", True))
        self.macd_valid_bars = int(p.get("macd_valid_bars", 10))
        self.use_continuation = bool(p.get("use_continuation", True))
        self.continuation_len = int(p.get("continuation_len", 5))
        self.cooldown_bars = int(p.get("cooldown_bars", 3))
        self.allow_longs = bool(p.get("allow_longs", True))
        self.allow_shorts = bool(p.get("allow_shorts", True))

        # Trend & Filter
        self.trend_ema_len = int(p.get("trend_ema_len", 99))
        self.use_ema_slope = bool(p.get("use_ema_slope", True))
        self.ema_slope_bars = int(p.get("ema_slope_bars", 3))
        self.adx_len = int(p.get("adx_len", 11))
        self.adx_threshold = float(p.get("adx_threshold", 20.0))
        self.use_adx_filter = bool(p.get("use_adx_filter", True))

        # Volumen
        self.use_volume_filter = bool(p.get("use_volume_filter", True))
        self.vol_sma_len = int(p.get("vol_sma_len", 22))
        self.vol_multiplier = float(p.get("vol_multiplier", 0.6))

        # Risk / Exit-Naeherung (s. Docstring Punkt 1+2)
        self.atr_len = int(p.get("atr_len", 18))
        self.emergency_mult = float(p.get("emergency_mult", 2.5))
        self.min_rr = float(p.get("min_rr", 1.0))            # Naeherung fuer trailingTpMinProfit
        self.trail_atr_mult = float(p.get("trail_atr_mult", 1.0))  # Naeherung fuer trailingTpGiveback
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = (
            max(self.slow_len * 3, self.trend_ema_len * 3, self.adx_len * 5, self.atr_len * 5)
            + self.macd_valid_bars + self.continuation_len + 10
        )
        self._last_entry_bar: int | None = None

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        if i < self._window:
            return None
        ts = df.index[i]

        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]
        close = win["close"]

        fast_ema = _ema(close, self.fast_len)
        slow_ema = _ema(close, self.slow_len)
        macd_line = fast_ema - slow_ema
        signal_line = _ema(macd_line, self.signal_len)
        macd_hist = macd_line - signal_line
        trend_ema = _ema(close, self.trend_ema_len)
        adx_df = _adx(win, self.adx_len)
        vol_sma = _sma(win["tick_volume"], self.vol_sma_len)
        atr_series = _atr(win, self.atr_len)

        need = [fast_ema, slow_ema, signal_line, trend_ema, adx_df["adx"], vol_sma, atr_series]
        if any(pd.isna(s.iloc[-1]) for s in need):
            return None
        if self.use_ema_slope and (
            len(trend_ema) <= self.ema_slope_bars or pd.isna(trend_ema.iloc[-1 - self.ema_slope_bars])
        ):
            return None

        c = float(close.iloc[-1])
        a = float(atr_series.iloc[-1])
        if not (a > 0):
            return None

        # -- Trend-Filter -----------------------------------------------------
        t_ema = float(trend_ema.iloc[-1])
        ema_slope_up = (not self.use_ema_slope) or t_ema > float(trend_ema.iloc[-1 - self.ema_slope_bars])
        ema_slope_dn = (not self.use_ema_slope) or t_ema < float(trend_ema.iloc[-1 - self.ema_slope_bars])
        long_trend_ok = c > t_ema and ema_slope_up
        short_trend_ok = c < t_ema and ema_slope_dn

        adx_ok = (not self.use_adx_filter) or float(adx_df["adx"].iloc[-1]) > self.adx_threshold
        volume_ok = (not self.use_volume_filter) or (
            float(win["tick_volume"].iloc[-1]) > float(vol_sma.iloc[-1]) * self.vol_multiplier
        )
        market_ok = adx_ok and volume_ok

        # -- MACD-Cross-Arming (statelos aus dem Fenster rekonstruiert) --------
        bull_cross = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        bear_cross = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        bull_cross = bull_cross.iloc[1:]  # erste Bar hat kein shift(1)
        bear_cross = bear_cross.iloc[1:]

        macd_now_bull = float(macd_line.iloc[-1]) > float(signal_line.iloc[-1])
        macd_now_bear = float(macd_line.iloc[-1]) < float(signal_line.iloc[-1])

        if not self.use_macd_arming:
            bull_cross_fresh = True
            bear_cross_fresh = True
        else:
            bull_idx = bull_cross[bull_cross].index
            bars_since_bull = (len(win) - 1 - win.index.get_loc(bull_idx[-1])) if len(bull_idx) else None
            bull_cross_fresh = (
                bars_since_bull is not None and bars_since_bull <= self.macd_valid_bars and macd_now_bull
            )
            bear_idx = bear_cross[bear_cross].index
            bars_since_bear = (len(win) - 1 - win.index.get_loc(bear_idx[-1])) if len(bear_idx) else None
            bear_cross_fresh = (
                bars_since_bear is not None and bars_since_bear <= self.macd_valid_bars and macd_now_bear
            )

        # -- Continuation -------------------------------------------------------
        long_continuation = False
        short_continuation = False
        if self.use_continuation and len(win) > self.continuation_len + 1:
            highest_before = float(win["high"].iloc[-self.continuation_len - 1 : -1].max())
            lowest_before = float(win["low"].iloc[-self.continuation_len - 1 : -1].min())
            long_continuation = (
                macd_now_bull and float(macd_hist.iloc[-1]) > 0 and c > highest_before
            )
            short_continuation = (
                macd_now_bear and float(macd_hist.iloc[-1]) < 0 and c < lowest_before
            )

        long_trigger = bull_cross_fresh or long_continuation
        short_trigger = bear_cross_fresh or short_continuation

        # -- Cooldown -------------------------------------------------------------
        cooldown_ok = self._last_entry_bar is None or (i - self._last_entry_bar) >= self.cooldown_bars

        long_cond = (
            self.allow_longs and cooldown_ok and market_ok and long_trend_ok and long_trigger
        )
        short_cond = (
            self.allow_shorts and cooldown_ok and market_ok and short_trend_ok and short_trigger
        )

        if long_cond:
            direction = 1
        elif short_cond:
            direction = -1
        else:
            return None

        sl = c - direction * self.emergency_mult * a
        tp = c + direction * self.min_rr * self.emergency_mult * a
        self._last_entry_bar = i
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "adx": float(adx_df["adx"].iloc[-1]), "atr": a,
                "entry_kind": "macd_cross" if (bull_cross_fresh if direction > 0 else bear_cross_fresh)
                else "continuation",
            },
            expires_bars=0,
        )
