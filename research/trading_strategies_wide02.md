# Facet: Smart Money / Price Action (SMC, ICT, Wyckoff, klassische Candlestick-PA)

Recherche-Datum: 2026-06 (Datum der KI-Sitzung); 30+ unabhängige Websuchen (EN + DE).
Zielkontext: Top-5-Strategien für Python-Bots auf MT5 (XAUUSD, NAS100, Forex), PF > 1.5, RR ≥ 1:2, Prop-Firm-tauglich, **deterministisch formalisierbar**.

---

## Key Findings

### 1) Formalisierbarkeit: Ja, mit Einschränkungen — und das ist der Knackpunkt

SMC-Kernbausteine sind im Prinzip deterministisch kodierbar, und es existieren mehrere Open-Source-Implementierungen:

- **`smartmoneyconcepts` (Python, joshyattridge)** — ~2.000 Stars / ~850 Forks, das Referenz-Paket: `smc.fvg()`, `smc.swing_tops_bottoms(swing_length)`, `smc.bos_choch(close_break=True)`, `smc.ob()`, `smc.vob()` (Volumized Order Blocks), `smc.liquidity()` (Equal Highs/Lows). Input: OHLC(V)-DataFrame. [^1^]
- **`smart-money-concept` (PyPI, v0.1.3)** — BOS/CHoCH, OB, FVG mit Mitigation-Logik, EQH/EQL, Premium/Discount-Zonen, yfinance-Daten. [^2^]
- **MQL5/Pine:** GitHub-Topic "order-block" listet u. a. einen freien MT5-EA für XAUUSD (FVG+OB, quality-scored, behauptete 45 % WR, +48,7 % im 6-Monats-Backtest), ein MT5-SMC-Indicator-Repo (Liquidity, OB, BOS) und einen französischen Multi-TF-Crypto-Analyzer mit **deterministischer Setup-Generierung, Paper-Trading-Engine und 206 Unit-Tests** (Python/FastAPI). [^3^]
- **Pine Script:** SM Radar (CedInvest) — Open-Source-Detektion von OB, FVG, BSL/SSL, BOS/CHoCH; explizit **ohne** Signale/Backtest-Versprechen. [^4^]

**Aber:** Die Parameter sind frei wählbar (Swing-Länge, OB-Definition, Equal-Highs-Toleranz), und unterschiedliche Implementierungen liefern unterschiedliche Zonen. LuxAlgo selbst räumt ein: Es gibt keine feste Toleranz für Equal Highs ("a few ticks or pips … or a small fraction of ATR"), und Sweeps haben keine feste Distanz. [^5^] Backtrex (No-Code-Backtester mit nativen ICT-Signalen) beschreibt die Kodierung diskretionärer ICT-Kontexte (HTF-Struktur, Session, FVG-Konfluenz) als "genuinely difficult" ohne Look-ahead-Bias. [^6^]

**Konkret formalisierbare Regeln (aus den Quellen extrahiert, bot-tauglich):**
- FVG: 3-Kerzen-Imbalance (Bar A High < Bar C Low bullisch, invers bearisch); Mindestgröße relativ zu ATR; **Anti-Repainting: erst nach Close der 3. Kerze, close[1] verwenden**. [^7^]
- Order Block: letzte Gegen-Kerze vor Impuls > X % mit BOS/CHoCH-Bestätigung + FVG in den folgenden N Kerzen; Entry 50 % des Body, Stop hinter OB-Extrem. [^6^]
- Breaker Block: OB, dessen gesamter Body gegenläufig durchlaufen wurde, mit BOS/CHoCH; Entry beim Return (30–100 % Pullback), Stop 5 Pips hinter Zonen-Extrem, Ziele 1:2/1:3. [^8^]
- Liquidity Sweep: Wick bricht Equal Highs/Lows (Toleranz: 10–20 Pips FX-Majors, 1–5 $ Gold laut Quantum Algo) oder Session-H/L, gefolgt von CHoCH/MSS auf LTF; Stop hinter Sweep-Wick → RR 3:1–5:1 möglich. [^9^][^10^]
- Silver Bullet: rein zeitbasiert (03–04, 10–11, 14–15 Uhr ET), Sweep + MSS + FVG-Retracement, 2R-Ziel — **am einfachsten automatisierbar**, weil Session-Filter deterministisch. [^11^]

### 2) Dokumentierte Backtest-Ergebnisse (mit Quelle und Qualitätsurteil)

| Strategie | Ergebnis | Quelle / Qualität |
|---|---|---|
| **FVG-Retracement, mechanisch, ungefiltert** (BTC/ETH 5m, 12 Mon., 2.232 Trades, Kosten inkl.) | **PF 0,34–0,50, WR 27–32 %, Net P&L −95 bis −99 % → KEIN Edge** | Secuora, deterministischer Runner, volle Regelpublikation — hohe methodische Transparenz [^7^] |
| **ICT Silver Bullet, mechanisch** (BTC/ETH, 12 Mon.) | Strikte Same-Candle-Lesart: zu wenige Trades für Win-Rate; "Treat any quoted Silver Bullet win rate without a published rule set as marketing" | Secuora [^11^] |
| **ICT, mechanisch vs. AI-diskretionär** (EURUSD M15, Killzones, 2 Monate) | Mechanisch: **WR 29,6 % (unprofitabel)**. AI-diskretionär ("Michael", anonymisierte Charts, kein Lookahead): WR 40,4 %, **PF 1,99**, +83 % auf 10k, aber nur **n=47** Trades; Profit kam aus Payoff-Asymmetrie (Ø +2,93R) und Ablehnung von 92 % der Setups. Open Source (ict-tools + DTSB-Engine, MT5) | OffbeatForex — replizierbar, aber kleine Stichprobe [^12^] |
| **Breaker Block (BOS + FVG + Return)** | EURUSD 2022–24: WR 54 %, PF 1,62, n=87, Ø RR 1:2,1; NAS100: WR 57 %, PF 1,74, n=64, Ø RR 1:2,3. **Ohne FVG-Konfluenz fällt PF < 1,2** | Backtrex (Vendor, verkauft Backtest-Tool → Interessenkonflikt) [^8^] |
| **ICT-Bachelorarbeit (HAW Hamburg)** — algorithmischer Nachbau der ICT-Konzepte, ~20 Jahre Backtest, mehrere Märkte | Algorithmus langfristig profitabel, **aber: kein einziges ICT-Konzept zeigte Prognosefähigkeit über herkömmliche Methoden hinaus**; "die Aussagen, die ICT über den Markt trifft, [sind] als ziemlich unwahrscheinlich anzusehen". Verbesserungen kamen nur aus Trade-Management-Modifikationen, nicht aus den Konzepten | Bachelorarbeit J. Steinkamp, HAW Hamburg — **einzige akademische Arbeit, zentrale Quelle** [^13^] |
| **Wyckoff Spring/Upthrust, mechanisch** (PineScriptForge, $4,50 RT + 1 Tick Slippage) | Extrem instrumentenabhängig: MNQ Spring PF 2,21 (WR 57 %, n=342); PL Upthrust PF 2,43 (n=418); aber 6J Spring PF 0,81, CT Spring PF 0,77, ALI Upthrust PF 0,66 (DD 85 %) | PineScriptForge — **geringe Glaubwürdigkeit**: auto-generierte Seiten, interne Zahlenwidersprüche auf derselben Seite, Affiliate-Links [^14^][^15^] |
| **ICT Silver Bullet / Breaker Block (PineScriptForge)** | Silver Bullet MNQ: PF 2,03, WR 47,1 %, n=646; Breaker 6B: PF 1,75, WR 50,9 %, n=646; 6J: PF 1,90 | Ebenfalls PineScriptForge — als ungeprüfte Marketing-Datenpunkte werten [^16^] |
| **Bearish Engulfing (Klassik-PA)** | QuantifiedStrategies (Aktien, 25 J., als Mean-Reversion-Long gehandelt): 274 Trades, Ø +0,57 %/Trade, **PF 2,7**, MaxDD ~16 %. Youpattern (Krypto, n=892): 61,8 % "Erfolg", mit 3 Filtern (Trend + Confirmation + Volumen) 77,7 % bei n=160 — aber kein PF/Expectancy publiziert | [^17^][^18^] |
| **Candlestick-Patterns akademisch** | Marshall/Young/Rose (2006, DJIA): kein Mehrwert; Duvinage/Mazza/Petitjean (2013, 5-Min-DJIA): nichts schlägt B&H nach Kosten; Jönsson (2016, OMXS30): nicht profitabel; Tharavanij et al. (2017, SET50): Pattern-Returns meist nicht von 0 verschieden | Überblickszusammenfassung stick-stocks.com [^19^] |
| **Supply & Demand Zonen** | Sekundär zitierte Studien: TrendSpider 2024 — Zonen mit >3 %-Departure in 5 Kerzen: 68 % Hold-Wahrscheinlichkeit beim ersten Retest; Forex Bee 2024 — Sub-H1-Zonen >60 % Failure vs. 32 % bei H4; PriceActionNinja 2024 — >5 % Departure in 3 Kerzen: 72 % Hold vs. 41 % bei graduellem Departure | GoatFundedTrader-Blog (Prop-Firm-Marketing), Originalstudien nicht verifiziert [^20^] |
| **ATAS (aus Landscape-Scan)** | Regelbasierte SMC-Entries DXY: WR 50–65 %, PF > 1,5 | Konsistent mit Breaker-Block-/Vendor-Daten, Originalquelle nicht erneut gefunden |

### 3) Konsistentes Muster über alle Quellen

1. **Ungefilterte mechanische SMC-Signale haben keinen Edge** (Secuora FVG PF 0,34–0,50; mechanisches ICT WR 29,6 %; akademische Candlestick-Studien).
2. **Filter machen den Unterschied** — dieselben Filter tauchen überall auf: HTF-Trend-/BOS-Alignment, Killzone/Session-Filter, Mindest-Imbalance-Größe, Volumen-Bestätigung, Premium/Discount-Lage, FVG-OB-Konfluenz. Backtrex: ohne FVG-Konfluenz fällt Breaker-PF unter 1,2. Youpattern: 3 Filter heben Engulfing-Erfolg von 61,8 % auf 77,7 %. [^8^][^18^]
3. **Profitabilität kommt aus Asymmetrie, nicht Trefferquote**: WR 40–55 % bei Ø 2–3R (OffbeatForex PF 1,99 bei 40,4 % WR; innercircletrader.net: 55–65 % WR bei 1:3). [^12^][^21^]
4. **Zeitfilter sind der am einfachsten automatisierbare und am häufigsten bestätigte Edge-Verstärker** (Silver-Bullet-Fenster, London/NY-Killzones; "trading outside the window" degradiert WR nachhaltig). [^11^][^21^]
5. **Instrumentenabhängigkeit ist massiv**: Selbst unterstellt, PineScriptForge-Zahlen stimmen, oszilliert dieselbe Strategie zwischen PF 0,66 und 2,43 je nach Future. Kein blindes Cross-Asset-Deployment. [^14^][^15^]

### 4) Overfitting- und Bias-Risiken (spezifisch für SMC-Bots)

- **Repainting/Lookahead**: FVG/BOS erst mit close[1] bestätigen; Backtrex nennt das "one of the most damaging backtesting mistakes". [^7^]
- **Subjektivitäts-Spielraum als versteckte Freiheitsgrade**: Swing-Länge, OB-Definition, Sweep-Toleranz, "Displacement > X %", Mitigation-Regeln — jede Wahl ist ein Optimierungsparameter. Walk-Forward + Out-of-Sample Pflicht.
- **Hindsight bei Zonen**: Fundlabz (RTM/Supply-Demand): "Mark zones forward, with the next candle hidden" — Zonen wirken rückblickend offensichtlich; Wick-basierte Stops machen Close-only-Backtests zu optimistisch. [^22^]
- **Kleine Stichproben**: OffbeatForex PF 1,99 bei n=47/2 Monate ist nicht belastbar; Backtrex n=64–87 ebenfalls grenzwertig. Forderung: ≥ 100–300 Trades, mehrere Regime.
- **Backtest≠Live**: Financial-Hacker/Zorro: PF-1,5-Backtests können reine Zufallsprodukte sein; Slippage/Spread-Sensitivität gerade bei engen SMC-Stops (5 Pips hinter Zone) hoch. FXGlory-Sensitivitätstest zeigt: Spread+Slippage drücken PF einer Reversal-Strategie von 0,71 auf 0,54. [^23^][^24^]

---

## Major Players & Sources

- **Michael J. Huddleston (ICT)** — Urquelle (Silver Bullet, Killzones, MSS, OTE); Community-Lehre, keine Peer-Review. [^21^]
- **LuxAlgo** — ICT Concepts Indicator (25.600 Likes auf TradingView), AI-Backtesting-Assistant; gleichzeitig Quelle des Landscape-Zweifels ("no rigorous public study"). [^25^]
- **Backtrex** — No-Code-ICT-Backtester mit nativen OB/FVG/BOS-Sweeps und Pine-Export; publiziert konkrete Backtest-Zahlen (Vendor-Bias!). [^6^][^8^]
- **Secuora** — deterministische Open-Rule-Backtests mit **negativen** Ergebnissen (FVG, Silver Bullet); methodisch transparenteste Quelle. [^7^][^11^]
- **OffbeatForex** — mechanisch-vs-AI-ICT-Experiment mit Open-Source-Toolchain (ict-tools, DTSB, MT5). [^12^]
- **joshyattridge/smartmoneyconcepts** — De-facto-Standard-Python-Bibliothek für SMC-Detektion. [^1^]
- **HAW Hamburg (Steinkamp, Bachelorarbeit)** — einzige gefundene akademische Prüfung von ICT: Konzepte ohne nachweisbare Prognosefähigkeit. [^13^]
- **PineScriptForge** — große Backtest-Datenbank (u. a. Wyckoff, Silver Bullet, Breaker), aber auto-generiert, intern inkonsistent, Affiliate-monetarisiert → nur als Hypothesen-Generator. [^14^][^16^]
- **QuantifiedStrategies / Youpattern** — klassische Candlestick-Backtests (Engulfing). [^17^][^18^]
- **Trading.de** — deutschsprachige SMC-Einführung; nennt als Nachteile u. a. ungeeignet für sehr kurzfristiges Scalping und Fehlinterpretationsrisiko. [^26^]

---

## Trends & Signals

- **Industrialisierung von SMC**: 2025/26 entstehen No-Code-Backtester mit nativen ICT-Primitiven (Backtrex, TradeZella Plain-English-Engine, LuxAlgo AI), dazu wachsende GitHub-Landschaft (Python-Pakete, MT5-EAs, sogar XAUUSD-spezifische Open-Source-EAs mit FVG+OB-Scoring). → Die Formalisierungsfrage ist gelöst; die Edge-Frage nicht. [^1^][^3^][^27^]
- **Hybrid-Signal**: Die derzeit glaubwürdigsten positiven Resultate entstehen nicht durch reine Mechanik, sondern durch Mechanik + Selektion (AI-diskretionär bei OffbeatForex; hart gefilterte Setups bei Backtrex). Für einen Python-Bot heißt das: strenge Konfluenz-Filter (HTF-BOS + Sweep + FVG + Session) statt Signal-Sprühen. [^12^][^8^]
- **Session-/Zeit-basierte Modelle (Silver Bullet, Killzones)** sind der stärkste automatisierbare SMC-Teil, weil der Zeitfilter deterministisch ist und die Setup-Rate begrenzt (Overfitting-resistenter, prop-firm-freundlich niedrige Trade-Frequenz). [^11^][^21^]
- **Prop-Firm-Kompatibilität als Verkaufsargument**: PineScriptForge auditiert explizit gegen Tradeify-Limits (Trailing DD, Daily Loss) — zeigt, dass Drawdown-Profil (nicht PF) der Prop-Firm-Engpass ist; mehrere "PASS"-Strategien scheitern am Daily-Loss-Limit. [^16^]
- **Kritik-Signal**: Akademische Arbeit (HAW) + Secuora-Negativtests + akademische Candlestick-Literatur zeigen in dieselbe Richtung: Nackte, ungefilterte SMC/PA-Muster ≈ kein Edge. Der Markt konsolidiert sich auf "Konfluenz + Kontext + Risk-Asymmetrie". [^13^][^7^][^19^]

---

## Controversies & Conflicting Claims

1. **"70–80 % Win-Rate" Silver Bullet** (LuxAlgo-Blog, howtotrade) vs. **Secuora**: strikte mechanische Lesart produziert zu wenige Trades; jede Win-Rate ohne publiziertes Regelset = "marketing". Innercircletrader.net selbst nennt realistischere 55–65 % bei 1:3. [^25^][^11^][^21^]
2. **Akademisch vs. Vendor**: HAW-Bachelorarbeit — kein ICT-Konzept mit Prognosekraft über Standardmethoden hinaus — vs. Backtrex/PineScriptForge mit PF 1,6–2,4. Auflösung wahrscheinlich: Vendoren selektieren Instrument/Zeitraum/Filter (Survivorship im Reporting); die HAW-Arbeit testete konzeptgetreu ohne Execution-Tricks und fand den Nutzen nur im Trade-Management. [^13^][^8^]
3. **Mechanisch vs. diskretionär**: OffbeatForex zeigt denselben Playbook-Regelsatz mechanisch unprofitabel (29,6 % WR), mit diskretionärer Selektion profitabel (PF 1,99) — stützt die LuxAlgo-These, dass SMC "on its own" nicht profitabel ist; widerspricht der Bot-Machbarkeit, *es sei denn*, die Selektion wird in harte Filter gegossen. [^12^]
4. **PineScriptForge interne Inkonsistenzen**: Auf denselben Seiten widersprechen sich Summary-Box und Fließtext (z. B. MYM Silver Bullet: Box PF 1,82/59,8 %, daneben 1,29/42,5 %; "6J NQ Nasdaq futures" für ein Yen-Produkt) — klar auto-generiert, **Zahlen nicht ohne eigene Replikation verwenden**. [^16^]
5. **Supply/Demand-Statistiken** (68–72 % Hold-Rates) stammen aus Sekundärzitaten auf einer Prop-Firm-Marketing-Seite; Originalstudien (TrendSpider, Forex Bee, PriceActionNinja 2024) nicht auffindbar → mit Vorsicht. [^20^]
6. **"Smart Money manipuliert Retail-Stops"** als Erklärungsnarrativ: selbst SMC-freundliche Quellen (howtotrade-PDF) konzedieren fehlende Belege und das Größenargument (Retail-Liquidität für Institutionen unbedeutend). Die Muster können trotzdem als heuristische Struktur-Marker funktionieren — die Kausalgeschichte ist unbewiesen. [^28^]

---

## Recommended Deep-Dive Areas (für Bot-Umsetzung)

1. **Silver Bullet / zeitfensterbasiertes Sweep→MSS→FVG-Modell** — beste Formalisierbarkeit (Zeitfilter deterministisch), eigener NQ-1-Min-Backtest auf GitHub vorhanden; auf XAUUSD/NAS100 mit 2R–3R testen. Priorität HOCH. [^3^][^11^]
2. **Sweep + CHoCH + FVG-Retracement mit voller Konfluenz-Kette** (HTF H4-Bias → EQH/EQL-Sweep (ATR-Fraktions-Toleranz) → M15/M5-CHoCH → 50 %-FVG/OB-Entry, Stop hinter Sweep-Wick) — Replikation auf Basis von `smartmoneyconcepts` (Python) + Backtesting-Framework; Zielmetriken PF > 1,5 bei n ≥ 300, Walk-Forward. [^1^][^9^]
3. **Breaker Block (invalidierter OB) als eigenständiges Setup** — Backtrex-Zahlen (PF 1,62–1,74) replizieren; klare Invalidationslogik ist bot-freundlich; FVG-Konfluenz als Pflichtfilter (ohne: PF < 1,2). [^8^]
4. **Supply/Demand H4/D1 mit Departure-Stärke-Filter** (> x·ATR in ≤ 3 Kerzen, Volumen > 150 % des 20er-Schnitts, nur frische Zonen) — algorithmisch sauber definierbar; Sub-H1-Zonen meiden (60 %+ Failure). [^20^]
5. **Klassisches Engulfing/Pin Bar nur als Bestätigungs-Trigger an SMC-Levels**, nicht als Standalone — akademische Evidenz gegen nackte Patterns, aber QuantifiedStrategies zeigt PF 2,7 im Aktien-Mean-Reversion-Kontext; als Konfluenz-Baustein in XAUUSD/NAS100 testen. [^17^][^19^]
6. **Robustheits-Pflichtprogramm**: Anti-Repainting (close[1]), Spread/Slippage-Stresstest (enge SMC-Stops sind kostensensitiv), Session-Analyse, mindestens 2 Regime, Out-of-Sample; Prop-Firm-Checks auf Daily-Loss/Trailing-DD statt nur PF. [^7^][^24^][^16^]

---

## Quellen

[^1^]: GitHub – joshyattridge/smartmoneyconcepts (Python-Paket, FVG/OB/BOS/CHoCH/Liquidity; ~2k Stars), via https://github.com/joshyattridge & https://pypi.org/project/smartmoneyconcepts/0.0.14/ (abgerufen 2026-06; PyPI-Release 2024-02-23)
[^2^]: PyPI/libraries.io – smart-money-concept 0.1.3, https://libraries.io/pypi/smart-money-concept (2025-09-19)
[^3^]: GitHub Topics – order-block (5 Repos, darunter MT5-XAUUSD-EA "45% WR, +48,7% 6M-Backtest", NQ-1min-Silver-Bullet-Backtest, deterministischer Crypto-Analyzer mit 206 Unit-Tests), https://github.com/topics/order-block (abgerufen 2026-06; Repo-Updates bis 2026-09-03)
[^4^]: GitHub – CedInvest/sm-radar-pine, https://github.com/CedInvest/sm-radar-pine (2026-04-28)
[^5^]: LuxAlgo Library – Equal Highs/Lows as Liquidity, https://www.luxalgo.com/library/concept/equal-highs-lows-as-liquidity/ (o. D.)
[^6^]: Backtrex – ICT Order Block: Identify, Trade and Backtest Without Code, https://backtrex.com/en/blog/ict-order-block-backtest-strategy (2026-05-24)
[^7^]: Secuora – Fair Value Gap (FVG) Strategy Backtest: Stats on Real Data (PF 0,34/0,50; Anti-Repainting-Regel), https://secuora.net/strategy/fvg-strategy (2026-06-12)
[^8^]: Backtrex – ICT Breaker Block Trading Guide (EURUSD PF 1,62/n=87; NAS100 PF 1,74/n=64; ohne FVG PF <1,2), https://backtrex.com/en/blog/ict-breaker-block-trading-guide (2026-07-07)
[^9^]: Backtrex – SMC Trading Setups: 7 Entry Patterns (Sweep+MSS: RR 3:1–5:1), https://backtrex.com/en/blog/smc-trading-setups-entry-guide (2026-08-16)
[^10^]: Quantum Algo – Equal Highs/Equal Lows (Toleranzen: 10–20 Pips FX, 1–5 $ Gold), https://www.quantum-algo.com/glossary/equal-highs-equal-lows/ (2026-04-30)
[^11^]: Secuora – ICT Silver Bullet Backtest Results: 12 Months of Real Data, https://secuora.xyz/strategy/ict-silver-bullet (2026-06-12); Zeitfenster-Definition auch: LuxAlgo, https://www.luxalgo.com/blog/ict-silver-bullet-setup-trading-methods/ (2025-07-18)
[^12^]: OffbeatForex – Is ICT Strategy Profitable? I Backtested It Using AI (mechanisch 29,6 % WR; AI-diskretionär PF 1,99, n=47; Open Source: ict-tools + DTSB auf MT5), https://offbeatforex.com/is-ict-strategy-profitable/ (2026-08-02)
[^13^]: Steinkamp, J. – Bachelorarbeit HAW Hamburg (ICT-Algorithmus, ~20 Jahre Backtest; keine Prognosefähigkeit der ICT-Konzepte über Standardmethoden hinaus), https://schumann.mt.haw-hamburg.de/BachelorArbeitJonSteinkamp.pdf (o. D.)
[^14^]: PineScriptForge – MNQ Wyckoff Spring (PF 2,21) & 6J Wyckoff Spring (PF 0,81), https://pinescriptforge.com/mnq/wyckoff-spring/backtest , https://pinescriptforge.com/6j/wyckoff-spring/backtest (2024-10)
[^15^]: PineScriptForge – ALI Wyckoff Upthrust (PF 0,66) & PL Wyckoff Upthrust (PF 2,43), https://pinescriptforge.com/ali/wyckoff-upthrust/backtest , https://pinescriptforge.com/pl/wyckoff-upthrust/backtest (2024)
[^16^]: PineScriptForge – MNQ ICT Silver Bullet (PF 2,03, n=646), https://pinescriptforge.com/mnq/ict-silver-bullet/backtest (2024-12-24); 6B ICT Breaker Block (PF 1,75), https://pinescriptforge.com/6B/ict-breaker-block/backtest (2024-10-22); interne Inkonsistenzen z. B. MYM, https://pinescriptforge.com/mym/ict-silver-bullet/backtest/conservative
[^17^]: QuantifiedStrategies – Engulfing Candlestick Pattern Backtest (PF 2,7, 274 Trades, Aktien), https://www.quantifiedstrategies.com/engulfing-trading-candlestick-pattern-backtest/ (2026-03-20)
[^18^]: Youpattern – Bearish Engulfing Backtest (61,8 % Basis, 77,7 % mit 3 Filtern, n=892), https://youpattern.com/backtests/bearish-engulfing/ (2026-06-01); ergänzend ChartRead: "raw bullish engulfing is close to a coin flip", https://chartread.ai/blog/bullish-engulfing-win-rate (2026-06-22)
[^19^]: Stick-Stocks – Do Candlestick Patterns Work? What Research Shows (Marshall/Young/Rose 2006; Duvinage et al. 2013; Jönsson 2016; Tharavanij et al. 2017), https://stick-stocks.com/blog/en/do-candlestick-patterns-work (2026-08-06)
[^20^]: Goat Funded Trader – Supply and Demand Trading Strategy (zitiert TrendSpider/Forex Bee/PriceActionNinja 2024), https://www.goatfundedtrader.com/blog/supply-and-demand-trading-strategy (2026-05-07)
[^21^]: InnerCircleTrader.net – ICT Silver Bullet Strategy (55–65 % WR bei 1:3; Automatisierbarkeit eingeschränkt: MSS-Bestätigung schwer kodierbar), https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/ (2026-05-03)
[^22^]: Fundlabz – How to Backtest the RTM Supply and Demand Style (Hindsight-Bias, Wick-Problem), https://www.fundlabz.com/blog/how-to-backtest-rtm-supply-demand-strategy (2026-06-20)
[^23^]: Financial-Hacker/Zorro – When Backtests Meet Reality (PF-1,5-Backtest kann Zufall sein), https://financial-hacker.com/Backtest.pdf (o. D.)
[^24^]: FXGlory – Forex Reversal Strategy Backtest & Slippage-Sensitivität (PF 0,71 → 0,54), https://fxglory.com/learn/forex-strategies/forex-reversal-strategy/ (2026-07-02)
[^25^]: LuxAlgo – ICT Silver Bullet Setup & Trading Methods ("70–80 % win rate"-Claim), https://www.luxalgo.com/blog/ict-silver-bullet-setup-trading-methods/ (2025-07-18); Indicator-Popularität: Lunefi, https://lunefi.com/blog/best-ict-indicators-tradingview-2026... (2026-05-06)
[^26^]: Trading.de – Smart Money Concepts (SMC) Trading Strategie erklärt, https://trading.de/lernen/strategien/smart-money/ (2025-08-21)
[^27^]: TradeZella – How to Backtest an ICT Strategy in Plain English, https://www.tradezella.com/blog/backtest-ict-strategy (2026-07-07)
[^28^]: HowToTrade – Smart Money Concept Trading Strategy PDF (Kritikpunkte: fehlende Evidenz, Retail-Liquidität unbedeutend), https://howtotrade.com/wp-content/uploads/2024/06/Smart-Money-Concept-trading-strategy-PDF.pdf (2024-06)

*Hinweis zur Quellenqualität: Methodisch am stärksten sind Secuora (volle Regeltransparenz, negative Ergebnisse publiziert), die HAW-Bachelorarbeit (akademisch) und OffbeatForex (replizierbar, Open Source). PineScriptForge- und Vendor-Zahlen (Backtrex, LuxAlgo) sind als Hypothesen, nicht als Belege zu behandeln.*
