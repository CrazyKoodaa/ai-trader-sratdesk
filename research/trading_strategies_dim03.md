# Deep-Dive Dimension 03: ICT Silver Bullet — vollständige Regel-Spezifikation

Recherche-Datum: 2026-06 (KI-Sitzung); 15 gezielte Suchen (EN/DE) + 5 Deep-Reads (GitHub-Code, Vendor-Guides, Negativ-Backtest).
Zielkontext: Python-Bot auf MT5 (pymt5trade), PF > 1.5 OOS, RR ≥ 1:2, Prop-Firm-tauglich. Baut auf wide01/wide02 auf.

---

## 1) Kanonisches Regelwerk (Rekonstruktion aus Original- und Sekundärquellen)

### 1.1 Zeitfenster — hoher Konsens, DST-kritisch

**Claim:** Drei Fenster à 60 Min, NY-Lokalzeit: **03:00–04:00 (London Open), 10:00–11:00 (NY AM, primär), 14:00–15:00 (NY PM)**. Fenster sind in NY-Zeit DST-stabil (EST↔EDT); nur die UTC-/CET-Umrechnung wandert. Trades außerhalb = kein Silver Bullet.
- Source: LuxAlgo Blog; innercircletrader.net; howtotrade; forexbee; lsgclub; fairvaluehub; backtrex
- URL: https://www.luxalgo.com/blog/ict-silver-bullet-setup-trading-methods/ ; https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/ ; https://backtrex.com/en/blog/ict-silver-bullet-strategy-trading-guide
- Date: 2025-07-18 / 2026-05-03 / 2026-07-04
- Excerpt: "All times below are referenced to New York local time… The windows do not move in NY local time — only the label changes EST→EDT." / backtrex: "Ein falsch konfigurierter Zeitfilter (EDT vs EST) kann den gesamten Backtest verfälschen."
- Confidence: HOCH (7+ unabhängige Quellen, identische Zeiten). **Implementierungspflicht: tzdata America/New_York, nie Serverzeit.**

### 1.2 Referenz-Liquidität (was wird gesweept?) — zwei Varianten

**Claim A (Level-Variante, ICT-nah):** Vor Fensterbeginn auf M15 markieren: Previous Day High/Low, Overnight-/Asian-Session H/L, Equal Highs/Lows, Wochen-H/L = "Draw on Liquidity"-Kandidaten.
- Source: innercircletrader.net, michaeljhuddleston.org, fxnx
- Excerpt: "Before the window opens, I mark the nearest buy-side and sell-side liquidity on the 15-minute chart."
- Confidence: HOCH (mehrere Quellen), aber Level-Wahl ist diskretionär → für Bot festzulegen.

**Claim B (Previous-Hour-Variante, mechanisch am saubersten):** Referenz = High/Low der **vorangegangenen Stunden-Kerze** (für 10–11 Uhr: die 09:00–09:59-Kerze). Sweep = Bruch einer Seite dieser Range.
- Source: GitHub hindsight-finance/Silver-Bullet-AM-Session (strategy.md); ScalperIntel NinjaTrader-Indikator ("Previous-Hour Liquidity"); dipprofit ICT-PDF ("break either the highest or lowest point of the last hour's candle")
- URL: https://github.com/hindsight-finance/Silver-Bullet-AM-Session/blob/main/strategy.md ; https://scalperintel.com/products/ict-silver-bullet
- Date: 2026-05-11 / 2025-08-06
- Confidence: HOCH als *implementierte* Lesart (zwei unabhängige Code-Implementierungen); das ist die bot-tauglichste Sweep-Definition.

### 1.3 Sweep-Definition

**Claim:** Wick bricht Referenz-Level; Bestätigung = **Close zurück innerhalb der Range** (Sweep ≠ Breakout). Sweep-Extrem kann sich über mehrere Kerzen fortsetzen, bis erster Close zurück im Range.
- Source: hindsight-finance backtest.py (Code inspiziert); Secuora ("wick takes out prior swing… and the candle closes back inside", Fraktal-Lookback 3); sarahleesoffice ("wicks beyond a key swing level, then closes back inside")
- Excerpt (Code, hindsight): Sweep-Loop tracke Extrem über Folgekerzen; Abbruch sobald `Close < range_high` (High-Sweep) bzw. `Close > range_low`.
- Confidence: HOCH. Alternative Lesart (nur Wick, kein Close-Back) existiert (ScalperIntel: wick/close/any-break konfigurierbar) → Parameter.

### 1.4 MSS / Displacement

**Claim:** Nach dem Sweep impulsive Gegenbewegung ("Displacement"), die eine rezente Swing-Struktur bricht (Close jenseits des letzten gegenläufigen Swings). Mechanische Operationalisierung (hindsight): Body > **1,5 × ATR(20)** UND Body ≥ **70 % der Kerzenrange** UND Close zurück innerhalb der gesweepten Range.
- Source: hindsight-finance backtest.py (`is_displacement_candle`); quantum-algo ICT-2022-Guide ("displacement … breaks structure and leaves an FVG behind"); fxnx ("Displacement must create MSS: break of previous swing high/low")
- URL: https://raw.githubusercontent.com/hindsight-finance/Silver-Bullet-AM-Session/main/backtest.py ; https://www.quantum-algo.com/blog/guides/ict-2022-model-complete-guide/
- Confidence: MITTEL-HOCH. MSS-Swing-Definition variiert (Fraktal-Lookback 3 bei Secuora; Swing-Länge frei in smartmoneyconcepts). innercircletrader.net selbst: "die Diskretion beim MSS-Schritt ist schwer zu kodieren" — **das ist der größte Formalisierungs-Hebel/-Risiko.**

### 1.5 FVG-Definition und Entry

**Claim:** FVG = 3-Kerzen-Imbalance (bullisch: high[i-2] < low[i]; bearisch: low[i-2] > high[i]), entstanden in der Displacement-Leg. Entry = **Limit-Order im FVG**: aggressiv an der Gap-Kante, konservativ an **50 % (Consequent Encroachment)**. Mindest-Gap-Größe z. B. **0,3 × ATR**. Anti-Repainting: erst nach Close der 3. Kerze (close[1]).
- Source: michaeljhuddleston.org ("limit buy at the 50% level of the FVG"); Secuora (50 %-CE, max 30 Bars alt); backtrex ("close[1] non-negotiable"); hindsight (Entry bei Retracement in Gap, Min-Size 0,3 ATR); quantum-algo (far edge aggressiv / CE konservativ)
- Confidence: HOCH (Definition), MITTEL (Entry-Tiefe ist freier Parameter).

### 1.6 Stop & Target

**Claim Stop:** Jenseits des Sweep-Extrems (hindsight: 1 Tick; sarahleesoffice: 3 Handles; quantum-algo: "just beyond the sweep wick"). Alternative: hinter FVG-Grenze/Swing (LuxAlgo, fluxcharts).
**Claim Target:** (a) gegenüberliegende Liquidität / Gegenseite der Referenz-Range (hindsight: andere Seite der 9-Uhr-Range; fluxcharts: BSL↔SSL), oder (b) fix **2R** (fxnx: "The Silver Bullet is designed for 2:1"; Secuora: 2R). Mindest-Distanzregel: Entry→Target > **5 Handles Indizes / 10–15 Pips FX**, sonst skip (michaeljhuddleston.org). Mindest-RR-Filter z. B. **2,5R** (hindsight) bzw. 1:2 (lsgclub, fluxcharts).
**Management:** Teilausstieg bei 5 Handles/10 Pips, dann BE (michaeljhuddleston.org); oder BE bei 3R (hindsight). Max 1 Trade pro Fenster ("one shot, one kill"); kein Setup bis Fensterende = kein Trade. Trade darf über Fensterende hinauslaufen (innercircletrader.net) — Secuora testete Gegenvariante (Close am Fensterende).
- Confidence: HOCH (Stop-Logik), MITTEL (Target variiert stark → Parameter).

### 1.7 Kanonische 8-Regeln-Kette (lsgclub, deckt sich mit allen anderen)

1. HTF-Bias (H4/D1) → Richtung · 2. Fenster aktiv · 3. Sweep eines Liquidity-Levels · 4. FVG auf M1/M5 direkt nach Sweep+Displacement · 5. Retracement ins FVG **innerhalb desselben Fensters** · 6. Entry am FVG (50 % oder Gap-Kante) · 7. SL hinter FVG/Sweep-Wick · 8. TP nächster gegenüberliegender Liquidity-Pool, min. 1:2. [Confidence: HOCH als Sekundär-Konsens]

---

## 2) Öffentliche Implementierungen und deren konkrete Detection-Regeln

| Implementierung | Sprache/Plattform | Detection-Regeln (konkret) | URL |
|---|---|---|---|
| **hindsight-finance/Silver-Bullet-AM-Session** ⭐ Referenz | Python/pandas, NQ 1-Min | 9-Uhr-Range als Referenz; Sweep = Bruch + Close zurück; Displacement = Body>1,5×ATR(20) & Body/Range≥0,7; Entry = früheste Retest-Kerze von FVG (≥0,3×ATR) / OB (Body-Overlap) / Breaker (Swing-Retest, inkl. Pre-Session-Kontext); Entry-Preis = Close der Signalkerze; SL = Sweep±1 Tick; TP = Gegenseite 9-Uhr-Range; MIN_RR=2,5; BE@3R; 1 Trade/Tag | https://github.com/hindsight-finance/Silver-Bullet-AM-Session |
| **sarahleesoffice/Macro_Liquidity_Sweep-_Backtester** | Python, QQQ×40 als NQ-Proxy, 1-Min, Bar-by-Bar | Multi-TF-Swings (1m→5m/15m/1h/4h resample); Sweep = Wick jenseits Swing + Close zurück; MSS = Displacement bricht Struktur; Entry am FVG; SL = 3 Handles hinter Sweep; TP = nächster Swing-Body; min 1:1; Sweep-Cooldown 20 Bars; FTMO-Regeln (0,5 % Risiko, Daily-Loss, max 3 Versuche, "one and done") | https://github.com/sarahleesoffice/Macro_Liquidity_Sweep-_Backtester |
| **joshyattridge/smartmoneyconcepts** (aus wide02) | Python | `smc.fvg()`, `smc.swing_highs_lows(swing_length)`, `smc.bos_choch()`, `smc.liquidity()` — Bausteine, kein fertiger SB | https://github.com/joshyattridge/smartmoneyconcepts |
| **BAKOME-Hub/BAKOMEGoldScalper** | MQL5, XAUUSD M5 | Silver-Bullet-Killzones (Brokerzeit 8–9, 15–16), FVG+OB+Sweep, EMA-H1/H4-Bias, ATR-Filter (Min 100 Punkte), Spread-Filter (max 50), Daily-Loss 5 %, Trailing ab 1,5×ATR | https://github.com/BAKOME-Hub/BAKOMEGoldScalper |
| **ScalperIntel ICT Silver Bullet** ($229) | NinjaTrader 8 (NinjaScript) | Previous-Hour-Liquidity (wick/close/any-break wählbar), CHoCH/BOS im Fenster, richtungsgebundene FVGs, 140+ Regelpfade, ATR-Signal-Throttling, non-repainting (bar close) | https://scalperintel.com/products/ict-silver-bullet |
| **NadirAliOfficial/STAR-EA v11.20** | MQL5 | 12-Regime-Klassifikator, Silver Bullet als Feature neben OB/FVG/OTE/CRT; Breakout-Bestätigung 2 Closes; ATR(14)-Min 8 Pips; News-Filter ±30 min | https://github.com/NadirAliOfficial/STAR-EA-v11.20 |
| **ikeawesom/xauusd-backtest** (verwandt: PDH/PDL-Sweep) | Python, XAUUSD | Sweep PDH/PDL + Reversal, TP am Sweep-Punkt, Tagesende-Stop | https://github.com/ikeawesom/xauusd-backtest |

---

## 3) Performance-Hinweise — alle mit kritischer Bewertung

| # | Claim | Quelle/Setup | Kritik | Confidence |
|---|---|---|---|---|
| P1 | **Strikte mechanische Lesart: ~1 Trade in 12 Monaten** (Same-Candle-Konfluenz); Relaxed (Sweep+FVG ohne Same-Candle-MSS, 2R, Fensterende-Exit): BTC 46 Trades, WR 17,4 %, **PF 0,14**; ETH 47, WR 8,5 %, **PF 0,08**; "No Edge" 20/100 | Secuora, Binance BTC/ETH 5m, 06/2025–06/2026, 1 % Risiko, 0,05 % Fees, volle Regelpublikation | Härtester negativer Datenpunkt, ABER: Krypto (kein echter Session-Open), Same-Candle- bzw. Relaxed-Lesart ≠ kanonische sequentielle Lesart, kein HTF-Bias-Filter, kein Displacement-Filter. Zeigt: **Definitionswahl ist alles.** | HOCH (Transparenz), eingeschränkte Übertragbarkeit |
| P2 | **Fenster C (10–11 NY, kanonisch): WR 38,3 %, PF 1,32, n=149**; Fenster B (9:30–10:00): WR 49,4 %, PF 2,47, n=77; Fenster A (8:30–9:10): WR 60,7 %, PF 3,16, n=183. Gesamt 409 Trades, 2022–2025, Ø Win/Loss 2,16:1, maxDD $1.154 @ FTMO-konform | GitHub sarahleesoffice, QQQ×40-Proxy, 1-Min | Selbstberichtetes Repo, Kostenmodell unklar dokumentiert, QQQ-Proxy, Min-RR nur 1:1 (nicht 2R) → nicht kanonisch. **Zentrale Erkenntnis: das klassische 10–11-Fenster war hier das SCHWÄCHSTE; PF 1,32 < Ziel 1,5.** | MITTEL |
| P3 | Video-Backtest (FX Replay): 15 Trades/45 Tage, Ø RR ~5:1, +44,4 % (Jul–Aug) | hindsight-finance strategy.md (Referenzvideo) | n=15, manuell, nicht unabhängig → Hypothese | NIEDRIG |
| P4 | MNQ Silver Bullet: PF 2,03, WR 47,1 %, n=646; CT: PF 1,37, WR 53,3 %, n=798 | pinescriptforge (Vendor, AI-generiert, intern widersprüchlich laut wide02) | Marketing-Datenpunkte; interne Inkonsistenzen dokumentiert → nicht ohne Replikation verwenden | NIEDRIG |
| P5 | XAUUSD M5 2024–25: 342 Trades, WR 68,7 %, **PF 1,82**, maxDD 12,4 %, Ø RR 1:2,3 | BAKOMEGoldScalper README (selbstberichtet, "real tick data") | Kein Audit, kein OOS-Nachweis, Sponsor-Finanzierung → Interessenkonflikt; aber vollständiger MQL5-Code = replizierbar | NIEDRIG-MITTEL |
| P6 | "70–80 % Winrate" (LuxAlgo); ">77 %" (michaeljhuddleston.org); "55–65 % @ 1:3" (innercircletrader.net) | Marketing-/Community-Seiten | Keine publizierten Regelsets/Backtests → Secuora-Fazit: "jede Winrate ohne Regelwerk ist Marketing" | SEHR NIEDRIG |
| P7 | Zielmetriken Prop-Tauglichkeit: WR>45 %, PF>1,4, maxDD<8 %, n≥50–100; EUR/USD besser 10–11, GBP/JPY besser 03–04 | backtrex (Vendor) | Plausible Benchmarks, verkauft Tool | MITTEL (als Benchmark, nicht als Ergebnis) |
| P8 | ICT Silver Bullet EA MT4: "PF 104.120" | fxcrack-Reseller | Unsinnige Metrik → Scam-Referenz | — |

**Synthese:** Kein auditierter positiver Backtest existiert. Härteste Evidenz (P1, P2) zeigt: mechanisch-ungefiltert **kein Edge**; sequentielle+gefilterte Lesart auf Index-Proxy erreicht bestenfalls PF ~1,3–2,5 je nach Fenster (selbstberichtet). Der PF-2,03-MNQ-Claim bleibt unbelegt. Bot-Ziel PF>1,5 OOS ist ambitioniert; realistischer Pfad = harte Konfluenz-Kette (HTF-Bias + Sweep + Displacement + FVG-Mindestgröße + Fenster) + Kostenrobustheit.

---

## 4) Instrumenten-Fit

| Instrument | Beleglage | Detail |
|---|---|---|
| **NQ/NAS100 (ES)** | STÄRKSTE | ICT hat das Modell auf US-Index-Futures designed (innercircletrader.net: "originally designed and tested on NQ/ES"). Alle ernsthaften Code-Backtests (hindsight, sarahleesoffice) laufen auf NQ. 10–11-Fenster = Equity-Open-Orderflow. Empfohlene Stops 5–8 Handles, Ziele 10–15 Handles (backtrex). |
| **EUR/USD, GBP/USD** | MITTEL-STARK | FX-Benchmarks laut backtrex/LuxAlgo/howtotrade; 10–11-Fenster > 03–04 für EUR/USD; enge Spreads killzone-tauglich. Stop 8–15 Pips, Ziel 15–20 Pips (backtrex-Tabelle). Kein harter Backtest gefunden. |
| **XAUUSD** | MITTEL | innercircletrader.net & fxnx: "works exceptionally well on gold… aber schneller, weitere Stops nötig"; michaeljhuddleston.org: London-Fenster, weitere Stops. Einzige Code-Implementierung mit Zahlen: BAKOME (P5, unauditiert). Hohe Vola → Slippage-Sensitivität der engen Stops kritisch (wide02: enge SMC-Stops kostensensitiv). |
| **GBP/JPY, JPY-Paare** | SCHWACH-NISCHE | backtrex: eher 03–04-Fenster (Asia/London), Stop 12–18, Ziel 20–25 Pips. |
| **Krypto (BTC/ETH)** | NEGATIV BELEGT | Secuora P1: PF 0,08–0,14. backtrex-FAQ: keine institutionellen Öffnungszeiten → Killzone-Logik entfällt. |

**Empfehlung:** Primär NAS100 (10–11 NY), sekundär EUR/USD; XAUUSD nur mit adaptierten Stop-/Slippage-Parametern; Krypto ausschließen.

---

## 5) Parameter-Räume für Walk-Forward

Aus den inspizierten Implementierungen abgeleitete Räume (Defaults in Klammern):

| Parameter | Raum | Quelle-Default |
|---|---|---|
| Fenster | {03–04, 10–11, 14–15} NY; ggf. {9:30–10:00, 8:30–9:10} als Alternativen testen | 10–11 |
| Referenz-Level | 9-Uhr-Range / Asian-H/L / PDH-PDL / EQH-EQL (Toleranz 0,1–0,3×ATR) / Session-H/L | 9-Uhr-Range |
| Sweep-Bestätigung | wick-only / close-back-inside; Fraktal-Lookback 2–5 | close-back |
| ATR_PERIOD | 10–20 (20) | hindsight |
| ATR_DISPLACEMENT_MULT | 1,0–2,0 (1,5) | hindsight |
| BODY_RATIO_MIN | 0,55–0,80 (0,70) | hindsight |
| FVG_MIN_GAP_ATR | 0,1–0,5 (0,3) | hindsight |
| FVG-Max-Alter | 15–60 Bars (30) | Secuora |
| Entry-Tiefe | Gap-Kante / 50 % CE / 100 % | 50 % |
| MIN_RR | 1,5–3,0 (2,5) | hindsight |
| BREAK_EVEN_R | off / 1,0–3,0 (3,0); alternativ Teilausstieg bei 5 Handles/10 Pips | hindsight/michaeljhuddleston |
| Stop-Puffer | 1 Tick – 3 Handles bzw. 0–0,2×ATR | hindsight/sarahleesoffice |
| Zeit-Exit | Fensterende / Sessionende / keiner | Varianten |
| Trades/Tag | 1 (max 2, zweiter nur nach BE des ersten) | Konsens |
| Risiko/Trade | 0,5 % (Prop) – 1,0 % | sarahleesoffice/Konsens |

**WFO-Design (clearedge.trading / algotrading101):** IS 12 Mon / OOS 3 Mon (4:1), rollierend; WF-Effizienz-Ratio > 0,5 (stark > 0,7); OOS-PF > 1,2 über alle Fenster, ≥ 60 % profitable OOS-Fenster; Parameter-Stabilität als Abbruchkriterium; max. 4–5 freie Parameter gleichzeitig optimieren (Overfitting-Limit).

---

## IMPLEMENTIERUNGS-SPEZIFIKATION (Pseudo-Code, MT5/pymt5trade-tauglich)

```
KONSTANTEN (NY-Lokalzeit via zoneinfo America/New_York, DST-sicher):
  WINDOWS = [(03:00,04:00), (10:00,11:00), (14:00,15:00)]   # primär: 10-11
  ATR_PERIOD=20, DISP_MULT=1.5, BODY_MIN=0.70, FVG_MIN_ATR=0.3
  MIN_RR=2.0, BE_R=3.0, RISK=0.005, MAX_TRADES_PER_WINDOW=1

VOR Fenster (auf M15/H1):
  bias   = HTF-Bias (H4: letzter BOS-Richtung ODER Close vs. EMA50)   # optionaler Filter
  ref_hi/ref_lo = High/Low der Referenz-Range
                  (Variante A: Kerze 09:00-09:59 für 10-11-Fenster
                   Variante B: Asian-Session H/L bzw. EQH/EQL)
  target_long  = nächster Pool oberhalb (ref_hi, Session-High, PDH)
  target_short = nächster Pool unterhalb

IM Fenster (M1-Bars, sequentiell, kein Lookahead — alles erst ab close[1]):
  1. SWEEP:
     if high > ref_hi: sweep_dir=SHORT; sweep_ext = max(high) solange Folgekerzen
        über ref_hi; BESTÄTIGT erst wenn eine Kerze close < ref_hi
     (spiegelverkehrt für LOW/LONG)
     else nach Fensterende: NO_TRADE (skip day)
  2. DISPLACEMENT/MSS:
     erste Kerze nach Sweep-Extrem mit:
        body > 1.5*ATR(20) UND body/range >= 0.70
        UND Richtung == sweep_dir UND close zurück innerhalb Range
        UND close bricht letzten gegenläufigen M1/M5-Swing (Fraktal k=2..3)  ← MSS
     nicht gefunden vor Fensterende: NO_TRADE
  3. FVG (in der Displacement-Leg, 3-Kerzen-Imbalance, size >= 0.3*ATR):
     bullisch: gap = low[i] - high[i-2] > 0 ; Zone [high[i-2], low[i]]
     bearisch: gap = low[i-2] - high[i] > 0 ; Zone [high[i], low[i-2]]
  4. ENTRY (nur im Fenster, Retracement):
     Limit am 50%-CE der Zone (konservativ) ODER Gap-Kante (aggressiv)
     Entry gelöscht wenn nicht gefüllt bis Fensterende.
  5. RISIKO:
     SL = sweep_ext ∓ buffer (buffer = 1 Tick..3 Handles bzw. 0.1*ATR)
     TP = gegenüberliegender Pool;  ABLEHNEN wenn RR(entry→TP) < MIN_RR
     ABLEHNEN wenn Distanz(entry→TP) < 5 Handles (Index) / 10 Pips (FX) / 1.5 USD (XAU)
  6. MANAGEMENT (darf über Fensterende laufen, max bis Sessionende/EOD-flat):
     bei +BE_R: SL → Entry (BE). Optional: 50% Teilausstieg bei 1R/5 Handles.
     EOD-Flat spätestens 16:55 NY (Prop-Regel).
  7. GUARDS (Prop-Firm):
     Daily-Loss-Stop (z.B. -1.5%), MaxDailyTrades=2, News-Blocker
     (kein neuer Trade ±5..15 min um Red-Folder USD-News; sarahleesoffice: News-Tage
     als eigene Kategorie testen), Spread-Filter (reject wenn Spread > 0.2*ATR(M1)),
     Anti-Repaint: sämtliche Signale nur auf geschlossenen Bars.
```

**Mappings auf `smartmoneyconcepts`:** FVG→`smc.fvg()`; Swings/MSS→`smc.swing_highs_lows()`+`smc.bos_choch()`; EQH/EQL-Referenz→`smc.liquidity()`. Sweep-, Fenster- und Displacement-Logik selbst implementieren (Paket deckt Zeitlogik nicht ab). Referenz-Code direkt forkbare Basis: hindsight-finance `backtest.py` (Detection-Logik oben dokumentiert).

---

## Quellen

[^1^]: GitHub hindsight-finance/Silver-Bullet-AM-Session (Repo + strategy.md + backtest.py vollständig inspiziert), https://github.com/hindsight-finance/Silver-Bullet-AM-Session (2026-05-11)
[^2^]: Secuora – ICT Silver Bullet Backtest: 12 Months Real Data (strikte/relaxed Lesart, PF 0,14/0,08), https://secuora.xyz/strategy/ict-silver-bullet (2026-06-12)
[^3^]: GitHub sarahleesoffice/Macro_Liquidity_Sweep-_Backtester (409 Trades, Fenster C PF 1,32), https://github.com/sarahleesoffice/Macro_Liquidity_Sweep-_Backtester (2026-02-08)
[^4^]: LuxAlgo – ICT Silver Bullet Setup & Trading Methods (Fenster, FVG-Entry, 70–80 %-Claim), https://www.luxalgo.com/blog/ict-silver-bullet-setup-trading-methods/ (2025-07-18)
[^5^]: innercircletrader.net – ICT Silver Bullet (15m-Levels, 55–65 % @1:3, Automatisierungsvorbehalt, XAU-Beispiel, NQ/ES-Ursprung), https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/ (2026-05-03)
[^6^]: backtrex – ICT Silver Bullet Trading Guide (Killzone-Tabelle, Instrumenten-Stops/Ziele, Prop-Benchmarks, DST-Warnung), https://backtrex.com/en/blog/ict-silver-bullet-strategy-trading-guide (2026-07-04)
[^7^]: michaeljhuddleston.org – Silver Bullet Notes (50 %-CE-Entry, 5-Handles-Distanzregel, Teilausstieg/BE, 10–40 Pips), https://michaeljhuddleston.org/notes/ict-silver-bullet-strategy-capture-10-40-pips-in-just-60-minutes/ (2026-04-03)
[^8^]: quantum-algo – ICT 2022 Model Guide (5-Komponenten-Sequenz, Sweep-Wick-Stop, CE vs. Far-Edge, 3–5R), https://www.quantum-algo.com/blog/guides/ict-2022-model-complete-guide/ (2026-06-17)
[^9^]: fxnx – Silver Bullet 10–11 Setup & 60-Min-Guide (DOL, 2R-Standard, Stop an Displacement-Swing, Gold-Hinweis), https://fxnx.com/en/blog/ict-silver-bullet-master-10-11-am-setup + /ict-silver-bullet-strategy-60-minute-cure-overtrading (2026-07)
[^10^]: lsgclub.trade – Silver Bullet Entry Rules (8-Regeln-Kette), https://lsgclub.trade/blog/ict-silver-bullet-trading-strategy (2026-04-22)
[^11^]: fluxcharts – ICT Silver Bullet Explained (SL/TP-Varianten 1:2 bzw. BSL↔SSL), https://www.fluxcharts.com/articles/ict-silver-bullet-strategy-explained-how-to-identify-and-trade-it (2024-09-18)
[^12^]: GitHub BAKOME-Hub/BAKOMEGoldScalper (MQL5 XAUUSD; Claims PF 1,82 unauditiert; Parameterliste), https://github.com/BAKOME-Hub/BAKOMEGoldScalper (2026-05-12)
[^13^]: ScalperIntel – ICT Silver Bullet NinjaTrader (Previous-Hour-Liquidity, wick/close/any-break, 140+ Pfade, non-repaint), https://scalperintel.com/products/ict-silver-bullet (2025-08-06)
[^14^]: pinescriptforge – MNQ ICT Silver Bullet (PF 2,03) & CT conservative (PF 1,37), https://pinescriptforge.com/mnq/ict-silver-bullet/backtest , https://pinescriptforge.com/ct/ict-silver-bullet/backtest/conservative (2024-11/12; Vendor, intern inkonsistent)
[^15^]: GitHub NadirAliOfficial/STAR-EA-v11.20 (MQL5, 12-Regime inkl. Silver Bullet), https://github.com/NadirAliOfficial/STAR-EA-v11.20 (2026-04-14)
[^16^]: GitHub ikeawesom/xauusd-backtest (PDH/PDL-Sweep XAUUSD, ~70 % WR ohne Kosten — Artefakt kleiner TP), https://github.com/ikeawesom/xauusd-backtest (2026-02-07)
[^17^]: forexbee – ICT Silver Bullet (Fenster, HTF/LTF-Trennung), https://forexbee.co/ict-silver-bullet-trading-strategy/ (2026-07-17)
[^18^]: fairvaluehub.de – ICT Silver Bullet Guide (EN; Fenster CET-Umrechnung), https://fairvaluehub.de/en/blog/ict-silver-bullet-en (2026-02-14)
[^19^]: clearedge.trading – Walk-Forward Optimization (4:1 IS/OOS, WFE>0,5, ≤4–5 Parameter), https://clearedge.trading/post/walk-forward-optimization-futures-strategy-validation (o. D.); ergänzend algotrading101.com/learn/walk-forward-optimization/ (2020-06-24)
[^20^]: arongroups.co – ICT Silver Bullet (Gate-Logik, "one move"-Disziplin, Fehlerkatalog inkl. DST/Spread), https://arongroups.co/technical-analyze/ict-silver-bullet-strategy/ (2026-04-06)

*Qualitätshinweis: Härteste Datenpunkte sind Secuora (transparent, negativ) und die beiden GitHub-Backtester (Code offen, Ergebnisse selbstberichtet). Alle Winrate-/PF-Claims von LuxAlgo, pinescriptforge, BAKOME, innercircletrader.net sind nicht auditiert — als Hypothesen für die eigene Replikation behandeln.*
