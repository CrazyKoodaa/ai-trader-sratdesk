# Deep-Dive Dimension 06: COT-Report-basierte Sentiment-Strategie für Forex Majors

**Scope:** Implementierbare Regel-Spezifikation für einen COT-Sentiment-Bot (MT5 via pymt5trade), FX-Majors, wöchentlicher Rhythmus, Prop-Firm-tauglich, Ziel PF > 1.5 OOS, ≥ 1:2 RR.
**Methodik:** 22+ gezielte Websuchen (EN/DE), 5 Deep-Dive-Reads, **direkte Extraktion der EarnForex-Original-Spreadsheets (CoT Strategies Spreadsheet.zip, CoT_Backtest_Summary.zip) und des COT-Data-Pakets** aus earnforex.com (in-memory analysiert). Zitationsnummern [^N^] sind lokal zu dieser Datei.

---

## TL;DR / Key Findings

1. **Die einzige publizierte, vollständig replizierbare COT-Studie (EarnForex, 32 Strategien, 7 Majors, 2014–2021) zeigt: nur 5/32 Strategien profitabel, und die besten sind NICHT die intuitive "Dealer-Folge", sondern die Non-Reportable-(Kleinspekulanten)-Folge bei steigendem Open Interest (Strategien #29/#32).** [^1^][^2^]
2. **Die klassische Dealer-Folge-Strategie (#1, das EarnForex-"Hauptsystem") war im 2014–2021-TFF-Backtest insgesamt VERLUSTBRINGEND (−3.100 $ kumuliert über alle Paare)** — der häufig zitierte Befund "profitabel auf allen Majors außer AUD/USD" stammt aus einem älteren Backtest (Legacy-Daten, ~2004–2012, inkl. GFC-Drawdowns). Edge-Verfall oder Regime-Abhängigkeit ist anzunehmen. [^1^][^2^]
3. **Akademische Evidenz ist zweigeteilt:** Klitgaard & Weir (NY Fed) finden starke *zeitgleiche* COT-Wechselkurs-Korrelation (75 % Richtungstreffer), aber **keine Vorhersagekraft für die Folgewoche**; Speculative-Pressure-Literatur findet dagegen, dass Spekulanten in Währungsfutures 2,5–4,1 % p. a. Überschussrendite als Hedging-Prämie verdienen. [^7^][^8^][^9^]
4. **Konsens der Praktiker-Literatur: COT ist ein Bias-/Kontext-Filter, kein Standalone-Entry-Signal** ("It is context, not signal" — cotdata.net; Jason Shapiro: Oszillator als Aufmerksamkeitsfilter, Lookback explizit NICHT optimiert). → **Architektur-Empfehlung: COT als Wochen-Bias ÜBER technischen Entries (H4/D1), nicht als always-in-market-Flipper.** [^11^][^12^][^13^][^14^]
5. **Daten-Pipeline ist vollständig kostenlos realisierbar:** CFTC Historical ZIPs (TFF: `com_fin_txt_YYYY.zip`, ab 2006), CFTC Socrata-API ohne Key (6 Dataset-IDs verifiziert), Python-Lib `cot_reports`. [^15^][^16^][^17^]
6. **Prop-Tauglichkeit ist der Knackpunkt:** Wochen-Haltedauer = Wochenend-Gap-Risiko, das bei vielen Prop-Firms die Daily-Loss-Regel am Montag-Open brechen kann; FTMO erlaubt Weekend-Holding nur im Swing-Account. Standalone-COT-Strategien mit 23–42 % Avg-Drawdown sind prop-untauglich; nur die Filter-Variante mit SL/TP ist es. [^19^][^20^][^2^]

---

## A. EarnForex-COT-Studie — vollständige Extraktion

### A1. Setup der Studie
**Claim:** EarnForex hat 32 COT-basierte Strategien über 01.01.2014–22.08.2021 auf USD/CAD, USD/CHF, GBP/USD, USD/JPY, EUR/ AUD/USD, NZD/USD mit fixer Positionsgröße 0.1 Lot gebacktestet (224 Einzelreports). EA + Daten frei verfügbar. Datenbasis = **TFF Combined (FinComYY.txt)** — verifiziert durch Inspektion des COT-Data.zip (enthält `com_fin_txt_2014`…`com_fin_txt_2021` = FinComYY.txt). [^1^][^2^]
**URL:** https://www.earnforex.com/guides/backtesting-strategies-based-on-commitments-of-traders/
**Date:** ~2021/2022 (Backtestende 22.08.2021)
**Confidence:** ✅ Hoch (Originalquelle + eigene Spreadsheet-Extraktion)

### A2. Exakte Regeln der profitablen Strategien (aus `CoT Strategies Spreadsheet.zip` extrahiert, Sheet "CoT Strategies Spreadsheet.ods")
Alle Strategien nutzen Wochen-Änderungen (Δ vs. Vorwoche) der TFF-Positionen. Kategorien: Dealer, AssetMan/Inst, Leveraged, OtherRep, NonRep; OI = Open Interest.

**Strategie #1 (Referenz, "Buy and Sell with Dealers" — die beworbene EarnForex-Strategie):**
- Buy: ΔDealer_longs > 0 AND ΔDealer_shorts < 0
- Sell: ΔDealer_shorts > 0 AND ΔDealer_longs < 0
- Exit: Gegensignal; Extra-Exit: ΔDealer_longs < 0 OR ΔDealer_shorts > 0
- **Ergebnis 2014–2021: GESAMT −3.099,97 $ (Avg DD 21,6 %, 865 Trades).** Pro Paar: USDCHF +3.283 / EURUSD +975 / NZDUSD −2.184 / USDCAD −2.497 / USDJPY −1.743 / GBPUSD −235 / AUDUSD −699.

**Strategie #2 (Dealer + AssetMgr kombiniert, mit Extra-Exit):** Gesamt +573,80 $, Avg DD 16,8 %, 777 Trades.
**Strategie #4 (Dealer UND AssetMgr separat bestätigt, Extra-Exit):** Gesamt +853,89 $, Avg DD **6,1 %**, 155 Trades → bestes DD-Profil unter den Profitablen.
**Strategie #12 (wie #4, aber %-of-OI statt Kontrakte):** Gesamt +713,39 $, Avg DD **4,6 %**, 115 Trades → bestes DD absolut, wenig Trades.

**Strategie #29 (BESTE Konsistenz, NonRep-Folge + OI-Filter, Extra-Exit):**
- Buy: (ΔNonRep_longs > 0 AND ΔNonRep_shorts < 0) AND ΔOI_all > 0
- Sell: (ΔNonRep_shorts > 0 AND ΔNonRep_longs < 0) AND ΔOI_all > 0
- Exit: Gegensignal (ohne OI-Bedingung); Extra-Exit: ΔNonRep_longs < 0 OR ΔNonRep_shorts > 0
- **Gesamt +2.108,93 $, Avg DD 13,4 %, 635 Trades; Verlust nur bei AUDUSD (−851).** Pro Paar: USDJPY +315 / GBPUSD +1.124 / USDCHF +484 / EURUSD +79 / AUDUSD −851 / USDCAD +2 / NZDUSD +956.

**Strategie #32 (höchster Gesamtprofit, NonRep-Folge + OI-Filter, OHNE Extra-Exit):**
- Entry wie #29; Exit nur Gegensignal.
- **Gesamt +4.507,13 $, Avg DD 23,7 %, 374 Trades; Verluste bei USDCHF (−2.447), EURUSD (−1.049), AUDUSD (−3.053).** Pro Paar: USDJPY +1.028 / GBPUSD +5.214 (beste Einzelkombination) / USDCAD +2.943 / NZDUSD +1.870.
- Equity-Kurve #32/GBPUSD (aus Report): relativ glatter Anstieg von 10.0k auf 15.1k über 51 Wochen — einzelnes gutes Jahr, keine Langzeitbeweisführung.

**Wichtige Gegenbefunde aus derselben Studie:** Strategien #15, #26, #31 verlieren >15.000 $ (EarnForex: "invertieren könnte profitabel sein"); ALLE 7 Paare kumulieren über alle 32 Strategien Verluste (GBPUSD −63.108 $, USDCAD −48.195 $); Drawdown-Spalte = MT5 relative Balance-DD in %, #10 GBPUSD DD 85,3 %. [^2^]
**Confidence:** ✅ Hoch (Originaltabellen)

### A3. Interpretation (wichtig für Spezifikation)
- Die "smart-money-Folge" (Dealer) funktionierte 2014–2021 **nicht**; die "dumb-money-Folge" (NonRep = Kleinspekulanten) **bei steigendem OI** (Momentum-Bestätigung) war am robustesten. Plausibel, weil NonRep-Fluss in Währungsfutures trendfolgend ist und OI-Anstieg frisches Kapital signalisiert — konsistent mit Speculative-Pressure-Forschung (Spekulanten = Momentum/Carry-Trader, die Hedging-Prämie verdienen). [^8^][^9^]
- Die alte Dealer-Folge-Evidenz (~2004–2012, Legacy-Report) vs. neue TFF-Evidenz zeigt: **Ergebnis ist report- UND regimeabhängig** → Walk-Forward Pflicht, kein Parameter aus Einzelbacktest übernehmen.
- EarnForex-Warnungen: AUD/USD explizit ausgeschlossen ("profitabel auf allen Majors außer AUD/USD"); XAU/USD und USD/MXN/BRL/RUB "sehr ungenau, weggelassen" (v. a. Spreads); Reports mit Datenstand Dienstag, Release Freitag 15:30 ET, teils Feiertags-Verschiebungen; invertierte Paare (USD/CAD, USD/JPY, USD/CHF, USD/NZD) spiegeln. [^1^]
**URL:** https://www.earnforex.com/forex-strategy/cot-strategy/
**Confidence:** ✅ Hoch

---

## B. Daten-Pipeline (konkret & kostenlos)

### B1. CFTC Historical Compressed (Bulk-Download, kein Key)
Basis-URL: `https://cftc.gov/files/dea/history/` — Datei-Konventionen (aus cot_reports-Quellcode verifiziert [^16^]):

| Report | Jahres-ZIP | TXT darin | Historien-Bundle |
|---|---|---|---|
| Legacy Futures-only | `deacot{YYYY}.zip` | annual.txt | `deacot1986_2016.zip` |
| Legacy Fut+Opt | `deahistfo{YYYY}.zip` | annualof.txt | `deahistfo_1995_2016.zip` |
| Disaggregated Fut | `fut_disagg_txt_{YYYY}.zip` | f_year.txt | `fut_disagg_txt_hist_2006_2016.zip` |
| Disaggregated Fut+Opt | `com_disagg_txt_{YYYY}.zip` | c_year.txt | `com_disagg_txt_hist_2006_2016.zip` |
| **TFF Futures-only** | `fut_fin_txt_{YYYY}.zip` | FinFutYY.txt | `fin_fut_txt_2006_2016.zip` |
| **TFF Combined** | `com_fin_txt_{YYYY}.zip` | FinComYY.txt | `fin_com_txt_2006_2016.zip` |

Aktuelle Woche als TXT: `https://www.cftc.gov/dea/newcot/FinFutWk.txt` (TFF fut-only) bzw. FinComWk.txt. **Für FX zuständig ist der TFF-Report** (Dealer/AssetMgr/Leveraged/OtherRep/NonRep); Legacy unterscheidet nur Commercial/Non-Commercial. Praxis-Regel der Community: TFF/Leveraged Money für FX, Disaggregated/Managed Money für Rohstoffe; Legacy "verwischt" den FX-Look, weil Swap-Dealer als Hedger einsortiert werden. [^6^]
**Confidence:** ✅ Hoch

### B2. CFTC Socrata-API (kein Key nötig, JSON/CSV)
Basis: `https://publicreporting.cftc.gov/resource/{DATASET_ID}.json` — verifizierte IDs [^17^]:

| Report | futures-only | combined |
|---|---|---|
| Legacy | `6dca-aqww` | `jun7-fc8e` |
| Disaggregated | `72hh-3qpy` | `kh3c-gbw2` |
| TFF | `gpe5-46if` | `yw9f-hn96` |

Beispiel: `https://publicreporting.cftc.gov/resource/gpe5-46if.json?contract_market_name=EURO FX&$where=report_date_as_yyyy_mm_dd>'2020-01-01'&$limit=5000`
Update freitags ~15:30 ET (Datenstand Dienstag), kein Rate-Limit dokumentiert (App-Token erhöht Limits). [^17^][^18^]
**Confidence:** ✅ Hoch (IDs aus Client-Lib gegen publicreporting.cftc.gov bestätigt)

### B3. Python-Bibliotheken
- **`cot_reports` (NDelventhal, MIT):** `pip install cot_reports`; `cot.cot_all(cot_report_type='traders_in_financial_futures_fut')` etc. (7 Reporttypen). ~25k Downloads/Monat. [^15^]
- **`cftc-cot` (Mcamin):** `pip install cftc-cot`; `cot_download_year(year, cot_report_type, store_zip=True)` — sauberer ETL-Downloader, liest ZIPs in-memory. [^21^]
**Confidence:** ✅ Hoch

### B4. Sekundärquellen (Fallback/Benchmark)
- **xoomar.com Pulse API (kostenlos, kein Key, 30 req/min):** `GET https://xoomar.com/api/markets/cot/euro-fx` — TFF geparst, Historie ab ~2010, "byte-identical mit CFTC-Quelle verifiziert". [^22^]
- **cotdata.net API:** Free-Tier mit Token: 43 Majors, aktuelle Woche + 24 Monate, 10 req/min; `GET https://cotdata.net/api/cot?instrument=088691`. [^23^]
- **Nasdaq Data Link (Quandl):** CFTC-COT-Datenbank frei mit API-Key (z. B. `CFTC/EC_FO_ALL` u. ä. Codes). [^24^]
**Confidence:** ✅ Hoch (xoomar/cotdata), ⚠️ Mittel (Quandl-Codes unverändert verfügbar, aber API-Doku zeigt nur generellen Zugang)

---

## C. Kombinationsidee: COT als Wochen-Bias-Filter (Evidenz)

**Claim 1:** "COT ist Kontext, nicht Signal. Extreme (oberes/unteres Perzentil) haben probabilistischen, nicht deterministischen Wert; Nutzen = Risiko-Asymmetrie erkennen." [^14^] — cotdata.net Guide, 2026-02. **Confidence:** ✅ (Anbieter, aber mit akademischem Rückhalt)
**Claim 2:** Jason Shapiro (Better System Trader): COT-Oszillator (Lookback-Perzentile) als **Aufmerksamkeits-Filter**, explizit **nicht** als mechanisches Signal; Lookback-Länge bewusst NICHT optimiert (Anti-Overfitting). Entries/Stopps regelbasiert separat. [^13^] **Confidence:** ✅
**Claim 3:** comparebroker.io: Konkreter Workflow — Large-Spec-Nettoposition >80. / <20. Perzentil (3-Jahres-Range) = Extreme; **erst auf technisches Reversal-Signal warten** (Break of Structure, Reversal-Kerze), dann in Unwind-Richtung mit definiertem SL/TP. "COT identifies the condition; the technical signal identifies the timing." [^11^] **Confidence:** ✅
**Claim 4:** InsiderWeek (DE-Praktiker): 5-Schritte-Setup — COT-Signal → Wochentrend prüfen → Bestätigung via Commercials+OI+Divergenz → **Timing über Tagestrend/Divergenz** (SL unter Tief der letzten 2 Balken, Beispiel-Trade 5R). "Es ist möglich, dass alle Positionseröffnungen bis Dienstag abgeschlossen sind." Kontoempfehlung ≥30k $, 2–3 Märkte. [^12^] **Confidence:** ⚠️ Mittel (kommerzieller Anbieter, keine verifizierte Trackrecord)
**Claim 5:** FXPremiere-Guide: COT nur als H1/H4-Bias, Entries M5–M15, ATR-Stops (1,2–1,8× ATR), Partials 1R/2R; explizite A/B-Test-Empfehlung (Strategie mit vs. ohne COT-Filter, Expectancy loggen). [^25^] **Confidence:** ⚠️ Mittel (Signal-Anbieter)
**Claim 6:** fxmacrodata.com: Standard-Lektüre — Net-NonCommercial als Sentiment, Extreme als Wendepunkt-Warnung. [^10^] **Confidence:** ⚠️ Mittel

**Akademische Kontrapunkte:**
- Klitgaard & Weir (NY Fed EPR 2004): Änderung der Spec-Nettoposition erklärt 30–45 % der **gleichwöchigen** FX-Bewegung, 75 % Richtungstreffer zeitgleich — **aber keine Prognosekraft für die Folgewoche**. → COT-Change-Signale (wie EarnForex #29/#32) reiten zeitgleiche Flows; ob daraus handelbarer Edge nach Kosten entsteht, ist NICHT belegt. [^7^]
- Dreesmann/Herberger/Charifzadeh (IJFMD 2023): CoT-Reversal-Strategie — Long-only schlägt S&P-B&H in 6 Märkten signifikant, Long/Short nur in 2; im Portfolio keine Überschuss-Sharpe → "CoT trug zu effizienten Derivatemärkten bei" (Edge wegarbitriert). [^8^]
- Sanders/Boris/Manfredo (Energy Economics 2004): Positionen führen Renditen im Allgemeinen NICHT an (Energie). [^9^]
**Konfidenz akademisch:** ✅ Hoch (Peer-reviewed)

---

## D. Prop-Tauglichkeit & Drawdown-Charakteristik

**Claim 1 (Drawdown-Realität):** Selbst die profitablen EarnForex-Strategien zeigen Avg-DD 4,6–23,7 % (0.1 Lot!); per-Paar bis 37 % (#32 AUDUSD), Portfolio über alle Paare kumulativ tief negativ. "Significant periods of drawdowns (especially following the GFC 2008)" (alte Studie). → **Standalone always-in-market COT ist NICHT prop-tauglich** (typ. Max-DD 4–10 %). Nur mit SL-basiertem Risiko pro Trade und als Filter nutzbar. [^1^][^2^]
**Confidence:** ✅ Hoch

**Claim 2 (Weekend-Holding = Kernrisiko):** FTMO erlaubt Wochenend-Halten nur im Swing-Account; The5ers/FundedNext erlauben es, Apex verbietet es (Futures). Wochenend-Gap (EURUSD typ. 10–20 Pips, geopolitisch 50–100+) schlägt am Montag-Open **durch den Stop hindurch die Daily-Loss-Regel** — Konto failbar ohne eigenes Zutun. [^19^][^20^]
**Confidence:** ✅ Hoch (mehrere Prop-Regel-Quellen, 2026)

**Claim 3 (Consistency-Regeln):** FTMO: keine Daily-Consistency in Normal-Accounts (Swing: max 30 % Profit/Trade); FundedNext 40 % Best-Day, FundingPips Zero 15 %, 5ers 50 %. Wochenstrategien mit wenigen großen Gewinntagen sind hier **strukturell gefährdet** → ggf. Teilschließungen über Tage verteilen oder Firma ohne/ohne harte Consistency wählen. [^20^][^26^]
**Confidence:** ✅ Hoch

**Claim 4 (News-Fenster):** Weekly-COT-Swing hält Positionen durch NFP/CPI — das **Halten** ist bei den meisten Firmen erlaubt, aber **Eröffnen/Schließen** im ±2–10-Min-Fenster je nach Firma verboten → EA braucht News-Gate um Entry/Exit-Events (FTMO ±2 min etc.). COT-Release selbst (Fr 15:30 ET) ist kein Kalender-Event. [^27^]
**Confidence:** ✅ Hoch (steht so in wide04-Quellen [^120^][^123^], hier konsistent)

**Timing-Optionen (Evidenz):** EarnForex-EA handelt direkt nach Release Fr 15:30 ET (FX offen bis 17:00 ET); InsiderWeek analysiert am Wochenende und steigt Mo–Di ein. Fr-15:30-ET-Ausführung = dünne Liquidität/Spreads; Mo-Open = Gap-Risiko der COT-News des Wochenendes. **Empfehlung: Signal Freitag nach Release berechnen, Entry Montag nach erster Handelsstunde (Spread-Normalisierung), alternativ Fr 16:00–17:00 ET mit Limit-Orders. Beides im Backtest als Parameter testen.** [^1^][^12^]
**Confidence:** ⚠️ Mittel (Eigenableitung aus Quellen)

---

## E. Weitere Evidenzbausteine

- **COT-Index-Definition (Briese/Williams-Konvention):** Index = (Net_aktuell − min(Net, N)) / (max(Net, N) − min(Net, N)) × 100; N = 156 Wochen (3 J) klassisch; Zonen <25 % "Sell"/>75 % "Buy" (Kagels, DE) bzw. 90/10-Crowding (tessl/cot-contrarian-detector, 26w+156w). [^28^][^29^][^30^]
- **Larry-Williams-Proxy ohne Report:** COTIndex ≈ Avg(Open−Close, n)/Avg(TrueRange, n)×50+50 — Fallback, falls CFTC-Release ausfällt. [^31^]
- **cotdata.net Euro-Beispiel:** COT-Index (3J) = 1/100 bei Specs −72k netto short EUR → "bearish extreme", kommentiert als Contrarian-Setup. [^32^]
- **Speculative Pressure (JFM, City-Preprint 2019):** Spekulanten in Währungsfutures = Momentum/Carry-Trader; Long-Short-Portfolios verdienen 2,51–4,12 % p. a. signifikante Überschussrendite als Hedging-Druck-Prämie. → Fundamentale Begründung für Folge-Strategien auf Spec-Seite. [^9^]

---

## IMPLEMENTIERUNGS-SPEZIFIKATION (Pseudo-Code)

### Empfohlene Architektur: **COT-Wochen-Bias-Filter + technische Entries** (Variante B; Standalone-Replikation Variante A als Baseline im Backtest)

```
# ============ KONFIGURATION (Walk-Forward-Parameter) ============
PAIRS        = [EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, NZDUSD]   # AUDUSD optional (EarnForex-Warnung)
REPORT       = "TFF_combined"        # A/B: TFF_fut | TFF_combined | Legacy_fut
MAPPING      = {EURUSD:"EURO FX", GBPUSD:"BRITISH POUND", USDJPY:"JAPANESE YEN",
                USDCHF:"SWISS FRANC", USDCAD:"CANADIAN DOLLAR", NZDUSD:"NEW ZEALAND DOLLAR",
                AUDUSD:"AUSTRALIAN DOLLAR"}                         # CFTC-Marktnamen; invertierte Paare (JPY/CHF/CAD/NZD) spiegeln!
INVERT       = {USDJPY, USDCHF, USDCAD} if symbol in USD-quote     # COT bezieht sich auf Nicht-USD-Bein

# --- Bias-Logik (wöchentlich, Datenstand Di, Release Fr 15:30 ET) ---
BIAS_MODEL    = "dealer_am_change"   # A/B: "nonrep_change_oi" (=#29/#32) | "dealer_am_change" (=#4/#12)
                                     #      | "cotindex_extreme" (Contrarian) | "netpos_sign"
LOOKBACK_W    = 52                   # A/B: {26, 52, 156} für Index/Perzentile
IDX_HI, IDX_LO= 80, 20               # A/B: {90/10, 80/20, 75/25}; nur für cotindex_extreme
OI_FILTER     = True                 # A/B: ΔOI_all > 0 als Trend-Bestätigung

# --- Entry-Layer (technisch, H4/D1) ---
ENTRY_MODEL   = "ema_pullback"       # A/B: ema_pullback | donchian_breakout(20) | bos_reversal
SL_ATR        = 1.8                  # ATR(14, D1); A/B {1.2..2.5}
RR            = 2.0                  # min 2R-Ziel; A/B {1.5, 2.0, 3.0}; optional Partial 50% @1R + Trail
RISK_PER_TRADE= 0.005                # 0.5 % Equity; A/B {0.25, 0.5, 0.75} %
MAX_TRADES_WK = 2                    # Pair- und Portfolio-Limit
ENTRY_WINDOW  = "Mon 02:00 - Wed 23:00 Serverzeit"   # A/B: "Fri 16:00-17:00 ET" | "Mon_Open+1h" 

# --- Prop-Risk-Layer ---
DAILY_DD_CAP  = 3 %                  # harter EA-Cap < Firmenlimit (4-5 %)
NEWS_BLOCK    = ±15 min High-Impact (MT5-Kalender), kein Open/Close im Fenster
WEEKEND_RULE  = "firmenspezifisch"   # FTMO-Standard: Freitag X Stunden vor Close flach;
                                     # FTMO-Swing/5ers/FundedNext: Halten erlaubt, Size so, dass
                                     # 100-Pip-Gap < Daily-DD-Cap bleibt
CONSISTENCY   = Partial-TPs über Tage verteilen; Ziel Best-Day < 30 % Gesamtprofit

# ============ WOCHEN-PIPELINE ============
every Friday 15:45 ET:
    df = fetch_cot(REPORT)            # Socrata gpe5-46if/yw9f-hn96 ODER cftc.gov ZIP-Fallback
    for pair in PAIRS:
        pos = df[market == MAPPING[pair]]
        if INVERT-aware: pos = mirror(pos)   # USDCHF etc.: Long/Short tauschen
        ΔDL, ΔDS, ΔAML, ΔAMS, ΔNRL, ΔNRS, ΔOI = changes_vs_last_week(pos)
        signal = evaluate(BIAS_MODEL, ..., OI_FILTER)   # {-1, 0, +1}
        if pair == AUDUSD and BIAS_MODEL=="dealer_am_change": signal = 0   # Studienbefund
        weekly_bias[pair] = signal

every trading day (H4 close), within ENTRY_WINDOW, outside NEWS_BLOCK:
    for pair with weekly_bias != 0:
        tech = entry_signal(ENTRY_MODEL, direction=weekly_bias)   # nur in Bias-Richtung!
        if tech and open_risk_ok():
            place_market_order(pair, dir=weekly_bias, sl=SL_ATR*ATR14_D1, tp=RR*sl_dist,
                               lots=size(RISK_PER_TRADE, sl_dist))

# --- Variante A (Baseline-Replikation EarnForex #29) ---
every Friday 16:00 ET (or Monday open):
    if (ΔNRL>0 and ΔNRS<0 and ΔOI>0): close_all(); buy
    elif (ΔNRS>0 and ΔNRL<0 and ΔOI>0): close_all(); sell
    elif (ΔNRL<0 or ΔNRS>0) and position==long: close   # Extra-Exit (#29); #32: weglassen
    else: hold   # always-in-market
```

### Walk-Forward-Design (Pflichtprogramm)
- **Daten:** TFF combined ab 2006 (Bundle + Jahres-ZIPs); Legacy ab 1986/1995 optional als Robustheitscheck.
- **Schema:** Anchored Walk-Forward, IS 3 Jahre / OOS 6 Monate, schrittweise rollierend 2014→heute; Metrik je Fold: PF, maxDD, Sharpe, Trades. **Abbruchkriterium:** OOS-PF < 1,3 oder maxDD > 2× IS-maxDD.
- **Parameter-Gitter (klein halten, Anti-Overfitting, Shapiro-Warnung beachten):**
  - BIAS_MODEL ∈ {nonrep_change_oi, dealer_am_change, cotindex_extreme}
  - LOOKBACK_W ∈ {26, 52, 156}; IDX-Schwellen ∈ {90/10, 80/20, 75/25}
  - OI_FILTER ∈ {on, off}; ENTRY_WINDOW ∈ {Fri_close, Mon_open+1h}
  - SL_ATR ∈ {1.2, 1.8, 2.5}; RR ∈ {1.5, 2.0, 3.0}
  - Paare: EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, NZDUSD (+AUDUSD separat tagged, Studie negativ)
- **Kostenmodell:** Majors-Spread 0,5–1,5 Pips + Slippage 0,5 Pip/Seite; zusätzlich Swap (Carry-Paare!) — Carry kann bei wochenlangen Shorts auf USDJPY-USD-Shorts positiv/negativ drehen.
- **Robustheitschecks:** (1) A/B mit vs. ohne COT-Filter (FXPremiere-Methodik); (2) Subperioden 2014–2019 vs. 2020–2026 (Regime); (3) Shuffle-Test der Wochenlabels; (4) Report-Switch TFF↔Legacy (Datenquellen-Robustheit).

### Erwartungsmanagement (ehrlich)
- Bester dokumentierter Standalone-Edge: #32 mit PF ≈ 1,3–1,5 in-sample auf 2–3 Paaren, bei 23 % Avg-DD. **PF > 1,5 OOS ist als Standalone unwahrscheinlich** — die realistische Hoffnung ist die Filter-Variante: technisches Setup (mit eigenem PF ~1,3–1,5) × COT-Bias-Gate (Elimination gegenläufiger Trades) → PF-Verbesserung um 0,2–0,4. Das muss der A/B-Test beweisen, sonst Bot verwerfen.
- CFTC-Release-Verzögerungen (Feiertage, Shutdowns) → EA muss fehlende Reports tolerieren (altes Signal max 1 Woche halten, dann flat).

---

## Quellenverzeichnis (lokal zu dieser Datei)

- [^1^] https://www.earnforex.com/forex-strategy/cot-strategy/ — EarnForex, "Commitments of Traders — Forex Trading Strategy" (2012, laufend aktualisiert)
- [^2^] https://www.earnforex.com/guides/backtesting-strategies-based-on-commitments-of-traders/ + https://www.earnforex.com/blog/files/CoT%20Strategies%20Spreadsheet.zip + .../CoT_Backtest_Summary.zip + .../COT-Data.zip — EarnForex 32-Strategien-Backtest (~2021)
- [^6^] https://forexfundamentals.com/learn/cot-report-explained — ForexFundamentals (2026-02)
- [^7^] https://www.newyorkfed.org/research/epr/04v10n1/0405klit/0405klit.html — Klitgaard & Weir, NY Fed Economic Policy Review 10(1), 2004
- [^8^] https://www.inderscience.com/info/inarticle.php?artid=129093 — Dreesmann, Herberger & Charifzadeh, IJFMD 9(1/2), 2023
- [^9^] https://openaccess.city.ac.uk/id/eprint/23283/1/FINAL_JFM__Accepted_27Nov2019_SSRN.pdf — "Speculative Pressure" (JFM, akzeptiert 2019); Sanders/Boris/Manfredo: Energy Economics 26(3), 2004, https://www.sciencedirect.com/science/article/pii/S0140988304000209
- [^10^] https://fxmacrodata.com/articles/cot-report-guide-fx-traders — FXMacroData (2026-04)
- [^11^] https://comparebroker.io/what-is-the-cot-report-and-how-to-use-it-in-forex-trading/ — CompareBroker (2026-05)
- [^12^] https://insider-week.com/de/articles/cot-strategie/ — InsiderWeek DE (2023)
- [^13^] https://bettersystemtrader.com/203-going-against-the-crowd-a-contrarian-approach-to-trading-profits-jason-shapiro/ — Better System Trader (Jason Shapiro, 2026-04)
- [^14^] https://www.cotdata.net/blog/how-to-read-cot-data — cotdata.net (2026-02)
- [^15^] https://github.com/NDelventhal/cot_reports — cot_reports Python-Lib (MIT)
- [^16^] https://raw.githubusercontent.com/NDelventhal/cot_reports/master/cot_reports/cot_reports.py — URL-Konventionen CFTC Historical ZIPs
- [^17^] https://raw.githubusercontent.com/moshejs/commitments-of-traders/main/src/index.ts — Socrata-Dataset-IDs (gegen publicreporting.cftc.gov verifiziert laut Repo)
- [^18^] https://publicreporting.cftc.gov/stories/s/User-s-Guide/p2fg-u73y/ — CFTC PRE User's Guide
- [^19^] https://audacity.capital/trading-guides/can-you-hold-trades-overnight-or-over-the-weekend/ — Audacity Capital (2026-06)
- [^20^] https://joinprop.com/academy/prop-firm-evaluation-rules-2026-consistency-drawdown-explained/ — JoinProp (2026-07)
- [^21^] https://github.com/Mcamin/cftc-cot — cftc-cot Python-Downloader (2026-01)
- [^22^] https://xoomar.com/markets/api/cot — Xoomar Pulse COT API (2026-06)
- [^23^] https://www.cotdata.net/api-access — cotdata.net API-Tiers
- [^24^] https://blog.quantinsti.com/nasdaq-data-link/ — QuantInsti Nasdaq Data Link Guide (2026-08)
- [^25^] https://www.fxpremiere.com/using-the-cot-report-to-improve-xau-usd-signals-a-step-by-step-guide-2025/ — FXPremiere (2025-08)
- [^26^] https://www.tradernotion.com/blog/prop-firm-consistency-rules-explained-2026 — TraderNotion (2026)
- [^27^] s. wide04: FTMO FAQ / Propvator / BestProps (News-Fenster ±2/±5/±10 min)
- [^28^] https://www.kagels-trading.de/cot-daten/ — Kagels Trading, COT-Index-Zonen (2026-08)
- [^29^] https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/cot-contrarian-detector — COT-Index 90/10-Crowding-Definition
- [^30^] https://xoomar.com/markets/cot — COT-Index = 1-Jahres-Perzentil
- [^31^] https://usethinkscript.com/threads/larry-williams-cot-proxy.11384/ — Larry-Williams-Proxy-Formel
- [^32^] https://www.cotdata.net/cot/fx/legacy/euro — cotdata.net Euro-Beispielwerte

*Erstellt: Deep-Dive-Recherche Dimension 06; ~24 gezielte Suchen (EN/DE), 8 geöffnete Primärquellen, 2 Original-Spreadsheets in-memory extrahiert.*
