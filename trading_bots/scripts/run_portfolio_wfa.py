"""scripts/run_portfolio_wfa.py — Portfolio-WFA ueber mehrere Symbole/Legs.

Jedes Leg (Strategie-Config + Symbol) wird UNABHAENGIG per Walk-Forward
optimiert (core.validation.walk_forward, wie scripts/run_wfa.py) — jedes
Symbol bekommt seine eigenen, eigenstaendig gewaehlten Best-Params je Fold.
Der Clou: die Positionsgroesse je Leg wird um ``--risk-scale`` (Default
1/Anzahl-Legs) reduziert, sodass das AGGREGIERTE Risiko ueber alle Legs
etwa dem eines Einzelsymbol-Systems entspricht — mehr Trades durch
Diversifikation, nicht durch mehr Risiko pro Position (SPEC-Wunsch:
"verschiedene Maerkte um Tradevolumen zu erhoehen bei gleichbleibendem
Risiko").

Portfolio-Kennzahlen (OOS-PF, WFE, DSR, MC-MaxDD, Kostenstress) werden aus
den PER-FOLD ZUSAMMENGEFUEHRTEN Trades aller Legs berechnet — echte
Portfolio-Metriken, nicht der Mittelwert der Einzel-Metriken. Fuer die
WFE-Berechnung wird je Leg/Fold zusaetzlich ein IS-Backtest mit den vom
Grid-Search gewaehlten Best-Params nachgefahren (die IS-Trades selbst
liefert core.validation.walk_forward nicht, nur den IS-PF-Skalar).

PBO/CSCV wird auf Portfolio-Ebene NICHT berechnet — die IS-PF-Matrizen der
Legs leben in getrennten, unabhaengig optimierten Parameterraeumen, eine
gemeinsame (Folds x Kombos)-Matrix ist dafuer nicht sauber definierbar.
Die einzelnen Legs behalten ihre eigenen PBO-Werte aus ihren separaten
run_wfa.py-Laeufen (falls vorhanden) als Referenz.

Nutzung:
  python scripts/run_portfolio_wfa.py \\
      --leg configs/s10_ema_cross_trend.yaml:NZDUSD \\
      --leg configs/s10_ema_cross_trend.yaml:AUDUSD \\
      --leg configs/s10_ema_cross_trend.yaml:GBPJPY \\
      --out reports/wfa_portfolio_s10
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_backtest import (  # noqa: E402
    build_backtest_config, load_common, load_config, load_data, resolve_window,
)
from scripts.run_wfa import check_gates  # noqa: E402

log = logging.getLogger("run_portfolio_wfa")


def _parse_leg(spec: str) -> tuple[str, str]:
    cfg_path, _, symbol = spec.rpartition(":")
    if not cfg_path or not symbol:
        raise ValueError(f"Leg-Spec muss 'config.yaml:SYMBOL' sein, bekam: {spec!r}")
    return cfg_path, symbol


def run_portfolio_wfa(leg_specs: list[str], data_dir: str = "data",
                      common_path: str = "configs/common.yaml",
                      gates_path: str = "configs/validation_gates.yaml",
                      out_dir: str | None = None, workers: int = 1,
                      risk_scale: float | None = None) -> tuple[dict, list]:
    from core import validation
    from core.backtester import Backtester
    from core.live import load_strategy_class
    from core.reporting import compute_metrics

    common = load_common(common_path)
    with open(gates_path, encoding="utf-8") as fh:
        gates = yaml.safe_load(fh) or {}

    legs_spec = [_parse_leg(s) for s in leg_specs]
    n_legs = len(legs_spec)
    scale = risk_scale if risk_scale is not None else 1.0 / n_legs
    log.info("Portfolio: %d Legs, risk_scale=%.4f", n_legs, scale)

    leg_results = []  # (symbol, cfg, common, data, bt_cfg, strategy_cls, WFAResult, n_combos)
    for cfg_path, symbol in legs_spec:
        cfg = load_config(cfg_path)
        cfg = json.loads(json.dumps(cfg))  # tiefe Kopie (YAML-Dict enthaelt nur Primitives)
        cfg["params"] = dict(cfg.get("params") or {})
        base_risk = float(cfg["params"].get("risk_pct", 0.005))
        cfg["params"]["risk_pct"] = base_risk * scale

        start, end = resolve_window(cfg, symbol, data_dir)
        data = load_data(cfg, symbol, data_dir, start, end)
        bt_cfg = build_backtest_config(cfg, common, symbol, start, end)
        strategy_cls = load_strategy_class(cfg["strategy"])

        wfo = cfg.get("wfo") or {}
        param_grid = wfo.get("param_space") or {}
        if not param_grid:
            raise ValueError(f"{cfg_path}: kein wfo.param_space")
        n_combos = int(np.prod([len(v) for v in param_grid.values()]))

        log.info("Leg %s/%s: risk_pct %.4f -> %.4f, %d Kombos",
                 cfg_path, symbol, base_risk, cfg["params"]["risk_pct"], n_combos)
        result = validation.walk_forward(
            strategy_cls, param_grid, data, bt_cfg,
            is_months=int(wfo.get("is_months", 24)),
            oos_months=int(wfo.get("oos_months", 6)),
            anchored=bool(wfo.get("anchored", False)),
            workers=workers,
            base_params=cfg["params"],
        )
        leg_results.append(dict(
            symbol=symbol, cfg=cfg, data=data, bt_cfg=bt_cfg,
            strategy_cls=strategy_cls, result=result, n_combos=n_combos,
        ))

    n_folds = min(len(lr["result"].folds) for lr in leg_results)
    if any(len(lr["result"].folds) != n_folds for lr in leg_results):
        log.warning("Legs haben unterschiedliche Fold-Zahlen (Datenabdeckung) "
                    "— auf gemeinsames Minimum (%d) gekappt.", n_folds)

    # -- Je Fold: OOS-Trades UND (nachgefahrene) IS-Trades ueber alle Legs mergen
    fold_oos: list[pd.DataFrame] = []
    fold_is_pf: list[float] = []
    fold_oos_pf: list[float] = []
    per_fold_meta = []
    for k in range(n_folds):
        oos_parts, is_parts = [], []
        for lr in leg_results:
            f = lr["result"].folds[k]
            if len(f.oos_trades):
                oos_parts.append(f.oos_trades)
            strat_is = lr["strategy_cls"](validation._expand_dotted(f.best_params))
            from core.backtester import BacktestConfig
            is_cfg = BacktestConfig(**{**lr["bt_cfg"].__dict__, "start": f.is_start, "end": f.is_end})
            is_trades = Backtester(strat_is, is_cfg, lr["data"]).run().trades
            if len(is_trades):
                is_parts.append(is_trades)
        oos_df = (pd.concat(oos_parts).sort_values("exit_time").reset_index(drop=True)
                  if oos_parts else pd.DataFrame())
        is_df = (pd.concat(is_parts).sort_values("exit_time").reset_index(drop=True)
                 if is_parts else pd.DataFrame())
        oos_pf = compute_metrics(oos_df).get("pf") if len(oos_df) else float("nan")
        is_pf = compute_metrics(is_df).get("pf") if len(is_df) else float("nan")
        fold_oos.append(oos_df)
        fold_is_pf.append(is_pf)
        fold_oos_pf.append(oos_pf)
        per_fold_meta.append((k, leg_results[0]["result"].folds[k].is_start,
                              leg_results[0]["result"].folds[k].is_end,
                              leg_results[0]["result"].folds[k].oos_start,
                              leg_results[0]["result"].folds[k].oos_end,
                              is_pf, oos_pf, len(oos_df)))

    oos_trades = (pd.concat(fold_oos).sort_values("exit_time").reset_index(drop=True)
                  if any(len(d) for d in fold_oos) else pd.DataFrame())
    n_oos = len(oos_trades)

    wfe_values = [o / i for o, i in zip(fold_oos_pf, fold_is_pf)
                  if np.isfinite(i) and i > 0 and np.isfinite(o)]
    wfe_median = float(np.median(wfe_values)) if wfe_values else None
    folds_ge_05 = float(np.mean([w >= 0.5 for w in wfe_values])) if wfe_values else None

    oos_metrics = compute_metrics(oos_trades) if n_oos else {"pf": 0.0}
    initial_balance = sum(lr["bt_cfg"].initial_balance for lr in leg_results) / n_legs
    mc = validation.monte_carlo_dd(oos_trades) if n_oos else None
    mc_p95_dd_pct = (mc["p95"] / initial_balance * 100.0) if mc else None

    dsr = None
    n_combos_total = sum(lr["n_combos"] for lr in leg_results)
    if n_oos and "r_multiple" in oos_trades.columns:
        dsr = validation.deflated_sharpe(oos_trades["r_multiple"].to_numpy(),
                                         n_trials=max(1, n_combos_total))

    # Kosten-Stress 2x/3x, portfolio-gemergt je Fold
    oos_pf_stress: dict[float, float | None] = {}
    for stress in (2.0, 3.0):
        if f"pf_{stress:g}x_min" not in gates:
            continue
        stress_parts = []
        for k in range(n_folds):
            for lr in leg_results:
                f = lr["result"].folds[k]
                strat_s = lr["strategy_cls"](validation._expand_dotted(f.best_params))
                from core.backtester import BacktestConfig
                cfg_s = build_backtest_config(lr["cfg"], common, lr["symbol"],
                                              f.oos_start, f.oos_end, stress=stress)
                t = Backtester(strat_s, cfg_s, lr["data"]).run().trades
                if len(t):
                    stress_parts.append(t)
        if stress_parts:
            oos_pf_stress[stress] = compute_metrics(
                pd.concat(stress_parts).sort_values("exit_time").reset_index(drop=True)
            ).get("pf")

    metrics = {
        "n_oos": n_oos, "oos_pf": oos_metrics.get("pf"),
        "wfe_median": wfe_median, "wfe_folds_ge_05": folds_ge_05,
        "mc_p95_dd_pct": mc_p95_dd_pct, "dsr": dsr, "pbo": None,
        "n_params": sum(len((lr["cfg"].get("wfo") or {}).get("param_space") or {}) for lr in leg_results),
        "oos_pf_2x": oos_pf_stress.get(2.0), "oos_pf_3x": oos_pf_stress.get(3.0),
        "n_folds": n_folds, "n_legs": n_legs, "risk_scale": scale,
    }
    checks = check_gates(metrics, gates)

    def _fmt(v, nd=3):
        return "n/a" if v is None else round(v, nd)

    print(f"\n=== Portfolio-WFA: {n_legs} Legs ({', '.join(s for _, s in legs_spec)}) ===")
    print(f"risk_scale={scale:.4f} (je Leg von risk_pct-Basis)")
    print(f"Folds: {n_folds} | OOS-Trades: {n_oos} | OOS-PF: {_fmt(metrics['oos_pf'])} | "
          f"WFE-Median: {_fmt(wfe_median)} | PF(2x): {_fmt(metrics['oos_pf_2x'])} | "
          f"PF(3x): {_fmt(metrics['oos_pf_3x'])} | DSR: {_fmt(dsr)}")
    for k, is_s, is_e, oos_s, oos_e, is_pf, oos_pf, n in per_fold_meta:
        print(f"  Fold {k}: IS {is_s.date()}..{is_e.date()} PF={is_pf:.2f} -> "
              f"OOS {oos_s.date()}..{oos_e.date()} PF={oos_pf:.2f} (n={n})")
    print("\n--- Gates (configs/validation_gates.yaml, SPEC §7; PBO nicht portfolio-weit berechnet) ---")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} ({detail})")

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if n_oos:
            oos_trades.to_csv(out / "oos_trades.csv", index=False)
        with open(out / "portfolio_gates.json", "w", encoding="utf-8") as fh:
            json.dump({"metrics": metrics, "legs": [s for _, s in legs_spec],
                       "checks": [(n, ok, d) for n, ok, d in checks]}, fh, indent=2, default=str)
        print(f"Artefakte: {out}")

    return metrics, checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Portfolio-WFA ueber mehrere Symbole/Legs")
    parser.add_argument("--leg", action="append", required=True,
                        help="config.yaml:SYMBOL, wiederholbar")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--common", default="configs/common.yaml")
    parser.add_argument("--gates", default="configs/validation_gates.yaml")
    parser.add_argument("--out", default=None)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--risk-scale", type=float, default=None,
                        help="Default: 1/Anzahl-Legs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)

    _metrics, checks = run_portfolio_wfa(
        args.leg, data_dir=args.data_dir, common_path=args.common,
        gates_path=args.gates, out_dir=args.out, workers=args.workers,
        risk_scale=args.risk_scale,
    )
    all_ok = all(ok for _n, ok, _d in checks) if checks else False
    print(f"\nERGEBNIS: {'ALLE GATES BESTANDEN' if all_ok else 'GATES NICHT BESTANDEN'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
