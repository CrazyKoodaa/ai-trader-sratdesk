#!/usr/bin/env bash
# scripts/start_s4_live.sh — startet den S4-LondonBreakout-Live-Bot.
#
# Braucht Python >= 3.13 mit pymt5linux + rpyc==6.0.2 (nicht im Projekt-.venv,
# siehe AGENTS.md "Abhaengigkeits-Fallen"). Auf dieser Maschine bereits
# vorhanden in miniforge3 (dieselbe Umgebung, die David-V2-Ben nutzt).
#
# Voraussetzung: die pymt5linux-Bruecke laeuft unter Wine auf Port 8001:
#   WINEPREFIX=~/.mt5 wine "C:\Python313\python.exe" -m pymt5linux \
#     --host localhost --port 8001 "C:\Python313\python.exe"
#
# Default: DRY-RUN (Orders werden nur geloggt, siehe --no-dry-run unten).
# Sicherheitsschalter: schlaegt zusaetzlich fehl, wenn das Konto kein Demo-
# Konto ist (configs/s4_london_breakout.yaml: live.allow_real_account).
#
# Nutzung:
#   ./scripts/start_s4_live.sh                 # Dry-Run (sicher, Default)
#   ./scripts/start_s4_live.sh --no-dry-run    # ECHTE Orders (nach Demo-Test!)
#   ./scripts/start_s4_live.sh --once          # ein Loop-Durchlauf (Debug)
set -euo pipefail
cd "$(dirname "$0")/.."   # trading_bots/

PYTHON="${S4_PYTHON:-/home/crazyneo/miniforge3/bin/python3.13}"
if [ ! -x "$PYTHON" ]; then
  echo "FEHLER: $PYTHON nicht gefunden. Python >= 3.13 mit pymt5linux/rpyc==6.0.2 noetig." >&2
  exit 1
fi

export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
exec "$PYTHON" -m core.live --config configs/s4_london_breakout.yaml "$@"
