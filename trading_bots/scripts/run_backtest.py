#!/usr/bin/env python3
"""scripts/run_backtest.py — CLI: Config + Daten -> Backtest + Report.

Beispiele:
    python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml
    python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --stress 0.5,1,2,3
    python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --layers

Daten kommen aus ``--data-dir`` (CSV {SYMBOL}_{TF}.csv, UTC-Index, SPEC §3).
Kostenmodell ist IMMER aktiv (SPEC §1); ``--stress`` skaliert Spread +
Kommission (Slippage skaliert ueber den Spread mit, SPEC §4.2).
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.connector import load_ohlcv  # noqa: E402
from core.live import load_strategy_class  # noqa: E402  (Registry, lazy)

log = logging.getLogger("run_backtest")


# ---------------------------------------------------------------------------
# Config-Hilfen
# ---------------------------------------------------------------------------
def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    for key in ("strategy", "symbols", "timeframes"):
        if key not in cfg:
            raise ValueError(f"Config {path}: Schluessel {key!r} fehlt")
    return cfg


def load_common(path: str | Path = "configs/common.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def build_cost_model(costs_cfg: dict | None, common: dict, symbol: str,
                     stress: float = 1.0):
    """CostModel (SPEC §4.2) aus Strategie-Config, Fallback common.yaml."""
    from core.backtester import CostModel  # lazy
    base = dict((common.get("symbols", {}).get(symbol) or {}))
    base.update(costs_cfg or {})
    return CostModel(
        spread_points=float(base.get("spread_points", 0.0)) * stress,
        slippage_multiplier=float(base.get("slippage_multiplier", 1.0)),
        commission_per_lot_rt=float(base.get("commission_per_lot_rt", 0.0)) * stress,
        swap_long_pts=float(base.get("swap_long_pts", 0.0)),
        swap_short_pts=float(base.get("swap_short_pts", 0.0)),
        triple_swap_weekday=int(base.get("triple_swap_weekday", 2)),
        slippage_extra_points=float(base.get("slippage_extra_points", 0.0)) * stress,
    )


def build_backtest_config(cfg: dict, common: dict, symbol: str,
                          start: pd.Timestamp, end: pd.Timestamp,
                          stress: float = 1.0):
    from core.backtester import BacktestConfig  # lazy
    from core.risk import RiskConfig

    risk_raw = cfg.get("risk") or {}
    risk = RiskConfig(**{k: v for k, v in risk_raw.items()
                         if k in RiskConfig.__dataclass_fields__})
    sym_common = common.get("symbols", {}).get(symbol) or {}
    return BacktestConfig(
        symbol=symbol,
        timeframes=list(cfg["timeframes"]),
        start=start, end=end,
        costs=build_cost_model((cfg.get("costs") or {}).get(symbol), common, symbol, stress),
        risk=risk,
        intrabar=cfg.get("intrabar", "stop_first"),
        point_value=float(sym_common.get("point_value", 1.0)),
        point=float(sym_common.get("point", 1.0)),  # MT5-Punkte -> Preiseinheiten
        account_ccy_rate=float(sym_common.get("account_ccy_rate", 1.0)),
        initial_balance=float(cfg.get("initial_balance", 100_000.0)),
        volume_step=float(sym_common.get("volume_step", 0.01)),
        volume_min=float(sym_common.get("volume_min", 0.01)),
        volume_max=float(sym_common.get("volume_max", 100.0)),
    )


_DATA_CACHE: dict = {}


def load_data(cfg: dict, symbol: str, data_dir: str | Path,
              start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Laedt alle Timeframes aus dem CSV-Cache.

    Prozessweiter In-Memory-Cache: Stress-Matrix/Layer-Compare rufen mit
    identischem Fenster mehrfach auf — CSV-Parsing waere sonst der
    Flaschenhals.
    """
    key = (str(data_dir), symbol, tuple(cfg["timeframes"]), str(start), str(end))
    if key not in _DATA_CACHE:
        _DATA_CACHE[key] = {
            tf: load_ohlcv(symbol, tf, start, end, source="cache", data_dir=data_dir)
            for tf in cfg["timeframes"]
        }
    return _DATA_CACHE[key]


def resolve_window(cfg: dict, symbol: str,
                   data_dir: str | Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Backtest-Fenster aus cfg['start']/cfg['end'].

    Fehlen die Keys (rueckwaertskompatibler Default), wird die Ueberlappung
    der Datenabdeckung aller Timeframes verwendet (max. Start / min. Ende).
    """
    start, end = cfg.get("start"), cfg.get("end")
    if start is not None and end is not None:
        return pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    mins, maxs = [], []
    for tf in cfg["timeframes"]:
        base = Path(data_dir) / f"{symbol}_{tf.upper()}"
        pq = base.with_suffix(".parquet")
        if pq.exists():
            idx = pd.read_parquet(pq, columns=[]).index
            mins.append(pd.Timestamp(idx[0]))
            maxs.append(pd.Timestamp(idx[-1]))
        else:
            idx = pd.to_datetime(
                pd.read_csv(base.with_suffix(".csv"), usecols=["time"])["time"],
                utc=True)
            mins.append(idx.min())
            maxs.append(idx.max())
    return (pd.Timestamp(start, tz="UTC") if start is not None else max(mins),
            pd.Timestamp(end, tz="UTC") if end is not None else min(maxs))


def make_strategy(cfg: dict, meta_layer: dict | None = None):
    """Instanziiert die Strategie; meta_layer wird in params gemergt (A/B)."""
    params = copy.deepcopy(cfg.get("params") or {})
    params["meta_layer"] = copy.deepcopy(
        meta_layer if meta_layer is not None else (cfg.get("meta_layer") or {}))
    return load_strategy_class(cfg["strategy"])(params)


def run_single(cfg: dict, common: dict, symbol: str, data_dir: str | Path,
               stress: float = 1.0, meta_layer: dict | None = None):
    from core.backtester import Backtester  # lazy

    start, end = resolve_window(cfg, symbol, data_dir)
    log.info("Backtest-Fenster: %s .. %s", start, end)
    data = load_data(cfg, symbol, data_dir, start, end)
    bt_cfg = build_backtest_config(cfg, common, symbol, start, end, stress=stress)
    strategy = make_strategy(cfg, meta_layer=meta_layer)
    return Backtester(strategy, bt_cfg, data).run()


# ---------------------------------------------------------------------------
# Stress / Layers
# ---------------------------------------------------------------------------
def _stress_worker(args):
    """Prozess-Worker: ein Stress- oder Layer-Lauf (laedt eigene Daten).

    threadpool_limits(1): pinnt BLAS auf 1 Thread je Worker-Prozess (siehe
    core/validation.py::_wfa_eval_chunk) — verhindert N-Prozesse x M-BLAS-
    Threads-Oversubscription bei --workers > 1.
    """
    import threadpoolctl

    cfg, common, symbol, data_dir, stress, meta_layer = args
    with threadpoolctl.threadpool_limits(limits=1):
        return run_single(cfg, common, symbol, data_dir, stress=stress, meta_layer=meta_layer)


def _run_pool(tasks: list, workers: int) -> list:
    """tasks parallel (fork) oder sequenziell ausfuehren; Reihenfolge bleibt."""
    if workers <= 1 or len(tasks) <= 1:
        return [_stress_worker(t) for t in tasks]
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        return list(pool.map(_stress_worker, tasks))


def stress_matrix(cfg: dict, common: dict, symbol: str, data_dir: str | Path,
                  factors: list[float], workers: int = 1) -> pd.DataFrame:
    """Kosten-Stressmatrix: PF je Faktor (SPEC §7: PF(1x)>=1.5, 2x>=1.2, 3x>=1.0)."""
    tasks = [(cfg, common, symbol, data_dir, f, None) for f in factors]
    rows = {}
    for f, res in zip(factors, _run_pool(tasks, workers)):
        m = res.metrics
        rows[f"{f:g}x"] = {"n": m["n"], "pf": m["pf"], "winrate": m["winrate"],
                           "avg_r": m["avg_r"], "max_dd_balance": m["max_dd_balance"],
                           "total_pnl": m["total_pnl"]}
        log.info("Stress %gx: PF=%.3f n=%d", f, m["pf"], m["n"])
    return pd.DataFrame(rows).T


def layer_compare(cfg: dict, common: dict, symbol: str, data_dir: str | Path,
                  workers: int = 1):
    """A/B-Layer-Vergleich: Baseline (wie konfiguriert) + jeder Layer getoggelt."""
    from core.reporting import ab_compare  # lazy

    meta = dict(cfg.get("meta_layer") or {})
    variants = [("baseline", meta)]
    for layer, value in meta.items():
        toggled = dict(meta)
        toggled[layer] = ("off" if str(value).lower() in ("on", "true", "1") else "on") \
            if isinstance(value, str) else (not value)
        label = f"{layer}={'off' if toggled[layer] in (False, 'off') else 'on'}"
        variants.append((label, toggled))
    tasks = [(cfg, common, symbol, data_dir, 1.0, m) for _lbl, m in variants]
    results = {}
    for (label, _m), res in zip(variants, _run_pool(tasks, workers)):
        results[label] = res
    return ab_compare(results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest-CLI (SPEC §4.2)")
    parser.add_argument("--config", required=True, help="Strategie-YAML")
    parser.add_argument("--data-dir", default="data", help="CSV-Verzeichnis")
    parser.add_argument("--out", default=None, help="Report-Verzeichnis "
                        "(default: reports/{strategy}_{symbol})")
    parser.add_argument("--symbol", default=None, help="nur dieses Symbol")
    parser.add_argument("--stress", default=None,
                        help="Kosten-Stressfaktoren, z.B. 0.5,1,2,3")
    parser.add_argument("--layers", action="store_true",
                        help="A/B-Layer-Vergleich (meta_layer togglen)")
    parser.add_argument("--common", default="configs/common.yaml")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                        help="Parallele Prozesse fuer Stress-Matrix/Layer-Compare")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)

    from core.reporting import render_report  # lazy

    cfg = load_config(args.config)
    common = load_common(args.common)
    symbols = [args.symbol] if args.symbol else list(cfg["symbols"])
    rc = 0
    for symbol in symbols:
        out_dir = Path(args.out or f"reports/{cfg['strategy']}_{symbol}")
        if args.stress:
            factors = [float(x) for x in args.stress.split(",")]
            matrix = stress_matrix(cfg, common, symbol, args.data_dir, factors,
                                   workers=args.workers)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "stress.md").write_text(matrix.to_markdown(), encoding="utf-8")
            print(f"\n=== Kosten-Stressmatrix {symbol} ===\n{matrix.to_markdown()}\n")
            # Gates (SPEC §7.2) nur pruefbar, wenn 1/2/3 enthalten
            gates = {1.0: 1.5, 2.0: 1.2, 3.0: 1.0}
            for f, pf_min in gates.items():
                if f in factors:
                    pf = matrix.loc[f"{f:g}x", "pf"]
                    ok = pf >= pf_min
                    print(f"Gate PF({f:g}x) >= {pf_min}: {pf:.3f} -> {'PASS' if ok else 'FAIL'}")
                    rc |= 0 if ok else 1
            continue
        if args.layers:
            table = layer_compare(cfg, common, symbol, args.data_dir,
                                  workers=args.workers)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "layers.md").write_text(table.to_markdown(), encoding="utf-8")
            print(f"\n=== A/B-Layer-Vergleich {symbol} ===\n{table.to_markdown()}\n")
            continue
        res = run_single(cfg, common, symbol, args.data_dir)
        report_path = render_report(res, out_dir)
        print(f"Report: {report_path}")
        print(f"  n={res.metrics['n']} PF={res.metrics['pf']:.3f} "
              f"Winrate={res.metrics['winrate'] * 100:.1f}% "
              f"MaxDD(Bal)={res.metrics['max_dd_balance']:.2f}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
