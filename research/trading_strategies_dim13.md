# Deep-Dive Dimension 13: Volume Profile POC-Retest als Trading-Strategie (6. Bot vs. Filter-Layer)

**Research-Datum:** 2026-09-03 | **Suchen:** 16 gezielte Queries (EN/DE) + 6 Volltext-Deep-Reads (2 GitHub-Repos komplett, Tick-Volumen-Primärquellen, Regelwerk-Quellen) | **Scope:** Swing-Anchored Volume-Profile POC-Retest (Instagram-"neo.wilder"-Setup), quantifizierte Evidenz, Tick-Volumen-Tauglichkeit auf MT5-CFDs, algorithmische Formalisierbarkeit, Portfolio-Einordnung (a/b/c)
**Kontext aus Vorarbeit:** dim02 (Tick-Volumen ~90 %-Korrelation = FX-Studie 2011, Index-CFDs unbelegt), dim10 (S5 = gefilterte MR auf XAUUSD/EURUSD, Konfluenz-Filter = dokumentierter Edge-Hebel), dim12 (MT5-Python-Stack).

---

## 0. WICHTIGSTER BEFUND VORAB

Es existiert **genau ein öffentliches, zum Instagram-Setup passendes quantifiziertes Referenz-Repo**: `parthsarthisaxena/Gold-POC-Retest` — systematische Long-only POC-Retest-Strategie auf XAU/USD, 8 Jahre MT5-M5-Tick-Volumen-Daten, 523 Trades, **PF 1.99, WR 59.7 %, MaxDD 6.4 %**, Walk-Forward 5/6 Fenster ROBUST [^1^]. Dem gegenüber steht die härteste Falsifikationsstudie (`pedrobraiti/volume-profile-trading`, bis 33 Jahre, Walk-Forward + 6 adversariale Tests): **Profil-Geometrie (POC/VA/80 %-Rule) allein ist "mostly folklore"; kein Sleeve besteht alle Falsifikationstests; der Wert liegt im Volumen-Lesen als Filter/Kontext, nicht in den Levels als eigenständiges Signal** [^2^]. **Konsequenz: Empfehlung (b) — POC/HVN als Konfluenz-Filter-Layer, nicht als eigenständiger 6. Bot.** (a) nur als replikationspflichtiger Research-Track auf XAUUSD.

---

## 1. Regelwerk-Rekonstruktion: Swing-High/Low + Anchored-POC-Retest

Das angezeigte Instagram-Video ("neo.wilder": Swing-Low→Swing-High als Anker-Range, Volume Profile darüber, POC als Retest-Level für Long) ist **nicht direkt auffindbar** (Suche nach Handle+Setup: 0 Treffer). Die Mechanik ist aber ein Standard-Setup ("Anchored/Fixed-Range VP auf einer Impuls-Leg, POC-Retest als Continuation-Entry") und aus mehreren unabhängigen Quellen vollständig rekonstruierbar:

### 1.1 Kern-Regelwerk (Konsens aus 5 Quellen)

**Claim:** FRVP/AVP wird auf **eine abgeschlossene, saubere Impuls-Leg** gelegt (Swing-Low → Swing-High im Aufwärtstrend); POC/VAH/VAL dieser Leg werden markiert; beim Rücklauf zum POC wird **nicht blind per Limit**, sondern erst nach **Rejections-Kerze** (Pin-Bar/Engulfing, Schlusskurs in Trendrichtung) long eingestiegen. Stop jenseits der Kerzen-Wick bzw. jenseits VAL; Ziel = VAH / vorheriges Hoch / nächster HVN. [^9^][^10^][^8^]
**Sources:** Forex Tester Online FRVP-Guide (26.05.2026); Alchemy Markets Volume-Profile-Guide (05.09.2025); TradeZella/Forrest-Knight-Strategie (07.07.2026)
**Excerpt (FTO):** "Draw the FRVP on one clean move (for example: from a swing low to a swing high in an uptrend)… Wait for price to come back to POC. Entry trigger: rejection near POC… Stop-loss: beyond the other side of the VA… Take-profit: the opposite side of VA (VAH if you're long)… **Never blind-limit a POC. Wait for price action confirmation**… Avoid tiny ranges — small samples distort the profile and make the POC jump around."
**Excerpt (TradeZella):** "Previous Day POC Retest… After a breakout or trend day, the price often returns to the prior day's POC before resuming the trend… Entry after the signal candle closes at the volume edge. Stop just beyond the signal candle's wick. Target the next shelf — edge-to-edge through the low-volume zone."
**Confidence: HOCH (Regelwerk-Konsens), N/A für das konkrete Instagram-Video.**

### 1.2 Matching-Variante im Referenz-Repo (Gold-POC-Retest)

**Claim:** Die formalisierte Variante des Setups: Nach einer **bestätigten direktionalen Swing-Leg** ist der POC (höchster Volumen-Knoten der Leg) ein struktureller Magnet; **Break über VAH + Rücklauf Richtung POC = Continuation-Long**; struktureller Stop, keine Diskretion; 200-SMA-Trendfilter (long-only); 1 % Risiko/Trade, monatliches −2R-Loss-Limit. [^1^]
**Source:** GitHub parthsarthisaxena/Gold-POC-Retest | **URL:** https://github.com/parthsarthisaxena/Gold-POC-Retest---Multi-Timeframe-Strategy | **Date:** 03.08.2026
**Excerpt:** "After a confirmed directional swing leg, the Point of Control (POC) — the highest-volume price node of that leg — acts as a structural magnet. When price breaks above the Value Area High (VAH) and returns toward POC, it signals continuation of the original leg. Trend-following entry. Defined structural stop. No discretion."
**Confidence: HOCH (dass dies die gehandelte Logik ist); die Signal-Implementierung ist proprietär ("Strategy implementation is proprietary"), nur Diagnose-/WF-Framework öffentlich.**

### 1.3 Verwandtes, besser dokumentiertes Setup: Naked-POC-Retest

**Claim:** Naked/Virgin POC (POC einer Vorsession, den der Kurs noch nicht wieder angelaufen hat) wirkt als Magnet; erster Retest wird in HTF-Trendrichtung mit Bestätigungskerze gehandelt, Stop hinter dem Level, Ziel aktueller Session-POC/VAH. [^11^][^24^][^4^]
**Excerpt (Algobars):** "The thesis isn't 'it will bounce AT the POC,' it's 'price wants to return TO the POC.' Take profit at the level." / (Cofia): "Naked POC D-1 = statistical magnet > 75 % over 5 sessions… Absolute rule: never trade POC mechanically — always context (session type) + confirmation (order flow) + R/R ≥ 1:2."
**Confidence: MITTEL (>75 %-Magnet-Claim ohne offengelegte Stichprobe/Methodik).**

---

## 2. Evidenz: quantifizierte Backtests (positiv UND negativ)

### 2.1 Positiv-Befund: Gold-POC-Retest (XAU/USD, Tick-Volumen!)

**Claim:** XAU/USD M5, MT5-Export (`<TICKVOL>`), Aug 2018–Mai 2026: **523 Trades, WR 59.7 %, Ø +0.347R, PF 1.99, Total +488.96 %, CAGR 25.5 %, MaxDD 6.4 %, 82.4 % profitable Monate**. Walk-Forward (6 expandierende Fenster, ~75–85 OOS-Trades je Fenster): **5/6 ROBUST**, OOS-Calmar mean 7.64 / min 1.76; Fenster 4 (Okt 2023–Sep 2024, Gold-Konsolidierung) nur MARGINAL (OOS-WR 48.0 %) — Long-only-Schwäche in Seitwärtsregimen. [^1^]
**Source:** GitHub parthsarthisaxena/Gold-POC-Retest | **URL:** https://github.com/parthsarthisaxena/Gold-POC-Retest---Multi-Timeframe-Strategy | **Date:** 03.08.2026 (Repo-Update)
**Einschränkungen (vom Autor selbst deklariert, ungewöhnlich ehrlich):** Tick-Volumen-Proxy ("a CME Gold futures implementation with real dollar volume would be structurally cleaner"); long-only, nie in einem mehrjährigen Gold-Bärenmarkt getestet; **Sharpe-Punktschätzer 4.85, aber 95 %-CI [−0.01, 9.71]** — Untergrenze faktisch null; nur ein Asset; "Strategy has not been traded live"; Execution-Annahme next-bar-open mit fixem Kosten-Proxy.
**Confidence: MITTEL.** Plausibles, methodisch sauber dokumentiertes Ergebnis, aber: Einzelautor, keine unabhängige Replikation, proprietäre Signallogik, Sharpe-CI schließt 0 ein, Kostenmodell simpel. **Erfüllt aber nominal das Zielkriterium PF > 1.5 OOS-artig (WF) — der einzige gefundene Beleg, der das tut.**

### 2.2 Negativ-/Falsifikations-Befund: VP-Geometrie allein ohne robusten Standalone-Edge

**Claim:** Studie über SPY/QQQ/PETR4/VALE3/BOVA11 (täglich, bis 33 Jahre, Walk-Forward 8J-train/3J-test, Kosten-Modelle, 500× Volumen-Permutation, Random-Entry-Kontrolle, Bootstrap-CI auf PF): OOS-PFs — POC-Reversion SPY 1.13/QQQ **1.63**; Edge-to-Edge SPY 1.41/QQQ **2.06**; VA-Breakout QQQ 1.58; Volume-Exhaustion SPY 1.51/QQQ 1.94/BOVA11 2.16. **ABER:** Kein Sleeve besteht alle Falsifikationstests — Bootstrap-95 %-CIs des PF schließen 1.0 ein (SPY [0.99, 2.83]), kein Alpha über eigene Long-Exposure, schlägt risikofreien Zins nicht. 80-%-Rule traversiert nur 27–67 % (statt 80 %) und verliert nach Kosten. Trendige Einzelwerte (PETR4/VALE3): negativ. **Volumen-Bestätigungskerze hebt QQQ-E2E von PF 1.14 → 1.63 (1.2×) → 1.89 (1.5×)** — "the signal is in the volume, not the geometry". Kosten-Sensitivität: Edge tot ab ~0.8 % Round-Trip. [^2^]
**Source:** GitHub pedrobraiti/volume-profile-trading | **URL:** https://github.com/pedrobraiti/volume-profile-trading | **Date:** 09.06.2026
**Excerpt:** "Volume Profile is a legitimate context lens and the volume filter adds real selectivity, but there is no robust, standalone economic edge… The geometry alone (POC, Value Area, day-types, 80% Rule) is mostly folklore."
**Confidence: HOCH (Methodik transparent, reproduzierbar, adversarial) — mit Caveat: tägliche Composite-Profile auf ETFs, nicht M5-Intraday-CFD; überträgt sich nur bedingt 1:1 auf das Instagram-Setup.**

### 2.3 Orderflow-bestätigte NQ-Statistiken (klein, aber konkret)

**Claim:** NQ 2024–2025, 89 gefilterte Occurrences: Absorption am Naked POC (Vortag, unangetastet) → **WR 59 %, Ø-Win +2.1R, Ø-Loss −0.9R, Expectancy +0.87R**. Ohne Naked-POC-Kontext fällt dasselbe Absorptions-Muster auf 45–50 % WR ("not enough to have an edge"). CVD-Divergenz an Major-VP-Level (Prev-Day-POC/VAL): 128 Trades, WR 58 %, +0.82R. [^3^][^26^]
**Source:** Cofia Trading (ATAS-Orderflow-Setups) | **URL:** https://cofiatrading.com/en/blog/absorption-atas-3-setups-chiffres | **Date:** 22.04.2026
**Confidence: MITTEL-NIEDRIG (Vendor-Blog, Footprint-Konfirmation auf CFD nicht verfügbar, keine Kosten offengelegt) — aber directionell wichtig: VP-Level als Kontext-Filter macht den Unterschied zwischen keinem Edge (45–50 %) und Edge (59 %).**

### 2.4 Weitere Zahlen (schwache Quellenlage)

- **Journali.io:** ES, 100 RTH-Sessions manuell: POC-Magnet-Trades 60 % WR, VAH/VAL-Reversals 62 % WR [^5^]. **Confidence: NIEDRIG** (undokumentierte Methodik, n=100 Sessions ≠ 100 Trades).
- **PineScriptForge (Content-Farm, AI-generiert):** "Volume Profile POC" auf LE-Futures, n=608, Jan 2023–Mär 2026, **PF 0.85 post-friction, WR 49.5 %, MaxDD 36.9 %** — explizit unprofitabel [^6^]. Als Negativ-Datenpunkt für mechanisches POC-Bounce ohne Kontext verwertbar, aber Quelle unseriös (template-generierte Seiten). **Confidence: NIEDRIG.**
- **Lunefi:** "Hypothetical backtests on NQ (2024–2026): 66 % WR, PF 1.9" für MTF-VP+VWAP-Konfluenz [^7^]. **Confidence: SEHR NIEDRIG** ("hypothetical", keine Methode).

**Evidenz-Summe:** Genau 1 sauberer Positiv-Backtest (XAUUSD, WF, PF 1.99, aber Replikations- und CI-Caveats) + 1 saubere Falsifikation (kein robuster Standalone-Edge, Geometrie=Folklore, Volumen-Filter=echte Selektivität) + kleine Orderflow-Stichproben, die zeigen: **VP-Level erzeugen Edge nur in Kombination mit Kontext/Konfirmation.** Kein einziger unabhängiger, peer-reviewter oder akademischer Backtest zu POC/VPVR existiert (Suche SSRN/MDPI/ScienceDirect: 0 Treffer).

---

## 3. Tick-Volumen-POC auf Forex/CFD: funktioniert das?

### 3.1 Korrelations-Evidenz (Präzisierung von dim02)

**Claim:** Die ~90-%-Zahl ist konkret die **Caspar-Marney/fxvolume-Studie (2011, FX-Majors, Stunden-Aggregation)**: Pearson r ≈ **0.9683 EURUSD, 0.9583 USDJPY, 0.9894 GBPUSD, 0.9714 EURCHF** (r² 92–98 %) Tick-Count vs. ECN-Echtvolumen (HotSpot/EBS via eSignal). Korrelation fällt in Asien-Session auf ~0.60; auf Sub-Minuten-Bars deutlich schwächer. [^13^][^15^]
**Source:** BacktestMarket "Tick Volume vs Real Volume" (18.08.2026, referenziert fxvolume-Studie + 2016-Tick-Klassifikationsstudie); TradingWyckoff (23.05.2026)
**Confidence: HOCH für FX-Majors H1-Aggregation; UNBELEGT für XAUUSD/NAS100-CFDs und M5 (Bestätigung dim02).**

### 3.2 Spezifisch für Volume Profile / POC-Lage

**Claim:** Für die **POC-Position** (nicht absolute Volumen-Zahlen) ist Tick-Volumen brauchbarer als oft dargestellt: "If you analyze real volume and tick volume, they will have the same peak volume more than 90 % of the time… the older the timeframe, the greater this deviation… since it is most effective to use the volume profile on intraday time frames, this problem disappears by itself." [^16^] Profil-**Form** ("where the market was active") bleibt aussagekräftig; absolute Zahlen und Broker-Vergleiche sind es nicht. [^27^]
**Source:** JustMarkets Volume-Profile-Guide (28.02.2025); TradingSFX (13.07.2026)
**Confidence: MITTEL (Praktiker-Claims, keine Primärstudie zum POC-Peak-Match).**

### 3.3 Verzerrungen, die für POC-Strategien relevant sind

**Claim:** (a) Tick-Volumen ist **broker-feed-abhängig** — gleiche M5-XAUUSD-Kerze: Broker A 1.840 Ticks vs. Broker C 450 Ticks (Bridge-Throttling) [^14^]; (b) Quote-Churn in engen Konsolidierungen erzeugt falsche "Akkumulations"-HVNs; (c) Spread-Weitungen ohne Trade zählen als Ticks; (d) große Einzelorders sind tick-blind (1.000-Lot-Block = 1 Tick); (e) EarnForex zeigt wöchentliche EURUSD-Tick-Volumes zweier Broker **unkorreliert** mit 6E-Futures [^17^]. **Konsequenz: POC aus Tick-Volumen ist innerhalb eines Brokers/einer Session relativ stabil, aber nicht broker-übergreifend reproduzierbar; Backtests sind feed-spezifisch.**
**Sources:** FXNX XAUUSD-Tick-Volume (02.09.2026) [^14^]; TradingWyckoff [^15^]; EarnForex [^17^]
**Confidence: HOCH (Mechanik), MITTEL (Ausmaß der POC-Verschiebung).**

### 3.4 Praktischer Ausweg

**Claim (Konsens dim02 + TradingWyckoff):** "Elegant solution: analyze the future's real volume (6E/GC/NQ) and trade the CFD — arbitrage makes them move identically." Für XAUUSD: GC-Futures-Profil als Referenz-POC; für NAS100: NQ; für FX-Majors: 6E/6B/6J. [^15^][^14^]
**Confidence: HOCH als Best Practice; erfordert externen Futures-Datenfeed.**

---

## 4. Formalisierbarkeit: POC/HVN/LVN algorithmisch

### 4.1 Standard-Algorithmus (aus 3 Open-Source-Implementierungen rekonstruiert)

1. **Fenster/Anker:** Swing-Anker (Fractal/ZigZag-Pivots) oder fixe Lookback; Preis-Range = [min(Low), max(High)] des Fensters.
2. **Binning:** Range in N gleich hohe Zeilen teilen (typisch N=50–200, Default 100 [^18^][^19^]) **oder** Bin-Breite = k × ATR (volatilitätsadaptiv; k ≈ 0.1–0.25 ist gängige Praxis, nicht standardisiert). Pine v6: `volume.profile_fixed(bars, rows, va_pct)`; TradingView-Footprint: `request.footprint(ticksPerRow, vaPercent)` — Bin-Breite in Ticks parametrisierbar [^21^][^22^].
3. **Volumen-Verteilung:** Bar-Volumen gleichmäßig über die vom Bar (High–Low) überdeckten Bins verteilen (`volume_per_bin = bar_vol / n_covered_bins`) [^19^] — oder präziser via Lower-TF-/Tick-Daten.
4. **POC:** `argmax(volumes)` → Bin-Mitte [^19^].
5. **Value Area (70 %):** Vom POC aus greedily expandieren, jeweils die Seite mit höherem Nachbar-Bin-Volumen anfügen, bis Σ ≥ 70 % Gesamtvolumen → VAH/VAL [^19^][^20^].
6. **HVN/LVN:** Lokale Maxima/Minima des geglätteten Volumen-Histogramms (z. B. Bin-Vol > µ + k·σ = HVN).

**Referenz-Code (vollständig, lauffähig):** InsiderFinance `VolumeProfileAnalyzer.calculate_volume_profile()` (Python/ccxt, ~40 Zeilen, exakt Schritte 2–5) [^19^]; TraderMade `calculate_value_area()` (TPO-Variante, midmax-Tiebreak) [^20^]; Pine-v6-Template inkl. Session-POC-Crossover-Strategie [^21^]; TradersPost Pine-v6-Footprint-Strategie mit POC/VA/Delta [^22^].
**MT5/MQL5:** ZovraT/MT5-volume-profile-indicator (Session/Fixed/Visible-Range, POC/VAH/VAL, Tick- oder Real-Volumen wählbar) [^23^]; MarcosACH/volume-profile (Lookback 500/Rows 100/VA 70 % Defaults) [^18^].
**Confidence: SEHR HOCH — Formalisierung ist trivial lösbar; Aufwand steckt in Swing-Anker-Definition (Fractal-Parameter) und Rejections-Kerzen-Definition, nicht im Profil.**

### 4.2 Kritische Design-Entscheidungen (mit Evidenz)

- **Nur abgeschlossene Legs profilen** ("Only once the move is complete will VAH, VAL, POC be reliable") [^10^]; kleine Ranges vermeiden (POC springt) [^9^].
- **Rejections-Bestätigung Pflicht, kein Blind-Limit** [^9^][^4^] — konsistent mit 2.2/2.3 (Volumen-/Kontext-Filter = der eigentliche Edge).
- **Session-Filter:** Tick-Volumen-Korrelation nur in London/NY hoch [^13^] → Profilbildung und Entries auf liquide Fenster beschränken.
- **Kosten:** Edge ist dünn und kostensensitiv (tot ab ~0.8 % RT auf ETF-D1 [^2^]) → nur enge Spreads (XAUUSD/NAS100 bei Prop-Firm typisch OK, aber im Backtest realistisch modellieren).

---

## 5. IMPLEMENTIERUNGS-SPEZIFIKATION

### 5.1 Variante (b) — EMPFOHLEN: "VP-Confluence-Layer" für bestehende Bots

Gemeinsames Modul `volume_profile.py` (läuft neben S1–S5, kein eigener Orderfluss-Zwang):

```
# Daten: M5-Bars via MetaTrader5 copy_rates_*, tick_volume (VOLUME_REAL=0 auf CFD)
# Profil-Update: 1× pro geschlossener M5-Kerze (billig) 

def build_profile(bars, anchor_idx, n_rows=None, atr=None):
    lo, hi = bars.low[anchor_idx:].min(), bars.high[anchor_idx:].max()
    n_rows = n_rows or int(np.clip((hi-lo)/(0.15*atr), 40, 200))  # ATR-adaptive Bin-Breite
    edges  = np.linspace(lo, hi, n_rows+1)
    vol    = np.zeros(n_rows)
    for b in bars[anchor_idx:]:                                   # gleichmäßige Verteilung
        i0, i1 = np.searchsorted(edges, [b.low, b.high])
        vol[i0:max(i1, i0+1)] += b.tick_volume / max(i1-i0, 1)
    poc_i = vol.argmax(); poc = (edges[poc_i]+edges[poc_i+1])/2
    # Value Area: greedy Expansion ab POC bis 70 % Gesamtvolumen
    # HVN: vol > mean + 1.0*std (geglättet, 3-Bin-Kernel); LVN: < mean - 1.0*std
    return poc, vah, val, hvn_zones, lvn_zones

# Anker je Use-Case:
#  A) Session-Profil: Vortag 00:00 Server → POC_d1, VAH_d1, VAL_d1, naked-POC-Liste (letzte 5–10 Sessions)
#  B) Swing-Profil: letztes bestätigtes Fractal-Pivot-Paar (z. B. 5/5-Fractal auf H1), 
#     nur wenn Leg-Länge >= 2*ATR(H1) und Leg abgeschlossen (Gegen-Fractal gedruckt)
```

**Filter-Regeln (Konfluenz-Gate, blockiert oder gewichtet Entries der Bestands-Bots):**

| # | Regel | Wirkung | Begründung |
|---|---|---|---|
| F1 | Entry-Zone des Bots ∩ (POC ± 0.25·ATR oder HVN-Zone) ≠ ∅ | Entry erlaubt / Score +1 | VP-Level als Kontext: 45–50 % → 59 % WR [^3^]; Volumen-Selektivität [^2^] |
| F2 | Entry-Zone liegt in LVN / "mid-zone" | Entry **blockiert** | "Avoid mid-zone trades; low-volume zones unpredictable" [^8^]; LVN = schnelle Durchlaufzone [^25^] |
| F3 | Stop des Bots jenseits VAH/VAL bzw. jenseits LVN | Stop-Adjust | "Stop beyond LVN = only genuine repricing takes you out" [^25^] |
| F4 | TP mindestens am nächsten HVN / gegenüberliegender VA-Edge; RR-Check ≥ 1:2 gegen dieses strukturelle Ziel (nicht gegen fixe Distanz) | TP-Adjust/Veto | Edge-to-Edge-Targeting [^8^]; RR-Ziel des Portfolios |
| F5 | Session-Gate: Profil-Signale nur London/NY (Serverzeit 09:00–17:00 GMT+2/+3); Asien-POCs ignorieren | Zeitfilter | Tick-Korrelation ~0.6 in Asien [^13^] |
| F6 | Naked-POC-Liste als TP-Magnete für offene Positionen (TP-Verschiebung auf nPOC − Puffer) | Exit-Optimierung | nPOC-Magnet-Logik [^11^][^4^] |

**Anwendung konkret:** S5 (MR XAUUSD/EURUSD, dim10): RSI/BB-Signal nur feuern, wenn Entry am Vortags-POC/VAH/VAL oder Swing-POC liegt (F1+F2) → Ziel: Replikation des "Filter hebt PF"-Musters aus dim10 (EMA200+ADX: PF 0.98→3.00) mit VP als drittem Filter. S1 (Pullback): Pullback-Zone ∩ POC/HVN als Qualitäts-Score.

**Validierungs-Protokoll (Pflicht vor Live):** A/B im Backtest — Bot mit vs. ohne F1–F4, gleiche Signale, gleiche Kosten; Metriken PF/Expectancy/DD pro Instrument; ≥ 100 Trades je Arm [^999^]; Walk-Forward; Feed-Robustheitstest (Profile auf Broker-A-Daten rechnen, auf Broker-B-Daten ausführen, da tick-feed-abhängig [^14^]).

### 5.2 Variante (a) — nur als Research-Track: eigenständiger XAUUSD-POC-Retest-Bot

Replikationsziel = Repo [^1^] (einziger Positiv-Beleg). Spezifikation (aus README + Quellen-Konsens rekonstruiert, Lücken markiert):

- **Instrument/TF:** XAUUSD M5, Serverzeit; Daten MT5-Export `<TICKVOL>`.
- **Regime-Filter:** Close > SMA(200) (H1 oder M5 — **Lücke: Repo nennt TF nicht; WF-Scan beide**); long-only.
- **Anker:** bestätigte Swing-Leg (Fractal/ZigZag, **Lücke: Parameter proprietär** — Start: 5/5-Fractal H1, Mindest-Leg 2×ATR).
- **Signal:** (i) Break-Close über VAH der Leg; (ii) Rücklauf in POC-Zone (POC ± 0.25×ATR(M5)); (iii) Bullish-Rejection-Kerze (Close > Open, untere Wick ≥ 50 % der Range o. ä.); Entry next-bar-open.
- **Stop:** strukturell unter POC/VAL bzw. Rejection-Low (WF-Scan); **TP:** ≥ 2× Stop-Distanz oder VAH/Vorheriges-Hoch — 1:2-RR-Ziel des Portfolios prüfen (Repo: Ø +0.347R bei 59.7 % WR → implizit ~1.5:1 Payoff; für 1:2-Ziel ggf. TP an VAH hart setzen).
- **Risiko:** 1 %/Trade, monatliches −2R-Limit (Repo-Setting, prop-tauglich: MaxDD 6.4 % über 8 Jahre).
- **Go/No-Go-Kriterien:** Replikation PF ≥ 1.5 OOS UND Bootstrap-95 %-CI(PF) > 1.0 UND Bestehen der Falsifikations-Suite aus [^2^] (Volumen-Permutation, Random-Entry-Kontrolle) — sonst nicht deployen.

### 5.3 Variante (c) — Bedingungen

Gar nichts bauen, falls: A/B-Test in 5.1 keinen PF-/Expectancy-Uplift zeigt oder die [^1^]-Replikation an CI-/Falsifikations-Kriterien scheitert.

---

## 6. EINORDNUNG & EMPFEHLUNG: **(b) — Konfluenz-Filter-Layer**

**Begründung:**
1. **Evidenzlage Standalone zu dünn:** Genau ein Positiv-Backtest (Einzelautor, proprietär, Sharpe-CI ∋ 0, nie live, single-asset, Gold-Bullenmarkt-Dekade) [^1^] gegen eine methodisch stärkere Falsifikationsstudie: VP-Geometrie allein = "mostly folklore", kein Sleeve mit PF-CI > 1.0 [^2^]. Zwei kleinere Positiv-Stichproben (n=89/128) benötigen Orderflow-Footprint — auf MT5-CFD nicht verfügbar [^3^].
2. **Evidenzlage als Filter ist die konsistenteste Aussage aller Quellen:** Volumen-Signalkerze hebt PF 1.14→1.89 [^2^]; VP-Level-Kontext hebt WR 45–50 %→59 % [^3^]; LuxAlgo/FTO/PropTraderReviews-Konsens: Level = "location, not a reason", immer mit Konfluenz/Konfirmation [^12^][^9^][^24^]. Das deckt sich exakt mit dem Portfolio-Befund "Konfluenz-Filter = Edge-Hebel" (dim10).
3. **Tick-Volumen-Problem ist für Filter-Nutzung kleiner als für Standalone:** Als Filter reicht die Profil-Form/POC-Lage (intraday, liquide Sessions, ~90 %-Peak-Match-Claim [^16^]); ein Standalone-Bot hinge vollständig an feed-spezifischen POC-Levels. Optionaler Härtungs-Pfad: GC-/NQ-/6E-Futures-Volumen als Referenzprofil [^15^].
4. **Implementierungs-Asymmetrie:** Filter-Layer = 1 Modul, A/B-testbar, kein neuer Drawdown-Korrelations-Block im Portfolio; Standalone-Bot = voller Validierungszyklus + zusätzliche Korrelation zu S5 (beide XAUUSD, MR/Retest-Überlappung) unter Prop-DLL.
5. **Research-Track (a) behalten:** Die [^1^]-Replikation auf XAUUSD ist der am besten dokumentierte Weg zu einem echten 6. Bot — mit den Go/No-Go-Kriterien aus 5.2.

---

## Quellen

[^1^]: GitHub – parthsarthisaxena/Gold-POC-Retest — Multi-Timeframe-Strategy (XAU/USD POC-Retest, 8 Jahre M5-MT5-Tick-Volumen, PF 1.99, WR 59.7 %, n=523, WF 5/6 robust, Sharpe 95%-CI [−0.01, 9.71]), 03.08.2026, https://github.com/parthsarthisaxena/Gold-POC-Retest---Multi-Timeframe-Strategy
[^2^]: GitHub – pedrobraiti/volume-profile-trading ("Honest backtest and falsification…", 17–33 J., Walk-Forward, Permutation/Bootstrap; OOS-PF QQQ-E2E 2.06, POC-REV QQQ 1.63; kein Sleeve besteht alle Tests; Volumenkerze 1.14→1.89), 09.06.2026, https://github.com/pedrobraiti/volume-profile-trading
[^3^]: Cofia Trading – "ATAS Absorption — 3 quantified order flow setups" (Naked-POC-Absorption NQ 2024–2025: n=89, WR 59 %, +0.87R; ohne Kontext 45–50 %), 22.04.2026, https://cofiatrading.com/en/blog/absorption-atas-3-setups-chiffres
[^4^]: Cofia Trading – "POC Point of Control — 4 High-Probability Trading Setups" (nPOC-Magnet >75 %/5 Sessions; nie mechanisch, R/R ≥ 1:2), 20.04.2026, https://cofiatrading.com/en/blog/poc-point-of-control-4-setups
[^5^]: Journali.io – "Volume Profile / POC Trade Trading Strategy" (ES 100 RTH-Sessions: POC-Magnet 60 % WR, VAH/VAL 62 %), o. D., https://journali.io/strategies/volume-profile
[^6^]: PineScriptForge – "LE Volume Profile POC Backtest" (n=608, PF 0.85 post-friction, WR 49.5 %, MaxDD 36.9 %; AI-Content-Farm), 15.07.2024, https://pinescriptforge.com/le/volume-profile-poc/backtest/conservative
[^7^]: Lunefi – "Volume Profile Indicator 2026" (hypothetischer NQ-Backtest: 66 % WR, PF 1.9), 06.05.2026, https://lunefi.com/blog/volume-profile-indicator-2026-strategies-stats-tips-day-trading
[^8^]: TradeZella / Forrest Knight – "Volume Profile Trading Strategy" (Prev-Day-POC-Retest, Edge-to-Edge, Mid-Zone-Verbot, Wick-Retrace-Entry), 07.07.2026, https://www.tradezella.com/strategies/volume-profile-strategy
[^9^]: Forex Tester Online – "Fixed Range Volume Profile: Settings, Strategies & Backtesting" (Swing-Low→Swing-High-Anker, POC-Rejection-Regeln, nie blind limitieren, kleine Ranges vermeiden), 26.05.2026, https://forextester.com/blog/fixed-range-volume-profile/
[^10^]: Alchemy Markets – "Volume Profile Effective Trading Guide" (FRVP/AVP/SVP, FRVP+Fib-HVN-Swing-Strategie, nur abgeschlossene Legs), 05.09.2025, https://alchemymarkets.com/education/indicators/volume-profile/
[^11^]: Algobars – "Naked POC Retest" (Regelwerk: nPOC 5–10 Tage, VWAP-Momentum-Filter, Stop 1 ATR, Ziel nPOC, 3–5R), 13.05.2026, https://algobars.com/strategy-templates/volume-profile/naked-poc-retest/
[^12^]: LuxAlgo Library – "Point of Control — Concept FAQ" (naked POCs nicht garantiert; Forex-Profile aus Tick-Counts "read exact node sizes more skeptically"), o. D., https://www.luxalgo.com/library/indicator/Jp01IItw-volume-footprint-poc-for-every-candle/
[^13^]: BacktestMarket – "Tick Volume vs Real Volume for Forex Traders" (fxvolume-Studie: r≈0.97 EURUSD H1, r² 92–98 %; Asien ~0.60; Sub-Minuten schwach), 18.08.2026, https://www.backtestmarket.com/en/blog/forex-tick-volume-vs-real-volume
[^14^]: FXNX – "XAUUSD Tick Volume on MT5: What the Bars Actually Count" (Broker-A 1840 vs. Broker-C 450 Ticks gleiche Kerze; Quote-Churn-Artefakte; Tick-VWAP bricht an Range-Extremen), 02.09.2026, https://fxnx.com/en/blog/xauusd-tick-volume-mt5-what-bars-actually-count
[^15^]: TradingWyckoff – "Tick Volume vs Real Volume" (Korrelation bricht bei großen stillen Orders; 6E-Realvolumen analysieren, EURUSD-CFD handeln), 23.05.2026, https://tradingwyckoff.com/en/tick-volume-vs-real-volume/
[^16^]: JustMarkets – "Volume Profile Indicator" (Tick- vs. Real-Volumen: gleicher Peak >90 % der Zeit; Abweichung wächst mit TF; intraday unkritisch), 28.02.2025, https://justmarkets.com/trading-articles/learning/volume-profile-indicator-your-trading-assistant
[^17^]: EarnForex – "Tick Volume in Forex" (Broker-Disparitäten; wöchentliches Tick-Volumen teils unkorreliert mit 6E-Futures), o. D., https://www.earnforex.com/guides/tick-volume-in-forex/
[^18^]: GitHub – MarcosACH/volume-profile (Binning/POC/VA-Methodik, Defaults Lookback 500, Rows 100, VA 70 %), 08.07.2025, https://github.com/MarcosACH/volume-profile
[^19^]: InsiderFinance Wire – "Mastering volume profile: building a bitcoin market structure analyzer in Python" (vollständiger Python-Code: np.linspace-Binning, gleichmäßige Bar-Verteilung, argmax-POC, greedy VA-Expansion), 23.10.2024, https://wire.insiderfinance.io/mastering-volume-profile-building-a-bitcoin-market-structure-analyzer-in-python-64f3c01135b8
[^20^]: TraderMade – "Build a Market Profile Dashboard with Python" (TPO midmax-POC, calculate_value_area greedy), 14.03.2025, https://tradermade.com/tutorials/build-a-market-profile-dashboard-in-python
[^21^]: offline-pixel.github.io – "Pinescript Volume Profile Guide" (Pine v5/v6 volume.profile_fixed/session, POC-Crossover-Strategie-Code), 16.06.2025, https://offline-pixel.github.io/pinescript-strategies/pine-script-volumeprofile/
[^22^]: TradersPost – "Trade the Point of Control with Pine Script Footprint" (request.footprint(ticksPerRow, vaPercent), POC/VA/Delta-Strategie v6, 5m–1h empfohlen), 11.03.2026, https://blog.traderspost.io/article/poc-value-area-strategy-pine-script
[^23^]: GitHub – ZovraT/MT5-volume-profile-indicator (MQL5/C#: Session/Fixed/Visible-Range, POC/VAH/VAL, Tick-/Real-Volumen-Umschaltung), 23.07.2026, https://github.com/ZovraT/MT5-volume-profile-indicator
[^24^]: Audacity Capital – "Volume Profile Trading Strategy Guide" (Naked-POC-Retest-Setup: HTF-Trend + Konfirmationskerze, "a location, not a reason"), 11.08.2026, https://audacity.capital/trading-guides/volume-profile-trading-strategy/
[^25^]: PropTraderReviews – "Volume Profile Trading Explained" (LVN als Stop-Lage/Target-Logik; nPOC-Tag-Rate als eigene testbare Statistik), o. D., https://proptraderreviews.com/guides/volume-profile-trading-explained-poc-value-areas-and-how-funded-traders-use-them
[^26^]: Cofia Trading – "CVD divergences guide" (CVD-Divergenz an VP-Level: n=128, WR 58 %, +0.82R), 22.04.2026, https://cofiatrading.com/en/blog/cvd-divergences-guide-complet
[^27^]: TradingSFX – "How to Read POC, Value Area, and Volume Nodes" (Tick-Profil-Form brauchbar, absolute Zahlen Proxy, brokerabhängig), 13.07.2026, https://tradingsfx.com/blog/volume-profile-explained-poc-value-area
[^999^]: Backtrex – "Backtest Metrics: Expectancy, Profit Factor" (PF-Bands; ≥100 Trades Mindeststichprobe), 24.05.2026, https://backtrex.com/en/blog/backtest-metrics-expectancy-profit-factor

---

*Methodik: 16 gezielte Suchqueries (EN/DE) + Volltext-Reads der 2 Schlüssel-Repos [^1^][^2^] und der Tick-Volumen-Primärquellen [^13^][^14^][^15^]. Härteste Datenpunkte: [^1^] (einziger WF-validierter Positiv-Backtest, exakt das Ziel-Setup auf dem Ziel-Instrument mit Ziel-PF) und [^2^] (einzige adversariale Falsifikation). Größte Lücken: (i) Instagram-Video "neo.wilder" nicht auffindbar — Regelwerk über Konsens-Quellen rekonstruiert; (ii) [^1^]-Signallogik proprietär, keine unabhängige Replikation; (iii) keine akademische Literatur zu POC/VPVR (0 Treffer SSRN/MDPI/ScienceDirect); (iv) Tick-POC-vs.-Futures-POC-Vergleichsstudie existiert nicht als Primärquelle (>90 %-Peak-Match ist Praktiker-Claim [^16^]).*
