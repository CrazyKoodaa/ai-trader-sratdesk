"""strategies/analyze_e241bb189fa2.py — Portierung von
"XAUUSD_TrendPullback_ATR.mq5" (MT5/MQL5-EA, extern eingereicht,
vollstaendiges, kompilierbares Snippet). Siehe
``reports/analyze_e241bb189fa2.md`` fuer den Review inkl. Triage-Ergebnis
und den Vergleich zum vorherigen Quick-Check.

Handelsidee (Original): Trendfolge auf XAUUSD mit H4-EMA50 als Trendfilter
(Preis ueber/unter EMA + EMA-Steigung ueber 2 Bars), Einstieg auf M15 bei
Pullback zur EMA20 (Beruehrung der Vorkerze + Ruecklauf ueber/unter die
EMA) mit Bestaetigungskerze (Schlusskurs schlaegt Hoch/Tief der Pullback-
Kerze UND liegt jenseits der EMA). SL = der ENGERE von (a) ATR-Multiplikator
ab aktuellem Kurs und (b) Struktur-Extremum der Pullback-Kerze +/- 0.20x
ATR-Puffer; TP = RR-Multiplikator (Default 2) des SL-Abstands. Money-
Management ueber Equity-Risiko-Prozent + Tick-Value, Rundung per Volume-
Step nach unten; Session-, Spread- und Mindest-ATR-Filter; Break-Even-
Verschiebung des SL bei Erreichen von +1R (TP bleibt unveraendert).

Es gibt nur EINEN Parametersatz im Original (keine benannten
Risiko-Profile/Presets) — diese Portierung bildet daher keinen
``risk_profile``-Auswahlparameter, sondern die Original-Werte direkt als
einzelne, frei tunbare Parameter ab (s. Quick-Check Abschnitt 2).

WICHTIGE ANNAHMEN / VEREINFACHUNGEN gegenueber dem Original
=============================================================
1. **Kein separater Break-Even-Hook.** Das Original zieht den SL bei
   Erreichen von ``InpBreakEvenAtR`` (Default 1R) auf Einstand + kleinen
   Offset, OHNE das TP zu veraendern und OHNE danach weiterzutrailen — ein
   reines "SL auf B/E, TP bleibt hart bei 2R" ("HALTE"-Zustand). ``core/
   backtester.py`` kennt nur zwei SL-Modelle: fixer SL/TP, oder
   ``tp_converts_to_trail`` (TP-Beruehrung zieht SL auf TP-Niveau + startet
   einen offenen ATR-Trail, das etablierte Muster in anderen ``analyze_*``-
   Portierungen dieses Projekts). Beides bildet "B/E bei 1R, hartes TP bei
   2R" nicht ab (kein Per-Bar-Hook, der den SL auf ein beliebiges
   Zwischen-R-Niveau zieht und dort stehenbleibt, ohne das TP zu beruehren).
   Diese Portierung laesst SL/TP daher FEST (kein B/E) — das macht das
   Ergebnis tendenziell PESSIMISTISCHER als das Original bei Trades, die
   1R erreichen und danach durch den Original-B/E-Punkt zurueck in einen
   Verlust laufen (das Original waere dort ~+/-0 statt -1R Verlust).
2. **Spread-Filter global statt Bar-fuer-Bar.** ``InpMaxSpreadPoints``
   entspricht dem projektweiten Kostenmodell (``core/backtester.py``:
   Spread/Slippage global ueber ``CostModel``, s. Config ``costs:``) statt
   einer Vor-Ablehnung pro Bar — ein zu teurer Trade schlaegt sich hier in
   den Kosten nieder statt in einer verworfenen Chance.
   ``SYMBOL_TRADE_STOPS_LEVEL`` (Broker-Mindestabstand) hat keine
   Entsprechung im Backtest (kein Broker-Zwangsabstand modelliert).
3. **ATR-Mindestschwelle auf Preis-Einheiten umgerechnet.** Statt Broker-
   "Punkten" (die vom `_Point`-Wert des Brokers abhaengen und im Original
   ungeprueft blieben, s. Quick-Check) verwendet diese Portierung direkt
   einen ATR-Mindestwert in Kursnotierung (``min_atr_price``, Default 1.00
   = Original-Default 100 Punkte * angenommene Point-Groesse 0.01 fuer
   XAUUSD). Exakt die im Quick-Check als unbegruendete Magic Number
   bemaengelte Schwelle — hier nur explizit statt implizit ueber `_Point`.
4. **Session-Filter interpretiert ``InpStartHour``/``InpEndHour`` direkt
   als UTC-Stunden** statt als unbekannte MT5-Broker-Serverzeit (im
   Original serverabhaengig, oft UTC+2/+3, hier nicht rekonstruierbar).
   Halb-offenes Fenster mit Ueber-Mitternacht-Unterstuetzung wie im
   Original uebernommen.
5. **Money-Management delegiert an die Engine.** ``core/backtester.py``
   sized ueber ``risk.risk_per_trade_pct`` (Config, Equity-basiert, analog
   ``InpRiskPerTradePct``) und rundet wie im Original per Volume-Step nach
   UNTEN; ``Signal.risk_pct`` wird nur informativ mitgefuehrt (Engine-
   Konvention in diesem Projekt, s. andere ``analyze_*``-Strategien).
   ``CalculateVolume()``s Ablehnen bei Volumen < ``SYMBOL_VOLUME_MIN``
   entspricht der globalen ``volume_min``-Clamp/Skip-Logik der Engine.
6. **``InpOnePositionOnly`` / Magic-Number-Filter** entsprechen der
   Engine-Config ``risk.max_concurrent: 1`` (s. ``configs/
   analyze_e241bb189fa2.yaml``) statt einer eigenen Positions-Abfrage in
   der Strategie — die Engine fuehrt ohnehin nur EIN Strategie-Portfolio
   pro Backtest-Lauf; "Magic Number" hat hier keine Entsprechung.
7. **H4-Trendfilter exakt wie im Original** (Quick-Check Finding
   "Trendfilter simpel"): Preis > EMA50(H4) UND EMA50(H4) steigt ueber die
   letzten 2 geschlossenen H4-Bars (bzw. umgekehrt fuer Short) — bewusst
   OHNE Mindestabstand/Slope-Schwellenwert nachgeruestet, um die
   Original-Schwaeche (anfaellig bei flachem EMA) unveraendert zu testen.
8. **Kein hartes Max-Drawdown-/Tagesverlust-Cap** — wie im Original
   (Quick-Check Finding 3) bewusst NICHT nachgeruestet; Engine-Config setzt
   ``daily_loss_halt_pct: 0`` (aus), analog zum Original ohne Kapitalschutz
   ausserhalb von Risiko-pro-Trade.
"""
from __future__ import annotations

import pandas as pd

from .base import Signal, Strategy, atr as _atr, ema as _ema


class AnalyzeXauTrendPullbackAtr(Strategy):
    name = "analyze_e241bb189fa2"
    required_timeframes = ["M15", "H4"]

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.tf_entry = p.get("tf_entry", "M15")
        self.tf_trend = p.get("tf_trend", "H4")

        # -- Trendfilter (H4) ----------------------------------------------------
        self.trend_ema_period = int(p.get("trend_ema_period", 50))

        # -- Entry (M15) -----------------------------------------------------------
        self.fast_ema_period = int(p.get("fast_ema_period", 20))
        self.atr_period = int(p.get("atr_period", 14))

        # -- Risiko/Ziele (ATR-basiert, Original InpSL_ATR_Multiplier/InpRiskReward) --
        self.sl_atr_mult = float(p.get("sl_atr_mult", 1.50))
        self.rr = float(p.get("risk_reward", 2.00))
        self.structure_buffer_atr = float(p.get("structure_buffer_atr", 0.20))
        self.min_atr_price = float(p.get("min_atr_price", 1.00))  # s. Docstring Punkt 3

        # -- Session (s. Docstring Punkt 4) -----------------------------------------
        self.use_session_filter = bool(p.get("use_session_filter", True))
        self.start_hour = int(p.get("start_hour", 8))
        self.end_hour = int(p.get("end_hour", 22))

        # -- Richtung / Risiko (informativ, Sizing s. Docstring Punkt 5) -----------
        self.allow_long = bool(p.get("allow_long", True))
        self.allow_short = bool(p.get("allow_short", True))
        self.risk_pct = float(p.get("risk_pct", 0.50))

        self._window_entry = max(self.fast_ema_period, self.atr_period) * 3 + 30
        self._window_trend = self.trend_ema_period * 4 + 20
        # Trend-Regime aendert sich nur, wenn eine neue H4-Bar schliesst —
        # Cache-Key = Laenge der sichtbaren H4-Serie (Performance, analog
        # anderen MTF-Portierungen in diesem Projekt).
        self._trend_cache: tuple[int, dict | None] = (-1, None)

    @staticmethod
    def _in_hours(hour: int, start: int, end: int) -> bool:
        if start == end:
            return True
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _trend_state_calc(self, win: pd.DataFrame) -> dict | None:
        if len(win) < self.trend_ema_period + 5:
            return None
        ema_t = _ema(win["close"], self.trend_ema_period)
        e1, e2 = ema_t.iloc[-1], ema_t.iloc[-2]
        if pd.isna(e1) or pd.isna(e2):
            return None
        close1, e1, e2 = float(win["close"].iloc[-1]), float(e1), float(e2)
        if close1 > e1 and e1 > e2:
            return {"direction": 1}
        if close1 < e1 and e1 < e2:
            return {"direction": -1}
        return None

    def _trend_state_for(self, trend_view: pd.DataFrame) -> dict | None:
        length = len(trend_view)
        cached_len, cached_state = self._trend_cache
        if cached_len == length:
            return cached_state
        win = trend_view.iloc[-self._window_trend:] if length > self._window_trend else trend_view
        state = self._trend_state_calc(win)
        self._trend_cache = (length, state)
        return state

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        m15 = bars[self.tf_entry]
        if i < self._window_entry:
            return None
        ts = m15.index[i]

        if self.use_session_filter and not self._in_hours(int(ts.hour), self.start_hour, self.end_hour):
            return None

        trend = self._trend_state_for(bars[self.tf_trend])
        if trend is None:
            return None
        direction = trend["direction"]
        if direction > 0 and not self.allow_long:
            return None
        if direction < 0 and not self.allow_short:
            return None

        win = m15.iloc[max(0, i + 1 - self._window_entry): i + 1]
        entry_ema = _ema(win["close"], self.fast_ema_period)
        atr_series = _atr(win, self.atr_period)
        if pd.isna(entry_ema.iloc[-1]) or pd.isna(entry_ema.iloc[-2]) or pd.isna(atr_series.iloc[-1]):
            return None

        c1 = win.iloc[-1]  # letzte geschlossene M15-Kerze (Original "shift 1")
        c2 = win.iloc[-2]  # Kerze davor, Pullback-Touch (Original "shift 2")
        ema1, ema2 = float(entry_ema.iloc[-1]), float(entry_ema.iloc[-2])
        cur_atr = float(atr_series.iloc[-1])
        if not (cur_atr > 0) or cur_atr < self.min_atr_price:
            return None

        cur_close = float(c1["close"])

        if direction > 0:
            touched = c2["low"] <= ema2 and c2["close"] >= ema2
            confirmed = c1["close"] > c1["open"] and c1["close"] > c2["high"] and cur_close > ema1
            if not (touched and confirmed):
                return None
            atr_stop = cur_close - cur_atr * self.sl_atr_mult
            structure_stop = float(c2["low"]) - self.structure_buffer_atr * cur_atr
            sl = min(atr_stop, structure_stop)
            risk_distance = cur_close - sl
        else:
            touched = c2["high"] >= ema2 and c2["close"] <= ema2
            confirmed = c1["close"] < c1["open"] and c1["close"] < c2["low"] and cur_close < ema1
            if not (touched and confirmed):
                return None
            atr_stop = cur_close + cur_atr * self.sl_atr_mult
            structure_stop = float(c2["high"]) + self.structure_buffer_atr * cur_atr
            sl = max(atr_stop, structure_stop)
            risk_distance = sl - cur_close

        if not (risk_distance > 0):
            return None
        tp = cur_close + direction * risk_distance * self.rr

        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "atr": cur_atr, "sl_atr_mult": self.sl_atr_mult,
                "structure_stop": structure_stop, "atr_stop": atr_stop,
                "trend_direction": direction,
            },
            expires_bars=0,
        )
