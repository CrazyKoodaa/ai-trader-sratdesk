"""strategies/analyze_95443742cec6.py — Portierung von "XAU Velocity External
Validation F7" (MQL5/MT5-EA, extern eingereicht, VOLLSTAENDIGES Snippet ueber
alle drei Teile 1-3B). Dieselbe EA-Familie wie
``strategies/analyze_2166fb052559.py`` (dort brach das Snippet in
``NormalizeVolume()`` ab, deshalb dezidiert verworfen — s.
``reports/analyze_2166fb052559.md``) und ``strategies/analyze_a3d5ea031833.py``
(vollstaendiges Snippet, aber Management dort hart auf F7 eingefroren wie im
Original-Build). **Unterschied zu ``analyze_a3d5ea031833``**: dieser Port
bildet die 8 benannten FTMO-Management-Presets (F0-F7, ``ManagementMode``-Enum
im Original) NICHT verschmolzen ab, sondern als expliziten Auswahl-Parameter
``risk_profile`` — jedes Profil bleibt seine eigene, in sich konsistente
TP/Lock-Kombination (s. Tabelle unten), keine freie Einzel-Justierung von
TP-R/Lock-Trigger-R quer durch die Presets.

Handelsidee (Original): 4-TF-Trendfolge/Retracement auf XAUUSD
(H4-Kontext-Slope, H1-Trend via 3-EMA-Alignment(20/50/200), M15-ADX/DI-Regime
+ weiche Struktur-Bestaetigung, M5-Impuls("Expansion")-Erkennung + Pullback-
Retracement + FVG). Ein additiver Quality-Score (Regime/HTF/Expansion/
Struktur/Retrace/Session/Richtung) wird gegen eine je nach roher Impuls-
Guete ADAPTIVE Mindestschwelle geprueft (ClassifyRawQuality -> STANDARD/
STRONG/ELITE/REJECT -> required_score 84/78/72/92); eine "Weak Raw Quality
Exception" laesst sogar REJECT-Signale bei Score>=92 als STANDARD durch.
Session: Asia(0-7 UTC)+London(7-13 UTC) aktiv, NewYork(13-21 UTC) per Default
aus; Challenge-/FTMO-Tagesstopp fuer diesen "External Validation"-Build
bewusst deaktiviert (kein Kapitalschutz ausserhalb von RiskPct/Trade).

FTMO-Management-Presets (``ManagementMode``-Enum, 1:1 aus ``SelectedTPR``/
``SelectedLockTriggerR``/``SelectedLockSLR`` im Original abgeleitet):

| Profil | TP-Ziel | Lock-Trigger | Lock-SL  | Bemerkung              |
|--------|---------|-------------|----------|------------------------|
| F0     | 8.0R    | +2.75R      | +0.75R   |                        |
| F1     | 8.0R    | +2.75R      | +1.00R   |                        |
| F2     | 8.0R    | +3.00R      | +0.75R   |                        |
| F3     | 8.0R    | +3.00R      | +1.00R   | Original "current benchmark" |
| F4     | 8.0R    | +3.25R      | +0.75R   |                        |
| F5     | 8.0R    | +3.25R      | +1.00R   |                        |
| F6     | 8.5R    | +3.00R      | +1.00R   |                        |
| F7     | 8.5R    | +3.25R      | +1.00R   | Original-Default-Build (eingefroren) |

WICHTIGE ANNAHMEN / VEREINFACHUNGEN gegenueber dem Original
=============================================================
1. **M5-Entry-TF wird NICHT separat gefuehrt — M15 uebernimmt die Rolle von
   TF_SETUP UND TF_ENTRY.** Das Original trennt: H4-Kontext / H1-Trend /
   M15 (nur ADX/DI + weiche Struktur) / M5 (Expansion + Retracement +
   Ausfuehrung, mit ``RETRACE_MAX_BARS=1``). Zwei Gruende gegen eine 1:1-
   M5-Portierung: (a) ``RETRACE_MAX_BARS=1`` bedeutet, dass ein Setup im
   Original bereits einen M5-Bar-Wechsel spaeter automatisch expired
   (``SetupAgeBars()>=RETRACE_MAX_BARS`` in ``ProcessNewM5Bar``) — die
   eigentliche Retracement-Pruefung laeuft dort im Original PRO TICK
   innerhalb derselben, noch offenen M5-Kerze. Ein Bar-Close-Engine (SPEC
   §4.1: ``on_bar`` nur auf geschlossenen Bars) kann diese Intrabar-Tick-
   Granularitaet grundsaetzlich nicht abbilden. (b) M5-Vollhistorie fuer
   XAUUSD umfasst hier >500k Bars; eine treue Naeherung haette pro Bar
   ADX/EMA(200) auf H1 UND H4 zu erfordern — ohne Zwischenspeicherung waere
   Vorab-Triage UND volle WFO nicht in vertretbarer Zeit lauffaehig. Diese
   Portierung nutzt Caching (``_h1_state_for``/``_h4_state_for``) auf
   M15-Kadenz statt M5. Effekt: das effektive ``EXPANSION_LOOKBACK``-Fenster
   ist ~3x so lang in Wall-Clock-Zeit wie im Original (8xM15 statt 8xM5).
2. **Kein "Lock bei +Trigger-R -> SL fix auf +Lock-SL-R, TP bleibt hart bei
   TP-Ziel-R"** — die Engine (core/backtester.py) kennt keinen Per-Bar-Hook,
   der SL auf ein beliebiges R-Niveau zieht UND dort stehen bleibt; sie
   kennt nur (a) festes SL/TP oder (b) ``tp_converts_to_trail``: TP-
   Beruehrung schliesst nicht, sondern zieht SL auf TP-Niveau und startet
   einen ATR-Chandelier-Trail (etabliertes Projekt-Muster, s. S9/S11/S16/
   S21 sowie beide Schwester-Ports derselben EA-Familie). Diese Portierung
   nutzt daher je Profil ``take_profit = entry + lock_trigger_r(Profil) *
   risk`` mit ``tp_converts_to_trail=True`` + ATR-Trail (Parameter
   ``trail_atr_mult``). Zwei reale Abweichungen je Profil: (a) der SL wird
   bei Konversion auf das VOLLE Lock-Trigger-R-Niveau gezogen statt der im
   Original vorgesehenen (niedrigeren) Lock-SL-R-Marke — konservativer als
   das Original, ``lock_sl_r`` selbst fliesst NICHT in die Engine ein
   (nur dokumentarisch in der Profiltabelle oben); (b) danach folgt ein
   OFFENER ATR-Trail statt eines harten TP-Ziel-R-Caps — im Trend
   potenziell > TP-Ziel-R, bei schnellem Ruecksetzer ggf. weniger. Das
   ``tp_target_r`` je Profil (8.0/8.5) wird NICHT als hartes Ziel verwendet.
3. **Score-Formel und Quality-Router sind eine ECHTE Portierung** (komplette
   Formel im Original sichtbar: ``ExpansionScoreV23``, ``RetraceScoreV23``,
   ``ClassifyRawQuality``, ``QualityRouter`` inkl. "Weak Raw Quality
   Exception"), 1:1 abgebildet — MIT EINER Ausnahme: der "Delayed Setup"-
   Zweig (``setup_age_bars>=1`` verlangt Score>=88 + Expansion>=1.60 +
   Body>=0.70) ist im Original bei ``RETRACE_MAX_BARS=1`` de-facto TOTER
   CODE (``SetupExpired()`` greift exakt bei ``age>=RETRACE_MAX_BARS``,
   sodass ``BuildRetraceSignal()`` nie mit Alter>=1 aufgerufen wird). Der
   Zweig bleibt hier dennoch implementiert (ueber ``retrace_max_bars`` als
   Parameter erreichbar), bei Original-Default-Werten inaktiv wie im
   Original.
4. **Regime-Check laeuft EINMAL, zur Entry-Bar** (nicht separat bei
   Impuls-Erkennung UND nochmal bei Retracement wie im Original
   ``DetectAndArmExpansion`` + ``SetupRegimeStillValid``) — H1/H4 aendern
   sich innerhalb weniger M15-Bars praktisch nie, daher wird die
   Doppel-Pruefung auf eine zusammengefasst.
5. **ATR-Bezug**: ``atr_len`` (=ATR_PERIOD, einheitlich 14) wird je TF neu
   berechnet (H1/H4 fuer Separation/Slope, M15 fuer Expansion/Retrace/SL/
   Invalidierung) — wie im Original ein einziger globaler Parameter ohne
   TF-Differenzierung. Der SL-Puffer (``sl_buffer_atr=0.10``) und der
   Invalidierungs-Puffer (``setup_invalidation_atr=0.12``) sind im Original
   ZWEI VERSCHIEDENE, unabhaengige Konstanten — beide werden hier getrennt
   gefuehrt.
6. **FVG-Erkennung** (3-Kerzen-Imbalance zwischen Expansionskerze und der
   Kerze 2 Bars davor) wird 1:1 portiert (kleiner additiver Score-Bonus: +1
   vorhanden, +2 wenn aktueller Kurs im Gap liegt).
7. **Session-Uhrzeiten** exakt aus dem Original (``CurrentSession()``):
   Asia 00-07 UTC, London 07-13 UTC, NewYork 13-21 UTC (per Default aus).
8. **Nicht portiert** (Engine bietet keinen Haken bzw. irrelevant fuer
   Bar-Close-Semantik): ``MaxSpreadPoints`` (Kostenmodell laeuft global
   ueber ``core/backtester.py``), ``MaxEntriesPerHour`` (bei
   ``MAX_POSITIONS=1`` kaum zusaetzlich wirksam neben
   ``risk.max_concurrent``), FTMO-Challenge-Tagesstopp (im Original fuer
   diesen Build ohnehin deaktiviert).
9. **Overfitting-Verdacht (Quick-Check-Finding, unveraendert)**: die dichte
   Schwellenlandschaft (ADX 20/23/27/34, Body 0.60/0.68/0.75/0.82, Score-
   Boni 8/5/2, "Weak Raw Quality Exception" bei Score>=92) stammt laut
   Original-Kommentaren aus einem winzigen Sample ("V2.2 zeigte X"). Die 8
   Management-Presets selbst sind dagegen benannte, saubere FTMO-
   Kombinationen (kein Overfitting-Verdacht) — deshalb werden sie hier als
   ``risk_profile``-Auswahl behandelt statt als weitere freie Score-
   Parameter zu verschmelzen.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, adx as _adx, atr as _atr, ema as _ema


# FTMO-Management-Presets (ManagementMode-Enum im Original, s. Docstring-
# Tabelle). ``lock_sl_r`` ist rein dokumentarisch (s. Annahme 2) — die
# Engine kennt keinen fixen Post-Trigger-SL, nur tp_converts_to_trail.
_RISK_PROFILES: dict[str, dict[str, float]] = {
    "F0": {"tp_target_r": 8.0, "lock_trigger_r": 2.75, "lock_sl_r": 0.75},
    "F1": {"tp_target_r": 8.0, "lock_trigger_r": 2.75, "lock_sl_r": 1.00},
    "F2": {"tp_target_r": 8.0, "lock_trigger_r": 3.00, "lock_sl_r": 0.75},
    "F3": {"tp_target_r": 8.0, "lock_trigger_r": 3.00, "lock_sl_r": 1.00},
    "F4": {"tp_target_r": 8.0, "lock_trigger_r": 3.25, "lock_sl_r": 0.75},
    "F5": {"tp_target_r": 8.0, "lock_trigger_r": 3.25, "lock_sl_r": 1.00},
    "F6": {"tp_target_r": 8.5, "lock_trigger_r": 3.00, "lock_sl_r": 1.00},
    "F7": {"tp_target_r": 8.5, "lock_trigger_r": 3.25, "lock_sl_r": 1.00},
}


class AnalyzeXauVelocityF7Profiles(Strategy):
    name = "analyze_95443742cec6"
    required_timeframes = ["M15", "H1", "H4"]

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")

        # -- Risk-Profil (FTMO F0-F7, s. Docstring-Tabelle) --------------------
        profile_key = str(p.get("risk_profile", "F7")).strip().upper()
        if profile_key not in _RISK_PROFILES:
            raise ValueError(
                f"Unbekanntes risk_profile={profile_key!r}, erwartet eines von "
                f"{sorted(_RISK_PROFILES)}"
            )
        self.risk_profile = profile_key
        profile = _RISK_PROFILES[profile_key]
        self.tp_target_r = profile["tp_target_r"]        # dokumentarisch, s. Annahme 2
        self.lock_trigger_r = profile["lock_trigger_r"]  # -> Signal.take_profit (Trail-Trigger)
        self.lock_sl_r = profile["lock_sl_r"]             # dokumentarisch, s. Annahme 2

        # -- Timeframes (M5 nicht separat gefuehrt, s. Docstring Punkt 1) ----
        self.tf_setup = p.get("tf_setup", "M15")   # = Original TF_SETUP UND TF_ENTRY
        self.tf_trend = p.get("tf_trend", "H1")
        self.tf_context = p.get("tf_context", "H4")

        # -- Regime ------------------------------------------------------------
        self.ema_fast = int(p.get("ema_fast", 20))
        self.ema_mid = int(p.get("ema_mid", 50))
        self.ema_slow = int(p.get("ema_slow", 200))
        self.adx_len = int(p.get("adx_len", 14))
        self.atr_len = int(p.get("atr_len", 14))

        self.min_trend_adx = float(p.get("min_trend_adx", 20.0))
        self.strong_trend_adx = float(p.get("strong_trend_adx", 27.0))
        self.very_strong_trend_adx = float(p.get("very_strong_trend_adx", 34.0))
        self.min_h1_ema_sep_atr = float(p.get("min_h1_ema_separation_atr", 0.16))
        self.strong_h1_ema_sep_atr = float(p.get("strong_h1_ema_separation_atr", 0.25))
        self.h4_slope_bars = int(p.get("h4_slope_bars", 2))  # Original: shift1 vs shift3 = 2 Bars
        self.min_h4_slope_atr = float(p.get("min_h4_slope_atr", 0.03))
        self.strong_h4_slope_atr = float(p.get("strong_h4_slope_atr", 0.08))

        # -- Expansion -----------------------------------------------------------
        self.expansion_lookback = int(p.get("expansion_lookback", 8))
        self.detect_min_expansion_mult = float(p.get("detect_min_expansion_mult", 1.35))
        self.detect_min_body_pct = float(p.get("detect_min_body_pct", 0.60))
        self.quality_expansion_mult = float(p.get("quality_expansion_mult", 1.50))
        self.strong_expansion_mult = float(p.get("strong_expansion_mult", 1.80))
        self.elite_expansion_mult = float(p.get("elite_expansion_mult", 2.20))
        self.quality_body_pct = float(p.get("quality_body_pct", 0.68))
        self.strong_body_pct = float(p.get("strong_body_pct", 0.75))
        self.elite_body_pct = float(p.get("elite_body_pct", 0.82))

        # -- Retracement -----------------------------------------------------------
        self.retrace_min_pct = float(p.get("retrace_min_pct", 0.12))
        self.retrace_max_pct = float(p.get("retrace_max_pct", 0.62))
        self.retrace_acceptable_min = float(p.get("retrace_acceptable_min", 0.18))
        self.retrace_acceptable_max = float(p.get("retrace_acceptable_max", 0.55))
        self.retrace_ideal_min = float(p.get("retrace_ideal_min", 0.25))
        self.retrace_ideal_max = float(p.get("retrace_ideal_max", 0.48))
        self.retrace_elite_min = float(p.get("retrace_elite_min", 0.32))
        self.retrace_elite_max = float(p.get("retrace_elite_max", 0.42))
        self.retrace_max_bars = int(p.get("retrace_max_bars", 1))  # Original RETRACE_MAX_BARS
        self.delayed_setup_from_bar = int(p.get("delayed_setup_from_bar", 1))
        self.setup_invalidation_atr = float(p.get("setup_invalidation_atr", 0.12))

        # -- Score-Router (echte Portierung, s. Docstring Punkt 3) ---------------
        self.score_absolute_min = float(p.get("score_absolute_min", 72))
        self.score_standard_min = float(p.get("score_standard_min", 84))
        self.score_strong_min = float(p.get("score_strong_min", 78))
        self.score_elite_min = float(p.get("score_elite_min", 72))
        self.score_exceptional = float(p.get("score_exceptional", 92))
        self.delayed_setup_min_score = float(p.get("delayed_setup_min_score", 88))
        self.delayed_setup_min_expansion = float(p.get("delayed_setup_min_expansion", 1.60))
        self.delayed_setup_min_body = float(p.get("delayed_setup_min_body", 0.70))

        # -- Session (exakte Original-Uhrzeiten, s. Docstring Punkt 7) -----------
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

        # -- Risk / Management (Profil liefert tp_target_r/lock_trigger_r/
        # lock_sl_r oben; hier nur, was nicht profilabhaengig ist) ----------------
        self.sl_buffer_atr = float(p.get("sl_buffer_atr", 0.10))       # Original: nackter Literal 0.10
        self.trail_atr_mult = float(p.get("trail_atr_mult", 2.5))
        self.min_minutes_between_entries = int(p.get("min_minutes_between_entries", 15))
        self.risk_pct = float(p.get("risk_pct", 0.007))  # Original RiskPct=0.7%

        self._window_h1 = self.ema_slow * 3 + self.atr_len * 3 + 20
        self._window_h4 = self.ema_slow * 3 + self.atr_len * 3 + self.h4_slope_bars + 20
        self._window_m15 = (
            max(self.adx_len * 5, self.atr_len * 3)
            + self.expansion_lookback + self.retrace_max_bars + 40
        )
        self._last_entry_time: pd.Timestamp | None = None

        # Caches: H1/H4-Regime aendert sich nur, wenn eine neue H1/H4-Bar
        # schliesst -- Neuberechnung ausschliesslich bei Laengenaenderung des
        # sichtbaren Fensters (Performance).
        self._h1_cache: tuple[int, dict | None] = (-1, None)
        self._h4_cache: tuple[int, dict | None] = (-1, None)

    # -- Session-Helfer (exakte Original-Stunden) -------------------------------
    @staticmethod
    def _session_for_hour(h: int) -> str:
        if 0 <= h < 7:
            return "asia"
        if 7 <= h < 13:
            return "london"
        if 13 <= h < 21:
            return "newyork"
        return "off"

    # -- H1-Regime (3-EMA-Alignment 20/50/200 + Separation) ----------------------
    def _h1_state_calc(self, win: pd.DataFrame) -> dict | None:
        if len(win) < self.ema_slow + 5:
            return None
        close = win["close"]
        ema_f, ema_m, ema_s = _ema(close, self.ema_fast), _ema(close, self.ema_mid), _ema(close, self.ema_slow)
        atr_h1 = _atr(win, self.atr_len)
        vals = (ema_f.iloc[-1], ema_m.iloc[-1], ema_s.iloc[-1], atr_h1.iloc[-1])
        if any(pd.isna(v) for v in vals) or not (float(atr_h1.iloc[-1]) > 0):
            return None
        f, m, s, a = (float(v) for v in vals)
        sep = abs(f - m) / a
        if sep < self.min_h1_ema_sep_atr:
            return None
        if f > m > s:
            direction = 1
        elif f < m < s:
            direction = -1
        else:
            return None
        return {"direction": direction, "sep_atr": sep}

    def _h1_state_for(self, h1_view: pd.DataFrame) -> dict | None:
        length = len(h1_view)
        cached_len, cached_state = self._h1_cache
        if cached_len == length:
            return cached_state
        win = h1_view.iloc[-self._window_h1:] if length > self._window_h1 else h1_view
        state = self._h1_state_calc(win)
        self._h1_cache = (length, state)
        return state

    # -- H4-Regime (Slope-bestaetigte EMA(50)-vs-EMA(200)) ------------------------
    def _h4_state_calc(self, win: pd.DataFrame) -> dict | None:
        if len(win) < self.ema_slow + self.h4_slope_bars + 5:
            return None
        close = win["close"]
        ema_m, ema_s = _ema(close, self.ema_mid), _ema(close, self.ema_slow)
        atr_h4 = _atr(win, self.atr_len)
        if len(ema_m) <= self.h4_slope_bars or pd.isna(ema_m.iloc[-1 - self.h4_slope_bars]):
            return None
        a4 = float(atr_h4.iloc[-1])
        s_now = float(ema_s.iloc[-1])
        if pd.isna(a4) or not (a4 > 0) or pd.isna(s_now):
            return None
        m_now, m_old = float(ema_m.iloc[-1]), float(ema_m.iloc[-1 - self.h4_slope_bars])
        slope = (m_now - m_old) / a4
        if m_now > s_now and slope >= self.min_h4_slope_atr:
            direction = 1
        elif m_now < s_now and slope <= -self.min_h4_slope_atr:
            direction = -1
        else:
            return None
        return {"direction": direction, "slope_atr": slope}

    def _h4_state_for(self, h4_view: pd.DataFrame) -> dict | None:
        length = len(h4_view)
        cached_len, cached_state = self._h4_cache
        if cached_len == length:
            return cached_state
        win = h4_view.iloc[-self._window_h4:] if length > self._window_h4 else h4_view
        state = self._h4_state_calc(win)
        self._h4_cache = (length, state)
        return state

    # -- Kombinierte Regime-Pruefung (H1+H4 Alignment, M15-ADX/DI, Scores) -------
    def _regime(self, h1_view: pd.DataFrame, h4_view: pd.DataFrame, m15_win: pd.DataFrame) -> dict | None:
        h1s = self._h1_state_for(h1_view)
        if h1s is None:
            return None
        h4s = self._h4_state_for(h4_view)
        if h4s is None or h4s["direction"] != h1s["direction"]:
            return None
        direction = h1s["direction"]

        adx_df = _adx(m15_win, self.adx_len)
        adx_v, plus_di, minus_di = (
            adx_df["adx"].iloc[-1], adx_df["plus_di"].iloc[-1], adx_df["minus_di"].iloc[-1]
        )
        if any(pd.isna(v) for v in (adx_v, plus_di, minus_di)):
            return None
        adx_v, plus_di, minus_di = float(adx_v), float(plus_di), float(minus_di)
        if adx_v < self.min_trend_adx:
            return None
        if direction > 0 and plus_di < minus_di * 0.90:
            return None
        if direction < 0 and minus_di < plus_di * 0.90:
            return None

        regime_score = 18.0
        if adx_v >= 23.0:
            regime_score += 2.0
        if adx_v >= self.strong_trend_adx:
            regime_score += 3.0
        if adx_v >= self.very_strong_trend_adx:
            regime_score += 2.0
        adv = (plus_di - minus_di) if direction > 0 else (minus_di - plus_di)
        if adv >= 5.0:
            regime_score += 2.0
        if adv >= 10.0:
            regime_score += 1.0
        regime_score = min(regime_score, 28.0)

        htf_score = 12.0
        if h1s["sep_atr"] >= self.strong_h1_ema_sep_atr:
            htf_score += 3.0
        if h1s["sep_atr"] >= 0.40:
            htf_score += 2.0
        if abs(h4s["slope_atr"]) >= self.strong_h4_slope_atr:
            htf_score += 3.0
        htf_score = min(htf_score, 20.0)

        return {"direction": direction, "adx": adx_v, "regime_score": regime_score, "htf_score": htf_score}

    # -- Weiche M15-Struktur (nur Score, blockiert nie) --------------------------
    @staticmethod
    def _structure_score(m15_win: pd.DataFrame, direction: int) -> float:
        hist = m15_win.iloc[-11:-1]
        if len(hist) < 10:
            return 4.0
        recent, older = hist.iloc[-5:], hist.iloc[-10:-5]
        if direction > 0:
            aligned = recent["high"].max() > older["high"].max() and recent["low"].min() >= older["low"].min()
        else:
            aligned = recent["low"].min() < older["low"].min() and recent["high"].max() <= older["high"].max()
        return 8.0 if aligned else 4.0

    # -- ExpansionScoreV23 / RetraceScoreV23 (1:1 aus dem Original) --------------
    def _expansion_score(self, range_mult: float, body_pct: float) -> float:
        score = 6.0
        if range_mult >= self.quality_expansion_mult:
            score += 4.0
        if range_mult >= self.strong_expansion_mult:
            score += 4.0
        if range_mult >= self.elite_expansion_mult:
            score += 4.0
        if range_mult >= 2.75:
            score += 2.0
        if body_pct >= self.quality_body_pct:
            score += 4.0
        if body_pct >= self.strong_body_pct:
            score += 2.0
        if body_pct >= self.elite_body_pct:
            score += 2.0
        return min(score, 28.0)

    def _retrace_score(self, retrace_pct: float, fvg_present: bool, inside_fvg: bool) -> float:
        score = 4.0
        if self.retrace_acceptable_min <= retrace_pct <= self.retrace_acceptable_max:
            score += 3.0
        if self.retrace_ideal_min <= retrace_pct <= self.retrace_ideal_max:
            score += 4.0
        if self.retrace_elite_min <= retrace_pct <= self.retrace_elite_max:
            score += 2.0
        if fvg_present:
            score += 1.0
        if inside_fvg:
            score += 2.0
        return min(score, 16.0)

    # -- ClassifyRawQuality (1:1) --------------------------------------------------
    def _classify_quality(self, range_mult: float, body_pct: float) -> str:
        if range_mult >= self.elite_expansion_mult and body_pct >= self.strong_body_pct:
            return "ELITE"
        if range_mult >= self.strong_expansion_mult and body_pct >= self.elite_body_pct:
            return "ELITE"
        if range_mult >= self.strong_expansion_mult and body_pct >= self.quality_body_pct:
            return "STRONG"
        if range_mult >= self.quality_expansion_mult and body_pct >= self.strong_body_pct:
            return "STRONG"
        if range_mult >= self.quality_expansion_mult and body_pct >= self.quality_body_pct:
            return "STANDARD"
        return "REJECT"

    # -- Expansionskerze + FVG suchen (Position exp_pos = n-1-back) --------------
    def _find_expansion(self, m15_win: pd.DataFrame, direction: int, back: int) -> dict | None:
        n = len(m15_win)
        exp_pos = n - 1 - back
        lo = exp_pos - self.expansion_lookback
        if lo < 0:
            return None
        highs, lows = m15_win["high"], m15_win["low"]
        opens, closes = m15_win["open"], m15_win["close"]
        exp_high, exp_low = float(highs.iloc[exp_pos]), float(lows.iloc[exp_pos])
        exp_open, exp_close = float(opens.iloc[exp_pos]), float(closes.iloc[exp_pos])
        exp_range = exp_high - exp_low
        if not (exp_range > 0):
            return None
        avg_range = float((highs.iloc[lo:exp_pos] - lows.iloc[lo:exp_pos]).mean())
        if not (avg_range > 0):
            return None
        range_mult = exp_range / avg_range
        body_pct = abs(exp_close - exp_open) / exp_range
        if range_mult < self.detect_min_expansion_mult or body_pct < self.detect_min_body_pct:
            return None
        exp_dir = 1 if exp_close > exp_open else (-1 if exp_close < exp_open else 0)
        if exp_dir != direction:
            return None
        prior_high, prior_low = float(highs.iloc[lo:exp_pos].max()), float(lows.iloc[lo:exp_pos].min())
        if direction > 0 and exp_close <= prior_high:
            return None
        if direction < 0 and exp_close >= prior_low:
            return None

        fvg_present, fvg_low, fvg_high = False, 0.0, 0.0
        if exp_pos - 2 >= 0:
            c1_high, c1_low = float(highs.iloc[exp_pos - 2]), float(lows.iloc[exp_pos - 2])
            if direction > 0 and exp_low > c1_high:
                fvg_present, fvg_low, fvg_high = True, c1_high, exp_low
            elif direction < 0 and exp_high < c1_low:
                fvg_present, fvg_low, fvg_high = True, exp_high, c1_low

        return {
            "exp_pos": exp_pos, "age": back - 1,
            "exp_high": exp_high, "exp_low": exp_low, "exp_open": exp_open, "exp_range": exp_range,
            "range_mult": range_mult, "body_pct": body_pct,
            "fvg_present": fvg_present, "fvg_low": fvg_low, "fvg_high": fvg_high,
        }

    def _required_score(self, quality: str) -> float:
        req = {
            "ELITE": self.score_elite_min, "STRONG": self.score_strong_min,
            "STANDARD": self.score_standard_min, "REJECT": self.score_exceptional,
        }[quality]
        return max(req, self.score_absolute_min)

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        m15 = bars[self.tf_setup]
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

        m15_win = m15.iloc[max(0, i + 1 - self._window_m15): i + 1]
        h1_win = bars[self.tf_trend]
        h4_win = bars[self.tf_context]

        regime = self._regime(h1_win, h4_win, m15_win)
        if regime is None:
            return None
        direction = regime["direction"]
        if direction > 0 and not self.allow_longs:
            return None
        if direction < 0 and not self.allow_shorts:
            return None

        structure_score = self._structure_score(m15_win, direction)
        atr_series = _atr(m15_win, self.atr_len)

        exp = None
        for back in range(1, self.retrace_max_bars + 1):
            candidate = self._find_expansion(m15_win, direction, back)
            if candidate is not None:
                exp = candidate
                break
        if exp is None:
            return None

        atr_exp = float(atr_series.iloc[exp["exp_pos"]]) if exp["exp_pos"] < len(atr_series) else float("nan")
        if pd.isna(atr_exp) or not (atr_exp > 0):
            return None

        cur_close = float(m15_win["close"].iloc[-1])
        if direction > 0:
            retrace_pct = (exp["exp_high"] - cur_close) / exp["exp_range"]
            invalid = cur_close < exp["exp_open"] - self.setup_invalidation_atr * atr_exp
        else:
            retrace_pct = (cur_close - exp["exp_low"]) / exp["exp_range"]
            invalid = cur_close > exp["exp_open"] + self.setup_invalidation_atr * atr_exp
        if invalid or not (self.retrace_min_pct <= retrace_pct <= self.retrace_max_pct):
            return None

        inside_fvg = False
        if exp["fvg_present"]:
            lo_fvg, hi_fvg = min(exp["fvg_low"], exp["fvg_high"]), max(exp["fvg_low"], exp["fvg_high"])
            inside_fvg = lo_fvg <= cur_close <= hi_fvg

        expansion_score = self._expansion_score(exp["range_mult"], exp["body_pct"])
        retrace_score = self._retrace_score(retrace_pct, exp["fvg_present"], inside_fvg)
        session_bonus = {
            "asia": self.asia_score_bonus, "london": self.london_score_bonus,
            "newyork": self.newyork_score_bonus,
        }.get(session, 0.0)
        direction_bonus = self.sell_quality_bonus if direction < 0 else self.buy_quality_bonus

        base_score = min(
            regime["regime_score"] + regime["htf_score"] + expansion_score
            + structure_score + retrace_score + session_bonus + direction_bonus,
            100.0,
        )

        quality = self._classify_quality(exp["range_mult"], exp["body_pct"])
        quality_score = {"ELITE": 8.0, "STRONG": 5.0, "STANDARD": 2.0, "REJECT": 0.0}[quality]
        score = min(base_score + quality_score, 100.0)
        required_score = self._required_score(quality)

        if session == "london":
            required_score = max(required_score, self.london_min_score)
            if exp["range_mult"] < self.london_min_expansion and score < self.score_exceptional:
                return None

        if exp["age"] >= self.delayed_setup_from_bar:
            required_score = max(required_score, self.delayed_setup_min_score)
            if (exp["range_mult"] < self.delayed_setup_min_expansion
                    or exp["body_pct"] < self.delayed_setup_min_body):
                return None

        if quality == "REJECT":
            # "Weak Raw Quality Exception" — ein eigentlich abgelehntes
            # Signal wird bei Score>=92 dennoch als STANDARD durchgewunken.
            # 1:1 aus dem Original uebernommen.
            required_score = self.score_exceptional
            if score < required_score:
                return None
        elif score < required_score:
            return None

        sl = exp["exp_low"] - self.sl_buffer_atr * atr_exp if direction > 0 else exp["exp_high"] + self.sl_buffer_atr * atr_exp
        risk_distance = abs(cur_close - sl)
        if not (risk_distance > 0):
            return None
        tp = cur_close + direction * self.lock_trigger_r * risk_distance

        self._last_entry_time = ts
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "trail_atr_mult": self.trail_atr_mult, "trail_atr_len": self.atr_len,
                "tp_converts_to_trail": True,
                "score": score, "required_score": required_score, "quality": quality,
                "session": session, "setup_age_bars": exp["age"],
                "expansion_multiple": exp["range_mult"], "body_pct": exp["body_pct"],
                "retrace_pct": retrace_pct, "fvg_present": exp["fvg_present"], "inside_fvg": inside_fvg,
                "adx": regime["adx"], "risk_profile": self.risk_profile,
                "tp_target_r": self.tp_target_r, "lock_sl_r": self.lock_sl_r,
            },
            expires_bars=0,
        )
