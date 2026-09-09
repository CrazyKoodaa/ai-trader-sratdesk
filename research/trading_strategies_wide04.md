# Facet: News/Event/Sentiment — Trading-Strategie-Recherche

**Scope:** News-Trading um Wirtschaftskalender-Events (NFP/CPI/FOMC), News-Avoidance als Meta-Filter, SEC-Filing-Strategien (13F/Form 4/8-K), LLM-/Social-Media-Sentiment, COT-Daten. Zielkontext: Python-Bots auf MT5 (XAUUSD, NAS100, Forex), PF > 1.5, min. 1:2 RR, Prop-Firm-tauglich, nur freie Datenquellen, lokale LLMs (Qwen3) verfügbar.

**Recherche-Basis:** 23 unabhängige Websuchen (EN+DE), 2 Deep-Dive-Reads (EarnForex COT, QuantifiedStrategies CPI). Stand der Quellen überwiegend 2025–2026.

---

## Key Findings

### 1. News-AVOIDANCE als Meta-Filter — stärkster, am besten belegter Use Case ✅

**Regelwerk:** EA pausiert X Minuten vor bis Y Minuten nach High-Impact-Events (NFP, FOMC, CPI, Zentralbank-Reden), schließt offene Positionen / löscht Pending Orders vor dem Fenster, friert ggf. alle betroffenen Währungen ein. Empfohlene Praxis: asymmetrische Puffer (≥15 min vor, ≥10 min nach), "Order Purge" 10 min vorher, globaler Halt über alle Pairs bei Tier-1-Events — prop-firm-Seitig sind ±2-Minuten-Fenster üblich, aber operationell zu knapp wegen Spread-Ausweitung und HTTP-/DST-Fehlern [^54^][^123^].

**Dokumentierte Evidenz:**
- FxBacktest-Methodik: News-nahe Trades vs.. ruhige Trades getrennt messen. Beispielergebnis: ruhige Trades **+.035R** Expectancy, News-nahe Trades **−0.10R** → klarer Fall für Filter; muss aber je Strategie selbst gemessen werden (Swing-Strategien kaum betroffen, Scalper "zerstört") [^58^].
- Event-Timing-Backtest (FXGlory, 53 Trades, yfinance-Daten): Baseline **negativ** (−5.36R Gesamt, 34 % Winrate) bei realistischen Kosten (1.5 Pip Spread + 0.5 Pip Slippage) — Kalender-Event-Timing ohne Filter ist **kein** Edge [^60^].
- Ausführungsrealität: Spreads weiten sich bei NFP von 0.3–1 Pip auf 5–50+ Pips aus; Orderbuchtiefe bricht lt. BIS-Studien ms vor der Veröffentlichung um >80 % ein; Slippage frisst Stop-Distanzen [^362^][^367^][^365^].
- Backtest-vs-Live-Gap: Faustregel PF live 20–40 % unter Backtest; News-Spreads und Slippage sind Hauptursache [^63^].

**Prop-Firm-Kompatibilität: höchste Relevanz des gesamten Facets.** FTMO: ±2-min-Fenster auf Standard-Funded (Violation = Account-Breach, auch ausgelöste SL/TP zählen); FundingPips ±10 min (hard breach); FundedNext ±5 min (nur 40 % Profit-Anerkennung im Fenster); Blue Guardian ±5 min; The5ers ±2 min (soft breach); FTMO Swing ohne Restriktion [^120^][^119^][^123^]. **Für den Ziel-Bot ist ein News-Filter praktisch Pflichtmodul** — MT5 hat eine native Kalender-API (frei), ForexFactory-Kalender ebenfalls frei nutzbar [^54^].

**Datenquellen (frei):** MT5 Economic Calendar (nativ), ForexFactory Calendar, ForexFactory Red-Folder-Events.

### 2. News-TRADING (NFP/CPI/Fade-the-Spike) — regelklar, aber schwach belegt, prop-inkompatibel ⚠️

**Regelwerk (Post-Release-Fade XAUUSD):** 2–5 min nach Release warten, Spike-High/Low markieren, Entry erst bei Reversal-Kerze zurück in Pre-News-Range, SL hinter Spike-Extrem, TP 50–61.8 % Retracement; bei Abweichung >0.2 % vom Konsens oder FOMC-Woche **nicht** faden [^52^][^77^][^305^].

**Evidenz — widersprüchlich:**
- Strategie-Guides behaupten Edge ("initial reaction is often an overreaction", institutioneller Vol-Crush als strukturelle Begründung für Fades) [^52^][^318^].
- ABER: QuantifiedStrategies-Backtest (SPY/TLT/GLD, 1993–heute): Kauf am CPI-Tag = **+0.01 %/Trade = zufällig**; Kauf am CPI-Close + N Tage halten = max +0.15 %/Trade ≈ Zufall [^303^]. EarnForex-Event-Timing-Backtest negativ [^60^].
- Ausführungskosten tödlich: Gold-Spreads 50+ Pips bei News, Stops rutschen $2–5; Backtests ohne realistische Spread-/Slippage-Modellierung "worthless" [^56^][^63^][^362^].

**Prop-Firm:** Direktes News-Trading auf Standard-Funded-Konten faktisch verboten (s.o.); nur FTMO Swing (Leverage 1:30) oder MyFundedFX erlauben es [^119^][^234^]. **Für Prop-Kontext disqualifiziert als Kernstrategie.**

### 3. Pre-FOMC-Drift — akademisch stark, aber vermutlich wegarbitriert ⚠️ (Widerspruch!)

- Lucca & Moench (NY Fed Staff Report 512): 1994–2011 betrugen die US-Aktienrenditen an Ankündigungstagen >30× die anderer Tage; >80 % der Equity-Prämie fielen in die **24 h VOR** der Ankündigung; Replikation auf globalen Indizes, nicht auf anderen Anlageklassen [^116^]. Schwedische Replikation: +0.48 % pre-FOMC-Drift am OMXS [^131^].
- **Gegenbefund:** Kurov/Wolfe/Gilbert ("The Disappearing Pre-FOMC Announcement Drift", FRL 2020): Drift seit ZLB-Liftoff (Jan 2016) **nicht mehr signifikant**, auch bei Meetings mit Pressekonferenz; Ben Dor & Rosa (2019): kein Drift 2011–2017 [^359^][^369^].
- → Klassische Anomalie-Publikations-Dekadenz. Für NAS100-CFDs auf MT5: nur 8 Events/Jahr = winzige Stichprobe; historischer Edge fraglich. **Kein verlässlicher PF>1.5-Baustein, bestenfalls Satelliten-Signal.**

### 4. COT-Positionierungs-Strategie — belegbar, wöchentlich, prop-tauglich ✅ (für Forex)

**Regelwerk (EarnForex, Dealer-Folgestrategie):** Long wenn Dealer-Longs steigen UND Dealer-Shorts fallen (vs. Vorwoche), Short umgekehrt; kein Signal bei Gleichrichtung; always-in-market, wöchentlicher Rebalance nach COT-Release (Fr 15:30 EST, Datenstand Di); invertierte Paare (USD/CAD, USD/JPY, USD/CHF, USD/NZD) spiegeln [^125^].

**Evidenz:** Backtest von 32 CoT-Strategien über ~8 Jahre: Dealer-Folge positiv auf allen Majors **außer AUD/USD**, aber mit "signifikanten Drawdowns" (v.a. während GFC 2008) und "nicht sehr hoher" Profitabilität; Gold (XAU/USD) explizit als unzuverlässig ausgeschlossen [^125^][^126^]. Freier MQL5-EA + CFTC-CSV-Daten verfügbar → **direkt backtestbar auf MT5 mit freien Daten** [^126^].

**Prop-Firm:** Keine News-Fenster-Problematik (wöchentlich, Positionen halten über News ist erlaubt); kompatibel. **Instrumente: FX-Majors ja, Gold nein (Backtests unzuverlässig), NAS100 indirekt möglich (CFTC Nasdaq-100-Futures-COT existiert, aber im EarnForex-Backtest nicht validiert).**

### 5. SEC-Filing-Strategien (13F / Form 4 Insider) — akademisch gemischt, für NAS100-CFD-Bot kaum geeignet ⚠️

- **Form 4 / Insider-Käufe:** Lange akademische Tradition mit 4–8 % p.... Überschussrenditen (TradeAlgo-Zusammenfassung; stärkste Signale: Cluster-Käufe, große Beträge, C-Level, Small-Caps) [^53^]. ABER: Finance Research Letters 2024 — positive **Prozent-**Renditen nach Filing, die bei realistischem Dollar-Volumen **negativ** werden; Renditen negativ mit Liquidität korreliert → "limited arbitrage negating profitable and scalable trading strategy" [^50^]. **Direkter Widerspruch in der Literatur.**
- **13F-Cloning:** Freie Backtester existieren (the13f.com, 13Foresight) — Ergebnisse gemischt (Appaloosa-Clone 1999–2026: 18.9 % vs SPY 8.2 % p.a.; Nalanda: −2.5 % vs +15.4 %) [^238^][^237^]. Fundamentale Limits: 45-Tage-Meldelag, nur Long-US-Equity, keine Shorts/Derivate, Quartalsauflösung [^228^].
- **8-K/NLP auf Filings:** Keine belastbaren öffentlichen Retail-Backtests gefunden (Suche ergab nichts Substanzielles).
- **Relevanz für Zielportfolio:** 13F/Form 4 sind Einzelaktien-Strategien. Auf MT5-NAS100-CFD höchstens als **Aggregations-Signal** (13F-Cluster in Index-Schwergewichten → Index-Richtungsbias); Pfad wäre: SEC EDGAR (frei) → Parsing → Index-Gewichtung. Aufwand/Nutzen für Prop-Bot gering.

### 6. LLM-/Social-Media-Sentiment — hohe Paper-Returns, massive Methodenkritik ⚠️ (Widerspruch!)

**Pro-Evidenz:**
- Lopez-Lira & Tang (2023): ChatGPT-4-Long/Short auf US-Aktien-Headlines 2021–2022: **400 % kumuliert, Sharpe 3.8**; Springer-Replikation bis 2023: 650 % Long/Short, 300 % Short-only; stärker bei Small-Caps und negativen News [^114^][^115^].
- End-to-End-LLM-System (arXiv 2502.01574): Sentiment-Integration hebt Sharpe z.B. TSLA-SMA-Crossover von 0.34 auf 3.47, Winrate 32.2 %→57.0 % [^51^].
- Social Sentiment: Reddit-Sentiment prognostiziert Volatilitätsspitzen besser als Twitter; BERTweet-Strategie +84.4 % höhere Returns (2021/2023); Twitter-Sentiment-Backtest Sharpe 1.82 vs Buy&Hold 1.35 [^314^][^313^][^311^].

**Kritik (schwerwiegend):**
- **"Time Machine GPT"-Problem:** temporale Leakage — LLM-Trainingsdaten enthalten die Testperiode; präzise Vorhersagen können Memorisation sein; kaum detektierbar, da in den Gewichten eingebettet [^227^].
- Prompt-Iterations-Overfitting ("discarded prompts were specification tests"), Survivorship-Bias in generiertem Code (statische Index-Konstituenten blasen NAS100-Momentum-CAGR um +208 bp p.a. auf) [^239^][^232^].
- Öffentlicher 30-Tage-ChatGPT-Demo-Test: +8.7 %, aber Prompts wurden unterwegs angepasst → "sentiment, not evidence" [^239^].

**Für Qwen3-lokal:** Kein öffentlicher belastbarer Backtest speziell Qwen+FX gefunden. Realistischer Pfad: LLM als **Feature** (News-Headline-Scoring über freie Feeds), nicht als Signalgeber; OOS muss strikt nach Trainings-Cutoff liegen (Qwen3-Cutoff beachten!). FinBERT/FinGPT als Alternative.

### 7. Sentiment-Umfragen (AAII als Contrarian) — moderate, kostenlose Ergänzung ✅

- AAII: Extremes Bärensentiment (>2 SD) → überdurchschnittliche 6–12-Monats-Renditen (nach extrem niedrigem Optimismus: +14 %/+20.7 % im 6-/12-Monats-Schnitt, S&P stieg jedes Mal) [^300^][^304^].
- QuantifiedStrategies-Backtest: Long bei Bull-Bear-Spread <−20, 4 Wochen halten → +1.03 %/Trade; asymmetrisch (bullish Extreme schwächeres Signal) [^302^].
- Meta-Ranking (LambdaFin): Insider-Cluster & COT-Extreme "strong", 13F/AAII "medium", einzelne Insider-Verkäufe/13F-Zeilen "weak"; Retail-Sentiment schwächelt durch Meta-Kontrarian-Effekt [^306^].
- **Zeithorizont Wochen–Monate → eher Regime-Filter für NAS100-Swing-Bot als Standalone-Strategie; kein PF>1.5-Kandidat allein.**

---

## Major Players & Sources

| Quelle | Typ | Beitrag |
|---|---|---|
| Lucca & Moench (NY Fed SR 512) [^116^] | Akademisch | Pre-FOMC-Drift-Urpapier |
| Kurov/Wolfe/Gilbert; Ben Dor & Rosa [^359^][^369^] | Akademisch | Drift-Decay-Gegenbefund |
| Lopez-Lira & Tang [^114^][^115^] | Akademisch | ChatGPT-Sentiment-Returns (umstritten) |
| Finance Research Letters 2024 [^50^] | Akademisch | Insider-Filing-Strategie nicht skalierbar profitabel |
| EarnForex CoT-Strategie + MQL5-EA [^125^][^126^] | Community/Tool | 32 backtestete CoT-Strategien, freie CFTC-Daten |
| QuantifiedStrategies [^303^][^302^] | Backtest-Blog | CPI-Tag ~zufällig; AAII-Contrarian moderat positiv |
| FTMO FAQ / Propvator / BestProps [^120^][^119^][^123^] | Prop-Regelwerke | News-Fenster ±2/±5/±10 min, Soft/Hard Breach |
| FXNX / FxBacktest [^54^][^58^] | Praxis | News-Filter-Architektur (10-min-Flush), News-vs-Calm-Expectancy-Messung |
| Libertify "New Quant" Survey [^227^] | Survey | Temporal Leakage / 10-Punkte-Reporting-Standard |
| SEC EDGAR, CFTC COT, AAII, ForexFactory | Freie Datenquellen | Filings, Positionierung, Sentiment, Kalender |

---

## Trends & Signals

1. **News-Avoidance ist der Standard, nicht News-Trading:** Praktisch alle Prop-Firm-Regelwerke 2026 restringieren News-Fenster; "Fail-closed"-News-Filter mit Order-Purge ist EA-Pflichtarchitektur [^54^][^123^].
2. **LLM-Sentiment boomt in Papers, aber Replikationskrise droht:** Temporal Leakage und Prompt-Overfitting sind die zentralen ungelösten Probleme; Reporting-Standards werden gefordert [^227^][^239^].
3. **Anomalie-Dekadenz:** Pre-FOMC-Drift nach Publikation geschwächt/verschwunden — Mahnmal für alle kalenderbasierten Edges [^359^].
4. **Smart-Money-Composite statt Einzelsignale:** Kombination aus COT-Extremen + Insider-Clustern + Retail-Contrarian schlägt Einzelindikatoren [^306^].
5. **Ausführungskosten als Edge-Killer dominieren die News-Trading-Literatur:** Spread-Spikes 5–20×, Slippage, Orderbook-Kollaps >80 % [^362^][^365^].
6. **Strukturelle Begründung für Post-News-Fades** (institutioneller Vol-Crush nach Options-Pre-Positionierung) [^318^] — plausibel, aber ohne robusten öffentlichen Intraday-Backtest belegt.

---

## Controversies & Conflicting Claims

| Behauptung | Dafür | Dagegen |
|---|---|---|
| "Fade the spike" bei NFP/CPI hat Edge | Strategie-Guides, Vol-Crush-Mechanik [^52^][^318^] | QuantifiedStrategies: CPI-Tag ≈ Zufall; Event-Timing-Backtest negativ [^303^][^60^]; Ausführungskosten [^362^] |
| Pre-FOMC-Drift ist handelbar | Lucca & Moench: >80 % der Equity-Prämie [^116^]; OMXS-Replikation [^131^] | Verschwunden seit ~2015/2016 (Publication Decay / reduzierte Unsicherheit) [^359^][^369^] |
| Insider-Käufe (Form 4) liefern Alpha | 4–8 % p.a. Excess Returns, Cluster-Signale [^53^][^306^] | Negative USD-Renditen bei realistischer Kapazität, Liquiditätskorrelation [^50^] |
| LLM-Sentiment schlägt Markt | Sharpe 3.8 / 650 % kumuliert [^114^][^115^]; +84 % BERTweet [^314^] | Time-Machine-Leakage, Prompt-Overfitting, keine sauberen OOS-Tests [^227^][^239^] |
| "News meiden hilft immer" | Erwartungswert-Split +0.35R vs −0.10R [^58^] | Gleiche Quelle: hängt von Strategie ab; Swing-Strategien kaum betroffen, Filter kann Edge kosten |
| EA-Backtests belegen News-Filter-Nutzen | Anbieter-Claims (z.B. Forex Fury +204 %, 93 % Winrate) [^73^][^62^] | Anbieter-Claims ohne unabhängige Verifikation; MQL5-Backtests ohne Live-Forward "almost none show live results" [^56^] |

---

## Recommended Deep-Dive Areas

1. **News-Filter als Meta-Layer für die Top-5-Strategien (höchste Priorität):** Eigenes Experiment — Basisstrategie auf XAUUSD/NAS100 mit vs. ohne ±15/±10-min-High-Impact-Filter (MT5-Calendar-API), Expectancy-Split messen [^58^][^54^]. Direkt prop-pflichtrelevant.
2. **COT-Dealer-Folge + COT-Index-Extreme als wöchentlicher Regime-Filter für Forex-Majors:** Freie CFTC-Daten + freier EarnForex-MQL5-EA ermöglichen sofortige Replikation; Drawdown-Charakteristik prüfen; Gold separat testen (EarnForex warnt) [^125^][^126^].
3. **Post-News-Fade auf XAUUSD mit realistischen Kosten modellieren:** Intraday-Tick/M1-Daten, Spread-Spike-Modell (5–20×, 10–15 s Peak), Entry erst nach Spread-Normalisierung; einziger News-Trade mit plausibler Mechanik-Begründung [^318^][^367^].
4. **Qwen3-Sentiment als Feature (nicht Signal):** Striktes OOS-Protokoll (nur News nach Modell-Cutoff), klassifizierte Headline-Scores als Filter auf technische Entries; Reporting nach dem 10-Punkte-Standard dokumentieren [^227^][^239^].
5. **13F-Cluster-Aggregation auf NAS100-Schwergewichte als Low-Frequenz-Bias:** SEC EDGAR frei; prüfen, ob Quartals-Cluster der Top-Manager Index-Renditen vorhersagen (Steuerungsgröße, kein Entry-Signal) [^228^][^306^].
6. **AAII/CNN-Fear&Greed-Contrarian als Wochen-Regime-Gate für NAS100-Swing:** frei verfügbar, publizierte moderate Edge, trivial implementierbar [^302^][^300^].

---

## Quellenverzeichnis

- [^50^] https://www.sciencedirect.com/science/article/pii/S1544612324015435 — Finance Research Letters, "Insider filings as trading signals" (2024/2025-02)
- [^51^] https://arxiv.org/html/2502.01574v1 — arXiv, "An End-To-End LLM Enhanced Trading System" (2025-02-03)
- [^52^] https://newyorkcityservers.com/blog/gold-xauusd-trading-strategy — NYC Servers (2026-04)
- [^53^] https://www.tradealgo.com/trading-guides/stocks/insider-trading-signals-how-to-track-sec-form-4-filings-for-investment-ideas — TradeAlgo (2026-04)
- [^54^] https://fxnx.com/en/blog/filtres-news-ea-combien-de-trades-enfreignent-les-regles-des-prop-firms — FXNX (2026-09)
- [^56^] https://fortraders.com/blog/risk-reward-ratio-how-to-use-it-to-your-advantage — ForTraders (2026-08)
- [^58^] https://fxbacktest.app/guide/backtest-news-avoidance/ — FXBacktest (2026-07)
- [^60^] https://fxglory.com/learn/forex-strategies/economic-calendar-forex-strategy/ — FXGlory (2026-07)
- [^62^] https://eafxstore.com/product/ea-rx-five-mt4/ — EAFXStore (2025-11)
- [^63^] https://blodsalgo.com/blog/en/track-ea-performance-trading-metrics/ — BlodsAlgo (2026-02)
- [^73^] https://eafxstore.com/product/forex-fury-mt4/ — EAFXStore (2025-07)
- [^77^] https://www.pro-scalper.com/xauusd-strategies/news-trading-gold — Pro-Scalper (2025-01)
- [^114^] https://link.springer.com/content/pdf/10.1007/s10614-025-11024-w.pdf — Springer (2025)
- [^115^] https://www.imperial.ac.uk/media/imperial-college/faculty-of-natural-sciences/department-of-mathematics/math-finance/Kargarzadeh_Alireza_02092220.pdf — Imperial College MSc Thesis
- [^116^] https://econpapers.repec.org/repec:fip:fednsr:512 — Lucca & Moench, NY Fed SR 512 (2011)
- [^119^] https://propvator.com/blog/is-news-trading-allowed-in-ftmo/ — Propvator (2026-08)
- [^120^] https://ftmo.com/en/faq/can-i-trade-news/ — FTMO FAQ (2026-08)
- [^123^] https://bestprops.com/rules/news-trading-rules/ — BestProps (2026-07)
- [^125^] https://www.earnforex.com/forex-strategy/cot-strategy/ — EarnForex
- [^126^] https://www.earnforex.com/guides/backtesting-strategies-based-on-commitments-of-traders/ — EarnForex
- [^131^] http://arc.hhs.se/download.aspx?MediumId=3247 — SSE Bachelor Thesis (2017)
- [^228^] https://the13f.com/backtest.html — The13F Manager Clone Backtester
- [^237^] https://13foresight.com/fund/nalanda-india-fund-ltd — 13Foresight (2025-07)
- [^238^] https://13foresight.com/fund/appaloosa-management-lp — 13Foresight
- [^227^] https://www.libertify.com/interactive-library/llm-financial-prediction-trading-new-quant-survey/ — Libertify (2026-04)
- [^232^] https://www.crucible-research.com/claude-code-trading — Crucible Research (2026-06)
- [^239^] https://algotrader.ch/ai-trading/chatgpt-trading/ — AlgoTrader.ch (2026-07)
- [^300^] https://www.aaii.com/sentimentsurvey — AAII (2026-09)
- [^302^] https://www.quantifiedstrategies.com/aaii-and-market-sentiment-indicators/ — QuantifiedStrategies (2025-01)
- [^303^] https://www.quantifiedstrategies.com/cpi-trading-strategy/ — QuantifiedStrategies (2024-10)
- [^304^] https://www.aaii.com/journal/article/is-the-aaii-sentiment-survey-a-contrarian-indicator — AAII Journal (2013-06)
- [^306^] https://www.lambdafin.com/articles/smart-money-vs-dumb-money — LambdaFin (2026-05)
- [^311^] https://projekter.aau.dk/the-impact-of-sentiment-on-stock-price-movements-a-wallstreetbets-casestudie-a6079954.html — AAU Thesis
- [^313^] https://devexperts.com/blog/how-to-create-and-backtest-trading-strategy-on-twitter-sentiments/ — Devexperts (2019-09)
- [^314^] https://algolabhk.com/en/blogs/reddit-sentiment-analysis-trading — Algolab (2026-08)
- [^318^] https://fundedfast.com/learn/fundamentals/cpi-trading — FundedFast (2026-07)
- [^234^] https://blodsalgo.com/blog/de/eas-in-prop-firm-challenges-verwenden/ — BlodsAlgo DE (2026-02)
- [^359^] https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/ — PMC, "The disappearing pre-FOMC announcement drift" (2020)
- [^362^] https://fxnx.com/en/blog/backtest-spread-slippage-costs-your-tester-skips — FXNX (2026-08)
- [^365^] https://offbeatforex.com/forex-brokers-for-trading-news/ — OffbeatForex (2026-06)
- [^367^] https://comparebroker.io/how-to-trade-major-news-events/ — CompareBroker (2026-05)
- [^369^] https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf — Kurov/Wolfe/Gilbert (2020)
