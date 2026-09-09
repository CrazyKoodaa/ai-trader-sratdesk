# AGENTS.md — MT5 Trading-Bot-Framework (Top-5-Strategien)

> Projektkontext für Coding-Agents (Kimi Code CLI o. ä.). Diese Datei wird
> beim Start im Projektverzeichnis automatisch gelesen.

## Projekt in einem Satz

5 eigenständige, eigenvalidierte Trading-Bots (S1–S5) für MetaTrader 5 auf
Linux, Anbindung via **pymt5linux** (RPyC-Bridge zu MT5 unter Wine), Ziel:
**Profit Factor ≥ 1.5 OOS**, prop-firm-tauglich (0,5 % Risiko/Trade, RR ≥ 1:2,
max. 10 % DD, EOD-flat).

## Verbindliche Spezifikation

**`SPEC.md` ist die Single Source of Truth.** Interface-Verträge (§4),
Strategie-Regelwerke (§5), Meta-Layer (§6) und Validierungs-Gates (§7) sind
bindend. Keine einseitigen Abweichungen: Wenn Implementierung und SPEC
konfligieren, wird entweder die Implementierung an die SPEC angepasst oder die
SPEC explizit und begründet geändert — nie implizit driftend.

Hintergrund/Entscheidungsgrundlage: `../research/` (Wide-/Dim-Reports,
`trading_strategies_cross_verification.md`, `trading_strategies_insight.md`,
`trading_strategies_dim13.md` für Volume-Profile) und `../plan.md`.

## Repo-Karte

```
core/         Framework (alles strategie-unabhängig)
  time_engine.py    UTC/Session-Handling (zoneinfo, DST-fest)
  indicators.py     EMA/ATR/RSI/ADX/VWAP ... (kanonische Implementierung)
  smc.py            kausale SMC-Primitive (FVG/BOS/CHoCH/Sweeps, non-repainting)
  risk.py           Positionsgröße 0,5 %, RR-Check, Daily-Loss-Halt, EOD-flat
  backtester.py     Event-Loop, CostModel, Slippage-Stress
  validation.py     Walk-Forward, DSR, PBO/CSCV, Monte-Carlo
  news_filter.py    ForexFactory-XML, Tier-1-Halt, fail-closed live
  regime.py         HMM-Regimefilter (2-State, hysteresis)
  volume_profile.py POC/VA70/HVN/LVN, entry_gate(), structural_stop()
  connector.py      MT5Connector (dry_run=True Default, Retry, Magic)
  live.py           Closed-Bar-Polling, Health-Check, jsonl-Logging,
                    Traderbook-Log (Klartext), Konto-Sicherheitscheck (Demo)
  journal.py        Trade-Journal (CSV, Traderbook-Stil, von live.py befüllt)
  reporting.py      Kennzahlen/Reports
strategies/   base.py (Signal, Strategy ABC) + s1..s5 Implementierungen
              (S4: zusätzlich explain() — Live-Diagnose "warum kein Signal?")
configs/      s1..s5 YAMLs (Parameter + WFO-Ranges + vp_filter + live.magic/
              live.port/live.allow_real_account), common.yaml (11 Symbole),
              prop_*.yaml (Prop-Limit-Profile), validation_gates.yaml
scripts/      fetch_data.py (MT5 + Dukascopy bi5/LZMA), run_backtest.py,
              run_wfa.py (Exit 0/1 nach Gates), start_s4_live.sh,
              start_dashboard.sh (miniforge-Python 3.13, siehe unten)
dashboard.py  LAN-Web-Dashboard (stdlib only): Overview aller Bots per
              Magic-Number (read-only MT5), Subpage /s4 mit Equity-Kurve,
              Trades-Journal, Autopsie, Validierungs-Kennzahlen
tests/        pytest, ~390 Tests — müssen GRÜN bleiben
data/         Bar-Cache als Parquet (CSV-Fallback; UTC tz-aware;
              open/high/low/close/tick_volume)
```

## Die 5 Bots und ihre Magic Numbers

| Bot | Strategie | Config | Magic |
|-----|-----------|--------|-------|
| S1 | Trend-Pullback (XAUUSD H4/D1; Variante V5 + V1 DI-Cross) | configs/s1_trend_pullback.yaml | 20260901 |
| S2 | VWAP-Pullback (NAS100, 9:45–11:30 ET) | configs/s2_vwap_pullback.yaml | 20260902 |
| S3 | Silver Bullet (SMC/FVG, ET-Fenster) | configs/s3_silver_bullet.yaml | 20260903 |
| S4 | London Breakout | configs/s4_london_breakout.yaml | 20260904 |
| S5 | Gefilterte Mean-Reversion | configs/s5_filtered_mr.yaml | 20260905 |

Jeder Bot läuft mit eigener Magic, damit Trades in der MT5-Statistik getrennt
auswertbar sind. Neue Bots bekommen fortlaufende Magics (nächste frei: 20260906).

Fremder Bot auf demselben Konto/derselben Bruecke: **David V2** (TrendPullback,
Desktop/tagebuch/David-V2-Ben), **Magic 100042** — eigenstaendiger Prozess,
nicht Teil dieses Repos. `dashboard.py` liest seine Kennzahlen NUR read-only
per Magic-Filter aus MT5-Historie/-Positionen, nie aus seinen Dateien.

## Live-Deployment (Stand 2026-09-05): S4 als erster live-faehiger Bot

S4 ist der einzige Bot, der alle Validierungs-Gates besteht (10/11,
`reports/gates_matrix_s1_s5.md`) und ist als erster fuer Demo-Live-Betrieb
verdrahtet:

```bash
./scripts/start_s4_live.sh                  # Dry-Run (Default, sicher)
./scripts/start_s4_live.sh --no-dry-run     # ECHTE Orders (Demo-Konto!)
./scripts/start_dashboard.sh --host 0.0.0.0 # LAN-Dashboard, kein Login
```

- **Sicherheitsschalter**: `core/live.py` verweigert den Start (SystemExit),
  wenn `mt5.account_info().trade_mode` ein Echtgeldkonto meldet UND
  `live.allow_real_account` (Config) nicht explizit `true` ist.
- **Traderbook-Log**: `logs/<strategy>.log` (Klartext, taeglich rotierend,
  30 Tage) — ergaenzt das strukturierte `logs/live_<strategy>_<datum>.jsonl`
  um menschenlesbare Nachvollziehbarkeit (Signal/Order/Close/"KEIN EINSTIEG"
  inkl. Begruendung via `Strategy.explain()`, rein lesend, kein Einfluss auf
  die Handelsentscheidung).
- **Trade-Journal**: `logs/trades_<strategy>.csv` (`core/journal.py`), eine
  Zeile pro OPEN/CLOSE mit Klartext-Grund — Basis der `/s4`-Dashboard-Seite.
- **Ausfuehrungsumgebung**: braucht Python ≥3.13 + pymt5linux/rpyc==6.0.2
  (nicht im Projekt-`.venv`) — auf dieser Maschine `miniforge3` (dieselbe Env
  wie David V2), siehe `scripts/start_s4_live.sh`.

## Härteste Regeln (NICHT verletzen)

1. **UTC-at-ingestion**: Alle Zeitreihen intern UTC, tz-aware
   (`pd.Timestamp`, tz="UTC"). Sessions nur über `core/time_engine.py`
   (zoneinfo: America/New_York, Europe/London). **DST-Wochen 2026**
   (08.–29.03. und 25.10.–01.11., US/EU asynchron) sind der kritischste
   Bug-Vektor — Session-Logik nie mit festen UTC-Offsets bauen.
2. **Kausalität / No-Repainting**: SMC-Primitive in `core/smc.py` sind kausal
   (FVG: `confirmed_at = formed + 1 Bar`; Swing-Bestätigung laggt). Signale
   dürfen ausschließlich abgeschlossene Bars verwenden (Live: Closed-Bar-
   Polling in `core/live.py`).
3. **Kanone vor Fallback**: `core/indicators.py`, `core/smc.py`,
   `core/time_engine.py` sind die kanonischen Implementierungen. Strategien
   importieren daraus. Lokale Fallback-Implementierungen in `strategies/`
   müssen numerisch identisch sein (verifiziert, atol 1e-10) — Änderungen an
   Kern-Logik gehören in `core/`, nie nur in eine Strategie.
4. **Dry-Run ist Default**: `MT5Connector(..., dry_run=True)`. Echte Orders
   nur mit explizitem `--no-dry-run`. Retry-Codes: 10015/10016/10030.
   Zusaetzlich: `core/live.py` verweigert den Start auf einem Echtgeldkonto,
   solange `live.allow_real_account` nicht explizit `true` ist
   (`_enforce_account_safety`, siehe Live-Deployment-Abschnitt).
5. **Backtest-Code hat KEINE MT5-Abhängigkeit** (SPEC §1). Daten kommen aus
   `data/` (CSV) oder Dukascopy (`scripts/fetch_data.py`).
6. **Risk-Layer ist zentral** (`core/risk.py`): 0,5 %/Trade, RR ≥ 1:2,
   Daily-Loss-Halt, EOD-flat, feste SL/TP. Prop-Limits kommen aus
   `configs/prop_*.yaml` — nie hart kodieren.
7. **News-Filter fail-closed live** (`core/news_filter.py`): Bei nicht
   ladbarstem Kalender wird nicht gehandelt (Tier-1: FOMC/NFP/CPI,
   −15/+10 min um Release, ET→UTC konvertiert).

## Validierungs-Gates (SPEC §7, configs/validation_gates.yaml)

Eine Strategie gilt nur als "bestanden", wenn **alle** Gates erfüllt sind:

- PF ≥ 1.5 OOS (Walk-Forward: 24 M IS / 6 M OOS rolling)
- PF bei 2× Kosten ≥ 1.2 (Slippage-Stress 0,5×/1×/2×/3×)
- Deflated Sharpe ≥ 0.95, PBO/CSCV < 0.10
- Monte-Carlo p95-DD ≤ 8 %, P(Daily-Breach) ≤ 5 %
- n ≥ 300 Trades (sonst: unzureichende Evidenz, kein "Pass")

Erwartung: realistischerweise fallen 2–3 der 5 Kandidaten durch den
PF-Gate — das ist ein valides Ergebnis, kein Bug. Ergebnisse nicht
"schöntunen" (kein Parameter-Nachjustieren, bis der OOS-Gate besteht).

## Befehle

```bash
# Setup (Linux-nativ)
pip install -r requirements.txt

# Tests (MÜSSEN vor jedem Commit grün sein)
python -m pytest tests/ -q

# Daten holen (auf der User-Maschine mit MT5/Wine; Sandbox hat kein Netz)
python scripts/fetch_data.py --config configs/common.yaml --source mt5
python scripts/fetch_data.py --config configs/common.yaml --source dukascopy

# Backtest (mit Kosten-Stress / Layer-Toggles)
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --stress
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --layers off:vp_filter

# Walk-Forward-Validierung (Exit-Code 0 = alle Gates bestanden)
python scripts/run_wfa.py --config configs/s1_trend_pullback.yaml

# Live (Demo) — Standard: Dry-Run
python core/live.py --config configs/s1_trend_pullback.yaml
python core/live.py --config configs/s1_trend_pullback.yaml --no-dry-run

# S4 live (braucht Python >=3.13 + pymt5linux, siehe Live-Deployment-Abschnitt)
./scripts/start_s4_live.sh
./scripts/start_dashboard.sh --host 0.0.0.0
```

## Abhängigkeits-Fallen (pymt5linux-Setup)

- **rpyc-Version muss beidseitig identisch sein** (Linux-Client UND
  Wine-Server) — Major-Versionen (5.x/6.x) sind wire-inkompatibel.
  **Stand 2026-09-04: beidseitig 6.0.2** (ursprünglich 5.3.1 geplant und in
  SPEC/README so dokumentiert; angepasst, weil der laufende
  pymt5linux-Server rpyc 6 nutzt — siehe SPEC §1).
- **numpy-Pin <2.0 entfallen**: gegen diesen Server mit numpy 2.x
  verifiziert (keine Pickle-Fehler bei `copy_rates_range`).
- **Python ≥ 3.13 für Live/Fetch** (pymt5linux Requires-Python >=3.13);
  Backtest-Pfad läuft auch auf 3.10–3.12. Referenz-Env: conda `ai-trader313`.
- Das PyPI-Paket **`mt5linux` (1.1.1) NICHT verwenden** — es ist ein
  Docker-basiertes Fremdpaket und startet Container. Client-Modul ist
  `pymt5linux` (`from pymt5linux import MetaTrader5`).
- MT5-Option "Max bars in chart" auf **Unlimited** stellen, sonst
  unvollständige Historie.
- Wine-Seite auf dieser Maschine (Server läuft auf TCP **:8001**):
  `WINEPREFIX=/home/crazyneo/.mt5 wine "C:\Python313\python.exe" -m pymt5linux --host localhost --port 8001 "C:\Python313\python.exe"`
- **Historientiefe MetaQuotes-Demo**: H1/H4/D1 reichen Jahre zurück, M5 nur
  wenige Wochen (Server liefert alte M5 nicht) — betrifft S2/S3 (M5),
  siehe Phase-4-Notizen. NAS100 heißt dort **USTEC**.

## Arbeitsregeln für den Agent

- Vor Code-Änderungen: `python -m pytest tests/ -q` als Baseline; nach
  Änderungen erneut — kein Merge/Commit mit roten Tests.
- Neue Strategie-Logik → neuer Test in `tests/` (kausale Korrektheit und
  deterministische Reproduzierbarkeit testen, Fixtures aus `core/fixtures.py`).
- Config-Schema erweitern? Nur rückwärtskompatibel (Defaults), bestehende
  YAMLs müssen weiter laden.
- Keine Netzwerkannahmen: Diese Sandbox hat keinen Internetzugang für
  Marktdaten — reale Backtests laufen auf der User-Maschine.
- Keine stillen Semantik-Änderungen an Test-Erwartungen: Assertions nicht
  abschwächen, um Tests grün zu bekommen.
- Sprache: Code/Kommentare Englisch, Doku und User-Kommunikation Deutsch.

## Offene Phasen (Roadmap)

- **Phase 4** (auf User-Maschine): `fetch_data.py` → `run_backtest.py
  --stress` → `run_wfa.py` für S1–S5, Gate PF ≥ 1.5 OOS.
- **Phase 5**: Demo-Live-Phase (mehrere Wochen, alle 5 Bots parallel mit
  eigenen Magics), Abgleich Live-vs-Backtest, dann finaler Report.
- **Backlog**: Bot 6 (Gold-POC-Retest, Go/No-Go-Kriterien in
  `../research/trading_strategies_dim13.md`); XGBoost-Meta-Labeling (erst ab
  ≥300 Primärsignalen); COT-Bias-Filter A/B für Forex.
