"""Capture the real is_pf_matrix from an S21 WFA run and inspect it directly,
to check whether the bit-identical PBO=24/70 across differently-shaped runs
is a genuine data property or a pipeline bug."""
import sys
sys.path.insert(0, ".")
import numpy as np
from scripts.run_backtest import build_backtest_config, load_common, load_config, load_data, resolve_window
from core import validation
from core.live import load_strategy_class

cfg = load_config("configs/s21g_goldreaper_smallgrid_pf.yaml")
common = load_common("configs/common.yaml")
symbol = "XAUUSD"
start, end = resolve_window(cfg, symbol, "data_mt5")
data = load_data(cfg, symbol, "data_mt5", start, end)
bt_cfg = build_backtest_config(cfg, common, symbol, start, end)
strategy_cls = load_strategy_class(cfg["strategy"])
wfo = cfg["wfo"]
param_grid = wfo["param_space"]

result = validation.walk_forward(
    strategy_cls, param_grid, data, bt_cfg,
    is_months=int(wfo["is_months"]), oos_months=int(wfo["oos_months"]),
    selection="pf", workers=16, base_params=cfg.get("params") or {},
)
X = np.asarray(result.is_pf_matrix, dtype=float)
np.save("/tmp/claude-1000/-home-crazyneo-projects-dev-ai-trader/4964324a-51b5-4c9d-8ceb-2e5d7e4aa2ec/scratchpad/s21g_is_pf_matrix.npy", X)
print("shape", X.shape)
print(X)
print("column-wise correlation matrix:")
print(np.round(np.corrcoef(X, rowvar=False), 4))
print("PBO(S=8) on real matrix:", validation.pbo_cscv(X, S=8))

# Perturb: shuffle only the WORST-performing combo's column slightly,
# re-check PBO sensitivity on this exact real matrix's shape/scale.
rng = np.random.default_rng(1)
X2 = X.copy()
X2[:, 0] = X2[:, 0] * rng.uniform(0.8, 1.2, size=X2.shape[0])
print("PBO after perturbing column 0:", validation.pbo_cscv(X2, S=8))

X3 = X.copy()
X3 = X3[:, rng.permutation(X3.shape[1])]
print("PBO after column-permute (should be identical, order-invariant across combos? ):", validation.pbo_cscv(X3, S=8))
