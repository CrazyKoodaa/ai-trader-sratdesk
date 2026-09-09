"""strategies/analyze_7e9787b27c5c.py — Portierung von
"XAUUSD_TrendPullback_Presets_v2.mq5" (extern eingereichtes MT5/MQL5-EA-
Snippet, Research-EA mit explizitem Preset-System). Fortsetzung des
Quick-Checks: Multi-Timeframe-Trendfolge/Pullback auf XAUUSD — H4-Regime-
filter (EMA-Slope + ADX), H1-Impulserkennung mit Fibonacci-Retracement-Zone,
M15-Reclaim/Sweep als Entry-Trigger.

**Presets (``ENUM_RESEARCH_PRESET`` im Original) werden NICHT verschmolzen,
sondern als expliziter Auswahlparameter ``risk_profile`` gefuehrt** — jedes
Profil bleibt seine eigene, in sich konsistente Kombination aus ADX-
Schwelle, Impuls-ATR-Minimum, unterer Retracement-Grenze, max. Pullback-
Alter und SL-Puffer (s. Tabelle):

| Profil          | ADX  | Impuls-ATR-Min | Retr. unten | Max Pullback (H1) | SL-Puffer (ATR) |
|-----------------|------|-----------------|-------------|--------------------|-------------------|
| baseline        | 20.0 | 1.25            | 0.382       | 6                  | 0.15              |
| conservative    | 25.0 | 1.50            | 0.382       | 4                  | 0.25              |
| balanced (Default, Original-Default) | 25.0 | 1.50 | 0.382 | 6 | 0.20 |
| fast_pullback   | 20.0 | 1.25            | 0.500       | 4                  | 0.15              |
| strong_trend    | 25.0 | 1.50            | 0.500       | 6                  | 0.25              |

Fix je Profil (Original: ``InpUpperRetracementFixed``/``InpInvalidation-
Retracement``/``InpTakeProfitRFixed``): obere Retracement-Grenze 0.618,
Invalidierung 0.786, Take-Profit 2.0R.

Das Original kennt zusaetzlich ``PRESET_CUSTOM`` (freies Recherche-Grid ueber
dieselben 5 Achsen, 32 Kombinationen laut Kommentar) — das wird hier NICHT
als 6. Profil gefuehrt: diese Rolle uebernimmt bereits der ``param_space``-
Mechanismus des Projekt-eigenen WFO (s. Config), ein zusaetzliches
"CUSTOM"-Profil waere redundant.

WICHTIGE ANNAHMEN / VEREINFACHUNGEN gegenueber dem Original
=============================================================
1. **"Elapsed H1 bars since impulse"**: das Original ermittelt dies ueber
   ``iBarShift(..., exact=false)`` auf den Zeitstempel der Impuls-Bar, nach
   einer Scan-Schleife mit Index ``i`` (1..maxPullbackBars+1) auf einer
   ``shift=1``-basierten reversed-Serie — die Off-by-one-Beziehung zwischen
   Scan-Index ``i`` und dem zurueckgegebenen ``iBarShift``-Wert (``i+1`` bei
   exaktem Zeitstempel-Treffer) ist im Original-Code selbst nicht restlos
   eindeutig und wuerde 1:1 uebernommen den Pullback-Gueltigkeitsbereich um
   1 Bar verschieben. Diese Portierung definiert "Bars seit Impuls" daher
   direkt und eindeutig kausal: die ``i`` H1-Bars NACH der Impuls-Kandidaten-
   Bar bis inkl. der aktuellen letzten geschlossenen H1-Bar (identisch zur
   Scan-Index-Position, s. ``_find_impulse``/``_pullback_valid``) — inhaltlich
   dieselbe Absicht (Pullback-Fenster seit dem Impuls), ohne den fragwuerdigen
   Off-by-one.
2. **``EnforceMinimumStopDistance`` (Broker-Mindestabstand in MT5-Punkten)
   wird NICHT portiert** — die Engine (``core/backtester.py``) kennt kein
   Broker-Stops-Level; SL/TP werden direkt aus den ATR-Multiplikatoren
   verwendet. Der im Quick-Check genannte Logikfehler (SL wird verschoben,
   ohne TP/RR neu zu berechnen) ist damit gegenstandslos, weil der ganze
   Mechanismus entfaellt — real abweichend vom Original, aber der ATR-
   basierte SL-Abstand ist auf XAUUSD H1 fast immer >> jedes realistische
   Stops-Level, die Wirkung duerfte marginal sein.
3. **Konto-/Portfolio-Schutzmechanismen** (``InpUseDailyLossLimit``,
   ``InpUseEquityDrawdownLimit``, ``InpMaxTradesPerDay``,
   ``InpClosePositionsFriday``) sind Konto-State, kein Pro-Bar-Signal — die
   ``Strategy.on_bar``-Schnittstelle dieses Projekts ist rein kausal ohne
   Portfolio-State und bildet das nicht ab. ``InpOnePositionOnly`` wird
   naeherungsweise ueber ``risk.max_concurrent: 1`` in der Config abgedeckt.
4. **Spread-Filter (``InpMaxSpreadPoints``)** wird nicht separat auf
   Signal-Ebene geprueft — Spread-Kosten laufen projektweit einheitlich
   ueber das ``CostModel`` (jeder Trade traegt bereits Spread-Kosten); das
   EA-Verhalten "Signal komplett blocken bei zu weitem Spread" wird nicht
   gesondert nachgebildet.
5. **Kein Time-Stop / technischer Exit vor SL/TP** (Quick-Check-Finding):
   1:1 wie im Original — feste SL/TP (2R), kein Trail, kein Zeit-Exit. Das
   ist eine Eigenschaft der ORIGINAL-Strategie, keine durch die Portierung
   eingefuehrte Vereinfachung; bei Seitwaerts-Phasen bleibt Kapital bis
   TP/SL gebunden.
6. **``min_atr_price`` (absoluter Preis-ATR-Schwellenwert, Default 1.00)**
   wird unveraendert als fixer Literal-Parameter uebernommen — inkl. der im
   Quick-Check genannten Schwaeche (nicht repraesentativ ueber Goldpreis-
   Regime 1800->2600 hinweg). Wird in dieser WFO-Config NICHT mitgesweept
   (Scope-Entscheidung, s. Config-Docstring).
7. **``pullback_range_max_ratio`` (Default 0.75)** ebenfalls unveraendert
   als fixer Literal uebernommen (weitere im Quick-Check genannte
   unbegruendete Konstante) — nicht Teil des WFO-``param_space`` dieses
   Laufs.
8. **``trend_slope_min_atr`` (Default 0.20)** ist die vierte im Quick-Check
   genannte unbegruendete Konstante, wird hier aber zusaetzlich als 2.
   ``param_space``-Achse gefuehrt (neben ``risk_profile``), weil sie am
   weitesten oben in der Kausalkette sitzt (gate't den H4-Regimefilter, von
   dem alles Weitere abhaengt) — ein erster Sensitivitaets-Check im Rahmen
   dieses Laufs.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, adx as _adx, atr as _atr, ema as _ema


# Preset-Tabelle (ENUM_RESEARCH_PRESET im Original, s. Docstring-Tabelle).
_RISK_PROFILES: dict[str, dict[str, float | int]] = {
    "baseline": {
        "adx_threshold": 20.0, "min_impulse_atr": 1.25,
        "lower_retracement": 0.382, "max_pullback_bars": 6, "sl_buffer_atr": 0.15,
    },
    "conservative": {
        "adx_threshold": 25.0, "min_impulse_atr": 1.50,
        "lower_retracement": 0.382, "max_pullback_bars": 4, "sl_buffer_atr": 0.25,
    },
    "balanced": {
        "adx_threshold": 25.0, "min_impulse_atr": 1.50,
        "lower_retracement": 0.382, "max_pullback_bars": 6, "sl_buffer_atr": 0.20,
    },
    "fast_pullback": {
        "adx_threshold": 20.0, "min_impulse_atr": 1.25,
        "lower_retracement": 0.500, "max_pullback_bars": 4, "sl_buffer_atr": 0.15,
    },
    "strong_trend": {
        "adx_threshold": 25.0, "min_impulse_atr": 1.50,
        "lower_retracement": 0.500, "max_pullback_bars": 6, "sl_buffer_atr": 0.25,
    },
}


class AnalyzeXauTrendPullbackPresets(Strategy):
    name = "analyze_7e9787b27c5c"
    required_timeframes = ["M15", "H1", "H4"]

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")

        # -- Risk-Profil (5 benannte Presets, s. Docstring-Tabelle) -----------
        profile_key = str(p.get("risk_profile", "balanced")).strip().lower()
        if profile_key not in _RISK_PROFILES:
            raise ValueError(
                f"Unbekanntes risk_profile={profile_key!r}, erwartet eines von "
                f"{sorted(_RISK_PROFILES)}"
            )
        self.risk_profile = profile_key
        profile = _RISK_PROFILES[profile_key]
        self.adx_threshold = float(profile["adx_threshold"])
        self.min_impulse_atr = float(profile["min_impulse_atr"])
        self.lower_retracement = float(profile["lower_retracement"])
        self.max_pullback_bars = int(profile["max_pullback_bars"])
        self.sl_buffer_atr = float(profile["sl_buffer_atr"])

        # -- Timeframes ---------------------------------------------------------
        self.tf_entry = p.get("tf_entry", "M15")
        self.tf_impulse = p.get("tf_impulse", "H1")
        self.tf_trend = p.get("tf_trend", "H4")

        # -- Fixe Modellparameter (Original: "Fixed model parameters") ----------
        self.trend_ema_period = int(p.get("trend_ema_period", 50))
        self.trend_adx_period = int(p.get("trend_adx_period", 14))
        self.trend_slope_bars = int(p.get("trend_slope_bars", 8))
        self.trend_slope_min_atr = float(p.get("trend_slope_min_atr", 0.20))  # Quick-Check: unbegruendet, hier gesweept
        self.impulse_atr_period = int(p.get("impulse_atr_period", 14))
        self.entry_atr_period = int(p.get("entry_atr_period", 14))
        self.swing_lookback_h1 = int(p.get("swing_lookback_h1", 8))
        self.reclaim_lookback_m15 = int(p.get("reclaim_lookback_m15", 4))
        self.upper_retracement = float(p.get("upper_retracement_fixed", 0.618))
        self.invalidation_retracement = float(p.get("invalidation_retracement", 0.786))
        self.pullback_range_max_ratio = float(p.get("pullback_range_max_ratio", 0.75))  # Quick-Check: unbegruendet, fix
        self.take_profit_r = float(p.get("take_profit_r_fixed", 2.00))
        self.min_atr_price = float(p.get("min_atr_price", 1.00))  # Quick-Check: unbegruendet, fix (s. Annahme 6)

        self.allow_long = bool(p.get("allow_long", True))
        self.allow_short = bool(p.get("allow_short", True))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        # -- Session (UTC), Original-Defaults ------------------------------------
        self.use_session_filter = bool(p.get("use_session_filter", True))
        self.start_hour_utc = int(p.get("start_hour_utc", 8))
        self.end_hour_utc = int(p.get("end_hour_utc", 22))
        self.block_friday_late = bool(p.get("block_friday_late", True))
        self.friday_stop_hour_utc = int(p.get("friday_stop_hour_utc", 19))

        self._window_h4 = (
            max(self.trend_ema_period * 3, self.trend_adx_period * 3, self.impulse_atr_period * 3)
            + self.trend_slope_bars + 20
        )
        self._window_h1 = (
            self.swing_lookback_h1 + self.max_pullback_bars + self.impulse_atr_period * 3 + 20
        )
        self._window_m15 = self.entry_atr_period * 3 + self.reclaim_lookback_m15 + 10

        # Cache: H4-Regime aendert sich nur bei neuer H4-Bar (Performance,
        # analog zu s16/analyze_95443742cec6).
        self._h4_cache: tuple[int, tuple[bool, bool] | None] = (-1, None)

    # -- H4-Regime (EMA-Slope + ADX) --------------------------------------------
    def _h4_regime_calc(self, win: pd.DataFrame) -> tuple[bool, bool] | None:
        need = self.trend_ema_period + self.trend_slope_bars + 5
        if len(win) < need:
            return None
        close = win["close"]
        ema_s = _ema(close, self.trend_ema_period)
        adx_now = _adx(win, self.trend_adx_period)["adx"].iloc[-1]
        atr_h4 = _atr(win, self.impulse_atr_period).iloc[-1]
        if len(ema_s) <= self.trend_slope_bars:
            return None
        vals = (close.iloc[-1], ema_s.iloc[-1], ema_s.iloc[-1 - self.trend_slope_bars], adx_now, atr_h4)
        if any(pd.isna(v) for v in vals):
            return None
        c, e_now, e_old, adx_v, atr_v = (float(v) for v in vals)
        if atr_v <= 0:
            return None
        slope = (e_now - e_old) / atr_v
        adx_ok = adx_v >= self.adx_threshold
        bullish = adx_ok and c > e_now and slope >= self.trend_slope_min_atr
        bearish = adx_ok and c < e_now and slope <= -self.trend_slope_min_atr
        return (bullish, bearish)

    def _h4_regime_for(self, h4_view: pd.DataFrame) -> tuple[bool, bool] | None:
        length = len(h4_view)
        cached_len, cached = self._h4_cache
        if cached_len == length:
            return cached
        win = h4_view.iloc[-self._window_h4:] if length > self._window_h4 else h4_view
        state = self._h4_regime_calc(win)
        self._h4_cache = (length, state)
        return state

    # -- H1-Impulserkennung + Fibonacci-Retracement-Zone -------------------------
    def _find_impulse(self, h1_win: pd.DataFrame, is_long: bool) -> dict | None:
        n = len(h1_win)
        need = self.swing_lookback_h1 + self.max_pullback_bars + 2
        if n < need:
            return None
        highs, lows, closes = h1_win["high"].to_numpy(), h1_win["low"].to_numpy(), h1_win["close"].to_numpy()
        atr_s = _atr(h1_win, self.impulse_atr_period).to_numpy()

        for i in range(1, self.max_pullback_bars + 2):
            cand = n - 1 - i               # Kandidaten-Bar (aufsteigende Position)
            lo = cand - self.swing_lookback_h1
            hi = cand - 1
            if lo < 0 or pd.isna(atr_s[cand]) or atr_s[cand] <= 0:
                continue
            prior_high = highs[lo: hi + 1].max()
            prior_low = lows[lo: hi + 1].min()

            break_long = closes[cand] > prior_high
            break_short = closes[cand] < prior_low
            if is_long and not break_long:
                continue
            if not is_long and not break_short:
                continue

            impulse_low = prior_low if is_long else lows[cand]
            impulse_high = highs[cand] if is_long else prior_high
            impulse_range = impulse_high - impulse_low
            if impulse_range < self.min_impulse_atr * atr_s[cand]:
                continue

            if is_long:
                zone_high = impulse_high - self.lower_retracement * impulse_range
                zone_low = impulse_high - self.upper_retracement * impulse_range
                invalidation = impulse_high - self.invalidation_retracement * impulse_range
            else:
                zone_low = impulse_low + self.lower_retracement * impulse_range
                zone_high = impulse_low + self.upper_retracement * impulse_range
                invalidation = impulse_low + self.invalidation_retracement * impulse_range

            return {
                "bars_since": i,             # s. Annahme 1 im Docstring
                "impulse_high": impulse_high, "impulse_low": impulse_low,
                "zone_low": zone_low, "zone_high": zone_high, "invalidation": invalidation,
            }
        return None

    def _pullback_valid(self, h1_win: pd.DataFrame, setup: dict, is_long: bool) -> bool:
        n = len(h1_win)
        bars_since = setup["bars_since"]
        window = h1_win.iloc[n - bars_since: n]   # die bars_since H1-Bars seit dem Impuls (s. Annahme 1)
        if len(window) == 0:
            return False

        touched_zone = ((window["low"] <= setup["zone_high"]) & (window["high"] >= setup["zone_low"])).any()
        if not touched_zone:
            return False

        if is_long and (window["low"] <= setup["invalidation"]).any():
            return False
        if not is_long and (window["high"] >= setup["invalidation"]).any():
            return False

        impulse_range = setup["impulse_high"] - setup["impulse_low"]
        if impulse_range <= 0:
            return False
        avg_pullback_range = float((window["high"] - window["low"]).mean())
        return avg_pullback_range < self.pullback_range_max_ratio * impulse_range

    def _pullback_extreme(self, h1_win: pd.DataFrame, is_long: bool) -> float | None:
        n = len(h1_win)
        lookback = self.max_pullback_bars + 1
        if n < lookback:
            return None
        window = h1_win.iloc[n - lookback: n]
        return float(window["low"].min()) if is_long else float(window["high"].max())

    # -- M15-Reclaim/Sweep-Trigger -----------------------------------------------
    def _reclaim_confirmed(self, m15_win: pd.DataFrame, zone_low: float, zone_high: float, is_long: bool) -> bool:
        n = len(m15_win)
        if n < self.reclaim_lookback_m15 + 2:
            return False
        cur = m15_win.iloc[-1]
        prior = m15_win.iloc[n - 1 - self.reclaim_lookback_m15: n - 1]

        if is_long:
            sweep = cur["low"] < prior["low"].min()
            directional_close = cur["close"] > cur["open"]
            reclaim_zone = cur["close"] > zone_low
            breaks_prior = cur["close"] > m15_win.iloc[-2]["high"]
        else:
            sweep = cur["high"] > prior["high"].max()
            directional_close = cur["close"] < cur["open"]
            reclaim_zone = cur["close"] < zone_high
            breaks_prior = cur["close"] < m15_win.iloc[-2]["low"]
        return bool(sweep and directional_close and reclaim_zone and breaks_prior)

    # -- Session (UTC) -------------------------------------------------------------
    def _session_ok(self, ts: pd.Timestamp) -> bool:
        dow, hour = int(ts.dayofweek), int(ts.hour)  # Montag=0 .. Sonntag=6
        if dow >= 5:
            return False
        if self.block_friday_late and dow == 4 and hour >= self.friday_stop_hour_utc:
            return False
        if not self.use_session_filter:
            return True
        if self.start_hour_utc < self.end_hour_utc:
            return self.start_hour_utc <= hour < self.end_hour_utc
        return hour >= self.start_hour_utc or hour < self.end_hour_utc

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        m15 = bars[self.tf_entry]
        if i < self._window_m15:
            return None
        ts = m15.index[i]
        if not self._session_ok(ts):
            return None

        m15_win = m15.iloc[max(0, i + 1 - self._window_m15): i + 1]
        entry_atr = _atr(m15_win, self.entry_atr_period)
        if len(entry_atr) < 1 or pd.isna(entry_atr.iloc[-1]):
            return None
        atr_now = float(entry_atr.iloc[-1])
        if atr_now <= 0 or atr_now < self.min_atr_price:
            return None

        bullish, bearish = self._h4_regime_for(bars[self.tf_trend]) or (False, False)

        h1_view = bars[self.tf_impulse]
        h1_win = h1_view.iloc[-self._window_h1:] if len(h1_view) > self._window_h1 else h1_view

        direction = None
        setup = None
        if bullish and self.allow_long:
            cand = self._find_impulse(h1_win, True)
            if cand is not None and self._pullback_valid(h1_win, cand, True) and \
               self._reclaim_confirmed(m15_win, cand["zone_low"], cand["zone_high"], True):
                direction, setup = 1, cand
        if direction is None and bearish and self.allow_short:
            cand = self._find_impulse(h1_win, False)
            if cand is not None and self._pullback_valid(h1_win, cand, False) and \
               self._reclaim_confirmed(m15_win, cand["zone_low"], cand["zone_high"], False):
                direction, setup = -1, cand

        if direction is None:
            return None

        pivot = self._pullback_extreme(h1_win, direction > 0)
        if pivot is None:
            return None

        entry = float(m15_win["close"].iloc[-1])
        sl = pivot - self.sl_buffer_atr * atr_now if direction > 0 else pivot + self.sl_buffer_atr * atr_now
        risk_distance = entry - sl if direction > 0 else sl - entry
        if risk_distance <= 0:
            return None
        tp = entry + direction * self.take_profit_r * risk_distance

        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={
                "risk_profile": self.risk_profile, "atr_entry": atr_now,
                "bars_since_impulse": setup["bars_since"],
                "zone_low": setup["zone_low"], "zone_high": setup["zone_high"],
            },
            expires_bars=0,
        )
