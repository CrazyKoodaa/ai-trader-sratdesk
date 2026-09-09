# Deep-Dive Dimension 01: XAUUSD H4 Trend-Pullback-Strategie

**Recherche-Datum:** 2026 | **Eigene Suchen:** 14 gezielte Queries (EN/DE) + 4 Tiefenlektüren via web_open_url (quant-signals ADX-Studie, GitHub maker-tung/xauusd-trend-follow, QuantifiedStrategies Pullback, AlchemyMarkets Turtle-Guide) | **Vorarbeit:** trading_strategies_wide03.md (Indikator-Facet), trading_strategies_wide06.md (Instrumenten/Prop-Facet)
**Scope:** H4/D1-Trend-Bias (SMA200 / Donchian / DI-Cross / Supertrend) + Pullback-Entry H1/H4 (20-EMA / Fib 38.2–61.8 / Swing-Level) + ATR-Stops + Time-Exit. Ziel: PF > 1.5 OOS, RR ≥ 1:2, Prop-tauglich (0,5 % Risiko/Trade, EOD-DD, News-Blackout).

---

## 1. Executive Summary

Die am besten dokumentierte mechanische XAUUSD-Trend-Variante ist der **ADX-DI-Crossover auf D1** (PF 1.54, WR 43,6 %, MaxDD 5,0 %, 101 Trades; Regeln exakt publiziert [^1^]). Der **ehrlichste Prop-Referenz-Code** ist maker-tung/xauusd-trend-follow (MQL5, H1, EMA200-Filter + 3 OR-Trigger, SL 1.25×ATR, TP 6×ATR, Time-Exit 60 Bars, FTMO-Circuit-Breaker; PF nur ~1.17 bei 25,8 % WR über 4 Jahre Real-Ticks — **wichtige Realitäts-Kalibrierung**: PF > 1.5 OOS ist ambitioniert) [^2^]. Pullback-Entry-Regeln (20-EMA-Tag + Reversal-Kerze, Fib 38.2–61.8 Golden Zone, Swing-Break-Invalidierung) sind detailliert dokumentiert, aber die harten Statistiken dazu stammen aus Marketing-nahen Quellen (Confidence niedrig-mittel) [^5^][^6^][^7^]. Donchian/Turtle liefert das Regel-Gerüst (20/55-Breakout, 2N-Stop, 25/350-EMA-Filter, 80-Bar-Time-Exit), ist aber OOS seit 2007 massiv degradiert (CAGR 2–10 % statt 29–58 %) [^3^][^4^]. Supertrend XAUUSD: Praxis-Konsens ATR(10–14)/Mult 2.5–3.0 auf H4/D1; D1-Backtests BTC PF 1.51, Gold plausibel aber kein harter Gold-Beleg [^8^][^9^]. Kritische Implementierungs-Lektionen: **ADX als Filter auf andere Signale zerstört PF (XAUUSD 1.54 → 0.40)** [^1^]; Session-Filter (Gold ist 3,5× session-sensitivster Markt; Overlap-Std. 83 Pips vs. 24 Pips Asien) [^10^]; News-Spread-Widening 20 Cents → $1–3+ um NFP/FOMC/CPI [^11^][^12^].

---

## 2. Kern-Claims mit Evidenz-Blöcken

### CLAIM A — DI-Crossover D1 auf XAUUSD: exaktes Regelwerk + Kennzahlen (Basis-Variante 1)
- **Claim:** ADX-DI-Crossover (nicht ADX-Filter) auf D1 erreicht auf XAUUSD PF 1.54, WR 43,6 %, MaxDD 5,0 %, 101 Trades, Expectancy positiv; 2:1 RR, SL = 2.0×ATR.
- **Source:** quant-signals.com — "ADX Trading Strategy: How to Filter Weak Trends (Backtest Data)"
- **URL:** https://quant-signals.com/adx-trading-strategy/
- **Date:** 04.04.2026
- **Excerpt (Regeln, Long):** "DI+ crosses above DI- … ADX reading above 20 … Price above 5-period momentum average … Stop loss: 2.0 × ATR below entry … Take profit: 2:1 reward-to-risk ratio." Short analog. Standard ADX(14), 3-Perioden-ADX-Signalbestätigung.
- **Excerpt (Kennzahlen):** "Gold (XAUUSD) emerged as the second-best performer after Bitcoin. The ADX DI Crossover strategy produced 1.54 profit factor with 43.6% win rate across 101 daily trades. Maximum drawdown remained exceptionally low at 5.0%."
- **Gegenbefund (gleiche Studie, kritisch!):** ADX-als-Filter auf EMA-Cross **reduziert** XAUUSD PF von 1.54 auf **0.40** bei −82 % Trade-Frequenz; H1-Varianten teils negative Expectancy. "Use ADX DI crossovers instead of trend filtering … Focus on daily timeframes … Prioritize trending assets: Crypto and gold."
- **Confidence:** Mittel-Hoch. Unabhängiger Backtest-Blog, 4.236 Trades, 24 Varianten, konsistente Methodik; aber: keine Kostenmodellierung detailliert offengelegt ("do not include transaction costs, slippage" im Disclaimer → PF 1.54 ist **brutto**, muss mit Kosten nachgerechnet werden), kein expliziter IS/OOS-Split.

### CLAIM B — FTMO-konformer Open-Source-Referenz-EA: Regelwerk + ehrliche 4-Jahres-Kennzahlen (Code-Vorlage)
- **Claim:** Ein produktionsorientierter MQL5-EA für XAUUSD H1 (long-only) mit EMA200-Trend-Gate, ADX(14)≥20-Filter, 3 ODER-Triggern (MACD-Cross, Stoch-Cross <60, EMA9/21-Cross), SL 1.25×ATR(14), TP 6.0×ATR (~4.8:1 RR), Time-Exit nach 60 H1-Bars (~2,5 Tage), Risiko 0,25 %/Trade, Circuit-Breaker 4 % Tagesverlust / 8 % Max-DD erreicht über Jan 2022–Mai 2026 (100 % Real-Ticks, FTMO-Server-Feed, modellierter Spread 0.30): +54,8 %, PF ~1.17, WR 25,8 %, Max-Equity-DD 6,22 %, Sharpe ~2.42, ~1.354 Trades, Ø Haltedauer 5,4 h.
- **Source:** GitHub maker-tung/xauusd-trend-follow (README, Architektur-Diagramm, Parameter-Block, MFE/MAE-Analyse)
- **URL:** https://github.com/maker-tung/xauusd-trend-follow
- **Date:** 26.05.2026
- **Excerpt (Trend-Gate):** "Price[close, shift=1] > EMA(200)[shift=1] … All entry signals are blocked unless price is above the 200-period EMA."
- **Excerpt (RR-Logik):** "SL = Ask − (InpSL_ATR × ATR[1]); TP = Ask + (InpTP_ATR × ATR[1]). Default: SL = 1.25× ATR, TP = 6.0× ATR → RR ~4.8:1 … breakeven win rate is approximately 17.2%."
- **Excerpt (Time-Exit):** "Positions held beyond InpMaxBarsInTrade (default 60 H1 bars = ~2.5 trading days) are closed at market."
- **Excerpt (ehrliche Limitationen):** "28% win rate requires psychological discipline … 3–4 consecutive losses are routine … Live XAUUSD spreads during news events can spike to 5–15 pips … No news filter … No trailing stop … Long-only bias is the fundamental risk." M5-Variante explizit **verworfen**: MaxDD 12,07 % > FTMO 10 %.
- **Excerpt (Methodik):** "In-sample/out-of-sample separation — Initial parameter exploration on 2022–2023; 2024–2026 treated as validation period. Single-pass backtest — no curve-fitting to out-of-sample data."
- **Confidence:** Hoch für Regelwerk/Code-Architektur (direkt portierbar nach pymt5trade); Mittel für Performance-Übertragbarkeit (long-only in einem historischen Gold-Bullenmarkt 2022–2026; Autor selbst markiert das als Hauptrisiko).

### CLAIM C — Turtle/Donchian-Regelgerüst inkl. Faith-Filter & Time-Exit (Basis-Variante 3)
- **Claim:** Curtis Faiths getestete Donchian-Varianten (1996–2007): (1) 20d-Breakout-Entry, 10d-Breakout-Exit, **Filter 25d-MA > 350d-MA** für Longs (CAGR 29,4 %); (2) gleiche Entries, aber **Time-Exit nach 80 Tagen** (CAGR 57,2 %). Original-Turtle: S1 = 20d-Breakout (skip nach Gewinner), S2 = 55d-Breakout, Stop = 2N (2×ATR20), Pyramiding +0.5N bis 4 Units, Unit = 1 % Risiko. OOS 2007–2022 kollabiert auf CAGR 2–10 % bei DD 17–50 %.
- **Source:** QuantifiedStrategies ("Donchian Channels Trading Strategy" + "Turtle Trading Strategy"); Alchemy Markets Turtle-Guide; Altrady/TrendSpider (Original-Regeln)
- **URL:** https://www.quantifiedstrategies.com/donchian-channel/ | https://www.quantifiedstrategies.com/turtle-trading-strategy/ | https://alchemymarkets.com/education/strategies/turtle-trading-guide/ | https://www.altrady.com/blog/crypto-trading-strategies/turtle-trading-strategy-rules
- **Date:** 08.04.2024 / 14.04.2025 / 16.03.2026 / 27.04.2026
- **Excerpt (QS):** "A Donchian Trend system that uses a 20-day breakout for entry and a 10-day breakout for exits … requiring the short average [25] to be above the long one [350] to take a long trade … Donchian Trend with time exit … exits after 80 days … Strategy number one returned a CAGR of 29.4% while strategy number 2 had a whopping 57.2% annual return."
- **Excerpt (Alchemy, Sizing):** "Position size = (1% of capital) ÷ (2 × ATR) … Every position had a fixed stop placed at 2N (2x ATR)."
- **Excerpt (Altrady, Skip-Regel):** "The trade is skipped if the previous S1 signal was a winner … If a real new trend starts, the S2 channel will catch it."
- **Confidence:** Hoch für historische Regeln (Primärquelle Faith via Sekundärquellen, konsistent über 4+ Quellen); Hoch für OOS-Degradation (QS-Nachtest 27 Futures, siehe wide03 [^9^]). Konsequenz für uns: **Donchian pur ist kein PF>1.5-Kandidat mehr; sein Wert ist das Regelgerüst (2N-Stop, N-Sizing, Time-Exit 80 Bars, 25/350-Filter) als Baukasten.**

### CLAIM D — 20-EMA-Pullback: präzises Entry-Regelwerk (Pullback-Trigger, Variante für H1/H4)
- **Claim:** Hochwahrscheinlichkeits-20-EMA-Pullback = (1) 20-EMA mit Steigung in Trendrichtung (EMA heute > EMA vor 5 Bars), (2) vorheriges Higher High (Long), (3) Pullback berührt/leicht durchstößt 20-EMA, (4) Bestätigungskerze (Pin Bar / Bullish Engulfing / Schluss über Vorkerzen-Hoch) mit **Close abwarten**, (5) SL unter Pullback-Swing-Tief bzw. 0.5×ATR(14) unter EMA (was näher ist), (6) TP1 = vorheriges Swing-Hoch oder 1.5–3× Risiko, (7) **Time-Stop: wenn Kurs nicht innerhalb von 5 Bars 1R gelaufen ist → Exit bei Breakeven**.
- **Source:** tradingsim.com "20 Moving Average Pullback Strategy"; fxnx.com "Master 20-EMA Pullback Strategy"
- **URL:** https://www.tradingsim.com/blog/20-moving-average-pullback | https://fxnx.com/en/blog/master-20-ema-pullback-strategy
- **Date:** 26.04.2026 / 01.05.2026
- **Excerpt (tradingsim):** "The 20 MA must be sloping in your trade direction … Price must have made a higher high before the pullback … A reversal candle must form at the 20 MA … Stop: Below the swing low formed on the pullback, or 0.5× ATR(14) below the 20 MA — whichever is closer … Time stop: If price hasn't moved 1× risk away from entry within five bars, exit at break-even."
- **Excerpt (fxnx, Tiefe als Signal):** "In the strongest trends, pullbacks tend to be shallow and brief … deeper, slower pullbacks that linger at the EMA for many candles, the trend is losing momentum."
- **Excerpt (fxnx, MTF):** "Trading a 20-EMA pullback on the 1-hour chart while the 4-hour and daily charts are also trending in the same direction is a high-probability A+ setup."
- **Kontrast-Evidenz (aus wide03, nicht vergessen!):** Reiner 20-EMA-Pullback EUR/USD ohne Filter: WR 48,5 % ≈ Münzwurf (Trader-Dale, 138 Trades); standalone 20-EMA SPY CAGR 3,06 % < B&H. **Pullback-Entry braucht zwingend den D1/H4-Bias-Filter — genau unsere Architektur.**
- **Confidence:** Mittel. Regeln konsistent über mehrere Praxis-Quellen; harte Backtest-Kennzahlen für XAUUSD H4 fehlen (selbst zu testen).

### CLAIM E — Fib-Pullback auf Gold: Golden Zone 38.2–61.8, ADX-abhängige Pullback-Tiefe, 78.6 %-Invalidierung
- **Claim:** Auf XAUUSD H4 (trendende Phasen): Halte-Rate der Fib-Levels ca. 61.8 %→64 %, 50 %→55 %, 38.2 %→47 %, 23.6 %→31 %, 78.6 %→41 %; Pullback-Tiefe korreliert mit ADX (ADX 25–35: häufigste Tiefe 50–61.8 %; ADX 35–50: 38.2–50 %; ADX 50+: 23.6–38.2 %); Retracement > 78.6 % → <8 % der Trends erholen sich → harte Invalidierung. Pullback-Entries auf XAUUSD liefern ~15 % besseres R:R als Breakout-Entries am selben Level. 8-Punkte-Qualitäts-Checkliste (Trend H4/D1 klar; Tiefe 30–65 %; abnehmende Momentum-Kerzen; letztes Swing-Tief intakt; Fib-Konfluenz mit EMA/Struktur; Reversal-Kerze; ADX > 25). Stops: 15 Pips unter Fib-Level bzw. 10 Pips unter Trigger-Kerzen-Tief (was weiter weg ist); BE nach +1R; Trail an H1-Swing-Tiefs; TP1 = vorheriges Swing-Hoch, TP2 = 1.272er-Extension.
- **Source:** pro-scalper.com — "Pullback Trading Strategy on Gold" + "Gold Fibonacci Strategy"; liquidityfinder (Fib+MA-Confluence)
- **URL:** https://www.pro-scalper.com/xauusd-strategies/gold-pullback-strategy | https://www.pro-scalper.com/xauusd-strategies/gold-fibonacci-strategy | https://liquidityfinder.com/news/pullback-trading-strategy-using-moving-averages-fibonacci-61797
- **Date:** 01.01.2025 / 01.01.2025 / 24.07.2025
- **Excerpt:** "Analysis of H4 XAUUSD price behavior in trending market conditions reveals that the 61.8% retracement level holds as support or resistance approximately 64% of the time … less than 8% of valid trends recover after a retracement beyond 80% of the prior impulse … pullback entries at the same levels provide an average of 15% better risk-to-reward ratio than their breakout counterparts."
- **Confidence:** **Niedrig-Mittel.** EA-verkaufende Seite, Statistiken ohne offengelegte Methodik/Stichprobe. Als Hypothesen-Gerüst für eigene Backtests nutzbar, nicht als Beleg. (Deckt sich richtungsweise mit der ADX-Trendstärke-Logik aus CLAIM A.)

### CLAIM F — Supertrend XAUUSD: Parameter-Konsens (Variante 2)
- **Claim:** Gold-Supertrend-Praxis-Konsens: H4/D1 → ATR(10), Mult 3.0 (bzw. ATR(14)/3.0 für H1+ auf Gold wegen 10–15-Pip-Gegenmoves); M15/H1 → ATR(7–10), Mult 2.0–2.5. Mehrheit der Gold-Trader: Mult 2.5–3.5. Session-Filter nötig (Overlap-Signale sauberster Follow-Through); keine Signale ±30 min um FOMC. Multi-TF-Alignment (D1→H4→H1) als Standard-Verbesserung.
- **Source:** quantzee.com Supertrend-Settings-Guide; pro-scalper.com Supertrend-Gold; hw.online (Headway)
- **URL:** https://quantzee.com/supertrend-indicator-settings-guide/ | https://pro-scalper.com/indicators/supertrend-gold | https://hw.online/faq/best-mt4-indicator-for-gold-trading/
- **Date:** 31.05.2026 / 16.05.2026 / 24.03.2026
- **Excerpt:** "Testing on XAUUSD shows that ATR(14) with multiplier 3.0 provides a strong balance for H1 and above … the 3.0 multiplier keeps the bands wide enough to survive the typical 10-15 pip counter-moves … Most experienced gold traders settle in the 2.5-3.5 multiplier range." / "Gold most often trends clearly during the London-to-New-York overlap (13:00–17:00 UTC); SuperTrend signals during this window have historically produced cleaner follow-through."
- **Confidence:** Mittel (Praxis-Konsens, keine harte Gold-Backtest-Serie); kombiniert mit CoinQuant BTC D1 PF 1.51 (wide03 [^6^]) → plausibel, aber Gold-spezifisch selbst zu verifizieren.

### CLAIM G — Session-Filter: Gold ist der session-sensitivste Markt; Overlap-Only ist evidenzbasiert
- **Claim:** Gemessene Stunden-Volatilität XAUUSD: 13:00 UTC = 83 Pips, 14:00 = 81 Pips vs. 21:00 = 24 Pips, 04:00 = 27 Pips (3,5× Spread — höchste Session-Sensitivität aller getesteten Instrumente). Backtest-Praxis: gleiche Strategie mit positiver Expectancy in London/Overlap, ~null/negativ in Asien. maker-tung-EA bestätigt empirisch: Entry-Peak 13:00–16:00 Server-Zeit, Asien deutlich dünner.
- **Source:** fxbacktest.app "Forex Trading Sessions Explained"; fxnx.com Overlap-Goldmine; maker-tung README (Entry-Distribution-Heatmap)
- **URL:** https://fxbacktest.app/guide/forex-trading-sessions/ | https://fxnx.com/en/blog/london-ny-overlap-goldmine-strategy-xau-usd | https://github.com/maker-tung/xauusd-trend-follow
- **Date:** 11.05.2026 / 13.05.2026 / 26.05.2026
- **Excerpt:** "Gold is the most session-sensitive of the four. XAUUSD ranges 83.0 pips at 13:00 against 24.0 at 21:00, a 3.5x spread. A gold stop sized for the Asian session will be far too tight at the New York open." / "Adding a session filter is not curve fitting — it is identifying where your edge actually lives."
- **Confidence:** Hoch (gemessene Stunden-Tabelle + EA-Empirie + mehrere unabhängige Quellen in wide06).

### CLAIM H — News-Spread & Kosten: harte Zahlen für die Kostenmodellierung
- **Claim:** XAUUSD-Spread RAW/ECN Overlap: 0.12–0.26 USD (1.8–2.6 Pips); Standard-Accounts 0.35–0.55; Asien 0.15–0.35; Rollover 22:00–23:00 GMT: 10 → 150 Punkte in Sekunden; NFP/CPI/FOMC: **$1–3 bis $5+** Spread + Slippage, 30–90 s lang; Backtest ohne News-Spread-Modellierung überschätzt systematisch. Empfehlungen: MaxSpread-Filter hart codieren, ±5–30 min News-Blackout, Slippage-Parameter in OrderSend.
- **Source:** fxnx.com ("Build a Prop-Ready Gold EA", "XAUUSD Spread History"); fortraders.com Backtest-Bias; JustMarkets-Spread-Tabelle
- **URL:** https://fxnx.com/en/blog/build-prop-ready-gold-ea-mql5-surviving-xauusd-volatility | https://fxnx.com/en/blog/xauusd-spread-dated-log-measured-cost-changes | https://fortraders.com/blog/how-to-avoid-bias-in-backtesting
- **Date:** 28.08.2026 / 22.08.2026 / 31.08.2026
- **Excerpt:** "Between 22:00 and 23:00 GMT … XAUUSD spreads can widen from 10 points to 150 points in seconds." / "Around the Non-Farm Payrolls print or an FOMC rate decision, that spread can widen to $1-3 or more for the first 30-90 seconds … A backtest that doesn't model XAUUSD spread widening during NFP and FOMC windows will systematically overstate any breakout or news-reaction strategy." / "During tier-1 macroeconomic releases … the bid-ask spread [widens] frequently reaching $1.50 to $5.00+."
- **Confidence:** Hoch (mehrere unabhängige Quellen, konsistente Größenordnungen; deckt sich mit wide06 [^467^][^470^]).

### CLAIM I — Walk-Forward-Design: breite Räume, Plateau-Regel, 70/30
- **Claim:** WFO-Best-Practices: breite logische Parameter-Räume (z. B. MA 10–200, nicht 19–21), grobe Step-Size, **Plateau-Prinzip** (Parameter wählen, die bei Nachbarwerten gut performen — Einzelspitzen = Overfitting), IS/OOS 70/30, rollierend.
- **Source:** arongroups.co WFO-Guide; monstertradingsystems.com
- **URL:** https://arongroups.co/forex-articles/walk-forward-optimisation-in-trading/ | https://www.monstertradingsystems.com/walk-forward-optimization/
- **Date:** 12.02.2026 / 20.11.2025
- **Excerpt:** "Use broad, logical ranges (e.g., 10-200) … Larger steps help identify the 'plateau of profitability' rather than isolated spikes … Stability Over Peak Profit."
- **Confidence:** Mittel-Hoch (Methodik-Konsens; deckt sich mit Bajgrowicz/Scaillet-Logik aus wide03).

### CLAIM J — Ranging-Phasen sind der strukturelle Killer; Märkte trenden nur ~30 % der Zeit
- **Claim:** Märkte trenden grob nur ~30 % der Zeit; Trendfolge-Winrates < 50 % sind systemimmanent (Whipsaws in Ranges). Whipsaw-Reduktion nur über Bestätigungen (Penetration/Delay), Filter, Diversifikation — nie kostenlos (späterer Entry). Regime-Switch (Trend-Modul + Countertrend-Modul parallel) als professionelle Antwort.
- **Source:** Wiley-Excerpt (Trading-Systems-Lehrbuch); tosindicators SPX-Trendfolge-Walkthrough
- **URL:** https://catalogimages.wiley.com/images/db/pdf/9781119543558.excerpt.pdf | https://tosindicators.com/research/trend-following-strategy-walkthrough-examples-sp500
- **Date:** o.D. / 12.02.2022
- **Excerpt:** "Trend-following systems often produce less than 50% wins because of the many whipsaws during ranging markets … to avoid whipsaws, a trend-following system will be late in the trend and will thus miss profit potential at both ends." / "Markets trend roughly 30% of the time, and those trending periods account for the majority of annual returns."
- **Confidence:** Hoch (Lehrbuch-Konsens + SG-Trend-CTA-Realgeld aus wide03: 2023/2025 negative Trend-Jahre trotz funktionierender Systeme).

### CLAIM K — Pullback-Bias-Kombination mit harter Aktien-Backtest-Evidenz (Muster-Transfer)
- **Claim:** QS-Long-Term-Pullback SPY seit 1993: Close > SMA200 **und** Close < SMA20 **und** RSI(5) < 45 → Entry; Exit RSI(5) > 65: WR 82 %, CAGR 8,3 %, DD 30 %, nur 30 % Marktzeit. Beweist das Architektur-Muster "grober Langzeit-Bias + kurzfristiger Pullback-Trigger", ist aber Equity-Mean-Reversion — **nicht direkt auf Gold-Trendfolge übertragbar** (wide03 Befund 7).
- **Source:** quantifiedstrategies.com "Pullback Trading Strategies"
- **URL:** https://www.quantifiedstrategies.com/pullback-trading-strategy/
- **Date:** 12.08.2024
- **Excerpt:** "The close must be above the 200-day moving average. The close must be below the 20-day moving average. The five-day RSI must be below 45 … Win-ratio is 82%."
- **Confidence:** Hoch für SPY (sauber dokumentiert); Niedrig für Gold-Transfer → nur als Design-Muster nutzen.

---

## 3. Varianten-Vergleich (Trend-Bias-/Trigger-Module)

| Variante | Regelwerk (Kern) | Dokumentierte Kennzahlen XAUUSD | Stärken | Schwächen | Confidence |
|---|---|---|---|---|---|
| **V1: ADX-DI-Cross D1** [^1^] | DI+×DI− Cross + ADX>20 + Preis über/unter 5-Mom-Ø; SL 2×ATR; TP 2:1 | **PF 1.54, WR 43.6 %, MaxDD 5.0 %, 101 Trades (D1, brutto)** | Exakte Regeln publiziert; großes Gesamt-Sample (4.236 Trades); D1 = prop-freundlich niedrige Frequenz | Brutto-Zahlen (Kosten offen); WR < 45 %; kein Pullback-Entry (Entry am Cross = schlechterer Preis); H1-Variante negativ | Mittel-Hoch |
| **V2: Supertrend H4/D1** [^8^][^9^] + wide03 [^6^] | ST(10/3.0) Flip auf H4/D1 als Bias; Pullback zur ST-Linie oder EMA20 als Entry; Trail = ST-Linie | BTC D1 PF 1.51 (Proxy); Gold: nur Settings-Konsens, keine harte Serie | Volatilitäts-adaptiver Trail eingebaut; einfachste Implementierung; Multi-TF-Align dokumentiert | Kein gold-spezifischer PF-Beleg; Whipsaw in Ranges; Parameter-Optimierung = Overfitting-Falle (arXiv-Warnung wide03 [^31^]) | Mittel |
| **V3: Donchian-Breakout + Pullback-Retest** [^3^][^4^] | 20d/55d-Breakout als Trend-Event; Entry erst am Retest des Breakout-Levels oder Donchian-Midline; Stop 2N; Exit 10d-Gegen-Breakout **oder 80-Bar-Time-Exit** | Faith 1996–2007 CAGR 29.4–57.2 %; **OOS 2007–2022: CAGR 2–10 %, DD 17–50 %** | Vollständig mechanisch; Time-Exit-Evidenz (80d schlägt Breakout-Exit); 25/350-Filter belegt | OOS kollabiert; reine Breakout-Entries auf Gold = Stop-Hunt-Opfer (Pullbacks 15 % besseres R:R [^5^]); braucht Filter + Retest | Hoch (für Degradation) |
| **V4: EMA200-Bias + Multi-Trigger (maker-tung-Blueprint)** [^2^] | H4/D1: Close > EMA200; H1: MACD/Stoch/EMA9-21-Cross OR; SL 1.25×ATR, TP 6×ATR, Time-Exit 60 Bars | **PF ~1.17, WR 25.8 %, MaxDD 6.22 %, 4+ Jahre Real-Ticks, FTMO-konform** | Produktionsreifer Code; ehrlichste Limitationen; FTMO-Circuit-Breaker als Vorlage; Bar-Close-Execution | **PF 1.17 < Ziel 1.5** — Trigger ohne Pullback-Logik (Entry an Crosses, nicht an Value-Zonen); long-only; kein News-Filter | Hoch (Code), Mittel (Übertragbarkeit) |
| **V5 (Synthese, EMPFOHLEN): D1-Bias + H4/H1-Pullback** [^1^][^2^][^5^][^6^][^10^] | Bias: D1 Close > SMA200 **ODER** DI-Cross-State (DI+>DI− seit letztem Cross); Trigger: H4/H1-Pullback in Zone (EMA20-Tag **oder** Fib 38.2–61.8 der letzten Impulswelle **oder** letztes Swing-Level) + Reversal-Kerzen-Close; SL 1.5–2×ATR unter Struktur; TP1 2R + Trail; Time-Exit 20–40 H4-Bars; Session- + News-Filter | Kombiniert: DI-Cross PF 1.54 (Bias-Qualität) + Pullback-R:R-Vorteil ~15 % + Session-Edge | Jede Komponente einzeln belegt; adressiert die dokumentierten Schwächen jeder Einzelvariante | **Keine fertige publizierte Backtest-Serie — Eigenbau + eigener OOS-Test zwingend** | Konstrukt (Hohe Teil-Evidenz) |

**Kernaussage:** Keine der vier dokumentierten Einzelvarianten erfüllt "PF > 1.5 OOS + RR ≥ 1:2 + Prop-tauglich" gleichzeitig mit harten Belegen. V1 kommt am nächsten (PF 1.54 brutto, D1), hat aber keinen Pullback-Entry. V4 ist prop-fertig, aber PF 1.17. ⇒ **V5-Synthese ist der Forschungs-Output; V1 dient als OOS-Benchmark** (wenn die komplexere V5 den simplen DI-Cross D1 nicht schlägt, V1 deployen).

---

## 4. Parameter-Räume für Walk-Forward-Optimierung

Plateau-Prinzip [^13^]: breite Räume, grobe Steps, Nachbarwerte-Stabilität prüfen. **Stabil sein müssen** (= NICHT oder nur grob optimieren): SMA200-Bias-Länge, ATR-Periode 14, RR ≥ 2, News-Fenster, Risiko 0,5 %. Diese sind strukturell/ökonomisch begründet (Selbsterfüllungs-Niveau SMA200; Wilder-Standard; Prop-Regeln), nicht fit-bar.

| Parameter | Default | WFO-Raum (Step) | Begründung / Stabilitäts-Anker |
|---|---|---|---|
| Bias-MA (D1) | SMA 200 | {150, 175, 200, 250} — fix halten wenn Plateau | SMA200 = institutioneller Standard (wide03 [^17^][^48^]); Sensitivitätstest statt Optimierung |
| DI-Cross-Periode | ADX 14 | {10, 14, 20} | Wilder-Default; quant-signals nutzte 14 [^1^] |
| ADX-Schwelle (Regime-Gate, NICHT als Entry-Filter!) | 20 | {18, 20, 25} | >20 = DI-Cross-Standard [^1^]; >25 als Filter **zerstörte** PF [^1^] → nur als Regime-Info |
| EMA-Pullback (H4/H1) | EMA 20 | {15, 20, 21, 30, 50} | 20/21 = Praxis-Standard Gold [^5^][^6^]; 50 = Fallback tiefer Pullback [^6^] |
| Fib-Zone | 38.2–61.8 % | {Start: 38.2/50; Ende: 61.8/70/78.6} | Golden-Zone-Konsens [^5^][^6^]; >78.6 % = Invalidierung (kein Optimierungsparameter!) |
| Pullback-Definition (Kerzen) | 2–5 gegenläufige H1-/H4-Kerzen, Tiefe ≥ 0.5×ATR, ≤ 65 % der Impulswelle | Kerzen {2,3,5,8}; Tiefe {0.3, 0.5, 0.75}×ATR | pro-scalper-Checkliste: Tiefe 30–65 %, abnehmende Momentum-Kerzen [^5^] |
| Bestätigung | Reversal-Kerze (Engulfing/Pin) Close ODER Bruch der Pullback-Mini-Trendlinie | binär/aus | fxnx/tradingsim-Konsens: Close abwarten [^7^][^14^] |
| ATR-Periode (SL/Trail) | 14 | fix | Wilder-Standard; maker-tung 14 [^2^]; quant-signals ATR-basiert [^1^] |
| SL-Multiplikator | 1.5–2.0 ×ATR(H4) | {1.25, 1.5, 2.0, 2.5} | quant-signals 2.0 [^1^]; maker-tung 1.25 [^2^]; Turtle 2N [^3^]; enger als 1.25 = News-Noise-Todeszone [^11^] |
| TP / RR | TP1 = 2R (50 % ab), Runner Trail | RR {1.5, 2, 3}; Trail {2×ATR-Chandelier, EMA20, letztes H4-Swing} | Zielkriterium RR ≥ 2; fixer 2×ATR-Stop schlug Trailing in Chop (wide03 [^42^]) → TP1 fix + Runner trailen als Hybrid |
| Time-Exit | 20–40 H4-Bars (~3–7 Tage) bzw. 60 H1-Bars | {15, 20, 30, 40, 60} Bars | maker-tung 60 H1 [^2^]; Faith 80 D1-Bars [^4^]; tradingsim 5-Bar-No-1R-Exit [^7^] (zusätzlicher Früh-Exit: "kein 1R in 10 Bars → raus") |
| Session-Filter | Entries nur 07:00–17:00 UTC (London + Overlap), kein Entry 21:00–07:00 | Varianten {07–17, 08–20, nur Overlap 13–17} UTC | Gold 3.5× session-sensitiv [^10^]; maker-tung Entry-Peak 13–16 [^2^]; **Vorsicht Overfitting: grobe Fenster, keine Minuten-Optimierung** [^15^] |
| News-Filter | kein Entry −30 min/+15 min um High-Impact-USD; bestehende Pos: SL bleibt, kein Management im Fenster | Fenster {15/30/60} min vor | FTMO ±2 min Regel (wide06 [^117^]); fxnx 60-min-Check [^11^]; XAU-Sentinel 30/15 [^8^] |
| MaxSpread-Gate | Entry nur wenn Spread ≤ 0.40 USD (40 Punkte) | {30, 40, 60} Punkte | fxnx-Rollover-Warnung [^11^]; Scalping-Grenze 0.6 (wide06) |
| Risiko/Trade | 0.5 % | fix | Lead-Vorgabe; Turtle-1 %-Logik halbiert [^3^] |
| Circuit-Breaker | Tagesverlust-Stop 3.0 % (Puffer zu FTMO 5 %); Gesamt-DD-Halt 7 % (Puffer zu 10 %) | fix | maker-tung 4 %/8 % mit 0.5–1.0 Pp-Puffer [^2^]; bei 0.5 % Risiko → 3 % = 6 Verluste/Tag (defensiver als Referenz) |

**WFO-Protokoll (bindend):** IS/OOS 70/30 rollierend [^16^]; Optimierung nur 2022–2023-äquivalente Fenster, Validierung 2024–2026 (maker-tung-Methodik [^2^]); Kostenmodell: Spread 0.30 fix + News-Fenster-Spread $1.50–3.00 + Slippage 0.10–0.30/Seite [^11^][^12^]; Kandidat verworfen, wenn Plateau-Breite < 2 Nachbar-Steps oder OOS-PF < 0.8 × IS-PF.

---

## 5. Bekannte Schwächen & Gegenmaßnahmen

1. **Ranging-Phasen (~70 % der Zeit)** [^17^]: Whipsaw-Serien sind systemimmanent (WR 25–44 % über alle belegten Varianten). Gegenmaßnahmen: Regime-Gate (D1-Preis > SMA200 **und** ADX(14) D1 ≥ 20, sonst flat — als Gate, nicht als Entry-Filter! [^1^]); Verlustserien-Bremse (nach 3 SL in Folge 24 h Pause, analog Whipsaw-Control [^18^]); akzeptieren, dass 3–4 Verluste in Folge Routine sind [^2^].
2. **Gold-Whiplash um News** [^11^][^12^]: Spread 0.20 → $1–3+, Slippage, Stop-Hunts in beide Richtungen. maker-tung-EA hat explizit **keinen** News-Filter und zeigt MAE-Outlier −168 (Gap-Event) [^2^]. Gegenmaßnahmen: News-Blackout −30/+15 min (MQL5-Calendar-Äquivalent in Python: FF/Investing-Kalender-Feed), MaxSpread-Gate 40 Punkte, keine Pending-Orders über NFP/FOMC/CPI. FTMO-Funded: ±2-min-Regel ohnehin Pflicht (wide06 [^117^]) — unser Fenster ist strenger → kompatibel.
3. **Spread-/Kosten-Erosion** [^11^][^12^]: Round-Trip XAUUSD ~$12–25 (wide06 [^467^]). Bei SL 1.5×ATR(H4) ≈ $8–15 Distanz sind Kosten ~2–5 % der Risikodistanz — vertretbar; auf H1 schon ~5–10 % → **H4 als primärer Execution-TF, H1 nur für Fein-Entry**. Backtest-Pflicht: News-Spread-Szenarien, sonst systematische Überschätzung [^12^].
4. **Long-only-Falle** [^2^]: Gold 2022–2026 = Bullenmarkt; alle Gold-Backtests dieser Periode haben Long-Bias-Inflation. Gegenmaßnahme: Short-Seite symmetrisch implementieren (DI−-Cross / Close < SMA200), aber separat reporten; OOS-Fenster muss 2022 (Bär) und 2013–2015-ähnliche Phasen (falls Daten) enthalten.
5. **Pullback→Reversal-Verwechslung** [^5^]: Retracement > 78.6 % → <8 % Erholung → harte Invalidierung; H4-Close unter letztem relevantem Swing-Tief → Setup tot. Das muss als harter Exit codiert sein, nicht als SL-Ersatz-Hoffnung.
6. **Overfitting**: 5–10 %/Monat-Backtests = Overfitting-Signal (wide03 [^28^]); Fib/Session-Statistiken aus EA-Marketing-Quellen [^5^][^6^] nur als Hypothesen. WFO-Disziplin nach Abschnitt 4; Einfachheits-Tiebreaker: bei Gleichstand gewinnt die Variante mit weniger Bedingungen (V1-Benchmark!).
7. **EOD-DD-Risiko durch Overnight-Haltung**: H4-Swings halten über Nacht/Wochenende — FTMO-Standard verlangt Freitag flach (wide06 [^526^]). Gegenmaßnahme: Freitag-Flat-Regel (Entry-Stopp Do 20:00 UTC, Flat Fr 20:00 UTC) oder Swing-Account; Wochenend-Gap vs. SL im Backtest modellieren.

---

## 6. IMPLEMENTIERUNGS-SPEZIFIKATION (Bot: xau_h4_trend_pullback)

```python
# ============================================================
# BOT 01: XAUUSD H4 Trend-Pullback (Variante V5)
# Daten: D1 + H4 (+H1 optional Fein-Entry) via pymt5trade
# Risiko: 0.5% Equity/Trade | Max 1 Position | Prop-Layer: FTMO
# ============================================================

# ---------- MODULE ----------
# M1 Bias (D1, täglich nach Close):
bias_long  = (close_D1[-1] > SMA(close_D1, 200)[-1]) \
             AND (DIplus(14)_D1[-1] > DIminus(14)_D1[-1])      # DI-State, kein frischer Cross nötig
bias_short = spiegelbildlich
regime_ok  = ADX(14)_D1[-1] >= 20                               # Gate; <20 -> KEIN Trade (flat)

# M2 Impuls-/Swing-Tracking (H4):
impuls = letzte H4-Swingwelle in Bias-Richtung (Fractal(2)-Anker: swing_low -> swing_high)
fib_zone   = [impuls.high - 0.618*range, impuls.high - 0.382*range]      # long
ema20_zone = [EMA20_H4 - 0.25*ATR14_H4, EMA20_H4 + 0.25*ATR14_H4]
entry_zone = schnittmenge(fib_zone, ema20_zone); fallback: breitere der beiden
invalid    = min(impuls.low, fib78_6)                          # harte Invalidierung

# M3 Pullback-Erkennung (H4, rolling):
pullback_active = (2..5 H4-Kerzen gegen Bias) \
                  AND (tiefe >= 0.5*ATR14_H4) AND (tiefe <= 0.65*impuls_range) \
                  AND (letztes Bias-Swing-Tief NICHT per H4-Close gebrochen)

# M4 Trigger (H4-Close; H1-Close optional für Fein-Entry):
trigger_long = pullback_active AND close_in(entry_zone) AND (
                 bullish_engulfing(close) OR pinbar_lower_wick(close, wick>=2*body) \
                 OR close > max(high der letzten 2 Pullback-Kerzen))     # Mini-Trendlinien-Bruch
# KEIN Entry ohne Kerzen-Close (maker-tung: IsNewBar()-Guard-Äquivalent)

# ---------- FILTER (harte Gates, vor jeder Order) ----------
session_ok   = 07:00 <= utcnow < 17:00          # Mo-Do; Do ab 20:00 kein Entry; Fr: flat bis 20:00 UTC
news_ok      = kein High-Impact-USD-Event in [-30min, +15min]   # Kalender-Feed; Fenster konfigurierbar
spread_ok    = aktueller_spread <= 0.40 USD
daily_ok     = tages_pnl_equity > -3.0%          # Circuit-Breaker (Puffer zu FTMO 5%)
total_ok     = equity_dd_vom_peak < 7.0%         # permanenter Halt bis manueller Reset (maker-tung-Pattern)
whipsaw_ok   = nicht (letzte 3 Trades = SL in Folge innerhalb 24h)  # sonst 24h Pause

# ---------- ORDER ----------
if bias_long AND regime_ok AND trigger_long AND alle_filter_ok AND keine_position:
    sl_dist   = max(1.5 * ATR(14)_H4, einstieg - min(trigger_candle.low, entry_zone.low) + 0.2*ATR)
    sl        = einstieg - sl_dist
    lots      = floor_step( (0.005 * equity) / (sl_dist * tick_value_per_lot) )   # ATR-N-Sizing-Logik
    tp1       = einstieg + 2.0 * sl_dist          # 50% der Position
    runner    = 50% Rest, Trail ab +2R: max(letztes H4-Swing-Tief, einstieg + 2*sl_dist)
    max_bars  = 30 H4-Bars (~5 Tage)              # Time-Exit; plus Früh-Exit: kein +1R nach 10 Bars -> close
    # KEIN Management (Trail/BE) innerhalb News-Fenster; SL/TP stehen beim Broker (serverseitig)

# Short: spiegelbildlich, separater KPI-Report (Long-Bias-Inflation 2022-2026!)

# ---------- PROP-COMPLIANCE ----------
# - EOD-DD: Tages-Baseline um 00:00 Serverzeit resetten (maker-tung UpdateDailyEquity-Pattern)
# - FTMO-News-Regel (Funded, ±2min) ist Subset unseres ±30/15-Fensters -> konform
# - Wochenende: Freitag 20:00 UTC flat (FTMO-Standard); Swing-Account: optional halten
# - 1 Position, kein Grid/Martingale, kein Hedging -> universell erlaubt
# - pymt5trade: Order mit deviation<=30 Punkten; reject bei Requote statt akzeptieren

# ---------- BACKTEST-/WFO-PFLICHT ----------
# Kosten: Spread 0.30 fix + $1.5-3.0 in News-Fenstern + Slippage 0.10-0.30/Seite + Swap
# WFO: 70/30 rollierend; Parameter-Räume Abschnitt 4; Plateau-Regel
# Benchmark: Bot muss V1 (DI-Cross D1, PF 1.54 brutto-Replikation) OOS schlagen,
#            sonst V1 deployen (Einfachheits-Tiebreaker)
# Abbruchkriterium Live: OOS-PF < 0.8 * IS-PF über 60 Trades -> Review statt Nachoptimierung
```

**Abweichungen/Annahmen (transparent):**
- H4-Execution als Primär-TF (Kosten-Anteil der SL-Distanz 2–5 % vs. 5–10 % auf H1); H1-Fein-Entry nur als Optimierungs-Variante, nicht Default.
- Time-Exit 30 H4-Bars = geometrisches Mittel der Belege (maker-tung 60 H1 ≈ 15 H4; Faith 80 D1; tradingsim 5-Bar-Früh-Exit) → im WFO-Raum {15..60}.
- TP1 2R + Runner-Hybrid statt reinem 6×ATR-TP (maker-tung), weil 0.5 %-Risiko + EOD-DD geringere Trefferquote-Wahrnehmung verlangt und fixe TPs in Chop regelmäßig Trailing schlagen (wide03 [^42^]).

---

## 7. Quellen

[^1^]: quant-signals.com – "ADX Trading Strategy: How to Filter Weak Trends (Backtest Data)", 04.04.2026, https://quant-signals.com/adx-trading-strategy/ (Tiefenlektüre via web_open_url; Regeln + XAUUSD-Tabelle PF 1.54 + Filter-Gegenbefund PF 0.40)
[^2^]: GitHub maker-tung – "xauusd-trend-follow" (MQL5-EA, README, Parameter, FTMO-Layer, 4-Jahres-Real-Tick-Backtest), 26.05.2026, https://github.com/maker-tung/xauusd-trend-follow (Tiefenlektüre)
[^3^]: QuantifiedStrategies – "Donchian Channels Trading Strategy" (Faith 20/10 + 25/350-Filter + 80d-Time-Exit, CAGRs), 08.04.2024, https://www.quantifiedstrategies.com/donchian-channel/ ; + "Turtle Trading Strategy" (OOS 2007–2022), 14.04.2025, https://www.quantifiedstrategies.com/turtle-trading-strategy/
[^4^]: Alchemy Markets – "Turtle Trading Complete Guide" (Sizing-Formel, 2N-Stop, Pyramiding 0.5N), 16.03.2026, https://alchemymarkets.com/education/strategies/turtle-trading-guide/ (Tiefenlektüre); Altrady Turtle-Regeln, 27.04.2026, https://www.altrady.com/blog/crypto-trading-strategies/turtle-trading-strategy-rules
[^5^]: pro-scalper.com – "Pullback Trading Strategy on Gold" (4 Pullback-Typen, 8-Punkte-Checkliste, 78.6 %-Regel, 15 % R:R-Vorteil, ADX-Tiefen-Tabelle), 01.01.2025, https://www.pro-scalper.com/xauusd-strategies/gold-pullback-strategy
[^6^]: pro-scalper.com – "Gold Fibonacci Strategy" (Hold-Rates 61.8 %→64 % usw.), 01.01.2025, https://www.pro-scalper.com/xauusd-strategies/gold-fibonacci-strategy ; liquidityfinder Fib+MA, 24.07.2025, https://liquidityfinder.com/news/pullback-trading-strategy-using-moving-averages-fibonacci-61797
[^7^]: tradingsim.com – "20 Moving Average Pullback Strategy" (4 Bedingungen, Stop-Regel, 5-Bar-Time-Stop), 26.04.2026, https://www.tradingsim.com/blog/20-moving-average-pullback
[^8^]: quantzee.com – "SuperTrend Indicator Best Settings & Strategy Guide 2026" (Gold M15: 7/2.5; D1: 10/3.0; Overlap-Session; FOMC ±30 min), 31.05.2026, https://quantzee.com/supertrend-indicator-settings-guide/
[^9^]: pro-scalper.com – "SuperTrend Indicator on XAUUSD" (ATR14/3.0 für H1+, Mult-Konsens 2.5–3.5), 16.05.2026, https://pro-scalper.com/indicators/supertrend-gold ; hw.online Gold-MT4-Indikatoren, 24.03.2026, https://hw.online/faq/best-mt4-indicator-for-gold-trading/
[^10^]: fxbacktest.app – "Forex Trading Sessions Explained" (Stunden-Pip-Tabelle: XAUUSD 13:00 UTC 83 Pips vs. 21:00 24 Pips; Session-Filter ≠ Curve-Fitting), 11.05.2026, https://fxbacktest.app/guide/forex-trading-sessions/
[^11^]: fxnx.com – "Build a Prop-Ready Gold EA in MQL5" (Rollover 10→150 Punkte; MaxSpread-Code; Kalender-Filter), 28.08.2026, https://fxnx.com/en/blog/build-prop-ready-gold-ea-mql5-surviving-xauusd-volatility ; + "XAUUSD Spread History" (RAW 18–26 Cents; News $1.50–5.00+), 22.08.2026, https://fxnx.com/en/blog/xauusd-spread-dated-log-measured-cost-changes
[^12^]: fortraders.com – "How To Avoid Bias in Backtesting" (NFP/FOMC-Spread $1–3, 30–90 s; Backtests ohne Modellierung überschätzen), 31.08.2026, https://fortraders.com/blog/how-to-avoid-bias-in-backtesting
[^13^]: arongroups.co – "Walk Forward Optimisation in Trading" (breite Räume, Plateau-Regel), 12.02.2026, https://arongroups.co/forex-articles/walk-forward-optimisation-in-trading/
[^14^]: fxnx.com – "Master 20-EMA Pullback Strategy" (Pullback vs. Reversal, MTF-Alignment), 01.05.2026, https://fxnx.com/en/blog/master-20-ema-pullback-strategy
[^15^]: quantstrategy.io – "Seasonal Filters" (granulare Zeitfilter = Overfitting-Falle), 12.01.2026, https://quantstrategy.io/blog/using-seasonal-filters-to-optimize-any-trading-strategy-for/
[^16^]: monstertradingsystems.com – "Walk-Forward Optimization" (70/30, rollierend), 20.11.2025, https://www.monstertradingsystems.com/walk-forward-optimization/
[^17^]: Wiley-Excerpt (Trading-Systems-Lehrbuch; Whipsaw/<50 %-WR-Systemik), o.D., https://catalogimages.wiley.com/images/db/pdf/9781119543558.excerpt.pdf ; tosindicators Trend-Walkthrough (30 %-Trend-Zeit), 12.02.2022, https://tosindicators.com/research/trend-following-strategy-walkthrough-examples-sp500
[^18^]: stratcraft.ai – Donchian-Template (Whipsaw-Control: Pause nach Verlust-Clustern), o.D., https://stratcraft.ai/donchian-channel
[^19^]: quantifiedstrategies.com – "Pullback Trading Strategies" (SPY SMA200/SMA20/RSI5<45, WR 82 %), 12.08.2024, https://www.quantifiedstrategies.com/pullback-trading-strategy/ (Tiefenlektüre)
[^20^]: kentrade/Kagels-Trading (DE) – "Pullback Trading: die 10 besten Strategien" (Al-Brooks 2-Bein-Pullback zum 20-EMA), 24.01.2026, https://www.kagels-trading.de/pullback-trading-strategien/

*Vorarbeit-Verweise (nicht neu belegt):* wide03 [^5^][^6^][^9^][^10^][^11^][^22^][^23^][^31^][^32^][^34^][^42^]; wide06 [^117^][^451^][^452^][^456^][^467^][^470^][^523^][^526^].
