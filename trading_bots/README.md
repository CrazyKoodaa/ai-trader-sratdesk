# MT5 Trading-Bot-Framework

5 eigenständige, eigenvalidierte Trading-Bots für MetaTrader 5 (Demo, später
Prop-Firm) auf **Linux**. Die MT5-Anbindung läuft über **pymt5linux**
(RPyC-Bridge zu einem MT5-Terminal unter Wine). Verbindliche Spezifikation:
`SPEC.md` (Single Source of Truth).

## Architektur-Überblick

```
┌────────────────────────── Linux (nativ) ──────────────────────────┐
│  core/live.py  ──►  core/connector.py  ──►  rpyc-Client           │
│  (Live-Loop)        (MT5Connector)             │                   │
└────────────────────────────────────────────────┼───────────────────┘
                                                 │ TCP :18812 (Default;
┌────────────────────────── Wine-Präfix ─────────┼───────────────────┤
│  Windows-Python:  python -m pymt5linux  (RPyC-Server) ◄───────────┘
│  MetaTrader 5 Terminal (angemeldet, AlgoTrading an)
└──────────────────────────────────────────────────────────────────┘
```

> Auf dieser Maschine läuft der Server auf Port **8001**:
> `WINEPREFIX=/home/crazyneo/.mt5 wine "C:\Python313\python.exe" -m pymt5linux --host localhost --port 8001 "C:\Python313\python.exe"`
> (`--port 8001` an fetch_data.py/live.py übergeben bzw. `live.port` in der Config setzen.)

- **Backtest-Code hat KEINE MT5-Abhängigkeit** (SPEC §1) — Daten kommen aus
  CSV-Cache (`data/`) oder Dukascopy.
- Alle Zeitreihen intern **UTC, tz-aware** ("UTC-at-ingestion", SPEC §3).
- **Dry-Run ist Default**: Orders werden nur geloggt, solange nicht explizit
  `--no-dry-run` gesetzt wird.

## 1. Setup

### 1.1 Natives Linux-Python (Client)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # enthält rpyc==5.3.1 und numpy<2.0
```

> **Warum die Pins?** Der RPyC-Server (Wine) und der Client (Linux) müssen
> **beidseitig** `rpyc==5.3.1` haben — Versions-Mismatch führt zu
> Protokollfehlern beim Verbinden. numpy-Arrays (`copy_rates_range`) werden
> per Pickle übertragen; mit `numpy>=2.0` auf einer Seite schlägt das
> Deserialisieren fehl (`numpy._core`-Fehler) — daher **beidseitig**
> `numpy<2.0`.

### 1.2 MT5 unter Wine (Server)

```bash
# Wine installieren (Distro-Paket), dann:
export WINEPREFIX=$HOME/.wine-mt5
winecfg   # einmalig initialisieren

# MT5-Installer des Brokers im Präfix ausführen, Terminal starten, einloggen:
wine "$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"

# Windows-Python (z.B. 3.13, 64-bit) IM Wine-Präfix installieren:
wine python-3.13.x-amd64.exe

# Im Wine-Python die Server-Seite installieren (SELBE rpyc-Version wie Client!):
wine python -m pip install pymt5linux rpyc==6.0.2
```

> Hinweis: Das PyPI-Paket `mt5linux` (1.1.1) ist ein anderes, Docker-basiertes
> Projekt — **nicht** installieren. Client und Server heißen `pymt5linux`.

### 1.3 MT5-Terminal-Einstellungen (wichtig!)

1. **Extras → Optionen → Charts → "Max bars in chart" = Unlimited.**
   Sonst kappt MT5 die Historie (der Connector erkennt das und warnt mit
   `CAPPING VERDACHT` im Log — dann Setting ändern und neu fetchen).
2. **AlgoTrading aktivieren** (Toolbar-Button + in den EA-Optionen).
3. Gewünschte Symbole in der Marktübersicht sichtbar machen.

### 1.4 RPyC-Server starten

```bash
# im Wine-Präfix (Terminal muss laufen und eingeloggt sein):
WINEPREFIX=/home/crazyneo/.mt5 wine "C:\Python313\python.exe" -m pymt5linux \
  --host localhost --port 8001 "C:\Python313\python.exe"
# (startet einen rpyc_classic-Server auf dem angegebenen Port)
```

### 1.5 Verbindung testen

```bash
python - <<'EOF'
from core.connector import MT5Connector
c = MT5Connector()          # dry_run=True per Default
c.connect("localhost", 8001)
print("health:", c.health())
print("server_offset:", c.server_offset("XAUUSD"))
print("spec:", c.symbol_spec("XAUUSD"))
print(c.fetch_ohlcv("XAUUSD", "H1", "2024-01-02", "2024-01-05").tail())
c.disconnect()
EOF
```

## 2. Daten laden

### 2.1 Via MT5 (Brokerdaten — Referenz für finale Validierung)

```bash
python scripts/fetch_data.py --symbol XAUUSD --timeframe H4 \
    --start 2020-01-01 --end 2025-01-01 --source mt5 --out data/
```

Ausgabe: `data/{SYMBOL}_{TF}.csv` mit UTC-tz-aware-Index und exakt den
Spalten `open, high, low, close, tick_volume` (SPEC §3). Am Ende läuft ein
**Gap-Audit** (fehlende Bars außerhalb des Wochenendes werden gemeldet).

### 2.2 Via Dukascopy (kostenlose Fallback-Quelle, kein MT5 nötig)

```bash
python scripts/fetch_data.py --symbol EURUSD --timeframe M15 \
    --start 2023-01-01 --end 2024-01-01 --source dukascopy --out data/
```

Lädt Tick-Daten von `datafeed.dukascopy.com` (LZMA-.bi5, Stunden-Dateien),
aggregiert M1 → Ziel-Timeframe, cached Tage unter `data/dukascopy_cache/`
(resume-fähig, leere Wochenend-Tage werden als `.empty` gecacht).

> **ACHTUNG Instrumenten-Fit:** Dukascopy `USATECHIDXUSD` ≠ Broker-`NAS100`/
> `US100` (anderes Underlying-Niveau, andere Kontraktspezifikation).
> **Dukascopy nur für Forex/Gold-Entwicklungs-Backtests verwenden** — die
> finale Validierung (Stress, WFA, Gates) läuft immer auf MT5-Brokerdaten.

> **Dukascopy-Rate-Limit:** Der Server blockt ab ~5-10 req/s **pro IP** mit
> 429 — unabhängig von `--workers`. `fetch_data.py` hält seit 2026-09-04 ein
> **globales** Requests/s-Limit über alle Worker hinweg ein (`--rate-limit`,
> default 4.0 req/s); mehr `--workers` beschleunigt den Download NICHT über
> dieses Server-Limit hinaus, sondern erzeugt nur mehr 429/Backoff.

### 2.3 Via HistData.com (schnellere Alternative, fertige M1-Bars)

```bash
python scripts/fetch_data.py --symbol XAUUSD --timeframe H1 \
    --start 2020-01-01 --end 2025-01-01 --source histdata --out data/
```

Lädt fertige M1-Bars als **1 Zip je vollem Vergangenheitsjahr** (bzw. 1 Zip
je Monat im laufenden Jahr) von `histdata.com` — statt Dukascopys 24
Tick-Requests/Tag. Kein bekanntes hartes Rate-Limit, dadurch für
Mehrjahres-Backtests deutlich schneller (Praxiswert: XAUUSD H1, 2 Monate,
~5 s inkl. Resample). Cache unter `data/histdata_cache/` (Jahr/Monat-CSV,
resume-fähig). Braucht das optionale Paket `histdata` (in
`requirements.txt`).

> **ACHTUNG Tick-Volumen:** HistData-M1-Bars führen **kein echtes
> Tick-Volumen** (Spalte `tick_volume` immer `0`) — für **S2 VWAPPullback**
> (tick_volume-gewichtetes VWAP, SPEC §5) ist diese Quelle **nicht
> geeignet**; dort weiter Dukascopy oder MT5 verwenden. Für S1/S4/S5
> unkritisch.

> **ACHTUNG Instrumenten-Fit NAS100:** HistData führt keinen `NAS100`/
> `US100`, sondern einen eigenen Nasdaq-100-Proxy unter dem Pair-Code
> `nsxusd` (Symbol-Mapping automatisch, mit Warnung) — genau wie Dukascopys
> `USATECHIDXUSD` ein **anderer** Anbieter-Proxy als der Broker-Kontrakt.
> Nur für Entwicklungs-Backtests; finale Validierung bleibt MT5-Brokerdaten.

## 3. Backtest

```bash
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml
# Kosten-Stressmatrix (Gates SPEC §7.2: PF 1x>=1.5, 2x>=1.2, 3x>=1.0):
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --stress 0.5,1,2,3
# A/B-Layer-Vergleich (Meta-Layer einzeln togglen):
python scripts/run_backtest.py --config configs/s1_trend_pullback.yaml --layers
```

Reports landen in `reports/{strategie}_{symbol}/` (Markdown + Equity-PNG).
Das Kostenmodell (Spread + Slippage + Kommission + Swap) ist **immer aktiv**.

## 4. Walk-Forward + Gates

```bash
python scripts/run_wfa.py --config configs/s1_trend_pullback.yaml \
    --symbol XAUUSD --gates configs/validation_gates.yaml --out reports/wfa_s1
# Exit-Code 0 = alle Gates bestanden, 1 = mindestens ein FAIL
```

## 5. Live (Demo)

```bash
# RPyC-Server läuft (siehe 1.4), dann:
python -m core.live --config configs/s1_trend_pullback.yaml --dry-run
```

- `--dry-run` ist **Default** — Orders werden nur geloggt (jsonl unter `logs/`).
- Echte Orders erst nach explizitem `--no-dry-run` (vorher Demo-Validierung!).
- Der Loop pollt neue geschlossene Bars, wendet News-Filter (fail-closed bei
  fehlendem Feed) und Risiko-Engine an (Daily-Halt, EOD-Flat, Friday-Flat,
  max_concurrent) und setzt **immer serverseitigen SL/TP** (Crash-Netz).
- Health-Check alle 30–60 s mit automatischem Reconnect; SIGINT/SIGTERM =
  graceful shutdown.

## 6. Tests

```bash
python -m pytest tests/ -q
```

Connector-Tests laufen gegen ein Fake-RPyC-Objekt (kein echter MT5 nötig);
Dukascopy-Parser-Tests nutzen selbst erzeugte LZMA-Blobs (kein Download).

## 7. Troubleshooting

| Symptom | Ursache | Fix |
|---|---|---|
| `Connection refused` | RPyC-Server läuft nicht / falscher Port | `wine ... -m pymt5linux --port 8001 ...` starten; MT5-Terminal eingeloggt? Port per `--port` übergeben |
| `No module named 'pymt5linux'` | Client-Paket fehlt | `pip install pymt5linux rpyc==6.0.2` (braucht Python ≥ 3.13) |
| RPyC-Protokollfehler (`brine.load`, `ValueError: not enough values to unpack`) beim Connect | **Version-Mismatch** | rpyc muss **beidseitig** identisch sein: `pip show rpyc` nativ UND `wine python -m pip show rpyc` |
| Versehentlich Paket `mt5linux` installiert | Docker-basiertes Fremdpaket, startet Container | `pip uninstall mt5linux`, `pip install pymt5linux` |
| `CAPPING VERDACHT` im Log | "Max bars in chart" zu klein | MT5: Extras → Optionen → Charts → **Unlimited**, dann neu fetchen |
| Alte M5-Daten fehlen | Server liefert nur wenige Wochen M5 (MetaQuotes-Demo) | H1+ ist tief; für M5-Strategien (S2/S3) Dukascopy/Broker-Historie nutzen |
| Serverzeit/UTC stimmt nicht | Systemuhr (Wine-Host) falsch | Systemzeit per NTP syncen (`timedatectl`); Connector prüft Offset via Tick-Zeit (`server_offset()`) |
| SSL-/Zertifikatsfehler im Wine-Python | fehlende CA-Zertifikate im Präfix | `wine python -m pip install certifi`; Wine-Systemzeit prüfen (falsche Zeit = ungültige Zertifikate) |
| `is_blackout` immer True / keine Entries | News-Feed nicht erreichbar | Gewollt (**fail-closed**, SPEC §4.7): Feed/Cache `data/news/` prüfen |

## Repo-Layout

Siehe SPEC.md §2. Kernmodule unter `core/`, Strategien unter `strategies/`,
Configs unter `configs/`, CLIs unter `scripts/`, Tests unter `tests/`,
Daten-Cache unter `data/` (nicht im git).

## 9. Magic Numbers (Trade-Trennung pro Bot)

Jeder Bot sendet Orders mit einer eigenen Magic Number, damit Trades in der
MT5-Historie/Statistik eindeutig pro Strategie trennbar sind:

| Bot | Config | Magic |
|---|---|---|
| S1 TrendPullback (XAUUSD H4) | `configs/s1_trend_pullback.yaml` | 20260901 |
| S2 VWAPPullback (NAS100 M5) | `configs/s2_vwap_pullback.yaml` | 20260902 |
| S3 SilverBullet (NAS100/XAUUSD M5) | `configs/s3_silver_bullet.yaml` | 20260903 |
| S4 LondonBreakout (USDJPY H1) | `configs/s4_london_breakout.yaml` | 20260904 |
| S5 FilteredMR (XAUUSD/EURUSD H1) | `configs/s5_filtered_mr.yaml` | 20260905 |

Der Live-Loop liest `live.magic` aus der jeweiligen Config und verwaltet nur
Positionen mit der eigenen Magic (Positions-Filter). In MT5: Historie →
Rechtsklick → Gruppieren nach "Magic" bzw. Spalte "Expert" einblenden.






Done — S4 is now live-deployment-ready, with a working LAN dashboard

What I found first (this drove the whole design): trading_bots/ already had a validated, tested live-trading framework (core/live.py + connector.py + risk.py) built to spec, and S4 LondonBreakout is the only strategy of S1–S7 that passed validation (10/11 gates, PF 2.25/1.51/1.00 at 1x/2x/3x costs, 621 OOS trades). So instead of writing a new standalone bot, I wired S4 into that existing framework — safer and far less code than a parallel implementation.

What I built:
- strategies/s4_london_breakout.py: added explain() — a read-only diagnostic that mirrors the strategy's real gates, for "why didn't it trade" logging.
- core/connector.py: is_demo_account(), history_deals_range(), history_deals_for_position().
- core/live.py: an account-safety guard that refuses to start on a real-money account unless you explicitly set live.allow_real_account: true (mirrors David V2's ALLOW_REAL_ACCOUNT pattern, which this framework was missing); a daily-rotating human-readable log (logs/s4_london_breakout.log) — this is your "traderbook" backlog (signals, orders, closes, and why nothing happened), alongside the existing machine-readable JSONL; a periodic equity heartbeat; and a CSV trade journal (core/journal.py, new).
- dashboard.py (new, stdlib-only, no deps): / overview shows both bots — S4 (magic 20260904) and David V2/TrendPullback (magic 100042) — with David's stats pulled read-only from MT5 history filtered by magic number, never touching his files. /s4 subpage: equity curve, trade journal with per-trade "autopsy" (log lines around that trade), open positions, and the validation-gate summary parsed live from your gates-matrix report. No login (per your answer) — binds to 0.0.0.0:8802 when asked to.
- configs/s4_london_breakout.yaml: added the live: block pointing at port 8001, allow_real_account: false, magic 20260904 (already assigned).
- scripts/start_s4_live.sh / start_dashboard.sh: run under miniforge3's Python 3.13 (already has pymt5linux/rpyc==6.0.2 installed) — not this project's .venv (3.11, lacks those).

Verified live, not just unit-tested — your pymt5linux bridge was already running on :8001:
- Ran S4 in dry-run --once against the real bridge: connected, confirmed your account is genuinely the demo (MetaQuotes-Demo), logged a real heartbeat, and correctly logged KEIN EINSTIEG: USDJPY | Range 156.03-156.58 (55.0 Pips) | blockiert: inside_range.
- Ran the dashboard against the real bridge: correctly showed David V2's real numbers via magic-number filtering — 5 closed trades, 40% winrate, PF 1.34, net +508 EUR — which matches the account's actual equity growth almost exactly.

Tests: 387 passed (61 new tests across test_s4.py, test_journal.py, test_connector.py, test_live.py, test_dashboard.py). 6 pre-existing failures remain, all the same cause (pyarrow in requirements.txt but not installed in .venv) — unrelated to this work, not something I introduced; pip install pyarrow fixes it if you want.

To go live yourself:
cd trading_bots
./scripts/start_s4_live.sh              # dry-run (safe, default)
./scripts/start_dashboard.sh --host 0.0.0.0   # LAN dashboard on :8802
# only after checking the dry-run logs:
./scripts/start_s4_live.sh --no-dry-run
