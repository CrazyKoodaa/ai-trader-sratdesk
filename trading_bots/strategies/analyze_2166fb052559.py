"""strategies/analyze_2166fb052559.py — Portierung von "XAU Velocity External
Validation F7" (MQL5/MT5-EA, extern eingereicht, Snippet bricht in
``NormalizeVolume()`` ab; s. reports/analyze_2166fb052559.md fuer den
Vorab-Review inkl. Triage-Ergebnis).

Handelsidee (Original): Multi-Timeframe-Trendfolge/Retracement auf XAUUSD
(H4-Kontext, H1-Trend, M15-Setup, M5-Entry). Ein Impuls-Candle ("Expansion")
wird per Range-Multiple + Body% erkannt, danach muss ein Pullback in ein
Retrace-Band folgen. Ein additiver "Quality-Score" (Regime/HTF/Expansion/
Struktur/Retrace/Session/Richtung) entscheidet — mit einer je nach
Expansions-Staerke ADAPTIVEN Mindestschwelle (schwache Impulse brauchen einen
sehr hohen Score, starke Impulse kommen mit wenig Score aus) — ob final
gehandelt wird. Management: TP bei 8.5R, ab +3.25R Profit wird der SL auf
+1.0R nachgezogen ("F7"-Preset); Session-Filter (Asia+London aktiv, NY per
Default aus); Challenge-/FTMO-Regeln fuer diesen "External Validation"-Build
bewusst deaktiviert.

WICHTIGE ANNAHMEN / VEREINFACHUNGEN gegenueber dem Original
=============================================================
1. **Kein separates "Lock bei +3.25R -> SL auf +1.0R, TP bleibt bei 8.5R"**
   — die Engine (core/backtester.py) kennt keinen per-Bar-Hook, der eine
   offene Position auf ein beliebiges R-Niveau zieht; sie kennt nur (a)
   festes SL/TP oder (b) "TP-Beruehrung schliesst nicht, sondern zieht SL
   auf TP-Niveau und startet ab dort einen ATR-Chandelier-Trail"
   (``tp_converts_to_trail``, s. S9/S11/S16/S21/analyze_98946a741100 in
   diesem Projekt — etabliertes Muster fuer genau dieses Problem). Diese
   Portierung nutzt daher: ``take_profit = entry + LOCK_TRIGGER_R * risk``
   (3.25R statt 8.5R) mit ``tp_converts_to_trail=True`` + ATR-Trail
   (``trail_atr_mult``, Parameter). Zwei reale Abweichungen vom Original:
   (a) der SL wird bei Konversion auf das VOLLE 3.25R-Niveau gezogen, nicht
   auf die im Original vorgesehenen 1.0R — konservativer als das Original;
   (b) es gibt danach KEIN hartes 8.5R-Cap mehr, sondern einen offenen
   ATR-Trail — im Trend potenziell mehr als 8.5R, in schnellen Ruecksetzern
   ggf. weniger. Der TP_R=8.5-Parameter aus dem Original wird NICHT als
   hartes Ziel verwendet, nur ``LOCK_TRIGGER_R``/``LOCK_SL_R`` als
   Namensgeber der Trigger-Logik.
2. **M5-Entry-TF NICHT portiert** — das Snippet bricht ab, BEVOR die
   eigentliche M5-Ausloese-Logik (Order-Platzierung, Money-Management,
   Erfolgspruefung) sichtbar wird; es ist nicht erkennbar, was M5 zusaetzlich
   zum M15-Setup beitraegt (reiner Timing-Feinschliff vs. eigene Filter).
   Diese Portierung wertet Expansion + Retracement direkt auf M15
   (``TF_SETUP``) aus und tradet auf M15-Bar-Schluss — ein 3-TF- statt
   4-TF-System (H4/H1/M15). Das entspricht dem MTF-Muster dieses Projekts
   (s. S16) und ist die einzig belastbare Wahl angesichts der fehlenden
   M5-Quelle, aendert aber die Entry-Praezision gegenueber dem Original.
3. **Score-Formel ist eine REKONSTRUKTION, keine Portierung** — das
   Snippet enthaelt zwar alle Schwellwerte (SCORE_*, *_BONUS, *_MIN) und
   Kommentare zur Philosophie ("schwacher Impuls braucht hohen Score,
   starker Impuls braucht wenig"), aber NICHT die tatsaechliche
   Punkteformel (bricht vor der Score-Berechnung ab). Diese Portierung
   baut einen additiven Score aus den dokumentierten Komponenten
   (Regime/HTF/Expansion/Struktur/Retrace/Session/Richtung), kalibriert
   so, dass die genannten SCORE_*-Schwellen (72/78/84/88/92) im erreichbaren
   Bereich liegen. Die Zuordnung "Required-Score haengt von der
   Expansions-Guete ab" wird ueber die Enum-Namen (STANDARD/STRONG/ELITE)
   plausibel rekonstruiert: exp < QUALITY(1.50) -> SCORE_EXCEPTIONAL(92)
   noetig; < STRONG(1.80) -> SCORE_STANDARD_MIN(84); < ELITE(2.20) ->
   SCORE_STRONG_MIN(78); sonst SCORE_ELITE_MIN(72). Immer zusaetzlich
   SCORE_ABSOLUTE_MIN(72) als Boden. Das ist plausibel, aber NICHT
   verifizierbar am Original.
4. **Setup-Erkennung ist zustandslos aus dem Fenster rekonstruiert** (wie
   das MACD-Cross-Arming in analyze_98946a741100), statt eines im Original
   vermutlich persistenten ``ExpansionSetup``-State-Objekts: pro Bar wird
   rueckwaerts geprueft, ob vor ``RETRACE_MAX_BARS+1`` Bars ein Impuls lag
   und der aktuelle Pullback im Retrace-Band liegt. Bevorzugt wird das
   juengste (Age-0-)Setup vor einem Age-1-Setup, wie im Original-Kommentar
   ("age 0 normal, age>0 braucht mehr Guete") beschrieben.
5. **ATR-Bezug der Regime-/Expansion-/Retrace-Schwellen**: das Original
   nennt nur "ATR" ohne TF-Zuordnung fuer Expansion/Retrace-Messungen.
   Diese Portierung nimmt ATR(M15, ``ATR_PERIOD``) fuer alles, was auf
   ``TF_SETUP`` gemessen wird (Expansion/Retrace/Invalidierung/SL-Puffer),
   und ATR(H4)/ATR(H1) fuer die jeweilige Regime-Ebene.
6. **Struktureller Stop-Loss**: im Original nicht sichtbar (Snippet bricht
   vor der SL-Berechnung ab). Diese Portierung setzt den SL knapp hinter
   das Pullback-Extremum (niedrigstes Low bzw. hoechstes High seit dem
   Impuls) minus/plus ``sl_buffer_atr * ATR(M15)`` — eine plausible,
   aber frei gewaehlte Naeherung, die den Score-Router mit realistischem
   Risk-Multiple fuettert.
7. **Session-Uhrzeiten** (Asia/London/NY) sind im Snippet nur als
   Bool-Flags + Score-Boni vorhanden, NICHT mit konkreten UTC-Stunden.
   Diese Portierung nutzt projektuebliche Naeherungen: Asia 00-07 UTC,
   London 07-15 UTC, New York 13-21 UTC (per Default deaktiviert, wie im
   Original ``TradeNewYork=false``).
8. **Nicht portiert** (Snippet zeigt nur Konstanten/Enums, keine Logik
   dafuer, oder Engine bietet keinen Haken): FVG-Erkennung (``fvg_present``/
   ``inside_fvg`` sind im Original-Struct vorhanden, aber keine Schwelle
   dafuer sichtbar), ``MaxSpreadPoints`` (Engine hat kein Spread-Bar-
   Signal, Kosten laufen global ueber ``core/backtester.py``-Kostenmodell),
   ``MaxEntriesPerHour`` (bei ``MAX_POSITIONS=1`` -> ``risk.max_concurrent``
   in der Config kaum wirksam zusaetzlich), Challenge-/FTMO-Tagesstopp
   (im Original fuer diesen Build ohnehin deaktiviert — deckt sich mit dem
   Quick-Check-Befund, dass das eigentliche Risikomanagement hier gar
   nicht mitgetestet wird).
9. Wie im Quick-Check festgehalten: die vielen Schwellen/Boni sind laut
   Original-Kommentaren aus einem winzigen Sample (teils "nur 15
   observations") abgeleitet — ein Overfitting-Verdacht, den diese
   Portierung NICHT aufloest, nur strukturell abbildet. ``configs/
   analyze_2166fb052559.yaml`` variiert daher bewusst nur 3 grobe
   Parameter statt die volle Schwellen-Dichte zu erhalten.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, adx as _adx, atr as _atr, ema as _ema


class AnalyzeXauVelocityF7(Strategy):
    name = "analyze_2166fb052559"
    required_timeframes = ["M15", "H1", "H4"]

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")

        # -- Timeframes ------------------------------------------------------
        self.tf_setup = p.get("tf_setup", "M15")
        self.tf_trend = p.get("tf_trend", "H1")
        self.tf_context = p.get("tf_context", "H4")

        # -- Regime (Original: V2.2-Schwellen, s. Docstring) ------------------
        self.ema_fast = int(p.get("ema_fast", 20))
        self.ema_mid = int(p.get("ema_mid", 50))
        self.ema_slow = int(p.get("ema_slow", 200))
        self.adx_len = int(p.get("adx_len", 14))
        self.atr_len = int(p.get("atr_len", 14))  # ATR_PERIOD im Original

        self.min_trend_adx = float(p.get("min_trend_adx", 20.0))
        self.strong_trend_adx = float(p.get("strong_trend_adx", 27.0))
        self.very_strong_trend_adx = float(p.get("very_strong_trend_adx", 34.0))
        self.min_h1_ema_sep_atr = float(p.get("min_h1_ema_separation_atr", 0.16))
        self.strong_h1_ema_sep_atr = float(p.get("strong_h1_ema_separation_atr", 0.25))
        self.h4_slope_bars = int(p.get("h4_slope_bars", 3))
        self.min_h4_slope_atr = float(p.get("min_h4_slope_atr", 0.03))
        self.strong_h4_slope_atr = float(p.get("strong_h4_slope_atr", 0.08))

        # -- Expansion (M15) ---------------------------------------------------
        self.expansion_lookback = int(p.get("expansion_lookback", 8))
        self.detect_min_expansion_mult = float(p.get("detect_min_expansion_mult", 1.35))
        self.detect_min_body_pct = float(p.get("detect_min_body_pct", 0.60))
        self.quality_expansion_mult = float(p.get("quality_expansion_mult", 1.50))
        self.strong_expansion_mult = float(p.get("strong_expansion_mult", 1.80))
        self.elite_expansion_mult = float(p.get("elite_expansion_mult", 2.20))
        self.quality_body_pct = float(p.get("quality_body_pct", 0.68))
        self.strong_body_pct = float(p.get("strong_body_pct", 0.75))
        self.elite_body_pct = float(p.get("elite_body_pct", 0.82))

        # -- Retracement ---------------------------------------------------------
        self.retrace_min_pct = float(p.get("retrace_min_pct", 0.12))
        self.retrace_max_pct = float(p.get("retrace_max_pct", 0.62))
        self.retrace_acceptable_min = float(p.get("retrace_acceptable_min", 0.18))
        self.retrace_acceptable_max = float(p.get("retrace_acceptable_max", 0.55))
        self.retrace_ideal_min = float(p.get("retrace_ideal_min", 0.25))
        self.retrace_ideal_max = float(p.get("retrace_ideal_max", 0.48))
        self.retrace_elite_min = float(p.get("retrace_elite_min", 0.32))
        self.retrace_elite_max = float(p.get("retrace_elite_max", 0.42))
        self.retrace_max_bars = int(p.get("retrace_max_bars", 1))
        self.delayed_setup_from_bar = int(p.get("delayed_setup_from_bar", 1))
        self.setup_invalidation_atr = float(p.get("setup_invalidation_atr", 0.12))

        # -- Score-Router (Rekonstruktion, s. Docstring Punkt 3) ---------------
        self.score_absolute_min = float(p.get("score_absolute_min", 72))
        self.score_standard_min = float(p.get("score_standard_min", 84))
        self.score_strong_min = float(p.get("score_strong_min", 78))
        self.score_elite_min = float(p.get("score_elite_min", 72))
        self.score_exceptional = float(p.get("score_exceptional", 92))
        self.delayed_setup_min_score = float(p.get("delayed_setup_min_score", 88))
        self.delayed_setup_min_expansion = float(p.get("delayed_setup_min_expansion", 1.60))
        self.delayed_setup_min_body = float(p.get("delayed_setup_min_body", 0.70))

        # -- Session -------------------------------------------------------------
        self.trade_asia = bool(p.get("trade_asia", True))
        self.trade_london = bool(p.get("trade_london", True))
        self.trade_newyork = bool(p.get("trade_newyork", False))
        self.asia_score_bonus = float(p.get("asia_score_bonus", 9))
        self.london_score_bonus = float(p.get("london_score_bonus", 6))
        self.newyork_score_bonus = float(p.get("newyork_score_bonus", 2))
        self.london_min_score = float(p.get("london_min_score", 76))
        self.london_min_expansion = float(p.get("london_min_expansion", 1.45))
        self.friday_stop_hour = int(p.get("friday_stop_hour", 20))

        # -- Richtung --------------------------------------------------------------
        self.sell_quality_bonus = float(p.get("sell_quality_bonus", 2))
        self.buy_quality_bonus = float(p.get("buy_quality_bonus", 0))
        self.allow_longs = bool(p.get("allow_longs", True))
        self.allow_shorts = bool(p.get("allow_shorts", True))

        # -- Risk / Management (F7-Preset, s. Docstring Punkt 1) ----------------
        self.sl_buffer_atr = float(p.get("sl_buffer_atr", 0.25))
        self.lock_trigger_r = float(p.get("lock_trigger_r", 3.25))  # -> Signal.take_profit
        self.trail_atr_mult = float(p.get("trail_atr_mult", 2.5))
        self.min_minutes_between_entries = int(p.get("min_minutes_between_entries", 15))
        self.risk_pct = float(p.get("risk_pct", 0.007))  # Original RiskPct=0.7%

        self._window_m15 = self.expansion_lookback + self.retrace_max_bars + self.atr_len * 3 + 10
        self._window_h1 = max(self.ema_slow * 3, self.adx_len * 5) + 10
        self._window_h4 = max(self.h4_slope_bars + self.atr_len * 3, 30) + 10
        self._last_entry_time: pd.Timestamp | None = None

    # -- Session-Helfer --------------------------------------------------------
    @staticmethod
    def _session_for_hour(h: int) -> str:
        if 0 <= h < 7:
            return "asia"
        if 7 <= h < 15:
            return "london"
        if 13 <= h < 21:
            return "newyork"
        return "off"

    # -- Regime (H1 + H4) --------------------------------------------------------
    def _regime(self, h1: pd.DataFrame, h4: pd.DataFrame) -> dict | None:
        if len(h1) < self._window_h1 - 5 or len(h4) < self._window_h4 - 5:
            return None
        close_h1 = h1["close"]
        ema_f = _ema(close_h1, self.ema_fast)
        ema_s = _ema(close_h1, self.ema_slow)
        adx_h1 = _adx(h1, self.adx_len)["adx"]
        atr_h1 = _atr(h1, self.atr_len)
        vals = (ema_f.iloc[-1], ema_s.iloc[-1], adx_h1.iloc[-1], atr_h1.iloc[-1])
        if any(pd.isna(v) for v in vals) or not (float(atr_h1.iloc[-1]) > 0):
            return None
        ema_f_v, ema_s_v, adx_v, atr1_v = (float(v) for v in vals)

        trend_dir = 1 if ema_f_v > ema_s_v else (-1 if ema_f_v < ema_s_v else 0)
        if trend_dir == 0:
            return None
        h1_sep_atr = abs(ema_f_v - ema_s_v) / atr1_v
        if adx_v < self.min_trend_adx or h1_sep_atr < self.min_h1_ema_sep_atr:
            return None

        close_h4 = h4["close"]
        ema_h4 = _ema(close_h4, self.ema_mid)
        atr_h4 = _atr(h4, self.atr_len)
        if len(ema_h4) <= self.h4_slope_bars or pd.isna(ema_h4.iloc[-1 - self.h4_slope_bars]):
            return None
        atr4_v = float(atr_h4.iloc[-1])
        if pd.isna(atr4_v) or not (atr4_v > 0):
            return None
        h4_slope_atr = (float(ema_h4.iloc[-1]) - float(ema_h4.iloc[-1 - self.h4_slope_bars])) / atr4_v
        # H4-Slope muss Richtung des H1-Trends bestaetigen (nicht dagegenlaufen)
        if trend_dir > 0 and h4_slope_atr < self.min_h4_slope_atr:
            return None
        if trend_dir < 0 and -h4_slope_atr < self.min_h4_slope_atr:
            return None

        score_regime = 15.0
        if adx_v >= self.strong_trend_adx:
            score_regime += 5.0
        if adx_v >= self.very_strong_trend_adx:
            score_regime += 5.0
        if h1_sep_atr >= self.strong_h1_ema_sep_atr:
            score_regime += 5.0

        score_htf = 10.0
        if abs(h4_slope_atr) >= self.strong_h4_slope_atr:
            score_htf += 5.0

        return {
            "direction": trend_dir, "adx": adx_v, "atr_h1": atr1_v,
            "h1_sep_atr": h1_sep_atr, "h4_slope_atr": h4_slope_atr,
            "score_regime": score_regime, "score_htf": score_htf,
        }

    # -- Expansion + Retracement (M15, zustandslos rekonstruiert) --------------
    def _find_setup(self, m15: pd.DataFrame, direction: int) -> dict | None:
        n = len(m15)
        highs = m15["high"]
        lows = m15["low"]
        opens = m15["open"]
        closes = m15["close"]
        atr_series = _atr(m15, self.atr_len)
        cur_close = float(closes.iloc[-1])
        atr_now = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else float("nan")
        if pd.isna(atr_now) or not (atr_now > 0):
            return None

        for back in range(1, self.retrace_max_bars + 2):
            exp_pos = n - 1 - back
            if exp_pos - self.expansion_lookback < 0:
                continue
            exp_high = float(highs.iloc[exp_pos])
            exp_low = float(lows.iloc[exp_pos])
            exp_open = float(opens.iloc[exp_pos])
            exp_close = float(closes.iloc[exp_pos])
            exp_range = exp_high - exp_low
            if not (exp_range > 0):
                continue
            avg_range = float(
                (highs.iloc[exp_pos - self.expansion_lookback : exp_pos]
                 - lows.iloc[exp_pos - self.expansion_lookback : exp_pos]).mean()
            )
            if not (avg_range > 0):
                continue
            range_mult = exp_range / avg_range
            body_pct = abs(exp_close - exp_open) / exp_range
            if range_mult < self.detect_min_expansion_mult or body_pct < self.detect_min_body_pct:
                continue
            exp_dir = 1 if exp_close > exp_open else -1
            if exp_dir != direction:
                continue

            age = back - 1
            if direction > 0:
                retrace_pct = (exp_high - cur_close) / exp_range
                invalid = cur_close < exp_open - self.setup_invalidation_atr * atr_now
            else:
                retrace_pct = (cur_close - exp_low) / exp_range
                invalid = cur_close > exp_open + self.setup_invalidation_atr * atr_now
            if invalid or not (self.retrace_min_pct <= retrace_pct <= self.retrace_max_pct):
                continue

            score_expansion = 15.0
            if range_mult >= self.strong_expansion_mult:
                score_expansion += 5.0
            if range_mult >= self.elite_expansion_mult:
                score_expansion += 5.0

            score_structure = 10.0
            if body_pct >= self.strong_body_pct:
                score_structure += 2.5
            if body_pct >= self.elite_body_pct:
                score_structure += 2.5

            score_retrace = 0.0
            if self.retrace_acceptable_min <= retrace_pct <= self.retrace_acceptable_max:
                score_retrace += 5.0
            if self.retrace_ideal_min <= retrace_pct <= self.retrace_ideal_max:
                score_retrace += 5.0
            if self.retrace_elite_min <= retrace_pct <= self.retrace_elite_max:
                score_retrace += 5.0

            # Stop hinter dem Pullback-Extremum seit dem Impuls (s. Docstring Punkt 6)
            since = slice(exp_pos + 1, n)
            if direction > 0:
                extreme = float(lows.iloc[since].min())
                sl = extreme - self.sl_buffer_atr * atr_now
            else:
                extreme = float(highs.iloc[since].max())
                sl = extreme + self.sl_buffer_atr * atr_now

            return {
                "age": age, "range_mult": range_mult, "body_pct": body_pct,
                "retrace_pct": retrace_pct, "atr_m15": atr_now, "sl": sl,
                "score_expansion": score_expansion, "score_structure": score_structure,
                "score_retrace": score_retrace,
            }
        return None

    def _required_score(self, range_mult: float) -> float:
        if range_mult < self.quality_expansion_mult:
            req = self.score_exceptional
        elif range_mult < self.strong_expansion_mult:
            req = self.score_standard_min
        elif range_mult < self.elite_expansion_mult:
            req = self.score_strong_min
        else:
            req = self.score_elite_min
        return max(req, self.score_absolute_min)

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        m15 = bars[self.tf_setup]
        h1 = bars[self.tf_trend]
        h4 = bars[self.tf_context]
        if i < self._window_m15:
            return None
        ts = m15.index[i]

        if ts.dayofweek == 4 and ts.hour >= self.friday_stop_hour:
            return None
        session = self._session_for_hour(int(ts.hour))
        session_allowed = (
            (session == "asia" and self.trade_asia)
            or (session == "london" and self.trade_london)
            or (session == "newyork" and self.trade_newyork)
        )
        if not session_allowed:
            return None

        if self._last_entry_time is not None:
            if (ts - self._last_entry_time) < pd.Timedelta(minutes=self.min_minutes_between_entries):
                return None

        lo_m15 = max(0, i + 1 - self._window_m15)
        win_m15 = m15.iloc[lo_m15 : i + 1]
        h1_win = h1[h1.index <= ts]
        h4_win = h4[h4.index <= ts]

        regime = self._regime(h1_win, h4_win)
        if regime is None:
            return None
        direction = regime["direction"]
        if direction > 0 and not self.allow_longs:
            return None
        if direction < 0 and not self.allow_shorts:
            return None

        setup = self._find_setup(win_m15, direction)
        if setup is None:
            return None

        session_bonus = {
            "asia": self.asia_score_bonus, "london": self.london_score_bonus,
            "newyork": self.newyork_score_bonus,
        }.get(session, 0.0)
        direction_bonus = self.sell_quality_bonus if direction < 0 else self.buy_quality_bonus

        score = (
            regime["score_regime"] + regime["score_htf"] + setup["score_expansion"]
            + setup["score_structure"] + setup["score_retrace"] + session_bonus + direction_bonus
        )

        required_score = self._required_score(setup["range_mult"])
        if setup["age"] >= self.delayed_setup_from_bar:
            required_score = max(required_score, self.delayed_setup_min_score)
            if (setup["range_mult"] < self.delayed_setup_min_expansion
                    or setup["body_pct"] < self.delayed_setup_min_body):
                return None
        if session == "london":
            if score < self.london_min_score or setup["range_mult"] < self.london_min_expansion:
                return None
        if score < required_score:
            return None

        c = float(win_m15["close"].iloc[-1])
        sl = float(setup["sl"])
        risk_distance = abs(c - sl)
        if not (risk_distance > 0):
            return None
        tp = c + direction * self.lock_trigger_r * risk_distance

        self._last_entry_time = ts
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "score": score, "required_score": required_score,
                "session": session, "setup_age_bars": setup["age"],
                "expansion_multiple": setup["range_mult"], "body_pct": setup["body_pct"],
                "retrace_pct": setup["retrace_pct"], "adx": regime["adx"],
            },
            expires_bars=0,
        )
