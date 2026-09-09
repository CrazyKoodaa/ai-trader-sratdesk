# Deep-Dive 02: VWAP-Pullback NAS100/US100 Morning-Window-Strategie (M5, 9:45–11:30 ET)

**Recherche-Datum:** 2026 | **Eigene gezielte Suchen:** 16 Queries (EN/DE) + 5 Deep-Reads (web_open_url)
**Kontext:** 5 Python-Bots für MT5 (pymt5trade/MetaTrader5-API), Ziel PF > 1.5 OOS, RR ≥ 1:2, Prop-Firm-tauglich (EOD-DD → Intraday-only). Referenzen: trading_strategies_wide01/03/06.md.

---

## 1. ORIGINALQUELLE DES BACKTESTS (PF 2.08 / 312 Trades)

**Claim:** Der im Wide-Report zitierte VWAP-Pullback-Backtest stammt von PineGen.ai (Tool-Anbieter für Pine-Script-Generierung). Mechanischer Test QQQ 5M, 06.01.2024–30.06.2025 (18 Monate), non-repainting (`barstate.isconfirmed` auf jeder Signal-Evaluation), Kommission $0,02/Aktie/Side, 100 Shares fix, kein Compounding. Gesamt: 312 Trades, PF 1.54, WR 52,6 % (164W/148L), Net +$11.230, MaxDD 9,8 %, Ø Win +$198 / Ø Loss −$143 (Asymmetrie 1,38:1). **Zeitfenster-Breakdown: 9:45–11:30 ET = 186 Trades, PF 2.08, WR 62,4 %, +$17.190; Midday PF 0.69; Nachmittag PF 0.53; alle 126 Trades nach 11:30 aggregiert −$5.960.** Bester Monat Nov 2024 (+$2.840), schlechtester Apr 2024 (−$1.120), längste Verlustserie 8 Trades (Aug 2024, Yen-Carry-Unwind). [^1^]
**Source:** PineGen.ai Case Study | **URL:** https://www.pinegen.ai/resources/pine-script-user-case-studies/vwap-pullback-strategy-qqq-backtest | **Date:** 08.07.2026
**Excerpt (exaktes Regelwerk, Abschnitt 4):** "Long setup: QQQ must have closed at least three consecutive 5-minute bars above VWAP since the 9:45 AM bar … Entry trigger — Long: Price pulls back to touch VWAP and RSI(2) drops below 25 … Enter on the next 5-minute bar that closes green and holds above VWAP. Short: RSI(2) above 75, next red bar closing below VWAP. Stop loss: 1.5x ATR(14-period) from entry price, placed below VWAP for longs and above VWAP for shorts. Profit target: Previous session's high for longs, previous session's low for shorts. If already exceeded: 2x ATR from entry. Session rules: No trades before 9:45 AM Eastern … No trades after 3:00 PM Eastern. Maximum one long and one short entry per session."
**Excerpt (VWAP-Anchor):** "VWAP resets at the session open every day. It is calculated cumulatively from 9:30 AM Eastern."
**Excerpt (vorgeschlagene, NICHT getestete Modifikationen):** "9.1 Restrict entries to 9:45–11:30 AM only … 9.2 Only take entries when QQQ is at least 0.4 % above the session VWAP at the time of the pullback … 9.3 Only take short setups on sessions where QQQ's first 30-minute bar closed below the previous day's closing price."
**Confidence:** HOCH für die Regel-Extraktion (Primärquelle vollständig gelesen); **MITTEL für die Performance-Zahlen** — Vendor-Quelle (verkauft Pine-Script-Tool), keine unabhängige Replikation gefunden, Testperiode überwiegend Bullenmarkt. Zahlen als Hypothese, nicht als validierte Edge behandeln.

**Ergänzende Evidenz zur Zeitfenster-These:**
**Claim:** NAS100-Volatilität konzentriert sich strukturell auf das Cash-Open-Fenster: Stündliche ATR-Expansion +310 % gegenüber Pre-Market ab 09:30 ET; typische 5-Min-Kerze 13:35 UTC = 60–90 Punkte; das 13:30–15:30-UTC-Fenster (= 9:30–11:30 ET) ist das liquideste des Tages. [^2^][^3^]
**Source:** FXNX (2 Artikel) | **URLs:** https://fxnx.com/en/blog/ict-killzone-volatility-data-average-range-session-hour (23.08.2026), https://fxnx.com/en/blog/index-cfd-volatility-hour-ranges-compared-side-side (02.09.2026)
**Confidence:** MITTEL (Broker-nahe Content-Sites, aber konsistent mit wide06 [^462^]: 3-Phasen-ATR-Zyklus, Peak 09:30–11:30 ET).

**Claim (Gegenprobe/Risiko):** Dieselbe VWAP-Pullback-Logik auf 4H-Krypto (StrategyVerdict, 2 Jahre, 5 Coins, 16 Parametersets, OOS-Split): OOS nur 3/5 positiv (BTC PF 2.46 OOS, SOL/XRP negativ); **Trailing-Stop zerstört die Strategie (PF 0.76), fixer 2×ATR-Stop funktioniert**; Parameter-Robustheit 13/16 Zellen positiv (EMA 50–200 × ATR-Mult 1.5–3.0); TP:SL-Sweep 1:1 bis 1:3 alle PF > 1.0 (Peak 1:1.5 und 1:2.5 bei PF 1.29); **auf M5–H1 komplett toxisch (M5 PF 0.22)**. [^4^]
**Source:** StrategyVerdict | **URL:** https://strategyverdict.com/vwap-strategy-backtest-crypto/ | **Date:** 07.07.2026
**Confidence:** MITTEL (transparente Methodik, aber Krypto ≠ QQQ; wertvoll als Methodik-Template für Parameter-Plateaus und Exit-Sweeps).

**Claim (Zweitstudie QQQ):** VWAP-Trend-Trading QQQ 2018–2023: 671 % Return, Sharpe 2.1, MaxDD 9,4 % vs. Buy&Hold 126 %/DD 37 % — aber WR nur 17 % (payoff-getrieben, kein Pullback- sondern Trend-Folge-Setup). [^5^]
**Source:** quantbuffet.com | **URL:** https://quantbuffet.com/2024/04/17/volume-weighted-average-price-vwap-as-precise-trend-following-indicator-for-day-traders/ | **Date:** 17.04.2024
**Confidence:** MITTEL-NIEDRIG (Blog-Backtest, Details dünn; stützt nur Richtung "VWAP-Edge auf QQQ existiert").

---

## 2. ÜBERTRAGBARKEIT QQQ → NAS100/US100-CFD AUF MT5

### 2.1 Tick-Volumen statt echtem Volumen

**Claim:** Auf MT5-CFDs ist `VOLUME_REAL` für OTC-Instrumente praktisch immer 0; jeder Volumen-basierte Indikator rechnet mit `VOLUME_TICK` (Anzahl Quote-Updates pro Bar). Damit wird VWAP faktisch zu einem **tick-gewichteten** VWAP. Tick-Volumen korreliert laut Caspar-Marney-Analyse (2011, eSignal/EBS/Hotspot) zu >90 % mit realem FX-Volumen auf Majors — aber: (a) Studie betrifft FX, nicht Index-CFDs; (b) Tick-Zählung ist broker-feed-abhängig (Market-Maker-Feeds mit geringerer Granularität verzerren); (c) Spread-Weitungen ohne Trade erzeugen Ticks; (d) an Range-Extremen erzeugt Market-Maker-Quote-Churn falsche "Akkumulations"-Signale. [^6^][^7^][^8^]
**Sources:** FXNX "XAUUSD Tick Volume on MT5" (15.08.2026, https://fxnx.com/en/blog/xauusd-tick-volume-mt5-what-bars-actually-count); ForexFactory-Thread mit Marney-Zitat (https://www.forexfactory.com/thread/463566-does-volume-of-mt4-show-the-tick-volume); TradingWyckoff (23.05.2026, https://tradingwyckoff.com/en/tick-volume-vs-real-volume/)
**Excerpt:** "Retail CFD brokers almost universally set VOLUME_REAL to zero … While Tick-VWAP often mirrors true VWAP during normal trending conditions, it breaks down completely around range extremes." / "Elegant solution: analyze the future's real volume (6E) and trade the CFD (EURUSD) — arbitrage makes them move identically."
**Implikation für den Bot:** Tick-VWAP auf US100 ist im Morning-Window (höchste Tick-Dichte des Tages) am **wenigsten** verzerrt — der Zeitfilter der Strategie mildert das Tick-Volumen-Problem ab. Optionaler Qualitäts-Boost: VWAP aus NQ-Futures-Echt-Volumen (z. B. via Dukascopy/externem Feed) berechnen und auf den CFD anwenden. **Confidence: HOCH (Mechanik), MITTEL (90-%-Korrelation auf NAS100-CFD übertragbar).**

### 2.2 Zeitumrechnung ET → Serverzeit (kritischster Implementierungspunkt)

**Claim:** MT5-Charts/Timestamps laufen ausschließlich in **Broker-Serverzeit** (nicht änderbar); die meisten FX/CFD-Broker inkl. FTMO verwenden GMT+2 (Winter) / GMT+3 (Sommer), damit die Tageskerze am NY-Close schließt. FTMO-Server: "GMT+2 with DST" (FTMO US / OANDA-Server); IC Markets bestätigt GMT+2/+3. Die Python-MetaTrader5-API (`copy_rates_*`) liefert **timezone-naive Serverzeit**, nicht UTC. [^9^][^10^][^11^]
**Sources:** ThePayoutReport FTMO-US-MT5-Guide (20.03.2026, https://thepayoutreport.com/ftmo-us-mt5-setup-guide-servers-symbols-settings/); IC Markets DE Handelszeiten (14.11.2025, https://www.icmarkets.eu/de/trading-pricing/trading-hours); pdmt5-Doku (10.08.2026, https://pypi.org/project/pdmt5/ — "Returned datetimes are timezone-naive server time, not UTC")

**Claim (DST-Falle):** US und EU stellen zu **unterschiedlichen Terminen** um (2026: US 08.03.–01.11., EU/UK 29.03.–25.10.). In den Mismatch-Wochen (08.–28.03. und 25.10.–01.11.2026) verschiebt sich 9:30 ET relativ zur Serverzeit um 1 Stunde. Hardcodierte Offsets ("9:45 ET = 15:45 Server") sind in diesen Wochen **falsch** — klassischer Backtest-/Live-Fehler bei Session-Strategien. [^12^][^13^]
**Sources:** Chartmini (29.07.2026, https://chartmini.com/blog/best-time-to-trade-forex); MT4Programming DST-EA-Tutorial (10.06.2026, https://mt4programming.com/mt4-timezone-tutorial-build-a-dst-aware-ea-in-6-steps/ — "Hardcoded offsets eventually fail when DST transitions occur"; Empfehlung: Backtests über bekannte DST-Transitionen prüfen)
**Konsequenz für Python-Bot:** NIE Serverzeit hart kodieren. Umrechnung über IANA-Zonen: `server_time → UTC → America/New_York`. Der Server-UTC-Offset muss **laufend aus der Differenz `symbol tick time (server)` vs. UTC** bestimmt werden (nicht aus der Systemuhr — unter Wine/Linux ist die lokale Zeitzonen-Registry unzuverlässig, bekannte Wine-`find_reg_tz_info`-Fehler). [^14^] Da Bar-Timestamps vom Server kommen, ist der Bot unter Wine funktional sicher, solange alle Zeitlogik serverbasiert rechnet. **Confidence: HOCH.**

**Umrechnungstabelle (Normalfall vs. Mismatch):**

| Periode | Serverzeit (GMT+2/+3-Schema) | 9:45 ET = Server | 11:30 ET = Server |
|---|---|---|---|
| Beide Winter (Nov–Mär) | GMT+2 | 16:45 | 18:30 |
| Beide Sommer (Apr–Okt) | GMT+3 | 16:45 | 18:30 |
| US-Sommer/EU-Winter (08.–28.03.2026) | GMT+2 | 16:45 → **falsch wäre 15:45** | … |
| EU-Sommer/US-Winter (25.10.–01.11.2026) | GMT+3 | 16:45 → **falsch wäre 17:45** | … |

(Merksatz: Bei GMT+2/+3-Servern ist 9:45 ET im Gleichlauf immer 16:45 Server; nur in den ~5 Mismatch-Wochen/Jahr weicht es ab. Bot muss das dynamisch auflösen.)

### 2.3 Spread-/Kostenbild US100

**Claim:** Typische NAS100-CFD-Spreads (Peak-Hours): IC Markets 0,6–1,2 Pkt., Vantage 1,0, Pepperstone 1,0, XM US100Cash 1,1, FP Markets 0,4 (+$3/Lot Raw), IG 0,1 (Wall Street, spread-betting); BrokerChooser-Median getesteter Broker 0,4–1,0 Pkt., kommissionsfrei. Wide-Report: 0,7–1,5 Pkt. + $3/Side. Am Cash-Open (erste 1–2 Min) Spread-Weitung + Slippage — die Strategie startet bewusst erst 9:45 ET, also nach der Normalisierung. [^15^][^16^][^2^]
**Sources:** TradersTrusted (27.07.2025, https://traderstrusted.com/trading-intelligence/brokers/best-forex-broker-for-nasdaq/); BrokerChooser NAS100-Fee-Tabelle (06.05.2026); FXLeaders Broker-Tabellen (24.08.2026, https://www.fxleaders.com/forex-brokers/nasdaq-100-brokers/)
**Kosten-Einordnung:** NAS100 5M-ATR(14) im Morning-Window ≈ 37 Pkt. (Skyanalyst-Kalibrierung, 06.05.2026: 5m ATR 37 / 15m 50 / 60m 76,6 Pkt. [^17^]) → SL 1,5×ATR ≈ 55 Pkt. 1 Pkt. Spread ≈ 1,8 % des Risikos pro Trade — vernachlässigbar. **Aber:** QQQ-Test hatte $0,02/Share ≈ 0,004 % — CFD-Kosten relativ ähnlich klein. Slippage-Stresstest (±2–5 Pkt.) trotzdem Pflicht (Lektion DAX-ORB: 3 Pkt. Slippage killt PF 1.25→0.96 [wide01 ^155^]). **Confidence: HOCH (Spreads), MITTEL (ATR-Punktwerte — regimeabhängig, 2024–26 gestiegene Vol).**

### 2.4 Instrumenten-Basis QQQ ↔ US100-CFD

**Claim:** QQQ (ETF, 9:30–16:00 ET + Pre/Post-Market) vs. NAS100-CFD (quasi 24/5, folgt NQ-Future inkl. Fair-Value-Basis) vs. NQ-Future (CME, $20/Pkt., 23h). Konsequenzen: (1) Absolute Preislevel nicht übertragbar (QQQ ~$500 vs. US100 ~20.000+) → alle %- und ATR-basierten Regeln übertragen, keine Punkte; (2) "Previous session high/low" auf dem CFD neu definieren (CFD-RTH-Session vs. QQQ-RTH: CFD hat Overnight-Handel, Vortages-High des CFD ≠ QQQ-Vortages-High); (3) VWAP-Anchor: CFD hat kein "9:30-Reset" von Natur aus → Bot muss Session-VWAP selbst ab 9:30 ET kumulieren (RTH-Anchor, Standard-Praxis [^18^]); (4) Pre-Market-VWAP unzuverlässig (dünnes Volumen) [^18^]. [^19^][^20^]
**Sources:** FXNX QQQ-vs-NAS100-Guide (11.03.2026, https://fxnx.com/en/blog/nasdaq-100-day-trading-qqq-nas100-guide); NinjaTrader NQ-Specs (https://www.ninjatrader.com/futures/futures-contracts/equity-index/e-mini-nasdaq/); TradeZella VWAP-Guide (28.08.2026, https://www.tradezella.com/blog/vwap-trading-strategy — "VWAP resets at the start of every regular trading session (9:30 AM ET)… During pre-market hours, VWAP data is unreliable")
**Confidence: HOCH.**

---

## 3. ALTERNATIV-/ERWEITERUNGSVARIANTEN

### 3.1 FTMO-eigenes US100-Setup: 15-Min-OR + FVG (2:1 RR)

**Claim (vollständiges Regelwerk aus Primärquelle extrahiert):** (1) Opening Range = High/Low der ersten 15-Min-Kerze ab 15:30 CET (= 9:30 ET); (2) auf M5 wechseln, Breakout nur bei **M5-Schlusskurs** jenseits der Range (Wick zählt nicht); (3) kein Sofort-Entry — Limit-Order an der nächsten Kante des jüngsten **Fair Value Gaps**, das der Breakout-Impuls erzeugt hat; (4) SL hinter der Mittelkerze des FVG; (5) TP fix 2:1 RR. Filter: steigendes Volumen am Breakout, Lage vs. Vortages-High/Low, VWAP-Seite (Long nur über VWAP), Skip bei extrem weiter Opening Range. [^21^]
**Source:** FTMO Blog | **URL:** https://ftmo.com/en/blog/opening-range-breakout-strategy-how-to-master-the-1530-us-session/ | **Date:** 13.05.2026
**Confidence:** HOCH für Regelwerk (Primärquelle); KEINE Performance-Zahlen in der Quelle → Edge unbewiesen, nur plausibel. Synergie mit VWAP-Bot: FVG-Entry kann als **Entry-Verbesserung** des VWAP-Pullbacks dienen (Pullback zur VWAP + FVG-Confluence).

### 3.2 Crabel-ORB auf Nasdaq-Future mit Regime-/Wochentag-Filter (Unger Academy)

**Claim:** NQ, Cash-Session 8:30–15:00 Chicago, OR = High/Low der ersten 30-Min-Bar, Stop-Orders an beiden Seiten, Reverse bei Gegenbreak, EOD-Flat, initiales SL/TP $2.000/$5.000 (Anti-Outlier). Ergebnis roh: 6.190 Trades, Ø Trade zu klein für Kosten. **Regime-Filter "nur Shorts am Freitag"** (dokumentierter Intraweek-Bias: Fr cash-session bärisch, 2010–2024 über alle Subperioden stabil) hob Ø Short-Trade von $30 auf $155; Gesamt-Ø $95. Fazit der Quelle selbst: funktioniert long & short, aber nur mit Filtern, noch nicht live-tauglich. [^22^]
**Source:** Unger Academy | **URL:** https://ungeracademy.com/blog/testing-toby-crabel-s-opening-range-breakout-does-it-really-work-code-backtest-on-nasdaq | **Date:** 17.07.2026
**Confidence:** HOCH (seriöse Trading-Akademie mit offenem Code/ehrlichen Zahlen). Relevanz: Beleg, dass **OR-Bruch auf NAS100 ohne Filter keinen Kosten-Edge hat** — Wochentag-/Regime-Filter sind der Hebel; direkt als Filter-Layer für Bot testbar (Longs Mo–Do, Shorts Fr; vgl. wide06: Mo/Fr komprimiert).

### 3.3 ORB mit Regime-Filter — übergreifende Evidenzlage

**Claim:** Roher ORB auf Index-ETFs/Futures: kein Edge (paperswithbacktest SPY/QQQ/IWM: −1,8 bps nach Upside-Breaks; GitHub XBmosal SPY 3.340 Trades PF 0,96; QuantifiedStrategies: ES/NQ/GC/SI/CL roh negativ). Mit Tagesfilter auf NQ: 198 Trades, WR 65 %, PF 2,0 (Filter nicht offengelegt). Zarattini/Aziz-Edge (Sharpe 2.81) liegt im "Stocks-in-Play"-Selektionsfilter. [wide01 ^33^/^35^/^152^/^243^]
**Confidence:** HOCH (mehrere unabhängige Replikationen). Konsequenz: ORB nur als **Variante B** mit explizitem Regime-Layer (Gap-Size, Vortages-Trend, Wochentag, VIX/ATR-Regime).

---

## 4. PARAMETER-RÄUME FÜR WALK-FORWARD

Methodik-Anker: Kaufman-Übersetzung für Intraday — IS 3–6 Mon. / OOS 1 Mon., rollierend; ≥500-Trade-Sample ideal, min. 6–12 Mon. Intraday-Daten [^23^]; Connors-RSI(2)-Robustheit: Walk-Forward über Schwellen 4–12 bestätigte Nicht-Curve-Fitting [^24^]; StrategyVerdict-Praxis: Parameter-Plateau-Test (13/16 Zellen positiv = gesund), TP:SL-Sweep über 1:1–1:3 [^4^]; Overfitting-Warnung Intraday: 600k+ M1-Bars laden zu Scheinmustern ein → 60/40-Split + Parameter-Minimalismus [^25^].

| Parameter | Basiswert (PineGen) | WF-Scan-Bereich | Begründung |
|---|---|---|---|
| Entry-Fenster-Start (ET) | 9:45 | 9:45 / 10:00 / 10:15 | VWAP braucht Mindest-Datenbasis [^18^] |
| Entry-Fenster-Ende (ET) | 11:30 | 11:00 / 11:30 / 12:00 | Kern-Edge lt. Breakdown; Robustheit der Grenze prüfen |
| Trend-Bars über VWAP | 3 | 2–5 | Plateau-Test |
| RSI-Periode | 2 | 2–4 | RSI(2)-Logik, Sensitivität |
| RSI-Schwelle long/short | 25 / 75 | 15–35 / 65–85 | Connors-Range 4–12 (D1) vs. 25 (M5) — CFD-Noise ggf. höher [^24^] |
| ATR-Periode | 14 | 10–20 | Standard-Plateau |
| ATR-Mult SL | 1,5 | 1,0–2,5 (Schritt 0,25) | StrategyVerdict-Range 1,5–3,0 [^4^]; fazencapital US-Indizes 1,8–2,2 [^26^] |
| Trend-Buffer über VWAP | 0 (0,4 % vorgeschlagen) | 0 / 0,2 / 0,4 / 0,6 % | PineGen-Hypothese 9.2 (ungetestet!) [^1^] |
| Short-Filter (30-Min-Bar < Vortages-Close) | aus | ein/aus | PineGen-Hypothese 9.3 [^1^] |
| TP-Modus | PDH/PDL, sonst 2×ATR | PDH/PDL vs. fix 1,5R / 2R / 2,5R / 3R | TP:SL-Sweep-Praxis [^4^]; Zielkriterium RR ≥ 1:2 |
| Time-Exit | 15:00 ET (kein Entry danach) | Flat spätestens 12:30 / 15:00 / 15:55 ET | EOD-DD-tauglich: Flat vor Lunch-Lull als Variante |
| Max Trades/Tag | 1 long + 1 short | 1 / 2 gesamt | Prop-Disziplin |
| Wochentag-Filter | keiner | Mo–Fr einzeln; Shorts-nur-Fr (Unger) | [^22^] |
| Regime-Filter (optional) | keiner | VIX < 25; ATR(14) 5M im Band 20–80 Pkt.; Gap-Size-Filter | RSI(2)-Regime-Lektion [^24^]; Zarattini-Selektions-Analogon |
| Spread-/Slippage-Stress | — | +0 / +1 / +2 / +3 / +5 Pkt. je Seite | DAX-ORB-Lektion [wide01 ^155^] |

**Akzeptanzkriterien OOS:** PF ≥ 1.5 in ≥70 % der WF-Fenster; Parameter-Plateau ≥60 % der Nachbarzellen positiv; MaxDD-Sim (8 Verluste in Folge wie Aug 2024 [^1^]) bei 0,5 % Risiko = −4 % < FTMO-DLL 5 %.

---

## 5. IMPLEMENTIERUNGS-SPEZIFIKATION (Pseudo-Code, Python/MT5)

```
# === BOT 02: US100 VWAP-PULLBACK MORNING (M5) ===
SYMBOL        = "US100"           # broker-spezifisch: NAS100/USTEC/US100.cash
TF            = M5
RISK_PER_TRADE= 0.005             # 0.5 % Equity (EOD-DD-Headroom: 2 parallele Bots max)
MAX_TRADES    = 1 long + 1 short pro Session

# --- Zeitengine (KRITISCH, siehe §2.2) ---
# Server-UTC-Offset NICHT hardcoden; laufend schätzen:
#   offset = median(server_tick_time - utc_now) über N Ticks
#   t_ET = (t_server - offset) in ZoneInfo("America/New_York")   # DST-sicher
# Validierung: wöchentlicher Assert |offset - erwartet(GMT+2/+3)| < 1s-Drift;
#   Backtest-Pflichtmatrix über DST-Mismatch-Wochen (Mär/Okt-Nov) [^12^][^13^]

# --- Session-VWAP (selbst kumulieren, RTH-Anchor) ---
on_new_M5_bar(bar):
    if t_ET(bar) crosses 09:30:                       # Session-Reset
        cum_pv, cum_v = 0, 0
    tp  = (bar.high + bar.low + bar.close) / 3        # Typical Price
    v   = bar.tick_volume                             # VOLUME_TICK (VOLUME_REAL=0 auf CFD)
    cum_pv += tp * v;  cum_v += v
    vwap = cum_pv / cum_v                             # nur auf GESCHLOSSENEN Bars [^1^]

# --- State je Session ---
trend_long_ok  = (>= 3 aufeinanderfolgende M5-Closes > vwap seit 09:45-Bar)
trend_short_ok = (>= 3 aufeinanderfolgende M5-Closes < vwap seit 09:45-Bar)
rsi2  = RSI(close, 2);  atr = ATR(14, M5)
pdh, pdl = High/Low der Vortages-RTH-Session (09:30–16:00 ET, CFD-eigen!)

# --- Entry (nur 09:45 <= t_ET < 11:30, nur geschlossene Bars) ---
LONG:  trend_long_ok
       AND bar.low <= vwap AND bar.close >= vwap      # Pullback-Touch
       AND rsi2 < 25
       AND vorige-Signal-Bar bestaetigt: naechste Bar gruen (close>open)
            UND close > vwap                          # Entry am Close dieser Bar
       AND (close/vwap - 1) >= trend_buffer           # optional 0.4 % [^1^ 9.2]
SHORT: spiegelbildlich, rsi2 > 75, rote Bar, close < vwap
       AND optional: erste 30-Min-Bar der Session < Vortages-Close [^1^ 9.3]

# --- Order ---
sl_long  = entry - 1.5 * atr        # liegt strukturell unter VWAP [^1^]
tp_long  = pdh if pdh > entry + 0.5*atr else entry + 2.0 * atr
size     = risk_usd / (sl_dist_pts * point_value)     # Point-Value aus Spec lesen!
# KEIN Trailing-Stop (PF 0.76-Befund [^4^]); optional BE nach +1R als WF-Variante

# --- Exits ---
time_exit: spätestens 15:55 ET flat (Basis); Variante: 12:30 ET flat
cancel_all: keine neuen Entries nach 11:30 ET

# --- Prop-/Risiko-Layer ---
daily_loss_halt:  Equity < Tagesstart - 1.5 %  -> Bot aus für heute
news_guard:       8:30-ET-Red-Folder (CPI/NFP) -> kein Entry 09:30–09:45 ohnehin;
                  FOMC 14:00 ET irrelevant (flat bis dahin); FTMO: Indizes (außer
                  GER40) haben KEINE Restriction-News [^27^] — trotzdem Fenster loggen
spread_guard:     skip Entry wenn Spread > 2.0 Pkt
friday_rule:      Standard-Accounts: Freitag flat vor Wochenende (hier automatisch,
                  da intraday-only)
```

**Bekannte Abweichungen zur QQQ-Quelle, die dokumentiert werden müssen:** (1) Tick- statt Real-Volumen im VWAP; (2) CFD-Preisreihe ≠ QQQ (Basis/Overnight) → PDH/PDL anders; (3) 9:45–11:30-ET-Fenster = 16:45–18:30 Server (GMT+2/+3), außer DST-Mismatch-Wochen; (4) CFD-Handelspause (Daily Break, je nach Broker 22:00–23:00/23:59 Server) — irrelevant für Morning-Window, aber Session-Reset-Logik muss ihn sauber behandeln.

---

## 6. CONTROVERSIES & NEGATIVBEFUNDE

1. **Vendor-Quelle ohne Replikation:** Die PF-2.08-Zahl stammt ausschließlich von PineGen (verkauft das Tool, mit dem getestet wurde). Keine unabhängige Replikation gefunden (16 Queries). Einordnung: beste verfügbare, vollständig dokumentierte Regelquelle — aber Zahlen = Hypothese. Testperiode Jan 2024–Jun 2025 war überwiegend Nasdaq-Bullenmarkt; 63,5 % der Trades Long spiegelt den Drift.
2. **Intraday-VWAP widersprüchlich je nach Markt:** StrategyVerdict M5–H1 auf Krypto total negativ (M5 PF 0.22) [^4^]; CoinQuant VWAP-Cross BTC PF 0.40–0.99 [wide03 ^15^]; PineScriptForge NQ VWAP-Deviation PF nur 1.22 [wide03 ^16^]. ⇒ VWAP-Edge ist **session- und instrumentenspezifisch** (US-Equity-Open, institutionelles Benchmark-Verhalten), kein Universalphänomen. Der Morning-Window-Filter ist nicht Dekoration, sondern die Edge selbst.
3. **Tick-Volumen-Korrelation (90 %) stammt aus FX 2011** [^7^] — Übertragung auf Index-CFD-Feeds einzelner Broker nicht belegt; Feed-Qualität variiert [^6^]. Empfehlung: VWAP aus NQ-Futures-Volumen als Referenz gegenrechnen.
4. **8er-Verlustserien sind normal** (Aug 2024, Yen-Carry-Unwind) [^1^]: Bei 0,5 % Risiko = −4 % Equity in einer Serie → unter FTMO-DLL 5 %, aber mit zwei parallelen Bots knapp. Consistency-Rule (FTMO 1-Step 50 %-Best-Day) durch 1–2 Trades/Tag-Design unkritisch.
5. **RSI(2)-Schwelle 25 auf M5** ist aggressiv hoch vs. Connors-D1-Standard (5–10) [^24^] — im WF-Scan breit testen (15–35).

---

## Quellen

[^1^]: PineGen.ai – "We Tested the VWAP Pullback Strategy on QQQ, 18 Months of Backtest Data", 08.07.2026, https://www.pinegen.ai/resources/pine-script-user-case-studies/vwap-pullback-strategy-qqq-backtest
[^2^]: FXNX – "Index CFD Volatility by Hour: Major Ranges Compared", 02.09.2026, https://fxnx.com/en/blog/index-cfd-volatility-hour-ranges-compared-side-side
[^3^]: FXNX – "ICT Killzone Volatility Data: Average Range by Session Hour", 23.08.2026, https://fxnx.com/en/blog/ict-killzone-volatility-data-average-range-session-hour
[^4^]: StrategyVerdict – "VWAP Strategy Backtest: 5 Coins, 16 Parameter Sets, Full Out-of-Sample Test", 07.07.2026, https://strategyverdict.com/vwap-strategy-backtest-crypto/
[^5^]: quantbuffet – "VWAP as Precise Trend-Following Indicator for Day-Traders", 17.04.2024, https://quantbuffet.com/2024/04/17/volume-weighted-average-price-vwap-as-precise-trend-following-indicator-for-day-traders/
[^6^]: FXNX – "XAUUSD Tick Volume on MT5: What the Bars Really Count", 15.08.2026, https://fxnx.com/en/blog/xauusd-tick-volume-mt5-what-bars-actually-count
[^7^]: ForexFactory – Thread "Does 'volume' of MT4 show the tick volume" (Marney-Studie 2011, >90 % Korrelation), 23.08.2026, https://www.forexfactory.com/thread/463566-does-volume-of-mt4-show-the-tick-volume
[^8^]: TradingWyckoff – "Tick Volume vs Real Volume", 23.05.2026, https://tradingwyckoff.com/en/tick-volume-vs-real-volume/
[^9^]: The Payout Report – "FTMO US MT5 Setup Guide" (Server GMT+2 with DST), 20.03.2026, https://thepayoutreport.com/ftmo-us-mt5-setup-guide-servers-symbols-settings/
[^10^]: IC Markets EU (DE) – "Handelszeiten" (Serverzeit GMT+2/GMT+3 Sommerzeit), 14.11.2025, https://www.icmarkets.eu/de/trading-pricing/trading-hours
[^11^]: pdmt5 (PyPI) – "Returned datetimes are timezone-naive server time, not UTC", 10.08.2026, https://pypi.org/project/pdmt5/
[^12^]: Chartmini – "Best Time to Trade Forex" (DST-Mismatch 2026: US 08.03.–01.11., UK 29.03.–25.10.), 29.07.2026, https://chartmini.com/blog/best-time-to-trade-forex
[^13^]: MT4Programming – "Build a DST-Aware EA in 6 Steps" (GMT+2/+3-Standard, Hardcoding-Warnung), 10.06.2026, https://mt4programming.com/mt4-timezone-tutorial-build-a-dst-aware-ea-in-6-steps/
[^14^]: OpenSUSE-Forum – MT5 unter Wine: `find_reg_tz_info`-Fehler (lokale TZ-Registry unzuverlässig), https://forums.opensuse.org/t/how-use-metatrader-5-on-opensuse/132544
[^15^]: TradersTrusted – "Best forex broker for NASDAQ" (IC Markets 0,6–1,2 Pkt., Vantage 1,0, Pepperstone 1,0), 27.07.2025, https://traderstrusted.com/trading-intelligence/brokers/best-forex-broker-for-nasdaq/
[^16^]: BrokerChooser – "Lowest-Spread Brokers for NAS100 CFDs 2026" (getestete Spreads 0,40–1,00), 06.05.2026, https://brokerchooser.com/best-brokers/best-brokers-for-trading-nas100-cfds
[^17^]: Skyanalyst – "NAS100 Long May 6: VWAP Continuation" (5m ATR 37 / 15m 50 / 60m 76,6 Pkt.), 06.05.2026, https://www.skyanalyst.ai/en/blog/nas100-long-vwap-fib-38-2-continuation-primary-05-06-2026
[^18^]: TradeZella – "VWAP Trading Strategy" (RTH-Anchor 9:30 ET, Pre-Market unzuverlässig, 0,1-%-Touch-Regel, 10:00–14:00 ET), 28.08.2026, https://www.tradezella.com/blog/vwap-trading-strategy
[^19^]: FXNX – "NASDAQ 100 Day Trading: QQQ vs. NAS100", 11.03.2026, https://fxnx.com/en/blog/nasdaq-100-day-trading-qqq-nas100-guide
[^20^]: NinjaTrader – "E-mini Nasdaq 100 Futures (NQ) Contract Specs", 10.12.2023, https://www.ninjatrader.com/futures/futures-contracts/equity-index/e-mini-nasdaq/
[^21^]: FTMO Blog – "Opening Range Breakout Strategy: How to Master the 15:30 US Session", 13.05.2026, https://ftmo.com/en/blog/opening-range-breakout-strategy-how-to-master-the-1530-us-session/
[^22^]: Unger Academy – "Testing Toby Crabel's Opening Range Breakout … Nasdaq", 17.07.2026, https://ungeracademy.com/blog/testing-toby-crabel-s-opening-range-breakout-does-it-really-work-code-backtest-on-nasdaq
[^23^]: Trade Loss Tracker – Kaufman "New Trading Systems and Methods", Intraday-Übersetzung (IS 3 Mon./OOS 1 Mon.; 500+ Trades), https://tradelosstracker.com/library/book/84-new-trading-systems-and-methods-kaufman/extended
[^24^]: QuantifiedStrategies – "RSI 2 Strategy: Complete Guide" (WF über Schwellen 4–12; Regime-Filter VIX<25), 01.03.2026, https://www.quantifiedstrategies.com/rsi-2-strategy/
[^25^]: FlyTradr – "Why Strategies Work on 1D but Fail on 1m" (Intraday-Overfitting, 60/40-Split), 11.06.2026, https://www.flytradr.com/blog/why-strategies-work-daily-fail-minute-timeframe-traps
[^26^]: Fazen Capital – "ATR Stop Loss Multiple" (US-Indizes 1,8–2,2× ATR), 03.08.2026, https://fazencapital.com/learn/en/atr-stop-multiples-by-instrument
[^27^]: ForexFactory FTMO-Thread (Tomas/FTMO) – "XAUUSD … has no restrictive news at all as well as all indices with exception of DAX", 02.12.2020, https://www.forexfactory.com/thread/707034-ftmo-for-serious-traders?page=242

---
*Methodik: 16 eigene Suchqueries (EN/DE) + Volltext-Deep-Reads der 5 zentralen Quellen (PineGen, FTMO, Unger, StrategyVerdict, TradeZella). Härtester Datenpunkt: vollständiges Primär-Regelwerk [^1^]. Größte Lücke: keine unabhängige Replikation der PineGen-Zahlen; Tick-Volumen-Übertragbarkeit auf Index-CFDs nicht direkt belegt.*
