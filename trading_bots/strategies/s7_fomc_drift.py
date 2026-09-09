"""S7 — FomcDrift (EURUSD, H1). SPEC §5-analog (new strategy, not yet in
SPEC.md — see "Phase-1 finding" note below).

Evidence base: Lucca & Moench (2015), "The Pre-FOMC Announcement Drift"
(Journal of Finance) documents systematic pre-announcement equity drift
building in the hours before scheduled FOMC decisions; FX-specific
follow-on work finds an analogous EUR/USD-specific pre-FOMC drift. This
strategy captures only the SAME-DAY, intraday slice of that published
multi-day effect: this portfolio's risk rules require flat-by-close /
no-overnight-hold (SPEC §4.3 eod_flat/friday_flat), so a position can never
be carried into the next day the way the academic full-effect measurement
does. The mechanical rule below is therefore a deliberately narrowed,
same-day-only proxy for the published effect, not a replication of its
full magnitude.

Data source for FOMC decision dates/times (Phase-1 finding): core/news_filter.py
(SPEC §4.7) only ever holds the ForexFactory *rolling weekly* feed
(``ff_calendar_thisweek.xml``) — live "this week" data, re-fetched at most
once/day, with NO multi-year historical archive anywhere in this repo
(``data/`` has no news/calendar cache). It is therefore NOT usable as-is
for a 2019-2026 backtest date source. It DOES already parse a `title`
field that could distinguish "FOMC" from "Non-Farm"/"CPI" by keyword
(see ``TIER1_KEYWORDS``), but that capability is moot without historical
rows to apply it to.

Because the FOMC's rate-decision calendar is small, static, and directly
published by the Fed itself, this strategy instead loads a **new, one-time,
hand-curated static file**, ``data/fomc_dates.csv`` (created for this
strategy — see that file's header for the exact federalreserve.gov URLs
used and the verification method, incl. a cross-check that caught and
excluded a hallucinated single-source date). This is INTENTIONALLY
independent of core/news_filter.py's live/rolling infrastructure — the two
serve different purposes (weekly blackout gating vs. a fixed historical
backtest calendar) and mixing them would make this strategy silently
depend on news_filter's live-fetch/cache lifecycle, which SPEC §4.7 never
guarantees to hold multi-year history.

Mechanical rule (rein kausal, nur geschlossene H1-Bars; same-day-only,
continuation/drift, NOT reversal):
  1. On each FOMC decision day (from ``data/fomc_dates.csv``), at the
     Europe/London session open (08:00 London-local, DST-safe via
     zoneinfo — chosen over NY open because London open is this project's
     and the wider FX market's standard EUR/USD trading-day anchor; S2/S3/S5
     anchor USD-instrument sessions to America/New_York, but none of them
     anchors EURUSD specifically, so there is no existing in-repo precedent
     either way here — London open is documented as the deliberate choice),
     record that H1 bar's open price as the session anchor.
  2. At ``entry_check_hour`` hours before the scheduled decision time,
     measure the move from the session-open anchor to that bar's close.
  3. If |move| > ``min_momentum`` x ATR(H1,10), enter a market order in the
     direction of that move (continuation).
  4. Stop = ``stop_mult`` x ATR(H1,10) from the (expected) entry price.
     No take-profit — this is a time/structure exit only (Signal §4.1:
     take_profit=None).
  5. Exit unconditionally >= ``exit_buffer_min`` minutes before the
     scheduled decision time, no exception — realised via the backtester's
     existing ``meta["time_exit_bars"]`` mechanism (SPEC §4.2/core/
     backtester.py), computed exactly at signal time from the known
     decision timestamp: the *last* H1 bar whose close is still
     <= (decision_time - exit_buffer_min). Because H1 bars only close on
     the hour and decision times are always exactly on the hour (2:00pm ET
     converts to a whole-hour UTC time year-round), this is an exact,
     deterministic bar count, not an approximation. If even the very first
     post-entry bar close would already violate the buffer (structurally
     possible at the low end of entry_check_hour's 2-6h range, since the
     engine fills market orders at the OPEN of the bar *after* the signal
     bar — SPEC §4.2 — eating exactly 1h of the check-to-decision window),
     the trade is skipped rather than risking a same-bar-as-decision exit.

Parameters (4, all WFO-tunable): entry_check_hour, min_momentum, stop_mult,
exit_buffer_min. ATR length (10) and the London-open session anchor are
fixed design choices per the spec, not exposed as free parameters.

Instrument: EURUSD only, H1. Risk: 0.5%/trade (SPEC §0/§4.3 standard).
Magic: 20260907 (S1-S6 = 20260901-06; see AGENTS.md registry).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# core-Imports mit Fallback (SPEC §4.1/§4.5 — parallele Entwicklung)
# ---------------------------------------------------------------------------
try:  # SPEC §4.1
    from strategies.base import Signal, Strategy  # type: ignore
except ImportError:  # Fallback exakt nach SPEC §4.1

    @dataclass
    class Signal:  # type: ignore[no-redef]
        time: pd.Timestamp
        symbol: str
        direction: int
        entry_type: str
        entry_price: float | None
        stop_loss: float
        take_profit: float | None
        risk_pct: float
        meta: dict
        expires_bars: int = 0

    class Strategy(ABC):  # type: ignore[no-redef]
        name: str
        params: dict

        def __init__(self, params: dict):
            self.params = params

        @abstractmethod
        def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> "Signal | None":
            ...

        def on_trade_closed(self, trade: dict) -> None:
            ...

try:  # SPEC §4.5
    from core.indicators import atr as _core_atr  # type: ignore
except ImportError:
    _core_atr = None


def _wilder_atr(df: pd.DataFrame, n: int) -> pd.Series:
    """Fallback fuer core.indicators.atr — identische Semantik (Seed = SMA
    der ersten n TR-Werte, danach Wilder-Rekursion)."""
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    v = tr.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan, dtype="float64")
    if len(v) >= n:
        prev = float(np.mean(v[:n]))
        out[n - 1] = prev
        for t in range(n, len(v)):
            prev = (prev * (n - 1) + v[t]) / n
            out[t] = prev
    return pd.Series(out, index=df.index, dtype="float64")


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    if _core_atr is not None:
        return _core_atr(df, n)
    return _wilder_atr(df, n)


LONDON_TZ = ZoneInfo("Europe/London")
NY_TZ = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

DEFAULT_FOMC_DATES_FILE = "data/fomc_dates.csv"


# ---------------------------------------------------------------------------
# FOMC-Termine laden (Phase-1: statische, verifizierte Fed-Quelle — siehe
# data/fomc_dates.csv Header. NICHT core/news_filter.py — dessen Cache haelt
# nur die rollierende FF-Wochensicht, keine Mehrjahres-Historie.)
# ---------------------------------------------------------------------------
def load_fomc_decisions(path: str | Path = DEFAULT_FOMC_DATES_FILE) -> dict[_date, pd.Timestamp]:
    """Laedt ``data/fomc_dates.csv`` -> {decision_date: decision_ts_utc}.

    Zeiten stehen als America/New_York-Lokalzeit in der Datei und werden
    hier DST-sicher via zoneinfo nach UTC konvertiert (niemals fester
    UTC-Offset, AGENTS.md Regel #1).
    """
    df = pd.read_csv(path, comment="#")
    out: dict[_date, pd.Timestamp] = {}
    for _, row in df.iterrows():
        d = datetime.strptime(str(row["date"]).strip(), "%Y-%m-%d").date()
        hh, mm = (str(row["time_et"]).strip().split(":"))
        local = datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=NY_TZ)
        out[d] = pd.Timestamp(local).tz_convert("UTC")
    return out


# ---------------------------------------------------------------------------
# Strategie
# ---------------------------------------------------------------------------
class S7FomcDrift(Strategy):
    name = "s7_fomc_drift"
    required_timeframes = ["H1"]

    # Fixiertes ATR-Fenster laut Regelwerk (nicht WFO-Parameter).
    ATR_LEN = 10

    # Europe/London Session-Open-Stunde (lokal, DST-sicher via zoneinfo) —
    # fixierte Design-Entscheidung, kein Parameter (siehe Modul-Docstring
    # fuer die Begruendung: kein bestehendes S2/S3/S5-Praezedens fuer
    # EURUSD-Session-Anker, London-Open ist der FX-Marktstandard).
    LONDON_OPEN_HOUR = 8

    # Performance-Hinweis (Muster aus strategies/s3_silver_bullet.py
    # LOOKBACK_BARS, SPEC-Vorgabe: nicht denselben O(n^2)-Bug reproduzieren):
    # ANDERS als S3 ruft on_bar() hier _atr() NICHT auf jeder Bar auf,
    # sondern nur an den ~63 FOMC-Check-Bars der gesamten 2019-2026-Historie
    # (alle anderen Bars sind ein O(1) Dict-Lookup auf self._decisions und
    # geben sofort None zurueck) — die S3-Bedingung fuer das O(n^2)-Problem
    # (teure Funktion auf jeder wachsenden View-Bar) liegt hier strukturell
    # nicht vor. ATR_VIEW_BARS deckelt die an _atr() uebergebene View
    # trotzdem defensiv (billige Absicherung, falls die Engine irgendwann
    # sehr grosse Warmup-Views liefert): 12 x ATR_LEN(=10) ist der Wilder-
    # Seed-Washout-Punkt (Praezedens: core/backtester.py-Kommentar in
    # s5_filtered_mr.py), 300 H1-Bars (~12 Handelstage) liegt weit darueber
    # und deckt zugleich den Session-Open-Anker desselben Tages sicher ab.
    ATR_VIEW_BARS = 300

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "EURUSD")
        self.risk_pct = float(p.get("risk_pct", 0.005))

        # --- Die 4 WFO-Parameter -------------------------------------------------
        self.entry_check_hour = int(p.get("entry_check_hour", 4))       # 2-6
        self.min_momentum = float(p.get("min_momentum", 0.5))           # 0.3-1.0 x ATR
        self.stop_mult = float(p.get("stop_mult", 0.4))                 # 0.3-0.6 x ATR
        self.exit_buffer_min = int(p.get("exit_buffer_min", 15))        # 10-20 Min

        fomc_dates_file = p.get("fomc_dates_file", DEFAULT_FOMC_DATES_FILE)
        decisions = p.get("fomc_decisions_obj")  # Injektion fuer Tests
        self._decisions: dict[_date, pd.Timestamp] = (
            dict(decisions) if decisions is not None else load_fomc_decisions(fomc_dates_file)
        )

        # Pro FOMC-Termin vorab abgeleitete Zeitstempel (UTC) — kein
        # Session-Scan noetig, da London-Open und Check-Zeit direkt aus dem
        # Kalenderdatum berechenbar sind (DST-sicher via zoneinfo).
        self._session_open_ts: dict[_date, pd.Timestamp] = {}
        self._check_ts: dict[_date, pd.Timestamp] = {}
        for d, decision_ts in self._decisions.items():
            london_open_local = datetime(
                d.year, d.month, d.day, self.LONDON_OPEN_HOUR, 0, tzinfo=LONDON_TZ
            )
            self._session_open_ts[d] = pd.Timestamp(london_open_local).tz_convert("UTC")
            self._check_ts[d] = decision_ts - pd.Timedelta(hours=self.entry_check_hour)

        # State: session-open Anker je Kalendertag (gefuellt sobald die
        # London-Open-Bar durchlaeuft).
        self._session_open_price: dict[_date, float] = {}
        # Verhindert Doppel-Signale, falls on_bar fuer denselben Check-
        # Zeitstempel mehrfach aufgerufen wird (sollte im Backtester nicht
        # passieren, ist aber eine billige Absicherung).
        self._signalled: set[_date] = set()

    # -- Hauptlogik -------------------------------------------------------------
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars["H1"]
        if i < 0 or i >= len(df):
            return None
        ts_open = df.index[i]          # UTC, Bar-Open; Bar gerade geschlossen
        ts_close = ts_open + pd.Timedelta(hours=1)
        day = ts_open.date()

        if day not in self._decisions:
            return None  # kein FOMC-Tag -> billiger Dict-Lookup, sofort raus

        # -- (1) Session-Open-Anker einsammeln ---------------------------------
        if ts_open == self._session_open_ts.get(day):
            self._session_open_price[day] = float(df["open"].iloc[i])

        # -- (2)-(5) Check-Bar: Momentum pruefen, ggf. Signal -------------------
        if ts_close != self._check_ts.get(day):
            return None
        if day in self._signalled:
            return None
        anchor = self._session_open_price.get(day)
        if anchor is None:
            return None  # kein Session-Open-Bar in den Daten (Luecke) -> skip

        view = df.iloc[max(0, i + 1 - self.ATR_VIEW_BARS): i + 1]
        atr_s = _atr(view, self.ATR_LEN)
        atr_now = float(atr_s.iloc[-1])
        if not np.isfinite(atr_now) or atr_now <= 0:
            return None

        close = float(df["close"].iloc[i])
        move = close - anchor
        if abs(move) <= self.min_momentum * atr_now:
            return None  # Momentum-Gate nicht erfuellt

        direction = 1 if move > 0 else -1

        # -- Unconditional Flatten-Deadline (kein Ausnahme) --------------------
        decision_ts = self._decisions[day]
        deadline = decision_ts - pd.Timedelta(minutes=self.exit_buffer_min)
        entry_time = ts_close  # Market-Fill = Open der naechsten Bar (SPEC §4.2)
        # Anzahl volle Stunden von entry_time bis deadline; H1-Bars liegen
        # exakt auf der Stunde, decision_ts ist es ebenfalls (14:00 ET ist
        # ganzjaehrig eine volle UTC-Stunde) -> exakte, nicht approximierte
        # Rechnung (siehe Modul-Docstring).
        hours_to_deadline = (deadline - entry_time) / pd.Timedelta(hours=1)
        full_hours = int(np.floor(hours_to_deadline))
        time_exit_bars = full_hours - 1  # letzte Bar, deren CLOSE <= deadline liegt
        if time_exit_bars < 0:
            return None  # selbst die erste post-Entry-Bar wuerde den Puffer verletzen

        self._signalled.add(day)
        ref_price = close  # Referenz fuer SL; Fill = Open der naechsten Bar
        sl = ref_price - direction * self.stop_mult * atr_now

        return Signal(
            time=ts_open,
            symbol=self.symbol,
            direction=direction,
            entry_type="market",
            entry_price=None,  # Engine: Open der naechsten Bar
            stop_loss=sl,
            take_profit=None,  # nur Time-Exit (Signal §4.1)
            risk_pct=self.risk_pct,
            meta={
                "strategy": self.name,
                "fomc_decision_date": str(day),
                "fomc_decision_time_utc": decision_ts.isoformat(),
                "check_time_utc": ts_close.isoformat(),
                "session_open_utc": self._session_open_ts[day].isoformat(),
                "session_open_price": anchor,
                "move": move,
                "atr": atr_now,
                "entry_check_hour": self.entry_check_hour,
                "min_momentum": self.min_momentum,
                "stop_mult": self.stop_mult,
                "exit_buffer_min": self.exit_buffer_min,
                "time_exit_bars": time_exit_bars,
                "flatten_deadline_utc": deadline.isoformat(),
            },
        )
