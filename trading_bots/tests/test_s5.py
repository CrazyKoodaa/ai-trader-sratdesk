"""Tests strategies/s5_filtered_mr.py (SPEC §5/S5): Signal/Kein-Signal,
Gates, SL/TP-Geometrie, Filter-Layer, Kausalitaet.

Synthetik-Daten: Zufallswalk mit Drift; Signal-Bars (j_long=1019, j_short=1096)
wurden numerisch verifiziert: RSI14-Cross + ADX<25 + ATR<=Median + EMA200-Bias,
Stunde innerhalb 07-21 UTC.
"""
from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from strategies.s5_filtered_mr import S5FilteredMR

J_LONG = 1019    # long_df: RSI kreuzt unter 30, alle Gates ok, 11:00 UTC
J_SHORT = 1096   # short_df: RSI kreuzt ueber 70, alle Gates ok, 16:00 UTC


def _gen(seed: int, drift: float, n: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = drift + rng.normal(0, 0.15, n)
    close = 100 + np.cumsum(rets)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.06, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.06, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": np.full(n, 100.0)}, index=idx)


@pytest.fixture(scope="module")
def long_df() -> pd.DataFrame:
    return _gen(2, +0.004)


@pytest.fixture(scope="module")
def short_df() -> pd.DataFrame:
    return _gen(1000, -0.004)


def mk(**over) -> S5FilteredMR:
    return S5FilteredMR({"symbol": "XAUUSD", **over})


# ------------------------------------------------------------------ Signale
def test_long_signal(long_df):
    sig = mk().on_bar({"H1": long_df}, J_LONG)
    assert sig is not None
    assert sig.direction == +1
    assert sig.entry_type == "market" and sig.entry_price is None
    assert sig.symbol == "XAUUSD"
    assert sig.risk_pct == pytest.approx(0.005)
    assert sig.time == long_df.index[J_LONG]
    assert sig.meta["time_stop_bars"] == 48
    assert sig.meta["adx"] < 25.0
    assert sig.meta["atr"] <= sig.meta["atr_median"]
    assert sig.meta["rsi"] < 30.0
    assert float(long_df["close"].iloc[J_LONG]) > sig.meta["ema200"]


def test_long_sl_tp_geometry(long_df):
    sig = mk().on_bar({"H1": long_df}, J_LONG)
    close = float(long_df["close"].iloc[J_LONG])
    sl_dist = 1.5 * sig.meta["atr"]
    assert sig.stop_loss == pytest.approx(close - sl_dist)
    assert sig.take_profit == pytest.approx(close + 2.0 * sl_dist)  # 1:2 RR


def test_short_signal(short_df):
    sig = mk().on_bar({"H1": short_df}, J_SHORT)
    assert sig is not None
    assert sig.direction == -1
    close = float(short_df["close"].iloc[J_SHORT])
    sl_dist = 1.5 * sig.meta["atr"]
    assert sig.stop_loss == pytest.approx(close + sl_dist)
    assert sig.take_profit == pytest.approx(close - 2.0 * sl_dist)
    assert sig.meta["rsi"] > 70.0
    assert close < sig.meta["ema200"]


def test_no_signal_without_cross(long_df):
    assert mk().on_bar({"H1": long_df}, J_LONG - 1) is None
    assert mk().on_bar({"H1": long_df}, J_LONG + 1) is None


def test_no_signal_in_warmup(long_df):
    assert mk().on_bar({"H1": long_df}, 50) is None
    assert mk().on_bar({"H1": long_df}, 0) is None


# ------------------------------------------------------------------ Gates
def test_adx_gate_blocks(long_df):
    assert mk(adx_max=5.0).on_bar({"H1": long_df}, J_LONG) is None


def test_atr_median_gate_blocks(long_df):
    # atr_mult=0 -> kein Effekt auf Gate; stattdessen Median-Len hoch -> ATR > Median?
    # Direkter: adx/atr-Gate perParams nicht umgehbar -> pruefe, dass Gate greift,
    # indem ATR kuenstlich aufgeblaeht wird (letzte Bars hochvolatil).
    df = long_df.copy()
    j = J_LONG
    c = float(df["close"].iloc[j])
    df.iloc[j, df.columns.get_loc("high")] = c + 5.0   # ATR explodiert
    df.iloc[j, df.columns.get_loc("low")] = c - 5.0
    assert mk().on_bar({"H1": df}, j) is None


def test_ema_bias_blocks_countertrend_long(long_df):
    df = long_df.copy()
    j = J_LONG
    # EMA200 weit ueber den Kurs schieben: Historie +100, Signal-Bar unveraendert
    df.iloc[: j, df.columns.get_loc("close")] += 100.0
    assert mk().on_bar({"H1": df}, j) is None


def test_session_filter_blocks(long_df):
    h = long_df.index[J_LONG].hour
    # Fenster so legen, dass die Signal-Stunde ausgeschlossen ist
    assert mk(session_start_utc=(h + 1) % 24,
              session_end_utc=(h + 2) % 24).on_bar({"H1": long_df}, J_LONG) is None
    # Flag aus -> Signal trotz falschem Fenster
    assert mk(session_filter=False, session_start_utc=(h + 1) % 24,
              session_end_utc=(h + 2) % 24).on_bar({"H1": long_df}, J_LONG) is not None


# ------------------------------------------------------------------ Meta-Layer
class _NewsBlock:
    def is_blackout(self, ts, symbol):
        return True

    def tier1_halt(self, ts):
        return False


class _NewsTier1:
    def is_blackout(self, ts, symbol):
        return False

    def tier1_halt(self, ts):
        return True


class _RegimeNoRange:
    def allow_range(self, i):
        return False


def test_news_blackout_blocks(long_df):
    assert mk(news_filter_obj=_NewsBlock()).on_bar({"H1": long_df}, J_LONG) is None
    assert mk(news_filter_obj=_NewsBlock(),
              use_news_filter=False).on_bar({"H1": long_df}, J_LONG) is not None


def test_tier1_halt_blocks(long_df):
    assert mk(news_filter_obj=_NewsTier1()).on_bar({"H1": long_df}, J_LONG) is None
    assert mk(news_filter_obj=_NewsTier1(), use_tier1_halt=False)
    sig = mk(news_filter_obj=_NewsTier1(),
             use_tier1_halt=False).on_bar({"H1": long_df}, J_LONG)
    assert sig is not None


def test_regime_filter_blocks(long_df):
    assert mk(use_regime_filter=True,
              regime_obj=_RegimeNoRange()).on_bar({"H1": long_df}, J_LONG) is None
    assert mk(use_regime_filter=False,
              regime_obj=_RegimeNoRange()).on_bar({"H1": long_df}, J_LONG) is not None


# ------------------------------------------------------------------ Kausalitaet
def test_causality_future_bars_irrelevant(long_df):
    sig1 = mk().on_bar({"H1": long_df}, J_LONG)
    df2 = long_df.copy()
    for col in ("open", "high", "low", "close"):
        df2.iloc[J_LONG + 1:, df2.columns.get_loc(col)] *= 5.0
    sig2 = mk().on_bar({"H1": df2}, J_LONG)
    assert sig2 is not None
    assert sig2.direction == sig1.direction
    assert sig2.stop_loss == sig1.stop_loss
    assert sig2.take_profit == sig1.take_profit


def test_engine_passes_full_df(long_df):
    """Engine darf auch den vollen DF mit i liefern — intern wird bis i geslicet."""
    sig = mk().on_bar({"H1": long_df.iloc[: J_LONG + 50]}, J_LONG)
    ref = mk().on_bar({"H1": long_df}, J_LONG)
    assert sig is not None and sig.stop_loss == ref.stop_loss


def test_deterministic_rerun(long_df):
    a = mk().on_bar({"H1": long_df}, J_LONG)
    b = mk().on_bar({"H1": long_df}, J_LONG)
    assert a == b


# ------------------------------------------------------------------ VP-Layer
def _vp_dfs(df: pd.DataFrame, j: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Zwei Volumen-Varianten derselben Preis-Serie (Preise unveraendert ->
    RSI/ADX/ATR/EMA-Gates identisch, nur der VP-Layer sieht etwas anderes):
    - at_poc: Volumen-Cluster auf der Fenster-Bar, deren Mitte dem
      Signal-Close am naechsten liegt -> POC am Entry (F1 erlaubt)
    - in_lvn: hohe Volumen-Dichte ueberall, aber Entry-ueberdeckende Bars
      niedrig -> Signal-Close liegt in einer LVN (F6 blockiert)
    """
    entry = float(df["close"].iloc[j])
    win_lo = max(0, j - 119)                       # lookback_bars=120 (Default)
    mids = 0.5 * (df["high"] + df["low"])
    i_near = win_lo + int(np.argmin(
        (mids.iloc[win_lo: j + 1] - entry).abs().to_numpy()))
    at_poc = df.copy()
    at_poc["tick_volume"] = 100.0
    at_poc.iloc[i_near, at_poc.columns.get_loc("tick_volume")] = 5_000_000.0
    in_lvn = df.copy()
    in_lvn["tick_volume"] = (in_lvn["high"] - in_lvn["low"]) * 1e6
    cov = np.flatnonzero(((in_lvn["low"] <= entry)
                          & (in_lvn["high"] >= entry)).to_numpy())
    cov = cov[cov > win_lo]
    in_lvn.iloc[cov, in_lvn.columns.get_loc("tick_volume")] = 1.0
    return at_poc, in_lvn


def test_vp_filter_allows_at_poc(long_df):
    """VP-Layer enabled, POC am Signal-Close -> Signal mit identischem
    SL/TP (Gate passiert; A/B-Nachweis in meta)."""
    at_poc, _ = _vp_dfs(long_df, J_LONG)
    base = mk().on_bar({"H1": long_df}, J_LONG)
    sig = mk(vp_filter={"enabled": True, "anchor": "rolling"}).on_bar(
        {"H1": at_poc}, J_LONG)
    assert base is not None and sig is not None
    assert sig.stop_loss == base.stop_loss
    assert sig.take_profit == base.take_profit
    assert sig.meta["vp_enabled"] and sig.meta["vp_allowed"]
    assert sig.meta["vp_near_poc"] or sig.meta["vp_near_hvn"]


def test_vp_filter_blocks_in_lvn(long_df):
    """F6: Signal-Close in LVN -> kein Signal; gleiche Daten ohne den Layer
    -> Signal (Block kommt nachweislich aus dem VP-Gate)."""
    _, in_lvn = _vp_dfs(long_df, J_LONG)
    # Layer aus -> Signal trotz modifiziertem Volumen (Volumen aendert nur VP)
    assert mk().on_bar({"H1": in_lvn}, J_LONG) is not None
    # nur F6 aktiv (entry_requires_hvn aus) -> Block kommt aus der LVN
    assert mk(vp_filter={"enabled": True, "anchor": "rolling",
                         "entry_requires_hvn": False,
                         "block_lvn": True}).on_bar({"H1": in_lvn}, J_LONG) is None


# ------------------------------------------------------------------ Smoke
_HAS_CORE_IND = importlib.util.find_spec("core.indicators") is not None


@pytest.mark.xfail(not _HAS_CORE_IND, strict=False,
                   reason="core.indicators in paralleler Entwicklung")
def test_smoke_imports():
    import core.indicators  # noqa: F401
    from strategies.s5_filtered_mr import S5FilteredMR as S5  # noqa: F401
