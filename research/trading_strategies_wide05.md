# Facet: KI/ML-Strategien

Recherche-Facet: KI-/ML-basierte Trading-Strategien (TSFMs, klassisches ML, Deep Learning, Regime-Detection, LLM-Signale, RL).
Methodik: 15 unabhängige Websuchen (EN/DE), Deep-Dives in arXiv-Papers, Practitioner-Blogs, GitHub-Repos mit dokumentierten Backtests. Stand der Recherche: siehe Quellen-Datumsangaben unten.

## Key Findings

### 1. Time-Series-Foundation-Models (Chronos, TimesFM, TTM, Moirai, Kronos)

**Befund: Zero-Shot-TSFMs sind KEIN eigenständiges Entry-Signal; ihr Wert liegt in Fine-Tuning, Vol-Prognose und als Feature/Kovariate.**

- arXiv 2507.07296 (TTM vs. Chronos-Bolt auf 3 Finanz-Tasks: US-10Y-Yield-Changes, EUR/USD-Realized-Vol, Equity-Spread): TTM mit Fine-Tuning 25–50 % besser als identisches untrainiertes Modell bei wenig Daten, 15–30 % besser bei langen Datensätzen; Zero-Shot schlug TTM naive Benchmarks bei Volatilitäts- und Spread-Prognose. ABER: traditionelle spezialisierte Modelle erreichten oder übertrafen TTM in 2 von 3 Tasks — "TSFMs priorisieren Breite vor Task-Optimierung". Pretrained TTM brauchte 3–10 Jahre weniger Daten für gleiche Performance (Sample-Effizienz). [^1^]
- "Trading with the Devil" (arXiv 2510.17165, HF-Daten US-Equities + Binance-Crypto, TimesFM/Chronos/Moirai/Timer/TTM vs. LSTM/GRU/MLP-Baselines): Korrelation zwischen Modell-"Surprise" und Folgerenditen zerfällt innerhalb weniger Ticks/Sekunden gegen null oder negativ — Informationsvorteil wird sofort arbitriert. Größere Chronos-Varianten (8M→710M) verbessern Risiko-Rendite-Profil, aber Latenz-Trade-off. Rolling-Analyse einer TimesFM-Strategie 2023–2025 zeigt stetigen **Alpha-Decay** (beobachteter und theoretischer Sharpe sinken parallel). [^2^]
- Papers With Backtest (TSFM-Praxisleitfaden): Empfehlung = domain-adaptiertes Fine-Tuning statt Zero-Shot; Forecast nur als ein Signal unter vielen. Warnung: Mehrere Studien fanden, dass TSFM-Evaluations versehentlich Pretraining-Daten enthielten — gemeldete Accuracy um **47–184 % überhöht** (Data Leakage in Benchmarks). TTM (~1M Params) und Lag-Llama (~10M) als CPU-freundliche Alternativen zu Chronos-Large (710M, GPU nötig). [^3^]
- Jonathan Kinlay zu Kronos (OHLCV-Foundation-Model): Bear-Case klar formuliert — 5 % besseres MSE kann Information Coefficient von 0,01 bedeuten, "worthless after bid-ask spreads". Pretraining lernt Volatilitäts-Clustering (Risiko-Charakteristik), nicht Conditional-Mean-Predictability (Alpha). Größter praktischer Wert: **synthetische Daten für Backtest-Stress-Tests**, nicht Signalquelle. [^4^]
- PickMyTrade Advanced Guide (Practitioner-Referenz): Policy-Empfehlung — Apache-2.0/MIT-Modelle (TTM/PatchTSMixer, Chronos, TimesFM, Moirai, MOMENT, Lag-Llama) als Volatilitäts-/Kovariaten-Input in eine deterministische Sizing-Schicht verwenden, **nie als alleiniges Entry-Signal**; iTransformer (from scratch trainiert) schlug alle Foundation Models auf META — Pretraining ist kein universeller Vorteil auf Finanzdaten. TTM sub-5M Params = trivial auf CPU lauffähig. [^5^]
- Existierender MT5-Integrations-Beweis: GitHub-Repo "scalping_mt5-with-Amazon-Chronos" — Forex-Scalping-Bot, Chronos via Python + MT5, mit Multi-Timeframe-Gates (Session-Filter, Spread-Filter ≤25 % des TP, ADX-Regime-Filter M15 ADX<22 blockt, HTF-EMA-Bias-Filter), Daily-Kill-Switch 3 %, optionalem Fine-Tuning auf eigener Trade-Historie. Zeigt: technisch machbar auf Consumer-Hardware; kein verifizierter Live-Track-Record. [^6^]

### 2. Klassisches ML (XGBoost/RF) für Richtungsklassifikation

**Befund: Positivste evidenzbasierte Spur — aber fast alle "Erfolge" sind Aktien-Cross-Section, nicht Forex/Gold-Einzelinstrument. Auf XAUUSD/Forex nur schwache, ehrliche Ergebnisse.**

- OW-XGBoost (PMC-Studie, chinesische Aktien, CSI-300): monatliches Rebalancing: annualisierte Rendite 61 %, **Sharpe 3,11**, MaxDD 5,9 % vs. Index-Sharpe 0,14. SVM-Baseline 33,6 % ann. ABER: Aktien-Selektion (Cross-Section), nicht Direction-Timing; Performance fällt mit längerem Trainingsset (Feature-Decay). [^7^]
- XGBoost NEPSE (arXiv 2601.08896): methodisch sauberes Walk-Forward-Beispiel — Optuna-Tuning nur auf Trainingssegment, Expanding-Window mit 20 Lags, Richtungs-Accuracy 65,15 % OOS, schlug ARIMA/Ridge. Gut als Methodik-Template für Forex. [^8^]
- Ehrlichstes XAUUSD-Beispiel: GitHub SR_Mapping_NN — XGBoost als **Entry-Filter** für einen MT5-Gold-EA (nicht als Signal-Generator): AUC nur 0,538, Recall 6,8 %, explizite Limitationen (GC=F statt XAUUSD-Spot, geschätzter Spread, 14 Monate Daten, Pflicht zu Walk-Forward, periodischem Retraining alle 1–3 Monate, Demo-Phase). Hohe Thresholds → gute Precision bei wenigen Trades. Genau das "ML-as-Filter"-Muster, das funktionieren kann. [^9^]
- Sektor-Rotation TSX-60 (MDPI JRFM 2026, 2000–2025 mit OOS-Split): ML nur für Meta-Aufgaben (Vol-Regime 72,7 % Accuracy, Strategie-Typ 72,7 %) — Beleg für den Trend: ML auf "welches Regime/welche Strategie" statt "welche Richtung". [^10^]

### 3. LSTM/Deep Learning auf XAUUSD/Forex

**Befund: Hohe Accuracy-Claims in Papers (95–98 %) sind fast immer Regression-Metrik-Artefakte (Next-Price ≈ Last-Price). Kein belastbarer Live-Nachweis gefunden.**

- "Achilles" XAUUSD-LSTM (arXiv 2410.21291): Nur 9.544 Parameter, Paper-Account +162 % in einem Monat — Autoren selbst betonen Inkonsistenz ("can lose almost all the balance in a short term period"), keine Kosten, Paper-Trading, nur XAUUSD getestet. Typisches Beispiel für nicht-replizierbare Einzelmonats-Ergebnisse. [^11^]
- CNN vs. LSTM auf XAU/USD 1-Minuten-Daten (ScitePress, Anglia Ruskin Univ.): CNN schlug LSTM auf MSE/MAE/MAPE für Next-Minute-Preis — aber nur Punkt-Prognose-Metriken, kein Trading-Backtest mit Kosten. [^12^]
- Survey (arXiv 2103.09750) und EUR/USD-LLM-Fusion (arXiv 2408.13214): LSTM-Bagging/Hybrid-GRU-LSTM zeigen "verbesserte Profitabilität", aber: univariat, keine breiten Markttests, Schwierigkeiten bei abrupten Bewegungen. Kein PF/Sharpe-Nachweis, der Retail-Kosten übersteht. [^13^][^14^]
- Praktiker-Warnsignale (TradeAlgo ML-Backtesting-Guide): Backtest-Sharpe >3, Win-Rate >70 % bei Direction-Strategien, oder 10M Parameter auf 2.500 Tagesbars = "Definition von Overfitting". [^15^]

### 4. Regime-Detection (HMM/Clustering) — stärkste evidenzbasierte ML-Anwendung

**Befund: Konsistentester positiver Befund über alle ML-Ansätze: Regime-Filter reduzieren Drawdown deutlich und verbessern risikoadjustierte Renditen — Rendite-Verbesserung bescheidener. Ideal als Overlay für klassische Entry-Regeln.**

- arXiv 2402.05272 (HMM vs. Jump-Model, S&P500/DAX/Nikkei, 1990–2023, 10 bps Kosten, online-inferierte Regimes): Regime-basierte 0/1-Strategien senken Downside; Jump-Modelle robuster gegen Trading-Delays als HMM (HMM unterperformt bei 5-Tage-Delay auf DAX/Nikkei, JM hält Sharpe auch bei 2 Wochen Delay). [^16^]
- AIMS Press 2025 (Ensemble-HMM-Voting, XGBoost+HMM, S&P500/Russell-3000-ETFs 2020–2025): Voting-Klassifikator (Boosting–HMM) überlegen bei Sharpe/Sortino, MaxDD und Volatilität bei deutlich weniger Trades (18–22 statt 67) — publizierte, peer-reviewte Belege für den Hybrid ML-Regime-Filter. [^17^]
- QuantConnect GLD/SPY-HMM (2019–2024 LEAN-Backtest): Sharpe 0,823 vs. 0,646 B&H, CAGR 19,8 % vs. 17,2 %, MaxDD 27,1 % vs. 33,7 %; Sensitivitätstest: nur 11/40 Parameter-Kombis schlugen Benchmark-Sharpe, aber 40/40 reduzierten Drawdown. [^18^]
- QuantStart HMM-Regime-Filter (OOS, Trend-Following + HMM-Risikomanager): MaxDD von ~56 % auf ~24 % halbiert, Sharpe nur 0,48 — ehrliches Beispiel: Drawdown-Reduktion ja, Rendite-Boost nein; Trade-Zahl sinkt (statistische Validität leidet). [^19^]
- GitHub ItsSawhill/market-regime-detection (Multi-Asset, Walk-Forward-Retraining): HMM-Regime-Allokation ~12,6 % p.a., bester Sharpe, MaxDD ~-18 % vs. B&H -36 %; KMeans schwächer als HMM; Limitation: KEINE Transaktionskosten. [^20^]
- QuantInsti-Tutorial: HMM-regime-adaptive Strategie Sharpe 1,76 vs. 1,16 B&H, Vol 26 % vs. 43 %, MaxDD -20 % vs. -28 % (Tutorial-Niveau, kein Peer-Review). [^21^]

### 5. LLM-gestützte Signale (Sentiment, LLM-generierte Strategien)

**Befund: Größte Diskrepanz zwischen Paper-Claims und Replikation. Sentiment-LLM-Papiere zeigen Sharpe 3+, unabhängige Replikationen scheitern. LLM-generierte Strategien: fast komplett wertlos.**

- Germano (arXiv 2412.19245, UCL/LSE; OpenReview-Version): OPT-basiertes News-Sentiment auf 965.375 US-Artikeln 2010–2023, 74,4 % Accuracy, Long-Short mit 10 bps Kosten: **Sharpe 3,05**, +355 % Aug 2021–Jul 2023 (BERT 2,11, FinBERT 2,07, Loughran-McDonald 1,23). [^22^][^23^]
- KONTRAST — unabhängiger Replikationsversuch (GitHub bloomberg-sentiment-finbert, 30 S&P-100-Aktien, 2018–2026, IC-Analyse + L/S-Quintil-Backtest mit 5 bps): 1-Tages-IC = +0,004 (t=0,76, verworfen), 21-Tage-IC schwach +0,015, FF3-Alpha +10,7 %/Jahr aber t=1,01 (nicht signifikant), FinBERT repliziert Bloomberg-Sentiment NICHT (Spearman -0,26). Non-monotones Muster: moderat-positives Quintil schlägt extrem-positives. [^24^]
- Hybrid FinBERT+Technik+Regime (arXiv 2601.19504): Hybrides System (SMA/RSI-Baseline + FinBERT-Sentiment-Filter + Regime-Detection + adaptives Sizing) schlug Baseline um +126 % Total Return, **Sharpe 1,68**, MaxDD-Reduktion ~28 % — Sentiment als *Filter* (kein Entry bei bärischer News-Lage), nicht als Signal. [^25^]
- LLM-generierte Strategien (arXiv-Preprint Aug 2026 via algotrader.ch): 4 LLMs schrieben 40 Strategien, 8 ETFs, 2023–2024: nur **2 von 40** schlugen Buy-and-Hold; 32 sagten ihren eigenen Erfolg voraus — 1 davon lieferte. Ein simpler 50/200-MA-Crossover schlug den durchschnittlichen Sharpe aller LLM-Strategien. Absichtlich eingebauter Lookahead-Bias wurde vom automatischen Detektor nie erkannt. [^26^]
- End-to-End-LLM-Trading-System (arXiv 2502.01574, FinGPT + SMA/RSI/Stochastik): Sentiment-Integration hob Sharpe teils massiv (TSLA SMA-Cross 0,34→3,47) — aber nur 2022–2023, 3 Ticker, kein Peer-Review; als Signal fürs Kombinieren, nicht als Beweis. [^27^]

### 6. Reinforcement Learning

**Befund: Kein belastbarer Retail-tauglicher Nachweis. Durchgehende methodische Mängel in öffentlichen Implementierungen.**

- Öffentliche RL-Trading-Repos zeigen systematisch dieselben Lücken: DQN "trainiert während der Evaluation" (also nicht OOS), keine Transaktionskosten/Market-Impact, keine Risiko-Kontrollen, Single-Instrument/Single-Window (Beispiel: lob_mm_eval, CME WTI, 2 Wochen). [^28^]
- Vergleichsstudie DQN/PPO vs. Momentum/Mean-Reversion (JDAMR, Hou): Fokus liegt notgedrungen auf der Pipeline (Backtester, Slippage-Modell) — kein publizierter Netto-Alpha-Beleg. [^29^]
- Fazit für Prop-Firm-Kontext: RL ist der am wenigsten validierte Ansatz; Rechenaufwand hoch, Reproduzierbarkeit schlecht. Nicht für Top-5 empfohlen, höchstens als Meta-Layer (Sizing) in weiterer Zukunft.

### 7. Meta-Befund: Warum ML-Trading-Backtests systematisch überschätzen

- daru.finance-Replikation von López de Prado auf ~92.500 reale Strategien (50k Crypto, 22,5k US-Equity, 20k Forex, voll vercostet): Die jeweils beste Strategie jeder Asset-Klasse liegt UNTER der False-Strategy-Theorem-Null (Crypto: bester Sharpe 2,00 vs. erwartetes Maximum aus Rauschen 2,72; Deflated Sharpe 0,029 vs. Schwelle 0,95; 50.000 nominelle Trials = nur 434 effektive unabhängige Wetten). [^30^]
- Bailey/López-de-Prado-Kernreferenzen: Deflated Sharpe Ratio (JPM 2014), Probability of Backtest Overfitting/CSCV (JCF 2015/2017), Purged/Embargoed K-Fold, Triple-Barrier-Labeling, Meta-Labeling (AFML 2018); Beispiel: in-sample Sharpe 1,04 → OOS 0,07. Tools: backtest-audit, backtest-guard, afml-Repos. [^31^][^32^][^33^]
- Algotrader.ch (AI-Washing-Analyse, CFA-Institute-Framework 2025, SEC-Fälle Delphia/Global Predictions $400k, Two Sigma $255M): Vier Mechanismen, die Backtest→Live killen: Turnover-Kosten, überzeichnete Kapazität, Regime-Abhängigkeit, Crowding. Live-Beleg: Amplify AI Powered Equity ETF (ML-Aktienfonds seit 2017) hinter S&P-500-Tracker in 2024, 2025 und 2026; 4,55 %/Jahr 5-Jahres-Rendite bei 0,75 % Gebühr. Akademische Basis: Gu/Kelly/Xiu (RFS 2020) — ML hilft bei US-Aktien-Cross-Section (NN + Trees); Israel/Kelly/Moskowitz (JIM 2020) — aber begrenzt durch niedriges Signal-Rausch-Verhältnis, Regimewechsel, Kapazität. [^34^]

## Major Players & Sources

| Quelle | Typ | Relevanz |
|---|---|---|
| arXiv 2507.07296 (TTM vs. Chronos, Financial TSFM) | Peer-orientiertes Preprint | Zentrale TSFM-Evidenz; bestätigt Landscape-Scan |
| arXiv 2510.17165 "Trading with the Devil" | Konferenz-Paper (KDD-WS) | FM-Alpha-Decay, Risiko-Dekomposition, HF-Daten |
| arXiv 2402.05272 (HMM/JM Regime-Switching) | Preprint mit 33-Jahres-Backtest | Stärkste Regime-Evidenz mit Kosten |
| AIMS Press (2025) XGBoost+HMM-Voting | Peer-reviewed | Publizierte Hybrid-Ergebnisse 2020–2025 |
| Bailey & López de Prado (DSR, PBO, AFML) | Methoden-Literatur | Pflicht-Toolkit für jede ML-Strategie-Validierung |
| QuantConnect/QuantStart/QuantInsti | Practitioner-Backtests | Replizierbare Regime-Filter-Implementierungen |
| GitHub: SR_Mapping_NN, scalping_mt5-with-Amazon-Chronos, market-regime-detection | Code + ehrliche Limitationen | MT5-/XAUUSD-Integrations-Templates |
| Amazon (Chronos), Google (TimesFM), IBM (TTM/Granite), Salesforce (Moirai), NX-AI (TiRex), Kronos | Modelle | Alle via HuggingFace, Apache-2.0 (außer Moirai CC-BY-NC) |
| algotrader.ch, daru.finance, Kinlay, Papers With Backtest | Unabhängige Kritik/Replikation | Gegengewicht zu Paper-Hype |

## Trends & Signals

1. **Vom Signal zum Filter**: Der robusteste Trend — ML wird nicht als Entry-Generator, sondern als Regime-Detektor/Vol-Prognose/Sentiment-Filter über klassische Entry-Regeln gelegt (XGBoost-Entry-Filter für XAUUSD-EA, HMM-Overlay, FinBERT-Blocker, MDPI-Sektor-Rotation mit ML-Meta-Modellen).
2. **TSFM-Reifegrad steigt, Alpha-Beweis fehlt**: TTM-R2 (1M Params, CPU-tauglich, Apache-2.0) ist die praktikabelste Option; Zero-Shot schlägt naive Benchmarks nur bei Vol/Spreads, nicht bei Richtung. Feintuning auf eigene Asset-Daten ist Pflicht.
3. **Alpha-Decay wird messbar**: Foundation-Model-Signale zeigen dokumentierten Decay (TimesFM-Studie 2023–2025) — periodisches Retraining (1–3 Monate) ist Konsens.
4. **Validierungs-Infrastruktur industrialisiert sich**: DSR/PBO/CPCV/Purged-KFold als Standard-Checks (backtest-audit, backtest-guard, TraderPeak macht CPCV+DSR+Monte-Carlo zum Default) — für Prop-Firm-Tauglichkeit unverzichtbar.
5. **Synthetische Daten als legitimer TSFM-Use-Case**: Kronos-Style K-Line-Generierung für Backtest-Stress-Tests statt Live-Signalen.
6. **Consumer-Hardware ist kein Blocker für den empfohlenen Stack**: XGBoost/HMM/TTM/Lag-Llama laufen CPU-only; nur Chronos-Large/Moirai-Large brauchen GPU.

## Controversies & Conflicting Claims

1. **LLM-Sentiment Sharpe 3,05 (Germano/UCL) vs. Replikation IC≈0 (bloomberg-sentiment-finbert)**: Die stärkste dokumentierte Widerspruchslinie. Mögliche Erklärungen: US-Gesamtmarkt vs. 30 Titel, Long-Short-Breite vs. Quintile, Pretraining-Leakage (OPT kennt Zeitraum bis ~2021 nicht, aber Trainingscorpus-Überlappung nicht prüfbar). → Sentiment nur als Filter, nie als Kernsignal.
2. **"LLMs finden Alpha in Zufallsreihen" (arXiv 2412.09394, Chronos-Tiny L/S-Portfolio schlägt STR/Trend) vs. "Chronos schlägt naive Benchmarks nicht konsistent" (arXiv 2507.07296) und "TSFM-Benchmarks um 47–184 % durch Leakage überhöht" (Papers With Backtest)**. → Chronos-Positive-Claims mit extremer Vorsicht; der Landscape-Scan-Befund wird durch Mehrheits-Evidenz gestützt.
3. **XGBoost Sharpe 3,11 (CSI-300-Selektion) vs. AUC 0,538 (XAUUSD-Direction)**: Cross-sektionales Ranking (viele Aktien) funktioniert nachweislich besser als Einzelinstrument-Timing (Gold/Forex) — für MT5-Bots heißt das: ML-Edge ist auf XAUUSD/NAS100 deutlich dünner als Aktien-Paper suggerieren.
4. **LSTM "+162 % in einem Monat" (Achilles) vs. Praktiker-Regel "Win-Rate >70 %/Sharpe >3 = Overfitting"**: Einzelmonats-Paper-Accounts ohne Kosten sind kein Beleg; Autoren selbst warnen vor Inkonsistenz.
5. **HMM: Rendite-Verbesserung oder nur Drawdown-Reduktion?** QuantConnect/Tutorial-Quellen zeigen Sharpe-Gewinne, QuantStart zeigt Sharpe 0,48 (kaum Besserung) bei massiver DD-Reduktion, AIMS zeigt Überlegenheit bei weniger Trades. Konsens: DD-Reduktion robust, Return-Boost fragil und parameter-sensitiv (nur 11/40 Parametern schlagen Benchmark).
6. **KI-Fonds-Realität vs. Marketing**: Einziger ML-Fonds mit 9-Jahres-Live-Record (AIEQ) liegt 3 Jahre hinter dem Index; SEC/CFA verfolgen AI-Washing. Widerspricht jeder "AI-Trading funktioniert erwiesenermaßen"-Behauptung auf Retail-Ebene.

## Recommended Deep-Dive Areas

1. **HMM/Jump-Model-Regime-Overlay für XAUUSD+H1/H4** (höchste Priorität): arXiv 2402.05272 + AIMS-Voting-Framework auf Gold adaptieren; Output = Filter für klassische Entries (Trend-Pullback etc.). Erwartbarer Nutzen: DD-Reduktion → Prop-Firm-Konformität (Daily-Loss-Limits).
2. **TTM-R2 Fine-Tuning auf XAUUSD/NAS100 Volatilität** (statt Richtung): EUR/USD-Vol-Task aus arXiv 2507.07296 als Template; Vol-Prognose → Sizing/SL-TP-Abstände; CPU-tauglich; direkter Fit zu 0,5 %-Risiko/Trade-Constraint.
3. **XGBoost-Meta-Labeling (López de Prado)**: Primärmodell = klassische Entry-Regel, XGBoost entscheidet nur Trade ja/nein + Size; SR_Mapping_NN-Repo als XAUUSD-Vorlage, mit Purged K-Fold + Embargo + DSR/PBO-Audit.
4. **Validierungs-Pipeline zuerst bauen**: CPCV, DSR, PBO, Walk-Forward mit Purge/Embargo, Monte-Carlo-Permutation — bevor irgendein ML-Modell getestet wird (daru.finance-Befund: selbst bester von 92.500 Strategien ist Null-Hypothese-kompatibel).
5. **LLM-Sentiment als News-Blocker**: Qwen3/FinBERT lokal, nur als Filter um Entries vor/während hochimpactiger News zu unterbinden (billig, geringes Risiko, kein Alpha-Anspruch). Kein Deep-Dive in LLM-Direction-Strategien empfohlen.
6. **Nicht weiter verfolgen**: RL-Trading (kein belastbarer Nachweis, hoher Aufwand), Chronos-Zero-Shot-Direction-Signale (widersprüchlich/negativ belegt), LSTM-Preisprognose als Entry (Accuracy-Artefakte).

---

### Quellen

[^1^]: arXiv 2507.07296 — "Time Series Foundation Models for Multivariate Financial Time Series Forecasting", 09.07.2025. https://arxiv.org/html/2507.07296v1
[^2^]: arXiv 2510.17165 — "Trading with the Devil: Risk and Return in Foundation Model Strategies", 2025. https://arxiv.org/html/2510.17165v1
[^3^]: Papers With Backtest — "Time Series Foundation Models Explained", o.D. (abgerufen im Rahmen der Recherche). https://paperswithbacktest.com/course/time-series-foundation-models
[^4^]: Jonathan Kinlay — "Time Series Foundation Models for Financial Markets: Kronos…", 22.02.2026. https://jonathankinlay.com/2026/02/time-series-foundation-models-for-financial-markets-kronos-and-the-rise-of-pre-trained-market-models/
[^5^]: PickMyTrade — "Advanced AI Trading Guide", 03.07.2026. https://pickmytrade.io/ai-ml/advanced-guide
[^6^]: GitHub — antonykim1/scalping_mt5-with-Amazon-Chronos, 25.02.2026. https://github.com/antonykim1/scalping_mt5-with-Amazon-Chronos
[^7^]: PMC10936758 — "Predicting Chinese stock market using XGBoost…" (OW-XGBoost), 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC10936758/
[^8^]: arXiv 2601.08896 — "XGBoost Forecasting of NEPSE Index Log Returns with Walk Forward Validation", 13.01.2026. https://arxiv.org/html/2601.08896v1
[^9^]: GitHub — Mrizalfahlepi/SR_Mapping_NN (XGBoost Entry-Filter XAUUSD MT5), 06.03.2026. https://github.com/Mrizalfahlepi/SR_Mapping_NN
[^10^]: MDPI JRFM 19(1):70 — "Sector Rotation Strategies in the TSX 60…", 15.01.2026. https://www.mdpi.com/1911-8074/19/1/70
[^11^]: arXiv 2410.21291 — "Achilles, Neural Network to Predict the Gold Vs US Dollar", 2024. https://arxiv.org/pdf/2410.21291
[^12^]: ScitePress — "Using Neural Network Architectures for Intraday Trading in the Gold Market", 2023. https://www.scitepress.org/Papers/2023/117944/117944.pdf
[^13^]: arXiv 2103.09750 — "A Survey of Forex and Stock Price Prediction Using Deep Learning", 2021. https://arxiv.org/pdf/2103.09750
[^14^]: arXiv 2408.13214 — "EUR/USD Exchange Rate Forecasting…LLMs and Deep Learning", 23.08.2024. https://arxiv.org/html/2408.13214v1
[^15^]: TradeAlgo — "Machine Learning Backtesting Guide", 23.02.2026. https://www.tradealgo.com/trading-guides/ai-trading/machine-learning-backtesting-guide
[^16^]: arXiv 2402.05272 — "Downside Risk Reduction Using Regime-Switching Signals", 10.07.2024. https://arxiv.org/html/2402.05272v2
[^17^]: AIMS Press — "A forest of opinions: A multi-model ensemble-HMM voting framework…", 29.03.2025. https://www.aimspress.com/article/id/69045d2fba35de34708adb5d
[^18^]: QuantConnect Research — "Optimizing a Gold-SPY Portfolio Using HMMs for Market Downtime", 28.03.2025. https://www.quantconnect.com/research/18811/
[^19^]: QuantStart — "Market Regime Detection using HMM in QSTrader", o.D. https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/
[^20^]: GitHub — ItsSawhill/market-regime-detection, 07.04.2026. https://github.com/ItsSawhill/market-regime-detection
[^21^]: QuantInsti Blog — "Market Regime using Hidden Markov Model", 28.08.2026. https://blog.quantinsti.com/regime-adaptive-trading-python/
[^22^]: arXiv 2412.19245 — Germano, "Sentiment trading with large language models", 26.12.2024. https://arxiv.org/html/2412.19245v1
[^23^]: OpenReview — "Sentiment trading with large language models", 03.06.2024. https://openreview.net/forum?id=47pcnKq9Mn
[^24^]: GitHub — siddhant-rajhans/bloomberg-sentiment-finbert (Replikationsstudie), 06.05.2026. https://github.com/siddhant-rajhans/bloomberg-sentiment-finbert
[^25^]: arXiv 2601.19504 — "A Hybrid AI-Driven Trading System…Regime-Adaptive Equity Strategies", 27.01.2026. https://arxiv.org/html/2601.19504v1
[^26^]: Algotrader.ch — "AI Trading: What's Real and What's Hype", 30.08.2026. https://algotrader.ch/ai-trading/
[^27^]: arXiv 2502.01574 — "An End-To-End LLM Enhanced Trading System", 03.02.2025. https://arxiv.org/html/2502.01574v1
[^28^]: GitHub — zrodiere/lob_mm_eval (RL-Limitationen), 11.05.2026. https://github.com/zrodiere/lob_mm_eval
[^29^]: Glint Open Access JDAMR — Hou, "Reinforcement Learning for Trading Strategies", o.D. https://glintopenaccess.com/JDAMR/Abstract/Abstract-26-02
[^30^]: daru.finance — "Backtest Overfitting & the Deflated Sharpe Ratio" (92.500 Strategien), o.D. https://daru.finance/research-review/lopez-de-prado/backtest-overfitting
[^31^]: David H. Bailey — "Backtesting in the world of quantitative finance" (Vortragsfolien), o.D. https://www.davidhbailey.com/dhbtalks/dhb-london-quant.pdf
[^32^]: GitHub — Aliipou/backtest-audit, 24.03.2026. https://github.com/Aliipou/backtest-audit
[^33^]: GitHub — AgentJDrew/backtest-guard, 06.07.2026. https://github.com/AgentJDrew/backtest-guard
[^34^]: Algotrader.ch — AI-Washing/CFA/SEC/AIEQ-Analyse, 30.08.2026. https://algotrader.ch/ai-trading/
