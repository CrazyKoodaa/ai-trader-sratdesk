# Deep-Dive Dimension 10: Gefilterte Mean-Reversion auf XAUUSD und EURUSD

**Recherche-Facet:** Vollständige, implementierbare Regel-Spezifikation für gefilterte Mean-Reversion (MR) auf XAUUSD/EURUSD für MT5-Bots (pymt5trade), Ziel PF > 1.5 OOS, ≥ 1:2 RR, Prop-Firm-tauglich.
**Methodik:** 20 gezielte Websuchen (EN/DE) + 2 Volltext-Deep-Dives (quant-signals RSI-Studie komplett extrahiert; GitHub XAUUSD-Referenz-Repo). Kontext: wide03 (RSI(2) = Equity-Phänomen, M5–M30 toxisch), wide06 (EURUSD = DLL-schonendstes Prop-Instrument), dim08 (HMM-Regime-Overlay).
**Stand der Recherche:** Quellen 2024–2026, Datumswerte bei den Quellen.

---

## 1. Die RSI-Studie (2.397 Trades) — vollständig extrahiertes Regelwerk

### 1.1 Identifikation und Kerndaten

**Claim:** Die im Wide-Report referenzierte Studie ist quant-signals.com "RSI Trading Strategy: Why It Fails (Data From 2,397 Trades)". Klassisches RSI-MR scheitert auf allen 12 Asset×TF-Kombinationen (2.397 Trades gesamt, 2020–2025, H1+D1); mit zwei Filtern (EMA200 + ADX<25) wird XAUUSD H1 zu PF 3,00 / +0,80R und EURUSD H1 zu PF 2,00 / +0,50R.
**Source:** Quant Signals — "RSI Trading Strategy: Why It Fails (Data From 2,397 Trades)"
**URL:** https://quant-signals.com/rsi-trading-strategy/
**Date:** 04.04.2026
**Confidence:** Mittel (unabhängiger Backtest-Blog, Regeln vollständig offengelegt, aber **keine Kosten** — "do not account for slippage, commissions, spreads"; gefilterte Samples nur 10–16 Trades → Autor selbst: "suggestive evidence... not definitive proof")

### 1.2 Exaktes Regelwerk (Zitat-Extraktion)

**Excerpt (Rules):**
> "Long entry: RSI(14) crosses below 30. Short entry: RSI(14) crosses above 70. Stop Loss: 1.5 × ATR(14) from entry. Take Profit: 2.0 × stop loss distance (1:2 risk-reward). Risk per trade: 1% of account."

**Excerpt (Filter):**
> "Filter #1: Only take LONG trades when price is above the EMA(200)… Only take SHORT trades when price is below the EMA(200)."
> "Filter #2: Only take trades when ADX(14) is below 25, indicating the market is NOT in a strong trend."

**WICHTIG für die RR-Frage (Auftragspunkt 3):** Die Studie nutzt **bereits 1:2 RR** (TP = 2 × SL-Distanz). Das "MR hat <1:2 RR"-Problem ist hier also konstruktiv gelöst: ATR-basierter Stop + 2R-Ziel statt klassischem "Exit am Mittelband/RSI 50". Die gefilterte Variante erreicht damit 50–60 % WR bei 1:2 RR → Erwartungswert +0,5R bis +0,8R. Breakeven-WR bei 1:2 = 33,3 % (s. [^10^]) — die gefilterten 50–60 % WR liegen deutlich darüber.

### 1.3 Ergebnistabellen (ungefiltert vs. gefiltert)

**Ungefiltert (Auszug):**

| Asset | TF | Trades | WR | PF | Expectancy |
|---|---|---|---|---|---|
| EURUSD | H1 | 268 | 33,2 % | 0,99 | −0,004R |
| EURUSD | D1 | 49 | 26,5 % | 0,72 | −0,204R |
| XAUUSD | H1 | 261 | 33,0 % | 0,98 | −0,012R |
| XAUUSD | D1 | 56 | 23,2 % | 0,60 | −0,304R |
| BTCUSD | H1 | 387 | 31,8 % | 0,93 | −0,046R |

**Gefiltert (EMA200 + ADX<25, nur H1 sinnvoll):**

| Asset | TF | Trades | WR | PF | Sharpe | Expectancy |
|---|---|---|---|---|---|---|
| XAUUSD | H1 | **10** | 60,0 % | **3,00** | 8,20 | +0,800R |
| EURUSD | H1 | **10** | 50,0 % | **2,00** | 5,02 | +0,500R |
| ETHUSD | H1 | 15 | 40,0 % | 1,33 | 2,09 | +0,200R |
| GBPUSD | H1 | 13 | 38,5 % | 1,25 | 1,61 | +0,154R |
| NAS100 | H1 | 14 | 35,7 % | 1,11 | 0,76 | +0,071R |
| BTCUSD | H1 | 16 | 18,8 % | 0,46 | −5,74 | −0,438R |

**Excerpt (Caveat, wörtlich):** "These results are based on small sample sizes (10-16 trades per asset). They are promising and directionally consistent, but should not be treated as statistically proven."

**Konsequenz:** Filter eliminieren ~95 % der Trades (268 → 10 auf EURUSD H1 über 2020–2025 ≈ 1 Trade/2,5 Monate). Für einen Prop-Bot ist das **zu wenig Frequenz als Standalone-Strategie** — die Studie selbst sagt: "expect very few — roughly 1 signal every 1-3 months per asset on H1. This is by design." → Praxis-Implikation: Filter-Schwellen im Walk-Forward etwas lockern (ADX<30, RSI 25/75→30/70-Band-Test) oder mehrere Instrumente parallel fahren (XAUUSD + EURUSD + GBPUSD).

**Schwester-Studie (gleiche Datenbasis, 8.693 Trades XAUUSD) bestätigt:** RSI-MR basic auf Gold D1 PF 0,60 (−0,304R), H1 PF 0,98; gefiltert H1 PF 3,00 / DD nur 1,0 %. Gleichzeitig: "The data conclusively demonstrates that trend-following approaches outperform mean-reversion methods when trading XAUUSD" (EMA 21/50 D1: PF 1,85) — d. h. MR auf Gold ist ein **Pullback-in-Trend-Phänomen** (EMA200-Bedingung!), kein klassisches Range-Fading. [^2^]

**Zusätzlicher Metabefund derselben Quelle (H1 vs. D1, 22.362 Trades):** MR ist die **einzige** Strategie-Kategorie, die auf H1 besser ist als D1 (Median-PF H1 1,12 vs. D1 0,65); "Mean reversion strategies that lose money on D1 can become profitable on H1 timeframes." ATR-Trailing-Stops "destroy capital on hourly timeframes". [^3^]

---

## 2. Weitere MR-Varianten mit dokumentierter Performance

### 2.1 Bollinger-Band-Reversion (Regelwerk + realistische Benchmarks)

**Claim:** BB(20, 2σ)-Reversion mit Regime-Filter, Rejection-Trigger und Time-Stop: realistische WR 58–65 %, PF 1,3–1,6, per-Trade ~1:1 R — ohne Filter ~45 % WR und "blowup waiting to happen".
**Source:** Crosstrade.io — "Bollinger Band mean reversion" (Strategie-Bibliothek mit vollständigem Regelwerk)
**URL:** https://crosstrade.io/learn/trading-strategies/bollinger-mean-reversion
**Date:** 14.04.2026
**Confidence:** Mittel (Regelwerk vollständig, Zahlen als "realistic ranges" deklariert, nicht als einzelner Backtest-Report)
**Excerpt (Regelwerk):**
> "1. Regime filter. Skip trades when the market is trending [ADX]. 2. Setup. Price touches or wicks through the outer Bollinger Band (20-period SMA, 2 standard deviations). 3. Rejection trigger. The setup bar must show rejection. 4. Entry. Market order at the next bar open after the trigger. 5. Stop. 1× ATR beyond the extreme of the rejection bar. 6. Target. The middle band (20 SMA). Optionally: scale half off at the middle band, trail the rest to the opposite outer band. 7. Time stop. If the trade hasn't hit target within 15 bars on a 5-minute chart (or 10 bars on a 15-minute), close it. Mean reversion that hasn't reverted is probably a trend day."
> "Why target the middle band instead of the opposite band? The middle Bollinger Band (20 SMA) is hit far more often than the opposite outer band. Targeting the middle produces a higher win rate."
> Bandbreiten-Empfehlung: "2σ is the standard… 1.5σ fires more often but each signal is lower quality. 2.5σ fires rarely but with stronger edge."

**Gegenprobe aus derselben Datenfamilie wie die RSI-Studie:** quant-signals BB-Test (2.054 Trades) zeigt BB als **Breakout**-Indikator (Squeeze) profitabler als als Reversion-Tool auf D1; EURUSD BB-Squeeze H1 PF 1,14, D1 PF 0,85; XAUUSD D1 PF 1,14. → BB-Reversion braucht zwingend den Range-Filter; BB-Breakout ist ein anderes Regime-Spiel (Schnittstelle zu dim08: Regime-Switch). [^4^]

### 2.2 Session-basierte MR: Asian-Session-Range-Fade

**Claim (positiv, Regelwerk):** Asian-Session-Fade (Master-Candle-Variante, explizit als Fade konstruiert): H1-Master-Candle (≥4 Bars innerhalb), dann auf M15 Fade, wenn Preis 5 Pips über/unter die Master-Candle-Range läuft; TP = Range-Größe zurück, SL = Range-Größe → 1:1 RR, braucht >50 % WR. Geeignete Paare: EURUSD, GBPUSD, USDCAD (Heimatbörse außerhalb Asiens).
**Source:** FXSSI — "Forex Strategies for Each Session" (Asian Session Scalping/Fade)
**URL:** https://fxssi.com/forex-strategies-by-session
**Date:** 29.04.2020
**Confidence:** Niedrig-Mittel (älter, keine Trade-Statistik; Regelwerk aber exakt implementierbar)

**Claim (Night-Scalper-Ökosystem, Zahlen):** Asien-Session-MR-EAs ("fades moves away from session VWAP or moving average") werden mit typischen WR 70–80 %, reine Range-Scalper 75–85 % WR beworben; Grid/Martingale-Hybride 90 %+ "until it doesn't". Konkrete Setup-Empfehlungen: Handelsfenster 21:00–06:00 GMT hart begrenzen ("Never let an Asian session EA trade into London"), News-Pause 30 min vor / 15 min nach High-Impact, Spread-Filter (z. B. max 2 Pips USDJPY), fester SL 20–30 Pips, Stops 10–15 Pips hinter Range-Grenze (Liquiditäts-Spikes).
**Source:** NewYorkCityServers — "Asian Session Forex Strategy: Low-Volatility Trading Guide"
**URL:** https://newyorkcityservers.com/blog/asian-session-forex-strategy
**Date:** 05.05.2026
**Confidence:** Niedrig-Mittel (VPS-/Hosting-Anbieter, kommerzielle Nähe; EA-WR-Zahlen = Marketing-Kategorie; Setup-Regeln plausibel und konkret)

**Wichtige Negativ-Evidenz (Session-Breakout als Gegenstück):** QuantifiedStrategies London-Breakout EURUSD (Range 03:00–08:00 London, Entry 08:00–11:00, Time-Exit 12:00–17:00): Long-Breakout verliert Geld, Short-Breakout ~Null — "it makes sense to fade the breakout" (d. h. Fade-Richtung auf EURUSD intraday plausibler als Breakout-Richtung, aber ohne Zusatzfilter selbst der Fade nicht belegt). [^5^] Neuester 24/25-GitHub-Backtest (wide03 [^26^]): EURUSD flat. → Session-Fade auf EURUSD ist eine **Hypothese mit Gegenwind**, kein belegter Edge; nur mit Range-Qualitätsfilter (Range-Größe vs. ADR, ADX, HMM-State) testen.

### 2.3 VWAP-Reversion

**Claim:** VWAP-Band-Reversion (Fade ab ±2σ zurück zum Session-VWAP): geometrisch eingebautes RR ≥ 2–3:1, wenn Entry am 1,5–2σ-Band, Stop knapp hinter dem 2σ-Band/Session-Extrem, Ziel = VWAP. Konkretes NQ-Beispiel: Entry 1,5σ, Stop hinter 2σ (~15 Punkte Risiko), Ziel VWAP (~45 Punkte) = **3:1 RR auf dem Primärziel**; 25–30 % Runner mit Trailing knapp hinter VWAP Richtung gegenüberliegendes 1σ-Band/POC. Regime-Filter mandatory: Skip bei Trendtagen, News, ersten 30 Min, steil fallendem/steigendem VWAP.
**Sources:** (a) TraderVerdict — "VWAP Mean Reversion: Our Bread-and-Butter NQ Scalping Setup", https://traderverdict.com/blog/vwap-mean-reversion-nq (o.D.) — **Confidence: Mittel** (Praktiker-Regelwerk mit R-Mathe, keine Backtest-Tabelle). (b) Crosstrade.io — "VWAP reversion strategy", https://crosstrade.io/learn/trading-strategies/vwap-reversion, 14.04.2026 — "Works best on ES and NQ during non-event days… It fails badly on strong trend days — a regime filter is mandatory." Regeln: Setup 2× Session-StdAbw vom VWAP; Rejection-Candle-Trigger; Entry nächste Bar; Stop 1×ATR hinter Trigger-Extrem; Ziel VWAP, optional halb am VWAP + Trail. **Confidence: Mittel.**
**Excerpt (RR-Mathe, wörtlich):** "The math on a typical VWAP mean reversion NQ trade: entry at 1.5 SD, stop at 2 SD, target at VWAP… the stop is roughly 15 points and the target is roughly 45 points… That's a 3:1 risk-reward on the primary target. The runner extends it further."

**Forex-Übertragbarkeit (wichtig):** VWAP auf FX nutzt **Tick-Volumen** (kein zentrales Volumen) — "In forex, brokers show tick volume, not centralized volume. Treat VWAP as a proxy." [^6^] Zusätzlich wide03-Befund: VWAP-Edge ist instrumenten-/session-spezifisch (QQQ 9:45–11:30 ET PF 2,08; BTC PF 0,40–0,99). Für XAUUSD/EURUSD ist VWAP-Reversion daher **nicht vorbestätigt** — als dritte Variante im WF-Test mitführen, aber niedrigere Priorität als RSI+Filter und BB-Reversion. Parameter-Template (MomentumIQ, NSE VWAP-MR): `deviation_entry 2.0 (Range 1.0–4.0)`, `deviation_exit 0.5`, `atr_mult Stop 1.5 (0.5–3.0)`, Risiko 0,8 %/Trade — als WF-Raster direkt übernehmbar. [^7^]

### 2.4 Overnight-Reversion

**Befund:** Keine belastbare, instrumentenspezifische Backtest-Studie für XAUUSD/EURUSD-Overnight-MR gefunden (3 gezielte Suchen, u. a. "overnight mean reversion strategy forex EURUSD backtest", "overnight reversion gold XAUUSD London open fade backtest"). Was existiert: (a) Night-Scalper-Kategorie (s. 2.2) = de facto Overnight-MR in der Asien-Session; (b) akademischer Rahmen via OU/Half-Life (s. 2.5); (c) Prop-Constraint: FTMO-Standard-Accounts müssen Freitag flach sein (wide06) → Overnight-Holding Mo–Do erlaubt, Wochenende nicht. **Confidence: Niedrig — bewusst als Lücke dokumentiert; nicht als Bot-Baustein empfehlen.**

### 2.5 Statistische MR-Prüfgrößen (OU/Half-Life/Hurst) als Regime- und Lookback-Input

**Claim:** Half-Life der Mean-Reversion (OU-Prozess, λ aus OLS-Regression ΔX auf X(t−1), half_life = −ln2/λ) ist die robusteste Schätzung der optimalen Haltezeit und Lookback-Länge: "This half-life can be used to determine the optimal holding period for a mean-reverting position. Since we can make use of the entire time series… the estimate for the half-life is much more robust than can be obtained directly from a trading model." (Ernest Chan, Quantitative Trading). Praxis-Faustregel (ReignEdge Handbook, inkl. Python-Code): "A half-life of 3 bars → fast reversion, scalp it. A half-life of 200 bars → barely reverting, don't."
**Sources:** (a) Ernest Chan — "Quantitative Trading" (Buch-PDF), OU-Formel + GLD/GDX-Beispiel, https://nashnw.myqnapcloud.com:8083/download/160/pdf/160.pdf — **Confidence: Hoch (Primärliteratur)**. (b) ReignEdge — "Market Regime Detection Handbook" (Half-Life-Code, ADF als MR-Detektor, Variance-Ratio-Kurve), https://www.reignedge.com/library/regime-detection-handbook (o.D.) — **Confidence: Mittel-Hoch**. (c) flare9xblog (Hurst H<0,5 = MR; Lookback = Half-Life verbesserte Equity von 700 % auf 1.400 % im Beispiel), https://flare9xblog.wordpress.com/tag/half-life-of-mean-reversion/ — **Confidence: Mittel**.
**Excerpt (Code, ReignEdge):**
```python
def half_life(series):
    lag = series[:-1]; delta = np.diff(series)
    beta = OLS(delta, add_constant(lag)).fit().params[1]
    return -np.log(2) / beta
```
**Nutzung für die Bots:** rollierende Half-Life (Fenster 60–120 H1-Bars) als (a) Instrumenten-Gate (nur handeln, wenn half_life < MaxBars × 0,5), (b) Time-Stop-Setzung (Time-Stop ≈ 1–2 × Half-Life), (c) Lookback-Adaptivität für RSI/BB-Periode.

---

## 3. Das RR-Problem: MR mit ≥ 1:2 RR konstruieren — dokumentierte Ansätze

**Kernbefund 1 (Strukturelle Lösung, aus der RSI-Studie selbst):** 1:2 RR ist bei MR kein Widerspruch, wenn das Ziel **nicht** der Mittelband/RSI-50 ist, sondern TP = 2 × ATR-Stop-Distanz. Die gefilterte Variante erreicht damit WR 50–60 % ≫ Breakeven-WR 33,3 % bei 1:2 [^1^][^10^]. Klassisches "Exit am Mean" (~1:1 R bei 58–65 % WR, PF 1,3–1,6 [^8^]) und "2R-Ziel mit Filter" (PF 2–3, aber kleines Sample) sind zwei dokumentierte Design-Punkte — beide im WF gegeneinander testen.

**Kernbefund 2 (Geometrische Lösung, VWAP/BB):** Entry am 1,5–2σ-Band + Stop knapp hinter 2σ/Session-Extrem ergibt strukturell 2–3:1 RR zum Mean (traderverdict: 15 Pt Stop vs. 45 Pt Ziel = 3:1). [^9^] Gleiche Logik bei BB-Reversion: Stop 1×ATR hinter Rejection-Extrem, Ziel Mittelband — RR hängt von Bandbreite ab (breite Bänder = besseres RR, aber seltener).

**Kernbefund 3 (Skalierungs-Pläne, dokumentiert):**
- Blofin/Crypto-Range-MR: **50 % am Mid-Range (TP1 ≈ 1,6R), 30 % an gegenüberliegender Range-Kante (TP2 ≈ 3,2R), 20 % Runner mit Trail am Mid-Range; Blended ≈ 1,76R bei Volltreffer.** "Intra-range moves revert to mid-range 60-70% of the time." [^11^]
- Crosstrade BB: "scale half off at the middle band, trail the rest to the opposite outer band." [^8^]
- Crosstrade VWAP: "half off at VWAP, trail the rest to the other side of VWAP." [^12^]
- DE-Praxisbeleg (InsiderWeek DAX-Beispieltrade): Teilgewinn 50 % bei +20 Pt, SL der Restposition auf Break-Even, Rest via Trailing (10 Pt) oder Zweitziel — Gesamt-CRV steigt von 0,8 (Teil 1) auf 1,6 (Gesamt). [^13^]

**Kernbefund 4 (Warnung — realisiertes RR sinkt durch Skalierung/Trailing):** ForTraders RR-Studie: "Scale out half your position at 1R and trail a stop on the rest, and the average realized R multiple… typically lands around 1.2-1.4 — even on a system marketed and backtested at 1:3… a system needing a 25% win rate to break even at 1:3 planned suddenly needs 42-45% at a 1.2-1.4 realized average." Breakeven-WR-Tabelle: 1:1 → 50 %, 1:1,5 → 40 %, 1:2 → 33,3 %, 1:3 → 25 % (real ~1–3 pp höher nach Kosten). [^10^]
**Konstruktions-Regel daraus:** Wenn "min. 1:2 RR" als **durchschnittlich realisiertes R** gemeint ist → Teilgewinn-Pläne unterschreiten das systematisch; dann besser: Ganzposition mit TP = 2R (Studien-Design) ODER Skalierung so kalibrieren, dass Blend ≥ 2R (z. B. 40 % bei 1,5R + 60 % Runner-Ziel 2,7R). Breakeven-/Trail-Mechanik separat im WF abprüfen (wide03: Trailing zerstörte VWAP-Trend-Edge, PF 0,76; fixer 2×ATR-Stop positiv — H1-MR speziell: quant-signals "ATR trailing stops fail on H1" [^3^]).

**Kernbefund 5 (Time-Stop als RR-Schutz):** "Mean reversion that hasn't reverted is probably a trend day" — Time-Stop 10–15 Bars (M15/M5) bzw. half-life-basiert (s. 2.5) verhindert, dass Verlierer bis zum Voll-Stop laufen; QuantifiedStrategies-Methodik: "Test exit with time stops to verify robustness." [^8^][^14^]

---

## 4. Wann MR NICHT handeln — Regime-Filter und HMM-Schnittstelle (dim08)

**Dokumentierte Nicht-Handels-Bedingungen (Konsens über Quellen):**

| Filter | Regel | Quelle |
|---|---|---|
| Trend-Regime | ADX(14) ≥ 25 → kein MR-Trade (RSI-Studie: zentraler Filter; backtrex: "ADX-Filter… can reduce drawdown by 30 to 40 %") | [^1^][^15^] |
| Trendrichtung | MR-Long nur über EMA200, Short nur darunter (Pullback-in-Trend-Logik; kein Fading gegen den D1-Trend) | [^1^] |
| Volatilitäts-Regime | ATR(14) über seinem 20-Perioden-Mittel → keine MR-Signale (hochvolumige direktionale Phasen); fallende ATR = MR-freundlich, ATR-Spike = Ausdehnungsrisiko | [^15^][^16^] |
| Bandbreiten-Regime | BB weiten sich schnell → "stand aside (trend risk)" | [^16^] |
| VWAP-Slope | Steiler VWAP-Anstieg/-Fall = Trendtag → kein VWAP-Fade; flacher VWAP = Equilibrium | [^7^] |
| Zeitfenster | Erste 30 Min der Session, News-Fenster (±2–5 Min Prop-Regeln; Asien-EA: −30/+15 min), Trendtage, F&O-Expiry | [^7^][^17^] |
| Session-Gate | Asien-MR hart bei London-Open beenden; Gold-Asien = "tot", Range-Drift | [^17^], wide06 |
| Half-Life-Gate | half_life > Schwellwert (z. B. >50 % des Time-Stop-Fensters) → Instrument aktuell nicht MR-fähig | [^18^] |
| Hurst-Gate | H ≥ 0,5 (Random Walk/Trend) → MR pausieren; H < 0,5 = MR-Regime | [^19^] |

**HMM-Schnittstelle (dim08, dort belegt):**
- dim08 empfiehlt **2-State GaussianHMM** (BIC-Optimum auf 4 FX-Paaren), Features = Returns + log-Vol/log-ATR, kausale Inferenz (`predict(returns)[-1]`), Expanding-Window mit periodischem Re-Fit (Refit-Kadenz = getesteter Parameter).
- dim08-XAUUSD-Beleg (rahulsp.com, M1-Gold, mit Spread): Kalman-MR PF 1,34 → **+HMM-Filter PF 1,42**; ATR-Median-Proxy PF 1,31 — HMM nur marginal besser als simpler Proxy, Autor warnt vor Lookahead/WF-Degradation. → **Design-Entscheidung: HMM UND ADX<25/ATR-Perzentil als zwei ablösbare Regime-Arme im WF testen (Ablations-Design aus dim08 übernehmen).**
- Konkrete Schnittstelle für den MR-Bot: `regime_state ∈ {range/low-vol, trend/high-vol}` bzw. `P(range)` als weiches Gate (LuxAlgo-Pattern aus dim08-Suche: "exposure scales with the probability of the favorable state instead of flipping on a hard label, which softens whipsaw around regime boundaries" [^20^]). Mapping: HMM-State "ranging/low-vol" ≈ Bedingung ADX<25 ∧ ATR unter Median — die klassischen Filter sind die **Proxy-Fallbacks**, der HMM der probabilistische Layer darüber. Trend-State → MR aus, (optional) Übergabe an Trend-Modul (dim-übergreifender Regime-Switch, wide03-Empfehlung 4).
- LuxAlgo-Nutzungsmuster (belegt): "trend-following logic is enabled in the trending state and mean-reversion logic in the quiet state, with high-volatility states treated as stand-aside." [^20^]

---

## 5. Parameter-Räume für Walk-Forward

**WFO-Methodik (belegt):** Breite, logische Ranges statt Mikro-Tuning ("If you only test a Moving Average between 19 and 21, you aren't optimising; you are micro-tuning. Use broad, logical ranges (e.g., 10-200)"), grobe Step-Sizes ("Moving in increments of 1… is noise mining"), Plateau-Auswahl statt Peak ("Choose parameters that perform well across nearby values"). OOS-Reserve 30 % (neueste Daten); Abbruchkriterium: OOS-Drop > 40 % vs. IS = overfit. Mindest-Sample: ≥ 200 Trades Basis-Signifikanz, 300–500 über 3–5 Jahre und mehrere Regime ideal; "< 100 Trades cannot distinguish genuine edge from random variation." Runde Parameterwerte bevorzugen. [^21^][^15^]

**Konkrete WF-Raster pro Variante:**

| Parameter | Variant A: RSI+Filter (Studie) | Variant B: BB-Reversion | Variant C: VWAP-Band-Reversion |
|---|---|---|---|
| Signal-Periode | RSI: {7, 10, 14, 21} | BB-Periode: {14, 20, 34} | — (Session-VWAP fix) |
| Signal-Schwelle | OS/OB: {(20,80), (25,75), (30,70), (35,65)} | σ: {1,5; 2,0; 2,5} | Entry-Deviation: {1,5; 2,0; 2,5}σ (Quelle-Range 1,0–4,0 [^7^]) |
| Trend-Filter | EMA: {100, 150, 200} (nur Richtungsbias) | optional EMA200-Bias | optional EMA200-Bias |
| Regime-Filter | ADX(14) < {20, 25, 30} **oder** HMM-Arm (dim08) | ADX < {20, 25, 30} + ATR<MA20(ATR) | ADX < {20, 25, 30} + VWAP-Slope-Filter |
| Stop | ATR(14) × {1,0; 1,5; 2,0} | 1×ATR hinter Rejection-Extrem; Mult {0,75; 1,0; 1,5} | ATR-Mult {0,5; 1,0; 1,5; 2,0} (Quelle-Range [^7^]) |
| Ziel / RR | TP = {1,5; 2,0; 2,5} × SL **und** Alternativ-Arm "Exit RSI 50 / Mittelband" | TP1 Mittelband (50 %), Runner Gegenband — **und** Alternativ-Arm TP = 2×SL | TP = VWAP (Exit-Deviation {0; 0,5}σ), Runner optional |
| Time-Stop | {24, 48, 72} H1-Bars bzw. {1; 2} × roll. Half-Life | {10, 15} Bars (M15) / Half-Life-basiert | Session-Ende spätestens |
| Session-Gate | London+NY (07:00–17:00 UTC) / Asien-Fenster separat | Asien (00:00–07:00 UTC) vs. Overlap | Overlap 13:00–17:00 UTC |
| Risiko/Trade | 0,5 % (Prop-DLL) — Studie nutzte 1 %, für Prop halbieren | 0,5 % | 0,5–0,8 % [^7^] |

**Zeitrahmen-Empfehlung (aus Evidenz):** H1 ist der MR-Arbeits-TF (einzige Kategorie mit H1 > D1 [^3^]); M5–M30 toxisch nach Kosten (wide03); D1-MR auf XAUUSD katastrophal (PF 0,60 [^1^][^2^]). WF-Fenster: Daten 2020–2025+ (Studien-Periode), IS/OOS z. B. 24/6 Monate rollierend, anchored oder rolling — mit dem dim08-Caveat, dass HMM-Refit-Kadenz selbst WF-Parameter ist.

---

## 6. IMPLEMENTIERUNGS-SPEZIFIKATION

**Bot "FilteredMR" (XAUUSD + EURUSD, MT5/pymt5trade) — Primärspezifikation (Variant A, direkt aus [^1^]):**

```
INSTRUMENTE:   XAUUSD (Haupt), EURUSD (Zweit, DLL-schonend); optional GBPUSD/ETHUSD WF-Nebenarm
TIMEFRAME:     H1 (Signal + Execution); D1 nur für EMA200-Kontext optional
SESSION:       Entries nur 07:00–20:00 UTC (XAUUSD Overlap-Fokus 13:00–17:00 UTC);
               News-Blackout ±2 min (Funded) / ±5 min konfigurierbar; Freitag-Flat-Regel (FTMO)
SIGNAL:        RSI(14) Cross unter 30 → LONG-Kandidat; Cross über 70 → SHORT-Kandidat
FILTER 1:      Long nur wenn Close > EMA(200, H1); Short nur wenn Close < EMA(200, H1)
FILTER 2:      ADX(14, H1) < 25  (WF-Arm B: ADX < {20,30}; WF-Arm C: HMM-2-State "ranging" statt ADX)
ENTRY:         Market-Order zum Open der nächsten H1-Bar nach Signal-Bar (kein Intrabar-Lookup)
STOP:          Entry ∓ 1,5 × ATR(14, H1)
TARGET:        Entry ± 2,0 × Stop-Distanz  (= 1:2 RR, Studien-Design)
TIME-STOP:     48 H1-Bars (WF: {24,72}); optional max(1, 2×roll. Half-Life(H1, Fenster 120))
RISIKO:        0,5 % Equity/Trade; max 1 offene Position je Instrument; Daily-Loss-Cap 1,5 %
               (DLL-Puffer unter FTMO 3–5 %); kein Martingale/Grid/Adding
KOSTENMODELL:  EURUSD 0,0–0,2 Pip Spread + $6 RT; XAUUSD $0,12–0,25 Spread + $6 RT;
               Slippage EURUSD 1 Pip, XAUUSD 3–10 Pips (News bis $0,60 Spread-Widening)
ERFOLGSKRITERIEN OOS: PF > 1,5; realisiertes Ø R ≥ +0,3; WR ≥ 40 % (Puffer über Breakeven 33–36 %);
               ≥ 30 OOS-Trades je Instrument (sonst "suggestive", nicht deploybar)
```

**Variant B (BB-Reversion, Sekundärarm):** BB(20, 2σ, H1/M15) Touch/Wick + Rejection-Candle (Close zurück innerhalb des Bands); Entry nächste Bar; Stop = Extrem der Rejection-Bar ∓ 1,0×ATR(14); TP1 = Mittelband (50 % schließen), Runner → Gegenband mit Break-Even-Stop nach TP1; Time-Stop 10–15 Bars (M15) bzw. 24–48 (H1); Filter: ADX(14) < 25 ∧ ATR(14) < SMA20(ATR) ∧ keine schnelle Band-Erweiterung. RR-Arm B2: Ganzposition TP = 2×SL (Vergleichsarm gegen Skalierung — wegen Realized-R-Verfall [^10^]).

**Variant C (VWAP-Band-Reversion, experimentell):** Session-VWAP (UTC-Tag, Tick-Volumen — als Proxy deklariert [^6^]); Entry bei Touch ±2σ-Band + Rejection-Candle, nur Overlap 13:00–17:00 UTC, VWAP-Slope flach (|Slope| < Schwellwert, WF), ADX < 25; Stop 0,5–1,0×ATR hinter Trigger-Extrem/2σ-Band; TP = VWAP (strukturell ~2–3:1 [^9^]); harter Exit Session-Ende.

**Regime-Layer (Schnittstelle dim08):** Zwei austauschbare Arme — (1) Proxy: ADX<25 ∧ ATR-Unter-Median; (2) HMM: GaussianHMM(n_components=2, covariance_type="full", n_iter=1000) auf H1-Features [log-Ret, log-ATR], Fit-Fenster + Refit-Kadenz als WF-Parameter (Start: 90 Tage Fit, wöchentlicher Refit), Gate = letzter Viterbi-State ∈ {ranging} **oder** weiches Gate P(ranging) > 0,6. MR nur im Range-State; Trend-State → Bot pausiert (Übergabe an Trend-Bot = separates Modul). Ablations-Pflicht: Proxy vs. HMM vs. ohne Filter.

**Nicht handeln (harte Gates):** ADX ≥ 25 (bzw. HMM-Trend-State) · ATR über 20er-Mittel · News-Fenster · erste 30 Min nach Session-Start (Variante C) · Friday-Flat (FTMO Standard) · Spread > Schwellwert (EURUSD 2 Pips / XAUUSD $0,60) · Half-Life > 50 % des Time-Stops · Tages-Verlust-Limit erreicht.

**Statistische Leitplanken (anti-overfitting):** Studien-Kernsample (10–16 gefilterte Trades) ist NICHT signifikant — PF 2–3 als Hypothese, nicht als Zielvorgabe behandeln; WF-Mindestsample ≥ 200 Trades gesamt / ≥ 30 je OOS-Fenster; OOS-Drop > 40 % = verwerfen; runde Parameter bevorzugen; Plateau-Auswahl; Balance-DD UND Equity-DD getrennt tracken (MDPI-Lektion, wide03). Kostenpflicht: Studie ist kostenfrei gerechnet — EURUSD-Edge (+0,5R bei ~15–25 Pip-Trades) überlebt ~2 Pips Round-Trip-Kosten; XAUUSD-Signal (~$7–12 ATR-basierte Stops auf H1) überlebt $0,3–0,9 Round-Trip — aber das muss der eigene Backtest beweisen.

---

## 7. Quellen

[^1^]: Quant Signals — "RSI Trading Strategy: Why It Fails (Data From 2,397 Trades)", 04.04.2026, https://quant-signals.com/rsi-trading-strategy/
[^2^]: Quant Signals — "XAUUSD Trading Strategies: 3 Backtested Approaches for Gold (8.693 Trades)", 04.04.2026, https://quant-signals.com/xauusd-trading-strategies/
[^3^]: Quant Signals — "H1 vs D1 Trading: Which Timeframe Wins? (22.362 Trades, 136 Backtests)", 04.04.2026, https://quant-signals.com/h1-vs-d1-trading-strategy/
[^4^]: Quant Signals — "Bollinger Bands Trading Strategy: Backtest Results Across 6 Markets (2.054 Trades)", 04.04.2026, https://quant-signals.com/bollinger-bands-trading-strategy/
[^5^]: QuantifiedStrategies — "London Breakout Strategy: Rules and Backtest Performance" (EURUSD, Time-Exits 12:00–17:00), 27.01.2026, https://www.quantifiedstrategies.com/london-breakout-strategies/
[^6^]: ForexTester — "VWAP Indicator: Guide to VWAP Trading Strategies" (Tick-Volumen-Caveat Forex; VWAP-Band-MR-Regeln), 26.05.2026, https://forextester.com/blog/vwap/
[^7^]: MomentumIQ — "VWAP Mean Reversion Strategy" (Parameter-Tabelle: deviation_entry 2.0 [1.0–4.0], deviation_exit 0.5, atr_mult 1.5 [0.5–3.0], Risiko 0,8 %), 13.05.2024, https://www.momentumiq.in/strategies/vwap-mean-reversion
[^8^]: Crosstrade.io — "Bollinger Band mean reversion" (Regelwerk, WR 58–65 %, PF 1,3–1,6, Time-Stop), 14.04.2026, https://crosstrade.io/learn/trading-strategies/bollinger-mean-reversion
[^9^]: TraderVerdict — "VWAP Mean Reversion: Our Bread-and-Butter NQ Scalping Setup" (3:1-RR-Mathe, Runner-Logik), o.D., https://traderverdict.com/blog/vwap-mean-reversion-nq
[^10^]: ForTraders — "Risk-Reward Ratio: How to Use It to Your Advantage" (Breakeven-WR-Tabelle; Realized-R 1,2–1,4 bei Skalierung), 29.08.2026, https://fortraders.com/blog/risk-reward-ratio-how-to-use-it-to-your-advantage
[^11^]: Blofin Academy — "Mean Reversion in Crypto: How Range Traders Find High-Probability Entries" (50/30/20-Skalierung, Blended 1,76R), 23.04.2026, https://blofin.com/en/academy/education/mean-reversion-in-crypto
[^12^]: Crosstrade.io — "VWAP reversion strategy" (2σ-Setup, 1×ATR-Stop, Regime-Filter-Pflicht), 14.04.2026, https://crosstrade.io/learn/trading-strategies/vwap-reversion
[^13^]: InsiderWeek (DE) — "DAX Trading Strategien" (Teilgewinn 50 % + BE-Stop + Trailing; CRV 0,8→1,6), 27.04.2023, https://insider-week.com/de/articles/die-besten-strategien-dax/
[^14^]: QuantifiedStrategies — "Mean Reversion Trading Strategies" (Time-Exit-Robustheit; "sell on strength"; Stop-Loss-Dilemma), 09.02.2025, https://www.quantifiedstrategies.com/mean-reversion-trading-strategy/
[^15^]: Backtrex — "Mean reversion strategy backtesting: method and indicators" (ATR<MA20-Filter; ADX<25 senkt DD 30–40 %; OOS-30-%-Regel; 200–500-Trade-Mindestsample; runde Parameter), 25.07.2026, https://backtrex.com/en/blog/mean-reversion-strategy-backtesting-guide
[^16^]: ForexTester — "Mean Reversion Trading: Understanding Strategies & Indicators" (Band-Erweiterung = stand aside; Stops 1–2×ATR; Skalierung am MA), 26.05.2026, https://forextester.com/blog/mean-reversion-trading/
[^17^]: NewYorkCityServers — "Asian Session Forex Strategy" (Night-Scalper-MR WR 70–80 %; Fenster 21:00–06:00 GMT; News-Pause; Spread-Filter; SL 20–30 Pips), 05.05.2026, https://newyorkcityservers.com/blog/asian-session-forex-strategy
[^18^]: Ernest Chan — "Quantitative Trading" (OU-Modell, Half-Life = ln2/θ als optimale Haltezeit, GLD/GDX-Beispiel), Buch-PDF o.D., https://nashnw.myqnapcloud.com:8083/download/160/pdf/160.pdf
[^19^]: ReignEdge — "Market Regime Detection Handbook" (Half-Life-Python-Code; ADF als MR-Detektor; "half-life 3 bars → scalp it, 200 bars → don't"), o.D., https://www.reignedge.com/library/regime-detection-handbook
[^20^]: LuxAlgo — "Hidden Markov / Markov-switching Regimes" (MR im Quiet-State; High-Vol = stand-aside; weiches Sizing via State-Probability), o.D., https://www.luxalgo.com/library/concept/hidden-markov-markov-switching-regimes/
[^21^]: AronGroups — "What Is Walk Forward Optimisation in Trading?" (breite Ranges, Step-Size, Plateau statt Peak), o.D., https://arongroups.co/forex-articles/walk-forward-optimisation-in-trading/
[^22^]: FXSSI — "Forex Strategies for Each Session" (Asian-Fade Master-Candle-Regelwerk, 1:1 RR), 29.04.2020, https://fxssi.com/forex-strategies-by-session
[^23^]: GitHub ilahuerta-IA — "backtrader-pullback-window-xauusd" (5J-Backtest, PF 1,64, WR 55,4 %, DD 5,8 %, SL 2,5×ATR / TP 12×ATR, Session-Filter — Referenz-Implementierung Gold, aber Trend/Pullback nicht MR), 11.10.2025, https://github.com/ilahuerta-IA/backtrader-pullback-window-xauusd
[^24^]: QuantifiedStrategies — "Hidden Markov Model Market Regimes" (HMM als Regime-Switch: MR im Sideways-State; Walk-Forward-Retraining), 01.02.2026, https://www.quantifiedstrategies.com/hidden-markov-model-market-regimes-how-hmm-detects-market-regimes-in-trading-strategies/
[^25^]: Kontext-Reports: trading_strategies_wide03.md (TF-Toxizität M5–M30; RSI(2)=Equity-Phänomen), trading_strategies_wide06.md (EURUSD DLL-schonend; ADR-Tabelle), trading_strategies_dim08.md (HMM-Overlay: 2-State BIC, XAUUSD Kalman-MR PF 1,34→1,42, Ablations-Design)
