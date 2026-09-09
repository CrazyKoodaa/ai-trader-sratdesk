"""core/smc.py — kausale Smart-Money-Concepts-Bausteine (SPEC §4.6).

Bewusst KEINE Verwendung des PyPI-Pakets ``smartmoneyconcepts`` (repaintet).
Alle Events sind strikt kausal:

- FVG: ``confirmed_at`` = formed + 1 Bar.
- BOS/CHoCH: ein Swing gilt erst nach ``right`` Bars als bestätigt; ein
  Bruch wird per Close erkannt und nutzt nur *zuvor* bestätigte Swings.
- Sweeps/Equal-Highs-Lows: werden an der jeweiligen Bar geschlossen
  ausgewertet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.indicators import atr as _atr
from core.indicators import swing_points

FVG_COLUMNS = ["fvg_top", "fvg_bottom", "direction", "formed_at", "confirmed_at"]
EVENT_COLUMNS = ["kind", "direction", "level", "swing_time"]
OB_COLUMNS = ["ob_top", "ob_bottom", "direction", "formed_at", "event_time"]


def _check_df(df: pd.DataFrame) -> None:
    missing = [c for c in ("open", "high", "low", "close") if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame fehlt Spalten: {missing}")


# ---------------------------------------------------------------------------
# Fair Value Gaps
# ---------------------------------------------------------------------------

def fair_value_gaps(df: pd.DataFrame, min_size_atr: float = 0.0,
                    atr: "pd.Series | None" = None) -> pd.DataFrame:
    """Kausale FVG-Erkennung (3-Bar-Muster).

    Bullish FVG an Bar i: low[i] > high[i-2]  -> Zone [high[i-2], low[i]].
    Bearish FVG an Bar i: high[i] < low[i-2] -> Zone [high[i], low[i-2]].
    Mindestgröße: (top - bottom) >= min_size_atr * atr[i].
    ``confirmed_at`` = formed_at + 1 Bar (NaT, wenn die Bestätigungs-Bar
    außerhalb der Daten liegt).

    Rückgabe: DataFrame[fvg_top, fvg_bottom, direction (+1/-1), formed_at,
    confirmed_at], index = formed_at.
    """
    _check_df(df)
    if atr is None:
        atr = _atr(df, 14)
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    a = atr.to_numpy(dtype="float64")
    idx = df.index
    rows = []
    for i in range(2, len(df)):
        min_size = min_size_atr * a[i] if not np.isnan(a[i]) else np.inf
        confirmed = idx[i + 1] if i + 1 < len(df) else pd.NaT
        if l[i] > h[i - 2]:  # bullish
            top, bottom = l[i], h[i - 2]
            if top - bottom >= min_size:
                rows.append((idx[i], top, bottom, 1, idx[i], confirmed))
        elif h[i] < l[i - 2]:  # bearish
            top, bottom = l[i - 2], h[i]
            if top - bottom >= min_size:
                rows.append((idx[i], top, bottom, -1, idx[i], confirmed))
    out = pd.DataFrame(
        rows, columns=["_t", "fvg_top", "fvg_bottom", "direction", "formed_at", "confirmed_at"]
    )
    if out.empty:
        return pd.DataFrame(columns=FVG_COLUMNS).astype({"direction": "int64"})
    out.index = pd.DatetimeIndex(out.pop("_t"))
    out["direction"] = out["direction"].astype("int64")
    return out[FVG_COLUMNS]


# ---------------------------------------------------------------------------
# Swing-Struktur: BOS / CHoCH
# ---------------------------------------------------------------------------

def swing_structure(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """BOS/CHoCH-Events (kausal).

    Logik: Aktiv ist jeweils der jüngste *bestätigte* Swing (Bestätigung
    nach ``right`` Bars). Schließt eine Bar über dem aktiven Swing-High, ist
    das ein bullisher Bruch: ``BOS`` im Aufwärtstrend, ``CHoCH`` nach einem
    Abwärtstrend (Trendwechsel) — symmetrisch für Swing-Lows. Nach einem
    Bruch ist das Level konsumiert; ein neues Event erfordert einen neuen
    bestätigten Swing. Pro Bar werden Brüche mit den *vor* der Bar bekannten
    Levels geprüft, danach werden neu bestätigte Swings übernommen.

    Rückgabe: DataFrame[kind ("BOS"/"CHoCH"), direction (+1/-1), level,
    swing_time], index = Zeitpunkt der Bruch-Bar (Event-Zeit).
    """
    _check_df(df)
    sw = swing_points(df, left=left, right=right, confirmed_lag=0)
    idx = df.index
    n = len(df)
    pos = {t: k for k, t in enumerate(idx)}

    conf_at_bar: dict[int, list[tuple[int, str, float]]] = {}
    for i in range(n):
        sh, sl = sw["swing_high"].iloc[i], sw["swing_low"].iloc[i]
        if not pd.isna(sh):
            ts = sw["swing_high_confirmed_at"].iloc[i]
            if not pd.isna(ts):
                conf_at_bar.setdefault(pos[ts], []).append((i, "high", float(sh)))
        if not pd.isna(sl):
            ts = sw["swing_low_confirmed_at"].iloc[i]
            if not pd.isna(ts):
                conf_at_bar.setdefault(pos[ts], []).append((i, "low", float(sl)))

    close = df["close"].to_numpy()
    trend = 0  # +1 up, -1 down, 0 unbekannt
    active_high: tuple[int, float] | None = None  # (Kandidaten-Pos, Preis)
    active_low: tuple[int, float] | None = None
    rows = []
    for j in range(n):
        # 1) Bruch-Prüfung mit den vor Bar j aktiven Levels
        if active_high is not None and close[j] > active_high[1]:
            kind = "CHoCH" if trend == -1 else "BOS"
            rows.append((idx[j], kind, 1, active_high[1], idx[active_high[0]]))
            trend = 1
            active_high = None
        if active_low is not None and close[j] < active_low[1]:
            kind = "CHoCH" if trend == 1 else "BOS"
            rows.append((idx[j], kind, -1, active_low[1], idx[active_low[0]]))
            trend = -1
            active_low = None
        # 2) neu bestätigte Swings werden ab dieser Bar aktiv
        for i, side, price in conf_at_bar.get(j, ()):
            if side == "high":
                active_high = (i, price)
            else:
                active_low = (i, price)

    out = pd.DataFrame(rows, columns=["_t", "kind", "direction", "level", "swing_time"])
    if out.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS).astype({"direction": "int64"})
    out.index = pd.DatetimeIndex(out.pop("_t"))
    out["direction"] = out["direction"].astype("int64")
    return out[EVENT_COLUMNS]


# ---------------------------------------------------------------------------
# Liquidity Sweep
# ---------------------------------------------------------------------------

def liquidity_sweep(df: pd.DataFrame, level: float, wick_excess_min: float = 0.0,
                    direction: str = "both") -> pd.DataFrame:
    """Sweep-Events gegen ein festes Preis-Level (kausal, per Bar).

    - Sweep oberhalb (side=+1): high > level, Wick-Exzess (high - level)
      >= wick_excess_min, close < level (Close zurück unter dem Level).
    - Sweep unterhalb (side=-1): symmetrisch.

    ``direction`` ∈ {"above", "below", "both"}. Rückgabe: DataFrame
    [side, level, wick_excess, close], index = Bar-Zeitpunkt.
    """
    _check_df(df)
    if direction not in ("above", "below", "both"):
        raise ValueError("direction muss 'above', 'below' oder 'both' sein")
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    rows = []
    for i in range(len(df)):
        if direction in ("above", "both") and h[i] > level and (h[i] - level) >= wick_excess_min and c[i] < level:
            rows.append((df.index[i], 1, float(level), float(h[i] - level), float(c[i])))
        if direction in ("below", "both") and l[i] < level and (level - l[i]) >= wick_excess_min and c[i] > level:
            rows.append((df.index[i], -1, float(level), float(level - l[i]), float(c[i])))
    out = pd.DataFrame(rows, columns=["_t", "side", "level", "wick_excess", "close"])
    if out.empty:
        return pd.DataFrame(columns=["side", "level", "wick_excess", "close"]).astype({"side": "int64"})
    out.index = pd.DatetimeIndex(out.pop("_t"))
    out["side"] = out["side"].astype("int64")
    return out[["side", "level", "wick_excess", "close"]]


# ---------------------------------------------------------------------------
# Order Blocks
# ---------------------------------------------------------------------------

def order_blocks(df: pd.DataFrame, bos_events: pd.DataFrame,
                 max_lookback: int = 20) -> pd.DataFrame:
    """Order Blocks aus BOS/CHoCH-Events.

    Für ein bullishes Event ist der OB die letzte bearishe Bar
    (close < open) vor der Bruch-Bar (max. ``max_lookback`` Bars zurück,
    nicht vor dem gebrochenen Swing); Zone = [low, high] dieser Bar.
    Für bearishe Events symmetrisch. Kausal: der OB ist erst ab
    ``event_time`` (Bruch-Bar) bekannt.

    Rückgabe: DataFrame[ob_top, ob_bottom, direction, formed_at,
    event_time], index = event_time. Events ohne gefundene Gegen-Bar
    erzeugen keinen OB.
    """
    _check_df(df)
    required = {"direction", "swing_time"}
    if not required.issubset(bos_events.columns):
        raise ValueError(f"bos_events benötigt Spalten {required}")
    idx = df.index
    pos = {t: k for k, t in enumerate(idx)}
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    rows = []
    for ev_time, ev in bos_events.iterrows():
        j = pos.get(ev_time)
        if j is None:
            continue
        lo_bound = max(0, j - max_lookback)
        st = ev.get("swing_time")
        if st is not None and not pd.isna(st) and st in pos:
            lo_bound = max(lo_bound, pos[st])
        d = int(ev["direction"])
        for k in range(j - 1, lo_bound - 1, -1):
            is_ob = (c[k] < o[k]) if d == 1 else (c[k] > o[k])
            if is_ob:
                rows.append((ev_time, float(h[k]), float(l[k]), d, idx[k], ev_time))
                break
    out = pd.DataFrame(rows, columns=["_t", "ob_top", "ob_bottom", "direction", "formed_at", "event_time"])
    if out.empty:
        return pd.DataFrame(columns=OB_COLUMNS).astype({"direction": "int64"})
    out.index = pd.DatetimeIndex(out.pop("_t"))
    out["direction"] = out["direction"].astype("int64")
    return out[OB_COLUMNS]


# ---------------------------------------------------------------------------
# Equal Highs / Equal Lows
# ---------------------------------------------------------------------------

def equal_highs_lows(df: pd.DataFrame, tolerance_atr: float = 0.1,
                     lookback: int = 20, atr_n: int = 14) -> pd.DataFrame:
    """Equal Highs/Lows (kausal, pro Bar).

    Equal High an Bar i: |high[i] - max(high[i-lookback..i-1])| <=
    tolerance_atr * ATR[i]. Equal Low symmetrisch gegen das Rolling-Min.
    ``eq_high_level``/``eq_low_level`` enthalten das Referenz-Level.

    Rückgabe: DataFrame[equal_high (bool), equal_low (bool),
    eq_high_level, eq_low_level].
    """
    _check_df(df)
    a = _atr(df, int(atr_n))
    tol = tolerance_atr * a
    prior_max = df["high"].shift(1).rolling(int(lookback)).max()
    prior_min = df["low"].shift(1).rolling(int(lookback)).min()
    eq_h = ((df["high"] - prior_max).abs() <= tol).fillna(False)
    eq_l = ((df["low"] - prior_min).abs() <= tol).fillna(False)
    return pd.DataFrame(
        {
            "equal_high": eq_h.astype(bool),
            "equal_low": eq_l.astype(bool),
            "eq_high_level": prior_max.where(eq_h),
            "eq_low_level": prior_min.where(eq_l),
        },
        index=df.index,
    )
