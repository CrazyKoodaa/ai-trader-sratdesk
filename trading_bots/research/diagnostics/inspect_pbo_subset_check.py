"""Capture the 12-combo (mc5/s21e-grid) is_pf_matrix and check whether the
6-combo (s21f/g-grid) matrix is a literal subset of it (same params, same
folds, same data => identical numbers), which would explain why PBO landed
on the exact same 24/70 across differently-shaped grids."""
import sys
sys.path.insert(0, ".")
import numpy as np
from scripts.run_backtest import build_backtest_config, load_common, load_config, load_data, resolve_window
from core import validation
from core.live import load_strategy_class

cfg = load_config("configs/s21e_goldreaper_plateau_only.yaml")  # same grid as mc5
common = load_common("configs/common.yaml")
symbol = "XAUUSD"
start, end = resolve_window(cfg, symbol, "data_mt5")
data = load_data(cfg, symbol, "data_mt5", start, end)
bt_cfg = build_backtest_config(cfg, common, symbol, start, end)
strategy_cls = load_strategy_class(cfg["strategy"])
wfo = cfg["wfo"]
param_grid = wfo["param_space"]
print("param_grid order:", list(param_grid.items()))
combos = validation._param_combinations(param_grid)
for idx, c in enumerate(combos):
    print(idx, c)

result = validation.walk_forward(
    strategy_cls, param_grid, data, bt_cfg,
    is_months=int(wfo["is_months"]), oos_months=int(wfo["oos_months"]),
    selection="pf", workers=16, base_params=cfg.get("params") or {},
)
X12 = np.asarray(result.is_pf_matrix, dtype=float)
np.save("/tmp/claude-1000/-home-crazyneo-projects-dev-ai-trader/4964324a-51b5-4c9d-8ceb-2e5d7e4aa2ec/scratchpad/s21e_is_pf_matrix_12.npy", X12)
print("X12 shape", X12.shape)
print("PBO(X12, S=8):", validation.pbo_cscv(X12, S=8))

X6 = np.load("/tmp/claude-1000/-home-crazyneo-projects-dev-ai-trader/4964324a-51b5-4c9d-8ceb-2e5d7e4aa2ec/scratchpad/s21g_is_pf_matrix.npy")
print("X6 shape", X6.shape)

# min_rr is the last key -> varies fastest in itertools.product order.
# min_rr=2.0 is the SECOND value in [1.5, 2.0] -> odd indices (1,3,5,7,9,11).
sub = X12[:, [1, 3, 5, 7, 9, 11]]
print("max abs diff X12[:, min_rr=2.0 cols] vs X6:", np.max(np.abs(sub - X6)))
print("elementwise equal (atol=1e-9):", np.allclose(sub, X6, atol=1e-9))

# Also directly recompute PBO on that subset alone, standalone.
print("PBO on extracted subset alone:", validation.pbo_cscv(sub, S=8))
