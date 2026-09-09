"""S2 — VWAPPullback (US100/NAS100, M5; nur 9:45–11:30 America/New_York)
gemäß SPEC §5/S2.

- Session-VWAP (tick_volume) ab 9:30 ET.
- Kontext: >= min_closes M5-Closes ober-/unterhalb VWAP seit 9:45 ET.
- Setup: Pullback-Touch VWAP + RSI(2) < rsi_th (Long) / > 100-rsi_th (Short).
- Trigger: nächste M5 schließt in Trendrichtung über/unter VWAP
  → Market-Entry nächste Bar.
- SL: atr_mult × ATR14(M5). TP: PDH/PDL, Fallback 2×ATR; Gate RR >= min_rr,
  sonst kein Trade.
- Harter Time-Exit 11:30 ET + EOD-Flat 16:55 ET (Engine, via meta).
- Max 1 Long + 1 Short pro ET-Tag. Kein Trailing. Spread-Guard-Param.

Kausalität: alle Indikatoren laufen auf dem Slice bis inkl. Bar i; der
Session-VWAP nutzt nur Bars der laufenden ET-Session (ab 9:30) bis i;
PDH/PDL kommen aus dem vorangegangenen ET-Tag. Zeitzonen ausschließlich
via zoneinfo (America/New_York) — DST-Asynchronwochen-sicher.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base import (
    Signal,
    Strategy,
    atr,
    ny_time,
    rsi,
    vwap_session,
)

NY_TZ = "America/New_York"

DEFAULT_PARAMS: dict = {
    "symbol": "US100",
    "risk_pct": 0.005,
    "min_rr": 2.0,
    # --- Session/Fenster (ET) ---
    "vwap_start": "09:30",
    "context_start": "09:45",
    "entry_start": "09:45",
    "last_trigger": "11:25",        # letzter Trigger-Bar; Entry <= 11:30
    "time_exit": "11:30",           # hart (Engine erzwingt, meta)
    "eod_flat": "16:55",            # Engine (RiskConfig), meta
    # --- Kontext/Setup ---
    "min_closes": 3,
    "trend_buffer_pct": 0.0,        # WFO {0,0.2,0.4,0.6}
    "rsi_len": 2,
    "rsi_th": 25.0,                 # WFO {15,20,25,30,35}; Short = 100 - th
    "atr_len": 14,
    "atr_mult": 1.5,                # WFO {1.0,1.5,2.0,2.5}
    # --- Exits ---
    "tp_mode": "pdh",               # WFO {pdh,2atr,3atr}; pdh→Fallback 2×ATR
    "tp_fallback_atr": 2.0,
    "max_trades_per_side": 1,       # max 1 Long + 1 Short/Tag
    # --- Filter-Layer (A/B, SPEC §6) ---
    "filters": {
        "news_filter": True,        # Engine-seitig (USD); meta-Felder
        "spread_guard": True,
        "max_spread_points": 2.0,   # US100
        "friday_short_bias": False, # WFO-Variante: freitags nur Shorts
        "friday_flat": True,        # Engine-seitig
    },
    # Engine-Inputs (ggf. pro Bar gesetzt):
    "news_blackout": False,
    "current_spread_points": 0.0,
}


class VWAPPullback(Strategy):
    name = "s2_vwap_pullback"
    required_timeframes = ["M5"]

    def __init__(self, params: dict | None = None):
        merged = dict(DEFAULT_PARAMS)
        merged.update(params or {})
        merged["filters"] = {**DEFAULT_PARAMS["filters"],
                             **(params or {}).get("filters", {})}
        super().__init__(merged)
        # Kausaler Tages-State: ET-Datum -> gehandelte Richtungen
        self._traded: dict[object, set] = {}

    # ------------------------------------------------------------------ #

    def _session_slice(self, m5: pd.DataFrame, et_now: pd.Timestamp) -> pd.DataFrame:
        """Bars der laufenden ET-Session (heute ab vwap_start) bis jetzt."""
        local = m5.index.tz_convert(NY_TZ)
        start_t = pd.Timestamp(self.params["vwap_start"]).time()
        mask = (local.normalize() == et_now.normalize()) & (local.time >= start_t)
        return m5[mask]

    def _prev_day_hl(self, m5: pd.DataFrame, et_now: pd.Timestamp):
        """PDH/PDL: High/Low des vorangegangenen ET-Handelstags."""
        local = m5.index.tz_convert(NY_TZ)
        prev = m5[local.normalize() < et_now.normalize()]
        if prev.empty:
            return None, None
        prev_local = prev.index.tz_convert(NY_TZ)
        last_day = prev_local.normalize()[-1]
        day = prev[prev_local.normalize() == last_day]
        return float(day["high"].max()), float(day["low"].min())

    # ------------------------------------------------------------------ #

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Optional[Signal]:
        p = self.params
        f = p["filters"]
        m5 = bars["M5"].iloc[: i + 1]
        if i < 1 or len(m5) < p["atr_len"] + 2:
            return None
        t = m5.index[i]
        et = ny_time(t)

        # Zeitfenster (ET, DST-sicher via zoneinfo)
        start_t = pd.Timestamp(p["entry_start"]).time()
        last_t = pd.Timestamp(p["last_trigger"]).time()
        if not (start_t <= et.time() <= last_t):
            return None

        # Engine-seitige Gates nur abfragen
        if p.get("news_blackout", False):
            return None
        if f["spread_guard"] and float(p.get("current_spread_points", 0.0)) > f["max_spread_points"]:
            return None
        if f["friday_short_bias"] and et.weekday() == 4:
            long_allowed = False
        else:
            long_allowed = True

        day = et.normalize()
        traded = self._traded.setdefault(day, set())

        # Session-VWAP ab 9:30 ET (tick_volume-gewichtet)
        sess = self._session_slice(m5, et)
        if len(sess) < p["min_closes"] + 2:
            return None
        vwap = vwap_session(sess, NY_TZ)

        # Kontext: >= min_closes Closes über/unter VWAP seit 9:45 ET
        ctx_start = pd.Timestamp(p["context_start"]).time()
        sess_local = sess.index.tz_convert(NY_TZ)
        ctx = sess[sess_local.time >= ctx_start]
        ctx_vwap = vwap.loc[ctx.index]
        buf = p["trend_buffer_pct"] / 100.0
        n_above = int((ctx["close"] > ctx_vwap * (1 + buf)).sum())
        n_below = int((ctx["close"] < ctx_vwap * (1 - buf)).sum())

        rsi_now = float(rsi(m5["close"], p["rsi_len"]).iloc[-1])
        rsi_prev = float(rsi(m5["close"], p["rsi_len"]).iloc[-2])
        atr_now = float(atr(m5, p["atr_len"]).iloc[-1])
        if np.isnan(rsi_prev) or np.isnan(atr_now) or atr_now <= 0:
            return None

        # Setup-Bar j = i-1, Trigger-Bar = i
        j = m5.index[-2]
        if j not in vwap.index:
            return None
        vwap_j = float(vwap.loc[j])
        vwap_i = float(vwap.iloc[-1])
        bar_j = m5.iloc[-2]
        bar_i = m5.iloc[-1]
        th = p["rsi_th"]

        direction = 0
        if (long_allowed and n_above >= p["min_closes"]
                and float(bar_j["low"]) <= vwap_j and rsi_prev < th
                and float(bar_i["close"]) > vwap_i):
            direction = +1
        elif (n_below >= p["min_closes"]
                and float(bar_j["high"]) >= vwap_j and rsi_prev > 100.0 - th
                and float(bar_i["close"]) < vwap_i):
            direction = -1
        if direction == 0 or direction in traded:
            return None
        if len(traded) >= 2 and (direction not in traded):
            return None  # max 1 Long + 1 Short/Tag

        # SL: atr_mult × ATR14(M5), ref = Signal-Close (Entry = nächste Bar-Open)
        ref = float(bar_i["close"])
        sl_dist = p["atr_mult"] * atr_now
        sl = ref - sl_dist if direction == +1 else ref + sl_dist

        # TP: PDH/PDL, Fallback 2×ATR; Gate RR >= min_rr sonst kein Trade
        tp = None
        tp_used = None
        candidates: list[tuple[str, float]] = []
        if p["tp_mode"] == "pdh":
            pdh, pdl = self._prev_day_hl(m5, et)
            lvl = pdh if direction == +1 else pdl
            if lvl is not None:
                candidates.append(("pdh" if direction == +1 else "pdl", float(lvl)))
            fb = p["tp_fallback_atr"] * atr_now
            candidates.append((f"{p['tp_fallback_atr']:g}atr_fallback",
                               ref + fb if direction == +1 else ref - fb))
        else:
            mult = float(str(p["tp_mode"]).replace("atr", ""))
            candidates.append((p["tp_mode"],
                               ref + mult * atr_now if direction == +1
                               else ref - mult * atr_now))
        for label, level in candidates:
            rr = ((level - ref) if direction == +1 else (ref - level)) / sl_dist
            if rr >= p["min_rr"]:
                tp = float(level)
                tp_used = label
                break
        if tp is None:
            return None

        traded.add(direction)

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
                "tp_mode": p["tp_mode"],
                "tp_used": tp_used,
                "time_exit": p["time_exit"],          # 11:30 ET hart
                "time_exit_tz": NY_TZ,
                "eod_flat": p["eod_flat"],            # 16:55 ET
                "trail": None,                        # kein Trailing
                "vwap": vwap_i,
                "rsi2": rsi_prev,
                "rsi2_trigger": rsi_now,
                "atr": atr_now,
                "context_closes": n_above if direction == +1 else n_below,
                "trades_today": sorted(traded),
                "filters": dict(f),
                "news_filter": f["news_filter"],
                "news_blackout": None,                # wird engine-seitig gefüllt
                "spread_guard_points": f["max_spread_points"],
            },
        )
