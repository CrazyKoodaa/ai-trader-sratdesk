"""core/validation.py — WFA, WFE, DSR, PBO, Monte-Carlo, Prop-Sim (SPEC §4.9).

Alle Monte-Carlo-Anteile sind seed-kontrolliert (Determinismus, SPEC §1).
Gates: siehe configs/validation_gates.yaml (SPEC §7).
"""

from __future__ import annotations

import itertools
import logging
import time
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from core.backtester import BacktestConfig, Backtester
from core.reporting import compute_metrics

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Walk-Forward-Analyse
# ---------------------------------------------------------------------------
@dataclass
class WFAFold:
    fold: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    best_params: dict
    is_pf: float
    oos_pf: float
    oos_trades: pd.DataFrame


@dataclass
class WFAResult:
    folds: list[WFAFold] = field(default_factory=list)
    oos_trades: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    # IS-PFs aller Kombos je Fold (Folds x Kombos) — Grundlage fuer PBO/CSCV
    is_pf_matrix: list[list[float]] = field(default_factory=list)

    @property
    def is_pfs(self) -> list[float]:
        return [f.is_pf for f in self.folds]

    @property
    def oos_pfs(self) -> list[float]:
        return [f.oos_pf for f in self.folds]


def _param_combinations(param_grid: dict) -> list[dict]:
    keys = list(param_grid.keys())
    return [dict(zip(keys, combo)) for combo in itertools.product(*(param_grid[k] for k in keys))]


def _select_best_params(combos: list[dict], pfs: list[float], selection: str) -> tuple[dict, float]:
    """Waehlt die IS-Parameter fuer einen Fold. ``selection="pf"`` (Default,
    rueckwaertskompatibel): reines Arg-Max ueber die IS-PF-Spalte.
    ``selection="plateau"``: ``plateau_select`` (SPEC §4.9, "Plateau-Selektion
    statt Max-PF") -- bevorzugt eine Zelle mit stabiler Nachbarschaft
    (>=60% Nachbarzellen mit positiver Metrik) vor dem globalen Maximum,
    um Overfitting auf eine einzelne rauschende IS-Spitze zu vermeiden
    (die PBO/CSCV explizit bestraft). Faellt bei <2 Kombos oder <2 endlichen
    PFs auf reines Max-PF zurueck (plateau_select braucht >=2 Zeilen)."""
    if selection == "plateau" and len(combos) >= 2:
        finite = [(c, p) for c, p in zip(combos, pfs) if np.isfinite(p)]
        if len(finite) >= 2:
            df = pd.DataFrame([c for c, _ in finite])
            df["metric"] = [p for _, p in finite]
            res = plateau_select(df)
            return dict(res["selected"]), float(res["metric"])
    best_params, best_pf = None, -np.inf
    for params, pf in zip(combos, pfs):
        if np.isfinite(pf) and pf > best_pf:
            best_pf, best_params = pf, params
        elif best_params is None:
            best_params, best_pf = params, pf
    return best_params, best_pf


def _expand_dotted(params: dict) -> dict:
    """'vp_filter.enabled' -> {'vp_filter': {'enabled': ...}} (verschachtelt).

    WFO-Grids nutzen Dotted Keys; die Strategien erwarten verschachtelte
    Dicts (wie aus der YAML-Config)."""
    out: dict = {}
    for k, v in params.items():
        if "." in k:
            top, sub = k.split(".", 1)
            base = out.get(top)
            if isinstance(base, dict):
                base[sub] = v
            else:
                out[top] = {sub: v}
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


# -- Paralleler Grid-Search (Prozess-Pool, fork: Worker erben Daten CoW) ------
_W: dict = {}


def _wfa_eval_chunk(chunk: list[dict]) -> list[float]:
    """Worker: wertet eine Teilliste von Parameter-Kombos im IS aus.

    threadpool_limits(1): jeder Prozess-Worker pinnt BLAS (OpenBLAS/MKL) auf
    1 Thread. Ohne das kann jeder der N ProcessPoolExecutor-Worker zusaetzlich
    eigene BLAS-Threads aufmachen (N x M Threads auf 32 Kernen) — stille
    Oversubscription/Contention statt sauberer Skalierung mit --workers.
    """
    import threadpoolctl

    base_params = _W.get("base_params") or {}
    with threadpoolctl.threadpool_limits(limits=1):
        out = []
        for params in chunk:
            strat = _W["cls"](_expand_dotted({**base_params, **params}))
            fold_cfg = BacktestConfig(**{**_W["cfg"].__dict__,
                                         "start": _W["is_start"], "end": _W["is_end"]})
            out.append(Backtester(strat, fold_cfg, _W["data"]).run().metrics["pf"])
    return out


def _parallel_grid_eval(strategy_cls, combos: list[dict], data, cfg,
                        is_start, is_end, workers: int, base_params: dict) -> list[float]:
    """PFs aller Kombos, parallel. Reihenfolge = combos (deterministisch)."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor

    # fork: gesetzte Modul-Globals werden geerbt (kein Pickling der Daten)
    _W.update(cls=strategy_cls, data=data, cfg=cfg, is_start=is_start, is_end=is_end,
              base_params=base_params)
    n_chunks = min(workers, len(combos))
    chunk_size = -(-len(combos) // n_chunks)
    chunks = [combos[i:i + chunk_size] for i in range(0, len(combos), chunk_size)]
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        chunk_pfs = list(pool.map(_wfa_eval_chunk, chunks))
    return [pf for pfs in chunk_pfs for pf in pfs]


def walk_forward(
    strategy_cls,
    param_grid: dict,
    data: dict[str, pd.DataFrame],
    cfg: BacktestConfig,
    is_months: int = 24,
    oos_months: int = 6,
    anchored: bool = False,
    selection: str = "pf",
    workers: int = 1,
    base_params: dict | None = None,
) -> WFAResult:
    """Walk-Forward-Analyse: rolling (Default) oder anchored Fenster.

    ``data``: {tf: OHLCV-DataFrame}. ``cfg`` dient als Template; start/end
    werden je Fold gesetzt. Selektion im IS: ``selection="pf"`` (Default,
    rueckwaertskompatibel) = max Profit Factor; ``selection="plateau"`` =
    ``plateau_select`` (SPEC §4.9) -- s. ``_select_best_params``.
    ``workers`` > 1 parallelisiert den IS-Grid-Search ueber Prozesse
    (fork; Ergebnis identisch zur sequenziellen Ausfuehrung).

    ``base_params``: Basis-Parameter (i.d.R. Config-``params:``-Block), die
    JEDER Grid-Kombination als Default untergelegt werden, bevor die
    gesweepten Werte druebergemischt werden (dict-Overwrite, dann
    ``_expand_dotted``). Ohne das erreichen nur die im WFO-Grid gesweepten
    Keys die Strategie ueberhaupt — alle anderen ``params:``-Werte aus der
    YAML fallen sonst STILL auf den Python-Klassen-Default zurueck (realer,
    frueher dokumentierter Bug, s. reports/gates_matrix_s1_s5.md "Offene
    Punkte" — hier behoben)."""
    base_params = dict(base_params or {})
    idx = data[cfg.timeframes[0]].index
    data_start, data_end = idx.min(), idx.max()

    combos = _param_combinations(param_grid)
    folds: list[WFAFold] = []
    is_pf_matrix: list[list[float]] = []
    oos_start = data_start + pd.DateOffset(months=is_months)
    k = 0
    while True:
        is_start = data_start if anchored else oos_start - pd.DateOffset(months=is_months)
        is_end = oos_start
        oos_end = oos_start + pd.DateOffset(months=oos_months)
        if oos_start >= data_end:
            break
        oos_end = min(oos_end, data_end)
        if (oos_end - oos_start).days < 20:  # Rest-Stummel verwerfen
            break

        # IS: Grid-Search (parallel ueber Prozesse; Reihenfolge bleibt
        # die von combos => identische Selektion wie sequenziell)
        log.info("Fold %d: IS %s..%s, Grid %d Kombos, %d Worker",
                 k, is_start.date(), is_end.date(), len(combos), workers)
        t0 = time.monotonic()
        if workers > 1 and len(combos) > 1:
            pfs = _parallel_grid_eval(strategy_cls, combos, data, cfg,
                                      is_start, is_end, workers, base_params)
        else:
            pfs = []
            for params in combos:
                strat = strategy_cls(_expand_dotted({**base_params, **params}))
                fold_cfg = BacktestConfig(**{**cfg.__dict__, "start": is_start, "end": is_end})
                pfs.append(Backtester(strat, fold_cfg, data).run().metrics["pf"])
        best_params, best_pf = _select_best_params(combos, pfs, selection)
        log.info("Fold %d: IS fertig (%.0fs), best PF=%.3f params=%s",
                 k, time.monotonic() - t0, best_pf, best_params)

        # OOS mit besten Parametern
        strat = strategy_cls(_expand_dotted({**base_params, **best_params}))
        fold_cfg = BacktestConfig(**{**cfg.__dict__, "start": oos_start, "end": oos_end})
        res = Backtester(strat, fold_cfg, data).run()
        folds.append(WFAFold(
            fold=k, is_start=is_start, is_end=is_end, oos_start=oos_start,
            oos_end=oos_end, best_params=best_params,
            is_pf=float(best_pf), oos_pf=float(res.metrics["pf"]),
            oos_trades=res.trades,
        ))
        is_pf_matrix.append([float(p) for p in pfs])
        oos_start = oos_start + pd.DateOffset(months=oos_months)
        k += 1

    _nonempty = [f.oos_trades for f in folds if len(f.oos_trades)]
    oos_trades = (
        pd.concat(_nonempty).sort_values("exit_time").reset_index(drop=True)
        if _nonempty else pd.DataFrame()
    )
    return WFAResult(folds=folds, oos_trades=oos_trades, is_pf_matrix=is_pf_matrix)


def wfe(result: WFAResult) -> float:
    """Walk-Forward-Efficiency: median(OOS-PF / IS-PF). Gate: >= 0.5 (SPEC §7)."""
    ratios = [
        f.oos_pf / f.is_pf for f in result.folds
        if np.isfinite(f.is_pf) and f.is_pf > 0 and np.isfinite(f.oos_pf)
    ]
    if not ratios:
        return 0.0
    return float(np.median(ratios))


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014)
# ---------------------------------------------------------------------------
def deflated_sharpe(returns, n_trials: int = 1, periods_per_year: float = 252.0) -> float:
    """Probabilistische Sharpe Ratio gegen den Expected-Max-SR-Benchmark aus
    ``n_trials`` unabhaengigen Versuchen. Rueckgabe: P(SR > SR*) in [0,1].
    Gate: >= 0.95 (SPEC §7).
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    T = len(r)
    if T < 3 or n_trials < 1:
        return 0.0
    sr = r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else 0.0
    # Schiefe/Kurtosis der Returns
    g3 = float(stats.skew(r))
    g4 = float(stats.kurtosis(r, fisher=False))  # Pearson (Normal = 3)
    # Varianz des SR-Schaetzers (LdP, Gl. 4)
    var_sr = (1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2) / (T - 1.0)
    if var_sr <= 0:
        return 0.0
    # Erwartetes Maximum von N iid normalen SR-Schaetzern (Euler-Mascheroni)
    gamma = 0.5772156649015329
    n = float(n_trials)
    sr_star = np.sqrt(var_sr) * (
        (1 - gamma) * stats.norm.ppf(1 - 1.0 / n)
        + gamma * stats.norm.ppf(1 - 1.0 / (n * np.e))
    )
    dsr = stats.norm.cdf((sr - sr_star) / np.sqrt(var_sr))
    return float(dsr)


# ---------------------------------------------------------------------------
# PBO via Combinatorially Symmetric Cross-Validation (Bailey et al.)
# ---------------------------------------------------------------------------
def pbo_cscv(perf_matrix, S: int = 8) -> float:
    """Probability of Backtest Overfitting. ``perf_matrix``: T x N
    (T Beobachtungen, N Strategie-Varianten). Gate: < 0.10 (SPEC §7).
    """
    X = np.asarray(perf_matrix, dtype=float)
    if X.ndim == 1:
        raise ValueError("perf_matrix muss 2-dimensional (T x N) sein")
    T, N = X.shape
    if S % 2 or S < 2 or T < S or N < 2:
        raise ValueError(f"Ungueltig: T={T}, N={N}, S={S}")
    blocks = np.array_split(np.arange(T), S)
    logits = []
    for is_blocks in combinations(range(S), S // 2):
        is_mask = np.zeros(T, dtype=bool)
        for b in is_blocks:
            is_mask[blocks[b]] = True
        is_perf = X[is_mask].mean(axis=0)
        oos_perf = X[~is_mask].mean(axis=0)
        best = int(np.argmax(is_perf))
        # Rang der IS-besten Strategie im OOS (0 = schlechteste)
        rank = stats.rankdata(oos_perf, method="average")[best]
        omega = rank / (N + 1.0)
        logits.append(np.log(omega / (1 - omega)))
    logits = np.asarray(logits)
    return float((logits < 0).mean())


# ---------------------------------------------------------------------------
# Monte-Carlo-Drawdown (Trade-Shuffle)
# ---------------------------------------------------------------------------
def _pnl_array(trades) -> np.ndarray:
    if isinstance(trades, pd.DataFrame):
        return trades["pnl"].to_numpy(dtype=float)
    return np.asarray(trades, dtype=float)


def monte_carlo_dd(trades, n: int = 10000, seed: int = 42) -> dict:
    """Trade-Shuffle: p95-MaxDD der permutierten Equity-Pfade (Balance-DD)."""
    pnl = _pnl_array(trades)
    if len(pnl) == 0:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "max": 0.0}
    rng = np.random.default_rng(seed)
    dds = np.empty(n)
    for k in range(n):
        perm = rng.permutation(pnl)
        curve = np.cumsum(perm)
        peak = np.maximum.accumulate(curve)
        dds[k] = (peak - curve).max() if len(curve) else 0.0
    return {
        "p50": float(np.percentile(dds, 50)),
        "p95": float(np.percentile(dds, 95)),
        "p99": float(np.percentile(dds, 99)),
        "mean": float(dds.mean()),
        "max": float(dds.max()),
    }


# ---------------------------------------------------------------------------
# Stationary Block-Bootstrap (Politis & Romano)
# ---------------------------------------------------------------------------
def block_bootstrap(trades, block_len: int | None = None, n: int = 10000,
                    seed: int = 42) -> dict:
    """Stationary Bootstrap (Blocklaenge geometrisch, Mittel ~T^(1/3)).
    Rueckgabe: Perzentile der gebootstrapten Gesamt-PnL und des PF."""
    pnl = _pnl_array(trades)
    T = len(pnl)
    if T == 0:
        return {"block_len": 0, "pnl_p05": 0.0, "pnl_p50": 0.0, "pnl_p95": 0.0,
                "pf_p05": 0.0, "pf_p50": 0.0, "pf_p95": 0.0}
    if block_len is None:
        block_len = max(1, int(round(T ** (1.0 / 3.0))))
    p = 1.0 / block_len
    rng = np.random.default_rng(seed)
    totals = np.empty(n)
    pfs = np.empty(n)
    for k in range(n):
        sample = []
        i = int(rng.integers(0, T))
        while len(sample) < T:
            if rng.random() < p:
                i = int(rng.integers(0, T))
            sample.append(pnl[i])
            i = (i + 1) % T
        s = np.asarray(sample)
        totals[k] = s.sum()
        wins, losses = s[s > 0].sum(), -s[s < 0].sum()
        pfs[k] = wins / losses if losses > 0 else np.inf
    finite = pfs[np.isfinite(pfs)]
    return {
        "block_len": block_len,
        "pnl_p05": float(np.percentile(totals, 5)),
        "pnl_p50": float(np.percentile(totals, 50)),
        "pnl_p95": float(np.percentile(totals, 95)),
        "pf_p05": float(np.percentile(finite, 5)),
        "pf_p50": float(np.percentile(finite, 50)),
        "pf_p95": float(np.percentile(finite, 95)),
    }


# ---------------------------------------------------------------------------
# Prop-Firm-Simulation
# ---------------------------------------------------------------------------
def prop_simulation(trades, profile: dict, n_sims: int = 10000, seed: int = 42,
                    initial_balance: float = 100_000.0,
                    n_days_target: int | None = None) -> dict:
    """Monte-Carlo ueber Trade-Shuffles mit Prop-Regeln.

    Liefert P(Daily-Breach), P(Overall-Breach), P(Profit-Target in N Tagen)
    und den medianen EOD-Equity-Verlauf (normiert auf Startbalance).

    Tage werden aus den Original-``exit_time``s abgeleitet: die Trades je
    Kalendertag-Struktur bleibt erhalten, nur die Trade-Folge wird neu
    gemischt (Trades werden zufaellig auf die Tage verteilt, Anzahl pro Tag
    wie im Original).
    """
    pnl = _pnl_array(trades)
    T = len(pnl)
    if T == 0:
        return {"p_daily_breach": 0.0, "p_overall_breach": 0.0,
                "p_target": 0.0, "eod_equity_median": [], "n_sims": n_sims}

    if isinstance(trades, pd.DataFrame) and "exit_time" in trades.columns:
        days = pd.to_datetime(trades["exit_time"], utc=True).dt.normalize()
        trades_per_day = days.groupby(days).size().to_numpy()
    else:
        trades_per_day = np.array([T])
    D = len(trades_per_day)

    daily_pct = float(profile.get("daily_loss_pct", 0.0) or 0.0)
    overall_pct = float(profile.get("overall_loss_pct", 0.0) or 0.0)
    target_pct = float(profile.get("profit_target_pct", 0.0) or 0.0)
    if n_days_target is None:
        n_days_target = D

    rng = np.random.default_rng(seed)
    daily_breaches = overall_breaches = target_hits = 0
    eod_paths = np.empty((n_sims, D))
    for k in range(n_sims):
        perm = rng.permutation(pnl)
        bal = initial_balance
        day_start = bal
        breached = od = False
        target_day = -1
        pos = 0
        for d in range(D):
            day_start = bal
            for _ in range(trades_per_day[d]):
                bal += perm[pos]
                pos += 1
                if overall_pct and (initial_balance - bal) / initial_balance * 100 >= overall_pct:
                    od = True
                if daily_pct and (day_start - bal) / day_start * 100 >= daily_pct:
                    breached = True
            eod_paths[k, d] = bal
            if target_pct and target_day < 0 and (bal - initial_balance) / initial_balance * 100 >= target_pct:
                target_day = d
        daily_breaches += breached
        overall_breaches += od
        target_hits += (0 <= target_day < n_days_target)

    return {
        "p_daily_breach": daily_breaches / n_sims,
        "p_overall_breach": overall_breaches / n_sims,
        "p_target": target_hits / n_sims,
        "eod_equity_median": (np.median(eod_paths, axis=0) / initial_balance).tolist(),
        "n_sims": n_sims,
    }


# ---------------------------------------------------------------------------
# Plateau-Selektion (Anti-Overfitting)
# ---------------------------------------------------------------------------
def plateau_select(grid_results, min_positive_frac: float = 0.6) -> dict:
    """Waehlt Parameter aus stabilen Plateaus statt Max-PF.

    ``grid_results``: DataFrame mit einer Spalte je Parameter + Spalte
    ``metric`` (z.B. PF), ODER Series mit MultiIndex (Param-Werte) und
    metric-Werten.

    Ein Punkt gilt als Plateau, wenn >= ``min_positive_frac`` (Default 60 %)
    seiner direkten Nachbarzellen (je Dimension benachbarte Stufen) eine
    positive Metrik haben. Rueckgabe: {"selected": {params}, "metric": float,
    "scores": DataFrame mit Plateau-Score je Zelle}.
    """
    if isinstance(grid_results, pd.Series):
        df = grid_results.rename("metric").reset_index()
    else:
        df = grid_results.copy()
    param_cols = [c for c in df.columns if c != "metric"]
    if not param_cols:
        raise ValueError("Keine Parameter-Spalten gefunden")

    levels = {c: sorted(df[c].unique()) for c in param_cols}
    lookup = {tuple(row[c] for c in param_cols): float(row["metric"]) for _, row in df.iterrows()}

    scores: dict[tuple, float] = {}
    for combo in itertools.product(*(levels[c] for c in param_cols)):
        neighbors = 0
        positive = 0
        for j, c in enumerate(param_cols):
            lv = levels[c]
            pos = lv.index(combo[j])
            for step in (-1, 1):
                k = pos + step
                if 0 <= k < len(lv):
                    nb = combo[:j] + (lv[k],) + combo[j + 1:]
                    if nb in lookup:
                        neighbors += 1
                        positive += lookup[nb] > 0
        scores[combo] = (positive / neighbors) if neighbors > 0 else 0.0

    plateau = {c: s for c, s in scores.items() if s >= min_positive_frac}
    if plateau:
        # Innerhalb des Plateaus: beste Metrik, Tie-Break: hoechster Score
        best = max(plateau, key=lambda c: (lookup[c], plateau[c]))
        selected = dict(zip(param_cols, best))
        metric = lookup[best]
    else:
        best = max(scores, key=lambda c: lookup[c])
        selected = dict(zip(param_cols, best))
        metric = lookup[best]

    score_df = pd.DataFrame(
        [dict(zip(param_cols, combo)) | {"plateau_score": s, "metric": lookup[combo]}
         for combo, s in scores.items()]
    )
    return {"selected": selected, "metric": float(metric), "scores": score_df}
