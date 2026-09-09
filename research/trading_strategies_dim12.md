# Dimension 12: MT5-unter-Wine-Execution, Datenqualität & Python-API-Detail

**Research-Datum:** 2026-09-03 | **Suchen:** 17 gezielte Queries (EN/DE) + 2 direkte PyPI-Registry-Verifikationen (curl) | **Scope:** MetaTrader5-Python-API, pymt5trade-Disambiguierung, mt5linux/RPyC, PyTrader, aiomql, Historien-Tiefe, Symbol-Specs, Serverzeit/DST, Wine-Stabilität

---

## 0. WICHTIGSTER BEFUND VORAB: "pymt5trade" existiert nicht als öffentliches Paket

**Claim:** Es gibt kein Paket namens `pymt5trade` auf PyPI oder GitHub. Direkte Verifikation: `https://pypi.org/pypi/pymt5trade/json` liefert **HTTP 404**; Volltext-Grep über den kompletten PyPI-Index (`pypi.org/simple/`) findet nur `pymt5`, `pymt5adapter`, `pymt5linux`, `pymt5pure`, `mt5pytrader`, `MT5pytrader` — kein `pymt5trade`. GitHub/Google-Suche nach `"pymt5trade"` (3 Varianten: exakt, `py-mt5-trade`, `mt5trade`): **0 relevante Treffer**.
**Source:** Eigene Verifikation (PyPI-API + Index-Grep), 2026-09-03 | **Confidence: SEHR HOCH**

Wahrscheinliche Erklärungen für das, was beim User "funktioniert":
1. **Verwechslung/Umbenennung des offiziellen `MetaTrader5`-Pakets** (das läuft im Wine-Windows-Python), oder
2. **`mt5pytrader` / `MT5pytrader`** (PyPI, "MT5-based module for seamless trade execution", Funktionen `connect()`, `open_buy()`, `open_sell()`, `close_buy()` — passt exakt zu "Trade-Öffnung und Account-Status funktioniert"), oder
3. **`pymt5linux`** (Fork von `mt5linux`, "up-to-date version which incorporates recent MT5 software updates. It works with Python 3.13"), oder
4. ein interner/privater Wrapper-Name.
**Handlungsbedarf an Lead/User:** Paketname im laufenden Setup verifizieren (`pip show <name>`, `pip list | grep -i mt5`). Die technischen Aussagen unten gelten für alle Varianten, da fast alle Wrapper auf dem offiziellen MetaQuotes-Paket aufsetzen.

---

## 1. Python-MT5-Anbindungen im Vergleich

### 1.1 Offizielles MetaTrader5-Paket (MetaQuotes)

**Claim:** Das offizielle Paket ist **Windows-only**: Es existiert kein Source-Distribution und kein Nicht-Windows-Wheel; `pip install MetaTrader5` ist auf macOS/Linux by design ein No-Op. Die Kommunikation läuft über IPC (Named Pipes) zu einem lokal laufenden `terminal64.exe`.
**Source:** QUOTEZ MCP Server-Doku (glama.ai) | **URL:** https://glama.ai/mcp/servers/PNX89/QUOTEZ | **Date:** 2026-06-12 | **Excerpt:** *"`MetaTrader5` is Windows only and publishes no source distribution, so `pip install quotez[mt5]` is a no-op on macOS and Linux by design."* + Meta-Trader-MCP-Troubleshooting: *"the binding does not exist for macOS/Linux."* | **Confidence: HOCH** [^1^][^2^]

**Claim:** Funktionsumfang (32 Funktionen): `initialize/login/shutdown`, `account_info`, `terminal_info`, `version`, `symbols_get/symbol_info/symbol_info_tick/symbol_select`, `copy_rates_from/copy_rates_from_pos/copy_rates_range`, `copy_ticks_from/copy_ticks_range`, `orders_get/positions_get`, `order_check/order_send/order_calc_margin/order_calc_profit`, `history_orders_get/history_deals_get`, **Wirtschaftskalender: `calendar_value_history`, `calendar_value_last`, `calendar_event_history`** etc. Kein Push/Eventing — Polling-Pflicht. Pro Python-Prozess nur **eine** Terminal-Verbindung (Workaround: Paket-Ordner duplizieren oder mehrere portable Terminals).
**Source:** lobehub Skills-Marketplace (MT5-Trading-Skill) + StackOverflow #63975284 | **URL:** https://lobehub.com/zh-TW/skills/acaprino-alfio-claude-plugins-mt5-trading ; https://stackoverflow.com/questions/63975284 | **Date:** 2026-04-10 / 2021-05-18 | **Excerpt:** *"api-architecture.md — MT5 Python API architecture, 32 functions, named pipes IPC"* ; SO: *"they coded that module in such way that don't allow you to run multiple instances of that module, you can connect to one terminal only"* | **Confidence: HOCH** [^3^][^4^]

**Claim (Versionierungs-Fallen):** (a) **numpy ≥ 2.0 bricht das Paket** — `import MetaTrader5` wirft ABI-Fehler, da gegen numpy 1.x kompiliert; Fix: `numpy<2.0` (z. B. 1.26.4). (b) Wheels existieren historisch nur bis **Python 3.11**; aktuellere Windows-Pythons brauchen Prüfung, ob neue Wheels nachgezogen wurden (Stand der Quelle: Warnung im Code "MetaTrader5 wheels exist only for Python ≤ 3.11").
**Source:** StackOverflow #78896744 + ForexFactory-Thread-Code | **URL:** https://stackoverflow.com/questions/78896744/error-when-using-import-metatrader5-in-python ; https://www.forexfactory.com/thread/1346721-xauusd-and-machine-learning-trading | **Date:** 2024-08-21 / 2026-09-03 | **Confidence: HOCH (numpy), MITTEL (Python-Version, versionsabhängig)** [^5^][^6^]

### 1.2 mt5linux / pymt5linux (RPyC-Bridge) — DER Standard-Weg unter Linux/Wine

**Claim:** Architektur = **Dual-Python-Bridge**: (1) Windows-Python unter Wine mit offiziellem `MetaTrader5`-Paket, (2) natives Linux-Python mit `mt5linux`-Client. Der RPyC-Server läuft im Linux-Python und ruft `wine python.exe` als Subprozess auf. Client-API ist drop-in-kompatibel (`mt5.initialize()`, `mt5.copy_rates_from_pos(...)` etc.).
**Source:** lucas-campagna/mt5linux (Issue #18), deepwiki gmag11/MetaTrader5-Docker-Image, PyPI mt5linux 1.0.3 | **URL:** https://github.com/lucas-campagna/mt5linux/issues/18 ; https://deepwiki.com/gmag11/MetaTrader5-Docker-Image/4.2-python-integration-via-rpyc ; https://pypi.org/project/mt5linux/1.0.3/ | **Date:** 2023-12-08 / 2025-11-03 / 2026-02-20 | **Excerpt:** *"The Metatrader5 library cannot be used in Python for Linux. It can only be used by Python for Windows. … mt5linux can act as the bridge between these two Python installations."* | **Confidence: SEHR HOCH** [^7^][^8^][^9^]

**Claim (kritische Falle):** **RPyC 5.x und 6.x sind nicht wire-kompatibel.** Wenn der Linux-Client RPyC 6.x hat und der Wine-Server RPyC 5.x (implizit als Dependency installiert), schlägt jeder Call mit `ValueError: invalid message type: 18` fehl — sieht aus wie Netzwerk-/Protokoll-Korruption. Fix: `rpyc==5.3.1` (o. ä.) **in beiden Umgebungen pinnen**.
**Source:** gmag11/MetaTrader5-Docker Issue #26 | **URL:** https://github.com/gmag11/MetaTrader5-Docker/issues/26 | **Date:** 2026-02-08 | **Confidence: SEHR HOCH** [^10^]

**Claim (RPyC-Timeouts):** RPyC-Default `sync_request_timeout: 30` Sekunden — große `copy_rates_range`-/`copy_ticks_range`-Downloads über die Bridge können in Timeouts laufen; Konfiguration: `rpyc.connect(..., config={"sync_request_timeout": 240})`. RPyC hat **keinen eingebauten Reconnect-Mechanismus** — Verbindungsverlust = neue Verbindung manuell aufbauen.
**Source:** RPyC Docs + RPyC Issues #320, #233, #169 | **URL:** https://rpyc.readthedocs.io/en/latest/api/core_protocol.html ; https://github.com/tomerfiliba-org/rpyc/issues/233 | **Confidence: HOCH** [^11^][^12^]

### 1.3 PyTrader (TheSnowGuru — WebSocket-EA)

**Claim:** PyTrader = Python-Client + MQL5-EA, Kommunikation per **WebSocket/Sockets** (EA = Server, Python = Client), EA und Python können auf verschiedenen Maschinen laufen. Demo-Modus voll funktionsfähig, aber auf 5 Instrumente begrenzt (EURUSD, AUDCHF, NZDCHF, GBPNZD, USDCAD); Vollversion kostenpflichtig (MQL5 Market). Linux offiziell via Docker+Wine unterstützt. Vorteile: echtes Streaming/Keep-Alive, keine Windows-Python-Doppelstruktur; Nachteile: Closed-Source-EA (Lizenz-Indikator), Instrumentenlimit in Demo, EA muss im Terminal laufen.
**Source:** GitHub TheSnowGuru/PyTrader + Forks (Branly76, MchLrnX) | **URL:** https://github.com/TheSnowGuru/PyTrader-python-mt4-mt5-trading-api-connector-drag-n-drop | **Date:** 2020–2025 (zuletzt aktive Forks 2025-06-14) | **Confidence: HOCH** [^13^]

### 1.4 aiomql (async Wrapper + Bot-Framework)

**Claim:** aiomql wrappt jede MT5-API-Funktion mit `asyncio.to_thread` + **automatischem Reconnect bei transienten Fehlern**; bringt Bot-Orchestrator (Multi-Strategie/Multi-Symbol via Thread-Pools), Session-Management (London/NY/Tokyo-Zeitfenster als `Session`-Objekte), RAM-Risikomanager, eigene Backtest-Engine, CSV/SQLite-Trade-Recording, pandas-ta-Integration. **Requirements: Python ≥ 3.13 UND Windows** (weil es auf dem offiziellen Paket sitzt) — unter Linux also nur im Wine-Windows-Python nutzbar, nicht nativ.
**Source:** GitHub Ichinga-Samuel/aiomql + PyPI + plainenglish.io-Guide | **URL:** https://github.com/Ichinga-Samuel/aiomql ; https://python.plainenglish.io/the-complete-guide-to-building-algorithmic-trading-bots-with-python-metatrader-5-a97056ea6c75 | **Date:** 2026-03-29 (Guide) | **Excerpt:** *"Requirements: Python ≥ 3.13, Windows (MetaTrader 5 terminal requirement)"* | **Confidence: HOCH** [^14^][^15^]

### 1.5 Weitere relevante Pakete (PyPI-verifiziert 2026-09-03)

| Paket | Was es ist | Wine-Relevanz |
|---|---|---|
| `pymt5` (devcartel) | Python-API für MT5-**Gateways** (Broker-Server-Seite, kein Terminal-Client) | Irrelevant für Retail-Bots |
| `pymt5adapter` | Drop-in-Wrapper um offizielles Paket (Type-Hints, Docstrings) | Erbt Windows-only |
| `pymt5linux` | Aktiver Fork von mt5linux, Python-3.13-kompatibel, verweist auf Docker-Alternative `mt5docker` | **Empfohlene Bridge-Variante** |
| `pymt5pure` | MT5-**WebAPI**-Implementation (Manager-API, braucht Broker-Zugang) | Nicht für Demo-Retail |
| `nautilus_mt5` (nodalytics/quantspub) | Nautilus-Trader-Adapter, 3 Modi: IPC (Windows), **RPyC für Linux/Wine**, Socket-EA für Streaming | Sauberste Architektur-Referenz |

**Source:** PyPI-JSON-APIs (eigene Abfrage) + GitHub nodalytics/nautilus_mt5 | **URL:** https://github.com/nodalytics/nautilus_mt5 | **Date:** 2025-03-11 | **Confidence: HOCH** [^16^]

### 1.6 Vergleichs-Fazit Bindings

| Kriterium | Offiziell (Wine-WinPy) | mt5linux/pymt5linux | PyTrader | aiomql |
|---|---|---|---|---|
| Unter Wine lauffähig | Ja (im Wine-Python) | Ja (Bridge, nativ nutzbar) | Ja (nur EA unter Wine) | Ja (nur im Wine-Python) |
| Vollständiger Funktionsumfang | Ja (alle 32 Fkt.) | Ja (weitergereicht) | Teilweise (kein Kalender) | Ja |
| Economic Calendar | Ja | Ja | Nein | Ja |
| Streaming/Push | Nein (Polling) | Nein (Polling) | Ja (Socket) | Polling + async |
| Auto-Reconnect | Nein | Nein (RPyC ohne Reconnect) | Keep-Alive-Fkt. | Ja (eingebaut) |
| Multi-Terminal | Nein (1 Modul = 1 Terminal) | Eingeschränkt | Mehrere EAs möglich | Multi-Account via Bots |
| Kosten | Frei | Frei (OSS) | Demo limitiert / Full paid | Frei (OSS, MIT) |

---

## 2. Historische Datenqualität & Limitierungen

### 2.1 copy_rates_range / copy_rates_from_pos

**Claim (stilles Cap):** `copy_rates_from_pos` und `copy_rates_range` werden **still vom Terminal-Setting "Max. bars in chart" begrenzt** (Default oft 100.000 Bars). Eine Anfrage kann innerhalb des Broker-Limits trotzdem gekürzt zurückkommen, **ohne dass die API das meldet**. Fix: Tools → Optionen → Charts → "Max. bars in chart" auf "Unlimited"/hoch setzen + Terminal-Restart.
**Source:** QUOTEZ-Doku + fxnx.com XAUUSD-History-Guide | **URL:** https://glama.ai/mcp/servers/PNX89/QUOTEZ ; https://fxnx.com/en/blog/missing-xauusd-history-mt5-load-full-bars-real-ticks | **Date:** 2026-06-12 / 2026-08-15 | **Excerpt:** *"copy_rates_from_pos and copy_rates_range are silently capped by the terminal's 'Max. bars in chart' setting, so a request inside the server's own cap can still come back short and nothing in the MetaTrader API says so."* | **Confidence: SEHR HOCH** [^1^][^17^]

**Claim (M1-Ladeverhalten):** MT5 lädt historische M1-Daten vom Broker-Server erst bei expliziter Anforderung nach (Chart-Scroll, Backtest oder API-Call). Ein erster `copy_rates_range`-Call auf alte Daten kann `None`/leer liefern, während das Terminal im Hintergrund lädt → Retry-Loop mit Sleep einbauen. Höhere Timeframes (H1/H4/D1) werden serverseitig aus M1 aggregiert; D1/H4-Bars sind **an die Broker-Server-Zeitzone ausgerichtet** (typisch UTC+2/+3), nicht an UTC-Mitternacht — gleiche Anfrage liefert bei unterschiedlichen Brokern andere D1-OHLC.
**Source:** fxnx.com + QUOTEZ | **URL:** s. o. | **Excerpt:** *"A MetaTrader terminal aligns D1 and H4 to the broker's server day, which is commonly UTC+2 or UTC+3, so the same get_bars(symbol, 'D1') returns a candle with a different open time and different OHLC depending on which source is configured."* | **Confidence: SEHR HOCH** [^17^][^1^]

**Claim (Lücken-Erkennung, Referenz-Code):**
```python
df = pd.DataFrame(mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, utc_from, utc_to))
df['time'] = pd.to_datetime(df['time'], unit='s')
df['gap'] = df['time'].diff()
severe_gaps = df[df['gap'] > pd.Timedelta(minutes=5)]  # Wochenenden separat ausfiltern!
```
**Source:** fxnx.com (Auditing-Skript) | **URL:** https://fxnx.com/en/blog/missing-xauusd-history-mt5-load-full-bars-real-ticks | **Confidence: HOCH** [^17^]

### 2.2 Tick-Daten

**Claim:** Der MT5-Tick-Viewer/Export ist auf **131.072 Ticks gecappt** — bei Gold (>150.000 Ticks/Tag) unzureichend. Workaround: `CopyTicksRange()`/`copy_ticks_range` **tageweise** (86400-s-Fenster) chunken; mehrere Millionen Ticks so exportierbar. Ticks sind nur verfügbar, wenn das Terminal sie vorher vom Server geladen hat.
**Source:** GitHub koua29/mt5-export-ticks | **URL:** https://github.com/koua29/mt5-export-ticks | **Date:** 2026-06-18 | **Confidence: SEHR HOCH** [^18^]

**Claim (Broker-abhängige Tick-Tiefe, konkrete Messpunkte):** IC Markets: Ticks nur ~**64 Wochen** zurück. Darwinex via MT5: Einzelticks bis **2011-12-19** (!). Darwinex-FTP-Service: offiziell ab **Oktober 2017** für Live-Kunden. **Warnung Darwinex:** Forenbeleg, dass aus Darwinex-Ticks generierte M5-Bars **Lookahead-Spikes** enthielten (stündliche Spitzen auf Preisniveaus, die erst später erreicht wurden — ein EA "entdeckte" darauf faktenbasiert falsche Edges); die Roh-Ticks selbst waren sauber → Bar-Generierung, nicht Tick-Quelle, war korrupt.
**Source:** ForexFactory #1302650 + StrategyQuant-Forum + Tickstory-Support | **URL:** https://www.forexfactory.com/thread/1302650-darwinex-historical-data-invalid ; https://strategyquant.com/forum/topic/darwinex-historical-data/ | **Date:** 2026-06-11 / 2021-11-15 | **Confidence: HOCH (als dokumentierter Einzelbefund)** [^19^][^20^]

**Claim (Backtest-Modi MT5):** "Every tick based on real ticks" = einziger Modus mit faktischer Intrabar-Wahrheit (SL/TP-Touch-Reihenfolge); "Every tick" = synthetisch aus M1 interpoliert mit **aktuellem** (konstantem) Spread; "1 Minute OHLC" = 4 Punkte/Bar. Modelling Quality < ~90 % = Backtest ist Rekonstruktion, kein Protokoll.
**Source:** tradingbotmaker.com + ispybuy.com | **URL:** https://www.tradingbotmaker.com/view-post/blog/mt5-every-tick-real-ticks-backtest-accuracy-guide ; https://ispybuy.com/blog/mt5-strategy-tester-every-tick-vs-real-ticks-vs-ohlc/ | **Date:** 2026-08-30 / 2026-07-28 | **Confidence: HOCH** [^21^][^22^]

### 2.3 Alternative Datenquellen (für längere Historie / Cross-Validierung)

| Quelle | Tiefe | Format | Kosten | Qualitäts-Hinweise |
|---|---|---|---|---|
| **Dukascopy** (JForex/datafeed) | Majors ab ~2003–2007; Tick + Bars; 1600+ Instrumente | CSV/.jdf/binär | **Frei** | Community-Konsens: beste freie Tick-Qualität; Gain-Capital-Daten explizit als schlecht bewertet |
| **HistData.com** | 10+ Jahre, 66 Paare, Tick + M1 | MT4/MT5-nativ/CSV | Frei / $27 FTP | Liefert pro Datei **Gap-Report** (max. Gap in ms, alle Gaps >1 min) — Lücken-Transparenz eingebaut |
| **Darwinex** | FTP ab Okt 2017; MT5-Ticks bis 2011 | Tick (Bid/Ask getrennt) | Frei (Live-Konto) | Siehe Lookahead-Warnung oben — nur Roh-Ticks nutzen, Bars selbst bauen |
| **TrueFX** | ab 2009, 16 Paare | Tick | Frei (Registrierung) | Einzelne fehlende Tage, wenige Bad Ticks |
| **ForexSB / bluecapital** (Dukascopy-basiert) | bis 200.000 Bars vorkompiliert | MT4/MT5/CSV | Frei | Zeitzonen-Konvertierung eingebaut |
| **dukascopy-node / theorycraft-dukascopy** | 1990/2000er bis heute | JSON/CSV | Frei (OSS-CLI) | Aktiv gepflegte Download-Tools |
| **tvdatafeed** (TradingView) | ~5.000 Bars frei, 10k+ paid | Python-API | Frei/Paid | Nur als Cross-Check, nicht als Primärquelle |

**Source:** newyorkcityservers.com Top-12-Übersicht + ForexFactory #68015 + histdata.com + GitHub dukascopy-node | **URL:** https://newyorkcityservers.com/blog/top-12-sources-to-download-forex-historical-data-free-paid ; https://www.histdata.com/ ; https://www.dukascopy-node.app/ | **Date:** 2025-12-28 / 2026-08-31 | **Confidence: HOCH** [^23^][^24^][^25^]

---

## 3. Symbol-Spezifikationen via API (kritisch für 0,5 %-Risiko-Sizing)

**Claim:** `mt5.symbol_info(symbol)` liefert u. a.: `point`, `digits`, `spread` (in Points!), `trade_tick_size`, `trade_tick_value` (Wert **eines** Tick-Sprungs pro Lot in Kontowährung), `trade_contract_size`, `volume_min`, `volume_max`, `volume_step`, `trade_stops_level` (Mindestabstand SL/TP in **Points**, 0 = kein Limit!), `trade_freeze_level`, `filling_mode`, `swap_long/swap_short`, `trade_mode`. `symbol_select(symbol, True)` vorher nötig, wenn Symbol nicht im Market Watch sichtbar.
**Source:** tradingteaching.com (DataFeed-Referenzcode) + PythonMetaTrader5-PyPI + MQL5-Docs | **URL:** http://www.tradingteaching.com/blog/automation/complete-automated-trading-system.html ; https://pypi.org/project/PythonMetaTrader5/ | **Date:** 2026-01-15 / 2025-09-15 | **Confidence: SEHR HOCH** [^26^][^27^]

**Claim (warum das für Risiko-Berechnung kritisch ist):** Positionsgröße für 0,5 % Risiko:
```
risk_money   = equity * 0.005
sl_distance  = |entry - sl|                      # in Preis-Einheiten
ticks_at_risk = sl_distance / info.trade_tick_size
value_per_lot = ticks_at_risk * info.trade_tick_value
lots = risk_money / value_per_lot
lots = clamp(floor(lots / info.volume_step) * info.volume_step,
             info.volume_min, info.volume_max)
```
`trade_tick_value` unterscheidet sich je nach Symbol (XAUUSD: typisch $1 pro 0,01-Bewegung pro Lot, d. h. tick_size 0,01/tick_value 1,0 — aber brokerabhängig!), JPY-Paaren und CFDs massiv. **Niemals tick_value hartcodieren.** Zusätzlich Validierung via `mt5.order_calc_profit(ORDER_TYPE_BUY/SELL, symbol, lots, entry, sl)` — berücksichtigt Konversion in Kontowährung (Beleg aus MetaQuotes-Beispiel: 300 Points USDJPY ≙ $276,54 vs. EURUSD $300 bei 1 Lot — Kontowährungs-Konversion eingerechnet). Margin-Check via `mt5.order_calc_margin`, Pre-Trade-Validierung via `mt5.order_check()` (Prop-Firm-Pflicht, bevor `order_send`).
**Source:** fxbook.net/MetaQuotes order_calc_profit-Doku + dabanjia-Referenzimplementierung (Lot-Rounding) | **URL:** https://www.fxbook.net/zh-cn/docs/mql5参考/metatrader-python模块/order_calc_profit/ | **Confidence: SEHR HOCH** [^28^][^6^]

**Claim (häufigste order_send-Fehler):** Retcode **10016 (Invalid Stops)**: SL/TP näher als `trade_stops_level × point` am Preis → Abstand prüfen/auf `stops_level*point + 1 Punkt` Puffer aufblasen. Retcode **10030 (Unsupported filling mode)**: Filling-Mode (FOK/IOC/RETURN) ist symbol-/broker-spezifisch → aus `symbol_info.filling_mode` **dynamisch** ermitteln, nicht hardcoden. Retcode **10015 (Invalid price)** bei Pending Orders: Preis auf falscher Seite des Marktes (BuyStop ≤ Ask etc.).
**Source:** PythonMetaTrader5-PyPI + fx-sensei.com (Production-Code mit 10013/10015/10030-Behandlung) + lobehub MT5-Skill | **URL:** https://pypi.org/project/PythonMetaTrader5/ ; https://fx-sensei.com/python-mt5-bot-code/ | **Date:** 2026-02-04 | **Excerpt:** *"If you get Wrong SL (10016), check symbol_info(symbol).stops_level and multiply by point to know the minimal allowed distance."* ; *"Fill mode rejections (10030) — dynamic filling_mode detection per symbol"* | **Confidence: SEHR HOCH** [^27^][^29^][^3^]

---

## 4. Zeit-Problematik: Serverzeit, UTC, DST (entscheidend für ORB/Silver Bullet/Killzones)

### 4.1 Was die API tatsächlich liefert

**Claim:** Offizielle MetaQuotes-Doku: *"When creating the 'datetime' object, Python uses the local time zone, while MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift). Therefore, 'datetime' should be created in UTC time for executing functions that use time. Data received from the MetaTrader 5 terminal has UTC time."* → **Alle `datetime`-Argumente für `copy_rates_range`/`copy_ticks_*` MÜSSEN tz-aware-UTC sein** (`datetime(..., tzinfo=timezone.utc)`); naive lokale Datetimes erzeugen stille Verschiebungen. Rückgabe-Timestamps sind Unix-Epochs (UTC), ABER: die **Bar-Ausrichtung** (welche Stunde eine D1/H4-Kerze öffnet) folgt der Server-Zeitzone.
**Source:** MQL5-Docs zitiert in StackOverflow #79595025 + QUOTEZ | **URL:** https://stackoverflow.com/questions/79595025/ | **Date:** 2025-04-27 | **Confidence: SEHR HOCH** [^30^][^1^]

**Claim (dokumentierter Praxis-Fail):** Ein User (Budapest, UTC+2) wollte Broker-Daten (Zypern, UTC+3) und musste empirisch **+3 h** auf `to_datetime` addieren, um die aktuelle Kerze zu bekommen — Beweis, dass naive `datetime.now()`-Übergaben (lokale Zeit, vom System als UTC interpretiert) systematisch falsche Fenster liefern. Zweiter dokumentierter Fail (barmenteros, DRL-Deployment): Session-Flags (London/NY-Open) liefen **6 Stunden falsch**, weil `datetime.now()` ohne tz mit UTC-Bar-Timestamps verglichen wurde — *"The agent's session-conditional policies activated in the wrong sessions throughout every live trading day"* — **kein Fehler im Log, Strategie schlechter als Zufall**.
**Source:** StackOverflow #79595025 + barmenteros.com | **URL:** https://barmenteros.com/drl-trading-agent-deployment/ | **Date:** 2026-05-06 | **Confidence: SEHR HOCH** [^30^][^31^]

### 4.2 Server-Offset programmatisch ermitteln

**Claim (Rezept):** Es gibt **keine** direkte API-Funktion "gib mir den Server-GMT-Offset" im Python-Paket (kein `TimeGMTOffset()`-Äquivalent). Robuster Weg:
```python
tick = mt5.symbol_info_tick("EURUSD")   # tick.time = letzter Server-Tick als Epoch
server_offset_sec = tick.time - int(datetime.now(timezone.utc).timestamp())
# → typisch +7200 (EET/Winter) oder +10800 (EEST/Sommer)
```
Korrektur: Tick kann am Wochenende/illiquide alt sein → Offset auf volle Stunden runden (`round(offset/3600)`) und Alter des Ticks prüfen (`time_msc`). In MQL5 (falls EA-Hilfsmittel): `TimeCurrent() - TimeGMT()`. **Wichtig:** MQL5-`TimeGMT()` hängt von der OS-Uhr ab — unter Wine muss die **Linux-Systemzeit korrekt sein** (Zertifikats-Fehler "Invalid server certificate or invalid local time" bei falscher Container-Zeit ist dokumentiert).
**Source:** hw.online MT5-Timezone-Guide + vpsforextrader.com (TimeGMT-Caveats) + WineHQ-Forum (Zertifikats-/Zeit-Fehler) | **URL:** https://hw.online/faq/adjusting-the-time-zone-settings-in-metatrader-5-a-step-by-step-guide/ ; https://www.vpsforextrader.com/blog/what-is-ict-in-trading-a-comprehensive-guide/ ; https://forum.winehq.org/viewtopic.php?t=39590 | **Date:** 2026-03-02 / 2026-07-20 / 2024-10-24 | **Confidence: HOCH** [^32^][^33^][^34^]

### 4.3 DST — der stille Session-Killer

**Claim:** US-DST (2. Sonntag März → 1. Sonntag November) und EU/UK-DST (letzter Sonntag März → letzter Sonntag Oktober) sind **3 Wochen im Frühjahr und 1 Woche im Herbst asynchron** (2026: 8.–29. März und 25. Okt–1. Nov). Ein EA mit fixem NY↔London-Offset von 5 h liegt in diesen Wochen **1 Stunde daneben** — kein Fehler, kein Warning, Trades laufen schlicht im falschen Fenster. ForexFactory dokumentiert exakt das ("Right now the times are 1 hour off still as NY changed clocks before Europe"). **MetaTrader benachrichtigt EAs nicht programmatisch über DST-Wechsel**; Broker kommunizieren nur über den Mailbox-Tab (für Bots unlesbar). Die meisten FX-Broker-Server laufen EET/EEST (UTC+2/+3) und folgen dabei i. d. R. dem **US-DST-Kalender** (damit die NY-17:00-Kerze der Tageswechsel ist) — brokerindividuell verifizieren!
**Source:** vpsforextrader.com (DST-Deep-Dive) | **URL:** https://www.vpsforextrader.com/blog/what-is-ict-in-trading-a-comprehensive-guide/ | **Date:** 2026-07-20 | **Confidence: SEHR HOCH** [^33^]

**Claim (Implementierungs-Regel):** Session-Fenster (ORB, Killzones, Silver Bullet: 03:00–04:00 / 10:00–11:00 / 14:00–15:00 NY) **niemals in Serverzeit hardcoden**. Korrekte Kette: `zoneinfo.ZoneInfo("America/New_York")` (DST-sicher) → Ziel-Zeit in NY local → konvertieren nach UTC → konvertieren nach Serverzeit via gemessenem Offset (oder direkt alles in UTC rechnen und Serverzeit nur für die Bar-Filterung mappen). `zoneinfo` ist ab Python 3.9 Stdlib und behandelt US-DST automatisch korrekt; der **variable Teil** ist allein der Broker-Offset — deshalb täglich neu messen (s. 4.2) und bei Änderung alarmieren.
**Source:** Synthese aus [^31^][^33^] + Python-Stdlib | **Confidence: HOCH** 

---

## 5. Wine-spezifische Stabilität & bekannte Issues

**Claim (Versions-Matrix):** **Wine 9 wird von aktuellen MT5-Versionen nicht unterstützt** (gmag11: "Wine 9 is not supported by MT5"; Alpine 3.21 mit Wine 9.7 = bekanntes Problem; Image 2.2 geht auf Wine 10). ABER: **Wine 10.3 hat Regression Bug #57950** — MT5 bricht mit "a debugger has been found on your system" ab (Arch Linux, März 2025; verwandter MT4-Bug #58011, bisected auf Wine-Commit dc718fd...). Praxis: funktionierende Wine-Version **pinnen**, nicht blind upgraden.
**Source:** gmag11/MetaTrader5-Docker Releases + WineHQ Bug 57950/58011 (Mailinglisten-Mirror) | **URL:** https://github.com/gmag11/MetaTrader5-Docker-Image/releases ; https://list.winehq.org/archives/list/wine-bugs@list.winehq.org/message/BYEK6SJZB2AKCCYWZDRVSESCWPDQWQ7U/ | **Date:** 2025-12-20 / 2025-03-11 | **Confidence: HOCH** [^35^][^36^]

**Claim (LiveUpdate-Risiko):** MT5-**LiveUpdate kann eine laufende Wine-Installation unbrauchbar machen** (dokumentierter Fall: nach Update von terminal64.exe/metaeditor64.exe/metatester64.exe startete MT5 nicht mehr; Fix = gesicherte alte Binaries zurückkopieren). → **Wine-Präfix + funktionierende EXEn sichern; vor jedem Update-Fenster Snapshot.**
**Source:** LinuxMint-Forum (gelöster Fall) | **URL:** https://forums.linuxmint.com/viewtopic.php?t=385924 | **Date:** 2022-11/12 | **Confidence: HOCH (älterer, aber strukturell gültiger Befund)** [^37^]

**Claim (Zertifikate/Auth):** Wine importiert System-Root-Zertifikate u. U. fehlerhaft (`CRYPT_ImportSystemRootCertsToReg ... 00000057`) → Broker-Login schlägt fehl mit *"authorization failed (Invalid server certificate or invalid local time)"*. Mitursache kann auch falsche Container-Systemzeit sein. Vorsicht: `winetricks secur32` verschlimmerte im dokumentierten Fall alles.
**Source:** WineHQ-Forum t=39590 | **URL:** https://forum.winehq.org/viewtopic.php?t=39590 | **Date:** 2024-10-24 | **Confidence: HOCH** [^34^]

**Claim (Produktions-Einschätzung):** Mehrere VPS-/Tooling-Anbieter und Community-Konsens: MT5 unter Wine ist *"technically possible but unreliable in production"* (Font-Rendering-Fails, DLL-Kompatibilität, Proxy-Fehler; Referenz auf Bug #57950). Für Live-Prop-Trading mit echtem Geld wird Windows-Server-VPS empfohlen. Einordnung: Für **Demo/Forward-Test-Bots mit Watchdog** ist Wine+Docker (gmag11-Image, KasmVNC) der etablierte pragmatische Weg.
**Source:** vpsforextrader.com + forexvps.net | **URL:** https://www.vpsforextrader.com/blog/what-is-tradingview-and-how-to-use-it/ ; https://www.forexvps.net/resources/best-mt5-vps-providers/ | **Date:** 2026-07-20 / 2026-08-10 | **Confidence: MITTEL-HOCH (kommerzielle Quellen, aber konsistent mit Bug-Evidenz)** [^38^][^39^]

**Claim (Härtungs-Muster für langlebige Bots):** (1) Health-Check alle 30–60 s (`terminal_info()` + `account_info()` ≠ None), (2) `psutil`-Watchdog auf `terminal64.exe` + Restart via Subprozess, (3) exponentielles Backoff bei Reconnect, (4) jede API-Antwort auf `None` prüfen + `mt5.last_error()` loggen (stille Fehler sind die Norm), (5) Wochenend-Handling (kein endloser Reconnect-Spam Sa/So), (6) serverseitiger SL/TP an jeder Position als Katastrophen-Netz (Bot-Crash ≠ offenes Risiko).
**Source:** lobehub MT5-Trading-Skill (production-resilience.md) | **URL:** https://lobehub.com/zh-TW/skills/acaprino-alfio-claude-plugins-mt5-trading | **Date:** 2026-04-10 | **Confidence: HOCH** [^3^]

---

## IMPLEMENTIERUNGS-SPEZIFIKATION

Konkrete, aus den Befunden abgeleitete Bauanleitung für die 5 Python-Bots (MT5 unter Wine, Ziel PF > 1,5, Prop-tauglich, 0,5 % Risiko/Trade):

### A. Anbindung (Empfehlung)
1. **Paket-Identität klären:** `pip list | grep -i -E "mt5|trade"` im Wine-Python UND Linux-Python. "pymt5trade" gibt es nicht — vermutlich `MetaTrader5` (offiziell) oder `mt5pytrader`. Alle Aussagen gelten trotzdem, da Wrapper auf dem offiziellen Paket sitzen.
2. **Zielarchitektur:** Wine-Windows-Python (≤3.11, `numpy<2.0`, `MetaTrader5` gepinnt) als Execution-Layer + `pymt5linux`/mt5linux-RPyC-Bridge, damit Strategie-Code im nativen Linux-Python läuft. **`rpyc==5.3.1` auf BEIDEN Seiten pinnen** (Bug: `invalid message type: 18`).
3. Alternative mit weniger Moving Parts: Bots komplett **im** Wine-Python laufen lassen (kein RPyC), Linux nur als Scheduler/Watchdog — einfacher, aber ML-Libs dann unter Wine.
4. Falls echtes Tick-Streaming nötig wird: PyTrader-Socket-EA-Pattern (Referenz), aber Demo-Instrumentenlimit beachten; aiomql wegen Python-≥3.13-vs-numpy<2.0-Konflikt mit dem offiziellen Paket **vor Adoption verifizieren**.

### B. Execution-Layer-Regeln
- `initialize(path=..., login=..., password=..., server=..., timeout=60000)` mit Retry-Loop (3×/2 s); danach `account_info()`-Smoke-Test.
- **Vor jedem `order_send`: `order_check()`**; SL/TP-Distanz ≥ `trade_stops_level × point` (+1 Tick Puffer); Volumen = `floor(lots/volume_step)*volume_step`, geclamped auf [volume_min, volume_max]; Preise auf `digits` runden; `filling_mode` dynamisch aus `symbol_info` (Retcode 10030); `deviation` explizit setzen (z. B. 20 Points); Magic je Bot eindeutig.
- Retcode-Mapping: 10004 (Requote)/10015/10016/10019/10021/10030 loggen + kategorisiert behandeln; `TRADE_RETCODE_DONE` ist der einzige Erfolg.
- Serverseitiger SL/TP bei JEDER Position (Wine-Crash-Resilienz).
- Health-Loop 30–60 s: `terminal_info().connected` + `account_info()`; bei Ausfall: Backoff-Reconnect (5/15/60 s), nach N Fehlversuchen Terminal via Watchdog neu starten. RPyC: `sync_request_timeout` auf ≥240 s setzen (große History-Pulls), keine Reconnect-Erwartung an RPyC (manuell neu verbinden).

### C. Risiko-Sizing (0,5 %/Trade) — verbindliche Formel
```
risk = equity * 0.005
lots = risk / (|entry-sl| / tick_size * tick_value)   # je Symbol live aus symbol_info!
lots = clamp(floor(lots / volume_step) * volume_step, volume_min, volume_max)
assert order_calc_profit(BUY, sym, lots, entry, sl) ≈ -risk   # Kontowährungs-Konversion!
assert order_calc_margin(...) < freie Margin × Sicherheitsfaktor
```
`tick_value` niemals hardcoden (XAUUSD/JPY-Crosses/Indizes divergieren stark). Spread-Guard: bei `spread > max_spread_points` kein Entry (Session-Open-Spreads!).

### D. Daten-Pipeline (Backtest-Futter)
1. Terminal-Setting **"Max bars in chart" = Unlimited** + Restart, sonst stilles Cap (100k Bars ≙ nur ~10 Wochen M1!).
2. Historie chunkweise ziehen (z. B. 90-Tage-Fenster), bei `None`/leer: Sleep + Retry (Server lädt nach).
3. **Gap-Audit Pflicht** pro Symbol/TF: `df.time.diff() > TF-Dauer` (Wochenenden/Feiertage whitelisten); Gap-Report ins Datenpaket legen.
4. Für >2 Jahre M1 oder saubere Ticks: **Dukascopy** (primär, frei, ab ~2003/2007, dukascopy-node-CLI), HistData.com (mit eingebautem Gap-Report), ggf. Darwinex-Roh-Ticks (ab 2011, aber **Bars selbst aus Ticks bauen** — dokumentierter Lookahead-Bug in deren Bars). Broker-Daten (IC Markets ~64 Wo. Ticks) nur für die jüngste Validierung.
5. Backtest-Realismus: Session-Strategien mit Slippage-Stressmatrix (0/1/2/3/5 Pts) testen — DAX-14-Jahres-Studie zeigt PF 1,25 → 0,96 bei 3 Pts Slippage (aus wide01, hier relevant weil Execution-Layer!). M1-Interpolation unterschätzt Spread-Verhalten; wo möglich Real-Ticks.

### E. Zeit-Architektur (Killzone-/ORB-sicher)
1. **Single Source of Truth: UTC.** Alle internen Zeitstempel tz-aware UTC (`datetime.now(timezone.utc)`; `utcnow()` ist deprecated).
2. **Broker-Offset täglich messen** (Boot + alle 6 h): `offset_h = round((symbol_info_tick(SYM).time - utc_now_epoch)/3600)`; Tick-Alter prüfen; bei Änderung (DST!) Warn-Log + Session-Tabellen neu rechnen. Erwartung: +2/+3 (EET/EEST, meist US-DST-Kalender) — brokerindividuell verifizieren.
3. Session-Fenster in **Herkunftszeitzone** definieren (NY-Fenster via `ZoneInfo("America/New_York")`, London via `Europe/London`) → nach UTC konvertieren → gegen Bar-Timestamps (UTC-Epochs) vergleichen. **Niemals** Server-Stunden hardcoden. DST-Asynchron-Wochen 2026: 8.–29. Mär, 25. Okt–1. Nov → Regressionstest mit Daten aus genau diesen Wochen.
4. D1/H4-Bars sind serverzeit-ausgerichtet (NY-17:00-Konvention bei EET/EEST) — bei Aggregation aus M1/Ticks dieselbe Konvention nutzen, sonst OHLC-Mismatch zum Live-Chart.

### F. Wine-Betrieb (Runbook)
- Wine-Version **pinnen** (Wine 9 = unsupported; 10.3 = Debugger-Bug #57950; gmag11-Image 2.2/Wine 10 als Referenzbasis, vor Upgrade Testlauf).
- Funktionierende `terminal64.exe`-Installation + Wine-Präfix als Snapshot sichern (LiveUpdate-Risiko).
- Systemzeit im Container korrekt halten (Zertifikats-Login-Fehler!); NTP sicherstellen.
- Docker: gmag11/MetaTrader5-Docker (KasmVNC-Zugang für manuelle Erst-Anmeldung) oder hpdeandrade/mt5docker.
- Eskalationspfad für Prop-Live: Windows-Server-VPS (2 vCPU/4 GB) — Community-Konsens, dass Wine-Prod-Risiko die ~$10 Ersparnis nicht rechtfertigt. Demo-Phase auf Wine ist legitim.

### G. Offene Risiken / Verifikations-TODOs
1. Paket-Identität "pymt5trade" beim User klären (s. Abschnitt 0).
2. Broker (welcher?) → konkrete Tick-/M1-Historientiefe + Server-DST-Kalender empirisch messen, nicht annehmen.
3. numpy/Python-Version im Wine-Python verifizieren (`MetaTrader5` braucht numpy<2.0; Wheels-Historie ≤3.11 — ggf. neuere Wheels prüfen).
4. aiomql (Python ≥3.13) vs. MetaTrader5-Wheel-Verfügbarkeit — vor Framework-Entscheidung testen.

---
*Methodik-Hinweis: 17 Suchqueries (EN/DE) + direkte PyPI-Registry-Verifikation (404-Beweis für pymt5trade, Index-Grep) via curl. Härteste Quellen: GitHub-Issues (gmag11, lucas-campagna, RPyC, koua29), PyPI-API, MQL5/MetaQuotes-Doku-Zitate, StackOverflow; kommerzielle VPS-Quellen nur für Konsens-Aussagen genutzt.*

### Quellen
[^1^] https://glama.ai/mcp/servers/PNX89/QUOTEZ (2026-06-12)
[^2^] https://glama.ai/mcp/servers/shubhvisputek/meta-trader-mcp (2025-08-23)
[^3^] https://lobehub.com/zh-TW/skills/acaprino-alfio-claude-plugins-mt5-trading (2026-04-10)
[^4^] https://stackoverflow.com/questions/63975284 (2021-05-18)
[^5^] https://stackoverflow.com/questions/78896744/error-when-using-import-metatrader5-in-python (2024-08-21)
[^6^] https://www.forexfactory.com/thread/1346721-xauusd-and-machine-learning-trading (2026-09-03)
[^7^] https://github.com/lucas-campagna/mt5linux/issues/18 (2023-12-08)
[^8^] https://deepwiki.com/gmag11/MetaTrader5-Docker-Image/4.2-python-integration-via-rpyc (2025-11-03)
[^9^] https://pypi.org/project/mt5linux/1.0.3/ (2026-02-20)
[^10^] https://github.com/gmag11/MetaTrader5-Docker/issues/26 (2026-02-08)
[^11^] https://rpyc.readthedocs.io/en/latest/api/core_protocol.html (o.D.)
[^12^] https://github.com/tomerfiliba-org/rpyc/issues/233 (2017-12-06)
[^13^] https://github.com/TheSnowGuru/PyTrader-python-mt4-mt5-trading-api-connector-drag-n-drop (2020–2025)
[^14^] https://github.com/Ichinga-Samuel/aiomql (2022–2026)
[^15^] https://python.plainenglish.io/the-complete-guide-to-building-algorithmic-trading-bots-with-python-metatrader-5-a97056ea6c75 (2026-03-29)
[^16^] https://github.com/nodalytics/nautilus_mt5 (2025-03-11)
[^17^] https://fxnx.com/en/blog/missing-xauusd-history-mt5-load-full-bars-real-ticks (2026-08-15)
[^18^] https://github.com/koua29/mt5-export-ticks (2026-06-18)
[^19^] https://www.forexfactory.com/thread/1302650-darwinex-historical-data-invalid (2026-06-11)
[^20^] https://strategyquant.com/forum/topic/darwinex-historical-data/ (2021-11-15)
[^21^] https://www.tradingbotmaker.com/view-post/blog/mt5-every-tick-real-ticks-backtest-accuracy-guide (2026-08-30)
[^22^] https://ispybuy.com/blog/mt5-strategy-tester-every-tick-vs-real-ticks-vs-ohlc/ (2026-07-28)
[^23^] https://newyorkcityservers.com/blog/top-12-sources-to-download-forex-historical-data-free-paid (2025-12-28)
[^24^] https://www.histdata.com/ (2026-08-31)
[^25^] https://www.dukascopy-node.app/ (o.D.)
[^26^] http://www.tradingteaching.com/blog/automation/complete-automated-trading-system.html (2026-01-15)
[^27^] https://pypi.org/project/PythonMetaTrader5/ (2025-09-15)
[^28^] https://www.fxbook.net/zh-cn/docs/mql5参考/metatrader-python模块/order_calc_profit/ (MetaQuotes-Doku-Mirror)
[^29^] https://fx-sensei.com/python-mt5-bot-code/ (2026-02-04)
[^30^] https://stackoverflow.com/questions/79595025/timezones-and-offsets-handling-when-fetching-metatrader5-data-via-mt5-api (2025-04-27)
[^31^] https://barmenteros.com/drl-trading-agent-deployment/ (2026-05-06)
[^32^] https://hw.online/faq/adjusting-the-time-zone-settings-in-metatrader-5-a-step-by-step-guide/ (2026-03-02)
[^33^] https://www.vpsforextrader.com/blog/what-is-ict-in-trading-a-comprehensive-guide/ (2026-07-20)
[^34^] https://forum.winehq.org/viewtopic.php?t=39590 (2024-10-24)
[^35^] https://github.com/gmag11/MetaTrader5-Docker-Image/releases (2025-12-20)
[^36^] https://list.winehq.org/archives/list/wine-bugs@list.winehq.org/message/BYEK6SJZB2AKCCYWZDRVSESCWPDQWQ7U/ (2025-03-11)
[^37^] https://forums.linuxmint.com/viewtopic.php?t=385924 (2022-11/12)
[^38^] https://www.vpsforextrader.com/blog/what-is-tradingview-and-how-to-use-it/ (2026-07-20)
[^39^] https://www.forexvps.net/resources/best-mt5-vps-providers/ (2026-08-10)
