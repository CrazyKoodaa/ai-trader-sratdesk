#!/bin/bash
# Batch-Fetch MT5 (H1/H4/D1, tiefe Historie) — ai-trader313 Env, Port 8001
cd /home/crazyneo/projects/dev/ai-trader/trading_bots
PY=/home/crazyneo/miniforge3/envs/ai-trader313/bin/python
for job in "XAUUSD H4" "XAUUSD D1" "XAUUSD H1" "USDJPY H1" "USDJPY H4" "USDJPY D1" "EURUSD H1"; do
  set -- $job
  echo "=== $1 $2 ==="
  $PY scripts/fetch_data.py --symbol "$1" --timeframe "$2" --start 2019-01-01 --end 2026-09-05 --source mt5 --port 8001 --out data 2>&1 | tail -6
done
echo "BATCH FERTIG"
