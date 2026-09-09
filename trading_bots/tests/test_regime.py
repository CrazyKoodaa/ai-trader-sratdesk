"""Tests core/regime.py (SPEC §4.8): Kausalitaet, Label-Switching-Remapping,
Sanity-Fallback, Proxy-Methoden."""
from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from core.regime import RegimeFilter

_HAS_HMMLEARN = importlib.util.find_spec("hmmlearn") is not None


def make_ohlcv(close: np.ndarray, start: str = "2023-01-01") -> pd.DataFrame:
    n = len(close)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * 1.0002
    low = np.minimum(open_, close) * 0.9998
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": np.full(n, 100.0)}, index=idx)


def trending_df(n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    t = np.arange(n)
    return make_ohlcv(100 + 0.05 * t + rng.normal(0, 0.05, n))


def choppy_df(n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    t = np.arange(n)
    return make_ohlcv(100 + 0.5 * np.sin(t / 3.0) + rng.normal(0, 0.05, n))


def two_regime_df(seed: int = 7) -> pd.DataFrame:
    """alternierende Vol-Regime: ruhig / volatil / ruhig / volatil."""
    rng = np.random.default_rng(seed)
    segs = [(0.0003, 700), (0.004, 500), (0.0003, 700), (0.004, 500)]
    rets = np.concatenate([rng.normal(0, s, m) for s, m in segs])
    return make_ohlcv(100.0 * np.exp(np.cumsum(rets)))


SEG_BOUNDS = np.cumsum([0, 700, 500, 700, 500])  # zu two_regime_df
HMM_PARAMS = {"min_train_bars": 300, "refit": "monthly", "hmm_iter": 60}


# ---------------------------------------------------------------- off/proxy
def test_off_allows_everything():
    rf = RegimeFilter("off").fit(choppy_df())
    assert all(rf.allow_trend(i) and rf.allow_range(i) for i in (0, 100, 599))


def test_invalid_method_raises():
    with pytest.raises(ValueError):
        RegimeFilter("magic")


def test_adx_proxy_trend_vs_chop():
    rt = RegimeFilter("adx_proxy").fit(trending_df())
    rc = RegimeFilter("adx_proxy").fit(choppy_df())
    # spaeter Bereich (ADX voll aufgeheizt)
    assert np.mean([rt.allow_trend(i) for i in range(300, 600)]) > 0.9
    assert np.mean([rc.allow_range(i) for i in range(300, 600)]) > 0.9


def test_adx_proxy_causality():
    df = trending_df()
    rf = RegimeFilter("adx_proxy").fit(df)
    before_t = [rf.allow_trend(i) for i in range(400)]
    before_r = [rf.allow_range(i) for i in range(400)]
    df2 = df.copy()
    df2.iloc[400:, df2.columns.get_loc("close")] *= 3.0
    df2.iloc[400:, df2.columns.get_loc("high")] *= 3.0
    df2.iloc[400:, df2.columns.get_loc("low")] *= 3.0
    rf2 = RegimeFilter("adx_proxy").fit(df2)
    assert [rf2.allow_trend(i) for i in range(400)] == before_t
    assert [rf2.allow_range(i) for i in range(400)] == before_r


def test_atr_percentile_runs():
    rf = RegimeFilter("atr_percentile").fit(choppy_df())
    assert isinstance(rf.allow_trend(500), bool)
    assert isinstance(rf.allow_range(500), bool)


def test_out_of_range_index_false():
    rf = RegimeFilter("adx_proxy").fit(choppy_df())
    assert not rf.allow_trend(10_000)
    assert not rf.allow_range(-1)


# ---------------------------------------------------------------- HMM
@pytest.mark.skipif(not _HAS_HMMLEARN, reason="hmmlearn nicht installiert")
def test_hmm_separates_vol_regimes():
    rf = RegimeFilter("hmm", HMM_PARAMS).fit(two_regime_df())
    assert any(d.ok for d in rf.diagnostics_), "kein einziger HMM-Refit ok"
    # spaete Segmente (Modell hat beide Regime gesehen):
    calm = range(int(SEG_BOUNDS[2]) + 50, int(SEG_BOUNDS[3]) - 10)
    vola = range(int(SEG_BOUNDS[3]) + 50, int(SEG_BOUNDS[4]) - 10)
    trend_calm = np.mean([rf.allow_trend(i) for i in calm])
    trend_vola = np.mean([rf.allow_trend(i) for i in vola])
    assert trend_vola > 0.8
    assert trend_calm < 0.2
    # allow_range ist Komplement
    assert rf.allow_range(int(SEG_BOUNDS[2]) + 100) != rf.allow_trend(
        int(SEG_BOUNDS[2]) + 100)


@pytest.mark.skipif(not _HAS_HMMLEARN, reason="hmmlearn nicht installiert")
def test_hmm_causality_future_irrelevant():
    df = two_regime_df()
    rf = RegimeFilter("hmm", HMM_PARAMS).fit(df)
    k = 1500
    before_t = [rf.allow_trend(i) for i in range(k)]
    before_r = [rf.allow_range(i) for i in range(k)]
    df2 = df.copy()
    for col in ("close", "high", "low", "open"):
        df2.iloc[k:, df2.columns.get_loc(col)] *= 2.0
    rf2 = RegimeFilter("hmm", HMM_PARAMS).fit(df2)
    assert [rf2.allow_trend(i) for i in range(k)] == before_t
    assert [rf2.allow_range(i) for i in range(k)] == before_r


@pytest.mark.skipif(not _HAS_HMMLEARN, reason="hmmlearn nicht installiert")
def test_hmm_label_switching_remapped_by_variance():
    """State-Remapping: trend_state ist immer der hoeher-Varianz-State,
    unabhaengig vom (willkuerlichen) HMM-Label."""
    rf = RegimeFilter("hmm", HMM_PARAMS)
    df = two_regime_df()
    rf.fit(df)
    feats = rf._features(df, rf.params["rv_len"], rf.params["atr_len"]).dropna()
    X = feats.to_numpy()
    for seed in (1, 42, 123):  # verschiedene Seeds -> evtl. getauschte Labels
        rf_seed = RegimeFilter("hmm", {**HMM_PARAMS, "random_state": seed})
        mu, sd = X.mean(axis=0), X.std(axis=0)
        Xs = (X - mu) / sd
        result = rf_seed._fit_one(Xs)
        assert result is not None and result[0] != "fail"
        model, trend_state = result
        states = model.predict(Xs)
        var_by_state = [X[states == s, 0].var() for s in range(2)]
        assert trend_state == int(np.argmax(var_by_state))


@pytest.mark.skipif(not _HAS_HMMLEARN, reason="hmmlearn nicht installiert")
def test_hmm_fallback_on_sanity_fail():
    # unmoegliche Sanity-Schwelle -> jeder Refit faellt -> adx_proxy
    rf = RegimeFilter("hmm", {**HMM_PARAMS, "min_train_bars": 300,
                              "self_trans_min": 1.01}).fit(two_regime_df())
    assert rf.diagnostics_ and all(not d.ok for d in rf.diagnostics_)
    used = {rf.method_used(i) for i in range(400, rf._n)}
    assert used == {"adx_proxy"}


@pytest.mark.skipif(not _HAS_HMMLEARN, reason="hmmlearn nicht installiert")
def test_hmm_fallback_on_degenerate_data():
    n = 900
    idx = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
                       "tick_volume": 100.0}, index=idx)
    rf = RegimeFilter("hmm", {"min_train_bars": 300, "refit": "weekly"}).fit(df)
    assert rf.diagnostics_ and all(not d.ok for d in rf.diagnostics_)
    used = {rf.method_used(i) for i in range(300, n)}
    assert used == {"adx_proxy"}


@pytest.mark.skipif(not _HAS_HMMLEARN, reason="hmmlearn nicht installiert")
def test_hmm_warmup_uses_proxy():
    rf = RegimeFilter("hmm", HMM_PARAMS).fit(two_regime_df())
    assert rf.method_used(0) == "warmup"  # Features noch NaN
    assert rf.method_used(100) == "adx_proxy"  # < min_train_bars
    assert rf.method_used(2000) == "hmm"


# ---------------------------------------------------------------- Smoke
_HAS_CORE_IND = importlib.util.find_spec("core.indicators") is not None


@pytest.mark.xfail(not _HAS_CORE_IND, strict=False,
                   reason="core.indicators in paralleler Entwicklung")
def test_smoke_imports():
    import core.indicators  # noqa: F401
    from core.regime import RegimeFilter as RF  # noqa: F401
