# Dimension 05: Asian-Range-/London-Breakout auf USDJPY (+ Breakout-Retest auf FX Majors)

**Research-Datum:** 2026 | **Suchen:** 18 gezielte Queries (EN/DE) + 2 Repo-Zugriffe + eigene Signifikanzrechnung
**Kontext:** 5 Python-Bots auf MT5 (pymt5trade), Ziel PF > 1.5 OOS, ≥1:2 RR, Prop-Firm-tauglich. Ausgangspunkt: Trade-Desk-Claim "USDJPY Session-Breakout: 227 Trades, 48 % WR, PF 1.25, +0.14R" (einziger positiver Datenpunkt im Wide-Report).

---

## 1. Kernquelle: GitHub WalterVeriza/Trade-Desk — exaktes Regelwerk extrahiert

**Claim:** Session-Breakout-Archetyp auf 8 FX-Paaren ist aggregat breakeven (−0.08R), aber **USDJPY einzig positiv: 227 Trades, 48 % WR, PF 1.25, +0.14R netto**.
**Source:** GitHub WalterVeriza/Trade-Desk — ROADMAP.md + vollständiger Backtest-Code
**URL:** https://github.com/WalterVeriza/Trade-Desk/blob/main/ROADMAP.md · https://raw.githubusercontent.com/WalterVeriza/Trade-Desk/main/backend/scripts/forex-research.js
**Date:** 2026-06-23 (Repo archiviert 2026-08-21, read-only)
**Confidence:** HOCH für das Regelwerk (Primärcode gelesen), MITTEL für den Edge (siehe Signifikanz-Analyse §3)

**Exzerpt (ROADMAP, franz. Original):** "Breakout de session (range asiatique 00-07 UTC, trigger Londres/NY, R:R 1.5): −0.08R agrégat MAIS pile au breakeven (40% win = seuil) et USDJPY franchement positif (227 trades, 48% win, PF 1.25, +0.14R). Seule piste à creuser. […] valider en walk-forward avant d'y croire. Éviter le cherry-picking d'USDJPY."

**Exaktes Regelwerk aus `forex-research.js` (Funktion `breakoutSignal`, Zeile-für-Zeile rekonstruiert):**

| Komponente | Implementierung im Code |
|---|---|
| **Daten** | Yahoo Finance (`USDJPY=X` u. a.), **H1-Kerzen, 730 Tage** (~2 Jahre), letzte (unfertige) Kerze verworfen |
| **Range-Definition** | High/Low aller H1-Bars mit `getUTCHours() < 7` → **00:00–06:59 UTC** (7 Stunden), gruppiert nach UTC-Kalendertag |
| **Zeitzone** | **UTC, kein DST-Handling** (Yahoo-Timestamps sind Unix/UTC) |
| **Trigger-Fenster** | Stunden **07:00–16:59 UTC** (`hour >= 7 && hour < 17`) — deckt London + NY-Overlap ab |
| **Entry** | **Market zum Close der ersten H1-Kerze**, die jenseits der Range schließt (`close > rangeHigh` → Long; `close < rangeLow` → Short). **KEINE Stop-Orders, kein Retest, kein Buffer** |
| **Stop-Loss** | **Gegenseite der Range** (Long: SL = Range-Low). Risiko = Entry − RangeLow, d. h. **volle Range + Overshoot der Trigger-Kerze** |
| **Take-Profit** | **1.5 × Risiko** (`tp = entry + 1.5 * risk`) |
| **Trade-Limit** | **1 Trade/Tag/Paar** (`traded`-Set pro UTC-Tag); kein Re-Entry nach SL |
| **Stop-Management** | **Aus** (`beAtR: 0, trailR: 0`) — kein Break-Even, kein Trailing |
| **Time-Exit** | **KEINER** — Position läuft bis SL/TP, ggf. über Nacht / übers Wochenende (!) |
| **Kostenmodell** | `FEE = 0.00015` (1.5 bps) pro Seite, auf Entry+Exit-Preis, in R abgezogen — entspricht engem Spread+Kommission, **kein Slippage-Modell** |
| **Vergleichs-Archetypen (gleiche Engine)** | Mean-Reversion (Bollinger+RSI): −0.22R "mort partout"; Trend D1: −0.07R; Baseline-Trend-Strategie H1: PF 0.91 — **Breakout war der einzige nicht-tote Archetyp** |

**Wichtige Methodik-Lücken des Backtests (selbst bewerten!):**
1. **Yahoo-FX-H1-Datenqualität**: unbekannter Feed, keine echten Spreads, keine Tick-Daten → Slippage am Session-Open nicht modelliert (vgl. DAX-Studie: 3 Pts Slippage → PF 1.25→0.96).
2. **Kein Zeitexit** → Wochenend-Gap-Risiko auf USDJPY (MoF/BoJ-Interventionen!) im Sample enthalten, aber nicht prop-firm-kompatibel.
3. **2 Jahre ≈ ein Regime**: Der Zeitraum (~Mitte 2024–Mitte 2026) enthält den USDJPY-Carry-Unwind Aug 2024, MoF-Interventionen und BoJ-Hiking — ein außergewöhnlich trendiges JPY-Regime.
4. Autor selbst: "**Éviter le cherry-picking d'USDJPY**" und fordert Walk-Forward — wurde im Repo nie gemacht.

---

## 2. Warum USDJPY plausibel funktionieren könnte (Mechanismus-Evidenz)

**Claim:** USDJPY hat strukturelle Gründe, warum der Asian-Range-Breakout dort besser läuft als auf EURUSD/GBPUSD.
**Confidence:** MITTEL (konsistente Mikrostruktur-Argumente, aber kein direkter Kausaltest)

- **JPY ist in Asien zuhause aktiv** — USDJPY ist nicht "asiatische Totstille + London-Explosion" wie EURUSD, sondern hat zwei Aktivitätszentren. 5-Jahres-Stundenstudie (Spot + CME-Yen-Futures-Volumen): "unlike EUR/USD, volatility for USD/JPY is **just as high around the East Asian open as it is the London open**" [^1^]. Tokyo: Spot-USDJPY = **63 % des japanischen Spot-Turnovers** ($462 Mrd./Tag, Apr 2025) [^2^].
- **Tokyo→London-Übergabe als Breakout-Fenster:** Tokyo-London-Overlap **08:00–09:00 GMT** — "The Tokyo session's established ranges often get broken during this crossover as European liquidity floods in. Prime window for breakout traders targeting yen pairs" [^3^]. Tokyo-Fixing **09:55 JST (00:55 UTC)** erzeugt eigene Flow-Spitze [^4^].
- **Höhere ADR = mehr Raum für 1.5R-Ziele:** USDJPY ADR 2025 = **133 Pips = 1,77× EURUSD** (Wide-Report-06, OffbeatForex). Peak-Stunden USDJPY: **00:00–16:00 UTC** durchgehend aktiv (Tokyo + London) [^3^].
- **Carry-/Trend-Dynamik 2024–2026:** BoJ-Normalisierung + Fed-Divergenz erzeugte persistente USDJPY-Trends mit scharfen Unwinds (Aug 2024: −15 Yen in 3 Tagen; MoF-Interventionen Apr/Mai 2024, ~$36 Mrd./$26 Mrd.) [^5^][^6^]. Trendige Regime begünstigen Breakout-Follow-Through — **gleichzeitig ist das ein Regime-Bias des Backtest-Fensters**.
- **Unabhängige Tokyo-ORB-Studie (btcdana, 2023–2024, JPY-Paare, 287 Trades USDJPY):** USDJPY = bestes Paar (WR 51.2 %, +0.08R, maxDD −6.3 %), AUDJPY negativ (−0.15R), EURJPY breakeven — **stützt die USDJPY-Sonderstellung**, allerdings Vendor-Qualität [^7^].

## 3. Reicht die 227-Trade-Stichprobe? — Eigene Signifikanzrechnung

**Claim:** 227 Trades reichen NICHT für statistische Sicherheit; der USDJPY-Befund ist eine Hypothese, kein Edge.
**Source:** eigene Berechnung + fxnx-Stichprobenleitfaden + relaxedtrader-Heuristik
**Confidence:** HOCH (Arithmetik)

- Per-Trade-Verteilung (−1R / +1.5R bei 48 % WR): σ ≈ 1.25R → SE = 1.25/√227 ≈ 0.083R → **t ≈ 1.7, p ≈ 0.047 (einseitig)**. Bereits grenzwertig — und **nach Multiple-Testing-Korrektur über 8 getestete Paare (Bonferroni: p < 0.006) eindeutig NICHT signifikant**.
- **relaxedtrader-Heuristik** (Signifikanzfaktor = PF × √n ≥ 30): 1.25 × √227 = **18.8 → unter Schwelle**, "probably random noise" [^8^].
- **fxnx-Referenz:** Intraday-FX braucht **300–500 Trades über 2–3 Jahre für p < 0.05**; asymmetrische R:R-Systeme brauchen ~doppelte Stichprobe [^9^]. López de Prado via backtestbase: 200–500 Trades **über mehrere Regime** [^10^].
- WR-Konfidenzintervall: 48 % ± 6.5 pp (95 % CI: 41.5–54.5 %) — die Breakeven-WR bei 1:1.5 (40 %) liegt im Intervall.
- **Fazit:** 227 Trades / 2 Jahre / 1 Regime = Hypothesen-Generator. Pflicht: eigener Backtest über **≥10 Jahre** Tick-Daten (mehrere JPY-Regime: 2013–2021 Niedrigvol-Ära inklusive) + Walk-Forward.

---

## 4. Breakout-Retest-Variante (fortraders-Claim) — Verifikationsstatus

**Claim (fortraders):** "Breakout-Retest, best for Forex Majors during London Open. Mark Asian range before 07:00 GMT. Entry: candle close back above/below broken level on retest. Stop: back inside the range. Target: 2× Asian range (2–2.5R). Expected WR 50–60 %, R:R 2.5:1. EURUSD/GBPUSD produce this 3–4×/week." [^11^]
**URL:** https://fortraders.com/blog/5-proven-strategies-to-pass-a-prop-firm-challenge (2026-07-21, Authority C — Vendor/Marketing)
**Confidence für Claim: NIEDRIG — keine unabhängige Verifikation gefunden**

- Gezielte Suche nach unabhängiger Verifikation (myfxbook/Track-Record): **0 Treffer** — der Claim existiert nur als Marketing-Behauptung.
- Zirkulierende Winrate-Zahlen ohne Primärquelle: howtotrade "60–70 %" [^12^], tradingzenith "Studien zeigen: Direkt-Entry 40–50 % vs. Retest 60–70 %; 30–40 % der Breakouts retesten nie" [^13^] — beide **ohne zitierte Studie**, als Folklore einstufen. beirmancapital "50–90 %" = bedeutungslos breit [^14^].
- **Beste quasi-unabhängige Stütze:** btcdana-Tokyo-ORB-Studie: "Confirmation of the Breakout + Retest method […] **diminished false breakouts by 60 % and reduced trade opportunities by 50 %**" [^7^] — Richtung plausibel, Größenordnung unauditiert.
- **Mechanisches Referenz-Regelwerk (fxglory, D1, 50-Tage-Level — kein Session-Setup, aber sauber kodierbar):** Break-Close 0.10–1.25 × ATR(14) jenseits des Levels; Retest-Fenster ≤ 10 Bars; Retest-Zone 0.15 × ATR um das Level; Bestätigungskerze (in Zone getaucht, Close jenseits Level, Close über Open); Entry nächstes Open; SL hinter Retest-Extrem + 0.25 × ATR; Ziel 2R; Failure-Exit bei Close zurück durchs Level; Max-Haltedauer 25 Bars [^15^]. Als Vorlage für die H1-Session-Adaption nutzbar.
- Open-Source-Code-Referenz: GitHub wwakeford/breakout-retest-backtest (Python, Aktien; Sample 28 Trades, WR 64 % — Spielzeug-Stichprobe, nur als Code-Vorlage) [^16^].
- **Konsens-Trade-off (3 Quellen übereinstimmend):** Retest = höhere Trefferquote + engerer Stop, aber "Missed-Move-Risiko" — die stärksten Breakouts retesten nie; Hybrid (½ Direkt + ½ Retest) als Kompromiss [^13^][^17^].

---

## 5. Filter-Kandidaten zur PF-Verbesserung (mit Evidenzgrad)

| Filter | Evidenz | Effekt (Quelle) | Confidence |
|---|---|---|---|
| **Volatilitäts-/ATR-Filter** (nur handeln wenn ATR(14,D1) > 20-Tage-Ø) | btcdana 2-Jahres-Studie USDJPY | WR 51.2→**58.7 %**, Expectancy +0.08R→**+0.32R**; ATR<65 Pips → WR 39 %, ATR>80 Pips → WR 64 %; "reduced losing trades by 40 %" [^7^] | MITTEL (Vendor, aber detailliert & konsistent) |
| **Range-Größen-Band** (Min + Max!) | btcdana + newyorkcityservers + forexforstarters | Zu eng (<15–20 Pips USDJPY): WR 43 %, Fakeout-Serien 8–10 Verluste; >35 Pips (30-Min-Range Tokyo): WR 61 % [^7^]. Zu breit (>60 Pips EURUSD / >80 GBPUSD Asian Range): Skip — "London hat nicht genug Energie" [^18^][^19^]. **→ Band-Filter: z. B. 20 Pips ≤ Range ≤ 0.5×ADR** | MITTEL (Achtung: Min- und Max-Evidenz stammt aus versch. Studien/Session-Definitionen) |
| **HTF-Trend-Alignment** (nur Longs über EMA200-H4/D1) | btcdana + Trade-Desk (eigene Crypto-Erfahrung) + luxalgo | USDJPY WR → **56.3 %** (4H-EMA200) [^7^]; Trade-Desk: MTF-Filter war "single biggest edge lift" auf H1 [^20^]; luxalgo-Warnung: Filter laggt an Wendepunkten, nur geschlossene HTF-Bars lesen (Repainting!) [^21^] | MITTEL-HOCH (mehrere unabhängige Richtungsbestätigungen) |
| **Wochentag** | btcdana + forexforstarters + newyorkcityservers | Montag schlechtester Tag (WR 44 %, Gap-Unsicherheit); **Mi/Do best (53 %)** [^7^]; Di–Do "cleaner breakouts", Fr Position-Squaring [^19^][^18^] | MITTEL |
| **News-Filter** (Skip bei Red-Folder USD/JPY in 1. London-Stunden) | fxnx + newyorkcityservers + Prop-Regeln | "Trading directly into a high-impact news event is gambling" [^22^]; FTMO-Funded ±2 Min Blackout ohnehin Pflicht [^18^] | HOCH als Regel, NIEDRIG als Edge-Beleg (kein quantifizierter Backtest gefunden) |
| **Entry-Buffer / Close-Bestätigung** | newyorkcityservers + fxnx | 3–5 Pips Buffer über/unter Range (GBPJPY 7–10) gegen Wick-Fakeouts; alternativ Body-Close jenseits der Range statt Pending-Order [^18^][^17^] | MITTEL |
| **Session-Fenster-Fokus Tokyo→London (07:00–09:00 GMT)** | btcdana | Overlap-Trades WR **59 %** vs. 49 % reine Tokyo-Session [^7^] | MITTEL |

---

## 6. Walk-Forward-Design & Parameter-Räume

**Methodik-Referenzen:** TradersPost WFO-Guide (IS/OOS-Fenster, "Stabilität über Peak-Profit", Plateau-Regel) [^23^]; arongroups (breite logische Ranges, Flat-Top-Test) [^24^]; relaxedtrader (OOS-PF/IS-PF > 0.7; PF×√n ≥ 30) [^8^]; forextester (ein Parameter pro Iteration, Walk-Forward über Jahre) [^25^].

**Empfohlenes WFO-Protokoll für diesen Bot:**
- **Fenster:** 12 Monate IS / 3 Monate OOS, rollierend, gestitchte OOS-Equity als einzige Wahrheit. Bei ~110 Trades/Jahr/Paar → IS ≈ 110 Trades (Minimum), besser 24 Monate IS für ≥ 200 Trades.
- **Selektionskriterium im IS:** nicht Max-Profit, sondern Plateau (Nachbarparameter ±1 Stufe ebenfalls PF > 1.2) + OOS-PF/IS-PF > 0.7 + PF×√n ≥ 30.
- **Kostenmodell Pflicht:** Spread + Kommission + **Slippage-Stressmatrix 0/1/2/3 Pips pro Fill** (DAX-Präzedenzfall: PF 1.25 → 0.96 bei 3 Pts [^26^]); Entry am Session-Open = Spread-Widening einpreisen [^19^].
- **Regime-Abdeckung:** Daten ab ≥ 2014 (enthält USDJPY-Totvol-Ära 2016–2019, ADR ~60–80 Pips vs. 133 heute) — sonst ist der "Edge" nur das BoJ-Hiking-Regime.

**Parameter-Raum (Grid):**

| Parameter | Werte | Begründung |
|---|---|---|
| `range_start_utc` | 00:00 / 01:00 / 02:00 | Trade-Desk 00:00; newyorkcityservers 02:00–06:00-Variante filtert frühe Asia-Spikes [^18^] |
| `range_end_utc` | 06:00 / 07:00 / 08:00 | Trade-Desk 07:00; London-Open 08:00 (Summer: 07:00 UTC = London 08:00 BST!) — **DST-Entscheidung bewusst treffen** |
| `entry_mode` | close_trigger / stop_order(buffer 0/3/5 pips) / retest | 3 Archetypen A/B-testen (Retest-Regeln nach fxglory adaptiert [^15^]) |
| `trigger_end_utc` | 10:00 / 12:00 / 17:00 | Trade-Desk 17:00; klassisch 10:00 Cancel [^18^]; Overlap-Fokus 09:00 [^7^] |
| `rr` | 1.5 / 2.0 / 2.5 | Ziel ≥ 1:2 für Projekt-Vorgabe; Trade-Desk 1.5 |
| `range_min_pips` | 0 / 15 / 20 / 25 | Fakeout-Filter enger Ranges [^7^] |
| `range_max` | 0.4× / 0.5× / 0.6× ADR(14,D1) (≈ 55/65/80 Pips) | Breite-Range-Skip [^18^][^19^] |
| `atr_filter` | off / ATR14(D1) > Ø20d | Stärkster dokumentierter Filter [^7^] |
| `htf_filter` | off / EMA200-H4 / D1-Close vs. EMA200-D1 | [^7^][^20^][^21^] |
| `skip_weekdays` | none / Monday / Monday+Friday | [^7^][^19^] |
| `news_filter` | off / skip Red-Folder (USD+JPY) Tage vor 15:00 UTC | Prop-Pflicht + Fakeout-Vermeidung [^22^] |
| `time_exit_utc` | none / 17:00 / 21:00 / Fr-Close | **Prop-Pflicht** (Trade-Desk hat keinen — übernimmt Wochenend-Gap!) |
| `break_even_at_r` | off / 1.0 | Trade-Desk-Crypto-Erfahrung: BE@1R schnitt Avg-Loss auf 0.67R; Trailing lieber aus (killt 2R-Winner) [^20^] |

**Zeitzonen-Warnung (kritisch für MT5-Umsetzung):** >90 % der MT4/MT5-Broker laufen auf GMT+2/+3 (NY-Close-Alignment); DST-Wechsel US ≠ EU erzeugt 2–3 Wochen/Jahr 1-h-Versatz; "Sunday-Candle"-Problem verzerrt D1-Indikatoren. Yahoo-Daten (Trade-Desk) sind UTC — **Backtest- und Live-Zeit müssen explizit auf dieselbe Referenz (empfohlen: UTC, DST-aware via US/EU-Regeltabelle oder MQL5 DealingWithTime-Lib) gemappt werden**, sonst handelt der Bot ein anderes Setup als der Backtest [^27^][^28^].

---

## 7. IMPLEMENTIERUNGS-SPEZIFIKATION (Pseudo-Code, Bot-Blaupause)

```
# === BOT: USDJPY Asian-Range-Breakout (Baseline = Trade-Desk-Replik + Filter) ===
INSTRUMENT   = USDJPY            # Sekundär testen: EURJPY, GBPJPY (Overlap-Logik), NICHT EURUSD/GBPUSD roh
TIMEFRAME    = H1 (Range/Trigger), M15 optional für Retest-Entry
TZ_REFERENCE = UTC, DST-aware mapping (broker server time -> UTC)

# --- Tägliches Setup (nach 07:00 UTC Range-Close) ---
range_high = max(high) of bars where 00:00 <= utc_hour < 07:00
range_low  = min(low)  of bars where 00:00 <= utc_hour < 07:00
range_size = range_high - range_low

# --- Pre-Trade-Filter (ALLE müssen passieren, sonst SKIP) ---
if weekday in {Sat, Sun, Monday}:                 skip   # DoW-Filter (parametrierbar)
if japanese_holiday or red_folder_news(USD|JPY before 15:00 UTC): skip
if range_size < 20 pips:                          skip   # Fakeout-Zone [btcdana]
if range_size > 0.5 * ADR(14, D1):                skip   # zu breit -> kein Follow-Through
if ATR(14, D1) < SMA(ATR(14,D1), 20):             skip   # Volatilitätsfilter [btcdana]
htf_bias = sign(close_D1 - EMA200_D1)             # nur geschlossene D1-Bars! (Repainting)

# --- Entry (Variante A: Close-Trigger = Trade-Desk-Baseline) ---
if 07:00 <= utc_hour < trigger_end and not traded_today:
    if H1.close > range_high and htf_bias >= 0:   long  at market (close)
    if H1.close < range_low  and htf_bias <= 0:   short at market (close)
    traded_today = True                            # 1 Trade/Tag, kein Re-Entry

# --- Entry (Variante B: Retest, A/B-Test) ---
# after breakout close beyond range: wait max 6 x M15 bars for pullback into
# zone [range_high - 0.15*ATR14_H1, range_high]; enter on rejection-candle close
# back beyond level; SL = retest_extreme -/+ 0.25*ATR; cancel if no retest in 6 bars.

# --- Exits ---
sl     = opposite side of range                    # Long: SL = range_low
tp     = entry + 2.0 * (entry - sl)                # Ziel 1:2 (Projekt-Vorgabe); Grid 1.5/2.0/2.5
time_exit = 21:00 UTC same day                     # NEU vs. Trade-Desk: prop-tauglich, kein Overnight/Weekend
friday: flat by 21:00 UTC                          # FTMO-Standard
break_even: move SL to entry at +1R                # Grid: off/on

# --- Risk / Prop-Layer ---
risk_per_trade = 0.5 % equity                      # Prop-konform
daily_loss_halt = -1.5 % equity -> halt until next day
max_trades_day  = 1
news_blackout(FTMO-funded): no open/close +/- 2 min around red events

# --- Kostenmodell im Backtest (PFLICHT) ---
spread = real tick spread; commission = $3/side/lot
slippage_stress = [0, 1, 2, 3] pips per fill -> PF-Matrix reporten
accept only if PF(stress=2 pips) > 1.3 and OOS_PF/IS_PF > 0.7 and PF*sqrt(n) >= 30
```

**Replikations-Reihenfolge (empfohlen):**
1. Trade-Desk-Setup 1:1 nachbauen (UTC, 00–07 Range, 07–17 Trigger, 1.5R, kein Filter, kein Zeitexit) auf **MT5-Broker-Tick-Daten ≥ 2014** → prüfen, ob PF 1.25 auf echten Daten überhaupt reproduziert (Yahoo-Artefakt-Risiko).
2. Zeitraum-Sensitivität: 2014–2019 (Niedrigvol) vs. 2020–2022 vs. 2023–2026 separat — erwarteter Befund: Edge konzentriert im BoJ-Hiking-Regime → dann Regime-Filter Pflicht, sonst verwerfen.
3. Filter einzeln addieren (ATR > HTF > Range-Band > DoW > News), jeweils Plateau-Check.
4. Retest-Variante B parallel als eigenes Archetypen-Experiment (fortraders-Claim ist unverifiziert — selbst messen: Retest-Rate, WR-Delta, Missed-Move-Kosten).
5. Erst dann WFO + Slippage-Stress + Demo-Forward ≥ 3 Monate.

---

## 8. Fazit / Einordnung

1. **Trade-Desk-Regelwerk vollständig extrahiert** (Primärcode): Range 00:00–06:59 UTC, H1-Close-Trigger 07:00–16:59 UTC, SL = Range-Gegenseite, TP 1.5R, 1 Trade/Tag, kein Zeitexit, 1.5 bps/Seite, Yahoo-H1 730 Tage. [^20^]
2. **Der PF-1.25-Befund ist statistisch dünn**: t ≈ 1.7, überlebt keine 8-Paare-Multiple-Testing-Korrektur; Signifikanzfaktor 18.8 < 30; ~1 Regime. Als Hypothese wertvoll, als Edge unbewiesen.
3. **USDJPY-Sonderstellung mechanistisch plausibel** (Tokyo-Heimataktivität, 08:00–09:00-GMT-Übergabe, 133-Pip-ADR, Carry-Trend-Regime) und durch eine zweite (schwächere) Studie gestützt [^7^] — aber Regime-Abhängigkeit ist das Hauptrisiko.
4. **fortraders-Retest-Claim (50–60 % WR, 2.5:1) ist unverifiziertes Marketing** — keine unabhängige Bestätigung auffindbar; Retest-Mechanismus selbst ist mehrfach plausibilisiert (Fakeout-Reduktion ~60 %, Trade-Count −50 % [^7^]) und muss selbst getestet werden.
5. **Stärkster dokumentierter PF-Hebel: ATR-Volatilitätsfilter** (+0.24R Expectancy), danach HTF-EMA200 und Wochentag/Overlap-Fokus. News-Filter ist Prop-Pflicht, Edge-Beleg fehlt.
6. **Zwei Fallstricke vor Code-Start:** Zeitzonen/DST (UTC-Backtest vs. GMT+2/+3-Broker) und Slippage-Sensitivität (DAX-Präzedenz PF 1.25→0.96) — beide gehören in Tag-1-Architektur, nicht nachträglich.

---

## Quellen

[^1^]: https://bestbrokerdeals.com/forex-knowledge-base/the-best-time-to-trade-the-japanese-yen/ (5-Jahres-Stundenstudie USDJPY, Spot + CME-Futures)
[^2^]: https://www.defcofx.com/tokyo-session-forex-pairs/ (2025-10-01; Japan Spot-Turnover Apr 2025)
[^3^]: https://newyorkcityservers.com/blog/best-time-to-trade-forex (2026-02-16; Session-Overlap-Tabelle, Peak-Hours)
[^4^]: https://fibalgo.com/education/usdjpy-trading-strategy-session-based-risk-framework (2026-02-16; Tokyo-Fixing 09:55 JST, Exporter-Flows)
[^5^]: https://www.mdpi.com/2227-9091/14/3/46 (2026-02-26; Carry-Unwind Aug 2024, MDPI Risks — akademisch)
[^6^]: https://hoge.gg/japans-carry-trade-unwind-is-not-done-the-yen-tells-you-when/ (2026-07-23; MoF-Interventions-Tabelle 2024/25)
[^7^]: https://www.btcdana.com/magazine/blog/177 (2026-05-07; 2-Jahres-Tokyo-ORB-Studie USDJPY/AUDJPY/EURJPY, ATR-/Retest-/DoW-Filter — Vendor, detailliert)
[^8^]: https://relaxedtrader.com/out-of-sample-testing/ (2026-07-27; PF×√n ≥ 30, OOS/IS > 70 %)
[^9^]: https://fxnx.com/en/blog/backtest-sample-size-how-many-trades-make-results-real (2026-08-23)
[^10^]: https://www.backtestbase.com/education/how-many-trades-for-backtest (2026-01-04; López de Prado 200–500 Trades)
[^11^]: https://fortraders.com/blog/5-proven-strategies-to-pass-a-prop-firm-challenge (2026-07-21; Breakout-Retest-Claim)
[^12^]: https://howtotrade.com/trading-strategies/break-and-retest/ (2024-08-12; "60–70 %" unbelegt)
[^13^]: https://tradingzenith.net/artigos/forex-breakout-false-breakout (2026-03-15; Retest-Statistik-Folklore, Missed-Move 30–40 %)
[^14^]: https://beirmancapital.com/best-break-and-retest-strategy/ (2025-07-07)
[^15^]: https://fxglory.com/learn/forex-strategies/break-and-retest-strategy-forex/ (2026-07-02; mechanisches D1-Regelwerk mit ATR-Zonen)
[^16^]: https://github.com/wwakeford/breakout-retest-backtest (2025-07-24; Python-Code-Referenz)
[^17^]: https://fxnx.com/en/blog/forex-breakout-trading-anti-fakeout-guide (2026-08-31; Direkt vs. Retest, Hybrid-Ansatz)
[^18^]: https://newyorkcityservers.com/blog/london-breakout-strategy (2026-02-14; Range-Max 60/80 Pips, Buffer 3–5, Cancel 10:00, Skip-Regeln)
[^19^]: https://forexforstarters.com/strategies/breakout/asian-range-breakout/ (o.D.; Filter-Liste, USDJPY-Anmerkung, Spread-Widening)
[^20^]: https://github.com/WalterVeriza/Trade-Desk (README + ROADMAP.md + backend/scripts/forex-research.js, 2026-06-23, archiviert 2026-08-21)
[^21^]: https://www.luxalgo.com/library/concept/higher-timeframe-trend-filter/ (o.D.; HTF-Filter-Trade-offs, Repainting-Warnung)
[^22^]: https://fxnx.com/en/blog/london-open-first-candle-breakout-strategy-guide (2026-05-13; Red-Folder-Regel)
[^23^]: https://blog.traderspost.io/article/walk-forward-optimization-trading-guide (2026-07-10)
[^24^]: https://arongroups.co/forex-articles/walk-forward-optimisation-in-trading/ (2026-02-12; Plateau-/Flat-Top-Regel)
[^25^]: https://forextester.com/blog/breakout-trading-strategy/ (2025-12-04; Iterationsdisziplin)
[^26^]: https://fxvps.biz/blog/dax-opening-range-breakout-14-year-study/ (via Wide-Report-01; Slippage-Matrix)
[^27^]: https://mt4programming.com/mt4-timezone-tutorial-build-a-dst-aware-ea-in-6-steps/ (2026-06-10; GMT+2/+3, Sunday-Candle)
[^28^]: https://www.vpsforextrader.com/blog/what-is-ict-in-trading-a-comprehensive-guide/ (2026-07-20; DST-Tabellen, DealingWithTime-Lib)

*Methodik-Hinweis: 18 Suchqueries (EN/DE) + Volltext-Zugriff auf den Trade-Desk-Backtest-Code (Primärquelle). Eigene Signifikanzrechnung via scipy. Härteste Datenpunkte: Trade-Desk-Primärcode, MDPI-Carry-Paper, bestbrokerdeals-Stundenstudie. Schwächste (als Marketing markiert): fortraders, btcdana, tradingzenith, pinescriptforge.*
