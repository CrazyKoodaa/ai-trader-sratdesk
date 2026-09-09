# AGENTS.md — ai-trader (MT5 Trading-Bot-Framework)

> Kontextdatei für Coding-Agents. Beim Arbeiten in `trading_bots/` gilt
> zusätzlich die dortige, detailliertere `trading_bots/AGENTS.md` — diese
> Datei hier deckt das Gesamt-Repo ab.

## Projekt in einem Satz

5 eigenständige, eigenvalidierte Python-Trading-Bots (S1–S5) für
MetaTrader 5 auf **Linux**, Anbindung über **pymt5linux** (RPyC-Bridge zu
einem MT5-Terminal unter Wine). Ziel: **OOS Profit Factor ≥ 1.5**, RR ≥ 1:2,
prop-firm-tauglich (0,5 % Risiko/Trade, EOD-Drawdown-fokussiert).

## Repo-Karte (oberste Ebene)

```
plan.md            Projektplan mit Phasen 1–5 (Research → Demo-Live-Gate)
SPEC.md            Verbindliche Spezifikation (Single Source of Truth;
                   identische Kopie liegt als trading_bots/SPEC.md)
research/          Entscheidungsgrundlage: Wide-/Dim-Reports
                   (trading_strategies_wide01..06, dim01..dim13,
                   cross_verification, insight) — reine Markdown-Doku
trading_bots/      Der eigentliche Code (siehe unten)
```

`SPEC.md` ist bindend: Interface-Verträge (§4), Strategie-Regelwerke (§5),
Meta-Layer (§6), Validierungs-Gates (§7). Keine impliziten Abweichungen —
Konflikte zwischen Code und SPEC werden explizit aufgelöst (Code an SPEC
anpassen oder SPEC begründet ändern).

## Technologie-Stack & Konfigurationsdateien

- **Python ≥ 3.10** für den Backtest-Pfad, **≥ 3.13** für Live-/Fetch-Pfad
  (pymt5linux). Referenz-Env auf dieser Maschine: conda-Env **`ai-trader313`**
  (Python 3.13). Kein Build-System — reines Skript-/Modul-Repo.
- **`trading_bots/requirements.txt`** ist die einzige Dependency-Datei:
  pandas, numpy, scipy, scikit-learn, hmmlearn, xgboost, pyyaml, requests,
  matplotlib, **rpyc==6.0.2** (Version muss beidseitig identisch sein —
  Major-Versionen sind wire-inkompatibel), pymt5linux, pytest.
  Historie: ursprünglich rpyc==5.3.1 + numpy<2.0 geplant; am 2026-09-04 an
  den laufenden pymt5linux-Server (Python 3.13, rpyc 6) angepasst und
  empirisch verifiziert (numpy 2.x funktioniert über die Bridge).
- Laufzeit-Konfiguration liegt in **`trading_bots/configs/*.yaml`**: eine
  Datei pro Strategie (Parameter + WFO-Ranges + `live.magic`), dazu
  `common.yaml` (11 Symbole), `prop_*.yaml` (Prop-Firm-Limit-Profile) und
  `validation_gates.yaml` (harte Validierungs-Gates).
- **Kein git-Repo** im Projektverzeichnis (Stand 2026-09-04).

## Laufzeit-Architektur

- **Backtest-Pfad hat KEINE MT5-Abhängigkeit**: Daten kommen als CSV aus
  `trading_bots/data/` (UTC tz-aware, Spalten exakt
  `open, high, low, close, tick_volume`) oder via Dukascopy-Download
  (`scripts/fetch_data.py --source dukascopy`). Dukascopy nur für
  Forex/Gold — die finale Validierung läuft immer auf MT5-Brokerdaten.
- **Live-Pfad**: `core/live.py` → `core/connector.py` (`MT5Connector`) →
  rpyc-Client → TCP **:8001** (auf dieser Maschine; Default im Code 18812,
  per `--port` bzw. `live.port` konfigurierbar) → Windows-Python unter Wine
  → MT5-Terminal. Server-Start auf dieser Maschine:
  `WINEPREFIX=/home/crazyneo/.mt5 wine "C:\Python313\python.exe" -m pymt5linux --host localhost --port 8001 "C:\Python313\python.exe"`.
  rpyc-Version muss **beidseitig identisch** sein (Stand: 6.0.2).
  MT5-Option "Max bars in chart" muss auf Unlimited stehen.
- **Dry-Run ist Default** (`MT5Connector(..., dry_run=True)`); echte Orders
  nur mit explizitem `--no-dry-run`.
- Setup-Details und Troubleshooting-Tabelle: `trading_bots/README.md`.

## Code-Organisation (`trading_bots/`)

```
core/         strategie-unabhängiges Framework:
              time_engine (UTC/Sessions, zoneinfo, DST-fest), indicators,
              smc (kausale FVG/BOS/CHoCH/Sweeps), risk (Sizing, Prop-Limits,
              EOD-flat), backtester (Event-Loop + Kostenmodell),
              validation (WFA, DSR, PBO/CSCV, Monte-Carlo), news_filter,
              regime (HMM/ADX-Proxy), volume_profile, connector, live,
              reporting, fixtures (synthetische OHLCV für Tests)
strategies/   base.py (Signal-Dataclass + Strategy-ABC, SPEC §4.1)
              + s1_trend_pullback .. s5_filtered_mr
configs/      YAMLs (siehe oben)
scripts/      CLIs: fetch_data.py, run_backtest.py, run_wfa.py
tests/        pytest-Suite (~300 Tests, nutzt core/fixtures.py)
data/         CSV-Cache (aktuell nicht vorhanden; wird erzeugt)
```

Die 5 Bots: S1 TrendPullback (XAUUSD H4/D1), S2 VWAPPullback (NAS100 M5,
9:45–11:30 ET), S3 SilverBullet (SMC/FVG, M5), S4 LondonBreakout (USDJPY
H1), S5 FilteredMR (XAUUSD/EURUSD H1). Jeder Bot hat eine eigene Magic
Number (20260901–20260905) zur Trade-Trennung in MT5.

## Härteste Regeln (NICHT verletzen)

1. **UTC-at-ingestion**: alle Zeitreihen intern UTC, tz-aware. Sessions nur
   über `core/time_engine.py` mit `zoneinfo` (America/New_York,
   Europe/London) — niemals feste UTC-Offsets (DST-Asynchronwochen US/EU!).
2. **Kausalität / No-Repainting**: Signale nur aus abgeschlossenen Bars
   (close[1]-Prinzip); SMC-Events erst nach Bestätigungs-Lag sichtbar.
3. **Kanone vor Fallback**: `core/indicators.py`, `core/smc.py`,
   `core/time_engine.py` sind kanonisch; Strategien importieren daraus.
   Fallbacks in `strategies/base.py` müssen numerisch identisch bleiben
   (atol 1e-10). Kern-Logik-Änderungen gehören in `core/`.
4. **Kostenmodell immer aktiv** (Spread + Slippage + Kommission + Swap);
   Prop-Limits kommen aus `configs/prop_*.yaml`, nie hart kodieren.
5. **News-Filter fail-closed live**: bei nicht ladbarem Kalender wird nicht
   gehandelt.
6. **Determinismus**: gleiche Daten + gleiche Config = identisches Ergebnis.

## Befehle

```bash
# Setup
pip install -r trading_bots/requirements.txt

# Tests (aus trading_bots/ heraus)
cd trading_bots && python -m pytest tests/ -q

# Daten holen (nur auf der User-Maschine mit Netz/MT5; diese Sandbox hat
# keinen Internetzugang für Marktdaten)
python scripts/fetch_data.py --config configs/common.yaml --source mt5
python scripts/fetch_data.py --config configs/common.yaml --source dukascopy

# Backtest (Stress-Matrix / A/B-Layer-Toggles)
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --stress 0.5,1,2,3
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --layers

# Walk-Forward-Validierung (Exit 0 = alle Gates bestanden)
python scripts/run_wfa.py --config configs/s1_trend_pullback.yaml

# Live (Demo) — Dry-Run ist Default
python core/live.py --config configs/s1_trend_pullback.yaml
```

## Testing-Strategie

- `python -m pytest tests/ -q` vor und nach jeder Änderung; keine Commits
  mit roten Tests.
- Suite: ~300 Tests (Unit-Tests für indicators/smc/time_engine/risk plus
  Integrations-Tests jeder Strategie auf synthetischen Daten mit bekanntem
  Ergebnis aus `core/fixtures.py`). Connector-Tests laufen gegen ein
  Fake-RPyC-Objekt, Dukascopy-Parser-Tests gegen selbst erzeugte LZMA-Blobs
  — kein Netz nötig.
- Neue Strategie-Logik → neuer Test (kausale Korrektheit, deterministische
  Reproduzierbarkeit, DST-Übergänge wo relevant). Assertions nicht
  abschwächen, um Tests grün zu bekommen.
- **Aktueller Stand (2026-09-04): 300 passed, 0 failed.** Der früher rote
  Test `tests/test_backtester.py::TestIntrabarModes::test_m1_resolves_correct_order`
  war ein pandas-3-Bug im Backtester (asi8-Einheiten µs vs. ns), gefixt in
  `core/backtester.py` (unit-sicheres searchsorted auf DatetimeIndex).

## Validierungs-Gates (SPEC §7, `configs/validation_gates.yaml`)

Eine Strategie gilt nur als bestanden mit: PF ≥ 1.5 OOS (Walk-Forward
24 M IS / 6 M OOS rolling), PF bei 2× Kosten ≥ 1.2, DSR ≥ 0.95,
PBO/CSCV < 0.10, Monte-Carlo p95-DD ≤ 8 %, P(Daily-Breach) ≤ 5 %,
n ≥ 300 OOS-Trades. Erwartung: 2–3 der 5 Kandidaten fallen realistischerweise
durch — das ist ein valides Ergebnis, kein Bug. Ergebnisse nicht "schöntunen".

## Konventionen & Sprache

- Code-Identifier Englisch; **Docstrings/Kommentare und alle Doku
  (README, SPEC, research/) sind überwiegend Deutsch**. Neue Beiträge
  diesem Stil anpassen. (Hinweis: `trading_bots/AGENTS.md` nennt
  "Code/Kommentare Englisch" als Regel — der Bestand ist faktisch deutsch;
  im Zweifel dem umgebenden Code folgen.)
- Config-Schema nur rückwärtskompatibel erweitern (Defaults setzen);
  bestehende YAMLs müssen weiter laden.
- Keine Netzwerkannahmen in dieser Sandbox — reale Daten-Fetches, Backtests
  und Live-Läufe finden auf der User-Maschine statt (Phase 4/5 in
  `plan.md`).

## Sicherheit

- Kein echtes Geld ohne explizites Opt-in: Dry-Run ist Default, Live nur
  Demo, `--no-dry-run` erst nach Demo-Validierung.
- Keine Secrets im Repo (Broker-Logins etc.); `data/`-Cache nicht
  versionieren.
- News-Filter und Risk-Engine sind Sicherheitsnetze (fail-closed,
  Daily-Loss-Halt, EOD-/Friday-Flat, serverseitiger SL/TP als Crash-Netz)
  — diese Pfade nicht aufweichen.
