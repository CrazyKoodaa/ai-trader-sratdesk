"""S6 — FixReversal (WM/Reuters 4pm London Fix Reversal). Neuer Bot, nicht in
SPEC.md §5 enthalten (SPEC-Version 1.0 kennt nur S1-S5) — Regelwerk stammt aus
dem Research-Brief, das diesen 6. Bot begruendet (Krohn 2024, Journal of
Finance, "Foreign Exchange Fixings and Returns around the Clock").

Symbole: GBPUSD, AUDUSD, NZDUSD, USDCAD (Timeframe M5). Dieselbe Regel und
derselbe Parametersatz laeuft identisch ueber alle vier Paare — KEIN
Pair-Sonderfall im Code (Absicht: kombinierte Trade-Anzahl fuer die
Walk-Forward-Gates, siehe SPEC §7).

Mechanik (rein kausal, nur geschlossene M5-Bars):
  1. Fix-Zeitpunkt = 16:00 Europe/London LOKALZEIT (via zoneinfo — NIEMALS
     fester UTC-Offset; BST/GMT-Wechsel verschiebt die UTC-Uhrzeit des Fixes
     um eine Stunde, SPEC §1/AGENTS.md).
  2. Pre-Fix-Fenster: die ``pre_window_min`` Minuten unmittelbar vor dem Fix
     (Fenster [16:00-pre_window_min, 16:00) London-Lokalzeit). Netto-Move =
     Close der Fix-Bar (schliesst um 16:00 lokal) minus Open der ersten Bar
     des Fensters.
  3. Trigger: |Netto-Move| >= trigger_threshold x ATR(M5, atr_len). ATR
     kommt aus core.indicators.atr (Wilder, vektorisiert).
  4. Entry: Market, GEGEN die Pre-Fix-Bewegung (Fade) — Fuellung am Open der
     naechsten Bar (Engine-Konvention, SPEC §4.2). Signal.time = Open der
     Fix-Bar (wie bei allen anderen Strategien: Signal auf der geschlossenen
     Bar, Fill = naechste Bar).
  5. Stop: jenseits des Pre-Fix-Extrems (High bei Fade-Short, Low bei
     Fade-Long) + stop_buffer x ATR.
  6. Target: target_r x R (R = Stop-Distanz, SPEC-Konvention wie bei
     S1/S2/S3/S5).
  7. Time-Exit: ueber ``meta["time_exit_bars"]`` an die Risk-Engine deklariert
     (core/backtester.py::_close_position via ``pos.time_exit_bars`` — die
     Strategie flatten NICHT selbst, siehe core/backtester.py Zeile ~436).
  8. News-Filter: optional injizierbares NewsFilter-Objekt (gleiches Muster
     wie strategies/s5_filtered_mr.py: ``news_filter_obj``-Param,
     ``use_news_filter``-Flag) — blockiert das Setup, wenn ein High-Impact-
     Event in das Pre-Fix-Fenster faellt.
  9. Max 1 Trade/Tag/Symbol (London-Kalendertag; State ``self._day`` /
     ``self._traded_today``, Muster wie S3/S4).

Design-Entscheidung RR-Gate (nicht in Research-Brief fixiert): ``target_r``
ist ein WFO-Parameter im Bereich 0.5-1.5 (Fade-Setup: schneller Teil-
Retrace, KEIN Trendfolge-Ziel) — SPEC-Default fuer RiskConfig.min_rr ist 2.0
(SPEC §4.3), was bei target_r<2.0 IMMER blockieren wuerde. configs/
s6_fix_reversal.yaml deklariert daher zwei getrennte Werte: ``risk.min_rr:
2.0`` (RiskConfig-Dokumentationsfeld, wie bei S1/S4/S5 von der Engine nicht
erzwungen) und ``params.min_rr`` (der tatsaechliche Setup-Gate hier im Code,
Default 0.5 = Untergrenze von target_r) — der Gate-Mechanismus selbst folgt
exakt der S2/S3-Konvention (rr gegen min_rr pruefen, sonst kein Trade).

Performance (siehe strategies/s3_silver_bullet.py::LOOKBACK_BARS-Kommentar
fuer den Hintergrund): on_bar() wird fuer JEDE M5-Bar aufgerufen, aber die
teure Berechnung (ATR + Pre-Fix-Fenster-Scan) laeuft nur auf der EINEN
Fix-Bar pro Tag — trotzdem wird die dafuer uebergebene View auf
LOOKBACK_BARS gedeckelt (nie ``df.iloc[:i+1]`` unbegrenzt), weil sonst die
View mit wachsendem i linear waechst und die Gesamtkosten ueber alle
Fix-Events hinweg quadratisch in der Bar-Anzahl blieben (n_tage x n_bars),
selbst wenn core.indicators.atr() selbst vektorisiert ist. Siehe
tests/test_s6.py::test_lookback_bound_matches_unbounded_view.
"""
from __future__ import annotations

from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .base import Signal, Strategy, atr

LONDON_TZ = "Europe/London"

DEFAULT_PARAMS: dict = {
    "symbol": "GBPUSD",
    "risk_pct": 0.005,
    # RR-Gate (siehe Design-Entscheidung im Modul-Docstring) — NICHT
    # identisch mit configs/s6_fix_reversal.yaml::risk.min_rr (SPEC-Default,
    # Dokumentationsfeld, von der Engine nicht erzwungen).
    "min_rr": 0.5,
    # --- Fix-Definition (Europe/London-Lokalzeit, DST-sicher via zoneinfo) ---
    "fix_time": "16:00",
    "fix_tz": LONDON_TZ,
    # --- WFO-Parameter (5, siehe Research-Brief) ---
    "pre_window_min": 15,        # 10-20
    "trigger_threshold": 1.25,   # 0.5-2.0 (x ATR)
    "stop_buffer": 0.35,         # 0.2-0.5 (x ATR)
    "target_r": 1.0,             # 0.5-1.5 (R = Stop-Distanz)
    "max_hold_min": 30,          # 15-45
    # --- ATR (fix, kein WFO-Parameter) ---
    "atr_len": 20,
    # --- News-Filter (SPEC §6/§4.7, optional injizierbar wie S5) ---
    "use_news_filter": True,
    "news_filter_obj": None,
}


class S6FixReversal(Strategy):
    name = "s6_fix_reversal"
    required_timeframes = ["M5"]

    # Siehe Modul-Docstring "Performance". 2000 M5-Bars (~1 Handelswoche)
    # liegt weit ueber allem, was ATR(atr_len<=~30) und ein Pre-Fix-Fenster
    # von <= 20 Minuten (4 Bars) kausal brauchen: Wilder-ATR ist nach
    # wenigen 100 Bars ausgewaschen (Seed-Einfluss < 1e-10 nach ~1400
    # Rekursionsschritten bei n=20, alpha=1/20 -> (1-alpha)^1400 ~ 0).
    # Numerisch identisch zur ungedeckelten Variante, siehe
    # tests/test_s6.py::test_lookback_bound_matches_unbounded_view.
    LOOKBACK_BARS = 2000

    def __init__(self, params: dict | None = None):
        merged = {**DEFAULT_PARAMS, **(params or {})}
        super().__init__(merged)
        p = self.params
        self.symbol = str(p["symbol"])
        self.risk_pct = float(p["risk_pct"])
        self.min_rr = float(p["min_rr"])
        self.fix_time = str(p["fix_time"])
        self.fix_tz = str(p["fix_tz"])
        self._tz = ZoneInfo(self.fix_tz)
        fh, fm = self.fix_time.split(":")
        self._fix_h, self._fix_m = int(fh), int(fm)
        self._fix_minute_of_day = self._fix_h * 60 + self._fix_m
        self.pre_window_min = int(p["pre_window_min"])
        self._pre_window_bars = max(1, round(self.pre_window_min / 5))
        self.trigger_threshold = float(p["trigger_threshold"])
        self.stop_buffer = float(p["stop_buffer"])
        self.target_r = float(p["target_r"])
        self.max_hold_min = int(p["max_hold_min"])
        self.atr_len = int(p["atr_len"])
        self.use_news_filter = bool(p["use_news_filter"])
        self.news_filter = p.get("news_filter_obj")
        # State: 1 Trade/Tag/Symbol (London-Kalendertag)
        self._day = None
        self._traded_today = False

    # -- News-Filter (Muster wie strategies/s5_filtered_mr.py) --------------
    def _news_blocked(self, ts_window_start: pd.Timestamp, ts_fix: pd.Timestamp) -> bool:
        nf = self.news_filter
        if nf is None or not self.use_news_filter:
            return False
        # Pruefung an Fenster-Start und Fix-Zeitpunkt deckt (mit dem
        # Standard-Blackout-Fenster -15/+10 min, SPEC §4.7) jedes High-
        # Impact-Event ab, dessen Blackout-Fenster das Pre-Fix-Fenster
        # (<= 20 Minuten) ueberschneidet.
        return bool(nf.is_blackout(ts_window_start, self.symbol) or nf.is_blackout(ts_fix, self.symbol))

    # -- Hauptlogik -----------------------------------------------------------
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Optional[Signal]:
        df = bars["M5"]
        ts = df.index[i]  # UTC, Bar-Open; Bar gerade geschlossen
        local_open = ts.tz_convert(self._tz)
        day = local_open.date()
        if self._day != day:
            self._day = day
            self._traded_today = False

        # Fix-Bar = die Bar, die GENAU um 16:00 London-Lokalzeit schliesst
        # (Bar-Open = 15:55 lokal bei fix_time=16:00). DST-sicher: dieselbe
        # Bedingung matcht in BST- und GMT-Wochen dieselbe London-Lokalzeit,
        # auch wenn die UTC-Bar-Zeit sich um eine Stunde verschiebt.
        local_close = local_open + pd.Timedelta(minutes=5)
        if not (local_close.hour == self._fix_h and local_close.minute == self._fix_m):
            return None
        if self._traded_today:
            return None

        # Gedeckelte View (Performance, siehe Modul-Docstring) — NIE
        # df.iloc[:i+1] unbegrenzt an atr() uebergeben.
        lo = max(0, i + 1 - self.LOOKBACK_BARS)
        view = df.iloc[lo: i + 1]

        local_idx = view.index.tz_convert(self._tz)
        minute_of_day = local_idx.hour * 60 + local_idx.minute
        window_start_min = self._fix_minute_of_day - self.pre_window_min
        mask = (
            (local_idx.date == day)
            & (minute_of_day >= window_start_min)
            & (minute_of_day < self._fix_minute_of_day)
        )
        if mask.sum() < self._pre_window_bars:
            return None  # unvollstaendiges Pre-Fix-Fenster (Datenluecke) -> kein Trade
        seg = view[mask]

        window_open = float(seg["open"].iloc[0])
        window_high = float(seg["high"].max())
        window_low = float(seg["low"].min())
        fix_close = float(seg["close"].iloc[-1])  # Close der letzten Fenster-Bar = Fix-Bar-Close
        net_move = fix_close - window_open

        atr_s = atr(view, self.atr_len)
        atr_now = float(atr_s.iloc[-1])
        if not np.isfinite(atr_now) or atr_now <= 0:
            return None

        if abs(net_move) < self.trigger_threshold * atr_now:
            return None  # Pre-Fix-Move zu klein relativ zu ATR -> kein Setup

        if self._news_blocked(seg.index[0], ts):
            return None  # High-Impact-Event im Pre-Fix-Fenster -> Setup ausgesetzt

        # Fade: gegen die Pre-Fix-Bewegung. SL jenseits des Pre-Fix-Extrems
        # in der Richtung, die die Reversal-These widerlegen wuerde.
        if net_move > 0:
            direction = -1  # Rally in den Fix -> Short-Fade
            sl = window_high + self.stop_buffer * atr_now
            risk = sl - fix_close
        else:
            direction = 1   # Sell-off in den Fix -> Long-Fade
            sl = window_low - self.stop_buffer * atr_now
            risk = fix_close - sl
        if risk <= 0:
            return None

        rr = self.target_r  # R = Stop-Distanz (risk); TP wird direkt daraus gebaut -> rr == target_r
        if rr < self.min_rr:
            return None  # RR-Gate (Konvention wie S2/S3, SPEC §4.3)

        tp = fix_close + direction * self.target_r * risk

        self._traded_today = True
        meta = {
            "strategy": self.name,
            "fix_time": self.fix_time,
            "fix_tz": self.fix_tz,
            "pre_window_min": self.pre_window_min,
            "window_open": window_open,
            "window_high": window_high,
            "window_low": window_low,
            "fix_close": fix_close,
            "net_move": net_move,
            "atr": atr_now,
            "trigger_threshold": self.trigger_threshold,
            "stop_buffer": self.stop_buffer,
            "rr": rr,
            "min_rr": self.min_rr,
            "time_exit_bars": max(1, round(self.max_hold_min / 5)),
            "max_hold_min": self.max_hold_min,
            "news_filter": self.use_news_filter,
        }
        return Signal(
            time=ts,
            symbol=self.symbol,
            direction=direction,
            entry_type="market",
            entry_price=None,  # Engine: Open der naechsten Bar
            stop_loss=sl,
            take_profit=tp,
            risk_pct=self.risk_pct,
            meta=meta,
            expires_bars=0,
        )
