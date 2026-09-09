"""tests/test_validation.py — WFA/WFE, DSR, PBO, Monte-Carlo, Prop-Sim,
Plateau-Selektion (SPEC §4.9). Synthetische Daten inline (numpy seed)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from core.backtester import BacktestConfig, CostModel
from core.reporting import compute_metrics
from core.risk import RiskConfig
from core.validation import (
    WFAFold,
    WFAResult,
    block_bootstrap,
    deflated_sharpe,
    monte_carlo_dd,
    pbo_cscv,
    plateau_select,
    prop_simulation,
    walk_forward,
    wfe,
)
import core.validation as validation_module


# ---------------------------------------------------------------------------
# WFE (anhand handgesetzter Folds; walk_forward selbst ist Integration)
# ---------------------------------------------------------------------------
class TestWFE:
    def _result(self, pairs):
        folds = [
            WFAFold(fold=k, is_start=pd.Timestamp("2022-01-01", tz="UTC"),
                    is_end=pd.Timestamp("2023-01-01", tz="UTC"),
                    oos_start=pd.Timestamp("2023-01-01", tz="UTC"),
                    oos_end=pd.Timestamp("2023-07-01", tz="UTC"),
                    best_params={}, is_pf=is_pf, oos_pf=oos_pf,
                    oos_trades=pd.DataFrame())
            for k, (is_pf, oos_pf) in enumerate(pairs)
        ]
        return WFAResult(folds=folds)

    def test_wfe_median(self):
        r = self._result([(2.0, 1.0), (2.0, 1.5), (4.0, 1.0)])  # ratios .5,.75,.25
        assert wfe(r) == pytest.approx(0.5)

    def test_wfe_empty(self):
        assert wfe(WFAResult()) == 0.0


# ---------------------------------------------------------------------------
# Deflated Sharpe (Bailey / Lopez de Prado)
# ---------------------------------------------------------------------------
class TestDeflatedSharpe:
    def test_strong_edge_high_dsr(self):
        rng = np.random.default_rng(1)
        rets = rng.normal(0.002, 0.01, 500)  # klar positiver Drift
        assert deflated_sharpe(rets, n_trials=1) > 0.95

    def test_more_trials_lower_dsr(self):
        rng = np.random.default_rng(2)
        rets = rng.normal(0.001, 0.01, 300)
        dsr_few = deflated_sharpe(rets, n_trials=1)
        dsr_many = deflated_sharpe(rets, n_trials=10_000)
        assert dsr_many < dsr_few

    def test_noise_low_dsr(self):
        rng = np.random.default_rng(3)
        rets = rng.normal(0.0, 0.01, 300)
        assert deflated_sharpe(rets, n_trials=100) < 0.95

    def test_bounds(self):
        rng = np.random.default_rng(4)
        rets = rng.normal(0.0005, 0.01, 200)
        dsr = deflated_sharpe(rets, n_trials=50)
        assert 0.0 <= dsr <= 1.0


# ---------------------------------------------------------------------------
# PBO (CSCV, S=8)
# ---------------------------------------------------------------------------
class TestPBO:
    def test_consistent_ranking_pbo_zero(self):
        # Eine Strategie dominiert in JEDER Zeile -> IS-Beste auch OOS-Beste
        rng = np.random.default_rng(5)
        base = rng.normal(0, 1, (64, 6))
        base[:, 0] += 5.0  # Strategie 0 dominant
        assert pbo_cscv(base, S=8) == 0.0

    def test_shuffled_noise_high_pbo(self):
        # Strategie 0 im IS-Block dominant, im OOS-Block dominant schlecht
        # (antis persistent) -> IS-Beste faellt im OOS unter den Median
        T, N = 64, 4
        X = np.zeros((T, N))
        half = T // 2
        X[:half, 0] = 2.0   # IS-Haelfte: Strat 0 top
        X[:half, 1:] = 0.0
        X[half:, 0] = -2.0  # OOS-Haelfte: Strat 0 flop
        X[half:, 1:] = 0.0
        # Bloecke sind zeitlich geordnet; Kombis mit reinem IS aus erster
        # Haelfte waehlen Strat 0 -> OOS-Rang schlecht
        pbo = pbo_cscv(X, S=8)
        assert 0.0 <= pbo <= 1.0
        assert pbo > 0.3

    def test_invalid_input(self):
        with pytest.raises(ValueError):
            pbo_cscv(np.zeros(10), S=8)


# ---------------------------------------------------------------------------
# Monte-Carlo-MaxDD / Block-Bootstrap
# ---------------------------------------------------------------------------
class TestMonteCarlo:
    def test_all_winners_zero_dd(self):
        res = monte_carlo_dd(np.array([10.0] * 50), n=100, seed=1)
        assert res["p95"] == 0.0

    def test_deterministic_and_ordered(self):
        rng = np.random.default_rng(6)
        pnl = np.concatenate([rng.normal(15, 5, 60), rng.normal(-10, 5, 40)])
        r1 = monte_carlo_dd(pnl, n=500, seed=11)
        r2 = monte_carlo_dd(pnl, n=500, seed=11)
        assert r1 == r2  # Seed-Determinismus
        assert 0 <= r1["p50"] <= r1["p95"] <= r1["p99"] <= r1["max"]

    def test_dataframe_input(self):
        df = pd.DataFrame({"pnl": [10.0, -5.0, 20.0, -8.0]})
        res = monte_carlo_dd(df, n=50, seed=3)
        assert res["p95"] >= 0.0


class TestBlockBootstrap:
    def test_default_block_len_cuberoot(self):
        pnl = np.random.default_rng(7).normal(5, 20, 125)
        res = block_bootstrap(pnl, n=200, seed=9)
        assert res["block_len"] == 5  # 125^(1/3) = 5
        assert res["pnl_p05"] <= res["pnl_p50"] <= res["pnl_p95"]

    def test_deterministic(self):
        pnl = np.random.default_rng(8).normal(0, 10, 50)
        assert block_bootstrap(pnl, n=100, seed=4) == block_bootstrap(pnl, n=100, seed=4)


# ---------------------------------------------------------------------------
# Prop-Simulation
# ---------------------------------------------------------------------------
def _trades_df(pnls, start="2024-01-02"):
    idx = pd.date_range(start, periods=len(pnls), freq="4h", tz="UTC")
    return pd.DataFrame({"pnl": pnls, "exit_time": idx})


class TestPropSimulation:
    PROFILE = {"daily_loss_pct": 5.0, "overall_loss_pct": 10.0,
               "profit_target_pct": 10.0}

    def test_all_winners_no_breach_target_hit(self):
        trades = _trades_df([500.0] * 40)
        res = prop_simulation(trades, self.PROFILE, n_sims=100, seed=1,
                              initial_balance=10_000, n_days_target=30)
        assert res["p_daily_breach"] == 0.0
        assert res["p_overall_breach"] == 0.0
        assert res["p_target"] == 1.0
        assert len(res["eod_equity_median"]) > 0

    def test_all_losers_breach(self):
        trades = _trades_df([-600.0] * 40)  # -6 % vom 10k-Konto pro Trade
        res = prop_simulation(trades, self.PROFILE, n_sims=100, seed=2,
                              initial_balance=10_000)
        assert res["p_daily_breach"] == 1.0
        assert res["p_overall_breach"] == 1.0
        assert res["p_target"] == 0.0

    def test_deterministic_seed(self):
        trades = _trades_df(np.random.default_rng(9).normal(50, 300, 60))
        r1 = prop_simulation(trades, self.PROFILE, n_sims=200, seed=5)
        r2 = prop_simulation(trades, self.PROFILE, n_sims=200, seed=5)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Plateau-Selektion
# ---------------------------------------------------------------------------
class TestSelectBestParams:
    """``walk_forward``'s Fold-Selektor (``selection="pf"|"plateau"``,
    SPEC §4.9 "Plateau-Selektion statt Max-PF"). Nutzt dieselbe Spitze/
    Plateau-Konstellation wie TestPlateauSelect, aber ueber die
    combos/pfs-Schnittstelle, wie walk_forward sie tatsaechlich aufruft."""

    def _combos_pfs(self):
        # Profit-Factor-Skala (>= 0, Breakeven = 1.0) -- dieselbe Spitze/
        # Plateau-Geometrie wie TestPlateauSelect._grid(), aber um +1.0
        # verschoben, weil _select_best_params("plateau") PF intern wieder
        # um -1.0 verschiebt, bevor es an plateau_select geht (s. Docstring
        # dort: rohes PF ist nie negativ, "positive Nachbarn" waere sonst
        # immer 100% -> Plateau-Test degeneriert zu Arg-Max).
        pfs_by_combo = {
            (1, 1): 10.0, (1, 2): 0.0, (1, 3): 0.0,
            (2, 1): 1.5, (2, 2): 3.0, (2, 3): 2.8,
            (3, 1): 0.0, (3, 2): 2.5, (3, 3): 2.2,
        }
        combos = [{"a": a, "b": b} for (a, b) in pfs_by_combo]
        pfs = list(pfs_by_combo.values())
        return combos, pfs

    def test_pf_selection_picks_global_max(self):
        combos, pfs = self._combos_pfs()
        params, pf = validation_module._select_best_params(combos, pfs, "pf")
        assert params == {"a": 1, "b": 1}
        assert pf == pytest.approx(10.0)

    def test_plateau_selection_avoids_spike(self):
        combos, pfs = self._combos_pfs()
        params, pf = validation_module._select_best_params(combos, pfs, "plateau")
        assert params == {"a": 2, "b": 2}
        assert pf == pytest.approx(3.0)  # echter PF an (2,2), nicht die verschobene Metrik

    def test_plateau_shift_matters_for_all_positive_pf(self):
        """Regressionstest fuer den PF>=0-Degenerations-Bug: ohne die
        interne -1.0-Verschiebung waeren ALLE PF-Werte "positiv" und
        die Plateau-Bedingung (>=60% positive Nachbarn) triviell erfuellt
        fuer jede Zelle -> Ergebnis identisch zu reinem Arg-Max. Diese
        Fixture hat eine Spitze (1,1)=5.0 mit ausschliesslich <1.0-Nachbarn
        (unprofitabel) und ein stabiles Plateau um (2,2)=2.0 mit
        ausschliesslich >1.0-Nachbarn (profitabel) -- mit der Korrektur
        muss "plateau" das Plateau waehlen, NICHT die Spitze."""
        pfs_by_combo = {
            (1, 1): 5.0, (1, 2): 0.3, (1, 3): 0.3,
            (2, 1): 1.2, (2, 2): 2.0, (2, 3): 1.8,
            (3, 1): 0.3, (3, 2): 1.5, (3, 3): 1.3,
        }
        combos = [{"a": a, "b": b} for (a, b) in pfs_by_combo]
        pfs = list(pfs_by_combo.values())
        pf_params, pf_pf = validation_module._select_best_params(combos, pfs, "pf")
        plateau_params, plateau_pf = validation_module._select_best_params(
            combos, pfs, "plateau")
        assert pf_params == {"a": 1, "b": 1}
        assert pf_pf == pytest.approx(5.0)
        assert plateau_params == {"a": 2, "b": 2}
        assert plateau_pf == pytest.approx(2.0)
        assert plateau_params != pf_params, (
            "Plateau-Selektion darf bei diesem Setup NICHT mit Arg-Max "
            "zusammenfallen -- sonst ist die PF>=0-Degeneration zurueck.")

    def test_plateau_falls_back_to_pf_for_single_combo(self):
        params, pf = validation_module._select_best_params(
            [{"a": 1}], [3.0], "plateau")
        assert params == {"a": 1}
        assert pf == pytest.approx(3.0)


class TestPlateauSelect:
    def _grid(self):
        # 2D-Grid a x b; Plateau um (2,2)/(2,3)/(3,2)/(3,3) mit positiven
        # Metriken, Spitze bei (1,1) mit negativem Umfeld (Overfit-Falle)
        rows = []
        metrics = {
            (1, 1): 9.0, (1, 2): -1.0, (1, 3): -1.0,
            (2, 1): 0.5, (2, 2): 2.0, (2, 3): 1.8,
            (3, 1): -1.0, (3, 2): 1.5, (3, 3): 1.2,
        }
        for (a, b), m in metrics.items():
            rows.append({"a": a, "b": b, "metric": m})
        return pd.DataFrame(rows)

    def test_plateau_beats_spike(self):
        res = plateau_select(self._grid())
        # Spitze (1,1) hat 0 % positive Nachbarn -> verworfen;
        # Plateau-Zelle mit bester Metrik ist (2,2)
        assert res["selected"] == {"a": 2, "b": 2}
        assert res["metric"] == pytest.approx(2.0)

    def test_scores_cover_all_cells(self):
        res = plateau_select(self._grid())
        assert len(res["scores"]) == 9
        assert {"a", "b", "plateau_score", "metric"} <= set(res["scores"].columns)

    def test_fallback_when_no_plateau(self):
        df = pd.DataFrame({"a": [1, 2], "b": [1, 1], "metric": [-1.0, -2.0]})
        res = plateau_select(df)
        assert res["selected"] == {"a": 1, "b": 1}  # beste (weniger schlechte)


# ---------------------------------------------------------------------------
# compute_metrics-Rueckgrat (wird von BacktestResult verwendet)
# ---------------------------------------------------------------------------
class TestComputeMetrics:
    def test_pf_by_direction_and_year(self):
        exits = pd.to_datetime(
            ["2023-03-01", "2023-06-01", "2024-01-15", "2024-02-01"], utc=True)
        trades = pd.DataFrame({
            "entry_time": exits, "exit_time": exits,
            "direction": [1, 1, -1, -1],
            "entry": 0.0, "exit": 0.0, "sl": 0.0, "tp": 0.0, "lots": 1.0,
            "pnl": [100.0, -50.0, 200.0, -100.0],
            "r_multiple": [1.0, -0.5, 2.0, -1.0], "meta": [{}] * 4,
        })
        m = compute_metrics(trades)
        assert m["pf_long"] == pytest.approx(2.0)   # 100/50
        assert m["pf_short"] == pytest.approx(2.0)  # 200/100
        assert m["pf_by_year"][2023] == pytest.approx(2.0)
        assert m["pf_by_year"][2024] == pytest.approx(2.0)
        assert m["longest_losing_streak"] == 1
        assert m["n"] == 4


# ---------------------------------------------------------------------------
# walk_forward: base_params muessen JEDE Grid-Kombination erreichen
# (Regressionstest fuer den echten, session-uebergreifenden Bug: vorher
# erreichten NUR die gesweepten Grid-Keys die Strategie, jeder andere
# ``params:``-Wert aus der YAML fiel still auf den Python-Klassen-Default
# zurueck -- s. reports/gates_matrix_s1_s5.md "Offene Punkte" Punkt 4,
# reports/s14_xauusd_squeeze_volume.md).
# ---------------------------------------------------------------------------
class _RecordingStrategy:
    """Merkt sich die empfangenen Konstruktor-Params; handelt nie (kein
    Signal), damit walk_forward ohne Trades sauber durchlaeuft."""

    name = "recording_dummy"
    required_timeframes = ["D1"]
    received: list[dict] = []  # Klassen-Attribut: ueberlebt Re-Konstruktion

    def __init__(self, params: dict):
        self.params = dict(params)
        type(self).received.append(dict(params))

    def on_bar(self, bars, i):
        return None

    def on_trade_closed(self, trade):
        return None


def _make_daily_df(n_days: int) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n_days, freq="D", tz="UTC")
    price = 100.0 + np.arange(n_days, dtype=float) * 0.01
    return pd.DataFrame(
        {"open": price, "high": price + 0.5, "low": price - 0.5, "close": price,
         "tick_volume": np.full(n_days, 100.0)},
        index=idx,
    )


def _wfa_cfg() -> BacktestConfig:
    return BacktestConfig(
        symbol="TEST", timeframes=["D1"],
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        end=datetime(2020, 1, 1, tzinfo=timezone.utc),
        costs=CostModel(spread_points=1.0),
        risk=RiskConfig(risk_per_trade_pct=1.0, daily_loss_halt_pct=0.0,
                        eod_flat=False, friday_flat=False),
        initial_balance=10_000.0,
    )


class TestWalkForwardBaseParams:
    def test_sequential_path_merges_base_params(self):
        """workers=1 (sequenzieller Pfad): base_params muessen bei JEDER
        Kombi ankommen, gesweepte Keys ueberschreiben Basiswerte."""
        _RecordingStrategy.received = []
        data = {"D1": _make_daily_df(120)}
        cfg = _wfa_cfg()
        walk_forward(
            _RecordingStrategy, {"sweep_me": [1, 2]}, data, cfg,
            is_months=2, oos_months=1, workers=1,
            base_params={"marker": "present", "sweep_me": 0, "risk_pct": 0.005},
        )
        assert _RecordingStrategy.received, "keine Kombination wurde konstruiert"
        for params in _RecordingStrategy.received:
            assert params.get("marker") == "present", (
                "base_params (nicht gesweepter Key) hat die Strategie NICHT "
                f"erreicht: {params}")
            assert params.get("risk_pct") == 0.005
            # gesweepter Key ueberschreibt den Basiswert (0 kommt nie an):
            assert params.get("sweep_me") in (1, 2)

    def test_parallel_chunk_merges_base_params(self):
        """Direkter Test des Worker-Merges (_wfa_eval_chunk), ohne echten
        Prozess-Pool: dieselbe Merge-Logik, die auch bei workers>1 laeuft."""
        _RecordingStrategy.received = []
        data = {"D1": _make_daily_df(120)}
        cfg = _wfa_cfg()
        validation_module._W.update(
            cls=_RecordingStrategy, data=data, cfg=cfg,
            is_start=cfg.start, is_end=cfg.end,
            base_params={"marker": "present", "sweep_me": 0},
        )
        try:
            validation_module._wfa_eval_chunk([{"sweep_me": 7}, {"sweep_me": 8}])
        finally:
            validation_module._W.clear()
        assert len(_RecordingStrategy.received) == 2
        for params in _RecordingStrategy.received:
            assert params.get("marker") == "present"
        assert {p["sweep_me"] for p in _RecordingStrategy.received} == {7, 8}

    def test_oos_run_also_merges_base_params(self):
        """Die abschliessende OOS-Bewertung mit best_params muss base_params
        ebenfalls sehen (dritte Konstruktionsstelle in walk_forward)."""
        _RecordingStrategy.received = []
        data = {"D1": _make_daily_df(150)}
        cfg = _wfa_cfg()
        walk_forward(
            _RecordingStrategy, {"sweep_me": [1, 2]}, data, cfg,
            is_months=2, oos_months=1, workers=1,
            base_params={"marker": "present"},
        )
        # letzte Konstruktion pro Fold ist die OOS-Konstruktion mit best_params
        assert all(p.get("marker") == "present" for p in _RecordingStrategy.received)
