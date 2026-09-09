# Facet: Instrumenten-Eigenheiten & Prop-Constraints

**Research-Datum:** 2026 (Quellen 2023–2026) | **Suchen:** 25+ unabhängige Queries (EN/DE) | **Scope:** XAUUSD, NAS100/US100, Forex Majors, Commodity-Paare, JPY-Crosses, BTC/ETH, Prop-Firm-Regeln 2025/2026

---

## Key Findings

### 1. Volatilitäts- & Session-Profile je Instrument

**XAUUSD (Gold)**
- Höchste Bewegung im London/NY-Overlap (13:00–17:00 GMT / 8:00–12:00 ET); Asien-Session typischerweise "tot" (Range-Drift, dann 200 Pips in 90 Minuten nach London-Open) [^451^][^455^]
- Broker-Studien (XAUUSD-Daten 2006–2023): Große Bewegungen signifikant häufiger im Overlap als in Asien — jedoch proprietäre Research, nur indikativ [^455^]
- ADR-Schätzungen stark divergent (Einheiten-Chaos): $60–100/Tag [^537^], 530 "Pips" 2025 vs. 349 "Pips" 2024 (= $53/$34,9, OffbeatForex/ATR) [^523^], "15–30 Pips" [^99^] (vermutlich $15–30 gemeint), "100–200 Pip Daily Range" [^470^]. **Konsens-Richtung: Gold bewegt sich 7–10× so viel wie EURUSD** [^537^][^523^]
- Peak-Volatilität ~13:00 UTC; Intraday-Range im Overlap oft > $3 für Scalps [^456^][^537^]
- Treiber: Fed-Politik, DXY (68% der Gold-Bewegungen korrelierten invers zum DXY laut World Gold Council Q4 2024, zitiert in [^99^]), Geopolitik [^99^]

**NAS100 / US100**
- Volatilität ~1,5× S&P 500 (Beta ≈ 1,5); 2–3% Tages-Swings sind normal, nicht außergewöhnlich [^468^]
- 3-Phasen-ATR-Zyklus: NY Cash Open 09:30–11:30 ET = Peak (stündliche ATR 120–200+ Punkte), Lunch-Lull 12:00–14:00 ET (Whipsaws), MOC-Surge 15:00–16:00 ET (Rebalancing-Volumen) [^462^]
- Pre-Market (07:00–09:30 ET) + erste 2 Cash-Stunden = höchstes Volumen, klarste Richtungsmoves [^468^]
- Wochenrhythmus: Mo/Fr komprimiert, Mitte der Woche expandiert; FOMC-Tag = höchstes Monats-Volatilitäts-Event [^468^]
- >75% Indexgewicht Tech/Consumer Discretionary; Top-10-Earnings können den ganzen Index gap-en [^468^]

**Forex Majors — ADR 2025 (Jahresdurchschnitt, OffbeatForex/ATR)** [^523^]
| Paar | ADR 2025 | ADR 2024 | vs. EURUSD |
|---|---|---|---|
| EURUSD | 75 Pips | 65 | 1,00× |
| GBPUSD | 90 Pips | 81,5 | 1,20× |
| USDJPY | 133 Pips | 157,5 | 1,77× |
| USDCAD | 71 Pips | 63 | 0,95× |
| USDCHF | 62 Pips | 59,5 | 0,83× |
| AUDUSD | 57 Pips | 55 | 0,76× |
| NZDUSD | 54 Pips | 52 | 0,72× |
| XAUUSD | ~530 Pips | ~349 | ~7,1× |

- GBPUSD = volatilstes Major-Paar (ADR 111,5 Pips 2014–2025) [^529^]
- London/NY-Overlap (13–17 GMT) produziert die meiste Bewegung aller Session-Fenster; London-Open 08:00 GMT zweitaktivst, bes. GBP/EUR [^527^]
- Tokyo-Session: 30–60 Pips Ranges für Majors, Range-Trading-Umfeld [^510^]

**Crosses (JPY)**
- GBPJPY "The Beast/Dragon": ADR 150–250 Pips normal, 500–1000 Pips in Krisen; Carry-Trade-getrieben (UK-JP Zinsdifferenz 200–500 bp); Risiko-Off-Unwinds = 500–1000 Pips in Tagen [^453^]; andere Quelle: ~150–200 Pips [^527^]
- EURJPY: ~80–120 Pips ADR [^527^]; zwei aktive Fenster (Tokyo 00–09 GMT + London 07–16 GMT) — im Gegensatz zu EURUSD kein "Dead Zone" in Asien [^507^]; Spreads 1,5–3,0 Pips (Retail) [^507^]
- Tokyo-London-Overlap (07:00–09:00 GMT): Breakout-Fenster für JPY-Crosses — asiatische Ranges werden gebrochen, wenn europäische Liquidität einströmt [^502^][^509^]
- Treiber EURJPY: EZB-BoJ-Policy-Divergenz (Yield-Spread) + Risk-Sentiment (Risk-on → EURJPY up) [^520^]

**Commodity-Paare (AUDUSD, USDCAD, NZDUSD)**
- Niedrigste ADRs der Majors (54–71 Pips) → strukturell Range-freundlicher [^523^]
- USDCAD: inverse Korrelation zu Öl (Öl ↑ → USDCAD ↓); positiv korreliert mit USDCHF/USDJPY, negativ mit EURUSD/AUDUSD/GBPUSD [^495^][^497^]
- Sydney-Tokyo-Overlap relevanteste Session für AUD/NZD; Carry-Trade-Exposure (AUD/NZD vs. JPY) [^502^][^509^]

**BTC/ETH (optional)**
- 24/7-Markt → Wochenend-Regeln der Prop-Firma werden zum strategischen Constraint [^526^][^528^]
- Crypto-Trends zu persistent/gewaltsam für Mean-Reversion: RSI-Strategie auf BTCUSD schlug selbst mit Filtern fehl; Trend-Following (EMA-Crossover) besser geeignet [^459^]

### 2. Dokumentierte Strategie-Instrument-Fits (mit Quelle)

| Strategie | Instrument | Evidenz |
|---|---|---|
| Session-Breakout / ORB (London-Open, 5-Min-Range) | XAUUSD | 5-Min-ORB + 1-Min-VWAP-Filter, Stops 0,4–0,8 USD, 2:1 RR [^456^] |
| ORB (15-Min-Range ab NY-Open, FVG-Entry) | NAS100/US100 | FTMO-Blog: 15:30–15:45 CET Range, FVG-Limit-Entry, SL unter/über FVG-Mittelkerze, 2:1 RR [^458^] |
| ORB generisch | Indizes | Backtest SPX 15-Min-ORB: 56% Winrate, 1,8:1 RR [^501^]; NQ-ORB mit Tagesfilter: 198 Trades, 65% Win, PF 2,0, Ø +0,27% [^152^]; Unger-Academy-Backtest Nasdaq: funktioniert long & short, aber nur mit Filtern (Ø Trade $95) [^514^] |
| Trend-Following / Pullback (20/50 EMA) | XAUUSD | London-Trend-Continuation im Overlap; EMA-Pullbacks + Kerzenbestätigung [^452^][^457^] |
| Liquidity Sweep / Reversal | XAUUSD | "London Sweep": Stop-Grab unter Asia/London-Low, dann aggressive Umkehr im Overlap [^452^] |
| Mean Reversion (RSI + EMA200/ADX-Filter) | XAUUSD, EURUSD | Datensatz 2.397 Trades: XAUUSD bester Performer (PF 3,0, +0,8R Expectancy gefiltert), EURUSD zweitbest (PF 2,0, +0,5R); ungefiltert beide verlustig (PF <1) [^459^] |
| Mean Reversion (Flat-Regime) | EURUSD, GBPUSD, Gold | Asset-Strategy-Mapping: EURUSD/GBPUSD/XAUUSD = Mean Reversion, BTCUSD/AAPL = Trend [^450^] |
| Range-Trading | USDJPY, AUDJPY, EURJPY (Tokyo); AUDUSD/NZDUSD | Range + RSI/Stochastik in Tokyo-Session [^509^][^510^] |
| Breakout (Tokyo→London-Transition) | EURJPY, GBPJPY | Asia-Range-Bruch bei London-Open [^502^][^509^] |
| Momentum / Carry | GBPJPY | Positive Swap in Risk-on; Momentum-Strategien in anhaltenden Equity-Zyklen [^453^] |
| Scalping (Overlap, VWAP) | XAUUSD | Braucht <0,6 USD Spread, <100ms Latenz, 0,3–1,5 USD Targets, 1–30 Min Haltedauer [^456^] |
| News-Trading | Alle | Auf Funded-Accounts fast überall durch ±2–5-Min-Blackout eingeschränkt → strukturell kein frei wählbarer Stil mehr [^117^][^498^][^500^] |

### 3. Typische Spreads/Kosten (Retail/Prop, RAW-ECN, London/NY-Overlap)

Quelle: Vantage-Cost-Breakdown 2026 [^467^], FundingPips [^470^], Afterprime [^453^], ForexForStarters [^507^]

| Instrument | Typischer RAW-Spread | Kommission | Round-Trip-Kosten (1 Lot) |
|---|---|---|---|
| EURUSD | 0,0–0,2 Pips | $3/Side | ~$5–8 |
| GBPUSD | 0,1–0,4 Pips | $3/Side | ~$8–11 |
| USDJPY | 0,1–0,3 Pips | $3/Side | ~$7–10 |
| AUDUSD | 0,1–0,4 Pips | $3/Side | ~$7–10 |
| EURJPY | 1,5–3,0 Pips (Retail) | — | deutlich teurer als Majors |
| XAUUSD | 0,12–0,25 USD | $3/Side | ~$12–25 |
| NAS100/US100 | 0,7–1,5 Punkte | $3/Side | variiert (Futures-Roll) |
| BTC/USD | $20–80 (spread-only) | — | hoch |
| ETH/USD | $1,50–4,00 (spread-only) | — | mittel |

- Standard-Konten (kommissionsfrei): ~+0,6–1,0 Pips weiter [^467^]
- Kosten-Relevanz: EURUSD-Spreads ($1–3 RT) vernachlässigbar vs. 40-Pip-Trade; Gold (20–30 Pip-Spreads laut [^470^], widersprüchlich zu [^467^]) und Exotics teuer bei Hochfrequenz [^470^]
- Scalping-Grenze XAUUSD: < 20–30 Cents Spread empfohlen [^477^][^456^]

### 4. Prop-Firm-Regeln 2025/2026 im Detail

**FTMO (Branchen-Benchmark)**
- 2-Step: Phase 1 = 10% Target, Phase 2 = 5%; Max Daily Loss 5% (inkl. offener Positionen, Kommissionen, Swaps!), Max Loss 10% (statisch, initial balance), min. 4 Trading Days, kein Zeitlimit [^469^][^471^][^479^]
- NEU 1-Step: 10% Target, **3% Max Daily Loss**, 10% Max Loss, **50% Best-Day-Rule (Consistency)** — gilt auch auf dem simulierten Funded-Account; kein sofortiger Breach, aber Zwang zu weiteren Green-Days [^465^][^530^][^536^]
- News: Standard = kein Öffnen/Schließen ±2 Min um High-Impact-News (Funded); TP/SL-Trigger im Fenster = Soft Breach (Profit-Abzug). Swing-Account: News-Restriction komplett aufgehoben, dafür Leverage 1:30 statt 1:100 [^117^][^538^]
- Wochenende: Standard-Accounts müssen Freitag flach sein (automatische Liquidation, auch Crypto); Swing erlaubt Holding [^526^][^534^]. **Nuance/Konflikt:** FTMO-FAQ sagt "keine Restriktionen für Trading am Wochenende, wenn der Markt offen ist" (Crypto) [^540^] — Unterscheidung Trading vs. Halten beachten
- Leverage: FX 1:100, Indizes 1:50, Metals 1:30, Crypto 1:3,3 [^533^]
- EA: erlaubt ohne Pre-Approval (MT4/MT5), 2.000 Requests/Tag-Limit; verboten: Arbitrage, Drittzugriff/Account-Management, Latenz-Exploits [^494^][^519^]
- Wochenend-Crypto-Leverage wird dynamisch reduziert (Margin-Erhöhung Fr→So) [^524^]

**FundedNext**
- DLL 3–5% je nach Modell, Max Loss 6–10%; News erlaubt, Wochenend-Holding auf allen Accounts erlaubt, keine Consistency-Rule bei CFDs, kein Zeitlimit; EAs/Bots/Copy "responsible use" erlaubt; Scaling bis $4M [^475^][^482^][^483^]
- Eval: News frei; Funded (Stellar/Express): 2-Min-Fenster + Profit-Deduction [^117^]

**FundingPips**
- Third-Party-EAs nur als Trade/Risk-Manager erlaubt; eigene EAs vollautomatisch nur mit Ownership-Proof; verboten: HFT, Latenz-Arb, Tick-Scalping, Gap-Trading, Hedging, Copy-IN von extern, Server-Exploits [^486^]
- Funded: 2-Min-News-Blackout [^117^]

**The5ers**: News ±2 Min restricted (laut Vergleichstabelle [^475^]), andere Quelle: generell news-freundlich aber Monitoring gegen "News-Straddling" [^117^]; Stop-Loss mandatory (≤2%) [^475^]; Crypto 24/7 inkl. Wochenende [^531^]
**E8 Funding**: News ±5 Min [^475^] | **Alpha Capital**: 2-Min-Blackout, Profits void [^117^] | **FunderPro**: Challenge news-frei; Funded Standard 2-Min-Regel, Swing-Add-on uneingeschränkt [^500^] | **Soar Funding**: EA nur nach Risk-Team-Review; News 5-Min-Fenster (oder kostenpflichtiges Add-on) [^484^] | **BrightFunded**: EAs erlaubt; Funded 5-Min-News-Regel = Soft Breach [^478^]

**Branchenweit verboten (nahezu universell):** HFT/Latenz-Arbitrage, Tick-Scalping, Martingale/Grid (meist), Copy-Trading von externen Quellen (Signal-Seller), Hedging über Accounts hinweg, "Gambling"/Random-Lot-Sizing [^484^][^486^][^487^][^491^][^494^]
**Copy-Trading-Grenzlinie:** Intern (eigene Accounts, gleicher Name) fast überall erlaubt; extern IN (Signal-Seller → Funded) überall verboten [^494^]

---

## Major Players & Sources

- **Prop-Firmen (regelbildend):** FTMO (Benchmark, $650M+ ausgezahlt, 4,5M+ Kunden [^540^]), FundedNext, FundingPips, The5ers, E8, FunderPro, BrightFunded, Soar, FXIFY, Alpha Capital; Crypto-nativ: HyroTrader, Crypto Fund Trader, MyFundedFX
- **Datenquellen Volatilität:** OffbeatForex ADR-Tabelle [^523^][^529^], Trade That Swing (via [^523^]), Pro-Scalper Gold-ATR [^537^], FXNX Session-Mapping [^462^][^455^]
- **Backtest-Quellen:** QuantifiedStrategies (ORB, EURJPY) [^152^][^503^], Unger Academy (Crabel-ORB Nasdaq) [^514^], Quant-Signals (2.397-Trade RSI-Studie) [^459^], TradeAlgo ORB-Statistik [^501^]
- **Kosten:** Vantage-Breakdown [^467^], FXIFY [^466^]

---

## Trends & Signals

1. **Gold dominiert Prop-Trading:** XAUUSD = meistgehandeltes Symbol bei FTMO (24,04%, vor US30 15,91%, EURUSD 13,8%, US100 8,19%, GBPUSD 7,52%) [^512^]; FTMO-eigene Blogs bestätigen XAUUSD als Dauer-Spitzenreiter, US30/US100 als populärste Indizes [^504^][^505^][^506^][^513^]. Eine Quelle nennt XAUUSD "zweitmeistgehandelt nach EURUSD" [^99^] — Konflikt, FTMO-Primärdaten sprechen für Platz 1.
2. **Strategie-Regime-Switch statt Einzelstrategie:** Professionelle Ansätze kombinieren Mean-Reversion (50–60%) + Trend-Following (40–50%) im Portfolio und wechseln nach Marktlage [^450^]; Session-abhängige Strategiewahl (Range in Asien, Breakout/Trend in London/NY) ist Konsens [^451^][^455^][^509^]
3. **Filter machen den Unterschied:** Nackte RSI-/ORB-Signale sind breit unprofitabel (PF 0,98–0,99); mit EMA200+ADX- bzw. Tagesfiltern werden dieselben Setups profitabel (PF 2–3) [^459^][^152^][^514^]
4. **Prop-Regeln 2025/26 verschärfen sich strukturell:** Consistency/Best-Day-Rules (FTMO 1-Step 50% [^465^][^536^]), News-Blackouts auf Funded (aber frei in Eval → "Two-Phase News Illusion" [^117^]), dynamische Wochenend-Crypto-Margins [^524^]
5. **Eval-vs-Funded-Divergenz:** News-Trading in der Challenge fast überall erlaubt, auf Funded-Accounts fast überall ±2–5 Min eingeschränkt [^117^][^478^][^500^] → Strategien müssen für beide Regime validiert werden
6. **Instrumenten-Leverage als versteckter Constraint:** FTMO Metals 1:30, Indizes 1:50, Crypto 1:3,3 [^533^]; FXIFY Gold 1:30 (bis 1:50), Indizes 1:10 [^466^] → Positionsgrößen-Modelle müssen instrumentenspezifisch sein
7. **DLL-Management nach Instrument:** Forex-Majors (40–120 Pips ADR) sind strukturell leichter innerhalb 3–5% DLL zu managen als Gold ($50–100) und NAS100 (2–3% Swings) [^470^][^468^]

---

## Controversies & Conflicting Claims

1. **XAUUSD-ADR-Einheiten-Chaos:** Quellen nennen "15–30 Pips" [^99^], "$60–100" [^537^], "530 Pips 2025" [^523^], "100–200 Pips" [^470^] — je nachdem ob Pip = $0,10 oder $0,01 und welches Zeitfenster. Umrechnung nötig: 2025 realistisch ~$30–80/Tag. **Jede ADR-Zahl ohne Fenster+Datum ist unbrauchbar** [^523^].
2. **ORB-Evidenz widersprüchlich:** 56% Winrate/1,8:1 RR (TradeAlgo, SPX [^501^]) vs. "minuscule 0,04% avg gain" für rohe SPX-ORB (QuantifiedStrategies [^152^]) vs. 65% Win/PF 2,0 mit Tagesfilter (NQ [^152^]) vs. EliteTrader-Praktiker: "Backtesting war super bis auf Tick-Level, dann Desaster" [^516^]. Konsens: ORB funktioniert nur mit Filtern/Regime-Kontext, nicht mechanisch.
3. **Gold: Trend oder Mean-Reversion?** Landscape-These "Gold trendet sauber im Overlap" [^452^][^455^][^457^] vs. Asset-Mapping "XAUUSD = Mean-Reversion-Asset" [^450^] vs. RSI-Studie: Gold = bester Mean-Reversion-Performer, aber **innerhalb etablierter Trends** (Pullback-Logik, ADX<25) [^459^]. Auflösung: regime-abhängig — Mean-Reversion der Pullbacks, Trend-Following der Session-Richtung.
4. **FTMO Max Total Loss:** 10% (Konsens [^469^][^471^][^479^]) vs. "5% maximum total drawdown" (MyVeridex [^490^]) — letzteres widerspricht FTMO-Primärquellen, als Fehler einzustufen.
5. **FTMO Zeitlimit:** FundedNext-Vergleichstabelle nennt "30 Tage Phase 1" [^475^]; FTMO selbst sagt "unlimited/no time limit" [^465^][^471^][^540^] — Zeitlimit wurde abgeschafft, ältere Sekundärquellen outdated.
6. **FTMO Wochenend-Crypto:** "Muss Freitag flach sein, automatische Liquidation" [^526^][^534^] vs. FTMO-FAQ "keine Restriktionen am Wochenende, wenn Markt offen" [^540^] — vermutlich Unterscheidung *Handeln* (Crypto am WE möglich) vs. *Halten über FX-Close*; zusätzlich dynamische WE-Margin [^524^]. Vor Strategie-Design gegen aktuelles FTMO-Regelwerk verifizieren.
7. **The5ers News-Policy:** ±2-Min-Restriction [^475^] vs. "generell erlaubt, nur News-Straddling-Monitoring" [^117^] — planabhängig.
8. **NAS100 Tagesrange:** "50–150 Punkte" [^470^] vs. "120–200+ Punkte *stündliche* ATR im Cash-Open" [^462^] — massive Divergenz, vermutlich unterschiedliche Regime/Jahre; NAS100-Volatilität 2024–2026 stark gestiegen.

---

## Zuordnungs-Matrix: Strategietyp × Instrument × Timeframe

| Strategietyp | XAUUSD | NAS100 | EURUSD | GBPUSD | USDJPY/USDCHF | AUD/NZD/CAD | EURJPY/GBPJPY | BTC/ETH |
|---|---|---|---|---|---|---|---|---|
| **ORB / Session-Breakout** | ★★★ M5–M15, London-Open + Overlap [^456^][^457^] | ★★★ M5–M15, 09:30 ET + FVG [^458^][^514^] | ★★ M15 London-Open [^452^] | ★★ M15 London [^527^] | ★ Tokyo-Range-Break M15 [^509^] | ★ Sydney/Tokyo [^502^] | ★★★ Tokyo→London M15 [^502^][^509^] | ★ (24/7, kein "Open") |
| **Trend-Following / Pullback** | ★★★ M15–H1 Overlap, EMA20/50 [^452^][^457^] | ★★★ M5–H1 erste 2h [^468^] | ★★ H1–H4 | ★★ H1–H4 [^527^] | ★★ H1–H4 | ★ H4 (Öl/Commodity-getrieben) [^495^] | ★★★ H1–H4 Momentum/Carry [^453^] | ★★★ H1–H4, EMA-Cross [^459^][^450^] |
| **Mean Reversion (gefiltert)** | ★★★ RSI+EMA200+ADX H1 [^459^] | ★ (Volatilität zu hoch) | ★★★ H1 [^459^][^450^] | ★★ H1 [^450^] | ★★ USDCHF (niedrige ADR) [^523^] | ★★★ Asien-Range M15–H1 [^509^][^510^] | ★★ Range-Phasen [^527^] | ✗ fehlgeschlagen [^459^] |
| **Range-Trading** | ★ Asien-Session [^451^] | ✗ | ★★ Tokyo | ★ | ★★ Tokyo 30–60 Pip [^510^] | ★★★ niedrigste ADRs [^523^] | ★★ EURJPY [^527^] | ✗ |
| **Carry / Swing (Tage)** | ★★ H4–D1 (Zins-Differenz vs. USD) | ★★ H4–D1 | ★★ | ★★ | ★★★ USDJPY-Carry | ★★ AUD/NZD-Carry [^509^] | ★★★ GBPJPY/EURJPY positiver Swap [^453^] | ★★ (WE-Regeln beachten!) |
| **Scalping** | ★★★ Overlap, <0,6$ Spread [^456^] | ★★ Cash-Open | ★★★ engste Spreads [^470^] | ★★ | ★★ USDJPY Tokyo [^510^] | ★ | ★ (Spread 1,5–3 Pips) [^507^] | ★★ nur crypto-native Firms [^528^] |
| **News-Trading** | ★★★ reagiert stark auf US-Daten [^452^] | ★★★ FOMC-Playbook [^468^] | ★★ | ★★★ UK-Daten [^527^] | ★★ BoJ | ★ (Öl-Daten) | ★★ BoJ-Überraschungen [^507^] | ★★ |
| → **Prop-Funded-Eignung** | ⚠ News-Blackout ±2–5 Min; Overlap-Strategien kompatibel [^117^] | ⚠ Indizes-Leverage 1:10–1:50 [^466^][^533^] | ✅ am DLL-freundlichsten [^470^] | ✅ | ✅ | ✅ | ⚠ Swap-/WE-Regeln prüfen | ⚠ nur Swing/24-7-Firms [^528^][^531^] |

**Begründungs-Kernaussagen:**
- **XAUUSD + ORB/Trend im Overlap** = bestbelegter Fit im Prop-Kontext (Liquidität, Volumen, FTMO-Popularität) [^451^][^512^]
- **NAS100 + ORB ab NY-Open** = einziger dokumentierter Index-Fit mit FTMO-eigenem Setup [^458^]; enger DLL erfordert reduzierte Lotgrößen (1,5×-Vol-Regel: S&P-Size × 0,66) [^468^]
- **EURUSD + Mean Reversion / niedrige Kosten** = DLL-schonendster Prop-Pfad [^470^][^459^]
- **GBPJPY/EURJPY + Tokyo→London-Breakout + Carry-Swing** [^502^][^453^] — aber Swing nur auf Swing-Accounts/Firmen ohne WE-Restriction [^500^][^482^]
- **AUDUSD/NZDUSD/USDCAD + Range/Asien** [^509^][^523^]; USDCAD zusätzlich Öl-Korrelations-Overlay [^495^]
- **BTC/ETH + Trend-Following only** [^459^][^450^]; Prop-Constraints (1:2–1:3,3 Leverage, WE-Regeln) machen Crypto bei Forex-Firmen unattraktiv vs. Crypto-nativen Firms (HyroTrader 1:100, 24/7) [^528^][^534^]

---

## Recommended Deep-Dive Areas

1. **FTMO-Instrumenten-Statistik aktuell verifizieren** (Market-Analysis-Dashboard [^513^]): Ist XAUUSD 2025/26 weiterhin #1? Pip-Wert-Definitionen klären.
2. **ORB auf XAUUSD/NAS100 selbst backtesten** mit Tick-Daten inkl. Spread/Slippage — publizierte Edge-Zahlen widersprechen sich [^152^][^501^][^516^].
3. **Regime-Filter (ADX/EMA200) instrumentenübergreifend testen** — 2.397-Trade-Studie ist einzelne Quelle, Replikation nötig [^459^].
4. **FTMO 1-Step 50%-Best-Day-Rule**: Auswirkung auf Strategie-Design (Anti-Clustering von Profiten) quantifizieren [^530^][^536^].
5. **Wochenend-Gap-Risiko XAUUSD/GBPJPY** unter FTMO-Swing vs. FundedNext quantifizieren (Gap-Statistik [^513^], GBPJPY-Krisenmoves [^453^]).
6. **Kostenmodellierung pro Instrument × Strategie-Frequenz**: Spread-Anteil an Expectancy bei Scalping vs. Intraday vs. Swing [^467^][^456^].
7. **Eval-vs-Funded News-Divergenz**: Zwei-Phasen-kompatible Strategie-Architektur [^117^].

---

## Quellen

[^99^]: https://www.jptradingcapital.com/blog/en/gold-trading-strategies-xauusd (2026-05-06)
[^117^]: https://fxnx.com/en/blog/prop-firm-news-trading-rules-restricted-windows-program (2026-09-02)
[^152^]: https://www.quantifiedstrategies.com/opening-range-breakout-strategy/ (2026-01-06)
[^450^]: https://j2t.com/solutions/blogview/mean-reversion-strategies/ (2026-07-10)
[^451^]: https://www.quantvps.com/blog/when-to-trade-gold (2026-06-16)
[^452^]: https://fxnx.com/en/blog/london-ny-overlap-goldmine-strategy-xau-usd (2026-05-13)
[^453^]: https://afterprime.com/forex/gbpjpy (2026-09-03)
[^454^]: https://theforexscalpers.com/gold-trading-strategy-orderflow-xauusd-advanced-institutional-techniques-for-scalpers/ (2026-08-02)
[^455^]: https://www.wikifx.com/en/newsdetail/202606049314565824.html (2026-06-04)
[^456^]: https://fazencapital.com/learn/en/xauusd-scalping-5-minute-london-ny-overlap (2026-05-15)
[^457^]: https://www.jptradingcapital.com/blog/en/gold-trading-london-new-york-session-overlap-strategy-xauusd (2026-05-15)
[^458^]: https://ftmo.com/en/blog/opening-range-breakout-strategy-how-to-master-the-1530-us-session/ (2026-05-13)
[^459^]: https://quant-signals.com/rsi-trading-strategy/ (2026-04-04)
[^460^]: https://kentinofx.com/xauusd-session-based-strategy/ (2026-04-05)
[^462^]: https://fxnx.com/en/blog/nas100-trading-hours-session-volatility-gap-risk-mapped (2026-08-29)
[^465^]: https://ftmo.com/en/1-step-challenge/ (2026-07-01)
[^466^]: https://propfirmito.com/fxify/ (2026-08-14)
[^467^]: https://takeprofitapp.com/learn/vantage-spreads-commissions-fees (2026-04-17)
[^468^]: https://fazencapital.com/learn/en/nasdaq-100-trading-nas100-strategy-guide (2026-05-21)
[^469^]: https://www.edgeflo.com/blog/ftmo-rules (2026-03-05)
[^470^]: https://proptradingvibes.com/blog/fundingpips-forex-strategy (2026-04-20)
[^471^]: https://fundedaccountpro.com/prop-firms/ftmo (2025-12-11)
[^475^]: https://fundednext.com/blog/prop-firm-trading-rules (2025-11-12)
[^477^]: https://yoforex.org/phoenix-engine-pro-ea-v10-24-mt5-review/ (2026-05-23)
[^478^]: https://tradersfundhub.com/bright-funded-prop-firm (2025-10-01)
[^479^]: https://www.best-propfirms.com/reviews/ftmo/ (2025-08-01)
[^482^]: https://help.fundednext.com/en/articles/11982358 (2026-05-11)
[^483^]: https://h2tfunding.com/fundednext-vs-ftmo/ (2026-03-03)
[^484^]: https://thetrustedprop.com/prop-firms/soar-funding (2025-10-28)
[^486^]: https://help.fundingpips.com/hc/en-us/articles/34505029138449 (o.D.)
[^487^]: https://fundedtrading.com/prop-trading-firm/noctorial-review/ (2025-10-13)
[^490^]: https://www.myveridex.com/blog/en/best-prop-firm-2026 (2026-04-23)
[^491^]: https://thetrustedprop.com/prop-firms/arctic-funding (2025-06-09)
[^494^]: https://thortradecopier.com/blog/forex-prop-firms-that-allow-copy-trading-eas (2026-06-03)
[^495^]: https://theforexgeek.com/usdcad-trading-strategy/ (2024-11-29)
[^497^]: https://forextraininggroup.com/all-about-the-usdcad-currency-pair/ (2021-07-25)
[^498^]: https://clearedge.trading/post/prop-firm-news-trading-restrictions-automation-guide (o.D.)
[^500^]: https://funderpro.com/blog/news-trading-in-prop-firms-what-rules-you-must-follow-to-avoid-violations/ (2025-10-23)
[^501^]: https://www.tradealgo.com/trading-guides/day-trading/opening-range-breakout-strategy-how-to-trade-the-first-30-minutes (2026-04-01)
[^502^]: https://newyorkcityservers.com/blog/best-time-to-trade-forex (2026-02-16)
[^503^]: https://www.quantifiedstrategies.com/eurjpy-trading-strategy/ (2025-01-02)
[^504^]: https://ftmo.com/en/blog/a-high-win-rate-is-the-foundation-of-success/ (2025-11-04)
[^505^]: https://ftmo.com/en/blog/overtrading-will-not-give-you-good-returns/ (2025-11-04)
[^506^]: https://ftmo.com/en/blog/what-does-profitable-trading-look-like-with-a-working-ea/ (2025-11-04)
[^507^]: https://forexforstarters.com/markets/minors/eur-jpy/ (o.D.)
[^509^]: https://howtotrade.com/blog/best-pairs-to-trade-tokyo-session/ (2025-01-13)
[^510^]: https://www.defcofx.com/tokyo-session-forex-pairs/ (2025-09-30)
[^512^]: https://guestinvest.com/forex-symbols-ftmo-reveals-the-top-five-trading-symbols/ (2023-11-22)
[^513^]: https://academy.ftmo.com/lesson/statistical-application/ (2023-08-08)
[^514^]: https://ungeracademy.com/blog/testing-toby-crabel-s-opening-range-breakout-does-it-really-work-code-backtest-on-nasdaq (2026-07-17)
[^516^]: https://www.elitetrader.com/et/threads/opening-range-breakout-crabel-method.72968/page-5 (o.D.)
[^519^]: https://www.jptradingcapital.com/blog/en/what-is-ftmo-in-forex (2026-07-01)
[^520^]: https://ambienceairtech.com/eurjpy-trading-strategy-backtest-and-example/ (2025-09-18)
[^523^]: https://steadypips.net/guides/eurusd-average-daily-range-pips/ (2026-08-23)
[^524^]: https://propfirmcircle.com/industry-news/ftmo-updates-crypto-trading-rules (2026-05-20)
[^526^]: https://propfirmcircle.com/blog/myfundedfx-vs-ftmo-crypto (2026-03-17)
[^527^]: https://www.defcofx.com/which-forex-pairs-move-the-most-in-a-day/ (2026-05-10)
[^528^]: https://propfirmcircle.com/ar/blog/best-crypto-prop-firms (2026-01-06)
[^529^]: https://offbeatforex.com/forex-average-daily-range-table/ (2026-01-01)
[^530^]: https://www.fundedtradingplus.com/ftmo-1-step-challenge-vs-funded-trading-plus/ (2026-04-22)
[^531^]: https://www.tradernotion.com/blog/best-prop-firms-for-crypto-trading-2026 (o.D.)
[^533^]: https://bestpropfirmguide.com/faqs/ftmo/leverage/ (o.D.)
[^534^]: https://www.hyrotrader.com/blog/ftmo-for-crypto-traders/ (2025-03-18)
[^536^]: https://tradetanto.com/learn/ftmo-rules-evaluation-process (2026-06-21)
[^537^]: https://www.pro-scalper.com/gold-market/gold-volatility-xauusd (2025-01-01)
[^538^]: https://propnavi.io/en/blog/ftmo-swing-account-review/ (2026-07-08)
[^540^]: https://ftmo.com/en/faq/can-i-trade-on-the-weekend/ (2026-07-17)
