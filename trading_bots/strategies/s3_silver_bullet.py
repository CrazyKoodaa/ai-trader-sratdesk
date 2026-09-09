"""S3 — SilverBullet (NAS100 + XAUUSD, M5). SPEC §5/S3 (verbindlich).

Logik (rein kausal, nur geschlossene Bars):
  Fenster (Default 10:00–11:00 America/New_York; Alternativen per Config):
    1. Referenz-Liquiditaet: High/Low der 09:00-ET-Stundenkerze (Alt: Asian-Range).
    2. Sweep: Wick > Level + Close zurueck in Range (Wick-Exzess >= 0.1 x ATR).
    3. MSS/Displacement: Body >= 1.5 x ATR20 UND Body/Range >= 0.7 UND
       bricht Swing-Fraktal k=2 per Close.
    4. FVG >= 0.3 x ATR aus dem Displacement-Leg; Entry = Limit am 50 % CE,
       Expiry 12 Bars.
    5. SL hinter Sweep-Extrem + 0.3 x ATR; TP = Gegen-Liquiditaet, Gate RR >= 2.
    6. Max 1 Trade/Fenster. BE bei 3R optional (Meta-Flag fuer Risk-Engine).
  Filter-Layer: HTF-Bias (H4 letztes BOS/CHoCH) als A/B-Arm (Param htf_bias).

Nutzt core.smc / core.indicators / core.time_engine per SPEC-Signatur, sofern
vorhanden (parallele Entwicklung); sonst lokale kausale Fallbacks mit
identischer Semantik.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# core-Imports mit Fallback (SPEC §4.1/§4.4/§4.5/§4.6 — parallele Entwicklung)
# ---------------------------------------------------------------------------
try:  # SPEC §4.1
    from strategies.base import Signal, Strategy, as_flag  # type: ignore
except ImportError:  # Fallback exakt nach SPEC §4.1

    def as_flag(value, default: bool = False) -> bool:  # type: ignore[no-redef]
        """Fallback-Spiegel von strategies.base.as_flag (YAML on/off-Bool-Bug)."""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in ("on", "true", "yes", "1")

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

try:  # SPEC §4.5: atr(df, n) Wilder; swing_points(df, left, right, confirmed_lag)
    from core.indicators import atr as _core_atr  # type: ignore
    from core.indicators import swing_points as _core_swing_points  # type: ignore
except ImportError:
    _core_atr = None
    _core_swing_points = None

try:  # SPEC §4.6: fair_value_gaps(df, min_size_atr, atr) -> DataFrame
    from core.smc import fair_value_gaps as _core_fvg  # type: ignore
except ImportError:
    _core_fvg = None

try:  # SPEC §4.4
    from core import time_engine as _te  # type: ignore
except ImportError:
    _te = None


# ---------------------------------------------------------------------------
# Fallback-Implementierungen (kausal, gleiche Semantik wie SPEC-Signaturen)
# ---------------------------------------------------------------------------
def _wilder_atr(df: pd.DataFrame, n: int) -> pd.Series:
    """Wilder-ATR (Fallback fuer core.indicators.atr). Kausal.

    Identisch zu core: Seed = SMA der ersten n TR-Werte, danach Rekursion
    atr[t] = (atr[t-1]*(n-1) + tr[t]) / n (erste Bar: TR = high - low).
    """
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


def _fallback_fair_value_gaps(
    df: pd.DataFrame, min_size_atr: float, atr: pd.Series
) -> pd.DataFrame:
    """3-Bar-FVG (Fallback fuer core.smc.fair_value_gaps, SPEC §4.6).

    Semantik identisch zu core.smc (Single Source of Truth):
    Bullish FVG an Bar i: low[i] > high[i-2]  -> Zone [high[i-2], low[i]]
    Bearish FVG an Bar i: high[i] < low[i-2] -> Zone [high[i], low[i-2]]
    formed_at = Bar i (die 3. Bar, an der die Luecke sichtbar wird);
    confirmed_at = formed + 1 Bar (NaT am Datenende). Das Displacement-Leg
    ist die mittlere Bar i-1. Mindestgroesse gegen atr[i].
    """
    cols = ["fvg_top", "fvg_bottom", "direction", "formed_at", "confirmed_at"]
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    a = atr.to_numpy(dtype="float64")
    idx = df.index
    rows: list[tuple] = []
    for i in range(2, len(df)):
        min_size = min_size_atr * a[i] if np.isfinite(a[i]) else np.inf
        confirmed = idx[i + 1] if i + 1 < len(df) else pd.NaT
        if l[i] > h[i - 2]:  # bullish
            if l[i] - h[i - 2] >= min_size:
                rows.append((l[i], h[i - 2], 1, idx[i], confirmed))
        elif h[i] < l[i - 2]:  # bearish
            if l[i - 2] - h[i] >= min_size:
                rows.append((l[i - 2], h[i], -1, idx[i], confirmed))
    return pd.DataFrame(rows, columns=cols)


def _fair_value_gaps(df: pd.DataFrame, min_size_atr: float, atr: pd.Series) -> pd.DataFrame:
    if _core_fvg is not None:
        return _core_fvg(df, min_size_atr, atr)
    return _fallback_fair_value_gaps(df, min_size_atr, atr)


def _local_times(index_utc: pd.DatetimeIndex, tz: str) -> pd.DatetimeIndex:
    """UTC -> lokale Session-Zeit (core.time_engine oder zoneinfo)."""
    if _te is not None and hasattr(_te, "session_window_mask"):
        # session_window_mask wird im Window-Check genutzt; hier nur Konvertierung
        pass
    return index_utc.tz_convert(ZoneInfo(tz))


def _in_window(ts_utc: pd.Timestamp, tz: str, start: str, end: str) -> bool:
    """Fenster-Check in lokaler Session-Zeit (SPEC §4.4, niemals Serverzeit).

    start <= lokale Zeit < end (Ende exklusiv).
    """
    if _te is not None and hasattr(_te, "in_session"):
        return bool(_te.in_session(ts_utc, tz, start, end))
    local = ts_utc.tz_convert(ZoneInfo(tz))
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    mins = local.hour * 60 + local.minute
    return sh * 60 + sm <= mins < eh * 60 + em


def _swing_extremes(
    df: pd.DataFrame, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Kausale Swing-Fraktale k (nutzt core.indicators.swing_points, wenn
    verfuegbar; sonst lokaler Fallback mit identischer Semantik).

    Rueckgabe: (swing_high_price, swing_low_price) als float-Arrays mit NaN,
    Wert jeweils erst am Bestaetigungs-Bar j+k sichtbar
    (confirmed_lag=0 -> Sichtbarkeit nach right=k Bars, SPEC §4.5).
    """
    n = len(df)
    sh = np.full(n, np.nan)
    sl = np.full(n, np.nan)
    if _core_swing_points is not None:
        # core liefert Preise an der Kandidaten-Bar + confirmed_at-Spalten;
        # hier auf "Wert am Bestaetigungs-Bar" umgemappt (gleiche Kausalitaet).
        sw = _core_swing_points(df, left=k, right=k, confirmed_lag=0)
        pos = {t: p for p, t in enumerate(df.index)}
        for vals, conf, out, agg in (
            (sw["swing_high"], sw["swing_high_confirmed_at"], sh, max),
            (sw["swing_low"], sw["swing_low_confirmed_at"], sl, min),
        ):
            mask = vals.notna() & conf.notna()
            for v, ct in zip(vals[mask].to_numpy(), conf[mask]):
                p = pos.get(ct)
                if p is not None:
                    out[p] = float(v) if np.isnan(out[p]) else agg(out[p], float(v))
        return sh, sl
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    for j in range(k, n - k):
        if h[j] == h[j - k : j + k + 1].max() and (h[j] > np.delete(h[j - k : j + k + 1], k)).all():
            sh[j + k] = h[j]
        if l[j] == l[j - k : j + k + 1].min() and (l[j] < np.delete(l[j - k : j + k + 1], k)).all():
            sl[j + k] = l[j]
    return sh, sl


# ---------------------------------------------------------------------------
# Strategie
# ---------------------------------------------------------------------------
class S3SilverBullet(Strategy):
    name = "s3_silver_bullet"
    required_timeframes = ["M5", "H4"]

    # Performance: core.smc.fair_value_gaps() ist ein Python-Loop O(len(df))
    # pro Aufruf; on_bar() ruft ihn (+ _reference_levels/_atr) auf JEDEM
    # Fenster-Bar auf der bis-hierhin gewachsenen View auf. Ohne Deckelung
    # ist der gesamte Backtest O(n^2) in der Bar-Anzahl — bei H1/H4 (wenige
    # 1000ende Bars) unmerklich, bei M5 ueber mehrere Jahre (500k+ Bars)
    # praktisch unbrechenbar (Tage statt Stunden). LOOKBACK_BARS deckelt die
    # an ATR/FVG/Referenz-Level/Swing-Check uebergebene View auf ein
    # rollierendes Fenster. 5000 M5-Bars (~17 Handelstage) liegt weit ueber
    # allem, was diese Funktionen kausal brauchen: Wilder-ATR(atr_len<=~30)
    # ist nach wenigen 100 Bars ausgewaschen (Seed-Einfluss < 1e-10),
    # Referenz-Level/FVG/Swing-Check brauchen nur den aktuellen/vorherigen
    # Handelstag. Numerisch identisch zur ungedeckelten Variante (siehe
    # tests/test_s3.py::test_lookback_bound_matches_unbounded_view).
    LOOKBACK_BARS = 5000

    WINDOW_PRESETS = {
        "london": ("03:00", "04:00"),
        "ny_am": ("10:00", "11:00"),
        "ny_open": ("08:30", "09:10"),
        "ny_pm": ("14:00", "15:00"),
    }

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "NAS100")
        self.risk_pct = float(p.get("risk_pct", 0.005))
        # Fenster (SPEC: Default 10:00–11:00 America/New_York)
        self.tz = p.get("window_tz", "America/New_York")
        win = p.get("window", "10:00-11:00")
        if win in self.WINDOW_PRESETS:
            self.win_start, self.win_end = self.WINDOW_PRESETS[win]
        else:
            self.win_start, self.win_end = win.split("-")
        # Referenz-Liquiditaet
        self.sweep_ref = p.get("sweep_ref", "hour9")  # hour9 | asian
        self.ref_hour_tz = p.get("ref_tz", "America/New_York")
        self.asian_tz = p.get("asian_tz", "UTC")
        self.asian_start = p.get("asian_start", "00:00")
        self.asian_end = p.get("asian_end", "07:00")
        # Sweep / MSS / FVG
        self.atr_len = int(p.get("atr_len", 20))
        self.sweep_wick_atr = float(p.get("sweep_wick_atr", 0.1))
        self.disp_body_atr = float(p.get("disp_body_atr", 1.5))
        self.disp_body_range = float(p.get("disp_body_range", 0.7))
        self.swing_k = int(p.get("swing_k", 2))
        self.swing_lookback = int(p.get("swing_lookback", 30))
        self.fvg_min = float(p.get("fvg_min", 0.3))
        self.entry_ce = float(p.get("entry_ce", 0.5))  # 50 % Consequent Encroachment
        self.expiry = int(p.get("expiry", 12))
        # SL / TP
        self.sl_buffer_atr = float(p.get("sl_buffer_atr", 0.3))
        self.rr_min = float(p.get("rr_min", 2.0))
        self.max_trades_per_window = int(p.get("max_trades_per_window", 1))
        self.be_enabled = bool(p.get("be_enabled", False))
        self.be_at_r = float(p.get("be_at_r", 3.0))
        # Filter-Layer
        self.htf_bias = as_flag(p.get("htf_bias"), default=False)  # off | on
        # State
        self._day = None
        self._sweep: dict | None = None
        self._trades_today = 0

    # -- Tages-Reset ---------------------------------------------------------
    def _reset_day(self, day) -> None:
        self._day = day
        self._sweep = None
        self._trades_today = 0

    # -- Referenz-Liquiditaet -------------------------------------------------
    def _reference_levels(
        self, df: pd.DataFrame, i: int, day
    ) -> tuple[float, float] | None:
        """High/Low der 09:00-ET-Stundenkerze (Default) bzw. Asian-Range."""
        lo = max(0, i + 1 - self.LOOKBACK_BARS)
        idx = df.index[lo : i + 1]
        if self.sweep_ref == "hour9":
            local = _local_times(idx, self.ref_hour_tz)
            mask = (local.date == day) & (local.hour == 9)
        else:  # asian
            local_utc = _local_times(idx, self.asian_tz)
            sh, sm = map(int, self.asian_start.split(":"))
            eh, em = map(int, self.asian_end.split(":"))
            mins = local_utc.hour * 60 + local_utc.minute
            local_ny = _local_times(idx, self.tz)
            mask = (
                (local_ny.date == day)
                & (mins >= sh * 60 + sm)
                & (mins < eh * 60 + em)
            )
        if not mask.any():
            return None
        seg = df.iloc[lo : i + 1][mask]
        return float(seg["high"].max()), float(seg["low"].min())

    # -- HTF-Bias (H4 letztes BOS/CHoCH, A/B-Arm) ------------------------------
    def _htf_bias_dir(self, bars: dict[str, pd.DataFrame], ts_close: pd.Timestamp) -> int:
        h4 = bars.get("H4")
        if h4 is None or len(h4) < 4 * self.swing_k + 2:
            return 0
        # nur H4-Bars, die zum aktuellen M5-Close bereits geschlossen sind
        h4 = h4[h4.index + pd.Timedelta(hours=4) <= ts_close]
        if len(h4) < 4 * self.swing_k + 2:
            return 0
        k = self.swing_k
        sh, sl = _swing_extremes(h4, k)
        closes = h4["close"].to_numpy()
        last_up = last_dn = -1
        for j in range(len(h4)):
            if np.isfinite(sh[j]):  # Swing-High wird bei j sichtbar
                lvl = sh[j]
                later = closes[j + 1 :]
                brk = np.nonzero(later > lvl)[0]
                if len(brk):
                    last_up = max(last_up, j + 1 + brk[0])
            if np.isfinite(sl[j]):
                lvl = sl[j]
                later = closes[j + 1 :]
                brk = np.nonzero(later < lvl)[0]
                if len(brk):
                    last_dn = max(last_dn, j + 1 + brk[0])
        if last_up < 0 and last_dn < 0:
            return 0
        return 1 if last_up > last_dn else -1

    # -- Hauptlogik -----------------------------------------------------------
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars["M5"]
        min_bars = max(self.atr_len + 2, 2 * self.swing_k + 3)
        if i < min_bars:
            return None
        ts = df.index[i]  # UTC, Bar gerade geschlossen
        local = ts.tz_convert(ZoneInfo(self.tz))
        day = local.date()
        if self._day != day:
            self._reset_day(day)

        in_win = _in_window(ts, self.tz, self.win_start, self.win_end)
        if not in_win:
            # Killzone-Regel: ausserhalb des Fensters kein Trade; Sweep-State purgen
            self._sweep = None
            return None

        view = df.iloc[max(0, i + 1 - self.LOOKBACK_BARS) : i + 1]
        atr_s = _atr(view, self.atr_len)
        atr_now = float(atr_s.iloc[-1])
        if not np.isfinite(atr_now) or atr_now <= 0:
            return None

        ref = self._reference_levels(df, i, day)
        if ref is None:
            return None
        ref_high, ref_low = ref

        o = float(view["open"].iloc[-1])
        h = float(view["high"].iloc[-1])
        l = float(view["low"].iloc[-1])
        c = float(view["close"].iloc[-1])

        # -- (2) Sweep-Detection ------------------------------------------------
        if self._sweep is None and self._trades_today < self.max_trades_per_window:
            if h > ref_high and (h - ref_high) >= self.sweep_wick_atr * atr_now and c < ref_high:
                self._sweep = {
                    "dir": -1,
                    "extreme": h,
                    "ref_high": ref_high,
                    "ref_low": ref_low,
                    "sweep_time": ts,
                }
            elif l < ref_low and (ref_low - l) >= self.sweep_wick_atr * atr_now and c > ref_low:
                self._sweep = {
                    "dir": 1,
                    "extreme": l,
                    "ref_high": ref_high,
                    "ref_low": ref_low,
                    "sweep_time": ts,
                }
            return None  # Sweep-Bar selbst kann kein Signal sein (MSS noetig)

        sw = self._sweep
        if sw is None or self._trades_today >= self.max_trades_per_window:
            return None
        # Sweep-Extrem nachziehen (fuer SL hinter Sweep-Extrem)
        if sw["dir"] == -1:
            sw["extreme"] = max(sw["extreme"], h)
        else:
            sw["extreme"] = min(sw["extreme"], l)

        # -- (4) FVG, bestaetigt auf aktuellem Bar (confirmed_at == ts) ---------
        fvgs = _fair_value_gaps(view, self.fvg_min, atr_s)
        if fvgs.empty:
            return None
        cand = fvgs[
            (fvgs["confirmed_at"] == ts) & (fvgs["direction"] == sw["dir"])
        ]
        if cand.empty:
            return None
        fvg = cand.iloc[-1]
        # core.smc-Semantik (SPEC §4.6): formed_at = 3. Bar des Musters (an
        # ihr wird die Luecke sichtbar), confirmed_at = formed + 1 Bar. Das
        # Displacement-Leg ist die mittlere Bar des 3-Bar-Musters, also die
        # Bar unmittelbar vor formed_at.
        formed_pos = view.index.get_loc(fvg["formed_at"])
        disp_pos = formed_pos - 1
        # Zeitvergleich statt Positionsvergleich: disp_pos/formed_pos sind
        # relativ zur (ggf. gedeckelten) view, sweep_time ist ein absoluter
        # Timestamp — ein Positionsvergleich waere bei gedeckelter View
        # (view.index[0] != df.index[0]) falsch (Off-by-lo-Fehler).
        if disp_pos < 0 or view.index[disp_pos] <= sw["sweep_time"]:
            return None  # Displacement muss NACH dem Sweep kommen

        # -- (3) MSS/Displacement auf dem Displacement-Leg --------------------
        d_o = float(view["open"].iloc[disp_pos])
        d_h = float(view["high"].iloc[disp_pos])
        d_l = float(view["low"].iloc[disp_pos])
        d_c = float(view["close"].iloc[disp_pos])
        d_atr = float(atr_s.iloc[disp_pos])
        if not np.isfinite(d_atr) or d_atr <= 0:
            return None
        body = abs(d_c - d_o)
        rng = d_h - d_l
        if rng <= 0:
            return None
        if sw["dir"] == -1 and not (d_c < d_o):
            return None
        if sw["dir"] == 1 and not (d_c > d_o):
            return None
        if body < self.disp_body_atr * d_atr:
            return None
        if body / rng < self.disp_body_range:
            return None
        # bricht Swing-Fraktal k=2 per Close (nur bestaetigte Swings)
        k = self.swing_k
        sh_arr, sl_arr = _swing_extremes(view.iloc[: disp_pos + 1], k)
        lo = max(0, disp_pos - self.swing_lookback)
        if sw["dir"] == -1:
            known = sl_arr[lo : disp_pos + 1]
            known = known[np.isfinite(known)]
            if len(known) == 0 or not (d_c < known[-1]):
                return None
        else:
            known = sh_arr[lo : disp_pos + 1]
            known = known[np.isfinite(known)]
            if len(known) == 0 or not (d_c > known[-1]):
                return None

        # -- HTF-Bias-Filter (A/B-Arm) ------------------------------------------
        if self.htf_bias:
            htf_dir = self._htf_bias_dir(bars, ts + pd.Timedelta(minutes=5))
            if htf_dir != sw["dir"]:
                return None

        # -- (5) Entry / SL / TP -------------------------------------------------
        fvg_top = float(fvg["fvg_top"])
        fvg_bottom = float(fvg["fvg_bottom"])
        entry = fvg_bottom + self.entry_ce * (fvg_top - fvg_bottom)  # 50 % CE
        if sw["dir"] == -1:
            sl = sw["extreme"] + self.sl_buffer_atr * atr_now
            tp = sw["ref_low"]  # Gegen-Liquiditaet
            risk = sl - entry
            reward = entry - tp
        else:
            sl = sw["extreme"] - self.sl_buffer_atr * atr_now
            tp = sw["ref_high"]
            risk = entry - sl
            reward = tp - entry
        if risk <= 0 or reward <= 0:
            return None
        rr = reward / risk
        if rr < self.rr_min:
            return None  # RR >= 2 Gate

        self._trades_today += 1
        self._sweep = None  # max 1 Trade/Fenster (Purge)
        meta = {
            "window": f"{self.win_start}-{self.win_end}",
            "window_tz": self.tz,
            "sweep_ref": self.sweep_ref,
            "sweep_extreme": sw["extreme"],
            "ref_high": sw["ref_high"],
            "ref_low": sw["ref_low"],
            "fvg_top": fvg_top,
            "fvg_bottom": fvg_bottom,
            "atr": atr_now,
            "rr": rr,
            "htf_bias": self.htf_bias,
        }
        if self.be_enabled:
            meta["move_to_be_at_r"] = self.be_at_r  # BE bei 3R (Risk-Engine)
        return Signal(
            time=ts,
            symbol=self.symbol,
            direction=sw["dir"],
            entry_type="limit",
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_pct=self.risk_pct,
            meta=meta,
            expires_bars=self.expiry,
        )
