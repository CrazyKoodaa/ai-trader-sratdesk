# Facet: Intraday/Session-Strategien
*(ORB-Varianten, London/NY-Session-Breakouts, ICT Killzones & Silver Bullet, Asian Range Breakout, NY Open Momentum)*
Research-Stand: 2026 (Web-Recherche, 27 Queries EN+DE). Zielkontext: Python-Bots auf MT5, XAUUSD/NAS100/FX-Majors, PF > 1.5, ≥1:2 RR, Prop-Firm-Tauglichkeit (0,5 % Risiko/Trade, EOD-DD).

---

## Key Findings

### 1. Opening Range Breakout (ORB) — stark widersprüchliche Evidenz, Edge hängt am Filter

**Regelwerk (Kanonical):** Range = High/Low der ersten 5/15/30/60 Min nach Session-Open; Entry bei Break (Close-Bestätigung oder Stop-Order an Range-Grenze); Stop auf Gegenseite der Range (= 1R); Ziel 1–2× Range oder EOD-Exit; Filter: Volumen > Durchschnitt, VWAP-Seite, Relative Strength, Range-Size-Filter. [^153^](https://chartinglens.com/blog/opening-range-breakout-strategy) (2026-07-07), [^154^](https://tradersmastermind.com/trading-strategy-opening-range-breakout/) (2026-07-31)

**Positive Evidenz:**
- Zarattini/Barbon/Aziz (2024, SSRN 4729284): 5-Min-ORB auf 7.000+ US-Aktien 2016–2023, **nur "Stocks in Play"** (abnormales Volumen/News). Top-20-Portfolio: >1.600 % Netto, **Sharpe 2.81**, annualisiertes Alpha 36 % vs. S&P 198 %. Caveats: Leverage/3x-ETFs, backtested. [^33^](https://tradewithpat.com/wp-content/uploads/2025/09/ssrn-4729284.pdf), QuantConnect-Replikation: Sharpe 2.4, Beta ~0. [^39^](https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/) (2024-12-13)
- **DAX-ORB 14-Jahres-Studie (fxvps):** Overnight-Range 03:00–09:00 Frankfurt, Entry per Stop-Order am Cash-Open, Stop = Gegenseite, Ziel 2× Range, flat bis 13:00. H1: **PF 1.25, Sharpe 1.46, +206R**; Edge über alle Wochentage verteilt (Di PF 1.35, Do 1.39) — robustes Profil. ABER: Edge ~0,1R/Trade; **3 Punkte Slippage killen die M15-Variante (PF 0.96)** → Execution/Latenz ist der dominierende Faktor. [^155^](https://fxvps.biz/blog/dax-opening-range-breakout-14-year-study/) (2026-06-10)
- edgeful: 5-Min-ORB auf ES, 6 Monate, 108 % Return; Target 50 % der Range, Stop 100 %, Max-ORB-Size-Filter 0,55 %, Tuesday-Filter. Explizit "nicht voll optimiert", aber kurze Stichprobe = Overfitting-Risiko. [^159^](https://www.edgeful.com/blog/posts/5-minute-opening-range-breakout-es-strategy) (2026-04-18)
- ForexFactory XAUUSD NY-Open-ORB-Scalping (selbstberichtet, unverifiziert): 61 % WR, avg 2,3R; Regeln: nur erste valide Kerze nach 09:30 NY, kein Trade nach 09:45, Body ≥ 0,8 ATR, Wick < 40 %, Volumen-Bestätigung, Close ≥ ½ ATR außerhalb der Range. [^42^](https://www.forexfactory.com/thread/1388244-xauusd-ny-open-range-breakout-scalping-system) (2026-09-02)

**Negative Evidenz:**
- paperswithbacktest: SPY/QQQ/IWM 2010–2025 (1-Min-Bars): nach 15-Min-Upside-Breaks **−1.8 bps** nach 3h, Downside **−3.5 bps** — kein Edge auf ETF-Index-Ebene. Zusätzlich: 27 replizierte Intraday-/Session-Strategien haben median Sharpe **0.05** (vs. 0.37 Katalog-Median), 44 % negativ — **schwächste Strategiefamilie** der Library. [^35^](https://paperswithbacktest.com/strategies/opening-range-breakout) (o.D.)
- GitHub-Studie (XBmosal/orb, SPY 2008–2021, 3.340 Trades): 2:1-ORB mean **−0.022R/Trade**, WR 38.2 %, PF 0.96 — kein grosser Edge, keine Kapazität; **kein Alpha-Decay** nachweisbar (war nie da / regime-abhängig). [^243^](https://github.com/xbmosal/orb) (2026-07-01)
- QuantifiedStrategies: roher ORB auf ES, NQ, **GC (Gold)**, SI, CL ohne Filter durchgehend negativ; mit (nicht offengelegtem) Daily-Filter auf NQ: 198 Trades, WR 65 %, PF 2.0. Fazit: "ORB heute viel weniger relevant als früher." [^152^](https://www.quantifiedstrategies.com/opening-range-breakout-strategy/) (2026-01-06)

**Auflösung des Widerspruchs:** Der Zarattini-Edge liegt im **"Stocks in Play"-Selektionsfilter** (News/Volumen), nicht im ORB-Mechanismus selbst. Auf Index-ETFs/Futures ohne Selektion: kein Edge. Übertragbarkeit auf XAUUSD/NAS100-CFDs fraglich — dort gibt es kein direktes Analogon zu "Stocks in Play"; mögliche Proxys: News-Kalender-Filter, abnormales Session-Volumen, Gap-Size.

### 2. ICT Silver Bullet / Killzones — mechanisierbar, aber keine unabhängig auditierte Evidenz

**Regelwerk (Silver Bullet):** Zeitfenster (NY-Time): **03:00–04:00 (London), 10:00–11:00 (NY AM), 14:00–15:00 (NY PM)**. Setup: HTF-Bias (H4/D1) → Liquidity Sweep (z. B. Asian High/Low) → Market Structure Shift/BOS mit Displacement → Entry per Limit-Order im entstandenen **Fair Value Gap** (FVG) → Stop hinter FVG-Grenze/Sweep-Extrem → Ziel ≥ 2R / nächster Liquiditätspool (min. 5 Handles Indizes / 15 Pips FX). Close[1]-Bestätigung gegen Repainting. [^26^](https://backtrex.com/en/blog/ict-silver-bullet-strategy-trading-guide) (2026-07-04), [^27^](https://innercircletrader.net/id/tutorial/killzone-silver-bullet-overlap/) (2026-06-21), dt. Beschreibung: [^246^](https://volity.io/de/forex/inner-circle-trader-ict-de/) (2026-08-21)

**Killzone-Zeiten (NY local):** Asian 19/20:00–22:00, London 02:00–05:00, NY 07:00–09:00 (FX) bzw. 08:30–11:00 (Indizes), London Close 10:00–12:00. Trade-Flow: Daily Bias → Draw on Liquidity markieren → Killzone abwarten → Sweep → MSS → Entry im FVG/OTE (0,62–0,79) → Stop hinter Sweep → TP am externen Pool → BE nach erstem internem Pool. [^29^](https://innercircletrader.net/tutorials/master-ict-kill-zones/) (2026-06-15), [^30^](https://tradingrage.com/learn/ict-killzone-explained) (2026-03-29), [^34^](https://innercircletrader.net/wp-content/uploads/2023/12/ICT-Kill-Zone-PDF.pdf)

**Performance-Claims (alle mit Vorsicht):**
- pinescriptforge MNQ Silver Bullet: 646 Trades, Jan 2023–Mär 2026, **47.1 % WR, PF 2.03, Sharpe 2.32, maxDD 5.3 %** ($4.50 RT + 1 Tick Slippage). Vendor-generierte Seite — Plausibilitätsproblem: dieselbe Site zeigt auf der MYM-"Conservative"-Seite **zwei widersprüchliche Werte (PF 1.82 und 1.29)** im selben Audit-Block. [^49^](https://pinescriptforge.com/mnq/ict-silver-bullet/backtest) (2024-12-24), [^183^](https://pinescriptforge.com/mym/ict-silver-bullet/backtest/conservative) (2024-07-03)
- backtrex: Zielmetriken für FTMO-Tauglichkeit: WR > 45 %, PF > 1.4, maxDD < 8 %, ≥ 50–100 Setups; EUR/USD 10–11h-Fenster > 3–4h-Fenster; GBP/JPY eher 3–4h. DST (EDT/EST) als klassischer Backtest-Fehler. [^26^](https://backtrex.com/en/blog/ict-silver-bullet-strategy-trading-guide) (2026-07-04)
- secuora (12-Monats-Test BTC/ETH): strikte Same-Candle-Lesart → zu wenige Trades für belastbare WR; Fazit: "Jede Silver-Bullet-Winrate ohne publiziertes Regelwerk ist Marketing." [^44^](https://secuora.xyz/strategy/ict-silver-bullet) (2026-06-12)
- lunefi: behauptet 65–75 % WR für ICT-Setups und "+15 % Prop-Pass-Rate" — Sekundärquellen (Phidias/Bitget-Marketing), **nicht auditiert**. [^176^](https://lunefi.com/blog/ict-trading-strategy-2026-65-75-win-rates-prop-firm) (2026-05-06)
- alphaexcapital (erfreulich ehrlich): **Kein peer-reviewter oder unabhängig auditierter Backtest des ICT OTE/62–79 %-Zone existiert**; alle Winrate-Zahlen selbstberichtet von kommerziellen Sites. [^101^](https://www.alphaexcapital.com/smart-money-concepts/ict-optimal-trade-entry) (2026-08-05)

**Bot-Umsetzbarkeit:** Silver Bullet ist von allen ICT-Konzepten am besten mechanisierbar (Zeitfilter + FVG-Detektion + MSS via Swing-Breaks). Kritisch: DST-Handling, Broker-Server-Time, FVG-Definition exakt kodieren, Sweep-Definition (Wick vs. Close).

### 3. London Breakout / Asian Range Breakout — roh negativ, mit Filtern grenzwertig

**Regelwerk (kanonisch):** Asian Range 00:00–08:00 GMT markieren (High/Low); BuyStop/SellStop an Range-Grenzen zur London-Eröffnung; Stop = Gegenseite (+Buffer); TP 1,5–2× Range oder Zeitexit; Order-Cancel, wenn bis ~10:00 GMT kein Trigger. **Filter (kritisch!):** Range-Width (skip wenn > 60 Pips EURUSD / > 80 GBPUSD bzw. zu eng), News-Filter (kein Trade bei Red-Folder in der 1. London-Stunde), Day-of-Week (Di–Do am besten, Mo/Fr schwach), HTF-Trend-Alignment. [^41^](https://newyorkcityservers.com/blog/london-breakout-strategy) (2026-02-14), [^23^](https://fxnx.com/en/blog/asian-range-breakout-set-forget-strategy) (2026-04-12), [^249^](https://forexforstarters.com/strategies/breakout/asian-range-breakout/)

**Backtest-Evidenz (überwiegend negativ bis gemischt):**
- QuantifiedStrategies EURUSD (Range 03:00–08:00 London, Entry 08:00–11:00, Zeitexits 12:00–17:00): Long-Breakouts **verlieren Geld**; Short-Seite ~0. Fazit: "braucht deutlich mehr Parameter; wir sind skeptisch für jedes FX-Paar." [^24^](https://www.quantifiedstrategies.com/london-breakout-strategies/) (2026-01-27)
- tradersmastermind (GBPUSD, ~267 Sessions, KI-generierter Light-Backtest): rohe Strategie netto negativ (~1 Pip/Trade vor Kosten); GBPJPY 1:1 Full-Range-Stop "lebendiger", aber kleine Stichprobe. Begründung: **FX ist mean-reverting → Blind-Breakout-Käufe fighten die Reversion.** [^248^](https://tradersmastermind.com/london-breakout-trading-strategy/) (2026-07-18)
- InsiderFinance/Medium (Python-Backtest, EURUSD, 10 Monate, mit Pivot-SL, RR 1:1.4, Asian-Range-Filter 10–50 Pips, Min-SL 25 Pips): +7,47 %, WR 49 %, Sharpe 1.84, maxDD 1,72 % — **positiv, aber nur 10 Monate Stichprobe**. [^245^](https://wire.insiderfinance.io/backtest-results-revealed-is-the-london-breakout-strategy-worth-it-0e9df65dd63b) (2025-02-21)
- GitHub Trade-Desk (8 FX-Paare, ~2 Jahre H1, netto nach Kosten): Session-Breakout aggregat **−0.08R, genau am Breakeven** (40 % WR = Schwelle bei 1:1.5); **USDJPY einzig positiv: 227 Trades, 48 % WR, PF 1.25, +0.14R** — Autor warnt explizit vor Cherry-Picking und fordert Walk-Forward. [^21^](https://github.com/WalterVeriza/Trade-Desk/blob/main/ROADMAP.md) (2026-06-23)
- pinescriptforge MGC (Micro-Gold) London Breakout "aggressive": PF 3.16, WR 56 %, maxDD 3,0 % — Vendor-Seite, auffällig perfekt, als **Marketing-Datenpunkt** einordnen. [^281^](https://pinescriptforge.com/mgc/london-breakout/backtest/aggressive) (2024-08-08)

### 4. NY Open Momentum (XAUUSD/NAS100) — bestes Session-Fenster, aber kaum harte Backtests

- pro-scalper (XAUUSD NY Session, detailliertes Playbook): Bestes Fenster **13:00–14:30 GMT** (erste 90 Min des Overlaps), avg Range 55+ Pips in 13:00–15:00, 68 % Wahrscheinlichkeit, dass 13:00–15:00-Bias in 15:00–17:00 persistiert. Drei Setups: (A) London-Trend-Continuation (Pullback auf 50 % der London-Bewegung, selbstberichtet ~62 % WR), (B) London-Reversal-Fade (~48 %), (C) News-Spike-and-Recover (~55 %). Regeln: keine Entries in den ersten 60–90 s nach News; harte Regeln ab 17:00 GMT (Positionsgröße halbieren, Trail enger, kein Trade auf London-Close-Spike, flat bis 21:00). [^179^](https://www.pro-scalper.com/xauusd-strategies/new-york-session-gold-strategy) (2025-01-01)
- quant-signals (NAS100, 76 Strategien / 10.830 Trades): **London Breakout auf NAS100 H1 katastrophal: 14,7 % WR, DD > 100 %** — Session-Volatilität erzeugt False Breakouts. Momentum generell: D1 >> H1 (EMA-Swing 21/50 D1: PF 3.75). [^45^](https://quant-signals.com/nas100-trading-strategy/) (2026-04-04)
- quant-signals H1-vs-D1-Studie (13 Strategien × 6 Assets inkl. XAUUSD, NAS100): **Time-basierte Strategien (Session-Breakouts) H1: PF 0.39 — mit Abstand schwächste Kategorie**; Trend-Following H1 PF 0.98 vs. D1 1.24. [^47^](https://quant-signals.com/h1-vs-d1-trading-strategy/) (2026-04-04)
- Prop-Kontext bestätigt: XAUUSD ist laut FTMO-Statistik 2024 zweitbeliebtestes Instrument in Challenges; empfohlen werden Session-Breakout + S/R-Price-Action, max 2–3 Trades/Tag auf Gold, SL ≥ 50 Pips, beste Sessions London Open + London/NY-Overlap; News-Trading ist regel-Grauzone. [^99^](https://www.jptradingcapital.com/blog/en/gold-trading-strategies-xauusd) (2026-05-06), [^52^](https://newyorkcityservers.com/blog/gold-xauusd-trading-strategy) (2026-04-02)

### 5. Closed-Source-Bots/EAs mit öffentlich beschriebener Logik (Session-/Breakout-Familie)

| EA | Instrument | Öffentlich beschriebene Logik | Zahlen/Red Flags |
|---|---|---|---|
| **Golden Range Breakout EA** (LazyAlgos, MT5, $129) | XAUUSD, FX, Indizes | Frei definierbare Zeit-Range (Default 03:00–06:00 Server = Asian Range für London-Breakout), BuyStop/SellStop an Grenzen, OCO, 3 TP-Modi, 4 SL-Typen, Range-Size-Filter (min/max %), FTMO-Trailing-DD, randomisierte Entry-Delays | Logik vollständig dokumentiert; keine unabhängigen Live-Audits [^110^](https://lazyalgos.com/products/golden-range-breakout-ea) |
| **Gold Breakout Scalper Pro** (MT5) | XAUUSD | NY-Session-Breakout auf Session-Open-Highs/Lows, 1 Trade/Tag, fixer SL ($5/0.01 Lot), trailing TP, kein Grid/Martingale, "unique trades" gegen Prop-Copy-Detection | FTMO-Pass-Behauptungen, unverifiziert [^102^](https://ecomforex.com/product/gold-breakout-scalper-pro-mt5/) (2025-12-18) |
| **The Gold Reaper** (MT5, Wim Schrynemakers) | XAUUSD | Multi-Timeframe-S/R-Levels (intraday/swing/strukturell), Entry bei Break mit Momentum, vordefinierter SL, dynamischer TP, Prop-Set-Files | "5 % der Trading-Tage machen 80 % der Returns" → VPS Pflicht [^98^](https://cheaperforex.com/product/the-gold-reaper-mt5/) (2026-07-15) |
| **Pivot Killer** (MT5, Pablo Dominguez Sanchez) | XAUUSD H1 | Breakout-basiert, 3 kombinierte Logiken (Zone-Detektion, Volatilitäts-/Session-Filter, Risiko-Modul), **starker Long-Bias**, kein Grid/Martingale | Unabhängiger 20-Jahres-Backtest (forexrobotlab): 3.197 Trades, WR ~38 %, **PF 1.33**, Profit konzentriert ab 2020 (Gold-Bullenmarkt) → Regime-Abhängigkeit; Forward (3 Wo., 10 Trades) PF 3.85 = "zu gut" [^46^](https://forexrobotlab.com/pivot-killer-mt5-ea-review/) (2025-12-02) |
| **Prop Firm Gold EA** (MQL5 Market, $990) | XAUUSD | Multi-Strategie, breakout-basiert für intraday-Dominanz + Intraday-Price-Patterns, indikatorlos, kein fixes TF, minimale Optimierung; Randomizer + Daily-DD-Schutz | Vendor-Claim: 15 Jahre Backtest + 15 Monate Live vor Release — nicht auditierbar [^112^](https://www.truthalgo.com/ea?id=153540) (2025-10-29) |
| **Ultimate Breakout System** (MT5, Wim Schrynemakers) | Multi | 100+ Strategien/Set-Files, Pending-Order-Breakouts; Basis für Gold Reaper | MQL5 5.0/56 Reviews; **ABER**: unabhängiger Test XAUUSD M15 (BBTrading, 2026-H1): **PF 1.01**, 1.522 Trades — quasi kein Edge im getesteten Set [^43^](https://quant.b123.com/product/ultimate-breakout-system-4-3/) (2026-08-26), [^178^](https://fxtoolsai.com/ultimate-breakout-system/) |
| **Golden Tiger EA** (LazyAlgos) | XAUUSD | Previous-Day-High/Low-Breakout + Gap-Detection (Market-Order wenn Open jenseits Vortagesrange), News-Filter via faireconomy-Calendar, FTMO/The5ers/MFF-Presets | [^106^](https://lazyalgos.com/products/golden-tiger-ea) |
| **ICT Silver Bullet EA** (MT4, diverse Reseller) | FX/Indizes | Silver-Bullet-Automation | **Red Flags:** FTMO-"Pass in 10 Tagen" mit 40-Lot-Trades, PF 104.120 (unsinnig), Sharpe 0.94 — Glücksspiel-Metriken, kein Beleg [^180^](https://fxcrack.com/product/ict-silver-bullet-mt4-ea/) (2024-11-24) |
| **GOLD_ORB** (Open Source, GitHub yulz008) | XAUUSD | MQL5-ORB-EA: Range am Candle-Start, Signale "11"/"10", dynamische Positionsgröße, DD-Monitoring-Modul | Open-Source-Referenz-Implementierung für eigenen Bot [^174^](https://github.com/yulz008/GOLD_ORB) (2022-11-15) |

---

## Major Players & Sources

- **Akademisch:** Zarattini (Concretum Research), Barbon (Uni St. Gallen/SFI), Aziz (Peak Capital/Bear Bull Traders) — SSRN 4729284 & SSRN 2023-Paper; Crabel (1990, Ur-ORB). QuantConnect-Replikation. [^33^][^38^][^39^]
- **Replikations-/Skeptiker-Seiten:** paperswithbacktest.com (Session-Familie = schwächste Kategorie), QuantifiedStrategies (EURUSD-London-Breakout negativ; NQ-ORB nur mit Filter), GitHub XBmosal/orb (SPY-Capacity-Studie), GitHub WalterVeriza/Trade-Desk (8-Paare-Session-Breakout: Breakeven, nur USDJPY positiv). [^35^][^24^][^243^][^21^]
- **Vendor-Backtest-Aggregatoren (niedrige Verlässlichkeit):** pinescriptforge.com (intern widersprüchliche Metriken), quant-signals.com, backtrex.com, secuora.xyz, edgeful.com, tapescript.io. [^49^][^45^][^26^][^44^]
- **ICT-Ökosystem:** innercircletrader.net (Killzone/Silver-Bullet-Definitionen), fxnx.com, tradingrage.com; ehrliche Evidenz-Einordnung: alphaexcapital.com ("kein auditierter ICT-Backtest existiert"). [^29^][^27^][^101^]
- **EA-Markt:** LazyAlgos (Golden Range Breakout, Golden Tiger), Wim Schrynemakers (Gold Reaper, Ultimate Breakout), Prop Firm Gold EA; unabhängige EA-Reviews: forexrobotlab.com, truthalgo.com. [^110^][^46^][^112^]
- **Community:** ForexFactory (XAUUSD NY-Open-ORB-Thread, Shirley-Hudson-LCT-Kritik), Reddit r/algotrading (BTC/GBPUSD-ORB-Backtests, laut Landscape-Scan positiv — in dieser Recherche nicht direkt verifizierbar). [^42^][^96^]

## Trends & Signals

1. **"Filter ist die Strategie":** Konsens quer durch alle seriösen Quellen — rohe Session-Breakouts sind tot (FX mean-reverting, Crowding); der Edge liegt in Selektionsfiltern: News/"in play", Volumen-Anomalie, Range-Width-Bänder, HTF-Alignment, Wochentag, Session-Kontext (London-Trend → NY-Continuation).
2. **Execution ist der Margin-Killer:** DAX-14-Jahres-Studie zeigt PF 1.25 → 0.96 bei 3 Pts Slippage. Für MT5-Bots: Spread-/Slippage-Stresstests, VPS/Latenz, Fill-Qualität am Open sind entscheidend. [^155^]
3. **Prop-Firm-Design-Pattern etabliert sich:** 1 Trade/Tag, fester Zeit-Exit, Daily-Loss-Limit im Bot, kein Grid/Martingale, randomisierte Entries gegen Copy-Detection, FTMO-Trailing-DD-Modi sind Standard-Features kommerzieller Session-EAs — direkt für eigenen Bot übernehmbar. [^110^][^102^]
4. **ICT-Mechanisierung wächst:** Silver Bullet ist das meist-kodierte ICT-Modell (Pine Script v6, MQL5-EAs); die **Zeitkomponente (Killzone als Filter) ist der robuster Teil**, die FVG/MSS-Subjektivität der Overfitting-Teil.
5. **Zeitbasierte Strategien strukturell schwach in Replikationen:** paperswithbacktest (median Sharpe 0.05) + quant-signals (H1 time-based PF 0.39) deuten in dieselbe Richtung — reine "Tageszeit-Edges" ohne Preis-/Volumenkontext sind kaum robust.
6. **XAUUSD-Session-Struktur:** 08:00–10:00 GMT (London) und 13:00–15:00 GMT (Overlap) sind die volumenstärksten Fenster; professionelle Gold-Playbooks strukturieren den ganzen Tag um diese zwei Blöcke. [^179^][^32^]

## Controversies & Conflicting Claims

| Konflikt | Seite A | Seite B | Einordnung |
|---|---|---|---|
| **ORB hat Edge** | Zarattini/Aziz: Sharpe 2.81 (Stocks in Play, 2016–23); QuantConnect 2.4 | paperswithbacktest: −1.8 bps (SPY/QQQ/IWM); XBmosal: PF 0.96 (SPY 08–21); QuantifiedStrategies: negativ auf ES/NQ/GC/SI/CL | Kein echter Widerspruch: Edge steckt im **Stocks-in-Play-Filter + Leverage**, nicht im Mechanismus. Für CFDs ohne Selektions-Analogon eher negativ lesen. |
| **London Breakout profitabel** | InsiderFinance: +7,5 %/10 Mon., Sharpe 1.84 (mit Filtern); pinescriptforge MGC: PF 3.16 | QuantifiedStrategies: verliert auf EURUSD; tradersmastermind: netto negativ GBPUSD; Trade-Desk: aggregat Breakeven, nur USDJPY + | Gefilterte Varianten grenzwertig positiv; Vendor-PF 3.16 nicht glaubwürdig. USDJPY-Befund könnte Session-Logik (aktive Asian-Session) stützen — oder Cherry-Picking sein. |
| **ICT-Winrates 65–75 %** | lunefi/Phidias/Bitget-Marketing; "tausende funded Trader" | alphaexcapital: kein auditierter Backtest; secuora: strikte Mechanisierung zu wenige Trades; pinescriptforge intern widersprüchlich (PF 1.82 vs 1.29 auf einer Seite) | Alle hohen ICT-Zahlen sind Marketing. Mechanisierbare Kerne (Zeitfenster, Session-Sweeps) testbar; FVG/MSS-Lesart nicht standardisiert → Overfitting-Gefahr extrem hoch. |
| **London Close Trade (Shirley Hudson): 90–93 % WR, 47k Pips** | Forexmentor-Verkaufsseite | ForexFactory: "fraudulent claims", keine Broker-Statements, unabhängiger 2-Monats-Test (Simit Patel) schwach/abgebrochen | Klassisches Verkaufs-Narrativ; als Evidenz unbrauchbar. [^96^][^103^] |
| **Alpha-Decay nach Publikation** | Taylor: ~35 % Efficacy-Decay post-publication; Bulkowski: Pattern-Failure 11 % (1991) → 44 % (2007) | XBmosal: kein Decay beim ORB nachweisbar ("war nie da bzw. regime-abhängig") | Beide plausibel: Crowding killt Retail-lesbare Setups; ORB auf Indizes hatte evtl. nie robusten Edge. [^251^][^243^] |
| **NAS100 intraday tauglich** | pinescriptforge MNQ Silver Bullet PF 2.03 | quant-signals: NAS100 H1-Strategien ~breakeven, London Breakout H1 14,7 % WR / DD >100 % | Intraday-Edges auf NAS100 nur mit sehr spezifischem Setup (Zeitfenster + Struktur); generische Breakouts zerstörerisch. |

## Recommended Deep-Dive Areas

1. **XAUUSD NY-Open-ORB mit Filtern (Top-Kandidat für Bot):** ForexFactory-Regelwerk (erste valide Kerze, ATR-Filter, Volume) + pro-scalper-Kontext (13:00–14:30 GMT) als Basis für eigenen M5/M15-Backtest. Teste: Range-Size-Bänder, News-Filter, "London-Trend-Continuation"-Variante. [^42^][^179^]
2. **Silver Bullet mechanisiert auf NAS100/XAUUSD M1–M5:** Zeitfenster 10:00–11:00 NY + Sweep des Asian-/London-Levels + Displacement + FVG-Retest, 2R-Ziel. Referenz-Implementierungen: PineScriptForge-Logikbeschreibung, backtrex-Regeln. Eigenen Backtest bauen — Vendor-Zahlen (PF 2.03) nicht übernehmen. [^49^][^26^]
3. **USDJPY Asian-Range-Breakout (einziger positiver FX-Datenpunkt):** Trade-Desk-Setup (Range 00–07 UTC, R:R 1.5) replizieren + Walk-Forward; prüfen ob Session-Aktivität der JPY-Paare den Unterschied erklärt. [^21^]
4. **DAX-/Index-ORB-Slippage-Modell übernehmen:** Die fxvps-Slippage-Matrix als Pflicht-Stresstest für jeden eigenen Session-Bot (PF vs. 0–5 Pts Slippage). [^155^]
5. **"Stocks-in-Play"-Analogon für CFDs finden:** News-Kalender-Filter (Red-Folder ±X Min), abnormales Tick-Volumen, Overnight-Gap-Size als Selektor — Hypothese: Zarattini-Edge = Selektion, nicht Timing. [^33^]
6. **EA-Architektur-Muster (Prop-Tauglichkeit):** Golden Range Breakout / Gold Reaper Feature-Listen als Blaupause: OCO-Pending-Orders, Range-Size-Filter, Daily-DD-Halt (Balance/Equity/Trailing), News-Pause, 1–2 Trades/Tag, EOD-Flat. [^110^][^98^]
7. **Offen:** Reddit-Backtests (BTC/GBPUSD ORB aus Landscape-Scan) konnten in dieser Recherche nicht direkt verifiziert werden (Suchmaschinen-Treffer 0) — Lead ggf. Reddit-API/Pushshift nutzen.

---
*Methodik-Hinweis: 27 Suchqueries (EN/DE, grob→fein). Quellen-Autorität gemischt; Vendor-Backtests (pinescriptforge, backtrex, edgeful) sind AI-generierte Marketing-Seiten mit teils intern widersprüchlichen Metriken — als Hypothesen, nicht als Evidenz behandelt. Härteste Datenpunkte: SSRN-Paper, QuantConnect-Replikation, paperswithbacktest, GitHub-Studien (XBmosal, Trade-Desk), forexrobotlab-Eigenbacktest.*
