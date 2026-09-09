"""strategies/s8_dayflow_vwap_relay.py — S8 DayFlow VWAP Relay (Forex Majors, M5).

Portierung von "DayFlow VWAP Relay — Majors" (TradingView, Pine v6, Autor
exlux, MPL-2.0) in dieses Framework. Kernmechanik unveraendert: Daily-
Anchored-VWAP mit Stdev-Baendern, Regime-Split ueber ``expansion`` (rollierendes
Verhaeltnis Residual-Stdev / Preis-Stdev) — ruhiger Tag ("balanced") fadet an
den Residual-Perzentilen, expandierender Tag ("trend") folgt dem VWAP-Band-
Ausbruch. Mikro-Flow-Bestaetigung und ATR-Bracket wie im Original.

Zwei Korrekturen gegenueber dem Original (SPEC-Review vor dem WFA-Test):

1. SL/TP werden EINMALIG bei Signal-Erzeugung aus dem ATR der Signal-Bar
   berechnet (``Signal.stop_loss/take_profit``) und danach vom Backtester
   fix gehalten — im Original wurde die Bracket-Order jede Bar aus dem
   dann AKTUELLEN ATR neu gezogen (``strategy.exit(...)`` pro Bar erneut
   aufgerufen), wodurch Stop/Ziel waehrend der Trade-Laufzeit mit der
   Volatilitaet mitwanderten. Diese Klasse kennt nur "SL/TP bei Entry" —
   das ist hier keine bewusste Design-Entscheidung, sondern eine Eigenschaft
   der Engine (core/backtester.py haelt ``_Position.sl/tp`` fix), die den
   Fehler automatisch ausschliesst.
2. Explizites EOD-Flatten ueber die Risk-Engine (``risk.eod_flat`` +
   ``eod_flat_time_utc`` in der Config) ergaenzt — im Original endete der
   Session-Filter nur neue Entries, eine offene Position konnte unbegrenzt
   (auch uebers Wochenende) weiterlaufen. Fuer Intraday-/Prop-Firm-Nutzung
   ist das Pflicht.

Weitere Abweichung (Datengrundlage, nicht Designentscheidung): Das Original
bestaetigt Signale ueber einen "Micro Flow"-Score aus 1-Minuten-Daten
(``request.security_lower_tf``). Fuer keines der Forex-Majors liegen hier
M1-Daten vor (kleinste verfuegbare Aufloesung: M5 = Primary-TF selbst). Der
Mikro-Flow wird daher als kurzfristiger Vorzeichen-Mittelwert der letzten
``micro_span`` PRIMARY-Bars approximiert (funktional aequivalent: "ist die
juengste Kursbewegung noch in Signalrichtung?"), nicht aus echten Sub-Bars.

Dritte Abweichung (Datengrundlage): Die "VWAP" ist bei fehlendem Volumen ein
TWAP (Time-Weighted, Gewicht 1 je Bar). ``tick_volume`` ist in diesem Projekt
bei allen M5-Reihen und bei GBPUSD auch H1 durchgaengig 0 (Dukascopy/HistData-
Quelle ohne Volumen) — nur die MT5-gefetchten H1-Reihen (XAUUSD/USDJPY) haben
echtes Volumen. Fehlt es, faellt der Gewichtungsfaktor automatisch auf 1.0
zurueck (s. ``_step``).

Ebenfalls vereinfacht: das Original erlaubt sofortiges Flip-Reversal
(Short-Signal schliesst offene Long-Position direkt). Hier gilt wie bei
S4/S5 ``risk.max_concurrent: 1`` — ein neues Gegensignal kann erst nach
Schliessung der laufenden Position (SL/TP/EOD) oeffnen.

Performance-Hinweis: Alle Kennzahlen werden INKREMENTELL gepflegt (O(1)
bzw. O(sig_len) pro Bar-Aufruf) statt bei jedem ``on_bar`` neu ueber ein
Roll-Fenster berechnet zu werden — bei Forex-Majors mit oft >100k M5-Bars
waere eine Neuberechnung pro Bar O(n x Fenster) und in der WFA (viele
Fold x Parameter-Kombis) praktisch nicht mehr rechenbar (dieselbe Klasse
Fehler wie der schon behobene O(n^2)-fair_value_gaps-Bug).
"""
from __future__ import annotations

import logging
from collections import deque

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

from strategies.base import Signal, Strategy, in_session as _in_session

_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


class _WilderATR:
    """Inkrementelle ATR nach Wilder — SMA-Seed wie core.indicators._wilder_smooth,
    danach O(1)-Update pro Bar statt Neuberechnung ueber ein Fenster."""

    def __init__(self, n: int):
        self.n = n
        self._seed_buf: list[float] = []
        self._prev_close: float | None = None
        self.value: float | None = None

    def update(self, h: float, l: float, c: float) -> float | None:
        tr = (h - l) if self._prev_close is None else max(
            h - l, abs(h - self._prev_close), abs(l - self._prev_close)
        )
        self._prev_close = c
        if self.value is not None:
            self.value = (self.value * (self.n - 1) + tr) / self.n
            return self.value
        self._seed_buf.append(tr)
        if len(self._seed_buf) >= self.n:
            self.value = sum(self._seed_buf) / len(self._seed_buf)
        return self.value


class S8DayflowVwapRelay(Strategy):
    name = "s8_dayflow_vwap_relay"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "GBPUSD")
        self.primary_tf = p.get("primary_tf", "M5")
        self.required_timeframes = [self.primary_tf]
        self.bar_minutes = _TF_MINUTES[self.primary_tf]

        # Setup / Regime
        self.sig_len = int(p.get("sig_len", 63))
        self.stdev_mult = float(p.get("stdev_mult", 1.0))
        self.exp_gate = float(p.get("exp_gate", 0.65))

        # Mikro-Flow (Approximation auf Primary-TF, s. Docstring)
        self.micro_span = int(p.get("micro_span", 10))
        self.micro_gate = float(p.get("micro_gate", 0.20))

        # Session (UTC, halboffen [start, end))
        self.sess_start = p.get("sess_start", "07:00")
        self.sess_end = p.get("sess_end", "17:00")

        # Risiko / Exit
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr = float(p.get("sl_atr", 1.2))
        self.tp_atr = float(p.get("tp_atr", 1.8))
        self.cooldown_bars = int(p.get("cooldown_bars", 10))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        # -- Inkrementeller Zustand (pro Bar aktualisiert, s. Docstring) -----
        self._day = None
        self._cum_pv = 0.0
        self._cum_v = 0.0
        self._cum_dev2 = 0.0
        self._atr = _WilderATR(self.atr_len)
        self._buf_close: deque[float] = deque(maxlen=self.sig_len)
        self._buf_resid: deque[float] = deque(maxlen=self.sig_len)
        self._buf_sign: deque[float] = deque(maxlen=self.micro_span)
        self._prev_close_bar: float | None = None
        self._last_exit_time: pd.Timestamp | None = None

    # -- State-Hook ---------------------------------------------------------
    def on_trade_closed(self, trade: dict) -> None:
        self._last_exit_time = trade.get("exit_time")

    def _cool_ok(self, ts: pd.Timestamp) -> bool:
        if self._last_exit_time is None:
            return True
        return (ts - self._last_exit_time) >= pd.Timedelta(
            minutes=self.bar_minutes * self.cooldown_bars
        )

    # -- Inkrementelles Update je Bar (IMMER aufrufen, auch ausserhalb Session) --
    def _step(self, ts: pd.Timestamp, o: float, h: float, l: float, c: float,
              vol: float) -> dict | None:
        day = ts.date()
        if day != self._day:
            self._day = day
            self._cum_pv = 0.0
            self._cum_v = 0.0
            self._cum_dev2 = 0.0

        # Fallback TWAP statt VWAP, wenn kein echtes Volumen vorliegt (Dukascopy/
        # HistData-M5-Reihen in diesem Projekt fuehren durchgaengig tick_volume=0,
        # anders als die MT5-gefetchten H1-Reihen fuer XAUUSD/USDJPY — s. Docstring).
        w = vol if vol > 0 else 1.0
        tp = (h + l + c) / 3.0
        self._cum_pv += tp * w
        self._cum_v += w
        if self._cum_v <= 0:
            return None
        vwap = self._cum_pv / self._cum_v
        dev2 = w * (tp - vwap) ** 2
        self._cum_dev2 += dev2
        variance = self._cum_dev2 / self._cum_v
        stdev = np.sqrt(max(variance, 0.0))
        vup = vwap + self.stdev_mult * stdev
        vdn = vwap - self.stdev_mult * stdev
        resid = c - vwap

        atr_val = self._atr.update(h, l, c)

        sign = 0.0 if self._prev_close_bar is None else float(np.sign(c - self._prev_close_bar))
        self._prev_close_bar = c
        self._buf_sign.append(sign)
        self._buf_close.append(c)
        self._buf_resid.append(resid)

        if (
            atr_val is None
            or len(self._buf_close) < self.sig_len
            or len(self._buf_sign) < self.micro_span
        ):
            return None

        closes = np.fromiter(self._buf_close, dtype="float64", count=len(self._buf_close))
        resids = np.fromiter(self._buf_resid, dtype="float64", count=len(self._buf_resid))
        idx = np.arange(len(closes), dtype="float64")

        # vwap-Historie ist nicht separat gepuffert, aber rekonstruierbar:
        # resid = close - vwap wurde bei jedem Append aus dem DAMALIGEN vwap
        # gebildet -> vwaps = closes - resids reproduziert die vwap-Reihe exakt.
        vwaps = closes - resids
        var_idx = float(idx.var())
        v_slope = 0.0 if var_idx == 0 else float(np.cov(idx, vwaps, bias=True)[0, 1] / var_idx)
        res_hi = float(np.quantile(resids, 0.75))
        res_lo = float(np.quantile(resids, 0.25))
        resid_std = float(resids.std(ddof=0))
        close_std = float(closes.std(ddof=0))
        expansion = resid_std / max(close_std, 1e-10)
        mf = float(np.mean(self._buf_sign))

        return {
            "vwap": vwap, "vup": vup, "vdn": vdn, "resid": resid,
            "res_hi": res_hi, "res_lo": res_lo, "expansion": expansion,
            "v_slope": v_slope, "mf": mf, "atr": atr_val, "close": c,
        }

    # -- Hauptlogik -----------------------------------------------------------
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        ts = df.index[i]
        row = df.iloc[i]
        vals = self._step(
            ts, float(row["open"]), float(row["high"]), float(row["low"]),
            float(row["close"]), float(row["tick_volume"]),
        )
        if vals is None:
            return None
        if not _in_session(ts, "UTC", self.sess_start, self.sess_end):
            return None
        if not self._cool_ok(ts):
            return None

        balanced = vals["expansion"] < self.exp_gate
        c = vals["close"]

        long_fade = balanced and vals["resid"] <= vals["res_lo"] and vals["mf"] > self.micro_gate
        short_fade = balanced and vals["resid"] >= vals["res_hi"] and vals["mf"] < -self.micro_gate
        long_break = (not balanced) and c > vals["vup"] and vals["v_slope"] > 0 and vals["mf"] > self.micro_gate
        short_break = (not balanced) and c < vals["vdn"] and vals["v_slope"] < 0 and vals["mf"] < -self.micro_gate

        if long_fade or long_break:
            direction = 1
        elif short_fade or short_break:
            direction = -1
        else:
            return None

        a = vals["atr"]
        if not (a > 0):
            return None
        if direction == 1:
            sl = c - a * self.sl_atr
            tp = c + a * self.tp_atr
        else:
            sl = c + a * self.sl_atr
            tp = c - a * self.tp_atr

        meta = {
            "regime": "balanced" if balanced else "trend",
            "signal_kind": "fade" if (long_fade or short_fade) else "breakout",
            "resid": vals["resid"], "expansion": vals["expansion"],
            "vwap": vals["vwap"], "micro_flow": vals["mf"],
        }
        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta=meta, expires_bars=0,
        )
