# Deep-Dive Dimension 08: HMM-/Regime-Detection als Overlay-Filter für Trend-/Breakout-Strategien

Recherche-Facet: Hidden Markov Models (hmmlearn/GaussianHMM), Jump-Modelle, Volatilitäts-Regime als Risiko-Overlay für klassische Trend-/Breakout-Strategien auf XAUUSD/Forex (MT5, Prop-Firm-Kontext: EOD-DD-Reduktion).
Methodik: 16 gezielte Websuchen (EN/DE), Deep-Dives via web_open_url in QuantStart (Volltext inkl. Code + Tearsheet-Zahlen), rahulsp.com (XAUUSD-Kalman+HMM-Paper), arXiv-Quellen, hmmlearn-Doku, GitHub-Implementierungen. Stand der Recherche: siehe Quellen-Datumsangaben.

## Key Findings (Überblick)

1. **DD-Reduktion ist der robuste, replizierbare Effekt — Return-Boost ist fragil.** QuantStart OOS (2005–2014, fixiertes HMM): MaxDD 56,5 % → 24,0 %, Sharpe 0,37 → 0,48, CAGR 6,41 % → 6,88 %, Trades 41 → 31. QuantConnect GLD/SPY: **40/40 Parameter-Kombis reduzieren Drawdown, nur 11/40 schlagen Benchmark-Sharpe.** [^1^][^4^]
2. **XAUUSD-spezifische Evidenz existiert und ist ehrlich:** rahulsp.com (M1-Gold, mit Spread-Kosten): Kalman-Mean-Reversion PF 1,34 → +HMM-Filter PF 1,42; simpler ATR-Median-Vol-Filter erreicht PF 1,31. HMM > simpler Proxy, aber **marginaler Vorsprung**. ABER: Autor hat HMM full-sample gefittet (Lookahead!) und warnt selbst, dass Walk-Forward-Retraining die Performance "likely degrade" wird. [^6^]
3. **2 Regime sind die robusteste Default-Wahl** (BIC bevorzugt N=2 auf 4 FX-Paaren und Faktor-Daten; 24 europäische Indizes: 2–3 Zustände, Wechselwahrscheinlichkeit <2 %). 3 Regime (trending/ranging/volatile) nur mit Interpretierbarkeits-Begründung, nicht per Informationskriterium. [^8^][^9^][^12^]
4. **Re-Fit-Frequenz: Konsens = periodisch (wöchentlich bis monatlich), strikt kausal.** Praxis-Spannweite: QuantStart gar kein Re-Fit (10 Jahre OOS, funktionierte trotzdem); QuantConnect 50-Wochen-Lookback, wöchentlich; LSEG expanding-window mit retrain_step; QuantInsti rollierendes 4-Jahres-Fenster. Lookahead-Regel: predict nur auf Daten ≤ t, letzter Viterbi/Posterior-Wert. [^1^][^2^][^3^][^4^]
5. **Einfache Proxys (ADX, ATR-Perzentil) sind ernstzunehmende Konkurrenz bei begrenzter Datenlage.** GC-Gold ATR-Perzentil-Breakout (1H, 2023–2026, mit Kosten): WR 52,2 %, PF 1,30, MaxDD 12 %. ATR-Median-Filter auf XAUUSD M1: PF 1,31 (vs. HMM 1,42). Empfehlung: HMM UND Proxy als Ablations-Arme im Walk-Forward testen. [^6^][^14^][^15^][^16^]
6. **Jump-Modelle (Nystrup et al.) sind die akademisch überlegene Alternative zu HMM** bei wenig Daten, unbalancierten Regimen, hoher Persistenz und Trading-Delays: HMM-basierte Strategie fällt bei 5-Tage-Delay auf DAX/Nikkei ab, JM bleibt bis 2-Wochen-Delay profitabel; +1–4 % ann. Return vs. B&H bei 10 bps Kosten. [^5^][^11^]

---

## 1. QuantStart-HMM-Serie: konkrete Parameter und Ergebnisse (Volltext extrahiert)

**Claim:** Das kanonische Practitioner-Template. 2-State GaussianHMM auf SPY-Tagesreturns als *Risk-Manager-Overlay* über eine SMA(10/30)-Cross-Strategie.
**Source:** QuantStart — "Market Regime Detection using Hidden Markov Models in QSTrader" (Serie: "Hidden Markov Models – An Introduction" → "HMM for Regime Detection using R" (depmixS4) → QSTrader-Artikel)
**URL:** https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/
**Date:** o.D. (Serie ca. 2016/17; abgerufen im Rahmen dieser Recherche)
**Confidence:** Hoch (vollständiger Code + Tearsheet-Zahlen im Artikel; unabhängig in MIJ-Paper 2020 nachvollzogen [^7^])

**Excerpt / extrahierte Parameter:**
- Training: SPY Adj-Close-Tagesreturns, 29.01.1993 → 31.12.2004; `GaussianHMM(n_components=2, covariance_type="full", n_iter=1000)`, univariat (`np.column_stack([rets])`), Modell via pickle serialisiert. "Two states are used in this article, but three could also be tested easily. A full covariance matrix is used, rather than a diagonal version."
- Inferenz im Backtest: `hidden_state = hmm_model.predict(returns)[-1]` — Viterbi über alle bis t beobachteten Returns, **nur der letzte State wird verwendet** (kausal korrekt).
- Filter-Logik (RegimeHMMRiskManager): Regime 0 (low-vol) → BOT und SLD normal; Regime 1 (high-vol) → **keine neuen BOT-Orders**, SLD nur wenn Position offen ("never generating a new long position when in regime #1. However, a previously open long position can be closed in regime #1. An alternative approach might be to immediately close any open long position upon entering regime #1").
- Backtest OOS 01.01.2005–31.12.2014, **ohne Retraining** ("no returns data used within the backtest was used in the training of the Hidden Markov Model"), mit Transaktionskosten (IB-Fixed-Pricing).

**Ergebnisse (Tearsheet):**
| Metrik | Ohne Filter | Mit HMM-Filter | Benchmark SPY |
|---|---|---|---|
| Sharpe | 0,37 | 0,48 | 0,37 |
| CAGR | 6,41 % | 6,88 % | 5,62 % |
| MaxDD | 56,47 % | 23,96 % | 56,47 % |
| Sortino | 0,38 | 0,45 | 0,46 |
| Annual Vol | 26,01 % | 16,82 % | 20,37 % |
| Trades | 41 | 31 | – |

Autoren-Kommentare: Strategie handelte von Anfang 2008 bis Mitte 2009 **gar nicht** (blieb im DD vom High Watermark, verlor aber nichts); Trade-Reduktion 41→31 = "less positively expected bets... less statistical validity"; **"A production implementation would likely periodically retrain the HMM as the estimated state transition probabilities are very unlikely to be stationary... The rate at which this needs to be carried out is the subject of potential future research."**

---

## 2. Implementierungs-Details aus weiteren Quellen

### 2.1 Feed-Forward-/Walk-Forward-Training (Lookahead-Vermeidung)

**Claim:** Expanding-Window mit periodischem Re-Fit; nur der letzte vorhergesagte State wird je Schritt verwendet.
**Source:** LSEG (Refinitiv) Developer Article — "Market regime detection using Statistical and ML based approaches"
**URL:** https://developers.lseg.com/en/article-catalog/article/market-regime-detection
**Date:** 13.02.2023 | **Confidence:** Hoch (Code-Volltext)

**Excerpt:** `feed_forward_training(model, params, prices, split_index, retrain_step)`: initiales Fit auf Trainings-Block, dann pro Beobachtung `preds = rd_model.predict(prices[:split_index]).tolist(); states_pred.append(preds[-1])`, Re-Fit `if i % retrain_step == 0`. HMM-Params: `{'n_components':2, 'covariance_type':"full", 'random_state':100}`. Vergleich: GMM detektiert Crash-Regime "with smaller lags" als agglomeratives Clustering; explizite Warnung: "both results come from in-sample testing, and as expected, out-of-sample testing may lead to worse results."

### 2.2 Rollierendes Fenster + Regime-Spezialisten (QuantInsti)

**Claim:** 4-Jahres-Rolling-Window, 2-State-HMM auf Tagesreturns, danach je Regime ein Random-Forest-Spezialist; Signal-Schwelle >0,53.
**Source:** QuantInsti Blog — "Market Regime using Hidden Markov Model"
**URL:** https://blog.quantinsti.com/regime-adaptive-trading-python/
**Date:** 07.08.2025 | **Confidence:** Mittel (Tutorial, kein Peer-Review)

**Excerpt:** "It creates a window_size (4 years) of the most recent historical data... trains a Hidden Markov Model (HMM) on the daily returns... We've set it to find two states, which often correspond to low-volatility and high-volatility periods... if the HMM is leaning towards Regime 0 for tomorrow, we use the signal from Model 0... We only go long (1) if the chosen model's probability is high enough (e.g., > 0.53)." Ergebnis (BTC, lt. Secondary-Quelle): Sharpe 1,76 vs. 1,16 B&H, Vol 26 % vs. 43 %, MaxDD −20 % vs. −28 %.

### 2.3 QuantConnect GLD/SPY — Re-Fit-Frequenz + Parameter-Sensitivität

**Claim:** HMM auf SPY-Drawdown-Regime → Rotation SPY↔GLD; 50-Wochen-Lookback fürs Fit, wöchentliches Rebalancing; Ergebnis extrem fenster-/parameter-abhängig.
**Source:** QuantConnect Forum/Research — "Drawdown Regime Gold Hedge: Using HMM to Rotate Between SPY and GLD – 20-Year Backtest Results"
**URL:** https://www.quantconnect.com/forum/discussion/20417/ und https://www.quantconnect.com/research/18811/
**Date:** 12.03.2026 / 28.03.2025 | **Confidence:** Hoch (plattform-verifizierte Backtests)

**Excerpt:** "Key parameters include a 50-week history lookback for HMM fitting and a 20-week drawdown lookback window." 6-Jahres-Backtest (2019–2025): Sharpe 0,823, CAGR 19,8 %, MaxDD 27,1 %, WR 79 %. 20-Jahres-Backtest (2005–2025): Sharpe 0,469, PSR 1,3 % (!), CAGR 12,2 %, MaxDD 41 %, WR 70 %. "QC flags this as 'Likely Overfitting' due to 16 parameters... HMM-based regime detection adds value but is sensitive to parameter choices... only 11/40 parameter combos beat benchmark Sharpe, but 40/40 reduced drawdown." (Sensitivitätstest lt. Research-Seite 18811, in wide05 zitiert.)

### 2.4 hmmlearn-Praxis: Kovarianztyp, Restarts, Modellselektion

**Claim:** EM landet in lokalen Optima → mehrere Restarts Pflicht; AIC/BIC-Selekteion über n_components; `min_covar` gegen Overfitting.
**Source:** hmmlearn offizielle Doku (Tutorial, API, Model-Selection-Example)
**URL:** https://hmmlearn.readthedocs.io/en/stable/auto_examples/plot_gaussian_model_selection.html ; https://hmmlearn.readthedocs.io/en/latest/tutorial.html
**Date:** Doku-Stand 0.3.3 (abgerufen in dieser Recherche) | **Confidence:** Hoch (Primärdoku)

**Excerpt:** "since the EM algorithm is a gradient-based optimization method, it will generally get stuck in local optima. You should in general try to run fit with various initializations and select the highest scored model." Model-Selection-Beispiel: `for n in [2..6]: for i in range(10): GaussianHMM(n, n_iter=200, tol=1e-4, random_state=rs)` → bestes LL, dann `model.aic(X)`/`model.bic(X)` vergleichen. Kovarianztypen: spherical/diag/full/tied; `min_covar` default 1e-3 ("Floor on the diagonal of the covariance matrix to prevent overfitting"). GitHub-Issue (Sakeeb91, 31.12.2025) zeigt Praxis-Pattern: BIC über n∈{2..5}, full covariance, n_iter=1000, random_state fixiert.

### 2.5 Anzahl Regime: BIC-Antwort ist meist 2

**Claim:** Auf FX- und Faktor-Daten bevorzugt BIC konsistent 2 Zustände; 3–4 nur bei explizitem Granularitäts-Bedarf.
**Sources:** (a) EconStor/Risks-Paper (HMM auf 4 FX-Paare, 3-Jahres-Kalibrierblöcke, quartalsweise gerollt, 2–5 Zustände): "based on the BIC, the HMM with two states is the best candidate for all four currency pairs." URL: https://www.econstor.eu/bitstream/10419/257904/1/risks-07-00066-v2.pdf (o.D.) — **Confidence: Hoch (Peer-Review-Journal "Risks")**. (b) City-University-Thesis 2025 (6 Fama-French-Faktoren 1963–2024): "AIC minimum at M=3, BIC minimum at M=2... prioritizing parsimony we select M=2." URL: https://openaccess.city.ac.uk/id/eprint/36507/ — **Confidence: Mittel-Hoch**. (c) Farzulla 2025: 4-State bester statistischer Fit, aber bewusst 3-State behalten "for interpretability and operational relevance (Low/Moderate/Elevated)". URL: https://farzulla.org/papers/Farzulla_2025_ASRI.pdf — **Confidence: Mittel**. (d) Economic Studies (Bulgarian Academy, 24 europäische Indizes): "information criteria clearly show the superiority of models with a small number of two or three states... average probability of switching from the calmer to the riskier state of less than 2%" (hohe Persistenz). URL: https://www.iki.bas.bg/Journals/EconomicStudies/2023/2023-1/22-01_bodytext.pdf — **Confidence: Hoch**.

### 2.6 Features: was in den HMM gehört

**Claim:** Minimal = Returns (+Realized Vol); erweitert = log-Vol, log-ATR, log-Volumen; Feature-Auswahl muss pro Regime separierbar sein; Rolling-Z-Score-Normalisierung üblich.
**Sources:**
- HamidAbbasi-R/ML-Toolbox-Finance (GitHub, 22.11.2024): Features "Return or log return, Log volatility, Log volume, Log ATR"; Warnung: "it is important to choose features that have a relationship with each other in all the regimes... all features should be separated by the hidden states." https://github.com/HamidAbbasi-R/ML-Toolbox-Finance — **Confidence: Mittel (Praktiker-Repo, gut begründet)**.
- Jaival111/Algo-Trading-Hackathon TECHNICAL_SPECIFICATION (2024): `X = [returns, atr_normalized]`, 3 Regime "sorted by variance: Regime 0 (TREND): Low variance → Trend-following; Regime 2 (VOLATILE): High variance → Mean-reversion"; regime-abhängiges Risiko 1,5 %/1,2 %/1,0 %, SL/TP in ATR-Multiples (2,0/5,0 | 2,5/4,0 | 3,0/3,0). **Wichtig: explizites State-Re-Mapping via Varianz-Sortierung — löst das Label-Switching-Problem nach jedem Re-Fit.** https://github.com/Jaival111/Algo-Trading-Hackathon/blob/main/TECHNICAL_SPECIFICATION.md — **Confidence: Mittel**.
- saiemula/Market-Regime-Detection-System (02.04.2026): Feature-Set Trend/Momentum/Vol/Volume/Market-Structure, "All features are z-score normalised within a rolling 252-day window to ensure stationarity"; GaussianHMM 3-State auf Return+Vol; Regime-Labeling via 20 %-Drawdown-Regel (Bär), Trend-Slope+Vol-Bounds (Sideways). https://github.com/saiemula/Market-Regime-Detection-System — **Confidence: Mittel**.
- Shivansh-707/Regime_aware_model (02.12.2025): GaussianHMM 3-State, Features = Returns, Rolling-Vol, ATR, Volume-Ratio → Regime-Embedding verbessert LSTM-Vol-Prognose (RMSE/MAE, Stabilität in High-Vol). https://github.com/Shivansh-707/Regime_aware_model — **Confidence: Niedrig-Mittel (Studentenprojekt)**.
- quantifiedstrategies.com (01.02.2026, Authority B): HMM-Feature-Beispiel "returns, volatility, VIX, 50–200-day MA trend signal, 10-year yield"; Interpretation via State-Means/Varianzen ("state 0 mean +0.02 %, state 1 mean −0.36 %"); HMM als Trade-Filter/Position-Modifier oder Stop-Trigger ("immediately liquidate if the model switches to the high-volatility state"). https://www.quantifiedstrategies.com/hidden-markov-model-market-regimes-how-hmm-detects-market-regimes-in-trading-strategies/ — **Confidence: Mittel**.

### 2.7 Jump-Modelle vs. HMM (akademischer Vergleich)

**Claim:** Bei begrenzten Daten, unbalancierten Regimen und Trading-Delays schlägt das Statistical Jump Model (Jump-Penalty λ erzwingt Persistenz) klassische HMMs.
**Sources:**
- arXiv 2402.05272 (Shu, Nystrup et al.) — "Downside Risk Reduction Using Regime-Switching Signals", v2 10.07.2024: JM-Features = Risiko-/Return-Maße aus der Return-Serie; Jump-Penalty per Time-Series-CV direkt auf **Strategie-Performance** optimiert; S&P500/DAX/Nikkei 1990–2023, 10 bps Kosten + Delays: "JM-guided strategy consistently outperforms both the HMM-guided strategy and buy-and-hold in reducing volatility and maximum drawdowns and enhancing risk-adjusted returns... improves annualized returns by approximately 1 % to 4 %... JMs' inherent persistence lends enhanced robustness against trading delays." (wide05: HMM bricht bei 5-Tage-Delay auf DAX/Nikkei ein, JM hält bis 2 Wochen.) https://arxiv.org/html/2402.05272v2 — **Confidence: Hoch (33-Jahres-Backtest mit Kosten)**.
- arXiv 2509.26029 / 2410.14841 / 2406.09578: "Nystrup et al. (2020) show through simulations that JMs are more robust than classical HMMs, particularly in challenging settings with limited data, imbalanced regimes, and high persistence"; HMMs erzeugen dort "state sequences that lack persistence and stability, leading to frequent false alarms." Sparse JM (SJM) gewichtet Features zusätzlich. — **Confidence: Hoch**.
- bscapitalmarkets.com (o.D.): λ als "time-scale selector: low values detect short-term fluctuations, high values reveal only major structural breaks". https://www.bscapitalmarkets.com/statistical-jump-models-for-regime-switching.html — **Confidence: Mittel (Praktiker-Blog)**.

---

## 3. XAUUSD-/Forex-spezifische Evidenz

**Claim (stärkster direkter Beleg):** 2-State GaussianHMM auf XAUUSD M1-Returns als Filter über Kalman-Mean-Reversion hebt PF von 1,34 auf 1,42 — aber ein simpler ATR-Median-Filter erreicht 1,31.
**Source:** rahulsp.com — "Kalman Filter and HMM Regime Detection for Gold Mean-Reversion"
**URL:** https://rahulsp.com/papers/kalman-hmm-gold
**Date:** o.D. (abgerufen in dieser Recherche) | **Confidence:** Mittel-Hoch (volle Methodik + Parameter + Limitationen transparent; kein Peer-Review; **HMM full-sample gefittet = In-Sample-Bias auf dem Filter**)

**Excerpt:** HMM-Spezifikation: 2 Zustände auf M1-Returns — "State 0 (Mean-Reverting): Low-volatility... State 1 (Trending): High-volatility regime with larger absolute returns and potential for sustained directional moves. In this state, deviations from the filtered price may represent genuine trend changes rather than temporary overshoots." Baum-Welch auf rollierendem Trainingsfenster, Viterbi-Dekodierung. Kosten: fixer Spread $0,20 RT, Cooldown 5 Bars; Grid SL∈{1,2,3,5}$, TP∈{0,1,2,3,5}$. Baseline-Ergebnis (SL=2/TP=3): 647 Trades, WR 53,8 %, PF 1,34, Sharpe 0,92. Vergleich: "Simple MA crossover mean-reversion: PF 1.18 (vs. 1.34 Kalman-only and 1.42 Kalman+HMM)... Volatility regime filter (rolling ATR): whether the 60-bar ATR is above or below its 240-bar median... produces PF 1.31 (vs. 1.42), suggesting that the HMM captures regime information beyond what a simple volatility threshold provides, but the marginal improvement is modest." Limitationen: "Single instrument... 2-state HMM... No walk-forward HMM retraining: The HMM is trained on the full dataset... would likely degrade performance." Zusätzlich: 3-State-Visualisierung auf XAUUSD M1 (Quiet n=18337 / Volatile n=1994 / Normal n=213 — starke Regime-Imbalance!).

**Weitere XAUUSD-/MT5-Implementierungen (Existenz-Beweise, keine verifizierten Track-Records):**
- GifariKemal/xaubot-ai (06.02.2026, Authority S): XAUUSD-MT5-Bot, **3-State-HMM klassifiziert trending/ranging/volatile**, XGBoost (37 Features), ATR-SL, Kelly-Sizing, Daily-Loss-Limit, "Modell wird automatisch neu trainiert wenn sich Marktbedingungen ändern". https://github.com/GifariKemal/xaubot-ai — Confidence: Niedrig-Mittel.
- Vinu-Kevin-Diesel/AI-Quant-Strategy-Lab (09.04.2026): XAUUSD-MT5-Framework, GaussianHMM via hmmlearn mit **Python→MQL5-Bridge per CSV-Datei** für Live-Regime-Klassifikation; lehrreiche Warnung: "Beast strategy had 6.7 % WR live (vs 38 % backtest) due to market regime change" → Kill-Switches gebaut. https://github.com/Vinu-Kevin-Diesel/AI-Quant-Strategy-Lab — Confidence: Niedrig-Mittel (aber technisches Integrations-Template!).
- 0x596173736972/MarketRegimeTrader (27.05.2025): HMM + Walk-Forward-Analyzer mit `train_months=12, test_months=3`, Transaktionskosten 0,001. https://github.com/0x596173736972/MarketRegimeTrader — Confidence: Mittel (Parameter-Template für WF-Design).
- NIFTY-50-Studie (internationalpubls.com, o.D.): HMM+Monte-Carlo-Regime-Strategie 2018–2024: Sharpe 1,05 vs. 0,67 B&H, MaxDD −17,5 % vs. −38,4 %; Limitationen: tägliche Daten, Kosten nur teilweise, Gaussian-Emissionen ohne Fat Tails. — Confidence: Mittel.

**Negativ-Befund:** Kein peer-reviewtes Paper mit verifiziertem Live-/OOS-Ergebnis eines HMM-Filters speziell auf XAUUSD-Spot unter Retail-Kosten gefunden. Kommerzielle "HMM-EAs" (ENEA MT5, AI Gold Scalp Pro — GroupBuy-Seiten) werben mit HMM-Regime-Switching, liefern aber keine auditierbaren Backtests (teils absurde Claims: "+377 %, WR 100 %"). — Confidence: Hoch (als Negativ-Befund).

---

## 4. Einfache Regime-Proxys vs. HMM (Robustheit bei begrenzter Datenlage)

**Claim:** ADX-Schwelle, ATR-Perzentil und SMA-Slope sind legitime, teils fast gleichwertige Alternativen — mit klar definierbaren, testbaren Regeln. HMM-Vorsprung auf XAUUSD ist empirisch **modest** (PF 1,42 vs. 1,31).
**Sources:**
- finquesta.com (20.08.2026): ADX als Regime-Filter "switches an entire strategy on or off"; **ADX-Schwelle selbst als Parameter testen, "not assuming 25 is correct just because Wilder used it"**; Warm-Up-Window-Warnung (Lookahead durch instabile Früh-ADX-Werte); Label-Leakage-Warnung: ML-Klassifikator auf ADX-abgeleitetem Label "memorised a single cutoff". https://finquesta.com/https-finquesta-com-trading/ — Confidence: Mittel-Hoch.
- traderspost.io (09.07.2026, Authority B): Konkrete Alert-Regeln — Breakout: "20-day high breakout + volume >1.5× 20-day avg; Regime filter: daily ADX(14) > 25"; Mean-Reversion invertiert: "disable long dip-buying entries when the 14-day ATR is above the 80th percentile of its trailing 252-day distribution". https://blog.traderspost.io/article/backtesting-market-regimes-for-2026-strategies — Confidence: Mittel-Hoch.
- orstac.com (18.10.2025): Für Mean-Reversion-Bots: "only allowing the bot to trade when the ADX is below a certain threshold (e.g., 25)... when ADX is high, pause or reduce position sizes drastically." — Confidence: Mittel.
- PineScriptForge GC-Gold ATR-Percentile-Breakout (20.12.2024): 1H/4H/Daily, Jan 2023–März 2026, mit $4,50 RT-Kommission + 1-Tick-Slippage: Entry wenn ATR < 10. Perzentil der letzten 100 Bars + Bruch des 5-Bar-High/Low; TP 2×ATR, Trail 1×ATR; Ergebnis: 418 Trades, **WR 52,2 %, PF 1,30, MaxDD 12,0 %**, Recovery 3,46; Hinweis: "Adding a volatility filter (e.g., ADX > 20) can reduce false signals... during high-volatility spikes (CPI, Fed) a pause-and-reassess approach". https://pinescriptforge.com/GC/atr-percentile-breakout/backtest — Confidence: Mittel (Vendor-Audit-Modell, aber voll parametriert mit Kosten).
- bigmovealgo.com (14.08.2026): Regime-Filter = Trend-Detektor (SMA50/200, EMA, MACD-Zero-Line) + Vol-Detektor (ATR); Trade-off benannt: "a 200-period SMA reacts slowly to regime shifts... stay active too long into a downturn". https://www.bigmovealgo.com/post/market-regime-filter — Confidence: Mittel.
- coinxsight.com (24.05.2026): Praxis-Regime-Tabelle: Low-Vol (ATR < 20er-Avg) → Range-Trade; Normal → Trend-Follow; High-Vol (ATR > 1,5× Avg) → **halbe Size, weite Stops, nur A+-Setups**. — Confidence: Niedrig-Mittel.

**Abgleich HMM vs. Proxy:** Der einzige direkte Head-to-Head-Vergleich auf XAUUSD (rahulsp) zeigt: ATR-Median-Filter 1,31 vs. HMM 1,42 — HMM gewinnt, aber der Proxy liefert ~70 % des Filter-Nutzens mit 2 statt ~20 Parametern. Bei begrenzter Datenlage (wenige Jahre H1-Bars, Regime-Imbalance wie im rahulsp-Plot: 213 vs. 18.337 Bars) ist das HMM-Instabilitätsrisiko (lokale Optima, Label-Switching, falsch-positive Alarme lt. Nystrup-Literatur) real. **Empfehlung: Proxy als Baseline-Arm im Walk-Forward, HMM nur deployen wenn OOS-Vorsprung > Rauschschwelle.**

---

## 5. Anwendung auf unsere Kandidaten (Trend-/Breakout-Bots, Prop-Firm-Kontext)

Evidenz-basierte Filter-Designs je Strategietyp:

| Strategietyp | Regime das schadet | Filter-Aktion (evidenzbasiert) |
|---|---|---|
| Trend-Pullback / MA-Cross | High-Vol (QuantStart: falsche "Trend"-Identifikation in Vol-Spikes) | Neue Entries in High-Vol-State blockieren; offene Positionen schließen dürfen (QuantStart-Pattern) [^1^] |
| Breakout (Donchian/ATR) | Chop/Low-Vol-Range (Whipsaws) + Extreme-Vol-Spikes (CPI/Fed-Gaps) [^14^] | Entries blockieren wenn Regime = Low-Vol-Range ODER Spike-Regime; alternativ ADX<20-25 als Proxy [^14^][^15^] |
| Mean-Reversion | Trending-High-Vol (Deviations werden permanent — rahulsp) | Nur im Mean-Reverting-State traden; ADX<25 als Proxy [^6^][^16^] |
| Alle (Sizing) | High-Vol | Risiko-Halbierung statt hartem Block (coinxsight: half size in ATR>1,5×Avg; Hackathon: 1,5 % → 1,0 % Risiko in Volatile-Regime) [^13^][^17^] |

Blockieren vs. Risiko-Halbierung: QuantStart und die meisten Quellen nutzen hartes Blockieren (0/1). Der QC-Sensitivitätstest (40/40 DD-Reduktion) legt nahe, dass die **DD-Wirkung robust gegenüber der exakten Blocking-Regel** ist — Risiko-Halbierung (0,5× Size in Grenzregime) ist die weichere Variante, die Trade-Count und damit statistische Validität erhält (QuantStart-Warnung: 41→31 Trades reduziert "positively expected bets").

**Prop-Firm-Fit:** Regime-Filter adressiert genau das EOD-/Daily-DD-Problem (kein Trading in Vol-Spike-Regimen = weniger Tail-Tage). Ergänzend bleibt ein **unabhängiger Daily-Loss-Kill-Switch** Pflicht (der Regime-Filter erkennt Regime mit Lag — HMM bricht bei abrupten Sprüngen erst nach einigen Bars aus; LSEG: GMM detektiert Crashes mit kleinerem Lag als Clustering; arXiv 2402.05272: HMM empfindlich gegen Delays).

---

## IMPLEMENTIERUNGS-SPEZIFIKATION

### A. Modell-Setup (Baseline)

```python
# Features (alle kausal, nur Daten <= t):
#   r1      = log(close_t / close_{t-1})                # Bar-Return (H1/H4)
#   rvol20  = rolling_std(r1, 20)                       # Realized Vol
#   natr14  = ATR(14) / close                           # normalisierte ATR
#   volz    = zscore(tick_volume, 200)   # optional; MT5-Tick-Volumen mit Vorsicht
# Skalierung: rolling z-score über TRAIN_WINDOW (kein globaler Scaler -> Lookahead!)

MODEL = GaussianHMM(
    n_components   = 2,              # Baseline; 3 als WF-Variante (trend/range/vol)
    covariance_type= "full",         # bei 2-3 Features ok; bei >4 Features "diag"
    n_iter         = 1000,
    tol            = 1e-4,
    min_covar      = 1e-3,           # Overfitting-Floor (hmmlearn-Default)
    random_state   = None            # -> 10 Restarts mit seeds 0..9
)
# Restart-Regel (hmmlearn-Doku): 10 Fits mit versch. Seeds, behalte bestes score(X)
```

### B. Regime-Benennung nach jedem Re-Fit (Label-Switching!)

```
states haben nach jedem Fit WILLKUERLICHE Nummern -> Remapping zwingend:
  var_k = diag(model.covars_)[k][return_feature_index]   # State-Varianz
  sorted_states = argsort(var_k)
  bei n=2:  low_var  = "CALM"   (erlaubt)
            high_var = "VOLATILE" (blockiert/Size halb)
  bei n=3:  zusaetzlich state_mean[r1] / sqrt(var) als Trend-Schaerfe nutzen:
            |mean|/sd hoch -> "TREND", low_var & |mean|/sd klein -> "RANGE/CHOP"
Sanity-Checks nach jedem Fit (sonst Fallback auf ADX/ATR-Proxy):
  - Convergence: model.monitor_.converged
  - Mindest-Occupancy jeder State > 2 % der Bars (sonst degeneriert)
  - Selbsttransitions-Wahrscheinlichkeit > 0.9 (Persistenz; sonst zu nervoes)
```

### C. Re-Fit- & Inferenz-Regeln (Lookahead-sicher)

```
TRAIN_WINDOW : expanding ab Start ODER rolling {504*2 .. 504*4} H4-Bars (~2-4 Jahre)
REFIT_EVERY  : 20 Handelstage (monatlich, Baseline) | WF-Variante: 5 Tage (woechentl.)
REFIT_ANCHOR : Wochenende/Marktschluss (vermeidet Intraday-Modellflattern)
INFERENCE (jede Bar t):
    X_hist = features[0 .. t]                 # NUR Vergangenheit
    post   = model.predict_proba(X_hist)[-1]  # Posterior des letzten Punkts
    p_bad  = post[state_id["VOLATILE"]]
HYSTERESE (gegen Flattern an der Grenze):
    if regime_active==False and p_bad > 0.60: regime_active = True   # blocken
    if regime_active==True  and p_bad < 0.40: regime_active = False  # freigeben
```

### D. Filter-Eingriff je Strategie (Pseudo-Regeln)

```
TREND/BREAKOUT-Bot:
    on_new_entry_signal:
        if regime_active:                    SKIP            # QuantStart-Blocking
        elif p_bad in (0.40, 0.60]:          risk *= 0.5     # Grauzone: halbe Size
        else:                                 risk *= 1.0
        # Breakout zusaetzlich: blockiere wenn 3-State-Modell "RANGE" sagt
    on_close_signal:                          IMMER erlaubt  # (QuantStart-Pattern)
    optional hart: bei Eintritt in VOLATILE offene Position schliessen
                 (quantifiedstrategies "stop-loss trigger"-Variante; testen!)

MEAN-REVERSION-Bot (falls vorhanden):
    invertiert: nur handeln wenn state in {CALM, RANGE}; VOLATILE+TREND blockiert

IMMER (unabhaengig vom Regime, Prop-Firm-Pflicht):
    daily_loss_kill_switch (z.B. -2.5 %/Tag), EOD-Flatten, News-Sperre um CPI/Fed/NFP
```

### E. Walk-Forward-Parameter-Räume (Grid für OOS-Tests)

| Parameter | Werte | Begründung |
|---|---|---|
| n_states | {2, 3} | BIC sagt 2; 3 nur mit Interpretierbarkeits-Gewinn [^8^][^9^] |
| Feature-Set | {r1}, {r1+rvol20}, {r1+rvol20+natr14} | Komplexität eskalieren; Volumen optional (MT5-Tick-Vol) [^13^] |
| Train-Window | {2 J, 3 J, 4 J, expanding} | QuantInsti 4 J; MarketRegimeTrader 12 M/3 M [^3^][^19^] |
| Re-Fit | {wöchentlich, monatlich} | QC weekly; LSEG retrain_step; QuantStart-Warnung [^1^][^2^][^4^] |
| Block-Schwelle p_bad | {0.5, 0.6, 0.7} + Hysterese {aus, 0.4/0.6} | Sensitivität (QC: 11/40-Problem) |
| Eingriff | {block, halbe Size} | Trade-Count vs. DD-Trade-off |
| **Ablations-Arme (Pflicht)** | (a) kein Filter, (b) ADX(14)>20 bzw. >25 (Trend-Bots), (c) ATR(14) < 80. Perzentil/252 (MR) bzw. ATR-Median-Regel (rahulsp: 60er-ATR vs. 240er-Median), (d) SMA200-Slope>0 | HMM muss diese Proxys OOS **signifikant** schlagen, sonst Proxy deployen [^6^][^14^][^15^] |

Mindestanforderungen an Validierung (aus wide05 übernommen): Purged/Embargoed Walk-Forward; Kosten realistisch (XAUUSD-Spread + Slippage); Trade-Count-Monitoring (QuantStart-Effekt 41→31); Sensitivitäts-Sweep ±15 % um gewählte Parameter; Entscheidungsregel: Filter wird nur übernommen, wenn MaxDD OOS um ≥20 % sinkt **und** PF nicht unter ~90 % des ungefilterten PF fällt.

### F. Bekannte Failure-Modes (Checkliste)

1. **Full-Sample-Fit = Lookahead** (rahulsp-Limitation!) — HMM niemals auf den Gesamtdaten fitten und dann "backtesten".
2. **Label-Switching nach Re-Fit** → State-Remapping via Varianz-Sortierung (Punkt B).
3. **Regime-Lag:** HMM erkennt Crash-Onset verzögert (arXiv 2402.05272: 5-Tage-Delay tötet HMM-Strategie auf DAX/Nikkei) → HMM ersetzt KEINEN Daily-Kill-Switch.
4. **Degenerierte Fits** (State-Occupancy ≈ 0) → Sanity-Checks + Proxy-Fallback.
5. **Regime-Imbalance auf Intraday-Daten** (rahulsp: 213 vs. 18.337 Bars) → 2-State-Baseline, ggf. Jump-Model (jump-Penalty λ) als robuster Alternative evaluieren (github: Nystrup-Implementierungen / `jumpmodels`-Paket).
6. **Zu wenige Trades** → PF-Ziel PF>1,5 OOS gefährdet durch reduzierte Stichprobe; lieber halbe Size als harter Block, wenn Trade-Count kritisch wird.

---

### Quellen

[^1^]: QuantStart — "Market Regime Detection using Hidden Markov Models in QSTrader", o.D. (Serie ~2016/17). https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/
[^2^]: LSEG Developers — "Market regime detection using Statistical and ML based approaches", 13.02.2023. https://developers.lseg.com/en/article-catalog/article/market-regime-detection
[^3^]: QuantInsti Blog — "Market Regime using Hidden Markov Model", 07.08.2025. https://blog.quantinsti.com/regime-adaptive-trading-python/
[^4^]: QuantConnect Forum/Research — "Drawdown Regime Gold Hedge: Using HMM to Rotate Between SPY and GLD – 20-Year Backtest Results", 12.03.2026 / Research 18811, 28.03.2025. https://www.quantconnect.com/forum/discussion/20417/ ; https://www.quantconnect.com/research/18811/
[^5^]: arXiv 2402.05272 — "Downside Risk Reduction Using Regime-Switching Signals" (Shu, Nystrup et al.), v2 10.07.2024. https://arxiv.org/html/2402.05272v2
[^6^]: rahulsp.com — "Kalman Filter and HMM Regime Detection for Gold Mean-Reversion" (XAUUSD M1), o.D. https://rahulsp.com/papers/kalman-hmm-gold
[^7^]: The MI Journal 6/2020 — HMM-Regime-Risk-Manager-Nachbau (QuantStart-Replikation), Jan–Dez 2020. https://www.themijournal.com/admin1/upload/04 Lavaneesh Sharma 49528.pdf
[^8^]: EconStor / Risks 7(2):66 — HMM-Kalibrierung auf FX-Paaren, BIC→2 Zustände, o.D. https://www.econstor.eu/bitstream/10419/257904/1/risks-07-00066-v2.pdf
[^9^]: City University London Thesis (Ibáñez, 2025) — AIC M=3 vs. BIC M=2 auf Faktor-Daten 1963–2024. https://openaccess.city.ac.uk/id/eprint/36507/
[^10^]: Farzulla 2025 (ASRI) — HMM-Modellselektion 2/3/4 Zustände, 10 Restarts, tol 1e-4, n_iter 1000. https://farzulla.org/papers/Farzulla_2025_ASRI.pdf
[^11^]: arXiv 2410.14841 / 2406.09578 / 2509.26029 — Sparse Jump Models / JM vs. HMM Robustheit (Nystrup et al. 2020/2021). https://arxiv.org/html/2410.14841v1 ; https://arxiv.org/html/2406.09578v1
[^12^]: Economic Studies (Bulgarian Academy of Sciences) 2023-1 — HMM-Selektion auf 24 europäischen Indizes, 2–3 Zustände, Persistenz <2 % Wechselwahrscheinlichkeit. https://www.iki.bas.bg/Journals/EconomicStudies/2023/2023-1/22-01_bodytext.pdf
[^13^]: GitHub Jaival111/Algo-Trading-Hackathon — TECHNICAL_SPECIFICATION (Features [returns, ATR_norm], 3 Regime nach Varianz sortiert, regime-abhängiges Risiko 1,5/1,2/1,0 %), 2024. https://github.com/Jaival111/Algo-Trading-Hackathon/blob/main/TECHNICAL_SPECIFICATION.md
[^14^]: PineScriptForge — "GC ATR Percentile Breakout Backtest" (Gold, 1H, 2023–2026, mit Kosten: WR 52,2 %, PF 1,30, MaxDD 12 %), 20.12.2024. https://pinescriptforge.com/GC/atr-percentile-breakout/backtest
[^15^]: TradersPost Blog — "Backtesting Market Regimes for 2026 Strategies" (ADX(14)>25-Filter; ATR 80.-Perzentil-Block), 09.07.2026. https://blog.traderspost.io/article/backtesting-market-regimes-for-2026-strategies
[^16^]: Orstac — "Plan A Bot Review" (ADX<25 für Mean-Reversion-Bots; Pausieren bei Trend), 18.10.2025. https://orstac.com/plan-a-bot-review-for-deeper-insights-3/
[^17^]: CoinXSight — "ATR & Volatility Trading" (ATR-Regime-Tabelle: High-Vol → halbe Size), 24.05.2026. https://coinxsight.com/blog/indicators/atr-volatility-trading
[^18^]: finquesta — "ADX as Regime Filter" (Schwelle als Parameter testen; Warm-Up-/Label-Leakage-Warnungen), 20.08.2026. https://finquesta.com/https-finquesta-com-trading/
[^19^]: GitHub 0x596173736972/MarketRegimeTrader — Walk-Forward train_months=12/test_months=3, 27.05.2025. https://github.com/0x596173736972/MarketRegimeTrader
[^20^]: GitHub GifariKemal/xaubot-ai — XAUUSD-MT5-Bot mit 3-State-HMM (trending/ranging/volatile), 06.02.2026. https://github.com/GifariKemal/xaubot-ai
[^21^]: GitHub Vinu-Kevin-Diesel/AI-Quant-Strategy-Lab — XAUUSD GaussianHMM + Python→MQL5-CSV-Bridge; Live-vs-Backtest-Regime-Warnung, 09.04.2026. https://github.com/Vinu-Kevin-Diesel/AI-Quant-Strategy-Lab
[^22^]: hmmlearn offizielle Doku — Tutorial (EM lokale Optima/Restarts), API (covariance_type, min_covar), AIC/BIC-Model-Selection-Example. https://hmmlearn.readthedocs.io/en/stable/auto_examples/plot_gaussian_model_selection.html
[^23^]: GitHub HamidAbbasi-R/ML-Toolbox-Finance — HMM-Feature-Empfehlungen (log ret/vol/volume/ATR; Separierbarkeits-Kriterium), 22.11.2024. https://github.com/HamidAbbasi-R/ML-Toolbox-Finance
[^24^]: GitHub saiemula/Market-Regime-Detection-System — Rolling-252d-Z-Score-Features, 3-State GaussianHMM, 02.04.2026. https://github.com/saiemula/Market-Regime-Detection-System
[^25^]: QuantifiedStrategies — "Hidden Markov Model Market Regimes", 01.02.2026. https://www.quantifiedstrategies.com/hidden-markov-model-market-regimes-how-hmm-detects-market-regimes-in-trading-strategies/
[^26^]: bigmovealgo — "Market Regime Filter: SMA+ATR Method", 14.08.2026. https://www.bigmovealgo.com/post/market-regime-filter
[^27^]: bscapitalmarkets — "Statistical Jump Models for Regime Switching" (λ als Zeitskalen-Selektor), o.D. https://www.bscapitalmarkets.com/statistical-jump-models-for-regime-switching.html
[^28^]: International Publications (CANA) — HMM+Monte-Carlo Regime-Strategie NIFTY 50, 2018–2024 (Sharpe 1,05 vs. 0,67; MaxDD −17,5 % vs. −38,4 %), o.D. https://internationalpubls.com/index.php/cana/article/download/6029/3393/10743
