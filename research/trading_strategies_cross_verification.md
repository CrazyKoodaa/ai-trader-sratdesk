# Cross-Verifikation — Trading-Strategien-Recherche (Stand 2026-09-03)

Basis: 6 Wide-Reports (wide01–06) + 12 Deep-Dives (dim01–12) unter /mnt/agents/output/research/

## Tier 1 — High Confidence (≥2 unabhängige Agenten, konsistente Quellen)

1. **News-Avoidance ist Pflicht-Meta-Filter.** News-nahe Trades −0.10R vs. +0.35R ruhig (wide04); FTMO ±2 min hard auf Funded inkl. SL/TP-Trigger-Breach, FundingPips Zero ±10 min (dim07); fortraders/blueguardian Prop-Guides (wide06). Konsistent über dim04/dim07/wide04.
2. **Klassische Indikator-Signale auf M5–M30 sind nach Kosten toxisch; H4/D1 ist der Arbeitsbereich** (wide03: EMA-Cross BTC M5 PF 0.56, Supertrend M5 PF 0.70 vs. D1 PF 1.51; dim01: MT5-Studie H4 > H1 auf Gold; dim10: einzige Ausnahme = gefilterte MR auf H1).
3. **Ungefilterte mechanische SMC-Signale haben keinen Edge** (wide02: Secuora PF 0.34–0.50; dim03: Secuora Silver-Bullet PF 0.14/0.08; dim04: ungefilterte FVG-Mechanik PF 0.43, n=2.232). Konfluenz-Filter sind die Edge (dim04: Breaker-Kette PF 1.62–1.74, Vendor).
4. **XAUUSD = trend-freundlichster Markt, Session 07–17 UTC entscheidend** (wide03: SG-Trend-CTA, ADX-DI-Cross D1 PF 1.54; dim01: Session-Sensitivität 3.5×, Overlap 83 Pips/h; wide06: XAUUSD #1-Prop-Instrument).
5. **Grid/Martingale kategorisch prop-untauglich** (wide03: MDPI 2026, Balance-DD 14 % vs. Equity-DD 80 %; dim06/dim11: EOD-DD-Regeln unvereinbar).
6. **Zeitzonen-/DST-Handling ist Tag-1-Architekturpflicht** (dim02, dim03, dim04, dim11, dim12 — fünf Agenten unabhängig: Serverzeit meist EET/EEST, US/EU-DST-Asynchronwochen 8.–29.03. und 25.10.–01.11.2026, Sessions via zoneinfo in NY/London-Zeit definieren).
7. **Slippage-Stressmatrix ist Pflicht** (wide01: DAX-ORB PF 1.25→0.96 bei 3 Pts; dim11: PF(2×Kosten) ≥ 1.2 als Hard-Gate; dim05: Trade-Desk-Backtest ohne Slippage-Modell).
8. **ML als Filter > ML als Signal** (wide05; dim09: daru.finance 38/42 PF-Verbesserung als Filter, 0/42 auf edge-losem Primary; dim08: HMM-DD-Reduktion robust, Return-Boost fragil).
9. **n ≥ 300 Trades Mindeststichprobe für jede OOS-Aussage** (wide02, dim09, dim11 konsistent).

## Tier 2 — Medium Confidence (1 Agent, plausible/autoritative Quelle)

1. VWAP-Pullback NAS100 9:45–11:30 ET: PF 2.08/WR 62.4 %/312 Trades (dim02) — Vendor-Quelle (PineGen.ai), keine unabhängige Replikation; Regelwerk vollständig extrahiert, bullenmarkt-lastige Testperiode.
2. London-Breakout USDJPY PF 1.25/+0.14R/227 Trades (dim05) — eigene Signifikanzrechnung des Agenten: t≈1.7, überlebt keine Multi-Paar-Korrektur → Hypothese.
3. Filtered MR RSI XAUUSD PF 3.00 / EURUSD PF 2.00 (dim10) — ABER nur ~10 Trades/Asset, kostenfrei → Hypothese; Multi-Instrument-Pflicht wegen ~1 Signal/2.5 Monate.
4. COT als Wochen-Bias-Filter (+0.2–0.4 PF-Hoffnung) (dim06) — Standalone negativ belegt (Dealer-Folge 2014–2021 verlustreich).
5. Meta-Labeling-Erwartung +0.1–0.3 PF auf profitablem Primary (dim09) — daru.finance, vercostet, DSR-gated.
6. HMM-Regime-Filter DD-Reduktion 56→24 % (dim08) — QuantStart, SPY; XAUUSD-Direktbeleg marginal (PF 1.34→1.42) mit Lookahead-Caveat.

## Tier 3 — Low Confidence / Exploratory

1. Silver-Bullet-Vendor-Claims (PF 2.03 MNQ, PF 1.82 XAUUSD, "70–80 % WR") — unauditiertes Marketing, teils intern widersprüchlich (wide01, dim03).
2. fortraders-Breakout-Retest-Claim (50–60 % WR, 2.5:1) — 0 unabhängige Treffer (dim05).
3. Reddit-ORB-Backtests (BTC/GBPUSD positiv) — nicht verifizierbar (wide01).
4. FTMO-1-Step-Funded-News-Regel — Sekundärquellen-Konflikt, Primär-FAQ hat Vorrang (dim07).

## Conflict Zones (dokumentiert, nicht geglättet)

| Konflikt | Seite A | Seite B | Auflösung/Handling |
|---|---|---|---|
| ORB profitabel? | Zarattini/Aziz Sharpe 2.4–2.81 (Stocks in Play, gehebelt) | paperswithbacktest SPY/QQQ/IWM −1.8 bps; SPY PF 0.96 (3.340 Trades) | Edge sitzt im Selektions-/Regime-Filter, nicht im Breakout. ORB nur mit Filtern testen. |
| ADX-Filter | Lehrbuch: ADX>25 filtert Chop | dim01: ADX als Filter zerstört Edge (XAUUSD PF 1.54→0.40); dim10: ADX<25 als MR-Gate belegt | ADX nur als Regime-Gate in Richtung der Studien-Logik verwenden, nie generisch. |
| Silver-Bullet-Fenster | ICT kanonisch 10–11 NY | sarahleesoffice-Backtest: 10–11 = SCHWÄCHSTES Fenster (PF 1.32), 8:30–9:10 PF 3.16 (NQ-Proxy) | Beide Fenster im WFO testen; kein Vendor-Blindglaube. |
| Trendfolge lebt? | SG-Trend: Gold profitabel seit 2023 | Turtle OOS 2007–2022 kollabiert (CAGR 2–10 %) | Instrumentenabhängig: Gold/Indizes ja, diversifizierte FX-Turtle nein. |
| COT | "profitabel außer AUDUSD" (Legacy ~2004–2012) | 2014–2021 Dealer-Folge −3.100 $; NY Fed: keine Prognosekraft | Nur als Bias-Filter, nie Standalone. |
| LLM-Sentiment | Lopez-Lira/Tang Sharpe 3.8 | Replikation IC≈0; "Time Machine GPT"-Leakage | Nicht für Top-5; höchstens News-Blocker. |
| Chronos/TSFM | Marketing: Zero-Shot-Forecasting | arxiv 2507.07296: schlägt naive Benchmark nicht; Alpha-Decay dokumentiert | Kein TSFM-Entry-Signal; TTM höchstens Vol-Sizing. |

## Entscheidender Meta-Befund
daru.finance-Replikation (92.500 reale Strategien): bester Deflated Sharpe 0.03 → **jede Strategie muss die dim11-Validierungspipeline (WFA, DSR ≥ 0.95, PBO < 0.10, MC-DD, Prop-Sim) durchlaufen, bevor sie als "PF > 1.5"-Kandidat gilt.** PF>3/WR>70 %/Sharpe>3 im Backtest = Red Flag, nicht Erfolg.

## Phase 5 — Targeted Validation
Keine separaten Validierungs-Agenten nötig: Alle Conflict Zones sind entweder durch Primärquellen-Hierarchie aufgelöst (Vendor < unabhängiger Backtest < peer-reviewed) oder als Design-Constraints in die Implementierung überführt (DST, Slippage, News-Filter). Der einzige offene Punkt — Identität des User-Pakets "pymt5trade" (PyPI 404; vermutlich offizielles MetaTrader5-Paket oder mt5pytrader, dim12) — wird dem User als Rückfrage im Implementierungs-Stage gestellt bzw. durch Connector-Abstraktion entschärft.
