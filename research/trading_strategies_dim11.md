# Dimension 11: Backtest-Methodik und Overfitting-Abwehr

**Deep-Dive-Facet:** Wissenschaftliche Grundlage der Validierungs-Pipeline für 5 Python-Bots auf MT5 (via pymt5trade). Ziel: PF > 1.5 OOS, Prop-Firm-Tauglichkeit (5 % Daily Loss / 10 % Max DD).
**Methodik:** 19 gezielte Websuchen (EN/DE), Deep-Dives in akademische Quellen (Bailey/López de Prado, Hansen, White), Paket-Dokumentationen (arch, backtest-guard, pypbo, skfolio), Practitioner-Quellen und MT5-spezifische Fallen. Stand der Recherche: siehe Datumsangaben in den Quellen. Baut auf trading_strategies_wide05.md (daru.finance-Replikation: bester DSR 0,029 von 92.500 Strategien) und wide01.md (DAX-Studie: 3 Punkte Slippage killen PF 1.25 → 0.96) auf.

---

## 1. Walk-Forward-Analysis: Anchored vs. Rolling, Fenster, WFE

### Claim 1.1 — Anchored vs. Rolling: Regime-Abhängigkeit entscheidet, nicht Geschmack
**Source:** fortraders.com — "How To Avoid Bias in Backtesting"
**URL:** https://fortraders.com/blog/how-to-avoid-bias-in-backtesting
**Date:** 2026-08-31
**Excerpt:** "Anchored walk-forward keeps the start date fixed and extends the in-sample window forward each step. Rolling walk-forward slides a fixed-length window forward, dropping old data as it adds new. Use anchored when you believe the underlying market regime is stable… Use rolling when you're trading something regime-sensitive, like an NQ scalp that behaves differently in low-VIX grinds versus FOMC volatility — a rolling window forces the strategy to keep re-proving itself on recent conditions rather than getting diluted by 2019 price action."
**Confidence:** Hoch (konsistent über ≥4 unabhängige Quellen: newyorkcityservers [^1^], fortraders [^2^], freyafinance [^4^], echozero [^5^]).

### Claim 1.2 — Konkrete Fenster-Empfehlung für Intraday/Retail: 18–24 Monate IS / 3–6 Monate OOS, mindestens 6 Folds
**Source:** fortraders.com — "How to Use AI to Optimize Your Trading Strategy"; luxalgo.com Stress-Test-Guide
**URL:** https://fortraders.com/blog/use-ai-optimize-trading-strategy ; https://www.luxalgo.com/blog/stress-test-your-algorithmic-trading-strategy-guide-to-avoiding-overfitting/
**Date:** 2026-07-21 / 2026-07-08
**Excerpt:** "For most multi-asset strategies — particularly anything touching XAUUSD or US indices where microstructure shifted meaningfully after 2020 — a rolling window of 18–24 months training with a 3–6 month out-of-sample test period is a practical starting point. Run a minimum of six folds before you trust the aggregate result." LuxAlgo: "For highly liquid markets like major Forex pairs or Gold, an in-sample window of 18–24 months paired with a 6-month out-of-sample window is a solid baseline."
**Confidence:** Hoch (zwei unabhängige Practitioner-Quellen mit identischen Zahlen).

### Claim 1.3 — Pardo-Konfigurationsrahmen: IS 2–5 Jahre (Daily) / 3–12 Monate (Intraday), OOS = 10–25 % der IS-Länge, Advancement = OOS-Länge (non-overlapping)
**Source:** tradelosstracker.com — Extended Summary von Robert Pardo, "The Evaluation and Optimization of Trading Strategies" (Pardo 1992/2008)
**URL:** https://tradelosstracker.com/library/book/44/extended
**Date:** o.D.
**Excerpt:** "In-sample length: 2-5 years for daily strategies; 3-12 months for intraday. Out-of-sample length: 10-25% of the in-sample length is typical. Window advancement: Equal to the out-of-sample length (non-overlapping) or less (overlapping)."
**Confidence:** Hoch (Pardo ist die kanonische Primärquelle für WFA; entspricht 4:1 bis ~9:1 IS:OOS-Verhältnis).

### Claim 1.4 — WFE-Definition und Schwellen: WFE = annualisierte OOS-Performance / annualisierte IS-Performance; <50 % = Overfitting-Verdacht, 50–70 % akzeptabel, >70–80 % stark, >90–100 % selbst verdächtig (Lookahead?)
**Source:** Pardo via tradelosstracker; luxalgo; echozero; ProRealTime-Doku
**URL:** https://tradelosstracker.com/library/book/44/extended ; https://blog.echozero.app/glossary/walk-forward-analysis ; https://www.prorealcode.com/wp-content/uploads/2018/09/probacktest.pdf
**Date:** o.D.
**Excerpt:** Pardo-Interpretationstabelle: ">80% Excellent — deploy with confidence; 60-80% Good; 40-60% Acceptable but concerning — deploy at reduced size; 20-40% Poor — do not deploy at full size; <20% Failed — strategy is likely overfit; Negative — abandon." echozero: "A WFE of 100% or higher actually raises red flags — it might indicate you're inadvertently introducing lookahead bias." ProRealTime: "if at least 3/5 test periods display a WFE ratio greater than 50%-60%, the strategy can be considered to be robust."
**Confidence:** Hoch (4 Quellen, konsistente Schwellen). Praktische Degradations-Variante: OOS-Sharpe/IS-Sharpe > 0.6 akzeptabel, < 0.4 overfit, < 0.2 verwerfen (fortraders [^3^]).

### Claim 1.5 — Erwartbare OOS-Degradation: ~30–60 % schlechter als IS ist normal; Beispiel-Tabelle Backtest → WFA → Live
**Source:** lobehub Walk-Forward-Skill; algorier.com
**URL:** https://lobehub.com/de/skills/brainbytes-dev-everything-claude-trading-walk-forward-optimization ; https://algorier.com/blog/walk-forward-analysis/
**Date:** 2026-05-15 / 2026-08-29
**Excerpt:** "Core advantages are realistic forward-performance estimates (expect OOS degradation of ~30–60% vs IS)". algorier-Beispiel: Backtest 38 % p.a./Sharpe 2.0/DD 9 % → WFA 21 %/1.2/17 % → Live 18 %/1.1/19 %.
**Confidence:** Mittel-Hoch (Practitioner-Heuristik, plausible Richtung; exakte Werte strategieabhängig).

### Claim 1.6 — Final Holdout: ein letztes, nie angefasstes OOS-Segment reservieren
**Source:** lobehub Walk-Forward-Skill
**URL:** https://lobehub.com/de/skills/brainbytes-dev-everything-claude-trading-walk-forward-optimization
**Date:** 2026-05-15
**Excerpt:** "Best practices include reserving a final unseen holdout and avoiding repeated peeks at OOS results."
**Confidence:** Hoch (Standard in der ML-/Quant-Literatur). backtrex ergänzt: "Once parameters are fixed on the IS period, test exactly once on the OOS period. If you are tempted to adjust parameters after the OOS test, start over completely." [^23^]

---

## 2. Overfitting-Metriken im Detail

### Claim 2.1 — Deflated Sharpe Ratio (DSR): Formel
DSR = PSR mit der erwarteten maximalen Sharpe unter der Nullhypothese (N unabhängige Trials) als Benchmark SR₀ statt 0:

```
DSR = Φ( (SR̂* − SR₀)·√(T−1) / √(1 − γ̂₃·SR₀ + ((γ̂₄−1)/4)·SR₀²) )
```

mit SR̂* = beobachtete (nicht-annualisierte) Sharpe, SR₀ = erwartetes Sharpe-Maximum aus N Trials (False Strategy Theorem), γ̂₃ = Skew, γ̂₄ = Kurtosis der Returns, T = Stichprobenlänge, Φ = Standardnormal-CDF.
**Source:** wikibin.org — "Deflated Sharpe ratio" (Bailey & López de Prado, JPM 2014)
**URL:** https://wikibin.org/articles/deflated-sharpe-ratio.html
**Date:** 2026-06-26
**Excerpt:** "The DSR will increase with: greater observed SRs, longer track records, positively skewed returns. The DSR decreases with fatter tails (Kurtosis)."
**Confidence:** Hoch (Formel deckt sich mit dem Original-Paper; mehrere unabhängige Wiedergaben).

### Claim 2.2 — Erwartetes Maximum unter der Null (getExpMaxSR) — Referenz-Implementierung in 5 Zeilen
```python
import scipy.stats as ss, numpy as np
def getExpMaxSR(mu, sigma, numTrials):
    emc = 0.5772156649  # Euler-Mascheroni
    maxZ = (1 - emc) * ss.norm.ppf(1 - 1. / numTrials) \
         + emc * ss.norm.ppf(1 - 1. / (numTrials * np.e))
    return mu + sigma * maxZ
```
**Source:** rollbrains.com — "The Deflated Sharpe Ratio: Why a 2.5 Sharpe Can Still Be Statistical Noise"
**URL:** https://rollbrains.com/quant/deflated-sharpe-ratio/
**Date:** 2026-06-09
**Excerpt:** "count every trial, deflate against the expected maximum, and treat any Sharpe whose DSR sits below 0.95 as unproven — no matter how large the raw number looks. … The hardest input is honest: the number of independent trials N. It is not the number of strategies you saved — it is the number you tried, including every parameter sweep, every discarded variant."
**Confidence:** Hoch.

### Claim 2.3 — Fertige DSR-Implementierung (vollständige Python-Funktion mit Skew/Kurtosis)
paperswithbacktest liefert eine direkt nutzbare `deflated_sharpe_ratio(observed_sr, sr_benchmark, t_obs, skew, kurtosis)` mit Nenner `sqrt((1 − skew·sr + (kurt−1)/4·sr²)/(T−1))` und Ausgabe `norm.cdf(z)`. Beispiel: 200 Trials, bester SR 1.8, 3 Jahre Tagesdaten → DSR < 0.95 → "likely overfit".
**Source:** paperswithbacktest.com/course/deflated-sharpe-ratio
**URL:** https://paperswithbacktest.com/course/deflated-sharpe-ratio
**Date:** o.D.
**Confidence:** Hoch (Code prüfbar; numerisch äquivalent zu quanthedgeai-Implementierung [^9^]).

### Claim 2.4 — PBO via CSCV: Verfahren, Schwellen, Anti-Patterns
CSCV (Bailey, Borwein, López de Prado, Zhu 2015/2017): Aus der T×K-Matrix per-Periode-Returns (K = Parameterkandidaten) wird T in 2S Blöcke geteilt; über alle C(2S,S)-Kombinationen (bei S=8: 12.870 Splits) wird das IS-Optimum gewählt und sein OOS-Rang bestimmt; PBO = Anteil der Splits, in denen der IS-Sieger unter der OOS-Median liegt. **Null ist 0,5 (Münzwurf), nicht 1** — PBO ≈ 0.5 = kein OOS-Skill; echter Edge treibt PBO → 0.
Schwellen (aligrithm): PBO < 0.10 deploy; 0.10–0.30 moderat (kleineres Kapital, Kill-Switches); 0.30–0.50 hoch (nicht deployen ohne Parameterreduktion); > 0.50 verwerfen.
Anti-Patterns: PBO auf einem einzelnen Parameterset berechnen (braucht volle T×K-Matrix); K nach Sichtung des PBO ändern (K muss vorher fixiert sein); nur eine Optimierungsmetrik prüfen.
Daten-Anforderungen: T ≥ 16× Autokorrelationshorizont, praktisch 500+ Beobachtungen (Daily).
**Source:** aligrithm.com — "CSCV: A Direct Probability of Backtest Overfit"; suenot/pbo-search (GitHub, kontrollierte Studie)
**URL:** https://aligrithm.com/cscv-a-direct-probability-of-backtest-overfit/ ; https://github.com/suenot/pbo-search
**Date:** 2026-07-27 / 2026-07-02
**Excerpt (pbo-search):** "null (200 iid zero-edge strategies): PBO 0.476, selected IS Sharpe 1.98 → OOS 0.06. Planted edge: PBO 0.001. Overfit MA-grid on random walk: PBO 0.463 — statistically indistinguishable from the null; best IS Sharpe 2.33 collapses to median OOS −0.22, 63% chance of an OOS loss."
**Confidence:** Hoch (Replikationsstudie mit synthetischer Ground Truth).

### Claim 2.5 — Python-Paket-Landschaft für PBO/DSR/Purged-CV (was existiert, was selbst bauen)
- **backtest-guard** (PyPI, MIT, numpy+scipy only): DSR, PSR, PBO/CSCV, PurgedKFold, Lookahead-Detektoren — "one job: is this backtest statistically sound?" [^13^]
- **pypbo** (GitHub esvhd/pypbo): spezialisierte CSCV/PBO-Referenz-Implementierung. **Achtung: kein PyPI-Paket namens `pbo`** (verifizierter 404) — `pip install pbo` schlägt fehl. [^14^]
- **R-Paket `pbo` auf CRAN**: kanonische Referenz inkl. Performance-Degradation und stochastischer Dominanz. [^14^]
- **arch (bashtage)**: `arch.bootstrap.SPA` (= White's Reality Check alias `arch.bootstrap.RealityCheck`), `StepM`, `MCS` — mit stationärem/circular/moving-block Bootstrap, `reps=1000` default, studentized. [^15^][^16^]
- **skfolio.model_selection**: `CombinatorialPurgedCV` und `WalkForward` — gewartete, BSD-3-lizenzierte, sklearn-kompatible CPCV-Implementierung. [^17^]
- **mlfinlab**: nicht via PyPI installierbar; offenes GitHub-Repo de facto leer, echter Code kommerziell. Fork **mlfinpy** 0.1.2 dormant seit 2025-01. **timeseriescv/filterpy**: tot (2018). [^17^]
**Source:** github.com/AgentJDrew/backtest-guard; guetaquant.com; arch-Dokumentation; christopherspenn.com Investment-Report
**URL:** https://github.com/AgentJDrew/backtest-guard ; https://guetaquant.com/blog/validar-backtest-sin-autoenganarse/ ; https://bashtage.github.io/arch/multiple-comparison/multiple-comparison-reference.html ; https://www.christopherspenn.com/interactives/investment-report-example.html
**Date:** 2026-07-06 / 2026-09-01 / o.D. / 2026-08-02
**Confidence:** Hoch für Paket-Fakten (mehrfach verifiziert); Hinweis: backtest-guard/backtest-audit sind junge Repos — API-Stabilität vor Produktiv-Einsatz pinnen.

### Claim 2.6 — White's Reality Check (2000) vs. Hansen's SPA (2005): Unterschied und wann welcher Test
White RC testet H₀: beste Strategie ≤ Benchmark unter Data-Snooping-Korrektur (Bootstrap-Verteilung des Max-Stats). SPA ist die studentisierte, mächtigere Verbesserung: adaptives Re-Centering, berücksichtigt Kreuz-Korrelationen zwischen Strategien, weniger konservativ. Faustregel: SPA bevorzugen bei großen, korrelierten Parameter-Grids; RC ok bei kleinen Kandidatenpools. Beide brauchen 1000+ Bootstrap-Replikationen.
**Source:** quantifiedtrader.com; lobehub Overfitting-Prevention-Skill; arch-Doku
**URL:** https://quantifiedtrader.com/projects/statistical-analysis-trading-strategies/ ; https://arch.readthedocs.io/en/stable/multiple-comparison/multiple-comparison-reference.html
**Date:** o.D.
**Excerpt:** "For the same 100-strategy example where White's RC yields p ≈ 0.926, SPA can reject at α = 0.05 when genuine signal and cross-strategy correlation structure support detection."
**Confidence:** Hoch (Original-Literatur + Paket-Doku deckungsgleich). Praxis-Note: Für unsere Pipeline liefert DSR+PBO denselben Kernschutz mit weniger Implementierungsaufwand; SPA via `arch` ist der einfachste dritte Baustein (Benchmark = Buy&Hold oder Null-Loss-Serie).

### Claim 2.7 — Harvey-Liu-Haircut und MinTRL als Ergänzung
**Source:** quantskills/skill-backtest-overfit (GitHub)
**URL:** https://github.com/quantskills/skill-backtest-overfit
**Date:** 2026-07-03
**Excerpt:** Demo: 200 reine Noise-Strategien, bester Sharpe 1.65 → DSR 0.63 < 0.95 → FAIL, PBO 0.34, Haircut −61 %. Mit echtem Edge: Sharpe 2.58 → DSR 0.98 → PASS, PBO 0.06, Haircut −22 %. Methoden-Tabelle: DSR (Bailey/LdP 2014), PBO/CSCV (Bailey et al. 2017), Purged+Embargoed CV (AFML 2018, Kap. 7), Haircut Sharpe (Harvey & Liu 2015), Minimum Track Record Length.
**Confidence:** Mittel-Hoch (Repo-Demo mit synthetischen Daten, aber Methoden-Zuordnung korrekt).

### Claim 2.8 — Purged K-Fold + Embargo: konkrete Regel und Embargo-Größe
Für jedes Test-Fold t: Trainings-Observation i behalten, wenn `t_start[i] >= t_end[test] + embargo` **ODER** `t_end[i] <= t_start[test] − embargo` (disjunktiv!). Embargo-Empfehlung: de Prado AFML §7.4.2 = 0.01 (1 % der Stichprobe); bei Minutendaten entspricht das ~1–2 Handelstagen; Kriterium: Embargo erhöhen, bis die Varianz der K-Fold-OOS-Scores nicht mehr signifikant sinkt.
**Source:** quant67.com (Purged-CV-Umsetzungsdetails); christopherspenn.com (Korrektur der UND/ODER-Falle); mlfinlab-Doku
**URL:** https://quant67.com/post/quant/21-walkforward-cv/21-walkforward-cv.html ; https://www.mlfinlab.com/en/latest/cross_validation/purged_embargo.html
**Date:** 2026-05-01 / o.D.
**Confidence:** Hoch. **Wichtige Detailfalle:** Eine verbreitete KI-generierte Version formuliert die Purge-Bedingung als Konjunktion — das löscht den gesamten Trainingssatz. [^17^]

---

## 3. Monte-Carlo-Validierung und Prop-Firm-Risikoabschätzung

### Claim 3.1 — Trade-Shuffling: 5.000–10.000 Iterationen, Drawdown ist sequenzabhängig — Sizing auf das 95. Perzentil, nicht aufs Backtest-Maximum
**Source:** fortraders.com — "Backtesting Strategies That Actually Work"; lobehub Monte-Carlo-Skill
**URL:** https://fortraders.com/blog/backtesting-strategies-that-actually-work ; https://lobehub.com/skills/brainbytes-dev-everything-claude-trading-monte-carlo-simulation
**Date:** 2026-07-23 / 2026-03-15
**Excerpt:** "Run 5,000 Monte Carlo iterations on your trade log. If your backtest shows a 12% maximum drawdown but the 95th percentile across those iterations shows 25%, your real drawdown budget is 25%. Not 12%. The 12% figure is the lucky path. Build your position sizing around the 95th percentile number." Lobehub-Beispiel (Sharpe 1.0, 5 Jahre daily): Backtest-DD 12 %, Bootstrap-Median 14 %, 90. Perzentil 22 %, 99. Perzentil 35 %.
**Confidence:** Hoch (zwei unabhängige Quellen, numerisch konsistentes Muster).

### Claim 3.2 — Block-Bootstrap vs. Shuffling: bei Autokorrelation (Regime-Clustering) ist IID-Shuffling zu optimistisch
**Source:** susanpotter.net — "Bootstrap Methods for Strategy Robustness"; euro-macromechanica-backtest (GitHub)
**URL:** https://www.susanpotter.net/quant/bootstrap-methods-strategy-robustness/ ; https://github.com/euro-macromechanica-backtest/results
**Date:** 2026-05-23 / o.D.
**Excerpt:** "The standard rule of thumb is l ~ T^(1/3)… Politis and White (2004) developed an automatic block length selection procedure… never report bootstrap results at a single block length. If your conclusions change when you double or halve the block length, you don't have a robust result." Stationary Bootstrap (Politis-Romano 1994): randomisierte Blocklängen, Parameter p; für tägliche Finanz-Returns typische mittlere Blocklängen 7–20 Handelstage. euro-macromechanica-Praxisbeispiel: stationary_bootstrap auf Monatsblöcken, 10.000 Pfade, Seed 42, mittlere Blocklängen 3–12 Monate als Grid.
**Confidence:** Hoch. **Praxis-Regel für uns:** Trade-Shuffling (IID) als Basis + Stationary/Block-Bootstrap als Robustheitscheck; beide berichten.

### Claim 3.3 — Random-Entry-Benchmark als Falsifikationstest
**Source:** github.com/AaroNLaU0307/quant-backtest-framework (PROJECT_BRIEF)
**URL:** https://github.com/AaroNLaU0307/quant-backtest-framework/blob/main/docs/PROJECT_BRIEF.md
**Date:** 2026-06-01
**Excerpt:** "Random-entry benchmark: same risk model, randomized entries → test whether the strategy's edge exceeds random entry. This is the core falsification test — keep it central. … Multiple-testing correction — mandatory. Apply Benjamini–Hochberg FDR, and report the Deflated Sharpe Ratio and Probabilistic Sharpe Ratio, explicitly feeding in the number of trials."
**Confidence:** Mittel-Hoch (einzelnes Repo-Briefing, aber methodisch standardkonform).

### Claim 3.4 — Prop-Firm-Simulation: LuxAlgo prop-firm-sim (Open Source) als Referenz-Engine
**Source:** github.com/LuxAlgo/prop-firm-sim
**URL:** https://github.com/LuxAlgo/prop-firm-sim
**Date:** 2026-08-24
**Excerpt:** "Open-source Monte Carlo simulation of prop-firm challenges over each firm's exact ruleset. Pass probability, expected attempts and cost, EV, optimal risk sizing. … 10,000 paths, seed 42." Beispiel-Output: FTMO 100K 2-Step, WR 48 %, 1.6R, 4 Trades/Tag, 1 % Risiko → Pass-Wahrscheinlichkeit 93.2 % pro Attempt; Max-DD p50 5.9 %, p95 12.5 %. **Dokumentierte Limitationen der Engine:** "trades-resolve-same-day" (kein Overnight-Holding), "intra-trade-excursions-not-modeled" → unterschätzt Trailing-DD- und Open-PnL-Breach-Risiko; "real odds are somewhat worse".
**Confidence:** Hoch (Code + explizite Annahmen-Liste). Genau diese Limitationen müssen wir in unserer eigenen Sim aufheben (unsere Bots halten intraday mit Floating-PnL).

### Claim 3.5 — Daily-Loss-Falle quantifiziert: 5 Verlierer an einem Tag bei 55 % WR = 1.8 %; über 25 Handelstage ≈ 37 % Wahrscheinlichkeit, das Tageslimit zu reißen
**Source:** grandalgo.com — "Prop Firm Risk of Ruin"; FTMO-Blog
**URL:** https://grandalgo.com/blog/prop-firm-risk-of-ruin-guide ; https://ftmo.com/en/blog/how-to-use-monte-carlo-simulations-to-pass-the-ftmo-challenge/
**Date:** 2026-03-24 / 2026-07-31
**Excerpt:** "Consider a trader risking 1% per trade on a $100K challenge with a $5,000 daily loss limit… Five losses in a single day hits the limit exactly. The probability of 5 consecutive losses for a 55% win rate trader is (0.45)^5 ≈ 1.8%. … Over 25 sessions, the probability of at least one 5-loss day is approximately 37%. More than one in three challenges will fail on the daily limit alone. … The solution is a daily trade cap that makes it mathematically impossible to breach the daily limit. If your maximum daily exposure stays below 80% of the daily loss limit, you create a buffer."
**Confidence:** Hoch (arithmetisch nachvollziehbar; 1−(1−0.018)^25 ≈ 36 %). FTMO bestätigt: Risikoreduktion von 2 % → 0.5–1 % kann Pass-Wahrscheinlichkeit "from 15% to 85%" heben. [^27^]

### Claim 3.6 — FTMO-Regelwerk exakt: Daily Loss = 5 % der **Vortags-Schlussbilanz**, inkl. Floating PnL, Echtzeit überwacht
**Source:** backtrex.com — "Backtesting With Prop Firm Rules"; tradingfunder.com FTMO-Review
**URL:** https://backtrex.com/en/blog/backtesting-prop-firm-rules ; https://tradingfunder.com/ftmo-rules/
**Date:** 2026-05-22 / 2026-05-24 (re-checked)
**Excerpt:** "FTMO calculates daily loss as the sum of closed position results for the day plus the floating loss on open positions. The limit is 5% of the previous day's closing balance… If your balance has grown to $108,000, your daily limit is $5,400. … the daily loss is calculated against the previous day's balance, not the initial challenge balance. … FTMO monitors loss in real time." Achtung: FTMO 1-Step verwendet **3 % Daily Loss + EOD-Trailing-Max-Loss** — regelwerkabhängig simulieren. Kalibrierformel: `Max Risiko/Trade = Daily-Loss-Limit / max. simulierte aufeinanderfolgende Intraday-Verlierer`; Ziel: globaler Max-DD < 8 % im Backtest (Puffer vor der 10 %-Grenze), min. 3–5 Jahre Daten.
**Confidence:** Hoch (mehrere Quellen, inkl. FTMO-naher Seiten). Konsequenz für die Pipeline: Die MC-Sim muss **Tages-PnL-Aggregate inkl. Floating Loss** aus Tick-/M1-Pfaden bilden, nicht nur Closed-Trade-R-Multiples shufflen.

### Claim 3.7 — Losing-Streak-Mathematik für die Sim-Plausibilisierung
P(N aufeinanderfolgende Verlierer) = (1−WR)^N. Erwartete längste Streak in N Trades wächst ~logarithmisch. Beispiele: 60 % WR → 6er-Streak in 200 Trades mit 63.8 % Wahrscheinlichkeit; 50 % WR → 7er-Streak in 100 Trades ≈ 55 %, 10er-Streak ~einmal pro 1.000 Trades. Risk-of-Ruin-Formel: RoR = (LossRate/(WR·RR))^(Threshold/RiskPerTrade); N Verlierer bis 50 % DD: N = log(0.5)/log(1−Risk) → 0.5 % Risk = 138, 1 % = 69, 2 % = 35.
**Source:** fxnx.com Streak-Tables; pomegra.io; journalplus.co RoR-Calculator; tradeology.app
**URL:** https://fxnx.com/en/blog/consecutive-loss-math-streak-tables-every-win-rate ; https://www.itafx.com/blog/risk-of-ruin-trading/
**Date:** 2026-08-27 / o.D.
**Confidence:** Hoch (reine Kombinatorik). **Prop-Kontext-Warnung (itafx):** "A strategy with 2% risk per trade might have only 1% mathematical ruin risk but 67% chance of breaching prop firm limits due to clustered losses and daily restrictions." [^32^]

---

## 4. Realistische Kostenmodelle

### Claim 4.1 — Spread-Modellierung: nur "Every tick based on real ticks" liefert historische Bid/Ask; "Current"-Spread und Fixwerte sind Fiktion
**Source:** fortraders.com — "How to Backtest a Strategy in MT5 (Advanced Guide)"; ispybuy.com MT5-Modi-Vergleich
**URL:** https://fortraders.com/blog/backtest-strategy-in-mt5-advanced-guide ; https://ispybuy.com/blog/mt5-strategy-tester-every-tick-vs-real-ticks-vs-ohlc/
**Date:** 2026-08-23 / 2026-07-28
**Excerpt:** "The only honest option for variable-spread accounts is real ticks with historical bid/ask baked in — this replays the actual spread widening that happened at 8:30am EST on NFP day, not a flat number." ispybuy-Modi-Tabelle: OHLC = "Close-only entries/exits, quick parameter screening"; Every Tick = synthetisch aus M1, "smoother but modeled"; Real Ticks = "the only mode where the answer to 'did price touch the stop before the target inside this bar' is a fact rather than a modeled inference". Modeling Quality < ~90 % = Rekonstruktion, kein Protokoll.
**Confidence:** Hoch. **Für Python-Backtests (pymt5trade):** MT5 liefert via `copy_ticks_range` echte Bid/Ask-Ticks inkl. historischem Spread — Spread-Zeitreihe daraus extrahieren (Session-Median + News-Perzentile) statt Konstanten.

### Claim 4.2 — Slippage-Steuer: 0.5–1.2 Pips Friktion pro Roundtrip killt dünne Scalping-Edges; Basis-Kosten ≥ 1.5× Advertised-Spread + volle RT-Kommission
**Source:** fxnx.com — "Backtest Spread and Slippage: Realistic Execution Testing"
**URL:** https://fxnx.com/en/blog/backtest-spread-slippage-costs-your-tester-skips
**Date:** 2026-08-23
**Excerpt:** Beispiel 60 % WR, 6 Pip TP/SL: theoretische Expectancy +1.2 Pips/Trade → nach 0.4 Pip Entry-Spread-Widening + 0.5 Pip SL-Slippage + 0.2 Pip Queue-Effekt = +0.3 Pips → "Your edge just decayed by 75%. If you add broker commissions, the strategy is dead." Kommission ECN: $3.50–$7.00 pro Lot Round-Turn (= 0.35–0.70 Pips EUR/USD). "always set your base transaction cost minimum to at least 1.5x the advertised broker spread plus full round-turn commission."
**Confidence:** Hoch (konsistent mit DAX-Studie aus wide01: 3 Pts Slippage → PF 1.25→0.96).

### Claim 4.3 — Rollover-Blindheit: 23:00–00:00 Serverzeit Spread-Explosion (EUR/USD 0.2→4.5 Pips, AUD/NZD 1.2→12 Pips) ist in M1-OHLC unsichtbar
**Source:** fxnx.com — "Tick Data vs 1-Minute OHLC: What Your MT5 Backtest Really Models"
**URL:** https://fxnx.com/en/blog/tick-data-vs-1-minute-ohlc-what-your-mt5-backtest-really
**Date:** 2026-09-01
**Excerpt:** "At 17:00 New York time (23:00 or 00:00 on most European broker servers)… top-of-book liquidity drops precipitously: EUR/USD spreads jump from 0.2 pips to 4.5 pips… any overnight grid or night-scalping EA holding trades through rollover would see its stop-loss hit purely by the expanding Ask price — an event completely invisible in M1 OHLC mode."
**Confidence:** Hoch (BIS-Liquiditäts-Referenz + konkrete Zahlen). **Pipeline-Regel:** Keine Orders/kein Halten über 23:00 Server-Rollover, oder explizites Rollover-Spread-Regime im Kostenmodell.

### Claim 4.4 — Swap-Modellierung: MT5-Backtests nutzen **heutige** Swap-Werte für die gesamte Historie (Static Swap Distortion)
**Source:** fxnx.com — "Swap Rate Change Log"
**URL:** https://fxnx.com/en/blog/swap-rate-change-log-dated-monthly-snapshots-instrument
**Date:** 2026-08-19
**Excerpt:** "[2021 Backtest Bar] → Uses Today's (2024) Swap Settings… Reality in 2021: Swap was actually POSITIVE (+$3.20/day). Result: Viable historical carry systems are discarded as unprofitable. … Correcting: Export raw trade execution logs; load historical interbank Tom-Next rates; add realistic broker markups (+1.5 pips asymmetrical wedge); calculate day-by-day financing dynamically; run Monte Carlo expanding broker swap markup by 20% to 50%."
**Confidence:** Hoch. Swap-Mathematik (Punkte-Modus): `Nightly Swap = Lots × ContractSize × PointSize × SwapValue`; Triple-Swap-Tag pro Symbol via `SYMBOL_SWAP_ROLLOVER3DAYS` (meist Mi für FX/Metalle, teils Fr für Indizes/Energien — brokerabhängig, z. B. IC Markets: Mi für FX/Metals, Fr für Energies/Indices/Crypto). [^38^][^39^][^40^]

### Claim 4.5 — Swap als Prop-Firm-Todesfalle: Midnight-Swap-Debit zählt ins Daily Loss
**Source:** fxnx.com — "Swap Long and Swap Short: Reading the MT5 Specification Tab"
**URL:** https://fxnx.com/en/blog/swap-long-swap-short-reading-mt5-specification-tab
**Date:** 2026-08-25
**Excerpt:** "Most prop firm evaluations enforce strict daily drawdown limits calculated at 17:00 EST / 00:00 server time. Swap debits are executed at this precise rollover mark. [Beispiel] Floating -$3,850 + Wednesday 3x Swap -$220 = -$4,070 → Daily Drawdown BREACH (Account Closed). Even if your stop-loss was never hit."
**Confidence:** Hoch. **Bot-Regel:** Positions-Close vor Rollover (z. B. 23:55 Server) wenn Swap negativ, besonders mittwochs.

### Claim 4.6 — MT5-Tester berechnet **keine Kommission** — muss im eigenen Python-Backtest hardcodiert werden
**Source:** strategyquant.com Forum (MT5 backtest report commissions); fxnx MT4-vs-MT5-Divergenz
**URL:** https://strategyquant.com/forum/topic/mt5-backtest-report-how-to-add-broker-commissions/ ; https://fxnx.com/en/blog/mt4-vs-mt5-backtest-divergence-one-ea-two-engines
**Date:** 2019-08-11 / 2026-08-25
**Excerpt:** "There are NO broker commissions in the MT5 strategy tester/backtest report. This totally skews the final result (especially if you are using a scalping one). A typical Forex broker commission is $3.5 per full Lot per side." Zusätzlich: Hedging vs. Netting im MT5-Tester explizit konfigurieren; Gold: Contract Size 100 oz beachten; Indizes: Spreads außerhalb der Haupthandelszeit oft 3×.
**Confidence:** Hoch für Kommissions-Fakt (und heute noch gültiges Verhalten des Testers; im eigenen Engine-Code ohnehin selbst zu modellieren).

### Claim 4.7 — Timezone-Fallen: MT5-Serverzeit meist GMT+2/GMT+3 (US-DST-folgend), Wechsel zweimal jährlich mit 1-h-Lücke zwischen US- und EU-Umstellung
**Source:** kcmtrade.com Server-Adjustment-Notice; VT Markets FAQ; Tick Data Suite Changelog; backtestmarket.com DST-Guide
**URL:** https://www.kcmtrade.com/news/mt4-mt5-server-time-zone-adjustment-notice-5 ; https://get.vtmarkets.help/hc/en-us/articles/37317868198297 ; https://eareview.net/tick-data-suite/changelog ; https://www.backtestmarket.com/en/blog/forex-daylight-saving-time
**Date:** 2026-02-24 / o.D. / 2026-05-27 / 2026-08-24
**Excerpt:** "the MT4/5 server time zone will change from GMT+2 to GMT+3 starting from Monday, March 9, 2026 [US-DST 8. März, EU-DST erst 29. März]". VT Markets: "server midnight (00:00) aligns with the New York closing time (5 pm EST)". TDS: "most brokers are using GMT+2 with US DST" als Default. Backtestmarket-Regeln: "Convert every timestamp to UTC at ingestion; never hardcode broker offsets; watch the gap weeks (US/EU switches land on different dates); run backtests across March and November DST weeks and check for one-hour jumps in trade timestamps."
**Confidence:** Hoch. **Konkrete Python-Falle:** MetaTrader5-Python-API (`copy_rates_*`) erwartet tz-aware datetimes — MetaQuotes-Referenzcode setzt `pytz.timezone("Etc/UTC")`, "to avoid the implementation of a local time zone offset" [^44^]; die gelieferten Bar-Zeiten sind Serverzeit, als Epoch kodiert. Für Session-Logik (z. B. "13:00–15:00 GMT Overlap") muss Serverzeit → UTC konvertiert werden, mit **historischem, DST-abhängigem Offset** (2 oder 3 h), sonst wandern Session-Fenster im Backtest zweimal jährlich um eine Stunde. Verifikation: NFP-Zeitpunkt-Matching oder Daily-Bar-Alignment.

---

## 5. Common Backtest-Fallen

### Claim 5.1 — Lookahead: Shift-Test als Detektor
**Source:** nexural.io backtesting.pdf; rollbrains.com Lookahead-Anatomie; hudson-and-thames Vectorized-Backtest-Tutorial
**URL:** https://www.nexural.io/pdfs/backtesting.pdf ; https://rollbrains.com/tradingview/backtest/lookahead-bias-penetration/ ; https://github.com/hudson-and-thames/backtest_tutorial
**Date:** o.D. / 2026-06-01 / 2023-12-30
**Excerpt:** "Shift every input by one bar and re-run. If returns collapse, look-ahead was present. … Compute the signal on bar T, execute on bar T+1 open. Never let the same bar produce the signal AND the fill price." Rollbrains: klassische Defekte = `pandas .shift(-1)`-Missbrauch, unfertige HTF-Kerze via `request.security()`, Snooping auf ATR(t) der laufenden Kerze → "Artificial 99.8% win rate distortion".
**Confidence:** Hoch (entspricht unserer close[1]-Anti-Repainting-Regel aus wide01/wide05).

### Claim 5.2 — Repainting-Indikatoren: MQL/Pine-Mechanismen + 4-Stufen-Audit
**Source:** fxnx.com — "Repainting Indicators: How to Test & Identify Repainting"
**URL:** https://fxnx.com/en/blog/repainting-indicators-how-test-if-your-indicator-repaints
**Date:** 2026-08-29
**Excerpt:** Mechanismen: Pine `request.security()` ohne `close[1]`+`lookahead_off`; fehlendes `barstate.isconfirmed`; MQL Forward-Indexing (`close[i-1]` in Rückwärtsschleife = Zukunft); falsches `prev_calculated`-Handling; `PLOT_SHIFT`-Illusion. Audit: (1) Forward-Logging über ≥50–100 Live-Kerzenschlüsse, (2) Static-vs-Live-Abgleich (frische Chart-Instanz vs. unbearbeiteter Live-Chart), (3) Tick-Simulation, (4) Stress-Test. Red Flags: "90%+ Win Rates", Arrows exakt auf Wick-Extremen, Closed-Source ohne Forward-Record.
**Confidence:** Hoch.

### Claim 5.3 — Intrabar-Ambiguität: gleiche OHLC-Bar ≠ gleiche Preis-Sequenz; bei Stop UND Target in derselben Bar entscheidet die (unbekannte) Reihenfolge
**Source:** propquantlab.com — "Why Intraday Strategies Are Harder to Backtest"
**URL:** https://propquantlab.com/article-intraday-backtesting.html
**Date:** 2026-07-21
**Excerpt:** "If an intraday position has a stop and a target inside the same 15-minute bar, the bar alone may not establish which was hit first. The same ambiguity affects a trailing stop, a scale-in rule and an equity-based loss limit. … The right standard is not the maximum possible data resolution. It is whether the remaining uncertainty could reverse the strategy's conclusion."
**Confidence:** Hoch. **Konsequenz:** Für M5-Bots bei engem SL/TP M1-Daten als Intrabar-Pfad nutzen; wo auch M1 ambig bleibt, konservativ annehmen (Stop zuerst) — oder Tick-Daten.

### Claim 5.4 — Mindest-Stichproben: 30 Trades = CLT-Floor, 100 Basis, 200–500 "institutional grade" (López de Prado), 300+ für Daytrading, 1.000+ für Scalping; 30-Trades-pro-Parameter-Regel
**Source:** fxnx.com Sample-Size-Studie; backtestbase.com; backtrex Overfitting-Guide
**URL:** https://fxnx.com/en/blog/backtest-sample-size-how-many-trades-make-results-real ; https://www.backtestbase.com/education/how-many-trades-for-backtest ; https://backtrex.com/en/blog/overfitting-backtesting-detect-prevent
**Date:** 2026-09-02 / 2026-01-04 / 2026-05-31
**Excerpt:** fxnx: "Scalpers (M1–M5): minimum 1,000+ trades; Day Traders (M15–H1): 300 to 500 trades spanning 2 to 3 full calendar years." backtrex: "Apply the 30-trades-per-parameter rule: if your backtest generates 150 trades, you can only validate a strategy with at most 5 parameters." Kontext: 60 % WR auf 100 Trades → 95%-CI [49.7 %, 69.7 %].
**Confidence:** Hoch (deckt sich mit n ≥ 300 aus dem Gesamtkontext). Zusatzdimension: Trades müssen über **mehrere Regime** verteilt sein (Bull/Bear/Sideways), nicht nur über Zeit. [^30^]

### Claim 5.5 — Weitere MT5-spezifische Fallen: Datenqualität, Hedging/Netting, symbology
**Source:** fortraders.com Advanced Guide; fxnx MT4/MT5-Divergenz; quantmonitor.net (StrategyQuant Broker Profiles)
**URL:** https://fortraders.com/blog/backtest-strategy-in-mt5-advanced-guide ; https://quantmonitor.net/best-algorithmic-trading-software/
**Date:** 2026-08-23 / 2026-07-28
**Excerpt:** Journal-Checks: "mismatched charts error", fehlende Sessions, "flat-lined, zero-volume bars"; "Cannot model requotes, partial fills, liquidity holes around NFP/FOMC"; "Historical spread on some symbols is stored as a constant, which flatters scalping systems". StrategyQuant-Workflow als Vorbild: Broker-Profil (Timezone, DST, Sessions, Point Values) → Ziel-Broker-MT5-Daten für finale Validierung → "Compare individual trades between [Backtest-Engine] and MetaTrader. Investigate any material mismatch before deployment."
**Confidence:** Hoch.

### Claim 5.6 — Plausibilitäts-Benchmarks (Red-Flag-Tabelle)
**Source:** github.com/rudraymehra/AutoTheta — ML_TRADING_STRATEGIES_RESEARCH.md
**URL:** https://github.com/rudraymehra/AutoTheta/blob/main/ML_TRADING_STRATEGIES_RESEARCH.md
**Date:** 2026-03-30
**Excerpt:** Suspicious vs. Realistic vs. Excellent: Annual Return >30 % / 10–20 % / 15–25 %; Sharpe >3.0 / 0.5–1.5 / 1.5–2.5; MaxDD <5 % / 15–30 % / 10–20 %; Win Rate >70 % / 45–55 % / 55–60 %; Profit Factor >3.0 / 1.3–2.0 / 1.5–2.5.
**Confidence:** Mittel-Hoch (Heuristik, aber konsistent mit TradeAlgo-Regel aus wide05: Sharpe >3/WR >70 % = Overfitting-Definition). Passt zu unserem Ziel PF > 1.5 OOS: PF 1.5–2.5 gilt als "excellent/realistisch", PF > 3 als Red Flag.

---

## IMPLEMENTIERUNGS-SPEZIFIKATION — Validierungs-Pipeline (5 Bots, MT5/pymt5trade, Ziel PF > 1.5 OOS)

### Phase 0 — Daten- und Kostenfundament (vor jedem Backtest)
1. **Daten:** M1 + echte Ticks via `copy_rates_range`/`copy_ticks_range` vom **Ziel-Broker** (nicht Dukascopy-Fremddaten für finale Validierung). [^43^][^44^]
2. **Timezone-Normalisierung:** Alle Timestamps bei Ingestion nach UTC. Broker-Offset **dynamisch** bestimmen (NFP-Matching / Daily-Bar-Alignment), nie hardcodieren; Verifikations-Backtest über die März- und November-DST-Wochen. [^42^]
3. **Spread-Modell:** Historische Spread-Zeitreihe aus Tick-Daten; Fallback: Session-abhängiges Profil (Asia/London/NY/Rollover). Rollover-Fenster 23:00–00:00 Server: Spread × 5–20 oder Trading-Verbot. [^35^][^37^]
4. **Kosten-Stack pro Trade:** `Kosten = max(1.5 × Median-Spread, realer Tick-Spread) + RT-Kommission (Broker-exakt, z. B. $7/Lot RT) + Slippage(szenario)`; Swap taggenau bei Overnight-Holding inkl. Triple-Swap-Tag (`SYMBOL_SWAP_ROLLOVER3DAYS`), Swap-Stress +20–50 % Markup. [^36^][^38^][^39^]
5. **Anti-Lookahead-Contract:** Signal auf Kerze T (nur geschlossene Bars, close[1]-Konvention), Fill frühestens Open T+1; kein Zugriff auf unfertige HTF-Kerzen; Shift-Test: alle Inputs +1 Bar shiften → wenn Performance kollabiert, lag Lookahead vor. [^45^][^46^]

### Phase 1 — Basis-Backtest (pro Bot, pro Symbol)
6. Vollkosten-Backtest über ≥ 5 Jahre (M5–H1) bzw. ≥ 3 Jahre (H4-Swing), inkl. mindestens eines Stress-Regimes (2020-Covid, 2022-Vol, 2024–2025-Gold-Run).
7. **Abbruchkriterium 1 (Sample):** n < 300 Trades gesamt → Bot nicht validierbar (nicht "failed", sondern "nicht testbar" → längerer Zeitraum oder mehr Symbole). [^30^][^50^]
8. **Abbruchkriterium 2 (Red Flags):** PF > 3.0, WR > 70 %, Sharpe > 3 → Overfitting-Verdacht, Parameterzahl reduzieren (Regel: ≤ 1 freier Parameter pro 30 Trades). [^23^][^52^]
9. **Slippage-Stress-Matrix (Pflicht):** Gesamtkosten × {0.5, 1, 2, 3}. Bot besteht nur, wenn PF(2×) ≥ 1.2 und PF(3×) ≥ 1.0 (Referenz: DAX-Studie — 3 Pts Slippage killten PF 1.25 → 0.96; Scalping-Beispiel: 0.9 Pips Friktion = −75 % Edge). [wide01 ^155; ^36^]

### Phase 2 — Walk-Forward-Analyse
10. **Design (Default):** Rolling WFA, IS 24 Monate / OOS 6 Monate (4:1), Advancement = 6 Monate (non-overlapping) → über 8 Jahre ≈ 10–11 Folds (Minimum 6). Alternativ-Run: anchored (Robustheitscheck — wenn anchored deutlich schlechter, ist die Strategie regime-sensitiv → Rolling-Logik + Retraining-Kadenz 1–3 Monate in Live-Bot übernehmen). [^2^][^3^][^6^]
11. **Optimierung pro Fold:** nur auf IS-Fenster (Grid oder Optuna), Zielmetrik vorab fixiert (Vorschlag: OOS-robuste Metrik = PF × min(WFE-Proxy) oder Sharpe; **nicht** Net Profit).
12. **WFE-Gates:** WFE = OOS/IS (annualisierte Returns oder Sharpe-Verhältnis). Pass: WFE ≥ 0.5 im Median über Folds **und** ≥ 3/5 Folds mit WFE ≥ 0.5 (ProRealTime/Pardo-Regel) **und** mindestens 60 % der Folds OOS-profitabel. Fail: Median-WFE < 0.4 → verwerfen; 0.4–0.5 → reduzierte Größe/Überarbeitung. WFE > 1.0 → Lookahead-Audit (Phase 0.5 erneut). [^6^][^7^][^8^]
13. **Final Holdout:** letzte 12 Monate werden in Phase 1+2 **nie** angefasst; genau **ein** Durchlauf am Ende. Wer danach Parameter ändert, beginnt die Pipeline von vorn. [^10^][^23^]

### Phase 3 — Overfitting-Statistik (Selection-Bias-Abwehr)
14. **Trial-Buchhaltung:** Jede getestete Konfiguration (Parameter-Sweep, verworfene Variante, Filter-Experiment) wird in einer Trials-DB geloggt. N_eff für DSR = Anzahl Trials (konservativ: nominale Anzahl; daru.finance-Befund zeigt, dass selbst 50.000 nominale Trials nur ~434 effektive sein können — effektive Zahl via Clusteranalyse der Korrelationsmatrix der Trial-Returns, sonst nominal verwenden = strenger). [wide05 ^30; ^12^]
15. **DSR-Gate:** DSR ≥ 0.95 erforderlich (Implementierung: 20 Zeilen, Claim 2.2/2.3; Inputs: OOS-Return-Serie des gewählten Bots, N_eff, Skew/Kurtosis). [^11^][^12^][^13^]
16. **PBO-Gate (CSCV):** T×K-Matrix aller getesteten Parameter-Sets (Tages-Returns), S=8 (12.870 Splits). Pass: PBO < 0.10; 0.10–0.30 → deploy nur mit halber Größe + Kill-Switch; > 0.30 → verwerfen. K vor der Berechnung fixieren. Tools: `backtest-guard` (pip) oder `pypbo` (GitHub esvhd); Eigenbau ~100 Zeilen machbar (Logik in Claim 2.4 dokumentiert). [^13^][^14^][^21^]
17. **SPA-Gate (optional, billig via arch):** `arch.bootstrap.SPA(benchmark_losses, model_losses, bootstrap='stationary', reps=1000)` gegen Null-Return- oder Buy&Hold-Benchmark; p < 0.05 erwartet. Nicht-blockierend, aber reporten. [^15^][^16^]

### Phase 4 — Monte-Carlo & Prop-Firm-Risiko
18. **Trade-Shuffling:** 10.000 Permutationen der OOS-Trade-Sequenz (R-Multiples) → Verteilungen für MaxDD, längste Streak, End-Equity. **Gate:** 95.-Perzentil-MaxDD ≤ 8 % (Puffer vor FTMO-10 %). [^24^][^26^]
19. **Stationary Block Bootstrap:** 10.000 Pfade, mittlere Blocklänge ≈ T^(1/3) der Trade-Serie (bei Tagesblöcken 3–12 Tage Grid, Sensitivität mit ½×/2× Blocklänge berichten — Schlussfolgerung darf nicht von der Blocklänge abhängen). Fängt Verlierer-Clustering ab, das IID-Shuffling unterschätzt. [^25^]
20. **Prop-Firm-Simulation (Challenge-Level):** 10.000 Challenge-Pfade mit exaktem Regelwerk: Daily Loss 5 % der **Vortagsbilanz**, inkl. **Floating PnL + Swap-Debits um 00:00 Server**; Max Loss 10 % statisch (bzw. 3 %/EOD-Trailing bei 1-Step); Profit-Target 10 %/5 %. Aus Tages-PnL-Pfaden (nicht nur Closed-Trade-R) simulieren. **Gates:** P(Breach Daily Loss) ≤ 5 % pro Challenge; P(Breach Max Loss) ≤ 2 %; Pass-Rate ≥ 60 %. Referenz-Engine zum Abgleich: LuxAlgo/prop-firm-sim (aber deren Annahmen — kein Intra-Trade-Excursion, kein Overnight — müssen wir aufheben). [^26^][^27^][^28^][^29^]
21. **Sizing-Ableitung aus der Sim:** Risiko/Trade so wählen, dass `Risiko × max_simulierte_Intraday_Streak ≤ 0.8 × Daily-Loss-Limit` (bei 0.5 % Risiko und Streak 6 → 3 % Tagesexposition = 60 % des Limits ✓). Daily-Trade-Cap als harte Bot-Regel. [^29^][^32^]
22. **Random-Entry-Falsifikation:** gleiche Risk-Engine, zufällige Entries (Session-Filter bleibt), 1.000 Runs → Bot-Expectancy muss > 95.-Perzentil der Random-Entry-Verteilung liegen. [^22^]

### Phase 5 — Demo-Live-Gate (Übergang)
23. Mindestens 50–100 Demo-Trades oder 3 Monate; Live-vs-Backtest-Abgleich **pro Trade** (Fill-Preis, Spread, Slippage, Swap) — StrategyQuant-Regel: "A backtest that does not reproduce the target platform's trades within a reasonable tolerance should not be treated as reliable evidence." Slippage-Ist fließt zurück ins Kostenmodell (Rekalibrierung). [^43^][^49^]

### Abbruchkriterien — Zusammenfassung (Hard Gates)
| Gate | Schwelle | Quelle |
|---|---|---|
| Sample | n ≥ 300 Trades (Scalping 1.000+); ≥ 5 Jahre; ≥ 2 Regime | [^30^][^50^] |
| Red Flags | PF ≤ 3.0, WR ≤ 70 %, Sharpe ≤ 3 (sonst Overfitting-Verdacht) | [^52^] |
| Slippage-Stress | PF(2×Kosten) ≥ 1.2, PF(3×) ≥ 1.0 | [^36^], wide01 |
| WFE | Median ≥ 0.5, ≥ 3/5 Folds ≥ 0.5, ≥ 60 % Folds profitabel; > 1.0 = Lookahead-Audit | [^6^][^7^][^8^] |
| DSR | ≥ 0.95 mit ehrlichem N_eff | [^11^][^12^] |
| PBO | < 0.10 (0.10–0.30 = halbe Größe; > 0.30 = verwerfen) | [^21^] |
| MC-Drawdown | 95.-Perzentil MaxDD ≤ 8 % | [^24^] |
| Prop-Sim | P(Daily-Breach) ≤ 5 %, P(MaxLoss-Breach) ≤ 2 %, Pass ≥ 60 % | [^26^][^29^] |
| Ziel-Metrik | PF ≥ 1.5 **auf gestitchter OOS-Kurve** (nicht IS, nicht Holdout-Peek) | Projektziel |
| Holdout | 1× testen; danach keine Parameteränderung | [^10^] |

### Paket-Stack (Empfehlung)
- **Eigenbau (klein, nötig):** WFA-Loop (~150 Zeilen), Slippage-Stress-Matrix, Prop-Firm-MC-Sim mit Floating-PnL (~200 Zeilen), Trial-Logger.
- **Fertig:** `backtest-guard` (DSR/PSR/PBO/PurgedKFold — API pinnen), `arch` (SPA + Stationary Bootstrap), `skfolio` (`CombinatorialPurgedCV`, `WalkForward`), `numpy/scipy` (DSR 20 Zeilen nach Claim 2.3).
- **Vermeiden:** `pip install pbo` (existiert nicht), `mlfinlab` (kein PyPI/kommerziell), `mlfinpy`/`timeseriescv` (dormant/tot). [^14^][^17^]

---

### Quellen

[^1^]: newyorkcityservers.com — "Walk-Forward Optimization & Monte Carlo Testing for EAs", 2026-07-07. https://newyorkcityservers.com/blog/walk-forward-monte-carlo-testing-eas
[^2^]: fortraders.com — "How To Avoid Bias in Backtesting", 2026-08-31. https://fortraders.com/blog/how-to-avoid-bias-in-backtesting
[^3^]: fortraders.com — "How to Use AI to Optimize Your Trading Strategy", 2026-07-21. https://fortraders.com/blog/use-ai-optimize-trading-strategy
[^4^]: freyafinance.com — "Walk-forward analysis for crypto strategies", 2026-05-28. https://www.freyafinance.com/academy/backtesting/walk-forward-analysis-strategy-validation
[^5^]: echozero.app — "Walk-Forward Analysis (Glossary)", o.D. https://blog.echozero.app/glossary/walk-forward-analysis
[^6^]: tradelosstracker.com — Pardo, "The Evaluation and Optimization of Trading Strategies" (Extended Summary), o.D. https://tradelosstracker.com/library/book/44/extended
[^7^]: luxalgo.com — "Stress-Test Your Algorithmic Trading Strategy", 2026-07-08. https://www.luxalgo.com/blog/stress-test-your-algorithmic-trading-strategy-guide-to-avoiding-overfitting/
[^8^]: ProRealTime — ProBacktest Programming Guide (WFE 70/30, 3/5-Regel), o.D. https://www.prorealcode.com/wp-content/uploads/2018/09/probacktest.pdf
[^9^]: quanthedgeai.com — "The Deflated Sharpe Ratio, Honestly Implemented", 2026-06-29. https://www.quanthedgeai.com/blog/the-deflated-sharpe-ratio-honestly-implemented/
[^10^]: lobehub.com — Walk-Forward Optimization Skill, 2026-05-15. https://lobehub.com/de/skills/brainbytes-dev-everything-claude-trading-walk-forward-optimization
[^11^]: rollbrains.com — "The Deflated Sharpe Ratio: Why a 2.5 Sharpe Can Still Be Statistical Noise", 2026-06-09. https://rollbrains.com/quant/deflated-sharpe-ratio/
[^12^]: wikibin.org — "Deflated Sharpe ratio" (Formel), 2026-06-26. https://wikibin.org/articles/deflated-sharpe-ratio.html
[^13^]: GitHub — AgentJDrew/backtest-guard (DSR/PSR/PBO/PurgedKFold/Lookahead-Detektoren, MIT), 2026-07-06. https://github.com/AgentJDrew/backtest-guard
[^14^]: guetaquant.com — "Validar Backtest sin Auto-Engañarse" (pypbo/pbo-PyPI-Falle, CRAN pbo), 2026-09-01. https://guetaquant.com/blog/validar-backtest-sin-autoenganarse/
[^15^]: arch-Dokumentation — arch.bootstrap.SPA / RealityCheck / StepM / MCS, o.D. https://arch.readthedocs.io/en/stable/multiple-comparison/multiple-comparison-reference.html
[^16^]: arch-Dokumentation — arch.bootstrap.SPA API-Referenz, o.D. https://bashtage.github.io/arch/multiple-comparison/generated/arch.bootstrap.SPA.html
[^17^]: christopherspenn.com — Investment-Report (Paket-Audit: skfolio CombinatorialPurgedCV/WalkForward; mlfinlab/mlfinpy/timeseriescv-Status), 2026-08-02. https://www.christopherspenn.com/interactives/investment-report-example.html
[^18^]: quantifiedtrader.com — "Statistical Analysis of Trading Strategies" (White RC vs. Hansen SPA), o.D. https://quantifiedtrader.com/projects/statistical-analysis-trading-strategies/
[^19^]: lobehub.com — Overfitting-Prevention-Skill (RC/SPA-Verfahrensschritte), 2026-03-15. https://lobehub.com/de/skills/brainbytes-dev-everything-claude-trading-overfitting-prevention
[^20^]: GitHub — quantskills/skill-backtest-overfit (DSR+PBO+Haircut+MinTRL Demo), 2026-07-03. https://github.com/quantskills/skill-backtest-overfit
[^21^]: aligrithm.com — "CSCV: A Direct Probability of Backtest Overfit" (PBO-Schwellen, Anti-Patterns), 2026-07-27. https://aligrithm.com/cscv-a-direct-probability-of-backtest-overfit/
[^21b^]: GitHub — suenot/pbo-search (kontrollierte CSCV-Studie, Null=0.5), 2026-07-02. https://github.com/suenot/pbo-search
[^22^]: GitHub — AaroNLaU0307/quant-backtest-framework PROJECT_BRIEF (Random-Entry-Falsifikation, BH-FDR, MC ≥10.000), 2026-06-01. https://github.com/AaroNLaU0307/quant-backtest-framework/blob/main/docs/PROJECT_BRIEF.md
[^23^]: backtrex.com — "Overfitting in backtesting: how to detect and prevent it" (30-Trades-pro-Parameter, OOS nur 1× testen), 2026-05-31. https://backtrex.com/en/blog/overfitting-backtesting-detect-prevent
[^24^]: fortraders.com — "Backtesting Strategies That Actually Work" (5.000 MC-Runs, 95.-Perzentil-Sizing), 2026-07-23. https://fortraders.com/blog/backtesting-strategies-that-actually-work
[^25^]: susanpotter.net — "Bootstrap Methods for Strategy Robustness" (Blocklänge T^(1/3), Politis-White, Sensitivität), 2026-05-23. https://www.susanpotter.net/quant/bootstrap-methods-strategy-robustness/
[^25b^]: GitHub — euro-macromechanica-backtest/results (stationary_bootstrap, 10.000 Pfade, Monatsblöcke 3–12), o.D. https://github.com/euro-macromechanica-backtest/results
[^26^]: GitHub — LuxAlgo/prop-firm-sim (Open-Source Prop-Firm-MC-Engine, Regelwerke, Annahmen-Liste), 2026-08-24. https://github.com/LuxAlgo/prop-firm-sim
[^27^]: FTMO — "How to Use Monte Carlo Simulations to Pass the FTMO Challenge", 2026-07-31. https://ftmo.com/en/blog/how-to-use-monte-carlo-simulations-to-pass-the-ftmo-challenge/
[^28^]: backtrex.com — "Backtesting With Prop Firm Rules: FTMO, Drawdown & Daily Loss", 2026-05-22. https://backtrex.com/en/blog/backtesting-prop-firm-rules
[^29^]: grandalgo.com — "Prop Firm Risk of Ruin: How to Size Positions for Challenge Survival" (37%-Daily-Loss-Rechnung, 80 %-Puffer-Regel), 2026-03-24. https://grandalgo.com/blog/prop-firm-risk-of-ruin-guide
[^30^]: fxnx.com — "Backtest Sample Size: How Many Trades Do You Need?" (Scalping 1.000+, Daytrading 300–500), 2026-09-02. https://fxnx.com/en/blog/backtest-sample-size-how-many-trades-make-results-real
[^31^]: fxnx.com — "Consecutive Loss Math: Streak Tables for Every Win Rate" (6er-Streak bei 60 % WR = 63.8 % in 200 Trades), 2026-08-27. https://fxnx.com/en/blog/consecutive-loss-math-streak-tables-every-win-rate
[^32^]: itafx.com — "Risk of Ruin in Trading" (2 %-Risk: 1 % Ruin, aber 67 % Prop-Breach-Wahrscheinlichkeit), 2026-05-19. https://www.itafx.com/blog/risk-of-ruin-trading/
[^33^]: tradingfunder.com — FTMO Rules (Daily Loss = Vortagsbilanz, inkl. Floating; 1-Step = 3 %/EOD-Trailing), 2026-05-24. https://tradingfunder.com/ftmo-rules/
[^34^]: lobehub.com — Monte-Carlo-Skill (DD-Bootstrap: Backtest 12 % → p90 22 %, p99 35 %), 2026-03-15. https://lobehub.com/skills/brainbytes-dev-everything-claude-trading-monte-carlo-simulation
[^35^]: fortraders.com — "How to Backtest a Strategy in MT5 (Advanced Guide)" (Spread-Modi, News-Slippage, XAUUSD-Kontraktgrößen), 2026-08-23. https://fortraders.com/blog/backtest-strategy-in-mt5-advanced-guide
[^36^]: fxnx.com — "Backtest Spread and Slippage: Realistic Execution Testing" (0.9 Pip Friktion = −75 % Edge; 1.5×-Spread-Regel; $3.50–$7 RT), 2026-08-23. https://fxnx.com/en/blog/backtest-spread-slippage-costs-your-tester-skips
[^37^]: fxnx.com — "Tick Data vs 1-Minute OHLC: What Your MT5 Backtest Really Models" (Rollover-Spread 0.2→4.5 Pips), 2026-09-01. https://fxnx.com/en/blog/tick-data-vs-1-minute-ohlc-what-your-mt5-backtest-really
[^38^]: fxnx.com — "Swap Rate Change Log" (Static Swap Distortion; Tom-Next + Markup; MC ±20–50 % Swap-Stress), 2026-08-19. https://fxnx.com/en/blog/swap-rate-change-log-dated-monthly-snapshots-instrument
[^39^]: fxnx.com — "XAUUSD Swap in the MT5 Specification" (Punkte-Formel, Triple-Swap), 2026-08-31. https://fxnx.com/en/blog/swap-xauusd-specifications-mt5-lire-votre-cout-nocturne
[^40^]: ic.com — Forex Swap Rates (Triple-Swap: Mi für FX/Metals, Fr für Energies/Indices/Crypto), 2026-08-27. https://www.ic.com/en/trading-pricing/swap-rates
[^41^]: fxnx.com — "Swap Long and Swap Short: Reading the MT5 Specification Tab" (Swap-Breach-Beispiel Daily Loss), 2026-08-25. https://fxnx.com/en/blog/swap-long-swap-short-reading-mt5-specification-tab
[^42^]: backtestmarket.com — "Forex Daylight Saving Time: Fixing DST Errors in Minute Data" (UTC-at-Ingestion, Gap-Weeks), 2026-08-24. https://www.backtestmarket.com/en/blog/forex-daylight-saving-time
[^42b^]: kcmtrade.com — MT4/MT5 Server Time Zone Adjustment Notice (GMT+2→GMT+3, US/EU-DST-Lücke), 2026-02-24. https://www.kcmtrade.com/news/mt4-mt5-server-time-zone-adjustment-notice-5
[^42c^]: VT Markets — GMT Offset / Server Time FAQ (Server-Midnight = 17:00 NY), o.D. https://get.vtmarkets.help/hc/en-us/articles/37317868198297
[^43^]: quantmonitor.net — "Best Algorithmic Trading Software 2026" (StrategyQuant Broker-Profile, Trade-by-Trade-Abgleich-Regel), 2026-07-28. https://quantmonitor.net/best-algorithmic-trading-software/
[^44^]: fxbook.net — MetaTrader5-Python copy_rates_range Referenz (pytz Etc/UTC-Konvention), 2026-07-24. https://www.fxbook.net/docs/mql5-reference/python-integration/copy_rates_range/
[^45^]: nexural.io — backtesting.pdf (Shift-Test, Signal T → Fill T+1), o.D. https://www.nexural.io/pdfs/backtesting.pdf
[^46^]: rollbrains.com — "The Anatomy of Look-Ahead Bias", 2026-06-01. https://rollbrains.com/tradingview/backtest/lookahead-bias-penetration/
[^47^]: fxnx.com — "Repainting Indicators: How to Test & Identify Repainting" (4-Stufen-Audit, Code-Mechanismen), 2026-08-29. https://fxnx.com/en/blog/repainting-indicators-how-test-if-your-indicator-repaints
[^48^]: propquantlab.com — "Why Intraday Strategies Are Harder to Backtest" (Intrabar-Ambiguität), 2026-07-21. https://propquantlab.com/article-intraday-backtesting.html
[^49^]: ispybuy.com — "MT5 Strategy Tester: Every Tick vs Real Ticks vs OHLC" (Modi-Tabelle, Modeling-Quality-90 %-Regel), 2026-07-28. https://ispybuy.com/blog/mt5-strategy-tester-every-tick-vs-real-ticks-vs-ohlc/
[^50^]: backtestbase.com — "How Many Trades for Backtest" (CLT-Floor 30, 200–500 LdP, Regime-Abdeckung), 2026-01-04. https://www.backtestbase.com/education/how-many-trades-for-backtest
[^51^]: strategyquant.com Forum — "MT5 backtest report: How to add broker commissions" (keine Kommission im Tester), 2019-08-11. https://strategyquant.com/forum/topic/mt5-backtest-report-how-to-add-broker-commissions/
[^52^]: GitHub — rudraymehra/AutoTheta, ML_TRADING_STRATEGIES_RESEARCH.md (Red-Flag-Benchmark-Tabelle), 2026-03-30. https://github.com/rudraymehra/AutoTheta/blob/main/ML_TRADING_STRATEGIES_RESEARCH.md
[^53^]: fxnx.com — "MT4 vs MT5 Backtest Divergence: One EA, Two Engines" (Hedging/Netting, Kommissions-Harmonisierung), 2026-08-25. https://fxnx.com/en/blog/mt4-vs-mt5-backtest-divergence-one-ea-two-engines
[^54^]: quant67.com — "Walk-forward 与 Purged CV" (Embargo 0.01, Purge-Regel-Details), 2026-05-01. https://quant67.com/post/quant/21-walkforward-cv/21-walkforward-cv.html
[^55^]: mlfinlab-Dokumentation — "Purged and Embargo" (AFML Kap. 7), o.D. https://www.mlfinlab.com/en/latest/cross_validation/purged_embargo.html

---
*Methodik-Hinweis: 19 Suchqueries (EN/DE/ES). Quellen-Autorität gemischt: akademische Primärmethoden (Bailey/López de Prado 2014; Bailey et al. 2015/2017; White 2000; Hansen 2005; Politis/Romano 1994; Pardo 2008) via Sekundärquellen mit deckungsgleichen Formeln; Paket-Fakten aus offiziellen Dokumentationen/Repos; Practitioner-Schwellen (WFE, Fenstergrößen) aus ≥2 unabhängigen Quellen jeweils. Härteste Datenpunkte: arch-Doku, backtest-guard-Repo, pbo-search-Replikation, LuxAlgo prop-firm-sim (Code + Annahmen), ProRealTime/Pardo-WFE-Kanon.*
