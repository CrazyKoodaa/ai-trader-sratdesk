#!/bin/bash
# Stress-Matrizen S4/S5/S1 mit korrigiertem point_value (post-fix)
cd /home/crazyneo/projects/dev/ai-trader/trading_bots
PY=/home/crazyneo/miniforge3/envs/ai-trader313/bin/python
$PY -m pytest tests/ -q 2>&1 | tail -1
for s in s4_london_breakout s5_filtered_mr s1_trend_pullback; do
  echo "########## $s ##########"
  $PY scripts/run_backtest.py --config "configs/$s.yaml" --stress 0.5,1,2,3 2>&1 | grep -E "^===|^\||Gate"
done
echo "STRESS-BATCH FERTIG"
