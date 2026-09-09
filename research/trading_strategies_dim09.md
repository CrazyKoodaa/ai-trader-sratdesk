# Dimension 09: XGBoost/ML Meta-Labeling über klassischen Entry-Signalen (López de Prado)

Recherche-Facet: Meta-Labeling-Methodik (Primary Model = Regel-Entries, Secondary Model = Trade-Filter/Sizing), Triple-Barrier-Labeling, zwingende Validierung (Purged K-Fold, CPCV, DSR, PBO), öffentliche Backtest-Evidenz, Datenanforderung, Parameter-Räume.
Methodik: 19 gezielte Websuchen (EN/DE), 2 Deep-Dive-Seiten (daru.finance-Replikation, Hudson & Thames), Tool-Inspektion (backtest-guard, backtest-audit, oos-lab, mlfinpy-Docs). Kontext aus wide05 (XGBoost XAUUSD AUC 0,538; daru.finance 92.500 Strategien DSR 0,029; CPCV/Purged-KFold-Pflicht) und wide02 (n≥300-Regel, PF>1,5-Ziel).

---

## Key Findings

### 1. Meta-Labeling-Methodik nach López de Prado (AFML 2018, Kap. 3)

**Kernarchitektur: Trennung von "Side" (Richtung) und "Size" (Ob/Wieviel).**

- **Claim:** Meta-Labeling entkoppelt die Richtungsentscheidung (primäres Modell, z. B. MA-Crossover, SMC-Setup, Momentum-Regel) von der Erfolgswahrscheinlichkeit (sekundäres ML-Modell). Das Sekundärmodell beantwortet nicht "steigt oder fällt der Kurs?", sondern "war das Signal des Primärmodells unter den aktuellen Marktbedingungen profitabel?" — binäres Label: 1 = Primärsignal korrekt/profitabel, 0 = falsch/verlustig. Endgültige Entscheidung: Trade nur, wenn Primary Side ≠ 0 UND Secondary P(1) > Schwellwert.
  **Source:** Papers With Backtest — "Meta-Labeling: How to Size Bets with ML"
  **URL:** https://paperswithbacktest.com/course/meta-labeling
  **Date:** o.D. (abgerufen 2026)
  **Excerpt:** "Meta-labeling ... decouples the problem of predicting trade direction (the side) from predicting trade success (the size). ... The meta-label for each event is binary: 1 if the primary model's signal was correct (profitable trade), 0 if wrong (losing trade). ... A probability threshold controls how selective the strategy is. Higher thresholds improve precision (fewer but better trades) at the cost of recall."
  **Confidence:** Hoch (Methodik-Kanon, deckt sich mit AFML).

- **Claim:** Das Primärmodell soll bewusst **hohe Recall** (jedes potenzielle Signal mitnehmen) bei mittlerer Präzision liefern; das Meta-Modell korrigiert dann die niedrige Präzision durch Filtern der False Positives → höherer F1-Score. Das Sekundärmodell darf Features nutzen, die das Primärmodell nicht sieht (Kontext-Features).
  **Source:** Mehta/Mittal (Theseus Thesis), zitiert de Prado 2018
  **URL:** https://www.theseus.fi/bitstream/handle/10024/746368/Mehta_Mittal.pdf
  **Date:** o.D.
  **Excerpt:** "First, we build a model that achieves high recall, even if the precision is not particularly high. Second, we correct for the low precision by applying meta-labeling to the positives predicted by the primary model. ... It is not its purpose to come up with a betting opportunity. Its purpose is to determine whether we should act or pass on the opportunity."
  **Confidence:** Hoch.

- **Claim (Konzept-Einordnung):** Ernest Chan nennt Meta-Labeling "Corrective AI": "Metalabeling is essentially using ML to predict unfavorable regimes for a trading strategy. ... Deciding the likelihood a trade will do well in current markets is easier for a machine than predicting the direction of the market itself." → Das Meta-Modell ist faktisch ein **Regime-/Kontext-Prädiktor für Strategie-Erfolg**, kein Richtungsprädiktor.
  **Source:** Comintel Meetup — Don Brady, "Meta-Labeling" (Vortragsfolien)
  **URL:** https://www.comintel.com/meetup/DonBrady/Meta-Labeling.pdf
  **Date:** o.D.
  **Excerpt:** "Side: This decision is made by the original trading system or discretionary trader. Size: This decision is made by the added meta-labeling layer — can be set to zero which is a veto of the original trade. ... You need at least a few hundred trades history."
  **Confidence:** Hoch (Praktiker-Sekundärquelle, zitiert Chan/de Prado).

- **Claim (neuere akademische Einordnung):** "Corrective AI" (Pik et al. 2025) formalisiert Meta-Labeling als Zuverlässigkeits-Schätzung eines Primärmodells M1 durch ein zweites Modell M2 — relevant in High-Stakes-Domänen mit niedriger False-Positive-Toleranz.
  **Source:** arXiv 2510.26353 — "Towards Explainable and Reliable AI in Finance"
  **URL:** https://arxiv.org/html/2510.26353v1
  **Date:** 2025
  **Excerpt:** "Here, a primary model M1 predicts the direction of the price action, whereas a secondary model M2 estimates the reliability of the primary model's prediction. ... Lopez de Prado speaks about the side of a bet versus the size of a bet."
  **Confidence:** Mittel-Hoch (Preprint, konzeptionell).

### 2. Triple-Barrier-Labeling (Label-Definition für das Meta-Modell)

**Claim:** Jedes Primary-Signal-Event erhält drei Barrieren: obere (Profit-Take), untere (Stop-Loss), vertikale (max. Haltezeit). Label = welche Barriere zuerst berührt wird. Mit `side` des Primärmodells ergibt sich das binäre Meta-Label direkt aus dem PnL-Vorzeichen: bin ∈ {0,1} statt {-1,1}.

- **Source:** mlfinpy-Dokumentation — `get_events` / `get_bins`
  **URL:** https://mlfinpy.readthedocs.io/en/latest/Labelling.html
  **Date:** o.D. (Doku)
  **Excerpt:** "Case 1: ('side' not in events): bin in (-1,1) <- label by price action. Case 2: ('side' in events): bin in (0,1) <- label by pnl (meta-labeling). ... Advances in Financial Machine Learning, Snippet 3.7, page 51."
  **Confidence:** Hoch (Referenzimplementierung der AFML-Snippets).

- **Claim (Parameter-Praxis):** Barrieren als **Vielfache der täglichen Volatilität** (EWMA, Lookback 50), nicht als fixe Prozentwerte; Beispiel-Code: `pt_sl=[2.0, 1.5]` × daily_vol, vertikale Barriere 10 Tage, `min_ret=0.0005`. Wichtig: `t1` (Barrier-Touch-Zeitpunkt) muss persistiert werden — Purging/CV downstream hängt davon ab.
  **Source:** PickMyTrade — "Advanced AI Trading Guide" (auch DE-Version verfügbar)
  **URL:** https://pickmytrade.io/ai-ml/advanced-guide
  **Date:** 03.07.2026
  **Excerpt:** "daily_vol = get_daily_vol(close=prices, lookback=50) ... pt_sl=[2.0, 1.5]  # profit-take / stop-loss as multiples of daily_vol ... add_vertical_barrier(t_events=signal_dates, close=prices, num_days=10) ... labels['t1'] -> the barrier-touch timestamp (needed for purging downstream)"
  **Confidence:** Hoch.

- **Claim (Warnung):** Der größte Anwenderfehler ist, `min_ret`/Targets so zu drehen, dass mehr Beobachtungen entstehen ("ML models require a fair amount of data. This is the wrong approach!") — das verbiegt das Label-Ökonomik-Verhältnis zum tatsächlichen Trade-Management. Stattdessen: Seven-Point-Protocol / ehrliche Feature-Definition.
  **Source:** mlfinlab-Dokumentation — Triple-Barrier and Meta-Labelling
  **URL:** https://www.mlfinlab.com/en/latest/labeling/tb_meta_labeling.html
  **Date:** o.D. (Doku)
  **Excerpt:** "The biggest mistake we see users making here is that they change the daily targets and min_ret values to get more observations, since ML models require a fair amount of data. This is the wrong approach!"
  **Confidence:** Hoch.

- **Claim (Epistemischer Vorbehalt):** Triple-Barrier/Meta-Labeling sind in Produktion stabil und peer-reviewed verwendet (Karakunnel et al. 2025, Financial Innovation, doi:10.1186/s40854-025-00866-w; Karasan et al. 2024, Mathematics 12(5):780), aber die **Überlegenheit gegenüber Fixed-Horizon-Labeling wurde nie in einer kontrollierten peer-reviewten Studie unabhängig repliziert**. Verteidigbar aus Ergonomie-Gründen (Label kodiert Risikomanagement), nicht als bewiesener Performance-Gewinn.
  **Source:** christopherspenn.com — "Doubling USD 100 in 90 Days" (Multi-LLM-Research-Audit)
  **URL:** https://www.christopherspenn.com/interactives/investment-report-example.html
  **Date:** 02.08.2026
  **Excerpt:** "the peer-reviewed evidence establishes that these techniques are stable in production; their claimed superiority over fixed-horizon labeling ... has not been independently replicated in a peer-reviewed controlled comparison. The technique is defensible on ergonomic grounds — it encodes risk management into the label — but it cannot be claimed to improve performance."
  **Confidence:** Mittel (Meta-Analyse mit LLM-Beteiligung, aber sauber referenziert).

### 3. Validierung: Purged K-Fold, Embargo, CPCV, DSR, PBO

**3a. Purged K-Fold + Embargo (AFML Kap. 7)**

- **Claim:** Standard-K-Fold ist für Finanzdaten invalid (überlappende Labels teilen Zukunftsinformationen). Fix: (1) Purging — Trainings-Observationen entfernen, deren Label-Fenster [t0, t1] den Test-Fold überlappt; (2) Embargo — zeitlicher Puffer nach dem Test-Fold. Embargo-Default: 1 % der Sample-Länge (AFML §7.4.2, mlfinlab-Default 0,01); Kriterium: Embargo so lange erhöhen, bis die Varianz der K-Fold-OOS-Scores nicht mehr signifikant sinkt. t1/t2 aus der Labeling-Phase müssen persistiert werden, alle CV/Backtests hängen daran.
  **Source:** quant67.com — "Walk-forward 与 Purged CV：时间序列正确切分"
  **URL:** https://quant67.com/post/quant/21-walkforward-cv/21-walkforward-cv.html
  **Date:** 01.05.2026
  **Excerpt:** "de Prado 在《Advances in Financial Machine Learning》第 7.4.2 节给出经验值 0.01（即 1% 总样本数）；mlfinlab 的默认值也是 0.01。 ... embargo 加大后，K 折 OOS 分数的方差是否明显下降？方差不再显著下降的那个 embargo 长度是合适的。"
  **Confidence:** Hoch.

- **Claim (gemessene Leckage-Größe):** Das K-Fold-Leck ist real, aber klein bei vernünftigem Modell: <2 pp AUC-Inflation selbst bei großem Overlap; skaliert mit **H / Fold-Größe** (Label-Horizon geteilt durch Fold-Länge), nicht mit H allein. Kurze Historien (Krypto/Forex, Fold ≈ 1.4k Bars): bis +1,69 pp AUC; lange Equity-Historien (Fold ≈ 7k Bars): praktisch null. Leck nur in **AUC** sichtbar, nicht in Accuracy (Fold-Rauschen ±0,5–1 pp überdeckt es). Embargo nach korrektem Purge nur zweite Ordnung — ~1 % halten.
  **Source:** daru.finance — "Labeling & Cross-Validation" (Replikation auf 42 Instrumenten, 3 Märkte)
  **URL:** https://daru.finance/research-review/lopez-de-prado/labeling-and-cross-validation
  **Date:** o.D. (abgerufen 2026)
  **Excerpt:** "The leak is real and directionally correct but small with a sensible model, sub-2pp even at large overlap, visible cleanly in AUC (not accuracy). ... inflation tracks H / fold-size ... Purge always, it is free and correct, but expect the size of the correction to scale with H/fold-size. ... Embargo, once labels are correctly purged, is a small second-order safeguard, keep it ~1%."
  **Confidence:** Hoch (empirische Multi-Market-Replikation, vercostet).

**3b. CPCV (AFML Kap. 12)**

- **Claim:** CPCV zerlegt die Serie in N Gruppen, testet auf allen C(N,k)-Kombinationen von k Testgruppen (mit Purge+Embargo) und erzeugt φ(N,k) = (k/N)·C(N, N−k) vollständige Backtest-Pfade. Kanonisches Beispiel N=6, k=2: 15 Splits, 5 Pfade. k=2 ist "Sweet Spot": φ(N,2) = N−1 Pfade bei großem Trainingsset. Ergebnis ist eine **Verteilung** von OOS-Sharpes statt eines Punktes.
  **Source:** risklab.ai — "Backtesting through Cross-Validation (CPCV)"; StackExchange-Antwort zur Pfad-Formel; Aalto-Thesis (CPCV-Praxisbeispiel: 6 Gruppen, 2 Test, Purge 90 Tage vor / 7 Tage nach, Embargo 1 %)
  **URL:** https://www.risklab.ai/research/backtesting/backtesting_cross_validation ; https://stats.stackexchange.com/questions/443159/ ; https://aaltodoc.aalto.fi/bitstreams/1ad6e657-e74a-495c-8222-aae0d6949d80/download
  **Date:** 22.06.2026 / 03.01.2020 / o.D.
  **Excerpt:** "φ[N,k] = (k/N)·C(N, N−k) ... Using k=2 is a powerful 'sweet spot.' It generates φ[N,2] = N−1 paths while keeping the training set size large." / "splits into 6 groups of which 2 are used in the validation sets, producing 15 cross-validation splits and 5 backtest paths ... preceding 90 days and succeeding 7 days purged ... 1% embargoed"
  **Confidence:** Hoch.

- **Claim (wichtigster CPCV-Befund):** Die CPCV-OOS-Pfad-Verteilung spannt ~15 pp Accuracy (BTCUSDT-Beispiel: 0,381→0,532) — das ist **~50× der Leckage-Bias**. Ein einzelner Backtest-Split ist "eine nahezu bedeutungslose Ziehung". Konsequenz: Niemals eine Strategie anhand eines einzelnen Splits beurteilen; Hyperparameter-Selektion über den **Mittelwert/Quantile der CPCV-Pfadverteilung**.
  **Source:** daru.finance — "Labeling & Cross-Validation"
  **URL:** https://daru.finance/research-review/lopez-de-prado/labeling-and-cross-validation
  **Date:** o.D.
  **Excerpt:** "CPCV gives 15 out-of-sample paths for BTCUSDT spanning 15.1 pp of accuracy (0.381 → 0.532). The single-split 'backtest' (0.478) is one arbitrary point above the CPCV mean (0.467). Path dispersion dwarfs the ~0.3 pp leakage bias by roughly 50×, one number from one split is nearly meaningless."
  **Confidence:** Hoch.

**3c. Deflated Sharpe Ratio (DSR) & PBO**

- **Claim (DSR):** DSR = PSR gegen das erwartete Maximum von N Trials unter der Nullhypothese (False Strategy Theorem). Schwellwert: DSR ≥ 0,95. Beispiel aus Tool-Doku: Bester von 200 reinen Rausch-Strategien mit naivem Sharpe 0,13 → DSR 23,3 % (FAIL). Aus wide05/daru.finance: bester von 50.000 Crypto-Strategien (Sharpe 2,00) liegt unter dem Rausch-Null-Erwartungswert 2,72, DSR 0,029; 50.000 nominelle Trials = nur 434 effektive Wetten.
  **Source:** github.com/AgentJDrew/backtest-guard (Worked Example); daru.finance — "Backtest Overfitting & the Deflated Sharpe Ratio"
  **URL:** https://github.com/AgentJDrew/backtest-guard ; https://daru.finance/research-review/lopez-de-prado/backtest-overfitting
  **Date:** 06.07.2026 / o.D.
  **Excerpt:** "Deflated Sharpe Ratio: 23.3% probability of a real edge (not significant) ... PBO = 80.8% (strong overfitting signal)" / "The corpus best annualises to a Sharpe of 2.00. But ... the expected maximum Sharpe of 50,000 skill-less trials is 2.72 ... The Deflated Sharpe Ratio of that corpus best is 0.029, against a 0.95 bar."
  **Confidence:** Hoch.

- **Claim (PBO/CSCV):** PBO = Anteil der CSCV-Splits (S=16 Blöcke, C(16,8)=12.870 Splits), in denen der IS-Sieger OOS ≤ Median rangiert. Interpretation: PBO ≈ 0,5 = Auswahl trägt keine Information; **< 0,2 = Rangfolge echt prädiktiv; > 0,5 = aktiv irreführend**. Kostet keine zusätzlichen Backtests — reine Nachverarbeitung der gespeicherten Return-Matrix (T×N, eine Spalte pro Parameter-Trial).
  **Source:** saral.money — "Backtest Overfitting: The Deflated Sharpe Test"
  **URL:** https://saral.money/blog/backtest-overfitting-deflated-sharpe/
  **Date:** 01.08.2026
  **Excerpt:** "PBO is the fraction of splits where the in-sample winner landed at or below the out-of-sample median. ... Below 0.2 the ranking is genuinely predictive. Above 0.5 the ranking is actively misleading ... Every number comes from post-processing return series you already have."
  **Confidence:** Hoch.

**3d. Tool-Implementierungen (mlfinlab-Alternativen, alle frei nutzbar)**

- **mlfinpy** (MIT): moderne Reimplementierung der AFML-Snippets — Triple-Barrier (`get_events`, `add_vertical_barrier`, `get_bins`), Meta-Labels, Fractional Differentiation, Sample-Weights/Uniqueness (`get_weights_by_return`, Sequential Bootstrap), PurgedKFold. `pip install mlfinpy`.
  **Source:** mlfinpy.readthedocs.io; PickMyTrade Advanced Guide
  **URL:** https://mlfinpy.readthedocs.io/en/latest/Labelling.html ; https://pickmytrade.io/ai-ml/advanced-guide
  **Date:** o.D. / 03.07.2026
  **Excerpt:** "Two free, permissively-licensed packages now cover triple-barrier labeling, meta-labeling, fractional differentiation, sample-uniqueness weighting, CPCV, and HRP: mlfinpy (MIT) ... skfolio (BSD-3-Clause)."
  **Confidence:** Hoch.

- **skfolio** (BSD-3): `CombinatorialPurgedCV` out-of-the-box, sklearn-kompatibel (sklearn-`split()`-Konvention) — direkte Verwendung als `cv=`-Argument für XGBoost-Hyperparameter-Search.
  **Source:** PickMyTrade Advanced Guide (s.o.)
  **Confidence:** Hoch.

- **backtest-guard** (MIT, numpy+scipy only): `deflated_sharpe_ratio(returns, n_trials)`, `pbo(returns_matrix, n_splits=16)`, `PurgedKFold(n_splits, label_end_times, embargo_fraction)` (sklearn-kompatibel), `probabilistic_sharpe_ratio`, `minimum_track_record_length`, Lookahead-/Leakage-Checks, `audit()`-Komplettreport mit PASS/FAIL.
  **Source:** github.com/AgentJDrew/backtest-guard
  **URL:** https://github.com/AgentJDrew/backtest-guard
  **Date:** 06.07.2026
  **Excerpt:** "deflated_sharpe_ratio(returns, n_trials) — PSR against the expected max Sharpe of n_trials independent noise strategies ... pbo(returns_matrix, n_splits=16) ... PurgedKFold(n_splits, label_end_times, embargo_fraction) — scikit-learn-compatible splitter with purging + embargo"
  **Confidence:** Hoch (Code inspiziert via README, 200-Trial-Beispiel reproduzierbar).

- **oos-lab** (MIT, `pip install oos-lab`): PSR, DSR, `expected_max_sharpe`, WalkForward-Splitter, `CombinatorialPurgedKFold`, `probability_of_backtest_overfit` (CSCV), Harvey-Liu-Haircut (Holm-Bonferroni, BHY).
  **Source:** github.com/OutOfSampleLab/oos-lab
  **URL:** https://github.com/OutOfSampleLab/oos-lab
  **Date:** 24.06.2026
  **Excerpt:** "CombinatorialPurgedKFold — combinatorial purged cross-validation with embargo (López de Prado 2018) ... probability_of_backtest_overfit ... Returns the PBO scalar plus the performance-degradation regression."
  **Confidence:** Hoch.

- **backtest-audit** (MIT): BacktestAuditor mit DSR (inkl. Newey-West-Autokorrelations-Korrektur), Monte-Carlo-Permutation (White Reality Check), Walk-Forward, Regime-Audit (LOW/NORMAL/HIGH-VOL), 7 Robustness-Stress-Szenarien, PBO via CPCV, Parameter-Sensitivität ("narrow peak vs. plateau"), REST-API.
  **Source:** github.com/Aliipou/backtest-audit
  **URL:** https://github.com/Aliipou/backtest-audit
  **Date:** 24.03.2026
  **Confidence:** Hoch.

- **pypbo** (älter, 2016): CSCV/PBO + PSR + MinTRL/MinBTL + DSR; Referenz-Implementierung, aber ungewartet.
  **Source:** github.com/esvhd/pypbo
  **URL:** https://github.com/esvhd/pypbo
  **Date:** 28.08.2016
  **Confidence:** Mittel (Legacy).

- **mlfinlab** (kommerziell, Hudson & Thames / QuantConnect-Cloud): Original-Implementierung; NICHT via PyPI installierbar — für unser Setup überflüssig, da mlfinpy+skfolio+backtest-guard/oos-lab alles abdecken.
  **Source:** qisagent.com Atlas-Profile; christopherspenn.com
  **URL:** https://qisagent.com/atlas/mlfinlab
  **Date:** 26.07.2026
  **Excerpt:** "mlfinlab is not installable from PyPI (commercial). Implement in pandas/numpy with vectorized barrier-crossing logic" bzw. mlfinpy als MIT-Ersatz.
  **Confidence:** Hoch.

### 4. Praktische Evidenz: dokumentierte Meta-Labeling-Ergebnisse

**Wichtigster Gesamtbefund (Multi-Market-Replikation, 42 Instrumente, voll vercostet, DSR-Gate):**

- **Claim:** Meta-Labeling macht genau das, was das Lehrbuch sagt — als **Precision-Filter**: hebt Precision und rohen Profit Factor in **38/42** Instrumenten, DSR in **39/42**, verdoppelt die Zahl der Instrumente mit PF>1 (12→24). ABER: Auf einem **edge-losen Primärmodell** (Vanilla-EMA-Crossover) erreichen **0/42** Instrumente DSR > 0,95 — "A filter can only concentrate edge that already exists." Markt-Mediane (Primär→Meta): Crypto PF 0,92→1,03, SR −0,61→+0,24; Equity PF 0,75→1,03, SR −0,68→+0,31; Forex PF 0,85→0,94, SR −1,13→−0,27. Medianer Precision-Lift +5–6 pp über Base-Rate.
  **Source:** daru.finance — "Labeling & Cross-Validation", Studie 02 (Meta-Labeling)
  **URL:** https://daru.finance/research-review/lopez-de-prado/labeling-and-cross-validation
  **Date:** o.D. (abgerufen 2026)
  **Excerpt:** "Meta-labeling does exactly what he says, it lifts precision and raw profit factor in 38/42 instruments and flips a cost-losing primary toward break-even. But on a vanilla EMA-crossover primary it is a precision filter, not an alpha source: 0 of 42 instruments clear DSR > 0.95. A filter can only concentrate edge that already exists."
  **Confidence:** Sehr hoch (1-Minuten-Echtdaten, Dollar/Tick-Bars, per-Fill-Kosten, Purged CV, ehrliche Trial-Zählung).

- **Claim (KORREKTUR / positiver Fall — LdP-Precondition erfüllt):** Mit Primärmodell, das **bereits Edge hat** (geschlossene, vorvalidierte Order-Flow/Open-Interest-Strategie), amplifiziert das Meta-Gate: OOS netto **PF 1,26 → 1,79**, Per-Trade-PnL **47 → 148 bp**, Profit-Rate 53,0 % → 63,6 %, Gate behält 64 % der Trades, DSR 0,64 → 0,78 (unter 0,95-Bar). Pro Paar: PF 1,32→1,49 und 1,23→1,96. **ABER Wash-out at Scale:** Gleiche Apparatur auf 6 Edges × 26 Perp-Paare (154 Sleeves): medianer PF-Lift nur **+0,02** (0,967→0,986), Per-Trade-PnL +4,7 bp; nur **1/154** Sleeves clearen DSR>0,95; gepoolte Meta-Strategie (14.725 OOS-Trades): **DSR 0,0**.
  **Source:** daru.finance — ebenda, Abschnitt 02b "Correction: meta-labeling a primary that already has an edge"
  **URL:** https://daru.finance/research-review/lopez-de-prado/labeling-and-cross-validation
  **Date:** o.D.
  **Excerpt:** "With the precondition met, the secondary amplifies the edge ... profit factor rises from 1.26 to 1.79 and mean per-trade P&L from 47 to 148 bp out-of-sample, net of per-fill costs ... the lift largely washes out [at scale]: median profit factor moves only 0.967→0.986 ... Only 1 of 154 meta-gated configurations clears DSR>0.95 ... pooled meta-strategy DSR is 0.0."
  **Confidence:** Sehr hoch. **Kernbotschaft für unser Projekt: PF-Verbesserung ~+0,5 ist auf fokussierten Setups mit echtem Primary-Edge dokumentiert, aber NICHT über viele Konfigurationen generalisierbar; Erwartung konservativ auf +0,1…+0,5 PF bei bereits profitablem Primary setzen, nie als Alpha-Quelle.**

- **Claim (Hudson & Thames / mlfinlab-Referenzstudie, S&P500-E-Mini-Tick-Daten):** Zwei Primary-Strategien (Bollinger-Mean-Reversion 1,5σ; SMA20/50-Trendfolge), RF-Meta-Modell. Features: RSI(14), Volatilität (50/31/15-Bar), MA(7/15), Autokorrelation 1–5 Tage, Momentum 1–5 Tage. Ergebnisse Mean-Reversion: Validation Accuracy 20 %→77 %, Precision 0,21→0,39; **OOS (2018-01→2019-01): Precision 0,17→0,20, Accuracy 17 %→63 %**; "alle Strategie-Metriken verbessert". Trendfolge OOS: Precision 0,48→0,54, Accuracy 48 %→55 %; risikoadjustiert besser, nicht auf jeder Rohmetrik. Hinweise: CUSUM-Threshold manuell getunt für genug Datenpunkte; Klassen-Upsampling wegen Ungleichgewicht; kein Bet-Sizing implementiert.
  **Source:** hudsonthames.org — "Does Meta Labeling Add to Signal Efficacy?" (Singh & Joubert)
  **URL:** https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/
  **Date:** 05.02.2023 (Artikel; Paper o.D.)
  **Excerpt:** "This test data is completely out-of-sample. The precision jumps from 0.17 to 0.20 and the accuracy from 17% to 63%. ... [Trend] precision increases from 0.48 to 0.54 and the accuracy from 48% to 55%. ... it doesn't out perform on all the metrics however it does outperform on a risk adjusted basis."
  **Confidence:** Mittel-Hoch (keine Kosten im Tear-Sheet explizit, kleine OOS-Periode, aber Original-Referenz der Methodik).

- **Claim (Peer-reviewed, ICAIF'20):** Meta-Labeling mit Random Forest + Feature-Selektion: Strategie-Sharpe **0,36 (ohne ML) → 0,74 (Meta-Labeling) → 0,83 (Meta + MDA/LIME/SHAP-Feature-Selektion)**; kumulierter Return 0,056 → 0,097 → 0,105 (100 RF-Seeds, Verteilung berichtet).
  **Source:** arXiv 2005.12483 — "The Best Way to Select Features? Comparing MDA, LIME and SHAP"
  **URL:** https://arxiv.org/pdf/2005.12483v1
  **Date:** ICAIF'20, Okt. 2020
  **Excerpt:** "the original Strategy without meta-labeling has a Sharpe ratio of 0.36. The mean Sharpe ratio increases to 0.74 when meta-labeling without feature selection is implemented, and it increases to 0.83 when feature selection is implemented."
  **Confidence:** Hoch (Konferenz-Paper), aber Sharpe-Ausgangsniveau niedrig.

- **Claim (Praktiker-System, Crypto):** Nydar (30+ Experimente, 10 Kryptos, 3 Timeframes, 8 ML-Architekturen, Walk-Forward 2000/500): XGBoost mit aggressiven Hyperparametern = bestes Einzelmodell (54–56 % Accuracy, RF 3–5 pp schlechter; LSTM/GRU/Transformer abgelehnt); **Meta-Labeling als Two-Stage-Confidence-Filter adoptiert, Beitrag +1–5 pp Accuracy**; Makro-Features (Yields, VIX, DXY, Gold) +3–5 pp.
  **Source:** nydar.co.uk — "How Nydar's AI Trading Signals Work — 13,500+ Model Fits"
  **URL:** https://nydar.co.uk/how-our-ai-works
  **Date:** 25.01.2026
  **Excerpt:** "XGBoost Aggressive — Winner — 54-56% ... Meta-Labeling — Adopted — +1-5% — Two-stage confidence filter ... Walk-forward validation (2000/500 split)"
  **Confidence:** Mittel (Vendor-Self-Report, kein unabhängiger Audit, aber ungewöhnlich detailliert/ehrlich inkl. Fehlschläge).

- **Claim (Gegenstimme):** QuantConnect-Forum (Francesco, beawai.com): Grid-Search mit use_meta ∈ {0,1} über mehrere Seeds — Meta-Modell verbreitert die Performance-Spanne, drückt aber den **durchschnittlichen** Sharpe vs. End-to-End-ML; "cannot increase the performance of a Machine Learning model trained end-to-end". Nutzen eher: Bet-Sizing für diskretionäre/exogene Modelle.
  **Source:** quantconnect.com/forum — "Why Meta-Labeling Is Not a Silver Bullet"
  **URL:** https://www.quantconnect.com/forum/discussion/14706/
  **Date:** 11.01.2023
  **Confidence:** Mittel (Einzelner Praktiker, aber methodisch nachvollziehbar; konsistent mit daru.finance-Scale-Befund).

- **Claim (Labeling-Benchmark, 16 Assets 2000–2025):** AEDL-Studie (MDPI): Triple-Barrier als Baseline erreicht im Schnitt **negativen Sharpe (−0,03)** über 16 Assets; beste Triple-Barrier-Konfiguration (Gradient Boosting) Sharpe 0,596. Lehre: Label-Methode allein erzeugt keinen Edge; Modellwahl × Label interagiert stark.
  **Source:** MDPI Applied Sciences 15(24):13204 — "Adaptive Event-Driven Labeling..."
  **URL:** https://www.mdpi.com/2076-3417/15/24/13204
  **Date:** 17.12.2025
  **Excerpt:** "AEDL achieves 0.480 Sharpe ratio versus negative performance for traditional baselines (Fixed Horizon: −0.29, Triple Barrier: −0.03, Trend Scanning: 0.00) ... the best baseline configuration (Triple Barrier with gradient boosting) achieves 0.596."
  **Confidence:** Mittel-Hoch (peer-reviewed, aber eigene Methode im Vergleich bevorteilt).

- **Claim (Horizon-Befund, relevant für Barrier-Parameter):** Trend-Scanning-Replikation: kurze Look-Forward-Bänder **(5,30) Bars kollabieren überall** (Equity DSR 0, PF 0,79); **(10,60) und (20,120) Bars halten in allen drei Märkten** (DSR 0,83–1,00). → Vertikale Barriere/Horizont nicht zu kurz wählen; mehrstündige bis mehrtägige Horizonte robust, Mikrostruktur-Horizonte werden von Kosten gefressen.
  **Source:** daru.finance — ebenda, Studie 03 (Trend-Scanning)
  **URL:** https://daru.finance/research-review/lopez-de-prado/labeling-and-cross-validation
  **Confidence:** Hoch.

### 5. Datenanforderung: Wie viele Trades/Signale minimal? (Prüfung der n≥300-Regel aus Wide02)

- **Wide02-Regel (interner Kontext):** "Forderung: ≥ 100–300 Trades, mehrere Regime" und Zielmetrik "PF > 1,5 bei n ≥ 300" für die SMC-Strategie. → n≥300 ist unser Projekt-interner Belastbarkeits-Maßstab.

- **Claim (Praktiker-Regel, konsistent):** Don Brady (Comintel/AFML-Meetup): "You need at least a **few hundred trades** history" als Voraussetzung für Meta-Labeling — auch bei diskretionären Primärmodellen ("Joe Trader's Bond Trading History" als explizit zulässiges Primary).
  **Source:** https://www.comintel.com/meetup/DonBrady/Meta-Labeling.pdf (o.D.)
  **Confidence:** Mittel-Hoch (Faustregel, kein formaler Beweis).

- **Claim (Ableitung aus Leckage-/CV-Befunden):** Die daru.finance-Leckage-Skalierung (Inflation ~ H/Fold-Size) und CPCV-Pfad-Streuung (~15 pp) implizieren: Bei n Trades und k Features sollte pro CPCV-Fold genug Signal-Events verbleiben, damit der Sekundär-Klassifikator überhaupt lernt (Tree-Modelle: Faustregel ≥10–20 Events pro Feature und Fold-Unterteilung). Mit 10–15 Features und N=6 CPCV-Gruppen sind 300 Events die praktische Untergrenze (≈50 Events/Gruppe, davon ~4/6 im Training ≈ 200). Zudem: Meta-Labeling erzeugt Klassen-Ungleichgewicht (mehr 0er) — Upsampling/`class_weight`/`scale_pos_weight` nötig (Hudson & Thames nutzten Up-Sampling).
  **Source:** Synthese aus daru.finance [Leckage-Gesetz], Hudson & Thames [Up-Sampling, CUSUM-Tuning für Datenmenge], mlfinlab-Warnung [min_ret nicht drehen]
  **Confidence:** Mittel (informierte Extrapolation, keine direkte Quelle für exakte Zahl).

- **Claim (Konsequenz für Timeframe):** Um n≥300 Signal-Events auf XAUUSD zu erreichen: H1-Primary mit moderater Signalrate (z. B. 2–5 Signale/Tag) benötigt ~0,5–1 Jahr Bars für 300–600 Events; M15 schneller, aber Achtung: kurze Horizonte/Barrieren kollabieren kostenbedingt (daru.finance (5,30)-Band-Befund) und Wide05-XAUUSD-AUC war nur 0,538 auf 14 Monaten. Empfehlung: H1/H4-Primary, Triple-Barrier-Horizont ≥10–60 Bars, NICHT min_ret senken um Event-Zahl künstlich zu erhöhen.
  **Source:** Synthese aus daru.finance Studie 03, wide05 [^9^ dort], mlfinlab-Doku
  **Confidence:** Mittel-Hoch.

### 6. Bet-Sizing aus Meta-Wahrscheinlichkeiten

- **Claim:** p = P(Meta-Label=1) direkt als Sizing-Input: (a) Linear: Size ∝ (p − 0,5), gecappt auf Max-Leverage; (b) **Kelly: f\* = (p·b − q)/b** mit b = Win/Loss-Verhältnis (≈ pt/sl-Verhältnis der Barrieren); (c) **Sigmoid: size = 2/(1+e^{−α(p−0,5)}) − 1** für glatte Übergänge (de Prados bevorzugte Form, AFML Kap. 10). Hedge-Fund-Case-Study: Trades mit p < 0,6 gefiltert + Confidence-Sizing → MaxDD −35 % bei nahezu gleichem Return.
  **Source:** Papers With Backtest Meta-Labeling-Course; risklab.ai "Bet Sizing"; quantstrategy.io "Optimal Bet Sizing"
  **URL:** https://paperswithbacktest.com/course/meta-labeling ; https://www.risklab.ai/research/backtesting/bet_size ; https://quantstrategy.io/blog/optimal-bet-sizing-integrating-ml-predictions-with-risk/
  **Date:** o.D. / 08.03.2024 / 04.08.2026
  **Excerpt:** "Linear sizing: position size proportional to p−0.5 ... Kelly criterion: f* = (p·b − q)/b ... Sigmoid mapping: size = 2/(1+e^{−α(p−0.5)}) − 1" / "By scaling the bet size based on the meta-model's confidence, they reduced their maximum drawdown by 35% while maintaining nearly the same total return."
  **Confidence:** Mittel-Hoch (Methodik kanonisch; Case-Study nicht unabhängig verifiziert).

### 7. Feature-Set zum Signalzeitpunkt (für unser XAUUSD/NAS100-Setup)

Belegte Feature-Kategorien aus den untersuchten Implementierungen:

- **Hudson & Thames (Referenz):** RSI(14), rollierende Volatilität (mehrere Fenster: 15/31/50 Bars), MA(7)/MA(15), Autokorrelation der Returns Lag 1–5, Momentum Lag 1–5. [hudsonthames.org]
- **PapersWithBacktest-Template:** "Market features + primary model prediction column" — die Primary-Seite selbst (+1/−1) als Feature aufnehmen.
- **QSE-Projekt (Produktions-Template):** Meta-Layer trainiert auf Regime-State (HMM), VPIN/Order-Flow-Imbalance, Signal-Stärke (s-score), Spread, Volatilität — "gated behind purging/embargo by design".
  **Source:** github.com/MarcusJMyrick/Quantitative-Strategy-Engine-QSE-/docs/PROJECT_PHASES.md
  **URL:** https://github.com/MarcusJMyrick/Quantitative-Strategy-Engine-QSE-/blob/main/docs/PROJECT_PHASES.md
  **Date:** 09.07.2026
  **Excerpt:** "a classifier decides whether to act and how big, trained on regime state, VPIN/OFI, s-score magnitude, spread, and vol ... it improves precision and sizes bets without ever predicting direction ... Deliberately last: it is only trustworthy under purging/embargo"
  **Confidence:** Mittel-Hoch (dokumentiertes Projekt, kein Track-Record-Beleg).
- **Nydar:** Makro-Features (Yields, VIX, DXY, **Gold** — für uns invertiert: bei XAUUSD-Primary ggf. DXY/Yields als Kontext) +3–5 pp.
- **Wide05-Kontext:** SR_Mapping_NN (XAUUSD-MT5): AUC 0,538 als Entry-Filter, hohe Thresholds → wenige, präzisere Trades; Retraining alle 1–3 Monate.
- **Eigene Ergänzung (aus Bot-Kontext abgeleitet):** ATR(14) absolut + relativ (ATR/Median-ATR), ADX (Trendstärke), Session-Dummies (Asia/London/NY + Stunde-des-Tages zyklisch kodiert), Spread zum Signalzeitpunkt (in Punkten/%-des-ATR), Candle-Statistiken (Body/Range-Ratio, Wick-Anteile, Close-Position-in-Range), Abstand zu HTF-EMA/PDH-PDL, laufende Konfluenz-Score des Primary. **Kein Lookahead: alle Features strikt kausal bis Signal-Bar-Close.**

---

## IMPLEMENTIERUNGS-SPEZIFIKATION

Konkrete, umsetzbare Spezifikation für den Meta-Labeling-Layer über den 5 MT5-Bots (pymt5trade). Ziel: PF > 1,5 OOS auf Strategieebene — Meta-Layer als Precision-Hebel, NICHT als Alpha-Ersatz.

### A. Architektur (2-stufig)

1. **Primary Model (bestehend):** Regel-Entries der Bots (SMC-Sweep/CHoCH/FVG, Trend-Pullback etc.). Primary liefert je Event: `t0` (Signal-Bar-Close), `side` ∈ {+1 long, −1 short}. Primary bewusst auf **hohe Recall** einstellen (lieber mehr Signale, der Filter entscheidet).
2. **Labeling (offline, mlfinpy oder eigenes pandas/numpy):**
   - `daily_vol = get_daily_vol(close, lookback=50)` (EWMA, kausal).
   - Vertikale Barriere: 10–60 Bars des Execution-Timeframes (H1: 10–60 h; Begründung: daru.finance-Horizon-Befund — kurze Bänder kollabieren). Startwert: 24 Bars.
   - `pt_sl = [2.0, 1.5]` × trgt (Start), Sweep ∈ {[1.5,1.0], [2.0,1.5], [2.5,2.0], [3.0,1.5]} — **als Trial gezählt** (DSR/PBO!).
   - `min_ret = 0.0005` fix lassen — NICHT drehen, um Event-Zahl zu erhöhen (mlfinlab-Warnung).
   - `get_events(..., side_prediction=side)` → Meta-Label bin ∈ {0,1} direkt aus PnL-Vorzeichen; `t1` (erster Barrier-Touch) pro Event **persistieren** (Pflicht für Purging).
   - Kosten ins Label einrechnen: Label = 1 nur wenn Brutto-PnL > (Spread + Kommission + Slippage-Schätzung). Sonst lernt der Filter kostendeckende Scheingewinne.
3. **Secondary Model:** `xgboost.XGBClassifier` (CPU). Alternativ-Baseline RandomForest (H&T-Referenz) — XGBoost als Hauptmodell (Nydar-Befund: RF 3–5 pp schlechter).

### B. Feature-Set zum Signalzeitpunkt (alle strikt kausal, Stand Signal-Bar-Close)

| # | Feature | Typ/Parameter |
|---|---|---|
| 1 | ATR(14) in Preiseinheiten | Execution-TF |
| 2 | ATR-Ratio | ATR(14) / median(ATR(14), 100 Bars) |
| 3 | ADX(14) | Trend-Stärke |
| 4 | Trend-Alignment | Abstand Close zu EMA(50/200) in ATR-Einheiten (auch HTF) |
| 5 | RSI(14) | H&T-Referenz |
| 6 | Return-Autokorrelation Lag 1–5 | H&T-Referenz |
| 7 | Momentum 1–5 Bars | H&T-Referenz |
| 8 | Volatilität 15/50-Bar (roll. Std der Returns) | H&T-Referenz |
| 9 | Session-Dummies + sin/cos(Stunde) | Asia/London/NY |
| 10 | Spread zum Signalzeitpunkt | Punkte + %-von-ATR |
| 11 | Candle-Statistik | Body/Range, oberer/unterer Wick-Anteil, Close-Pos-in-Range |
| 12 | Primary-Side (+1/−1) und Primary-Konfluenz-Score | Meta-Input |
| 13 | Distanz zu PDH/PDL bzw. letztem Swing in ATR | SMC-Kontext |
| 14 | (optional) Makro: DXY-/Yield-Proxy, VIX | Nydar-Befund |

Max. ~15 Features halten (Overfitting-Bremse); redundante Features via MDA/SHAP-Selektion reduzieren (ICAIF'20: Sharpe 0,74→0,83 durch Feature-Selektion).

### C. Training & Validierung (nicht verhandelbar)

1. **Split-Strategie:** Finale 12 Monate als unberührtes Holdout. Davor: **CPCV N=6, k=2** (15 Splits, 5 Pfade; Aalto-Referenz-Setup), Purge = Label-Overlap via `t1`, **Embargo = 1 %** der Samples.
2. **Implementierung CV:** `skfolio.model_selection.CombinatorialPurgedCV` oder `backtest_guard.PurgedKFold(n_splits=5, label_end_times=t1, embargo_fraction=0.01)` (sklearn-kompatibel → direkt in `cross_val_score`/`GridSearchCV`).
3. **Hyperparameter-Räume XGBoost (klein halten — jede getestete Kombi = Trial für DSR):**
   - `max_depth`: [2, 3, 4, 5] (finanzielle Noisy-Data → flach; Default 6 ist Obergrenze, nie >6)
   - `learning_rate` (eta): [0.01, 0.03, 0.05, 0.1]
   - `n_estimators`: [100, 300, 500] mit Early Stopping (50 Runden) auf Purged-Val-Fold
   - `subsample`: [0.5, 0.7, 0.8]
   - `colsample_bytree`: [0.6, 0.8, 1.0]
   - `min_child_weight`: [1, 5, 10]
   - `scale_pos_weight` = #neg/#pos (Klassen-Ungleichgewicht) oder Up-Sampling (H&T)
   - `gamma`: [0, 0.1] — Grid bewusst < 500 Kombis halten; besser RandomizedSearch n_iter≈50.
4. **Selektions-Metrik:** Mittleres OOS-**AUC** über CPCV-Pfade (Leak in AUC sichtbar; Accuracy-Fold-Rauschen zu groß) + Precision@Threshold. Threshold-Sweep {0,50; 0,55; 0,60; 0,65; 0,70} — ebenfalls Trials.
5. **Statistische Gates (Pflicht vor Live):**
   - **DSR ≥ 0,95** auf der finalen Equity-Kurve, mit ehrlichem `n_trials` = alle getesteten Parameter-Kombis inkl. Barrier-Sweep und Threshold-Sweep (Tools: `backtest-guard` oder `oos-lab`).
   - **PBO < 0,2** über CSCV S=16 auf der Return-Matrix aller Trials (>0,5 = aktiv irreführend, saral.money-Interpretation).
   - **CPCV-Pfadverteilung:** Anteil profitabler Pfade > 50 % (ml4t_diagnostic-Kriterium); Median-PF der Pfade, nicht Max-PF berichten.
   - Walk-Forward mit periodischem **Retraining alle 1–3 Monate** (wide05-Konsens, Alpha-Decay).
   - Kosten: XAUUSD Spread+Kommission+Slippage pro Trade im Backtest (daru-Standard: jede Positionsänderung vercostet).
6. **Paper-Trading:** 3–6 Monate Demo (TradeAlgo-Workflow, SR_Mapping_NN-Limitation) vor Prop-Firm-Einsatz.

### D. Inferenz im Live-Bot (pymt5trade)

1. Primary feuert Signal (t0, side) → Feature-Vektor aus den letzten Bars berechnen (identische Feature-Pipeline wie offline! Ein Feature-Modul, shared code).
2. `p = model.predict_proba(X)[1]`.
3. **Gate:** Trade nur wenn `p ≥ threshold` (Start 0,55–0,60; Case-Study: p<0,6-Filter → MaxDD −35 %).
4. **Sizing:** Sigmoid-Mapping `size_factor = 2/(1+exp(−α·(p−0.5))) − 1`, α≈10–12, geclippt auf [0, 1]; multipliziert mit Basis-Risiko 0,5 %/Trade (Prop-Firm-Constraint). Kelly-Fraktion f*=(p·b−q)/b mit b = pt/sl nur als Sanity-Check/Obergrenze, halbes Kelly falls genutzt.
5. **Monitoring:** Rollierende Precision des Meta-Modells auf realisierten Trades; Degradation unter IS-Niveau −1σ → Retrain; Log aller vetoed Trades für nachträgliche Analyse.

### E. Daten-/Sample-Budget

- **Minimum n = 300 Primary-Signal-Events** pro Instrument/Strategie (wide02-Regel, Brady-Faustregel "a few hundred trades"); **Ziel 500–1.000+** für stabilere CPCV-Folds (mit N=6 → ≥50 Events/Gruppe, Trainings-Subset ≈4/6).
- Bei n<300: Meta-Labeling NICHT trainieren — stattdessen nur harte Regel-Filter (Session/Spread/ADX) verwenden.
- Erreichbarkeit: H1-Primary mit 2–4 Signalen/Tag → ~500–1.000 Events/Jahr → 1–2 Jahre M1/H1-Historie aus MT5 exportieren. Horizont/Barrieren NICHT zur Event-Maximierung verbiegen.
- Class-Balance prüfen; `scale_pos_weight` oder Up-Sampling.

### F. Realistische Erwartung (Evidenz-basiert)

- **Best-Case dokumentiert:** PF 1,26→1,79 (+0,53), Per-Trade-PnL ×3, Sharpe 0,36→0,83 (mit Feature-Selektion), Precision +5–6 pp OOS, MaxDD −35 % via Sizing.
- **Median at Scale:** PF-Lift nur +0,02; 1/154 Configs übersteht DSR>0,95; pooled DSR 0,0 (daru.finance).
- **Planungsannahme:** Meta-Layer hebt PF eines **bereits profitablen** Primary (PF ≥ 1,2 nach Kosten) um **+0,1 bis +0,3** und senkt MaxDD spürbar; auf PF<1,0-Primary rettet er bestenfalls auf ~Break-even (Forex-Median 0,85→0,94). **Meta-Labeling ist die Maßnahme NACH der Primary-Edge-Validierung, nicht davor.**
- Ziel PF>1,5 OOS muss primär vom Regelwerk kommen; Meta-Layer + Bet-Sizing sind der Hebel von z. B. 1,3 → 1,5+.

---

## Quellen

[^1^]: Papers With Backtest — "Meta-Labeling: How to Size Bets with ML (Algo Trading)", o.D. https://paperswithbacktest.com/course/meta-labeling
[^2^]: Mehta/Mittal — Theseus-Thesis (Meta-Labeling für Signalqualität), o.D. https://www.theseus.fi/bitstream/handle/10024/746368/Mehta_Mittal.pdf
[^3^]: Comintel Meetup — Don Brady, "Meta-Labeling" (Vortragsfolien, Chan/de Prado-Zitate, "few hundred trades"), o.D. https://www.comintel.com/meetup/DonBrady/Meta-Labeling.pdf
[^4^]: arXiv 2510.26353 — "Towards Explainable and Reliable AI in Finance" (Corrective AI), 2025. https://arxiv.org/html/2510.26353v1
[^5^]: mlfinpy-Dokumentation — Data Labelling (get_events/get_bins, AFML Snippet 3.7), o.D. https://mlfinpy.readthedocs.io/en/latest/Labelling.html
[^6^]: PickMyTrade — "Advanced AI Trading Guide" (mlfinpy/skfolio, Triple-Barrier-Code pt_sl=[2.0,1.5]), 03.07.2026. https://pickmytrade.io/ai-ml/advanced-guide
[^7^]: mlfinlab-Dokumentation — "Triple-Barrier and Meta-Labelling" (min_ret-Warnung), o.D. https://www.mlfinlab.com/en/latest/labeling/tb_meta_labeling.html
[^8^]: christopherspenn.com — "Doubling USD 100 in 90 Days" (Replikations-Vorbehalt Triple-Barrier/Meta-Labeling; Karakunnel 2025, Karasan 2024), 02.08.2026. https://www.christopherspenn.com/interactives/investment-report-example.html
[^9^]: quant67.com — "Walk-forward 与 Purged CV" (Embargo 1 %-Heuristik, t1/t2-Persistenz), 01.05.2026. https://quant67.com/post/quant/21-walkforward-cv/21-walkforward-cv.html
[^10^]: daru.finance — "Labeling & Cross-Validation" (42 Instrumente: K-Fold-Leckage-Gesetz, CPCV-Dispersion ~15 pp, Meta-Labeling 38/42 PF-Lift, 0/42 DSR>0,95; Correction: PF 1,26→1,79 mit Edge-Primary, Wash-out at Scale pooled DSR 0,0; Horizon (10,60)/(20,120) vs. (5,30)), o.D. https://daru.finance/research-review/lopez-de-prado/labeling-and-cross-validation
[^11^]: risklab.ai — "Backtesting through Cross-Validation (CPCV)" (φ(N,k)-Formel, k=2 Sweet Spot), 22.06.2026. https://www.risklab.ai/research/backtesting/backtesting_cross_validation
[^12^]: Aalto-Thesis (CPCV-Praxis: N=6, k=2, Purge 90/7 Tage, Embargo 1 %), o.D. https://aaltodoc.aalto.fi/bitstreams/1ad6e657-e74a-495c-8222-aae0d6949d80/download
[^13^]: GitHub — AgentJDrew/backtest-guard (DSR/PBO/PurgedKFold, MIT, Worked Example), 06.07.2026. https://github.com/AgentJDrew/backtest-guard
[^14^]: daru.finance — "Backtest Overfitting & the Deflated Sharpe Ratio" (92.500 Strategien, DSR 0,029, PBO 0,28, 434 effektive Trials), o.D. https://daru.finance/research-review/lopez-de-prado/backtest-overfitting
[^15^]: saral.money — "Backtest Overfitting: The Deflated Sharpe Test" (PBO-Interpretation: <0,2 prädiktiv, >0,5 irreführend; S=16 → 12.870 Splits), 01.08.2026. https://saral.money/blog/backtest-overfitting-deflated-sharpe/
[^16^]: GitHub — OutOfSampleLab/oos-lab (PSR/DSR/CPCV/PBO/Harvey-Liu, pip, MIT), 24.06.2026. https://github.com/OutOfSampleLab/oos-lab
[^17^]: GitHub — Aliipou/backtest-audit (DSR+MC+WalkForward+Regime+Robustness+PBO, REST-API, MIT), 24.03.2026. https://github.com/Aliipou/backtest-audit
[^18^]: GitHub — esvhd/pypbo (CSCV/PBO-Referenz, Legacy), 28.08.2016. https://github.com/esvhd/pypbo
[^19^]: qisagent.com — "mlfinlab (Hudson & Thames) — QIS Atlas Profile" (Lizenz-Situation), 26.07.2026. https://qisagent.com/atlas/mlfinlab
[^20^]: Hudson & Thames — Singh & Joubert, "Does Meta Labeling Add to Signal Efficacy?" (Bollinger/SMA-Primaries, RF-Meta, OOS Precision 0,17→0,20 / 0,48→0,54, Feature-Liste, Up-Sampling), 05.02.2023. https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/ (Paper: https://hudsonthames.org/wp-content/uploads/2022/04/Does-Meta-Labeling-Add-to-Signal-Efficacy.pdf)
[^21^]: arXiv 2005.12483 — "The Best Way to Select Features? Comparing MDA, LIME and SHAP" (ICAIF'20; Sharpe 0,36→0,74→0,83 mit Meta-Labeling+Feature-Selektion), Okt. 2020. https://arxiv.org/pdf/2005.12483v1
[^22^]: Nydar — "How Nydar's AI Trading Signals Work — 13,500+ Model Fits" (XGBoost 54–56 %, Meta-Labeling +1–5 pp, Walk-Forward 2000/500), 25.01.2026. https://nydar.co.uk/how-our-ai-works
[^23^]: QuantConnect-Forum — "Why Meta-Labeling Is Not a Silver Bullet" (Francesco), 11.01.2023. https://www.quantconnect.com/forum/discussion/14706/
[^24^]: MDPI Applied Sciences 15(24):13204 — "Adaptive Event-Driven Labeling" (Triple-Barrier-Baseline Sharpe −0,03 über 16 Assets), 17.12.2025. https://www.mdpi.com/2076-3417/15/24/13204
[^25^]: quantstrategy.io — "Optimal Bet Sizing: Integrating ML Predictions with Risk Management" (Sigmoid-Sizing, Case-Study MaxDD −35 %), 04.08.2026. https://quantstrategy.io/blog/optimal-bet-sizing-integrating-ml-predictions-with-risk/
[^26^]: risklab.ai — "Bet Sizing" (Meta-Labeling-Wahrscheinlichkeit als Sizing-Input, AFML Kap. 10), 08.03.2024. https://www.risklab.ai/research/backtesting/bet_size
[^27^]: GitHub — MarcusJMyrick/Quantitative-Strategy-Engine-QSE- (Phase 16 Meta-Labeling: Features Regime/VPIN/s-score/Spread/Vol; Purging-Gate), 09.07.2026. https://github.com/MarcusJMyrick/Quantitative-Strategy-Engine-QSE-/blob/main/docs/PROJECT_PHASES.md
[^28^]: TradeAlgo — "Machine Learning Backtesting Guide" (10-Schritte-Workflow, Paper-Trading 3–6 Monate), 23.02.2026. https://www.tradealgo.com/trading-guides/ai-trading/machine-learning-backtesting-guide
[^29^]: XGBoost RFC #12131 — "Revisit Default Hyperparameters" (vorgeschlagene Defaults eta=0.1, subsample=0.8, colsample=0.8, n_estimators=300), 26.03.2026. https://github.com/dmlc/xgboost/issues/12131
[^30^]: ml4t_diagnostic — docs/methods/cpcv.md (CPCV-Motivation: ">50 % der Pfade profitabel?"), 02.05.2026. https://github.com/horatioh/ml4t_diagnostic/blob/main/docs/methods/cpcv.md
[^31^]: Interner Kontext: trading_strategies_wide02.md (n≥300-Regel, PF>1,5-Ziel) und trading_strategies_wide05.md (XAUUSD-AUC 0,538, SR_Mapping_NN, Retraining 1–3 Monate).
