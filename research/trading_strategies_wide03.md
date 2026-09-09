# Facet: Indikator/Trend/Mean-Reversion

**Recherche-Datum:** 2025 (Suche durchgeführt im Rahmen der Trading-Strategie-Landscape-Recherche; 30+ Queries, EN+DE)
**Scope:** EMA/SMA-Cross, ADX-Trendfolge, Supertrend, Donchian/Turtle, MACD, RSI-Reversion, Bollinger Bands, VWAP, Grid/Martingale (Negativbeispiel), Breakout-Retest — mit Fokus auf XAUUSD, NAS100, Forex Majors, Timeframes M5–H4, Prop-Firm-Tauglichkeit (PF > 1.5, RR ≥ 1:2, 0,5 % Risiko/Trade, EOD-DD).

---

## Key Findings

### Übergreifende Meta-Befunde (wichtigster Teil des Facets)

1. **Klassische Indikator-Regeln haben seit den 1990ern massiv an Profitabilität verloren — akademisch gut belegt.** Sullivan/Timmermann/White (1999) und Bajgrowicz & Scaillet (2012) zeigen für 7.846 technische Regeln (Filter, MA, S/R, Channel-Breakouts, OBV): In den drei jüngsten Dow-Subperioden (bis 2011) wurde **keine positive Performance mehr detektiert, selbst vor Transaktionskosten**; vergangene Gewinner-Regeln lassen sich nicht zuverlässig in die Zukunft selektieren [^1^]. Hsu & Kuan (2005) finden nach Data-Snooping-Korrektur nur noch in "jungen" Indizes (NASDAQ Composite, Russell 2000) profitable Regeln, nicht in Dow/S&P 500 [^1^]. Studien zum MA-Rule bestätigen einen klaren Profitabilitäts-Verfall nach ~1990 (Lebaron 2000, Schulmeister 2009, Fang et al. 2013, Taylor 2014) [^2^]. Für FX: Levich & Thomas (1993) und Neely et al. (1997, 2009) zeigen historische Profitabilität in den 1970/80ern, die in den frühen 1990ern abnahm; Neely & Weller (2003) finden auf **Intraday-FX-Daten keine Outperformance** optimaler Regeln [^3^][^4^].

2. **Timeframe-Effekt ist der stärkste, konsistenteste Befund über alle Quellen:** Identische Regeln liefern auf D1/W1 positive Ergebnisse und auf M5–M30 katastrophale Verluste. Unabhängige Multi-Timeframe-Backtests (CoinQuant, große Samples, inkl. Gebühren): EMA-Cross BTC: 5M PF 0.56 / −91.9 % ROI, 15M PF 0.63, 30M PF 0.72, 1H PF 0.76, 4H PF 1.03, 1D PF 1.34, 1W PF 2.94 [^5^]. Supertrend BTC: 1M PF 0.54, 5M PF 0.70, 15M PF 0.76, 30M PF 0.96 — aber 4H PF 1.41, 6H PF 1.44, 12H PF 1.49, 1D PF 1.51 [^6^]. RSI-Mean-Reversion ETH: 5M PF 0.89, 15M PF 0.82, 30M PF 0.71, 4H PF 0.79, 8H PF 1.35 [^7^]. **Konsequenz: M5–M15 mit reinen Indikator-Regeln ist nach Kosten fast immer toxisch; H4/D1 ist der realistische Arbeitsbereich** — deckt sich mit der Prop-Firm-Landscape (Trend-Pullback H4/D1 + H1).

3. **Trendfolge-Institutionen (Realgeld-Proxy) bestätigen "funktioniert, aber zyklisch und drawdown-lastig":** SG Trend Index (10 größte Trend-CTAs): +27 % (2022), −4 % (2023), +2.7 % (2024), YTD 2025 über −11 % (Stand 22.05.2025). Seit 2023 profitierten von 26 Futures-Märkten nur 6 von Trendfolge — **Gold war mit annualisiert +2,2 % einer der wenigen konstant positiven Trend-Beiträger** [^8^]. Barclay CTA Index + Lynx (Trendfolge-Fonds seit 1999) zeigen lange Durststrecken (2011–2020 fast flat bei CTA-Index) mit Ausreißerjahren 2021/2022 (Lynx +28,8 %/+40,8 %) und Korrelation ~0 zum S&P 500 [^9^].

4. **Turtle/Donchian: historische CAGRs (1996–2006) von 29–58 % sind im Out-of-Sample (2007–2022) auf 2–10 % CAGR bei 17–50 % Max-DD kollabiert.** QuantifiedStrategies-Nachtest der sechs Curtis-Faith-Systeme auf 27 Futures (2007–2022, long-only, ohne Sizing/Stops): 6-Monats-Momentum CAGR 9,76 %/DD 50 %; Dual-MA (100/350) CAGR 3 %/DD 41 %; ATR-Channel-Breakout CAGR 5,3 %/DD 30 %; Bollinger-Breakout CAGR 2,1 %/DD 17 % — vs. Faiths In-Sample-Werte von 29,4–57,8 % [^9^]. Faith selbst fand: **Time-Exit (80 Tage halten) schlug Breakout-Exits** (57,2 % vs. 29,4 % CAGR) und ein 25/350-EMA-Filter verbesserte die Qualität — Indiz für chop-pigere Märkte [^10^].

5. **ADX als Filter ist umstritten bis kontraproduktiv; DI-Crossover direkt ist besser.** Großer Multi-Asset-Backtest (4.236 Trades, 24 ADX-Varianten, Forex/Krypto/Gold/Indizes): 15/24 Varianten profitabel; **DI-Crossover auf D1 bei BTCUSD PF 1.56 (WR 43,8 %) und XAUUSD PF > 1.50**; aber ADX-als-Filter-auf-EMA-Cross **verschlechterte** die Ergebnisse fast überall (EURUSD PF 0.89, GBPUSD PF 0.67, nur NAS100 relativ ok mit PF 1.33); H1 deutlich schlechter als D1, teils negative Expectancy [^11^]. ADX+RSI auf BTC 4H: PF 1.74, WR 54,5 %, DD 19,75 %, aber nur 11 Trades/12 Monate [^12^].

6. **VWAP-Pullback (relevant für NAS100) hat die sauberste dokumentierte intraday Edge des Facets — aber stark zeitfenster-gebunden.** Mechanischer 18-Monats-Backtest QQQ 5M (Jan 2024–Jun 2025, 312 Trades, non-repainting, Kommission inkl.): gesamt PF 1.54, WR 52,6 %; **Entry-Fenster 9:45–11:30 ET: PF 2.08, WR 62,4 %; alle Trades nach 11:30 aggregiert verlustbringend (PF 0.69/0.53)** [^13^]. Regeln: ≥3 Schlusskurse über VWAP (Trend), Pullback-Touch + RSI(2) < 25, Entry auf nächster grüner 5M-Kerze über VWAP, SL 1,5×ATR(14), Ziel Vortages-Hoch. Zweite unabhängige Studie (quantbuffet, QQQ 2018–2023): VWAP-Trend-Trading 671 % Return, Sharpe 2.1, MaxDD 9,4 % vs. Buy&Hold 126 %/DD 37 % — aber WR nur 17 % (Payoff-getrieben) [^14^]. Gegenprobe: VWAP-Mean-Reversion auf BTC 1M/10M/1H (CoinQuant): PF 0.40–0.99, klar negativ [^15^]; VWAP-Deviation auf NQ-Futures (PineScriptForge, 760 Trades): PF 1.22, WR 50,5 %, DD 4,5 % [^16^].

7. **RSI(2)/Mean-Reversion funktioniert dokumentiert auf Aktienindizes (SPY/QQQ), auf Forex ist die Evidenz schwach.** Connors-Regeln (Long nur > SMA200, RSI(2) < 5–10, Exit RSI(2) > 65–75 oder > 5d-SMA): SPY seit 1993 ~0,9 %/Trade, CAGR ~9 %, WR ~76 %, DD 15–34 % je nach Variante [^17^]. QQQ RSI(2): 10,0 % p.a. vs. 6,4 % Buy&Hold, gut in allen Bärenmärkten [^18^]. Aber: Connors-Test auf 28 FX-Paaren (TradingHeroes) — funktionierte nur auf Teilmenge, Majors vs. Crosses reagierten gegensätzlich auf Optimierung [^19^]; CoinQuant RSI-MR auf ETH negativ auf fast allen TFs [^7^]. **Für Forex-Majors ist Mean-Reversion-Edge nicht belastbar belegt.**

8. **MACD standalone: Winrate < 50 %, Sharpe ~0,3 — nur als Kombination brauchbar.** Akademische Vergleichsstudie (Dow/Nasdaq/S&P-Konstituenten 2015–2021, Python): reine MACD-Regeln WR ~0,37, Sharpe 0,28; Histogramm-Regel höchste WR, aber P&L-Ratio < 1; Signal-Crossover-Variante WR ~0,5 mit P&L > 2, aber Sharpe nur 0,34–0,35; **MACD+RSI / MACD+MFI schlagen standalone deutlich** [^20^]. QuantifiedStrategies MACD+Bollinger auf SMH (2001–heute, Kosten inkl.): 209 Trades, 1,4 %/Trade, WR 78 %, DD 15 % — aber Regelwerk proprietär/teils hinter Paywall, Vorsicht Overfitting [^21^].

9. **20-EMA-Pullback (Prop-Firm-Landscape-Strategie) hat schwache unabhängige Evidenz in Reinform:** Trader-Dale-Backtest EUR/USD (2 Monate, 138 Trades, 1:1 RR): WR nur 48,5 % ≈ Münzwurf; mit VWAP-Filter: WR 60 % bei 73 Trades [^22^]. QuantifiedStrategies 20-EMA-Stand-alone SPY: CAGR 3,06 % vs. B&H 7,87 % — allein nicht effektiv, Kombination verbessert [^23^]. Pullback-Variante (>SMA200, <SMA20, RSI5<45): WR 82 %, CAGR 8,3 %, DD 30 %, nur 30 % Marktzeit [^24^]. 9/20-EMA-Cross auf 159 indischen Large Caps (6.590 Trades, echte Kosten): Expectancy +0,28R, WR 33 %, Payoff 3,2 — **3 von 9 Jahren negativ (regime-abhängig)** [^25^].

10. **Breakout-Retest / London Open: Evidenz gemischt bis negativ in unabhängigen Tests.** GitHub-Backtest London-Breakout (EURUSD/GBPUSD/GBPJPY, Jul 2024–Jul 2025, M15, SMA50-Filter, News-Filter, TP=2×Asian-Range): Accuracy nur ~54,1 %, GBPJPY am stärksten, **EURUSD flat, GBPUSD ~breakeven/negativ** [^26^]. QuantifiedStrategies: London-Breakout EUR/USD Long/Short "often resulted in losses" ohne Zusatzfilter [^27^]. Kommerzielle Quelle (newyorkcityservers): "typisch 50–60 % WR, PF > 1.3" — Marketing-Nähe, und explizite Warnung: 5–10 %/Monat im Backtest = Overfitting-Verdacht [^28^]. Simulierte Website-Backtests (tradinggambits, 60–65 % WR) sind explizit simuliert, nicht empirisch [^29^]. ORB auf ETH 5M (secuora, 417 Trades, Fees): PF 0.65, −44,8 % — klar negativ [^30^].

11. **Supertrend: auf H4+ bei trendstarken Assets (Gold!) plausibel, auf M5–M30 toxisch; Parameter-Optimierung = Overfitting-Falle.** Siehe Befund 2 [^6^]. Bayesian-Optimierungs-Paper (arXiv, Nifty 50 u.a.) zeigt Out-of-Sample-Verbesserung durch BO — aber explizit mit Train/Test-Split als Overfitting-Schutz; Default (ATR 10, ×3) wurde geschlagen [^31^]. Praxis-Konsens für XAUUSD: H4/D1 mit ATR 10 / Mult 3, M15/H1 mit 7/2; Multi-TF-Alignment (H4→H1→M15) als Standard-Verbesserung [^32^][^33^]. Indische MT5-EA-Studie (BB+ADX, XAUUSD): **H4 schlug H1 signifikant in Backtest UND 1-Monats-Realtime** [^34^].

12. **Grid/Martingale = Negativbeispiel, jetzt auch akademisch quantifiziert:** MDPI-Studie (2026) zu MT5-Grid+Soft-Martingale: Balance-Drawdown 13,98 % (das, was auf Tear-Sheets gezeigt wird) vs. **Maximaler Equity-Drawdown (floating) 79,97 %** — DDR-Kennzahl macht die Disclosure-Lücke sichtbar; System nur unter 1:500-Offshore-Leverage "überlebensfähig", unter ESMA 1:30 nicht deploybar; strukturell Gambler's-Ruin-äquivalent [^35^]. Martingale-Simulation: 6 Verluste in Folge treten in ~75 % der 200-Trade-Sessions auf; ein Sequenz-Fail kostet das 63–1023-fache des Sequenz-Gewinns [^36^]. **Für Prop-Firm (EOD-DD, 0,5 % Risiko) kategorisch ungeeignet.** Selbst EA-Verkäufer bewerben "No Martingale / No Grid" als Qualitätsmerkmal [^37^]. Forward-Test-Beleg (indonesische Thesis, XAUUSD H1, Martingale-EA): PF 1.41 in 11 Tagen, aber Backtest-DD 53,7 % — Tail-Risiko bestätigt [^38^].

---

## Major Players & Sources

| Quelle | Typ / Vertrauenswürdigkeit | Relevanz |
|---|---|---|
| Sullivan/Timmermann/White 1999; Bajgrowicz & Scaillet 2012; Hsu & Kuan 2005 | Peer-reviewed / A | Data-Snooping-Referenzrahmen; "7.846 Regeln"-Studien [^1^] |
| Neely/Weller/Dittmar (St. Louis Fed, JFQA 1997; intraday 2003) | Peer-reviewed / S | TA-Profitabilität FX: historisch ja, intraday nein [^3^][^4^] |
| QuantifiedStrategies.com | Unabhängiger Backtest-Blog / B | Turtle-OOS-Nachtest, RSI(2), Golden Cross, London Breakout [^9^][^17^][^27^] |
| Curtis Faith, "Way of the Turtle" (2007) | Primärquelle Original-Turtle | 6 Systeme, CAGRs 1996–2006, Time-Exit-Befund [^9^][^10^] |
| Ai For Alpha CTA-Report / SG Trend Index; Quantica | Industrie / NA–B | Realgeld-Trendfolge-Performance 2022–2025, Gold als Top-Beiträger [^8^] |
| CoinQuant.ai (Multi-TF-Backtests, große Samples) | Kommerzielle Backtest-Plattform / NA | Konsistenter TF-Effekt; Daten plausibel, aber Krypto-Fokus [^5^][^6^][^7^] |
| quant-signals.com ADX-Studie (4.236 Trades) | Unabhängiger Backtest-Blog / NA | Wichtigste ADX-Evidenz inkl. XAUUSD/NAS100 [^11^] |
| PineGen.ai Case Study VWAP QQQ | Tool-Anbieter mit transparenter Methodik / NA | Sauberster VWAP-Backtest (non-repainting, Kosten, Monats-Breakdown) [^13^] |
| GitHub: MHZardary/london-strategy-backtest; maker-tung/xauusd-trend-follow | Open Source / S | Reproduzierbare Backtests; XAUUSD-EA mit FTMO-Circuit-Breaker, 28 % WR-Charakteristik [^26^][^39^] |
| MDPI Algorithms 19(6):442 (2026) | Peer-reviewed / A | Grid/Martingale-Risikoquantifizierung (MBD vs. MED) [^35^] |
| arXiv 2206.12282 (MACD comparative study) | Preprint / S | MACD standalone schwach, Kombinationen besser [^20^] |
| ECU-Thesis (Bunten) 50/200-MA in Marktphasen | Thesis / A | MA-Rule in Bärenmärkten vermeiden [^40^] |

---

## Trends & Signals

- **Regime-Filter sind der zentrale moderne Hebel:** Faith-Filter (40d-MA > 200d-MA) hob Winrate eines Turtle-Systems von 68 %→76 % und Gain/Loss von 8:1→25:1 (JSE-Studie) [^41^]; 25/350-EMA-Filter [^10^]; SMA200-Bias bei RSI(2) [^17^]; H1-50-EMA-Richtungsfilter beim London-Breakout [^29^]. Konsistentes Muster: **Signal + Trendfilter schlägt Signal allein**, obwohl ADX-Filter explizit kontraproduktiv sein kann [^11^] — Widerspruch siehe unten.
- **Time-Exits und feste ATR-Stops schlagen Trailing/reaktive Exits in chop-pigen Märkten** [^10^]; bei VWAP-Trend-Pullback zerstörte ein Trailing-Stop die Edge (PF 0.76), fixer 2×ATR-Stop PF positiv [^42^].
- **Winrate ist Vanity-Metrik:** VWAP-Trend QQQ mit WR 17 % und Sharpe 2.39 [^14^]; 9/20-EMA mit WR 33 %, Payoff 3.2, +0.28R [^25^]; VWAP-Pullback BTC 4H: WR 22,7 %, +25,5 % (Payoff 4,7:1) [^42^]. Passt zu Zielkriterium "min. 1:2 RR" — niedrige WR mit asymmetrischem Payoff ist das Geschäftsmodell, nicht das Problem.
- **Out-of-Sample-Zerfall ist die Norm:** VWAP-Trend-Pullback 5 Kryptos, 3/5 OOS positiv, BTC sogar besser (PF 2.46), SOL/XRP negativ [^42^]; Turtle-Systeme 2007+ massiv schwächer [^9^]; DFRD-Studie: TA-Profitabilität hat "kurze Persistenz", adaptives Umschalten als Schlüssel [^43^].
- **Gold (XAUUSD) ist derzeit strukturell trend-freundlichster Markt des Facets:** CTA-Analyse (Gold +2,2 % ann. als einer von 6 profitablen von 26 Märkten seit 2023) [^8^]; ADX-DI-Cross XAUUSD D1 PF > 1.50 [^11^]; MT5-Studien zeigen H4 > H1 auf Gold [^34^]; Open-Source XAUUSD-Trend-EA (MQL5, FTMO-konform, 4-Jahres-Backtest) dokumentiert ehrlich: 28 % WR, Long-only-Bias als Hauptrisiko [^39^].
- **Overfitting-Signale erkennen:** zu hohe Backtest-Returns (5–10 %/Monat London-Breakout) [^28^]; EA-Marktplatz-Claims (PF 2.70/91,67 % WR ohne News-Filter im Tester) explizit als verzerrt markiert [^37^]; Bayesian-Optimierung ohne OOS-Split [^31^].

---

## Controversies & Conflicting Claims

1. **"Trendfolge funktioniert" vs. "Trendfolge ist seit 2011 tot":** Quantica dokumentiert SG Trend Index Q1 2024 +12,2 % (8.-bester Monat seit 2000) [^44^] vs. Ai For Alpha: 2023–2025 kumulativ stark negativ (−11 % YTD 2025) [^8^]. Auflösung: extrem regime-abhängig; 2022 war Ausreißer. Für Prop-Firm heißt das: Trendfolge muss DD-Phasen von Jahren überstehen können — bei EOD-DD-Regeln kritisch.
2. **MA-Crossover Evidenz widersprüchlich je nach Markt/Stichprobe:** Saudi-Aktienmarkt-Studie (2008–2017): MA-Regeln profitabel **auch nach Kosten**, Short-Seite am profitabelsten [^45^]; Emerging-Markets-Thesis: 7/15 VMA-Regeln schlagen Benchmark, aber nach Signifikanztest keine mehr [^46^]; STOXX-600-Studie: MA-Strategie generiert **keine abnormalen Returns**, Bollinger mit kurzem MA am besten, v.a. in Bärenmärkten [^47^]. ⇒ Edge hängt von Marktineffizienz-Grad ab; Majors/Indizes am härtesten.
3. **ADX: Filter-Nutzen widersprochen.** Lehrbuch-Konsens "ADX > 25 als Trendfilter" vs. 4.236-Trade-Studie: Filter **reduziert** PF (BTC 1.56→1.16), DI-Cross direkt besser [^11^]; CoinQuant ADX+RSI-Filter verbesserte dagegen BTC 4H auf PF 1.74 (kleines Sample, 11 Trades) [^12^].
4. **VWAP auf QQQ/NAS100:** PineGen PF 1.54–2.08 [^13^] und quantbuffet Sharpe 2.1 [^14^] (beide Long-Bias, US-Session) vs. CoinQuant VWAP auf BTC PF 0.40–0.99 [^15^] und PineScriptForge NQ PF 1.22 [^16^]. ⇒ VWAP-Edge scheint **instrumenten- und session-spezifisch** (US-Equity-Open, institutionelles Benchmark-Verhalten), nicht universell.
5. **Golden Cross 50/200 S&P 500:** QuantifiedStrategies: 79 % WR, DD 33 % vs. 56 % B&H, risk-adjusted besser [^48^] vs. tosindicators 20-Jahres-Test: Whipsaws in Seitwärtsphasen, nur mit Trendfilter brauchbar [^49^] vs. akademische Literatur: MA-Profite nach 1990 weitgehend verschwunden [^2^]. Einordnung: Golden Cross = Drawdown-Reduktions-Tool, kein Alpha-Generator.
6. **RSI-Mean-Reversion Forex:** Connors-Erfolge auf Equities [^17^] vs. TradingHeroes 28-FX-Paare-Test: gemischt, paar-spezifisch [^19^] vs. CoinQuant ETH durchgehend negativ [^7^]. ⇒ Mean-Reversion ist primär ein **Equity-Index-Phänomen** (intraday Overreaction + struktureller Long-Drift), auf Forex nicht übertragbar ohne Weiteres.
7. **Kommerzielle vs. unabhängige Claims London-Breakout:** fortraders-Landscape-Claim (50–60 % WR, 2,5:1 RR) wird von unabhängigen Backtests **nicht bestätigt** (EURUSD flat/negativ [^26^][^27^]; ORB ETH PF 0.65 [^30^]); kommerzielle Seiten selbst warnen vor Overfitting [^28^].

---

## Recommended Deep-Dive Areas

1. **XAUUSD H4/D1 Trend-Pullback mit DI-Crossover- oder Donchian-Trigger + 25/350-EMA- bzw. SMA200-Bias-Filter** — beste Quellen-Lage für Gold (CTA-Beleg [^8^], ADX-Studie [^11^], H4>H1-Beleg [^34^], ehrlicher Open-Source-EA als Code-Referenz [^39^]). Zu prüfen: PF > 1.5 mit 0,5 %-Risiko unter Prop-DD-Regeln erreichbar? Donchian-Time-Exit (80 Bars) als Alternative testen [^10^].
2. **VWAP-Pullback NAS100/QQQ, M5, nur 9:45–11:30 ET** — beste dokumentierte Intraday-Edge (PF 2.08) [^13^]; Deep-Dive: Übertragbarkeit QQQ→NAS100-CFD/MT5 (VWAP-Berechnung mit Tick-Volumen!), Short-Seiten-Filter, August-2024-Verlustserien-Robustheit.
3. **Supertrend H4+ auf XAUUSD (ATR 10/×3) mit Walk-Forward statt Grid-Optimierung** [^6^][^31^][^32^] — OOS-Disziplin nach Bajgrowicz/Scaillet-Logik [^1^].
4. **Regime-Switch-Layer:** Trend-Modul (Donchian/Supertrend) vs. Mean-Reversion-Modul (RSI(2)) adaptiv schalten — DFRD-Studie legt nahe, dass Regeln nur kurze Persistenz haben [^43^]; ADX als Regime-Detektor trotz schwacher Filter-Evidenz testen (als Switch, nicht als Entry-Filter) [^11^].
5. **Explizit ausschließen / als Negativ-Benchmark dokumentieren:** Grid/Martingale [^35^][^36^], reine M5–M30-Indikator-Crosses [^5^][^6^], ungefilterter London-Breakout auf EURUSD [^26^][^27^], standalone MACD [^20^], standalone 20-EMA [^23^].
6. **Kosten- und DD-Realismus:** Alle vielversprechenden Kandidaten mit Spread-Widening (XAUUSD News 5–15 Pips [^39^]), Kommission, Slippage und EOD-DD-Simulation nachrechnen; Balance-DD vs. Equity-DD unterscheiden (MDPI-Lektion [^35^]).

---

## Quellen

[^1^]: thefinsense.io – "Does the Bollinger Squeeze Work?" (Zusammenfassung Sullivan/Timmermann/White 1999, Bajgrowicz & Scaillet 2012, Hsu & Kuan 2005), 19.05.2026, https://thefinsense.io/bollinger-band-squeeze/
[^2^]: ScienceDirect – "How exactly do markets adapt? Evidence from the moving average rule in three developed markets", 01.09.2015, https://www.sciencedirect.com/science/article/pii/S1042443115000724
[^3^]: St. Louis Fed – Neely/Weller/Dittmar, "Is Technical Analysis in the Foreign Exchange Market Profitable? A Genetic Programming Approach" (JFQA 1997), https://files.stlouisfed.org/files/htdocs/econ/cneely/genetic/genetic.pdf
[^4^]: CERGE Dissertation (Štefko), Zitat Neely & Weller (2003): Intraday-FX-Regeln schlagen den Markt nicht, https://www.cerge.cuni.cz/pdf/dissertations/Dissertation_Final_Stefko_Peter.pdf
[^5^]: CoinQuant – BTC EMA-Cross Backtests über Timeframes (5M–1W), 13.07.2026, https://www.coinquant.ai/strategies/btc-ema-1h-backtest (u.a. /5m, /30m, /4h, /1d, /1w)
[^6^]: CoinQuant – BTC Supertrend Backtests über Timeframes (1M–1D), 22.07.2026, https://www.coinquant.ai/strategies/btc-supertrend-1d-backtest (u.a. /5m, /15m, /30m, /4h, /12h)
[^7^]: CoinQuant – ETH RSI Mean Reversion Backtests (5M–1D), 14.07.2026, https://www.coinquant.ai/strategies/eth-mean-reversion-30m-backtest (u.a. /5m, /15m, /4h, /8h, /1d)
[^8^]: Ai For Alpha – "A Long-Term Perspective on CTA Trend-Following Performance" (SG CTA Trend Index 2022–2025), Stand 22.05.2025, https://aiforalpha.com/dist/img/Spotlight_CTA_Trend_Followers.pdf
[^9^]: QuantifiedStrategies – "Turtle Trading Strategy: Richard Dennis Rules, Statistics, and Backtests" (Faith-CAGRs; OOS 2007–2022; Barclay CTA/Lynx-Tabelle), 14.04.2025, https://www.quantifiedstrategies.com/turtle-trading-strategy/
[^10^]: Alchemy Markets – "Turtle Trading Complete Guide" (Donchian Time Exit 80 Tage; 25/350-EMA-Filter; Faith-Systemdetails), 16.03.2026, https://alchemymarkets.com/education/strategies/turtle-trading-guide/
[^11^]: quant-signals.com – "ADX Trading Strategy: How to Filter Weak Trends (Backtest Data)" (4.236 Trades, 24 Varianten, XAUUSD/NAS100/Forex), 04.04.2026, https://quant-signals.com/adx-trading-strategy/
[^12^]: CoinQuant Blog – "ADX + RSI Strategy on Bitcoin: Filtering Noise with Backtest Data", 22.07.2026, https://www.coinquant.ai/blog/adx-rsi-strategy-on-bitcoin-filtering-noise-with-backtest-data
[^13^]: PineGen.ai – "We Tested the VWAP Pullback Strategy on QQQ, 18 Months of Backtest Data", 08.07.2026, https://www.pinegen.ai/resources/pine-script-user-case-studies/vwap-pullback-strategy-qqq-backtest
[^14^]: quantbuffet.com – "VWAP as Precise Trend-Following Indicator for Day-Traders" (QQQ/TQQQ 2018–2023), 17.04.2024/21.12.2024, https://quantbuffet.com/2024/04/17/volume-weighted-average-price-vwap-as-precise-trend-following-indicator-for-day-traders/
[^15^]: CoinQuant – BTC VWAP-Crossover Backtests (1M/10M/1H), 10.08.2026, https://www.coinquant.ai/strategies/btc-vwap-1h-backtest
[^16^]: PineScriptForge – "VWAP Deviation Backtest (NQ/5Y-Note-Futures)", 19.07.2024, https://pinescriptforge.com/zf/vwap-deviation/backtest/conservative
[^17^]: QuantifiedStrategies – "RSI 2 Strategy: Complete Guide to Larry Connors' 2-Period RSI Trading Rules", 01.03.2026, https://www.quantifiedstrategies.com/rsi-2-strategy/
[^18^]: QuantifiedStrategies – "RSI Mean Reversion Trading Strategy (QQQ, Nasdaq)", 17.07.2024, https://www.quantifiedstrategies.com/rsi-mean-reversion-trading-strategy/
[^19^]: TradingHeroes – "Connors RSI 2 in Forex: Complete Backtesting Report" (28 Währungspaare), 18.04.2024, https://www.tradingheroes.com/connors-rsi-forex/
[^20^]: arXiv 2206.12282 – "A comparative study of the MACD-based trading strategies" (Dow/Nasdaq/S&P 2015–2021), 2022, https://arxiv.org/pdf/2206.12282
[^21^]: QuantifiedStrategies – "MACD and Bollinger Bands Strategy (78% Win Rate, SMH)", 14.05.2026, https://www.quantifiedstrategies.com/macd-and-bollinger-bands-strategy/
[^22^]: Trader-Dale – "The Real Problem With EMA 20 Revealed" (EUR/USD 138 Trades; VWAP-Fix), 14.04.2026, https://www.trader-dale.com/the-real-problem-with-ema-20-revealed-watch-this-before-it-destroys-your-next-trade-20th-nov-25/
[^23^]: QuantifiedStrategies – "20 EMA Trading Strategy – Does It Work?", 18.02.2025, https://www.quantifiedstrategies.com/20-ema-trading-strategy/
[^24^]: QuantifiedStrategies – "Pullback Trading Strategies: Setup and Backtest Analysis", 12.08.2024, https://www.quantifiedstrategies.com/pullback-trading-strategy/
[^25^]: FakeTrades – "9-20 EMA Strategy" Auto-Backtest (159 Large/Mid Caps, 6.590 Trades, echte Kosten), 06.07.2026, https://app.faketrades.in/s/9-20-ema-strategy-move
[^26^]: GitHub MHZardary – "london-strategy-backtest" (EURUSD/GBPUSD/GBPJPY, 2024/25, M15), 21.07.2025, https://github.com/MHZardary/london-strategy-backtest
[^27^]: QuantifiedStrategies – "London Breakout Strategy: Rules and Backtest Performance", 27.01.2026, https://www.quantifiedstrategies.com/london-breakout-strategies/
[^28^]: NewYorkCityServers – "London Breakout Strategy: How to Trade the Session Open" (Benchmark-Metriken + Overfitting-Warnung), 14.02.2026, https://newyorkcityservers.com/blog/london-breakout-strategy
[^29^]: TradingGambits – "London Session Breakout Strategy" (simulierter 24-Monats-Backtest, H1-50-EMA-Filter), 01.05.2026, https://tradinggambits.com/strategies/london-session-breakout
[^30^]: Secuora – "Opening Range Breakout (ORB) Strategy Backtest" (ETH 5M, 417 Trades), 12.06.2026, https://secuora.net/strategy/opening-range-breakout
[^31^]: arXiv 2405.14262 – "Optimising Supertrend Parameters using Bayesian Optimisation", 23.05.2024, https://arxiv.org/html/2405.14262v1
[^32^]: Headway – "What is the Most Accurate MT4 Indicator for Trading Gold Profitably?" (Supertrend-Settings XAUUSD je TF), 24.03.2026, https://hw.online/faq/best-mt4-indicator-for-gold-trading/
[^33^]: Pro-Scalper – "SuperTrend Indicator on XAUUSD" (Multi-TF-Alignment H4/H1/M15), 16.05.2026, https://pro-scalper.com/indicators/supertrend-gold
[^34^]: EJEB Journal – EA-Studie XAU/USD (Bollinger+ADX, Oscar's Grind; H4 > H1 in Backtest und Realtime), https://jurnal.larisma.or.id/index.php/EJEB/article/download/1266/946
[^35^]: MDPI Algorithms 19(6):442 – "ML-Augmented High-Frequency Grid Trading: ... Drawdown Dichotomy Quantification" (MBD 13,98 % vs. MED 79,97 %), 01.06.2026, https://www.mdpi.com/1999-4893/19/6/442
[^36^]: GamblingCalc – "Martingale Strategy Simulator – Risk of Ruin", 25.02.2026, https://gamblingcalc.com/casino/martingale-simulator/
[^37^]: The Nomad Trader – "MT5 Robots" (Vermarktung "No Martingale/No Grid"; Beispiel verzerrter Backtest-Claims), 07.03.2026, https://nomadforexrobots.com/mt5-robots-2/
[^38^]: UIN Malang Thesis – EMA-RSI-Martingale-EA XAUUSD Forward-Test (PF 1.41, Backtest-DD 53,7 %), http://etheses.uin-malang.ac.id/82829/2/220605110116.pdf
[^39^]: GitHub maker-tung – "xauusd-trend-follow" (MQL5, ATR-Risk, FTMO-Circuit-Breaker, 4-Jahres-Backtest, ehrliche Limitationen), 26.05.2026, https://github.com/maker-tung/xauusd-trend-follow
[^40^]: ECU Thesis (Bunten) – "The Moving Average: Profitability of the 50-/200-Day MA Rule in Different Market Conditions", 29.06.2021, https://thescholarship.ecu.edu/items/7d2cd2e5-3ad8-4129-8640-1d427e30e69b
[^41^]: ForexFactory-Anhang (PowerStocks, JSE) – Faith-Filter (40d>200d MA) hebt WR 68→76 %, Gain/Loss 8:1→25:1, https://www.forexfactory.com/attachment/file/1905753?d=1460639591
[^42^]: StrategyVerdict – "VWAP Trend Pullback" (BTC 4H, fixer 2×ATR-Stop vs. Trailing PF 0.76; OOS 3/5 positiv), 24.07.2026, https://strategyverdict.com/tag/trend-following/
[^43^]: arXiv 1811.06766 – "Technical Analysis and Discrete False Discovery Rate" (kurze Persistenz von TA-Profitabilität), 2018, https://arxiv.org/pdf/1811.06766
[^44^]: Quantica Capital – "Negative Crisis Beta and the Hidden Market Timing Ability of Trend-Following CTAs" (SG Trend Index Q1 2024 +12,2 %), Q2 2024, https://quantica-capital.com/publications/pdf/2024Q2_QuanticaQuarterlyInsights.pdf
[^45^]: RMEEF – "The Predictive Ability and Profitability of Moving Average Rules in the Saudi Stock Market", 27.11.2023, https://oamonitor.ireland.openaire.eu/national/search/publication?pid=10.1515%2Frmeef-2024-0014
[^46^]: Claremont McKenna Thesis – "Finding Profitability of Technical Trading Rules in Emerging Markets", https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=1381&context=cmc_theses
[^47^]: UvT Thesis – "Profitability of Technical Trading Strategies" (STOXX Europe 600: MA ohne Alpha, BB kurzfristig am besten), https://arno.uvt.nl/show.cgi?fid=136773
[^48^]: QuantifiedStrategies – "Golden Cross Trading Strategy" (S&P 500 seit 1960: 79 % WR, DD 33 % vs. 56 %), 21.02.2026, https://www.quantifiedstrategies.com/golden-cross-strategy/
[^49^]: TOS Indicators – "Golden Cross Strategy: 20-Year S&P 500 Backtest" (Whipsaws, Trendfilter nötig), 12.09.2023, https://tosindicators.com/research/golden-cross-trading-strategy-20-year-backtest-results
[^50^]: St. Louis Fed WP 1999-016 – "Intraday Technical Trading in the Foreign Exchange Market" (Neely u.a.), https://files.stlouisfed.org/files/htdocs/wp/1999/99-016.pdf
