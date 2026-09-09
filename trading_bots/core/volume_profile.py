"""core/volume_profile.py — kausales Volume Profile auf tick_volume-Basis.

Konfluenz-Filter-Layer (Research dim13, Variante (b)): KEIN eigenständiger
Bot, sondern A/B-testbares Filter-Gate für S1 (TrendPullback) und S5
(FilteredMR) — Filter-Regeln F1 (Entry am POC/HVN) und F6 (Block in LVN).

Berechnung (Konsens-Algorithmus, dim13 §4.1):
1. Fenster: ``anchor="rolling"`` (letzte ``lookback_bars`` Bars) oder
   ``anchor="swing"`` (Video-Variante: Fenster zwischen letztem bestätigtem
   Swing-Low und letztem bestätigtem Swing-High via
   ``core.indicators.swing_points`` — nur Swings mit ``confirmed_at`` <=
   letzter Bar-Zeitpunkt; Fallback auf rolling, wenn kein Paar bestätigt).
2. Bin-Breite = ``bin_atr_mult`` × ATR14 (volatilitätsadaptiv).
3. Volumen-Verteilung: tick_volume jeder Bar anteilig (Range-Überdeckung)
   auf die überdeckten Bins; Range-0-Bars landen vollständig im Treffer-Bin.
4. POC = Bin-Mitte des argmax; Value Area = greedy Expansion ab POC bis
   ``va_pct`` (Default 70 %) des Gesamtvolumens.
5. HVN = Bin-Volumen > ``hvn_mult`` × Median; LVN = < ``lvn_mult`` × Median.

KAUSALITÄT: Die Funktion verwendet ausschließlich die Bars des übergebenen
DataFrames. Aufrufer (Strategien) slicen strikt bis einschließlich der
geschlossenen Signal-Bar (``df.iloc[: i + 1]``). Swing-Anker nutzt nur
bestätigte Swings (kein Lookahead, siehe ``swing_points``). ATR ist
Wilder-rekursiv und damit prefix-stabil — Anti-Repaint via Prefix-Test
abgesichert (tests/test_volume_profile.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.indicators import atr, swing_points

REQUIRED_COLS = ("high", "low", "close", "tick_volume")


@dataclass
class VolumeProfileResult:
    poc: float                 # Point of Control (Bin-Mitte des Max-Volumens)
    va_high: float             # obere Kante der Value Area (va_pct)
    va_low: float              # untere Kante der Value Area
    hvn: list[float] = field(default_factory=list)   # High-Volume-Nodes (Bin-Mitten)
    lvn: list[float] = field(default_factory=list)   # Low-Volume-Nodes (Bin-Mitten)
    bins: np.ndarray = field(default_factory=lambda: np.zeros(0))   # Bin-Kanten (n+1)
    volumes: np.ndarray = field(default_factory=lambda: np.zeros(0))
    anchor: str = "rolling"    # tatsächlich verwendeter Anker ("swing" kann
                               # auf "rolling" zurückfallen, Info für meta)
    va_volume_frac: float = 0.0   # realer Volumen-Anteil der VA (>= va_pct)

    @property
    def bin_midpoints(self) -> np.ndarray:
        if len(self.bins) < 2:
            return np.zeros(0)
        return 0.5 * (self.bins[:-1] + self.bins[1:])


def _value_area(volumes: np.ndarray, poc_i: int, va_pct: float) -> tuple[int, int]:
    """Greedy Value-Area-Expansion ab POC bis >= va_pct des Gesamtvolumens.

    Erweitert je Iteration um den Nachbar-Bin mit höherem Volumen
    (Links/Rechts-Tiebreak: Seite mit dem größeren Bin zuerst, bei Gleichstand
    nach unten — deterministisch). Rückgabe (lo_i, hi_i) inklusiv.
    """
    n = len(volumes)
    total = float(volumes.sum())
    lo = hi = poc_i
    acc = float(volumes[poc_i])
    target = va_pct * total
    while acc < target and (lo > 0 or hi < n - 1):
        up_v = volumes[hi + 1] if hi < n - 1 else -1.0
        dn_v = volumes[lo - 1] if lo > 0 else -1.0
        if up_v > dn_v:
            hi += 1
            acc += float(volumes[hi])
        else:
            lo -= 1
            acc += float(volumes[lo])
    return lo, hi


def _swing_window(df: pd.DataFrame, left: int, right: int) -> tuple[int, int] | None:
    """Fenster [start, end) zwischen letztem bestätigtem Swing-Low und letztem
    bestätigtem Swing-High (Kandidaten-Positionen, kausal sichtbar).

    Nur Swings mit ``confirmed_at`` <= Zeitpunkt der letzten Bar. Rückgabe
    None, wenn kein bestätigtes Paar existiert.
    """
    if len(df) < 2 * max(left, right) + 2:
        return None
    sp = swing_points(df, left, right, 0)
    t_last = df.index[-1]
    highs = sp.index[sp["swing_high"].notna()
                     & sp["swing_high_confirmed_at"].notna()
                     & (sp["swing_high_confirmed_at"] <= t_last)]
    lows = sp.index[sp["swing_low"].notna()
                    & sp["swing_low_confirmed_at"].notna()
                    & (sp["swing_low_confirmed_at"] <= t_last)]
    if len(highs) == 0 or len(lows) == 0:
        return None
    pos = df.index.get_indexer
    h_i = int(pos([highs[-1]])[0])
    l_i = int(pos([lows[-1]])[0])
    a, b = min(h_i, l_i), max(h_i, l_i)
    if b - a < 2:
        return None
    return a, b + 1   # inkl. beider Pivot-Bars


def volume_profile(df: pd.DataFrame, lookback_bars: int | None = None,
                   anchor: str = "rolling", bin_atr_mult: float = 0.25,
                   va_pct: float = 0.70, hvn_mult: float = 1.5,
                   lvn_mult: float = 0.5,
                   *, swing_left: int = 3, swing_right: int = 3,
                   atr_len: int = 14) -> VolumeProfileResult:
    """Kausales Volume Profile der übergebenen (abgeschlossenen) Bars.

    Parameter
    ---------
    df : OHLCV-DataFrame (Spalten high/low/close/tick_volume), nur Bars bis
        einschließlich der aktuellen Signal-Bar übergeben (close[1]-Prinzip).
    lookback_bars : Fensterlänge für anchor="rolling" (None = alle Bars);
        bei anchor="swing" Obergrenze für das Swing-Fenster.
    anchor : "rolling" | "swing". "swing" = Profil zwischen letztem
        bestätigtem Swing-Low und Swing-High (Video-Variante); fällt auf
        "rolling" zurück, wenn kein bestätigtes Swing-Paar existiert.
    bin_atr_mult : Bin-Breite = bin_atr_mult × ATR14 (letzter Wert).
    va_pct : Value-Anteil der Value Area (0.70 = 70 %).
    hvn_mult / lvn_mult : HVN = Bin-Vol > hvn_mult × Median(Bin-Vol),
        LVN = Bin-Vol < lvn_mult × Median(Bin-Vol).
    """
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame fehlt Spalten: {missing}")
    if len(df) == 0:
        raise ValueError("volume_profile: leerer DataFrame")
    if anchor not in ("rolling", "swing"):
        raise ValueError(f"anchor muss 'rolling' oder 'swing' sein, nicht {anchor!r}")

    used_anchor = anchor
    if anchor == "swing":
        win = _swing_window(df, int(swing_left), int(swing_right))
        if win is None:
            used_anchor = "rolling"
            start = 0 if lookback_bars is None else max(0, len(df) - int(lookback_bars))
        else:
            start, end = win
            if lookback_bars is not None:
                start = max(start, len(df) - int(lookback_bars))
            win_df = df.iloc[start:end]
            return _build(win_df, bin_atr_mult, va_pct, hvn_mult, lvn_mult,
                          atr_len, used_anchor, full_df=df)

    start = 0 if lookback_bars is None else max(0, len(df) - int(lookback_bars))
    win_df = df.iloc[start:]
    return _build(win_df, bin_atr_mult, va_pct, hvn_mult, lvn_mult,
                  atr_len, used_anchor, full_df=df)


def _build(win_df: pd.DataFrame, bin_atr_mult: float, va_pct: float,
           hvn_mult: float, lvn_mult: float, atr_len: int,
           used_anchor: str, full_df: pd.DataFrame) -> VolumeProfileResult:
    """Profil-Berechnung auf dem Fenster; ATR aus dem vollen (kausalen) DF,
    damit die Bin-Breite nicht vom Fenster-Start abhängt."""
    atr_s = atr(full_df, atr_len)
    atr_now = float(atr_s.iloc[-1]) if len(atr_s) else np.nan

    lo = float(win_df["low"].min())
    hi = float(win_df["high"].max())
    price_range = hi - lo

    # Bin-Breite: ATR-adaptiv; Fallbacks bei NaN/0 ATR oder degenerierter Range
    if not np.isfinite(atr_now) or atr_now <= 0:
        bin_w = price_range / 50.0 if price_range > 0 else 1.0
    else:
        bin_w = float(bin_atr_mult) * atr_now
    if price_range <= 0:
        # Degeneriertes Fenster (alle Bars gleiches Preisniveau)
        mid = float(win_df["close"].iloc[-1])
        return VolumeProfileResult(
            poc=mid, va_high=mid, va_low=mid, hvn=[], lvn=[],
            bins=np.array([mid - 0.5 * bin_w, mid + 0.5 * bin_w]),
            volumes=np.array([float(win_df["tick_volume"].sum())]),
            anchor=used_anchor, va_volume_frac=1.0,
        )

    n_bins = int(np.ceil(price_range / bin_w))
    n_bins = max(1, min(n_bins, 2000))          # Sicherheitskappe
    edges = lo + np.arange(n_bins + 1) * bin_w  # äquidistant ab Fenster-Low
    edges[-1] = max(edges[-1], hi)              # Rundung: High garantiert drin

    highs = win_df["high"].to_numpy(dtype="float64")
    lows = win_df["low"].to_numpy(dtype="float64")
    vols = win_df["tick_volume"].to_numpy(dtype="float64")
    vol = np.zeros(n_bins)

    # Pro Bar: Volumen anteilig (Range-Überdeckung) auf die überdeckten Bins
    lo_idx = np.clip(np.searchsorted(edges, lows, side="right") - 1, 0, n_bins - 1)
    hi_idx = np.clip(np.searchsorted(edges, highs, side="right") - 1, 0, n_bins - 1)
    for b in range(len(win_df)):
        i0, i1 = int(lo_idx[b]), int(hi_idx[b])
        rng = highs[b] - lows[b]
        if rng <= 0 or i0 == i1:
            vol[i0] += vols[b]
            continue
        # Überdeckungs-Anteile der Bins i0..i1 am Bar-Range [lows[b], highs[b]]
        e_lo = edges[i0: i1 + 1]
        e_hi = edges[i0 + 1: i1 + 2]
        overlap = np.minimum(e_hi, highs[b]) - np.maximum(e_lo, lows[b])
        vol[i0: i1 + 1] += vols[b] * np.clip(overlap, 0.0, None) / rng

    total = float(vol.sum())
    poc_i = int(np.argmax(vol))
    mids = 0.5 * (edges[:-1] + edges[1:])
    poc = float(mids[poc_i])

    lo_i, hi_i = _value_area(vol, poc_i, float(va_pct))
    va_vol_frac = float(vol[lo_i: hi_i + 1].sum() / total) if total > 0 else 0.0

    med = float(np.median(vol))
    hvn = [float(mids[k]) for k in range(n_bins) if vol[k] > hvn_mult * med]
    lvn = [float(mids[k]) for k in range(n_bins) if vol[k] < lvn_mult * med]

    return VolumeProfileResult(
        poc=poc,
        va_high=float(edges[hi_i + 1]),
        va_low=float(edges[lo_i]),
        hvn=hvn,
        lvn=lvn,
        bins=edges,
        volumes=vol,
        anchor=used_anchor,
        va_volume_frac=va_vol_frac,
    )


# ---------------------------------------------------------------------------
# Filter-Regeln (dim13 §5.1: F1/F6 + struktureller SL) — gemeinsame Logik
# für S1/S5, damit beide Strategien dieselbe Semantik teilen.
# ---------------------------------------------------------------------------

def entry_gate(profile: VolumeProfileResult, price: float, tolerance: float,
               entry_requires_hvn: bool = True,
               block_lvn: bool = True) -> tuple[bool, dict]:
    """F1/F6-Konfluenz-Gate für einen Entry-Preis.

    F1 (``entry_requires_hvn``): Entry nur, wenn ``price`` innerhalb
    ``tolerance`` von POC oder einem HVN liegt.
    F6 (``block_lvn``): Entry blockiert, wenn ``price`` innerhalb
    ``tolerance`` eines LVN liegt (Preis "fällt durch" Low-Volume-Nodes).

    Rückgabe (allowed, info) — info für Signal.meta.
    """
    dist_poc = abs(price - profile.poc)
    dist_hvn = min((abs(price - h) for h in profile.hvn), default=np.inf)
    dist_lvn = min((abs(price - l) for l in profile.lvn), default=np.inf)
    near_poc = dist_poc <= tolerance
    near_hvn = dist_hvn <= tolerance
    in_lvn = dist_lvn <= tolerance

    allowed = True
    reason = "ok"
    if entry_requires_hvn and not (near_poc or near_hvn):
        allowed, reason = False, "not_at_poc_or_hvn"   # F1
    if block_lvn and in_lvn:
        allowed, reason = False, "in_lvn"              # F6

    info = {
        "vp_allowed": allowed,
        "vp_reason": reason,
        "vp_poc": profile.poc,
        "vp_va_high": profile.va_high,
        "vp_va_low": profile.va_low,
        "vp_near_poc": bool(near_poc),
        "vp_near_hvn": bool(near_hvn),
        "vp_in_lvn": bool(in_lvn),
        "vp_anchor": profile.anchor,
    }
    return allowed, info


def structural_stop(profile: VolumeProfileResult, direction: int, sl: float,
                    buffer: float = 0.0) -> float:
    """``vp_structure_levels``: SL hinter die Value Area legen.

    Long: Kandidat = VA-Low − buffer; Short: VA-High + buffer. Wird NUR
    übernommen, wenn der strukturelle Stop WEITER WEG liegt als der
    bestehende ATR-/Swing-Stop — nie enger (Risiko darf durch den Layer
    nur strukturell begründet wachsen, nie künstlich schrumpfen).
    """
    if direction == +1:
        cand = profile.va_low - buffer
        return float(min(sl, cand))     # tieferer SL = weiter weg
    if direction == -1:
        cand = profile.va_high + buffer
        return float(max(sl, cand))     # höherer SL = weiter weg
    raise ValueError(f"direction muss +1/-1 sein, nicht {direction!r}")
