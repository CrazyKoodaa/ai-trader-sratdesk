"""Tests core/volume_profile.py — kausales Volume Profile (dim13 Variante b).

Abgedeckt:
- POC liegt im bekannten Volumen-Cluster (handgebaute Serie)
- Value Area enthält >= 70 % des Volumens (greedy Expansion)
- Kausalität/Anti-Repaint: Prefix-Stabilität unter modifizierter Zukunft
- anchor="swing": nur bestätigte Swings, kein Lookahead auf unbestätigte
- entry_gate (F1/F6) und structural_stop (nie enger) als Unit-Tests
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.indicators import swing_points
from core.volume_profile import (
    VolumeProfileResult,
    entry_gate,
    structural_stop,
    volume_profile,
)


def _mk_df(close: np.ndarray, vol: np.ndarray | float,
           start: str = "2024-01-01") -> pd.DataFrame:
    """OHLCV aus Close-Serie; Range ±1 um den Close (open=close)."""
    close = np.asarray(close, dtype="float64")
    n = len(close)
    if np.isscalar(vol):
        vol = np.full(n, float(vol))
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0,
         "close": close, "tick_volume": np.asarray(vol, dtype="float64")},
        index=idx)


def _cluster_df() -> pd.DataFrame:
    """Aufstieg 90→110, Volumen-Cluster bei ~100 (Bars, die 99.5–100.5
    überdecken, haben 100× Volumen). ATR ≈ 2 -> Bin-Breite ≈ 0.5."""
    n = 60
    close = np.linspace(90, 110, n)
    df = _mk_df(close, 10.0)
    mask = (df["low"] <= 100.5) & (df["high"] >= 99.5)
    df.loc[mask, "tick_volume"] = 1000.0
    return df


# ---------------------------------------------------------------------------
# POC / Value Area
# ---------------------------------------------------------------------------

def test_poc_in_volume_cluster():
    df = _cluster_df()
    r = volume_profile(df, anchor="rolling")
    assert isinstance(r, VolumeProfileResult)
    # Bin-Breite = 0.25×ATR ≈ 0.5 -> POC muss im Cluster-Bin (~100) liegen
    assert abs(r.poc - 100.0) <= 0.5
    # POC ist Bin-Mitte des Volumen-Maximums
    assert r.poc == float(r.bin_midpoints[int(np.argmax(r.volumes))])


def test_value_area_covers_70pct():
    df = _cluster_df()
    r = volume_profile(df, anchor="rolling", va_pct=0.70)
    total = float(r.volumes.sum())
    in_va = float(r.volumes[(r.bins[:-1] < r.va_high)
                            & (r.bins[1:] > r.va_low)].sum())
    frac = in_va / total
    assert frac >= 0.70 - 1e-9                       # Mindestabdeckung
    assert frac == pytest.approx(r.va_volume_frac)
    # nicht mehr als ein Bin über der Schwelle (greedy stoppt rechtzeitig)
    assert frac <= 0.70 + float(r.volumes.max()) / total + 1e-9
    assert r.va_low <= r.poc <= r.va_high
    # Cluster liegt in der Value Area
    assert r.va_low <= 100.0 <= r.va_high


def test_hvn_lvn_against_median():
    df = _cluster_df()
    r = volume_profile(df, anchor="rolling", hvn_mult=1.5, lvn_mult=0.5)
    med = float(np.median(r.volumes))
    mids = r.bin_midpoints
    for h in r.hvn:   # jede HVN-Mitte gehört zu einem Bin > 1.5×Median
        k = int(np.argmin(np.abs(mids - h)))
        assert r.volumes[k] > 1.5 * med
    for l in r.lvn:
        k = int(np.argmin(np.abs(mids - l)))
        assert r.volumes[k] < 0.5 * med
    # Cluster-Bin ist HVN
    assert any(abs(h - 100.0) <= 0.5 for h in r.hvn)


# ---------------------------------------------------------------------------
# Kausalität / Anti-Repaint (Prefix-Stabilität)
# ---------------------------------------------------------------------------

def _rand_df(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.2, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.2, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": rng.uniform(50, 150, n)}, index=idx)


def _assert_same_profile(a: VolumeProfileResult, b: VolumeProfileResult):
    assert a.poc == b.poc and a.va_high == b.va_high and a.va_low == b.va_low
    assert a.hvn == b.hvn and a.lvn == b.lvn and a.anchor == b.anchor
    np.testing.assert_array_equal(a.bins, b.bins)
    np.testing.assert_array_equal(a.volumes, b.volumes)


@pytest.mark.parametrize("anchor", ["rolling", "swing"])
def test_anti_repaint_prefix_stability(anchor):
    """Profil auf Präfix [:cut] darf nicht von Bars nach cut abhängen.

    df und df_mod sind bis einschließlich Bar k identisch und unterscheiden
    sich danach massiv (Preis ×3, Volumen ×100). Für jeden Cut <= k muss das
    Profil identisch sein — Zukunft ändert die Vergangenheit nicht.
    """
    df = _rand_df()
    df_mod = df.copy()
    k = 200
    for col in ("open", "high", "low", "close"):
        df_mod.iloc[k:, df_mod.columns.get_loc(col)] *= 3.0
    df_mod.iloc[k:, df_mod.columns.get_loc("tick_volume")] *= 100.0
    for cut in (120, 160, k):          # alle Cuts <= k (modifizierte Zukunft)
        a = volume_profile(df.iloc[:cut], lookback_bars=120, anchor=anchor)
        b = volume_profile(df_mod.iloc[:cut], lookback_bars=120, anchor=anchor)
        _assert_same_profile(a, b)
    # Sanity: nach k unterscheiden sich die Profile tatsächlich (Test greift)
    later_a = volume_profile(df.iloc[:250], lookback_bars=120, anchor=anchor)
    later_b = volume_profile(df_mod.iloc[:250], lookback_bars=120, anchor=anchor)
    assert later_a.poc != later_b.poc


# ---------------------------------------------------------------------------
# Swing-Anker (Video-Variante): nur bestätigte Swings
# ---------------------------------------------------------------------------

def _swing_df() -> pd.DataFrame:
    """Abwärts bis t=20 (Swing-Low), Aufwärts bis t=40 (Swing-High),
    danach Seitwärts, ab t=50 neue Rally mit Riesen-Volumen — potenzieller
    neuer Swing-High-Kandidat bei t=57 ist zum Serienende UNBESTÄTIGT
    (right=3) und darf den Anker nicht verändern."""
    down = np.linspace(120, 80, 21)          # t=0..20  -> Swing-Low bei 20
    up = np.linspace(80, 140, 21)[1:]        # t=21..40 -> Swing-High bei 40
    side = np.linspace(140, 132, 10)[1:]     # t=41..49
    rally = np.linspace(132, 150, 10)[1:]    # t=50..58 (unbestätigt)
    close = np.concatenate([down, up, side, rally])
    vol = np.full(len(close), 100.0)
    vol[-9:] = 100_000.0                     # Riesen-Volumen in der Rally
    return _mk_df(close, vol)


def test_swing_anchor_uses_confirmed_swings_only():
    df = _swing_df()
    r = volume_profile(df, anchor="swing")   # swing_left/right Default 3
    assert r.anchor == "swing"               # kein Fallback nötig

    # Erwartetes Fenster: zwischen den Kandidaten-Positionen des letzten
    # BESTÄTIGTEN Swing-High (t=40) und Swing-Low (t=49, die Seitwärtsphase
    # druckt ein bestätigtes Tief). Die Rally ab t=50 hat zum Serienende
    # KEINEN bestätigten Swing (right=3) und darf nicht im Fenster liegen.
    sp = swing_points(df, 3, 3, 0)
    t_last = df.index[-1]
    conf_h = sp.index[sp["swing_high"].notna()
                      & (sp["swing_high_confirmed_at"] <= t_last)]
    conf_l = sp.index[sp["swing_low"].notna()
                      & (sp["swing_low_confirmed_at"] <= t_last)]
    i_h = int(df.index.get_loc(conf_h[-1]))
    i_l = int(df.index.get_loc(conf_l[-1]))
    assert (i_h, i_l) == (40, 49)            # Testdaten wie designed
    # Sanity: Rally-Spitze (t=57) ist KEIN bestätigter Swing (Lookahead-Schutz)
    assert sp["swing_high"].iloc[-3:].isna().all() \
        or sp["swing_high_confirmed_at"].iloc[-3:].isna().all()

    # Vergleich: Profil auf genau diesem Fenster (ATR aus vollem df)
    from core.volume_profile import _build
    ref = _build(df.iloc[min(i_l, i_h): max(i_l, i_h) + 1], 0.25, 0.70,
                 1.5, 0.5, 14, "swing", full_df=df)
    _assert_same_profile(r, ref)

    # Anti-Lookahead: das unbestätigte Rally-Volumen (t>=50) ist riesig —
    # würde es einfließen, läge der POC oben statt im bestätigten Fenster.
    win = slice(min(i_l, i_h), max(i_l, i_h) + 1)
    assert float(df["low"].iloc[win].min()) <= r.poc \
        <= float(df["high"].iloc[win].max())
    rolling = volume_profile(df, anchor="rolling")   # sieht die Rally
    assert rolling.poc > r.poc


def test_swing_anchor_fallback_without_confirmed_pair():
    """Kein bestätigtes Swing-Paar -> Fallback auf rolling (markiert)."""
    close = np.linspace(100, 110, 12)        # monoton, keine Swings (right=3)
    df = _mk_df(close, 100.0)
    r = volume_profile(df, anchor="swing", lookback_bars=10)
    assert r.anchor == "rolling"
    ref = volume_profile(df, anchor="rolling", lookback_bars=10)
    _assert_same_profile(r, ref)


# ---------------------------------------------------------------------------
# entry_gate (F1/F6) und structural_stop
# ---------------------------------------------------------------------------

def test_entry_gate_f1_and_f6():
    df = _cluster_df()
    r = volume_profile(df, anchor="rolling")
    # F1: am POC erlaubt
    ok, info = entry_gate(r, r.poc, tolerance=0.5)
    assert ok and info["vp_near_poc"]
    # F1: weit weg von POC/HVN blockiert (Preis 90 = Serienrand, LVN/leer)
    ok, info = entry_gate(r, 90.0, tolerance=0.25)
    assert not ok and info["vp_reason"] in ("not_at_poc_or_hvn", "in_lvn")
    # F1 abgeschaltet, F6 aktiv: 90.0 liegt fern vom Cluster -> LVN-Block
    ok, info = entry_gate(r, 90.0, tolerance=0.25,
                          entry_requires_hvn=False, block_lvn=True)
    assert not ok and info["vp_reason"] == "in_lvn"
    # beides abgeschaltet -> immer erlaubt
    ok, _ = entry_gate(r, 90.0, tolerance=0.25,
                       entry_requires_hvn=False, block_lvn=False)
    assert ok


def test_structural_stop_only_wider_never_tighter():
    df = _cluster_df()
    r = volume_profile(df, anchor="rolling")     # VA um ~100
    # Long: enger ATR-Stop innerhalb der VA bleibt unverändert (nie enger)
    sl_atr = 99.0
    sl = structural_stop(r, +1, sl_atr, buffer=0.1)
    assert sl <= sl_atr                          # tiefer = weiter weg
    assert sl == pytest.approx(r.va_low - 0.1)   # hinter VA-Low
    # Long: ATR-Stop bereits unter VA-Low -> unverändert
    sl_deep = r.va_low - 5.0
    assert structural_stop(r, +1, sl_deep, buffer=0.1) == sl_deep
    # Short: symmetrisch hinter VA-High
    sl_short = 101.0
    sl_s = structural_stop(r, -1, sl_short, buffer=0.1)
    assert sl_s >= sl_short
    assert sl_s == pytest.approx(r.va_high + 0.1)
    sl_high = r.va_high + 5.0
    assert structural_stop(r, -1, sl_high, buffer=0.1) == sl_high


# ---------------------------------------------------------------------------
# Edge-Cases
# ---------------------------------------------------------------------------

def test_degenerate_flat_prices():
    """Range = 0 (high=low=close): kein Crash, POC auf dem Preisniveau."""
    n = 30
    close = np.full(n, 100.0)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame({"open": close, "high": close, "low": close,
                       "close": close, "tick_volume": 100.0}, index=idx)
    r = volume_profile(df, anchor="rolling")
    assert r.poc == pytest.approx(100.0)
    assert r.va_volume_frac == 1.0


def test_invalid_anchor_and_empty():
    df = _cluster_df()
    with pytest.raises(ValueError):
        volume_profile(df, anchor="session")
    with pytest.raises(ValueError):
        volume_profile(df.iloc[:0], anchor="rolling")
    with pytest.raises(ValueError):
        volume_profile(df.drop(columns=["tick_volume"]))
