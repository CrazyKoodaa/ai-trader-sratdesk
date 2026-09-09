#!/usr/bin/env bash
# scripts/start_dashboard.sh — startet das LAN-Dashboard (Overview aller
# Bots per Magic-Number + S4-Detailseite). Reiner Lesezugriff auf MT5, siehe
# dashboard.py Modul-Docstring.
#
# Nutzung:
#   ./scripts/start_dashboard.sh                 # nur localhost:8802
#   ./scripts/start_dashboard.sh --host 0.0.0.0  # LAN-Zugriff, KEIN Login
#                                                 # (wie David-V2-Ben/dashboard.py)
set -euo pipefail
cd "$(dirname "$0")/.."   # trading_bots/

PYTHON="${S4_PYTHON:-/home/crazyneo/miniforge3/bin/python3.13}"
if [ ! -x "$PYTHON" ]; then
  echo "FEHLER: $PYTHON nicht gefunden. Python >= 3.13 mit pymt5linux/rpyc==6.0.2 noetig." >&2
  exit 1
fi

exec "$PYTHON" dashboard.py --port 8802 --mt5-port 8001 "$@"
