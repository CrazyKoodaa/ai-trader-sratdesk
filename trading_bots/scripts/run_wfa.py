#!/usr/bin/env python3
"""scripts/run_wfa.py — Walk-Forward-Analyse + Gates-Check (SPEC §4.9, §7).

Beispiel:
    python scripts/run_wfa.py --config configs/s1_trend_pullback.yaml \
        --symbol XAUUSD --gates configs/validation_gates.yaml

Exit-Code: 0 = alle geprueften Gates bestanden, 1 = mindestens eines FAIL.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_backtest import (  # noqa: E402
    build_backtest_config,
    load_common,
    load_config,
    load_data,
    resolve_window,
)

log = logging.getLogger("run_wfa")


def check_gates(metrics: dict, gates: dict) -> list[tuple[str, bool, str]]:
    """Vergleicht berechnete Kennzahlen mit validation_gates.yaml (SPEC §7)."""
    checks: list[tuple[str, bool, str]] = []

    def add(name, ok, detail):
        checks.append((name, bool(ok), detail))

    if "min_oos_trades" in gates:
        n = metrics.get("n_oos", 0)
        add(f"n(OOS) >= {gates['min_oos_trades']}", n >= gates["min_oos_trades"],
            f"n={n}")
    if "wfe_median_min" in gates and metrics.get("wfe_median") is not None:
        wfe = metrics["wfe_median"]
        add(f"WFE-Median >= {gates['wfe_median_min']}",
            wfe >= gates["wfe_median_min"], f"wfe={wfe:.3f}")
        if wfe > gates.get("wfe_lookahead_max", 1.0):
            add("WFE <= 1.0 (Lookahead-Verdacht)", False, f"wfe={wfe:.3f} > 1.0")
    if "wfe_folds_min_frac" in gates and metrics.get("wfe_folds_ge_05") is not None:
        frac = metrics["wfe_folds_ge_05"]
        add(f">= {gates['wfe_folds_min_frac'] * 100:.0f}% Folds WFE>=0.5",
            frac >= gates["wfe_folds_min_frac"], f"frac={frac:.2f}")
    if "pf_1x_min" in gates and metrics.get("oos_pf") is not None:
        pf = metrics["oos_pf"]
        add(f"PF(1x) >= {gates['pf_1x_min']}", pf >= gates["pf_1x_min"], f"pf={pf:.3f}")
    for stress in ("2", "3"):
        gate_key = f"pf_{stress}x_min"
        val = metrics.get(f"oos_pf_{stress}x")
        if gate_key in gates and val is not None:
            add(f"PF({stress}x, OOS, WFA-Params) >= {gates[gate_key]}",
                val >= gates[gate_key], f"pf={val:.3f}")
    if "dsr_min" in gates and metrics.get("dsr") is not None:
        dsr = metrics["dsr"]
        add(f"DSR >= {gates['dsr_min']}", dsr >= gates["dsr_min"], f"dsr={dsr:.3f}")
    if "pbo_max" in gates and metrics.get("pbo") is not None:
        pbo = metrics["pbo"]
        add(f"PBO/CSCV < {gates['pbo_max']}", pbo < gates["pbo_max"], f"pbo={pbo:.3f}")
    if "max_params_per_30_trades" in gates and metrics.get("n_oos"):
        n_params = metrics.get("n_params", 0)
        allowed = max(1, metrics["n_oos"] // 30) * gates["max_params_per_30_trades"]
        add(f"Params ({n_params}) <= {allowed} (1 je 30 OOS-Trades)",
            n_params <= allowed, f"{n_params} params bei n={metrics['n_oos']}")
    if "mc_p95_maxdd_pct" in gates and metrics.get("mc_p95_dd_pct") is not None:
        dd = metrics["mc_p95_dd_pct"]
        add(f"MC p95-MaxDD <= {gates['mc_p95_maxdd_pct']}%",
            dd <= gates["mc_p95_maxdd_pct"], f"p95={dd:.2f}%")
    if metrics.get("prop") is not None:
        prop = metrics["prop"]
        if "prop_p_daily_breach_max" in gates:
            add(f"P(Daily-Breach) <= {gates['prop_p_daily_breach_max'] * 100:.0f}%",
                prop["p_daily_breach"] <= gates["prop_p_daily_breach_max"],
                f"p={prop['p_daily_breach']:.4f}")
        if "prop_p_overall_breach_max" in gates:
            add(f"P(Overall-Breach) <= {gates['prop_p_overall_breach_max'] * 100:.0f}%",
                prop["p_overall_breach"] <= gates["prop_p_overall_breach_max"],
                f"p={prop['p_overall_breach']:.4f}")
    return checks


def run_wfa(config_path: str | Path, symbol: str, data_dir: str | Path,
            gates_path: str | Path, common_path: str | Path = "configs/common.yaml",
            out_dir: str | Path | None = None, workers: int = 1,
            wfo_override: dict | None = None) -> tuple[dict, list]:
    """Fuehrt WFA + Gates-Check aus. Rueckgabe: (metrics, checks).

    ``wfo_override``: Dict mit Grid-Eintraegen, die den Config-Raum
    ueberschreiben (z. B. gestufte Laeufe: erst ohne VP-Layer-Variation)."""
    from core import validation  # lazy
    from core.risk import load_prop_profile

    cfg = load_config(config_path)
    common = load_common(common_path)
    with open(gates_path, "r", encoding="utf-8") as fh:
        gates = yaml.safe_load(fh) or {}

    start, end = resolve_window(cfg, symbol, data_dir)
    data = load_data(cfg, symbol, data_dir, start, end)
    bt_cfg = build_backtest_config(cfg, common, symbol, start, end)

    wfo = cfg.get("wfo") or {}
    # Drei Config-Varianten akzeptieren (rueckwaertskompatibel):
    # a) wfo.param_space (S3/S4), b) wfo_space (S5), c) Listen direkt in wfo (S1/S2)
    reserved = {"is_months", "oos_months", "anchored"}
    param_grid = (wfo.get("param_space") or cfg.get("wfo_space")
                  or {k: v for k, v in wfo.items()
                      if isinstance(v, list) and k not in reserved})
    if not param_grid:
        raise ValueError("Config hat keinen WFO-Param-Raum (wfo.param_space / "
                         "wfo_space / Listen in wfo) — WFA nicht moeglich")
    if wfo_override:
        param_grid = {**param_grid, **wfo_override}
        log.info("WFO-Override aktiv: %s", wfo_override)

    from core.live import load_strategy_class
    strategy_cls = load_strategy_class(cfg["strategy"])

    log.info("WFA %s %s: is=%dM oos=%dM, %d Param-Kombos",
             cfg["strategy"], symbol, wfo.get("is_months", 24),
             wfo.get("oos_months", 6),
             int(np.prod([len(v) for v in param_grid.values()])))

    result = validation.walk_forward(
        strategy_cls, param_grid, data, bt_cfg,
        is_months=int(wfo.get("is_months", 24)),
        oos_months=int(wfo.get("oos_months", 6)),
        anchored=bool(wfo.get("anchored", False)),
        workers=workers,
        base_params=cfg.get("params") or {},
    )

    # --- Kennzahlen -------------------------------------------------------
    oos_trades = result.oos_trades
    n_oos = len(oos_trades)
    n_combos = int(np.prod([len(v) for v in param_grid.values()]))
    wfe_values = [o / i for o, i in zip(result.oos_pfs, result.is_pfs)
                  if np.isfinite(i) and i > 0 and np.isfinite(o)]
    wfe_median = float(np.median(wfe_values)) if wfe_values else None
    folds_ge_05 = (float(np.mean([w >= 0.5 for w in wfe_values]))
                   if wfe_values else None)

    from core.reporting import compute_metrics
    oos_metrics = compute_metrics(oos_trades) if n_oos else {"pf": 0.0}

    initial_balance = bt_cfg.initial_balance
    mc = validation.monte_carlo_dd(oos_trades) if n_oos else None
    mc_p95_dd_pct = (mc["p95"] / initial_balance * 100.0) if mc else None

    prop = None
    profile_name = bt_cfg.risk.prop_profile
    if profile_name not in (None, "", "none") and n_oos:
        prop = validation.prop_simulation(oos_trades, load_prop_profile(profile_name))

    # DSR (SPEC §7.4): OOS-R-Multiples, ehrliche Trial-Zaehlung = Grid-Groesse
    dsr = None
    if n_oos and "r_multiple" in oos_trades.columns:
        dsr = validation.deflated_sharpe(oos_trades["r_multiple"].to_numpy(),
                                         n_trials=max(1, n_combos))

    # PBO via CSCV (SPEC §7.4): IS-PF-Matrix Folds x Kombos
    pbo = None
    S = int(gates.get("pbo_S", 8))
    if len(result.is_pf_matrix) >= S and n_combos >= 2:
        X = np.asarray(result.is_pf_matrix, dtype=float)  # T=Folds, N=Kombos
        try:
            pbo = validation.pbo_cscv(X, S=S)
        except ValueError as exc:
            log.warning("PBO nicht berechenbar: %s", exc)

    # Kosten-Stress auf OOS mit den je Fold selektierten Parametern (SPEC §7.2)
    oos_pf_stress: dict[float, float | None] = {}
    if n_oos:
        from core.backtester import Backtester
        for stress in (2.0, 3.0):
            key = f"oos_pf_{stress:g}x"
            if f"pf_{stress:g}x_min" not in gates:
                continue
            trades_s = []
            base_params = cfg.get("params") or {}
            for f in result.folds:
                # BUGFIX 2026-09-08: f.best_params enthaelt NUR die WFO-
                # Grid-Overrides (core/validation.py speichert dort bewusst
                # nicht die volle Merge-Kombination), nicht die Basis-Params
                # der Config (primary_tf, higher_tf, feste Filter-Settings
                # etc.). Ohne Merge fallen alle Nicht-Grid-Parameter auf die
                # Klassen-Defaults zurueck -- bei S17 (David V2) z.B. primary_tf
                # zurueck auf den Klassen-Default "H1" statt der konfigurierten
                # "H4", was hier hart mit KeyError('H1') crashte, weil die
                # Backtest-Daten nur H4/D1 geladen hatten. Bei Strategien,
                # deren Klassen-Defaults zufaellig den Config-Werten entsprachen,
                # blieb der Fehler unsichtbar -- die PF(2x)/PF(3x)-Kostenstress-
                # Werte koennten fuer solche Faelle in dieser Session dennoch
                # mit falschen (Default- statt Config-)Parametern berechnet
                # worden sein. core/validation.py macht diesen Merge ({**base_params,
                # **params}) an jeder anderen Stelle korrekt -- hier fehlte er.
                strat_s = strategy_cls(validation._expand_dotted({**base_params, **f.best_params}))
                cfg_s = build_backtest_config(cfg, common, symbol,
                                              f.oos_start, f.oos_end, stress=stress)
                trades_s.append(Backtester(strat_s, cfg_s, data).run().trades)
            trades_s = [t for t in trades_s if len(t)]
            if trades_s:
                oos_pf_stress[stress] = compute_metrics(
                    pd.concat(trades_s).sort_values("exit_time")
                    .reset_index(drop=True)).get("pf")

    metrics = {
        "n_oos": n_oos,
        "oos_pf": oos_metrics.get("pf"),
        "wfe_median": wfe_median,
        "wfe_folds_ge_05": folds_ge_05,
        "mc_p95_dd_pct": mc_p95_dd_pct,
        "dsr": dsr,
        "pbo": pbo,
        "n_params": len(param_grid),
        "oos_pf_2x": oos_pf_stress.get(2.0),
        "oos_pf_3x": oos_pf_stress.get(3.0),
        "prop": prop,
        "n_folds": len(result.folds),
    }
    checks = check_gates(metrics, gates)

    # --- Ausgabe ----------------------------------------------------------
    def _fmt(v, nd=3):
        return "n/a" if v is None else round(v, nd)

    print(f"\n=== WFA {cfg['strategy']} / {symbol} ===")
    print(f"Folds: {len(result.folds)} | OOS-Trades: {n_oos} | "
          f"OOS-PF: {_fmt(metrics['oos_pf'])} | WFE-Median: {_fmt(wfe_median)} | "
          f"PF(2x): {_fmt(metrics['oos_pf_2x'])} | PF(3x): {_fmt(metrics['oos_pf_3x'])} | "
          f"DSR: {_fmt(dsr)} | PBO: {_fmt(pbo)}")
    for f in result.folds:
        print(f"  Fold {f.fold}: IS {f.is_start.date()}..{f.is_end.date()} "
              f"PF={f.is_pf:.2f} -> OOS {f.oos_start.date()}..{f.oos_end.date()} "
              f"PF={f.oos_pf:.2f} params={f.best_params}")
    print("\n--- Gates (configs/validation_gates.yaml, SPEC §7) ---")
    all_ok = True
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} ({detail})")
        all_ok &= ok
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if n_oos:
            oos_trades.to_csv(out / "oos_trades.csv", index=False)
        with open(out / "wfa_gates.json", "w", encoding="utf-8") as fh:
            import json
            json.dump({"metrics": {k: v for k, v in metrics.items() if k != "prop"},
                       "checks": [(n, ok, d) for n, ok, d in checks]}, fh,
                      indent=2, default=str)
        print(f"Artefakte: {out}")
    return metrics, checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Walk-Forward + Gates (SPEC §7)")
    parser.add_argument("--config", required=True)
    parser.add_argument("--symbol", default=None, help="default: erstes Symbol der Config")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--gates", default="configs/validation_gates.yaml")
    parser.add_argument("--common", default="configs/common.yaml")
    parser.add_argument("--out", default=None)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                        help="Parallele Prozesse fuer den IS-Grid-Search")
    parser.add_argument("--wfo-override", default=None,
                        help="JSON-Dict, das Grid-Eintraege einschraenkt, z.B. "
                             "'{\"vp_filter.enabled\": [false]}' (gestufte Laeufe)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)

    cfg = load_config(args.config)
    symbol = args.symbol or cfg["symbols"][0]
    override = json.loads(args.wfo_override) if args.wfo_override else None
    _metrics, checks = run_wfa(args.config, symbol, args.data_dir, args.gates,
                               common_path=args.common, out_dir=args.out,
                               workers=args.workers, wfo_override=override)
    all_ok = all(ok for _n, ok, _d in checks) if checks else False
    print(f"\nERGEBNIS: {'ALLE GATES BESTANDEN' if all_ok else 'GATES NICHT BESTANDEN'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
