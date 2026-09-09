#!/bin/bash
# Stress-Matrizen S5 + S1 (parallel, post point_value-Fix)
cd /home/crazyneo/projects/dev/ai-trader/trading_bots
PY=/home/crazyneo/miniforge3/envs/ai-trader313/bin/python
for s in s5_filtered_mr s1_trend_pullback; do
  echo "########## $s ##########"
  $PY scripts/run_backtest.py --config "configs/$s.yaml" --stress 0.5,1,2,3 --workers 8 2>&1 | grep -E "^===|^\||Gate"
done
echo "STRESS-BATCH2 FERTIG"
