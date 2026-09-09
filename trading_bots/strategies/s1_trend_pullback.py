"""S1 — TrendPullback (XAUUSD, H4; Bias D1) gemäß SPEC §5/S1.

Varianten (param ``variant``):
- ``v5`` (Default): D1-Bias (Close vs SMA200 + DI-State + ADX≥20-Gate),
  H4-Pullback in Zone = EMA20(H4) ∩ Fib 38.2–61.8 % des letzten
  Impuls-Swings, Reversal-Close-Trigger, Market-Entry nächste Bar,
  SL = max(sl_atr×ATR14(H4), hinter Swing-Extrem), TP1 = tp1_r×R (50 %,
  Runner-Trail an H4-Pivots via meta), Time-Exit 30 H4-Bars (via meta).
- ``v1`` (Vergleichsarm): DI-Cross D1 pur, SL 2×ATR14(D1), TP 2:1.

Filter-Layer (SPEC §6) sind Config-Flags und A/B-abschaltbar:
- ``session_filter``: Entries nur 07–17 UTC (nur V5; V1 ist "pur").
- ``regime_filter``: delegiert an die Engine — die Strategie fragt nur ab,
  ob der Engine-Regime-State Trend erlaubt (``params['regime_allow_trend']``,
  Default True).
- ``news_filter``: Engine-seitig; die Strategie füllt die meta-Felder.
- ``vp_filter``: Volume-Profile-Konfluenz-Layer (dim13 Variante b, Default
  AUS): F1 Entry am POC/HVN, F6 Block in LVN, optional SL hinter VA
  (``vp_structure_levels``, nur weiter weg, nie enger; TP1 wird mit
  gleichem RR-Mult auf die neue SL-Distanz umgerechnet).

Kausalität: D1-Bars werden nur verwendet, wenn sie vor dem aktuellen UTC-Tag
eröffnet wurden (geschlossen). H4-Indikatoren laufen auf dem Slice bis inkl.
Bar i. Swing-Pivots sind erst nach ``right`` Bars sichtbar (kein Lookahead).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.volume_profile import entry_gate, structural_stop, volume_profile

from .base import (
    Signal,
    Strategy,
    adx,
    atr,
    ema,
    in_session,
    sma,
    swing_points,
)

DEFAULT_PARAMS: dict = {
    "symbol": "XAUUSD",
    "variant": "v5",                # "v5" | "v1"
    "risk_pct": 0.005,
    # --- V5: Bias (D1), stabil laut SPEC ---
    "sma_len": 200,
    "atr_len": 14,
    "adx_len": 14,
    "adx_gate": 20.0,               # Regime-Gate, kein Entry-Filter
    # --- V5: Setup/Trigger (H4) ---
    "ema_len": 20,                  # WFO {20,30,50}
    "fib_lo": 0.382,
    "fib_hi": 0.618,
    "ema_band_atr": 0.5,            # EMA20-Vicinity für Zone-Schnittmenge
    "swing_left": 2,
    "swing_right": 2,               # Pivot erst nach right Bars sichtbar
    "touch_max_age": 5,             # H4-Bars, die ein Zone-Touch gültig bleibt
    # --- V5: Exits ---
    "sl_atr": 1.5,                  # WFO {1.25,1.5,2.0,2.5}
    "tp1_r": 2.0,                   # WFO {1.5,2.0,2.5}; TP1 50 %, Runner-Trail
    "time_exit": 30,                # WFO {15,30,60} H4-Bars
    # --- V1 (Vergleichsarm) ---
    "v1_sl_atr": 2.0,
    "v1_tp_r": 2.0,
    # --- Filter-Layer (A/B, SPEC §6) ---
    "filters": {
        "session_filter": True,     # Entries nur 07–17 UTC (nur V5)
        "session_start_utc": "07:00",
        "session_end_utc": "17:00",
        "news_filter": True,        # Engine-seitig (meta-Felder)
        "regime_filter": "off",     # off|adx_proxy|hmm — Engine liefert State
        "friday_flat": True,        # Engine-seitig (kein Wochenend-Risiko)
    },
    # --- Volume-Profile-Konfluenz-Layer (dim13, Variante b; A/B, Default AUS) ---
    # F1: Entry-Signal-Close muss innerhalb tolerance_atr×ATR von POC/HVN liegen.
    # F6: Entry blockiert, wenn Signal-Close in einer LVN liegt.
    # vp_structure_levels: SL hinter VA-Low/High (nur weiter weg, nie enger);
    #   TP1 wird mit gleichem RR-Mult auf die neue SL-Distanz umgerechnet.
    "vp_filter": {
        "enabled": False,
        "anchor": "swing",          # "swing" (Video-Variante) | "rolling"
        "lookback_bars": 120,       # WFO {60,120,240}; swing: Obergrenze
        "entry_requires_hvn": True,
        "block_lvn": True,
        "tolerance_atr": 0.25,
        "vp_structure_levels": False,
    },
    # Engine-Inputs (werden ggf. pro Bar von der Engine gesetzt):
    "regime_allow_trend": True,
    "news_blackout": False,
}


class TrendPullback(Strategy):
    name = "s1_trend_pullback"
    required_timeframes = ["H4", "D1"]

    def __init__(self, params: dict | None = None):
        merged = dict(DEFAULT_PARAMS)
        merged.update(params or {})
        merged["filters"] = {**DEFAULT_PARAMS["filters"],
                             **(params or {}).get("filters", {})}
        merged["vp_filter"] = {**DEFAULT_PARAMS["vp_filter"],
                               **(params or {}).get("vp_filter", {})}
        super().__init__(merged)
        # Kausaler State: Zone-Touches + V1-Cross-Dedup (zeitstempel-basiert)
        self._touch: dict[int, Optional[pd.Timestamp]] = {+1: None, -1: None}
        self._last_v1_cross: Optional[pd.Timestamp] = None

    # ------------------------------------------------------------------ #
    # Hilfsfunktionen (alle rein kausal)
    # ------------------------------------------------------------------ #

    def _closed_d1(self, d1: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
        """Nur D1-Bars, die vor dem aktuellen UTC-Tag geschlossen wurden."""
        return d1[d1.index < t.normalize()]

    def _d1_bias(self, d1c: pd.DataFrame) -> int:
        """+1/-1/0 laut SPEC: Close vs SMA200, DI-State, ADX≥20-Gate."""
        p = self.params
        need = max(p["sma_len"], 3 * p["adx_len"]) + 2
        if len(d1c) < need:
            return 0
        close = d1c["close"]
        sma_v = sma(close, p["sma_len"]).iloc[-1]
        ax = adx(d1c, p["adx_len"]).iloc[-1]
        if np.isnan(sma_v) or np.isnan(ax["adx"]):
            return 0
        c = close.iloc[-1]
        if c > sma_v and ax["plus_di"] > ax["minus_di"] and ax["adx"] >= p["adx_gate"]:
            return +1
        if c < sma_v and ax["minus_di"] > ax["plus_di"] and ax["adx"] >= p["adx_gate"]:
            return -1
        return 0

    def _impulse_zone(self, h4: pd.DataFrame, direction: int,
                      ema_now: float, atr_now: float):
        """Fib-Zone des letzten Impuls-Swings ∩ EMA20-Band.

        Rückgabe (zone_lo, zone_hi) oder None, wenn keine verwertbare
        Schnittmenge existiert.
        """
        p = self.params
        sp = swing_points(h4, p["swing_left"], p["swing_right"], 0)
        highs = sp["swing_high"].dropna()
        lows = sp["swing_low"].dropna()
        if direction == +1:
            if len(highs) < 1 or len(lows) < 1:
                return None
            h_t, h_v = highs.index[-1], float(highs.iloc[-1])
            lows_before = lows[lows.index < h_t]
            if len(lows_before) < 1:
                return None
            l_v = float(lows_before.iloc[-1])
            if h_v <= l_v:
                return None
            leg = h_v - l_v
            fib_lo_p = h_v - p["fib_hi"] * leg
            fib_hi_p = h_v - p["fib_lo"] * leg
        else:
            if len(highs) < 1 or len(lows) < 1:
                return None
            l_t, l_v = lows.index[-1], float(lows.iloc[-1])
            highs_before = highs[highs.index < l_t]
            if len(highs_before) < 1:
                return None
            h_v = float(highs_before.iloc[-1])
            if h_v <= l_v:
                return None
            leg = h_v - l_v
            fib_lo_p = l_v + p["fib_lo"] * leg
            fib_hi_p = l_v + p["fib_hi"] * leg
        band = p["ema_band_atr"] * atr_now
        zone_lo = max(fib_lo_p, ema_now - band)
        zone_hi = min(fib_hi_p, ema_now + band)
        if zone_lo > zone_hi:
            return None
        return zone_lo, zone_hi

    def _last_swing_extreme(self, h4: pd.DataFrame,
                            direction: int) -> Optional[float]:
        sp = swing_points(h4, self.params["swing_left"],
                          self.params["swing_right"], 0)
        s = sp["swing_low"].dropna() if direction == +1 else sp["swing_high"].dropna()
        return float(s.iloc[-1]) if len(s) else None

    # ------------------------------------------------------------------ #
    # V5 — TrendPullback
    # ------------------------------------------------------------------ #

    def _on_bar_v5(self, bars: dict[str, pd.DataFrame], i: int) -> Optional[Signal]:
        p = self.params
        f = p["filters"]
        h4 = bars["H4"].iloc[: i + 1]
        t = h4.index[i]

        # Engine-seitige Gates nur abfragen (Regime/News laut SPEC §6)
        if not p.get("regime_allow_trend", True):
            return None
        if p.get("news_blackout", False):
            return None
        # Session-Filter (A/B): Entries nur 07–17 UTC
        if f["session_filter"] and not in_session(
            t, "UTC", f["session_start_utc"], f["session_end_utc"]
        ):
            return None

        bias = self._d1_bias(self._closed_d1(bars["D1"], t))
        if bias == 0:
            return None

        ema_now = float(ema(h4["close"], p["ema_len"]).iloc[-1])
        atr_now = float(atr(h4, p["atr_len"]).iloc[-1])
        if np.isnan(ema_now) or np.isnan(atr_now) or atr_now <= 0:
            return None

        zone = self._impulse_zone(h4, bias, ema_now, atr_now)
        if zone is None:
            return None
        zone_lo, zone_hi = zone

        # Setup: Touch = Bar-Low (long) / Bar-High (short) in Zone
        bar = h4.iloc[-1]
        if bias == +1 and zone_lo <= float(bar["low"]) <= zone_hi:
            self._touch[+1] = t
        if bias == -1 and zone_lo <= float(bar["high"]) <= zone_hi:
            self._touch[-1] = t

        # Touch verfällt nach touch_max_age Bars
        touch_t = self._touch[bias]
        if touch_t is None:
            return None
        age = len(h4.loc[touch_t:]) - 1
        if age > p["touch_max_age"]:
            self._touch[bias] = None
            return None

        # Trigger: Reversal-Close in Bias-Richtung (nach Zone-Touch)
        if bias == +1 and not (bar["close"] > bar["open"]):
            return None
        if bias == -1 and not (bar["close"] < bar["open"]):
            return None

        # Entry: Market nächste Bar (entry_price=None). SL/TP vom Signal-Close.
        ref = float(bar["close"])

        # --- Volume-Profile-Konfluenz-Layer (A/B, dim13 F1/F6) ---
        # Gate auf den Signal-Close (Proxy für den Fill = Open nächste Bar).
        # Bei Block: Touch bleibt gültig (der Filter ist ein Gate, kein
        # Signal-Verfall) — ein späterer Trigger im Touch-Fenster kann feuern.
        vp = p["vp_filter"]
        vp_meta: dict = {"vp_enabled": bool(vp.get("enabled", False))}
        vp_profile = None
        if vp.get("enabled", False):
            vp_profile = volume_profile(
                h4, lookback_bars=vp["lookback_bars"], anchor=vp["anchor"])
            allowed, vp_meta = entry_gate(
                vp_profile, ref, vp["tolerance_atr"] * atr_now,
                entry_requires_hvn=vp["entry_requires_hvn"],
                block_lvn=vp["block_lvn"])
            vp_meta["vp_enabled"] = True
            if not allowed:
                return None

        swing_ext = self._last_swing_extreme(h4, bias)
        sl_dist = p["sl_atr"] * atr_now
        if swing_ext is not None:
            sl_dist = max(sl_dist, (ref - swing_ext) if bias == +1
                          else (swing_ext - ref))
        sl = ref - sl_dist if bias == +1 else ref + sl_dist
        if vp_profile is not None and vp.get("vp_structure_levels", False):
            # SL hinter VA-Low/High statt reinem ATR-Stop — NUR wenn weiter
            # weg, nie enger (strukturell begründetes Risiko, kein engerer).
            sl_struct = structural_stop(vp_profile, bias, sl,
                                        buffer=0.1 * atr_now)
            new_dist = abs(ref - sl_struct)
            if new_dist > sl_dist:
                sl_dist = new_dist
                sl = sl_struct
                vp_meta["vp_sl_structure"] = True
        tp1 = ref + p["tp1_r"] * sl_dist if bias == +1 else ref - p["tp1_r"] * sl_dist

        self._touch[bias] = None  # kein Doppel-Signal aus demselben Touch

        return Signal(
            time=t,
            symbol=p["symbol"],
            direction=bias,
            entry_type="market",
            entry_price=None,
            stop_loss=sl,
            take_profit=tp1,
            risk_pct=p["risk_pct"],
            meta={
                "strategy": self.name,
                "variant": "v5",
                "tp1_r": p["tp1_r"],
                "tp1_close_pct": 0.5,           # TP1 50 %, Rest Runner
                "runner_trail": "h4_pivot",     # Trail unter/über H4-Pivots
                "time_exit_bars": p["time_exit"],
                "d1_bias": bias,
                "zone": [zone_lo, zone_hi],
                "swing_extreme": swing_ext,
                "atr": atr_now,
                "filters": dict(f),
                "regime_filter": f["regime_filter"],
                "news_filter": f["news_filter"],
                "news_blackout": None,          # wird engine-seitig gefüllt
                **vp_meta,                      # VP-Layer-Info (A/B-Nachweis)
            },
        )

    # ------------------------------------------------------------------ #
    # V1 — DI-Cross D1 pur (Vergleichsarm), SL 2×ATR, TP 2:1
    # ------------------------------------------------------------------ #

    def _on_bar_v1(self, bars: dict[str, pd.DataFrame], i: int) -> Optional[Signal]:
        p = self.params
        t = bars["H4"].index[i]
        if p.get("news_blackout", False):
            return None
        d1c = self._closed_d1(bars["D1"], t)
        if len(d1c) < 3 * p["adx_len"] + 2:
            return None
        ax = adx(d1c, p["adx_len"])
        a_last, a_prev = ax.iloc[-1], ax.iloc[-2]
        cross_time = d1c.index[-1]
        if cross_time == self._last_v1_cross:
            return None
        direction = 0
        if a_prev["plus_di"] <= a_prev["minus_di"] and a_last["plus_di"] > a_last["minus_di"]:
            direction = +1
        elif a_prev["minus_di"] <= a_prev["plus_di"] and a_last["minus_di"] > a_last["plus_di"]:
            direction = -1
        if direction == 0:
            return None
        atr_d1 = float(atr(d1c, p["atr_len"]).iloc[-1])
        ref = float(d1c["close"].iloc[-1])
        sl_dist = p["v1_sl_atr"] * atr_d1
        sl = ref - sl_dist if direction == +1 else ref + sl_dist
        tp = ref + p["v1_tp_r"] * sl_dist if direction == +1 else ref - p["v1_tp_r"] * sl_dist
        self._last_v1_cross = cross_time
        return Signal(
            time=t,
            symbol=p["symbol"],
            direction=direction,
            entry_type="market",
            entry_price=None,
            stop_loss=sl,
            take_profit=tp,
            risk_pct=p["risk_pct"],
            meta={
                "strategy": self.name,
                "variant": "v1",
                "d1_cross_time": cross_time,
                "atr_d1": atr_d1,
                "filters": dict(p["filters"]),
                "regime_filter": p["filters"]["regime_filter"],
                "news_filter": p["filters"]["news_filter"],
                "news_blackout": None,
            },
        )

    # ------------------------------------------------------------------ #

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Optional[Signal]:
        if self.params["variant"] == "v1":
            return self._on_bar_v1(bars, i)
        return self._on_bar_v5(bars, i)
