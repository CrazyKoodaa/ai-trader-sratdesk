# Dimension 07: News-Avoidance als Meta-Filter — Technische Implementierungsspezifikation

**Scope:** Pflicht-Modul "NewsFilter" für 5 Python-Bots auf MT5 (pymt5trade unter Wine). Ziel: kein Trading um High-Impact-News; prop-firm-konform (FTMO ±2 min, FundingPips ±5/±10 min u. a.). Kontext aus wide04: News-nahe Trades −0.10R vs. +0.35R ruhig (FxBacktest); Eval-vs-Funded-"Two-Phase News Illusion".

**Recherche-Basis:** 32 gezielte Websuchen (EN/DE), Quellenstand 2024–2026 (Schwerpunkt 2025/26), darunter FTMO-Primär-FAQ (EN+DE), FundingPips-Help-Center (Primär), MQL5-Referenz, GitHub-Implementierungen.

---

## 1. Datenquellen-Vergleich: Wirtschaftskalender (nur kostenlos, ohne API-Key bevorzugt)

### Claim 1.1 — MT5-eigener Wirtschaftskalender: MQL5-seitig voll, Python-seitig NICHT verfügbar
- **Source:** MQL5-Referenz (Economic Calendar functions) + VPSForexTrader + ForexFactory-Thread
- **URL:** https://www.mql5.com/en/docs/calendar (Funktionsliste via docs.mql4.com/mql5_language/mql5_functions/mql5_calendar gespiegelt) ; https://www.vpsforextrader.com/blog/ai-trading-co-pilot/ ; https://www.forexfactory.com/thread/1400596-mt5-calendar-data-bug
- **Date:** MQL5-Docs o.D. (laufend gepflegt); FF-Thread 2026-05/09
- **Excerpt:** MQL5 bietet `CalendarValueHistory`, `CalendarValueLast`, `CalendarEventById`, `CalendarEventByCurrency` u. a. ("Get the array of values for all events in a specified time range with the ability to sort by country and/or currency"). Diese Funktionen existieren **nur in MQL5 im Terminal** — das offizielle `MetaTrader5`-Python-Modul (und damit pymt5trade) exportiert **keine** Calendar-Funktionen (Funktionsliste des Python-Moduls: initialize/login/account_info/copy_rates_*/copy_ticks_*/order_send/history_* — kein calendar_*). Bekannte MQL5-seitige Fallstricke: `ERR_CALENDAR_TIMEOUT (5401)` bei Zeiträumen >30 Tage; leere Ergebnisse direkt nach Terminalstart (Sync abwarten); **Strategy Tester hat keinen Kalender** ("You must switch to a CSV fallback method for backtesting"); Demo-Server drosseln Kalender-Daten stärker als Live-Server.
- **Konsequenz für Wine-Setup:** Da der Kalender ohnehin nicht via Python abrufbar ist, stellt sich die Wine-Frage für den Direktzugriff nicht. Wine-relevant ist nur: Der MT5-Terminal unter Wine liefert den Kalender MQL5-intern (Kalender ist Server-/MetaQuotes-Feature, kein Windows-API-Feature); ein MQL5-Hilfs-EA kann unter Wine laufen und in `MQL5/Files` oder `Common/Files` CSV schreiben, die Python unter Wine liest (gemeinsames Wine-Filesystem). Direkter Beleg "Kalender kaputt unter Wine" wurde nicht gefunden; Beleg "Kalender funktioniert im Terminal, aber nicht im Python-Modul" ist hoch.
- **Confidence:** Hoch (Python-Modul-Funktionsliste), Mittel (Wine-Kalender im Terminal — plausibel, nicht direkt belegt)

### Claim 1.2 — ForexFactory Weekly XML/JSON: De-facto-Standard, kostenlos, ohne Key
- **Source:** AlgoSpecial (FAQ), mehrere FF-Threads, ehsanrs2/forexfactory-scraper, diverse EA-Dokus (XAUBOT, EAHub)
- **URL:** https://www.algospecial.com/blogs/news-trading-integration-mt5-ea ; https://www.forexfactory.com/thread/973 ff-cal-indicator (Seite 46) ; https://github.com/ehsanrs2/forexfactory-scraper ; https://xaubot.com/docs/setup/how-to-activate-the-news-filter/
- **Date:** 2025–2026
- **Excerpt:** Endpoints: `https://nfs.faireconomy.media/ff_calendar_thisweek.xml` (auch `.json`, `.csv`, `.ics`; Alias: `cdn-nfs.faireconomy.media`). "Free, no-authentication XML feed mirroring the Forex Factory economic calendar." Eigenschaften: **nur aktuelle Woche**, **keine Actual-Werte** ("lacks both the 'actual' and 'revised from' values"), **IP-Rate-Limit** ("They limited it to one load. Cannot be used on multiple pairs and metatraders on same VPS (IP)"). Empfohlene Abrufintervalle: alle 6 h (AlgoSpecial, "The calendar updates once daily"); min. 15 min (WONNFX). Timezone-Warnung aus FF-Thread: "Compare news time from FF web site, your real time and your broker time in MT4 before using!" — XML-Zeiten müssen normalisiert (auf UTC) und gegen Broker-Serverzeit verifiziert werden; AlgoSpecial: "Always convert everything to GMT … Never use local time or broker server time."
- **Rechtliches:** Der Feed wird von faireconomy.media (ForexFactory-Mutter) gehostet und ist der von der FF-Community seit Jahren für Indikatoren/EAs genutzte Weg (de-facto-sanktioniert); HTML-Scraping von forexfactory.com dagegen ist Cloudflare-geschützt und ToS-rechtlich grau (Scraper-Projekte nutzen `cloudscraper` und betonen "does not bypass Cloudflare/CAPTCHA"). XML-Feed = unproblematischer Pfad.
- **Confidence:** Hoch

### Claim 1.3 — investing.com: kein freier offizieller Weg, Scraping fragil/ToS-grau
- **Source:** GitHub julianocanuto/investing.com (Endpoint-Doku), mwblima/web-scraping-investing, andrevlima/economic-calendar-api
- **URL:** https://github.com/julianocanuto/investing.com ; https://github.com/andrevlima/economic-calendar-api
- **Date:** 2020–2021 (Endpoint-Doku), 2018 (API-Projekt)
- **Excerpt:** Dokumentierter Embed-Endpoint: `BASE_URL = https://sslecal2.investing.com` mit Parametern `columns=exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous`, `features=datepicker,timezone`, `countries=[...]`. Weiterhin von MT4/MT5-Dashboards genutzter Endpoint: `https://ec.forexprostools.com/` (WebRequest-Whitelist im News-Dashboard-EA [FF-Thread 1063159]). Aber: "It sources its data from investing.com through web crawling … there are no guarantees regarding its availability or stability." investpy hat die Kalender-Funktion entfernt; Cloudflare/Anti-Bot erschwert direktes Scraping.
- **Confidence:** Hoch (dass es keinen stabilen freien offiziellen Weg gibt), Mittel (aktuelle Funktionsfähigkeit der Legacy-Endpoints)

### Claim 1.4 — TradingEconomics `guest:guest` ist EINGESTELLT
- **Source:** api-evangelist/tradingeconomics (GitHub, Live-Verifikation)
- **URL:** https://github.com/api-evangelist/tradingeconomics
- **Date:** 2026-07-11 (verifiziert mit Live-Request)
- **Excerpt:** "the long-standing `guest:guest` sample-data account **has been discontinued** for the REST API (verified with a live request on 2026-07-11 …)". Kein Free Tier; Standard $149/Monat. → TradingEconomics fällt als kostenlose Quelle raus.
- **Confidence:** Hoch

### Claim 1.5 — Weitere freie Quellen / Bibliotheken
- **Source:** PyPI/GitHub
- **URL:** https://pypi.org/project/market-calendar-tool/ ; https://libraries.io/pypi/forexfactory ; https://github.com/spoluan/forex-factory-scraper ; https://github.com/fizahkhalid/forex_factory_calendar_news_scraper ; https://robots4forex.com/historical-forex-economic-calendar-2007-present-csv-format/ ; https://economic-calendar.horizonfx.id/
- **Date:** 2024–2026
- **Excerpt:**
  - `market-calendar-tool` (PyPI): scraped ForexFactory/MetalsMine/EnergyExch/CryptoCraft inkl. Datumsbereich → DataFrames.
  - `forexfactory` (PyPI, thomas-quant): "Fetch the Forex Factory economic calendar once and reuse it everywhere" — lokaler Parquet-Cache, CLI (`forexfactory populate`, `query --currency USD --impact high`).
  - `spoluan/forex-factory-scraper`: historischer Scraper (ab 2007), CSV pro Jahr, braucht `cloudscraper`.
  - `fizahkhalid/...`: Selenium-Scraper mit pre-event Alerts (Discord/Telegram/Webhook).
  - robots4forex: historischer FF-Kalender 2007–heute als CSV, Zeiten GMT+0 (Backtest-Fallback; Download-Bedingungen unklar/ggf. kommerziell — Confidence niedrig).
  - RapidAPI "Economic Calendar API" (horizonfx): Free Tier mit API-Key (`GET /calendar?countryCode=US&volatility=HIGH`), 5-min-Updates; Abhängigkeit von Drittanbieter-Scraping.
  - Financial Modeling Prep & Alpha Vantage: Free Tiers mit Key, aber Kalender-Abdeckung begrenzt (Sekundärquelle, niedrige Confidence).
- **Confidence:** Mittel–Hoch

### Datenquellen-Fazit (Priorisierung)
| Rang | Quelle | Key nötig | Abdeckung | Risiko |
|---|---|---|---|---|
| 1 | FF Weekly XML/JSON (`nfs.faireconomy.media`) | nein | aktuelle Woche, High/Med/Low, Forecast/Previous | IP-Rate-Limit; nur 1 Woche; keine Actuals |
| 2 | MT5-Terminal-Kalender via MQL5-Export-EA → CSV | nein | voller MetaQuotes-Kalender, laufend aktualisiert | Timeout >30 Tage; kein Tester; Demo-Drosselung; Extra-EA nötig |
| 3 | Historischer CSV-Cache (selbst aufgebaut aus wöchentlichen Pulls / spoluan-Scraper) | nein | 2007–heute | nur für Backtests nötig |
| 4 | RapidAPI horizonfx Free Tier | ja (kostenlos) | laufend | Drittanbieter-Stabilität |
| ✗ | TradingEconomics | guest eingestellt | — | entfällt |
| ✗ | investing.com Direkt-Scraping | — | — | Cloudflare/ToS, fragil |

---

## 2. Regelwerk-Spezifikation

### Claim 2.1 — Empfohlene Puffer: asymmetrisch −15/+10 min, Order-Purge bei T−10
- **Source:** FXNX (Bulletproof Compliance Architecture)
- **URL:** https://fxnx.com/en/blog/ea-news-filters-how-many-trades-break-prop-firm-rules
- **Date:** 2026-08-23
- **Excerpt:** "Prop firm rules often state a restricted window of ±2 minutes. However, running your EA with a 2-minute buffer is an operational hazard due to LP spread widening and potential slippage." → "pause trading at least **15 minutes before** high-impact events and **10 minutes after**"; "Exactly 10 minutes before a high-impact event, your EA must execute a purge routine that closes active market positions and cancels all pending orders on related and cross pairs"; "Global Currency Halts: When a high-tier event (NFP, CPI, FOMC) hits … freeze trading across **all currency pairs and indices**". Zusätzlich: Prop-Engines auditieren Fill-Timestamps (`deal_time`) — getriggerte Pending Orders UND Trailing-Stop-Modifikationen (`TRADE_ACTION_SLTP`) im Fenster zählen als Violation.
- **Confidence:** Hoch (mehrfach bestätigt, s. wide04)

### Claim 2.2 — Impact-Stufen: High zwingend; Medium optional/konfigurierbar
- **Source:** StrategyQuant-Forum (Praxis), XAUBOT-Docs, propifycompare
- **URL:** https://strategyquant.com/forum/topic/integrate-a-news-filter-with-ffcal_net/ ; https://xaubot.com/docs/setup/how-to-activate-the-news-filter/ ; https://propifycompare.com/resource/best-prop-firms-news-trading/
- **Date:** 2017 / 2025-10 / 2026-08
- **Excerpt:** Übliche Praxis: "avoid trading 30 mins before and after HIGH news impact only. Medium and Low is okay." XAUBOT: Filter wählbar "High, Medium" + Währungsliste. propifycompare: "Most firms follow the Forex Factory red folder calendar as a baseline … When a firm does not publish a list, treating all red folder Forex Factory events as restricted is the safest assumption." FundingPips Zero: "Only events marked Restricted on Economic Calendar on the FundingPips dashboard are restricted. Medium and low-impact events are not affected."
- **Spezifikations-Empfehlung:** Default = High only (+ optionales Flag `filter_medium_usd=true` für USD-Medium-Events in NFP-/FOMC-Wochen). Prop-Compliance bemisst sich ausschließlich an High-Impact (FTMO-Liste, FF red folder).
- **Confidence:** Hoch

### Claim 2.3 — Währungs-/Symbol-Mapping: FTMO-Primärtabelle als Vorlage
- **Source:** FTMO FAQ (DE + ES + EN, Primärquelle mit vollständiger Tabelle)
- **URL:** https://ftmo.com/de/faq/darf-ich-news-traden/ ; https://ftmo.com/es/faq/can-i-trade-news/ ; https://ftmo.com/en/faq/can-i-trade-news/
- **Date:** 2026-02-03 / 2025-12-02 / 2026-08-16
- **Excerpt (FTMO-Restricted-Events-Tabelle):**
  - **USD (Forex + Gold + US-Indizes + DXY):** Federal Funds Rate & Statement; Non-Farm Employment Change, Unemployment Rate & Wages; Advance GDP q/q; FOMC Meeting Minutes; CPI y/y
  - **EUR (nur Forex):** Main Refinancing Rate
  - **GBP (nur Forex):** Official Bank Rate & MPC Votes; CPI y/y
  - **CAD (nur Forex):** Overnight Rate/BOC Rate Statement; CPI m/m; Employment Change/Unemployment Rate
  - **AUD (nur Forex):** Cash Rate & RBA Statement; Employment Change; CPI q/q; GDP q/q
  - **NZD (nur Forex):** Official Cash Rate & RBNZ Statement; Employment Change; CPI q/q; GDP q/q
  - **CHF (nur Forex):** SNB Policy Rate
  - **Rohöl (UKOIL.cash, USOIL.cash):** Crude Oil Inventories
  - Beispiel-Logik FTMO: "während der US-NFP-Veröffentlichung können Sie EURGBP oder AUDNZD handeln; Sie dürfen jedoch keine Trades auf USDJPY oder GBPUSD innerhalb des Zeitfensters eröffnen oder schließen."
- **Abgeleitetes Mapping für das Bot-Portfolio:**
  - XAUUSD → {USD}; XAGUSD → {USD}; NAS100/US100/US30/SPX500 → {USD}; GER40 → {EUR}; UK100 → {GBP}; JPN225 → {JPY}
  - EURUSD → {EUR, USD}; GBPUSD → {GBP, USD}; USDJPY → {USD, JPY}; GBPJPY → {GBP, JPY}; EURJPY → {EUR, JPY}; USDCAD → {USD, CAD}; AUDUSD/NZDUSD → {AUD|NZD, USD}; USDCHF → {USD, CHF}
  - BTCUSD/ETHUSD → {USD} (defensiv; US-Makro treibt Crypto, vgl. Mubite [^1079^])
  - **Tier-1-Override:** Bei FOMC-Rate-Decision, FOMC-Minutes, NFP, US-CPI, Fed/ECB-PK → globaler Halt ALLER Symbole (Cross-Asset-Spillover, FXNX "Global Currency Halts").
- **Confidence:** Hoch (FTMO-Primärtabelle), Mittel (Tier-1-Global-Halt = Best Practice, nicht Firmenpflicht)

### Claim 2.4 — Umgang mit offenen Positionen: firmenabhängig, drei Regime
- **Source:** FTMO FAQ, FundingPips Help Center, E8 (Propvator), The5ers (Propvator), FXNX
- **URL:** https://ftmo.com/en/faq/can-i-trade-news/ ; https://help.fundingpips.com/hc/en-us/articles/34504137479441-News-Trading-Weekend-Holding ; https://propvator.com/blog/e8-markets-news-trading-rule/ ; https://propvator.com/blog/the5ers-news-trading-rule/
- **Date:** 2025–2026
- **Excerpt:**
  - **FTMO Standard Funded:** Halten erlaubt, wenn >2 min vor Event eröffnet — ABER: "if a Stop Loss or Take Profit is triggered within the restricted time window, this will also be considered a breach." → Praktisch: Position vor Fenster schließen ODER SL/TP-Risiko akzeptieren. Trailing-Stops im Fenster = Verstoß (FXNX).
  - **FundingPips Master (Flex/Standard/Pro):** Halten erlaubt; Öffnen/Schließen im ±5-min-Fenster → **Profit-Deduction (Soft Breach)**; **5-Stunden-Regel:** Trades ≥5 h vor Event eröffnet dürfen im Fenster geschlossen werden, Profits zählen. Partial Closes flaggen die ganze Order. **FundingPips Zero:** ±10 min, **Hard Breach**, auch Halten verboten ("No position may be opened, closed, or held").
  - **E8 One Funded:** ±5 min; Halten erlaubt, aber Schließen im Fenster unmöglich ("You cannot close the trade during the window, so plan accordingly"); Verstoß = Profit-Abzug bei Payout, kein Breach.
  - **The5ers High Stakes:** ±2 min nur für **neue Orders**; Halten inkl. SL/TP-Trigger im Fenster ausdrücklich erlaubt ("allowed to hit stop loss or take profit during the restricted window").
- **Spezifikations-Empfehlung (konservativster gemeinsamer Nenner):** Offene Positionen werden **vor** T−(buffer) geschlossen, wenn `close_before_news=true` (Default für FTMO-Standard-Modus, weil SL/TP-Trigger = Breach). Alternativ-Modus "hold_through": SL/TP einfrieren (keine Modifikationen im Fenster), Position unverändert — nur für The5ers/FundingPips-5h-Regel konform.
- **Confidence:** Hoch

### Claim 2.5 — Fail-Closed-Architektur & Zeitzonen sind Hauptfehlerquellen
- **Source:** FXNX, FF-Threads (WONNFX-Diskussion, FFCal)
- **URL:** https://fxnx.com/en/blog/ea-news-filters-how-many-trades-break-prop-firm-rules ; https://www.forexfactory.com/thread/1398065-free-wonnfx-news-filter-ea-for-mt4-and
- **Date:** 2026-08
- **Excerpt:** Silent-Failure-Modi: "failed WebRequest … missing terminal URL whitelisting … unhandled API rate limit, or a Daylight Saving Time (DST) timezone desynchronization between your broker's server clock and the calendar feed." WONNFX-Frage (unbeantwortet im Thread, aber zentrales Design-Kriterium): "when the news feed temporarily fails or returns stale data, does the EA fail safe by keeping trading disabled, or does it continue using the most recently downloaded calendar?" → Spezifikation: **fail-closed** (bei stale/fehlendem Feed: keine neuen Trades auf betroffenen Symbolen) + Staleness-HeartBeat (Feed älter als X h → Alarm).
- **Confidence:** Hoch

---

## 3. Prop-Firm-Regelwerk 2025/26 — konfigurierbares Regel-Set

### Claim 3.1 — FTMO
- **Source:** FTMO FAQ (Primär, EN/DE), propfirmsfinder, proptradingvibes, tradetanto/atlasfunded (Consistency)
- **URL:** https://ftmo.com/en/faq/can-i-trade-news/ ; https://propfirmsfinder.com/prop-firm/ftmo/ ; https://tradetanto.com/learn/prop-firm-consistency
- **Date:** 2026-02 bis 2026-08
- **Excerpt:** Eval (1-Step & 2-Step): **keine News-Restriktion** ("You may trade freely during all macroeconomic news releases"). Funded **Standard**: ±2 min um "selected news announcements", betroffene Instrumente gemäß Tabelle (Claim 2.3); Verbot umfasst Öffnen, Schließen, **Ausführung von Pending Orders inkl. SL/TP**; "Violating this rule may result in termination of an FTMO Account" (Hard Breach). Funded **Swing**: keine Restriktion (Trade-off: Leverage 1:30, s. wide06). **Konflikt:** propfirmsfinder behauptet "1-Step FTMO Account (Funded): Unrestricted" — widerspricht der FTMO-Primär-FAQ ("applies equally to traders who qualified through 1-Step and 2-Step"); Primärquelle hat Vorrang. **Consistency:** 2-Step: keine; 1-Step: 50%-Best-Day-Rule (in beiden Phasen; FTMO misst Best Day ggü. Summe der **positiven** Tage — strenger als üblich). **EA-Policy:** EAs erlaubt (kein Pre-Approval), verboten: Latenz-Arb, Cross-Account-Copying, Account-Management durch Dritte; späte-2025 "0.5–1% Risk-per-Trade"-Guidance wird bei Payout-Reviews als Flag genutzt (MyPropGenius).
- **Confidence:** Hoch (Regeln), Mittel (Konflikt 1-Step-Funded)

### Claim 3.2 — FundingPips
- **Source:** FundingPips Help Center (Primär), Propvator
- **URL:** https://help.fundingpips.com/hc/en-us/articles/34504137479441-News-Trading-Weekend-Holding ; https://help.fundingpips.com/hc/en-us/articles/34505029138449 ; https://propvator.com/blog/funding-pips-news-trading-rule/
- **Date:** 2026-01-29 (Help Center), 2025-09-22
- **Excerpt:** Eval: keine Restriktion, ABER "Purposely trading news in both evaluation phase and master phase is prohibited and will lead to account closure." Master (1-Step Flex, 2-Step Standard/Flex/Pro): **±5 min** um Restricted-High-Impact (News + Speeches; bei Reden: 5 min vor Beginn bis 5 min nach Ende) → Profit-Deduction (Soft), 5-h-Vorab-Eröffnungs-Exemption, Partial-Close flaggt ganze Order. **Zero-Account:** **±10 min, Hard Breach, Halten verboten**. Offizielle News-Quelle = "Economic Calendar on the FundingPips dashboard" (einzige maßgebliche Quelle!). Consistency: 1-Step Flex & 2-Step Standard/Flex **keine**; Zero 15%, On-Demand/2-Step Pro ~35% (atlasfunded/tradetanto). EA-Policy: Third-Party-EAs nur als Trade-/Risk-Manager; eigene vollautomatische EAs mit Ownership-Proof; HFT/Tick-Scalping/Gap-Trading/Hedging verboten (wide06 [^486^]).
- **Confidence:** Hoch

### Claim 3.3 — E8 Markets
- **Source:** Propvator, propfirmapp, coinspot
- **URL:** https://propvator.com/blog/e8-markets-news-trading-rule/ ; https://propfirmapp.com/prop-firms/e8-markets
- **Date:** 2026-07-24
- **Excerpt:** **E8 One / E8 One Crypto:** Eval frei; Funded ±5 min um High-Impact auf korrelierten Instrumenten (kein Öffnen/Schließen/Modifizieren; SL/TP-Trigger eingeschlossen); Halten erlaubt, Schließen im Fenster unmöglich; Verstoß = Profit-Deduction bei Payout (E-Mail-Notiz), kein Auto-Breach; wiederholte Verstöße → Kündigung im Ermessen. **E8 Signature (Forex/Crypto/Futures), E8 Pro, E8 Zero:** News komplett uneingeschränkt, alle Phasen. Consistency: Best-Day 40% (One/Classic/Track), 35% (Signature) — nur Funded, nur bei Payout, kein Breach. EA: erlaubt, muss trader-unique sein.
- **Confidence:** Hoch (Propvator verifiziert gegen Firmenquellen)

### Claim 3.4 — The5ers
- **Source:** Propvator (Primär-verifiziert), tradernotion
- **URL:** https://propvator.com/blog/the5ers-news-trading-rule/ ; https://www.tradernotion.com/prop-firms/the5ers
- **Date:** 2026-06-19 / 2025-11-18
- **Excerpt:** Hyper Growth / Pro Growth / Bootcamp: News erlaubt, aber **Bracketing** (gleichzeitig BUY STOP + SELL STOP um News) verboten (= "reckless trading", Kündigungsrisiko). **High Stakes (2-Step):** News-Trading in Eval UND Funded verboten: keine neuen Orders (Market oder Pending) ±2 min um High-Impact; Halten erlaubt, **SL/TP dürfen im Fenster triggern** (Unterschied zu FTMO!); Profit aus Verstoß-Orders wird abgezogen, Verluste trägt der Trader. Consistency: keine Best-Day-Rule auf CFD-Programmen (tradetanto). EA: eigene EAs erlaubt; Third-Party-Black-Box-EAs, Copy, Latenz-/Hedge-Arb, Tick-Scalping verboten.
- **Confidence:** Hoch

### Claim 3.5 — TopStep (Futures, kein CFD)
- **Source:** Propvator, tradetanto
- **URL:** https://propvator.com/blog/topstep-news-trading-rule/ ; https://tradetanto.com/learn/topstep-rules
- **Date:** 2026-08-13 / 2026-06-29
- **Excerpt:** Keine Blackout-Windows in keiner Phase; News-Trading erlaubt. Aber: "purposefully trading at maximum position size into a major news event is a prohibited trading strategy" → Review/Account-Schließung; Löschung des Trading-Tages möglich. Consistency: 50% Combine (Eval!), 40% XFA-Consistency-Pfad bei Payout. Relevanz für MT5-CFD-Bots: nur als Referenz (TopStep ist Futures-only, kein MT5).
- **Confidence:** Hoch

### Claim 3.6 — Branchenmuster ("Two-Phase News Illusion" bestätigt)
- **Source:** propifycompare, propfirmbridge, algospecial, backtrex (Konflikt!)
- **URL:** https://propifycompare.com/resource/best-prop-firms-news-trading/ ; https://propfirmbridge.com/education/prop-firm-challenge-day-1-checklist... ; https://backtrex.com/en/blog/prop-firm-news-trading-restrictions-strategies
- **Date:** 2026
- **Excerpt:** "The standard industry pattern is unrestricted evaluations and restricted funded accounts." (propifycompare). **Achtung Falschbehauptungen in Sekundärquellen:** backtrex behauptet, die FTMO-±2-min-Regel gelte "in beiden Phasen der Challenge" — widerspricht FTMO-Primär-FAQ; algospecial nennt FTMO "case-by-case/allowed with warnings" — veraltet/ungenau. → Regel-Set ausschließlich gegen Primärquellen (FTMO-FAQ, FundingPips-Help-Center) pflegen; Sekundärquellen ändern sich quartalsweise und widersprechen sich häufig.
- **Confidence:** Hoch (Muster), — (Negativbefund: Sekundärliteratur unzuverlässig)

### Konfigurierbares Regel-Set (YAML-artig)
```yaml
prop_rule_sets:
  ftmo_standard_funded:
    phases: [funded]
    window: {before_min: 2, after_min: 2}
    severity: hard_breach               # Account-Termination möglich
    covers_pending_execution: true      # SL/TP-Trigger im Fenster = Breach
    covers_sl_tp_modification: true
    hold_through_allowed: true          # aber SL/TP-Risiko!
    event_scope: ftmo_table             # Claim 2.3 (Restricted-Events-Liste)
    exemption: none
  ftmo_eval_or_swing:
    window: null                        # keine Restriktion
  fundingpips_master:
    phases: [funded]
    window: {before_min: 5, after_min: 5}
    severity: soft_profit_deduction
    covers_pending_execution: true
    hold_through_allowed: true
    exemption: opened_at_least_hours_before: 5
    event_scope: fundingpips_dashboard  # "Restricted"-Markierung; High + Speeches
  fundingpips_zero:
    phases: [funded]
    window: {before_min: 10, after_min: 10}
    severity: hard_breach
    hold_through_allowed: false         # auch Halten verboten
  e8_one_funded:
    phases: [funded]
    window: {before_min: 5, after_min: 5}
    severity: soft_profit_deduction_at_payout
    close_during_window: forbidden      # Halten ja, Schließen nein
  the5ers_highstakes:
    phases: [evaluation, funded]
    window: {before_min: 2, after_min: 2}
    severity: soft_profit_deduction
    covers_new_orders_only: true        # SL/TP-Trigger erlaubt!
    bracketing_banned: true
  operational_buffer:                   # unser eigener Sicherheits-Layer (Claim 2.1)
    block_new_entries: {before_min: 15, after_min: 10}
    purge_pending_and_positions_at_min_before: 10
    tier1_global_halt: true
```
**Empfehlung:** Bot mit `operational_buffer` (−15/+10, Purge T−10) fährt **jedes** obige Regel-Set compliant (max. Firmenfenster = ±10 bei FundingPips Zero). Nur FundingPips Zero erfordert zusätzlich `close_all_before_window` (Halten verboten).

---

## 4. IMPLEMENTIERUNGS-SPEZIFIKATION

### 4.1 Architektur
```
[Quellen-Schicht]
  Primary:   FF Weekly XML/JSON  https://nfs.faireconomy.media/ff_calendar_thisweek.xml
             (GET alle 60 min; Cache SQLite/Parquet; niemals >1 Request/15 min → IP-Rate-Limit)
  Secondary: MQL5-Export-EA im MT5-Terminal (unter Wine) → schreibt CalendarValueHistory
             (rolling, ≤30 Tage pro Call wegen ERR_CALENDAR_TIMEOUT 5401) nach
             Common/Files/calendar_export.csv → Python pollt Datei
  Tertiary:  manuell kuratierte Tier-1-Liste (FOMC/NFP/CPI-Termine aus forexfactory.com,
             Fed-Kalender) als YAML-Fallback
  Backtest:  historischer CSV/Parquet-Cache (spoluan-Scraper / robots4forex / eigener
             Langzeit-Cache ab Deployment-Tag — JETZT mit dem Sammeln beginnen)
```
**Wichtig (Wine/pymt5trade):** `mt5.calendar_value_history(...)` existiert **nicht** im Python-Modul — nicht implementieren! Entweder HTTP-Feed (läuft unter Wine problemlos via `requests`) oder MQL5-Helper.

### 4.2 Normalisierung (Pflicht, Hauptfehlerquelle)
```python
def normalize(event_raw):
    # 1. Zeit auf UTC bringen. FF-XML liefert US-Eastern (DST-sensitiv!).
    #    Nie Broker-Serverzeit oder lokale Zeit verwenden.
    t_utc = parse_ff_datetime(event_raw["date"]).tz_convert("UTC")
    # 2. Sanity-Crosscheck einmal täglich: FF-Webseite vs. Broker-Serverzeit
    #    vs. Systemzeit; Abweichung > 120 s -> Alarm + fail-closed.
    # 3. Impact mappen: FF {High, Medium, Low, Holiday} -> {3,2,1,0}
    # 4. Währung: ISO-3 (USD, EUR, ...); "ALL" bei Tier-1-Override-Liste
    return Event(t_utc, ccy, impact, title, is_speech=guess_speech(title))
```

### 4.3 Symbol→Währungs-Mapping (Claim 2.3)
```python
SYMBOL_CCY = {
  "XAUUSD": {"USD"}, "XAGUSD": {"USD"},
  "NAS100": {"USD"}, "US100": {"USD"}, "US30": {"USD"}, "SPX500": {"USD"},
  "GER40": {"EUR"}, "UK100": {"GBP"}, "JPN225": {"JPY"},
  "EURUSD": {"EUR","USD"}, "GBPUSD": {"GBP","USD"}, "USDJPY": {"USD","JPY"},
  "GBPJPY": {"GBP","JPY"}, "EURJPY": {"EUR","JPY"}, "USDCAD": {"USD","CAD"},
  "AUDUSD": {"AUD","USD"}, "NZDUSD": {"NZD","USD"}, "USDCHF": {"USD","CHF"},
  "BTCUSD": {"USD"}, "ETHUSD": {"USD"},
}
TIER1_GLOBAL = {"FOMC Rate Decision", "FOMC Minutes", "Non-Farm Payrolls",
                "CPI y/y (US)", "FOMC Press Conference", "Fed Chair Powell Speaks",
                "ECB Rate Decision", "ECB Press Conference"}   # -> halt ALL symbols
```

### 4.4 Filter-Logik (Pseudo-Code, in jedem Bot als Meta-Layer vor Order-Placement)
```python
def news_gate(symbol, now_utc, ctx) -> GateResult:
    if feed_stale(ctx.calendar, max_age=timedelta(hours=3)):
        return BLOCK("feed stale - fail closed")          # Claim 2.5
    for ev in ctx.calendar.events_window(now_utc, -30min, +30min):
        if ev.impact < cfg.min_impact:                    # default: High only
            continue
        if not (ev.ccy & SYMBOL_CCY[symbol]) and not (ev.title in TIER1_GLOBAL):
            continue
        # operationelles Fenster (strenger als jede Firmenregel)
        if now_utc >= ev.t - 15min and now_utc <= ev.t + 10min:
            return BLOCK(f"{ev.title} {ev.ccy}", resume_at=ev.t + 10min)
        # Purge-Zeitpunkt
        if now_utc >= ev.t - 10min and not ctx.purged[ev.id]:
            purge(symbol, ev)                              # s.u.
    return ALLOW

def purge(symbol, ev):
    cancel_all_pending_orders(symbol)                      # inkl. Cross-Pairs der Ccy
    if cfg.close_positions_before_news:                    # Default True (FTMO-Std)
        close_all_positions(symbol)                        # wegen SL/TP-Trigger=Breach
    else:  # hold_through-Modus (nur The5ers HS / FundingPips-5h-konform)
        freeze_sl_tp_modifications(symbol)                 # keine Trailing-Updates
        # bis ev.t + 10min

# Reden/Speeches (FundingPips): Fenster = [start-5min, end+5min] bzw.
# [start-10, end+10] bei Zero; Dauer unbekannt -> konservativ start-15 bis start+60.
```

### 4.5 Eval-vs-Funded-Profil (Two-Phase-Illusion adressieren)
```python
if cfg.account_phase == "evaluation":
    # Firmenregeln erlauben News-Trading — ABER: Expectancy-Daten (wide04:
    # -0.10R news-nah vs. +0.35R ruhig) sprechen dagegen. Filter TROTZDEM
    # aktiv lassen (mindestens Tier-1 + alle High-Impact), damit die Eval-
    # Equity-Kurve die Funded-Realität abbildet und keine News-Profits
    # entstehen, die auf Funded nicht replizierbar sind.
    apply(news_gate, profile="operational_buffer")
elif cfg.account_phase == "funded":
    apply(news_gate, profile=cfg.prop_rule_set)            # Kap. 3 YAML
    enforce("no_order_or_modify_inside_firm_window")       # inkl. SL/TP-Trigger
```
**FTMO-Standard-Funded-Sonderregel:** Da bereits ein **ausgelöster SL/TP** im ±2-min-Fenster ein Breach ist, gilt für Positionen, die das Fenster überleben sollen, faktisch: `close_positions_before_news=true` oder `risk_accepted=true` mit dokumentierter Entscheidung. FundingPips-Zero: `close_all` zwingend (Halten verboten).

### 4.6 Backtest-Hinweis
MT5 Strategy Tester hat **keinen** Kalender-Zugriff (MQL5, [FF-Thread 1400596]). Für Backtests: CSV/Parquet-Event-Cache in den Python-Backtester laden und `news_gate` identisch simulieren; sonst misst der Backtest systematisch Trades, die live verboten wären (Optimism Bias). Cache ab jetzt wöchentlich aufbauen — FF-XML hat nur 1 Woche Tiefe.

### 4.7 Test-Checkliste
- [ ] DST-Übergänge (US: Mär/Nov; EU: Mär/Okt — 1–3 Wochen Asymmetrie!)
- [ ] Feed-Ausfall simulieren → Bot muss blockieren (fail-closed), nicht weitertraden
- [ ] Pending Order wird bei T−30 s ausgelöst → Purge muss sie vorher gelöscht haben
- [ ] Trailing-Stop-Modifikation im Fenster → muss unterbunden sein
- [ ] Serverzeit-Drift Broker vs. UTC (>60 s) → Alarm
- [ ] Speech-Events ohne bekannte Endzeit → konservatives Fenster
- [ ] IP-Rate-Limit FF-XML: nur 1 Fetch-Prozess, geteilter Cache für alle 5 Bots

---

## Quellenverzeichnis

- [^911^] https://www.forexfactory.com/thread/1400596-mt5-calendar-data-bug — FF-Thread, MT5-Kalender-Bugs (ERR_CALENDAR_TIMEOUT 5401, >30 Tage, kein Tester, Demo-Drosselung) (2026-05/09)
- [^968^] https://github.com/api-evangelist/tradingeconomics — TradingEconomics guest:guest eingestellt, Live-verifiziert (2026-07-11)
- [^971^] https://www.forexfactory.com/thread/326551-mt4-news-calendar-indicator — NewsCal-Indikator, cdn-nfs.faireconomy.media Endpoint-Historie
- [^973^] https://www.forexfactory.com/thread/19293-ff-calendar-indicator-for-mt?page=46 — FFCal: XML nur aktuelle Woche, keine Actuals, IP-Limit "one load"
- [^974^] https://www.forexfactory.com/thread/326551-mt4-news-calendar-indicator?page=5 — IncludeSymbolCurrencies (Währungsfilter-Praxis)
- [^978^] https://www.algospecial.com/blogs/news-trading-integration-mt5-ea — FF-XML als "free, no-authentication feed"; 6-h-Fetch; GMT-Normalisierung; Buffer-Empfehlung
- [^901^] https://github.com/abbasi0abolfazl/forexfactory-scraper — Python-CLI für FF-XML (Filter Currency/Impact, TZ-Konvertierung)
- [^903^] https://github.com/ehsanrs2/forexfactory-scraper — ff_calendar_thisweek.* Export-Provider (json/csv/xml/ics), "not a public API", nur aktuelle Woche
- [^906^] https://github.com/spoluan/forex-factory-scraper — Historischer FF-Scraper (cloudscraper, CSV ab 2007)
- [^909^] https://pypi.org/project/market-calendar-tool/ — PyPI: FF/MetalsMine/EnergyExch/CryptoCraft-Scraper
- [^910^] https://libraries.io/pypi/forexfactory — PyPI `forexfactory`: Parquet-Cache-Paket
- [^970^] https://github.com/andrevlima/economic-calendar-api — investing.com-Crawler-API, "no guarantees regarding availability or stability"
- [^975^] https://www.forexfactory.com/thread/1063159-news-dashboard — News Dashboard EA: Quellen FF + investing (ec.forexprostools.com) + MQL5-Kalender; schließt Positionen/Pendings vor News
- [^1120^] https://github.com/julianocanuto/investing.com — investing.com Embed-Endpoint-Parametrisierung (sslecal2.investing.com, exc_*-Spalten)
- [^1042^] https://robots4forex.com/historical-forex-economic-calendar-2007-present-csv-format/ — Historischer Kalender 2007–heute, CSV, GMT+0
- [^1117^] https://economic-calendar.horizonfx.id/ — RapidAPI Economic Calendar Free Tier (Key nötig)
- [^621^] https://fxnx.com/en/blog/ea-news-filters-how-many-trades-break-prop-firm-rules — 10-Min-Pre-News-Flush, −15/+10 Puffer, Global Currency Halts, Pending-/SLTP-Fill-Timestamps = Violation, fail-closed, DST-Fehler (2026-08-23)
- [^626^] https://www.forexfactory.com/thread/1398065-free-wonnfx-news-filter-ea-for-mt4-and — WONNFX News Filter EA; Fail-safe-Designfrage; min. 15-min Update-Intervall
- [^1036^] https://strategyquant.com/forum/topic/integrate-a-news-filter-with-ffcal_net/ — Praxis: ±30 min nur High-Impact
- [^1028^] https://xaubot.com/docs/setup/how-to-activate-the-news-filter/ — XAUBOT: Impact-/Währungs-Selektion, Buffer-Parameter
- [^1044^] https://forexeastore.com/research/what-is-news-filter-in-expert-advisors/ — News-Filter-Definition, Quellen FF/MQL5, paar-spezifische Pausen
- [^120^] https://ftmo.com/en/faq/can-i-trade-news/ — FTMO-Primär-FAQ EN: ±2 min, SL/TP-Trigger = Breach, Eval frei, Swing exempt, 1-/2-Step gleich (2026-08-16)
- [^1078^] https://ftmo.com/de/faq/darf-ich-news-traden/ — FTMO-Primär-FAQ DE inkl. vollständiger Restricted-Events-/Instrumenten-Tabelle (2026-02-03)
- [^1085^] https://ftmo.com/es/faq/can-i-trade-news/ — FTMO ES, gleiche Tabelle (USD → Forex+Gold+US-Indizes+DXY) (2025-12-02)
- [^1083^] https://blog.pickmytrade.io/what-ea-are-banned-on-ftmo/ — FTMO-News-Regel-Details aus EA-Perspektive (2026-07-23)
- [^1074^] https://propfirmsfinder.com/prop-firm/ftmo/ — Behauptet 1-Step-Funded unrestricted (Konflikt mit FTMO-FAQ; als Fehler gewertet) (2026-04-16)
- [^1072^] https://propnavi.io/en/blog/ftmo-prohibited-strategies/ — FTMO Restricted-Event-Liste (Fed Funds, NFP, CPI, FOMC-Minutes, EZB/BoE/BoC/RBA/RBNZ/SNB, Crude Oil Inventories); Breach-Folgen (2026-07-08)
- [^1006^] https://mypropgenius.com/reviews/ftmo/ — FTMO 0.5–1%-Risk-Guidance als Payout-Review-Flag (2026-04-01)
- [^1005^] https://help.fundingpips.com/hc/en-us/articles/34501809112081-2-Step-Standard — FundingPips Help Center: ±5-min-Fenster, 5-h-Regel, Soft Breach, Dashboard-Kalender als offizielle Quelle (2026-07-24)
- [^1010^] https://help.fundingpips.com/hc/en-us/articles/34504137479441-News-Trading-Weekend-Holding — FundingPips: Eval frei aber "purposely trading news prohibited"; Master ±5; Zero ±10 Hard Breach, Halten verboten; nur "Restricted"-Events (2026-01-29)
- [^1011^] https://propvator.com/blog/funding-pips-news-trading-rule/ — FundingPips nach Account-Typ; kein Warnsystem (2025-09-22)
- [^1013^] https://help.fundingpips.com/hc/en-us/articles/34502157694865-FundingPips-Zero — Zero: News+Wochenende Hard Breach; Medium/Low nicht betroffen
- [^1025^] https://propvator.com/blog/e8-markets-news-trading-rule/ — E8: One ±5 min Profit-Deduction; Signature/Pro/Zero frei (2026-07-24)
- [^1127^] https://proptradingvibes.com/blog/e8-markets-consistency-rule — E8 Best-Day 40%/35%, nur Funded, nur bei Payout, kein Breach (2026-03-26)
- [^1026^] https://propvator.com/blog/the5ers-news-trading-rule/ — The5ers: High Stakes ±2 min neue Orders, SL/TP-Trigger erlaubt; Bracketing-Verbot (2026-06-19)
- [^1035^] https://www.tradernotion.com/prop-firms/the5ers — The5ers Programm-Details (2025-11-18)
- [^1024^] https://propvator.com/blog/topstep-news-trading-rule/ — TopStep: kein Blackout, Max-Size-in-News verboten (2026-08-13)
- [^1027^] https://tradetanto.com/learn/topstep-rules — TopStep Prohibited Practices (2026-06-29)
- [^1124^] https://tradetanto.com/learn/prop-firm-consistency — Consistency-Vergleich: FTMO 1-Step 50% (Basis = positive Tage), FundingPips je Produkt, The5ers/E8/FundedNext (2026-06-26)
- [^1123^] https://www.atlasfunded.com/post/prop-firms-with-no-consistency-rules — FundingPips Zero 15%, On-Demand ~35%, 1-Step Flex ohne (2026-07-23)
- [^1122^] https://fundingpips.com/blog/comparison-best-1-step-prop-firm-challenges — FundingPips 1-Step Flex: keine Consistency (2026-08-03)
- [^1126^] https://thepropfirmguide.com/best-prop-firms-no-consistency-rule/ — FTMO 2-Step & The5ers ohne Consistency (2026-07-20)
- [^1091^] https://propifycompare.com/resource/best-prop-firms-news-trading/ — Branchenmuster Eval-frei/Funded-restricted; FF red folder als Default-Annahme (2026-08-20)
- [^1014^] https://propfirmbridge.com/education/prop-firm-challenge-day-1-checklist... — 2026-Landkarte News-Policies; Pre-Positioning 3–5 h vor Events (2026-04-12)
- [^121^] https://backtrex.com/en/blog/prop-firm-news-trading-restrictions-strategies — Negativbeispiel: behauptet fälschlich FTMO-±2-min in Eval (2026-07-01)
- [^1076^] https://www.algospecial.com/blogs/prop-firm-news-trading-rules-2026.php — Vergleichstabelle (teilweise ungenau bei FTMO) (2026-08-01)
- [^1079^] https://mubite.com/en/crypto-reports/prop-firm-news-trading — US-Makro bewegt BTC 5–15 % (2026-05-30)
- [^913^] https://www.vpsforextrader.com/blog/ai-trading-co-pilot/ — CalendarValueHistory nur MQL5-seitig; EA prüft Kalender alle 5 min (2026-07-20)
- [^1039^] https://docs.mql4.com/mql5_language/mql5_functions/mql5_calendar — MQL5-Kalender-Funktionsliste (CalendarValueHistory, CalendarValueLast, CalendarEventByCurrency u. a.)
- [^1102^] https://github.com/Traders-Connect/mt5linux-tc/ — mt5linux: MetaTrader5-Python unter Wine via Windows-Python+RPyC (Architektur-Kontext)
