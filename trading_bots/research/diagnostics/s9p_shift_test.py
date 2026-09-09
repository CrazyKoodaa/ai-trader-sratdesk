"""Anti-repaint shift-test (SPEC §7.7): "+1 Bar Shift -> Ergebnis darf
nicht kollabieren". No existing reusable implementation anywhere in the
project (S4's precedent, referenced in reports/gates_matrix_s1_s5.md, was
apparently verified ad-hoc). Generic version: wraps ANY Strategy, holding
every signal it emits for exactly one extra bar before letting the
backtester act on it (entry consequently happens 1 bar later than normal).
If the strategy's edge collapses under this artificial extra delay, that's
consistent with the original relying on unrealistically precise timing
(a repaint/lookahead smell) rather than a real, robust edge.

Run for S9p's fixed base params (the dominant winning combo across its
WFO folds: don_len=500, sl_atr_mult=4.0, adx_min=25.0) over the full
available data_mt5 history -- single fixed-param backtest, not WFA (the
shift-test is a robustness sanity check on the mechanism, not a
performance-optimization exercise).
"""
import sys
sys.path.insert(0, ".")
import pandas as pd
from scripts.run_backtest import build_backtest_config, load_common, load_config, load_data, resolve_window
from core.backtester import Backtester
from core.live import load_strategy_class


class DelayedSignalStrategy:
    """Delays every signal the inner strategy emits by exactly one extra
    bar before returning it (holds it one on_bar() call, re-emits next
    call with its `time` updated to the now-current bar)."""
    name = "shift1_wrapper"

    def __init__(self, inner):
        self.inner = inner
        self.required_timeframes = inner.required_timeframes
        self._held = None

    def on_bar(self, bars, i):
        ready = self._held
        self._held = None
        new_sig = self.inner.on_bar(bars, i)
        if new_sig is not None:
            self._held = new_sig
        if ready is not None:
            df = bars[self.required_timeframes[0]]
            ready.time = df.index[i]
            return ready
        return None

    def on_trade_closed(self, trade):
        return self.inner.on_trade_closed(trade)


cfg = load_config("configs/s9p_donchian_trend_h1_trimmed.yaml")
common = load_common("configs/common.yaml")
symbol = "XAUUSD"
start, end = resolve_window(cfg, symbol, "data_mt5")
data = load_data(cfg, symbol, "data_mt5", start, end)
bt_cfg = build_backtest_config(cfg, common, symbol, start, end)
strategy_cls = load_strategy_class(cfg["strategy"])
base_params = dict(cfg.get("params") or {})
# The dominant winning combo across S9p's 20 WFO folds (fold log):
base_params.update(don_len=500, sl_atr_mult=4.0, adx_min=25.0)

baseline = strategy_cls(dict(base_params))
res_base = Backtester(baseline, bt_cfg, data).run()

shifted = DelayedSignalStrategy(strategy_cls(dict(base_params)))
res_shift = Backtester(shifted, bt_cfg, data).run()

print(f"BASELINE   : n={len(res_base.trades)}  PF={res_base.metrics['pf']:.4f}")
print(f"SHIFTED+1  : n={len(res_shift.trades)}  PF={res_shift.metrics['pf']:.4f}")
print(f"PF ratio (shifted/baseline): {res_shift.metrics['pf'] / res_base.metrics['pf']:.4f}")
