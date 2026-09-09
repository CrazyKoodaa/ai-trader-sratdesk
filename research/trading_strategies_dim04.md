# Dimension 04 — SMC-Konfluenz-Kette: Liquidity Sweep → CHoCH/MSS → FVG/OB-Retracement (inkl. Breaker-Block)

Recherche-Datum: 2026-06 (KI-Sitzung). 19 gezielte Websuchen (EN/DE) + vollständige Source-Code-Analyse des Python-Pakets `smartmoneyconcepts` v0.0.27.
Kontext: 5 Python-Bots für MT5 (pymt5trade), Ziel PF > 1.5 OOS, RR ≥ 1:2, Prop-Firm-tauglich. Bias-TF H4 (optional D1), Entry-TF M15/H1.

---

## 1) Detection-Algorithmen: `smartmoneyconcepts` (joshyattridge) im Detail — aus dem Source-Code

**KRITISCHER BEFUND VORAB:** Die Kernfunktionen des Pakets sind **vektorisiert über den gesamten DataFrame** und nutzen `shift(-1)` / Look-Forward — sie sind als **Backtest-Analyse-Werkzeug** gebaut, nicht live-sicher. Für den Bot muss jede Detektion um `swing_length/2` bzw. 1 Bar verzögert/"confirmed-only" neu implementiert werden, sonst Look-ahead-Bias.

### Claim 1.1 — FVG-Detection
- **Claim:** `smc.fvg(ohlc, join_consecutive=False)` erkennt ein bullishes FVG, wenn `high[i-1] < low[i+1]` UND `close[i] > open[i]` (Kerze i bullisch); bearish invers. Zone: Top=`low[i+1]`, Bottom=`high[i-1]` (bullish). Mitigation: erste Kerze ab i+2, deren `low <= Top` (bullish). `join_consecutive=True` merged aufeinanderfolgende FVGs (max Top, min Bottom).
- **Source:** smartmoneyconcepts/smc.py (v0.0.27), Methode `fvg`
- **URL:** https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/smartmoneyconcepts/smc.py ; Paket-Doku https://pypi.org/project/smartmoneyconcepts/
- **Date:** Code-Stand master/2024–2025, abgerufen 2026-06
- **Excerpt:** `fvg = np.where(((ohlc["high"].shift(1) < ohlc["low"].shift(-1)) & (ohlc["close"] > ohlc["open"])) | ...` — das `shift(-1)` beweist: FVG an Index i ist erst nach **Close der Kerze i+1** bekannt (1-Bar-Latenz, kein Repaint bei korrekter Nutzung).
- **Confidence:** Hoch (Primärquelle, Code gelesen).

### Claim 1.2 — Swing-Detection = Pivot mit Look-forward (KEIN ZigZag)
- **Claim:** `smc.swing_highs_lows(ohlc, swing_length=50)` markiert ein Swing-High, wenn `high[i]` das Maximum im Fenster `[i-L, i+L]` ist mit `L = swing_length` (intern verdoppelt: Fenster `2*swing_length`, Vergleich via `shift(-(swing_length//2)).rolling(swing_length).max()` nach Verdopplung). Anschließend werden aufeinanderfolgende gleichgerichtete Swings iterativ entfernt (nur das extremere High/Low bleibt), sodass Highs und Lows **alternieren**. Erste/letzte Kerze werden künstlich als Gegen-Swing gesetzt (Endeffekt).
- **Konsequenz:** Ein Swing an Position i ist frühestens `swing_length` Bars **später** bestätigt. Live muss man auf Bar `t` nur Swings bis `t - swing_length` verwenden. Das ist die größte Lookahead-Falle des Pakets.
- **Source:** smartmoneyconcepts/smc.py, Methode `swing_highs_lows`
- **URL:** wie oben (raw.githubusercontent)
- **Date:** abgerufen 2026-06
- **Excerpt:** `ohlc["high"] == ohlc["high"].shift(-(swing_length // 2)).rolling(swing_length).max()` (nach `swing_length *= 2`); danach while-Schleife zur Deduplikation konsekutiver Highs/Lows.
- **Confidence:** Hoch (Code). Praxis-Ersatz: Pine-Äquivalent `ta.pivothigh(high, L, L)` — bestätigt Pivot erst L Bars später, identische Latenz [^18^]. Alternative: reversalschwellen-basierter ZigZag (ATR-Multiple k=2–3 oder %), der Pivots bei Gegenbewegung ≥ T bestätigt [^19^].

### Claim 1.3 — BOS/CHoCH-Detection
- **Claim:** `smc.bos_choch(ohlc, swing_highs_lows, close_break=True)` benötigt eine Sequenz von **4 alternierenden Swings**. Bullish BOS: Pattern `[-1,+1,-1,+1]` mit `L4 < L2 < L3 < L1` (higher highs + higher lows); bullisher CHoCH: gleiches Pattern, aber `L1 > L3 > L4 > L2` (erster höherer High nach tieferem Low — Charakterwechsel). Das Event wird am **Swing-Index** markiert; `BrokenIndex` = erste Kerze ab Swing+2, deren Close (oder High/Low bei `close_break=False`) das Level `L3` bricht. **Nicht gebrochene BOS/CHoCH werden nachträglich gelöscht** → klassisches Repainting im Chart, im Backtest aber kausal nutzbar, wenn man nur bis `BrokenIndex` bestätigte Events akzeptiert.
- **Source:** smartmoneyconcepts/smc.py, Methode `bos_choch`
- **URL:** wie oben
- **Date:** abgerufen 2026-06
- **Excerpt:** `bos[...] = 1 if (np.all(highs_lows_order[-4:] == [-1, 1, -1, 1]) and np.all(level_order[-4] < level_order[-2] < level_order[-3] < level_order[-1]))` … `# remove the ones that aren't broken`.
- **Confidence:** Hoch (Code). Hinweis: Paket-BOS ist damit **trend-kontinuierlich** (HH nach HL), CHoCH ist der **erste Gegen-Bruch** — konsistent mit Community-Definition (CHoCH = Bruch des letzten internen Swing gegen den Trend; MSS = CHoCH + vorheriger Sweep + Displacement) [^3^][^4^].

### Claim 1.4 — Order-Block-Detection
- **Claim:** `smc.ob(ohlc, swing_highs_lows, close_mitigation=False)`: Ein **bullisher OB** entsteht, wenn `close[i]` erstmals über das High des letzten Swing-Highs schließt (impliziter BOS); OB-Kerze = Kerze mit dem **tiefsten Low zwischen Swing-High und Break-Kerze** (bei Gleichstand die letzte), Zone = deren [Low, High]. `OBVolume` = Volumen Break-Kerze + 2 davor; `Percentage` = min/max der Volumen-Blöcke × 100 (Stärke-Maß). Interner `breaker`-Flag: sobald Preis unter OB-Bottom läuft, gilt OB als mitigiert; läuft er danach über OB-Top, wird der OB gelöscht (interne Breaker-Logik, **nicht als eigener Output exponiert** — Breaker müssen selbst implementiert werden).
- **Source:** smartmoneyconcepts/smc.py, Methode `ob`
- **URL:** wie oben
- **Date:** abgerufen 2026-06
- **Excerpt:** `if _close[close_index] > _high[last_top_index] and not crossed[last_top_index]: ... segment = _low[start:end]; min_val = segment.min(); ... ob[obIndex] = 1; top_arr/bottom_arr = High/Low der Kerze`.
- **Confidence:** Hoch (Code).

### Claim 1.5 — Liquidity-Detection (Equal Highs/Lows)
- **Claim:** `smc.liquidity(ohlc, swing_highs_lows, range_percent=0.01)` gruppiert Swing-Highs, deren Level innerhalb von `pip_range = (max(high) - min(low)) * range_percent` **des gesamten geladenen Datensatzes** liegen (≥2 Swings = Liquidity-Pool, Level = Mittelwert). `Swept` = erste Kerze nach Pool-Start mit `high >= Level + pip_range`. **Zwei Fallen:** (a) `pip_range` skaliert mit der Gesamt-Range des Datensatzes → dieselben Parameter ergeben auf 3-Monats- vs. 3-Jahres-Daten andere Pools (Lookahead-artige Instabilität); (b) Pool-Bildung nutzt zukünftige Swings. Für den Bot: Toleranz stattdessen **lokal und ATR-relativ** definieren (z. B. `tol = k * ATR(14)` am Entstehungsbar, k = 0.1–0.3).
- **Source:** smartmoneyconcepts/smc.py, Methode `liquidity`
- **URL:** wie oben
- **Date:** abgerufen 2026-06
- **Excerpt:** `pip_range = (ohlc["high"].max() - ohlc["low"].min()) * range_percent` … `cond = ohlc_high[c_start:] >= range_high`.
- **Confidence:** Hoch (Code). Marktpraxis-Toleranzen: "keine feste Toleranz — wenige Ticks/Pips oder kleiner ATR-Bruchteil" (LuxAlgo) [^5^]; Quantum Algo: 10–20 Pips FX-Majors, 1–5 USD Gold (aus wide02).

### Claim 1.6 — Hilfsfunktionen: Sessions, previous_high_low, retracements
- **Claim:** `smc.sessions()` hat eingebaute Killzones (UTC-naiv): "London open kill zone" 06:00–09:00, "New York kill zone" 11:00–14:00, "london close kill zone" 14:00–16:00, Asian KZ 00:00–04:00; plus laufendes Session-High/Low. `smc.previous_high_low(ohlc, "1D")` liefert PDH/PDL + Broken-Flags (kausal korrekt, gruppiert pro Periode). `smc.retracements()` liefert Retracement-% der aktuellen Swing-Strecke (für OTE-Filter nutzbar).
- **Source:** smartmoneyconcepts/smc.py, Methoden `sessions`, `previous_high_low`, `retracements`; PyPI-Doku.
- **URL:** https://pypi.org/project/smartmoneyconcepts/
- **Date:** abgerufen 2026-06
- **Confidence:** Hoch (Code). **Achtung DST:** Paket-Zeiten sind fixe UTC-Werte; ICT-Killzones sind in **New-York-Zeit definiert** und wandern damit 2×/Jahr gegen UTC (Details Claim 3.1).

---

## 2) Die Konfluenz-Kette — deterministische Regeldefinitionen aus den Quellen

### Claim 2.1 — HTF-Bias (H4/D1)
- **Claim:** Standard-Workflow: D1/H4-Struktur lesen (HH+HL = bullish, LH+LL = bearish), Bias fixieren, nur in Bias-Richtung traden ("This single filter eliminates the majority of losing trades"). Ergänzend: Daily-Bias aus Candle-Close vs. Vortages-High/Low (Close > PDH = bullish; Sweep von PDL + Close zurück in Range = bullish) und "Draw on Liquidity" als Zielrichtung. Bias-TF sollte 4–6× über dem Entry-TF liegen (H4-Bias → M15/H1-Entry passt exakt).
- **Source:** Quantum Algo SMC Guide (DE/EN); TradeZella Learning "Daily Bias"; Quantum Algo HTF-Bias-Guide
- **URL:** https://www.quantum-algo.com/de/blog/smart-money-concepts-complete-guide-2026/ ; https://www.tradezella.com/learning-items/timing-context ; https://www.quantum-algo.com/blog/guides/higher-timeframe-bias-complete-guide/
- **Date:** 2026-04-08 / 2025-12-19 / 2026-06-17
- **Excerpt:** "Open your Daily or 4-Hour chart and determine the market structure. HH+HL = bullish, only longs. LH+LL = bearish, only shorts." / "A bullish bias forms when price closes above the previous high or sweeps the low and closes back inside the range." / "Use a bias timeframe roughly four to six times higher than your entry timeframe."
- **Confidence:** Mittel-Hoch (konsistent über ≥4 unabhängige Quellen; keine quantitative Evidenz für den Filter selbst, aber Secuora/Backtrex zeigen: Filter ja/nein entscheidet über PF — wide02).
- **Implementierungs-Optionen (WF-testen):** (a) letzter bestätigter H4-BOS/CHoCH via smc.bos_choch (swing_length H4 ∈ {5,10,20}); (b) D1-Close vs. PDH/PDL (smc.previous_high_low); (c) optional SMA200-H4-Lage als Zweitfilter (klassische Trendfilter-Hybridisierung [^20^]).

### Claim 2.2 — Sweep-Definition
- **Claim:** Gültiger Sweep = Kerze, deren Wick ein markiertes Liquidity-Level (EQH/EQL, Session-High/Low, PDH/PDL, Swing-Extrem) durchstößt, aber deren **Close zurück innerhalb** der Range liegt (Rejection). Ohne Rejection-Close ist es ein Breakout, kein Sweep. MSS nach ICT verlangt zwingend einen vorangegangenen Sweep ("An MSS without a preceding sweep is not a valid MSS"); CHoCH ist der generischere Begriff ohne Sweep-Pflicht.
- **Source:** Backtrex MSS-Guide; FXNX MSS-vs-CHoCH; AMD-FVG GitHub (Sweep-Parameterisierung)
- **URL:** https://backtrex.com/en/blog/ict-market-structure-shift-mss-guide ; https://fxnx.com/en/blog/ict-mss-vs-choch-demystifying-precision-entries ; https://github.com/rehanqx/AMD-FVG
- **Date:** 2026-06-11 / 2026-07-18 / 2026-06-29
- **Excerpt:** "The MSS is more demanding: it mandatorily includes the liquidity sweep context preceding the break." / AMD-FVG-Defaults: `Wick Multiplier for Stop Hunt = 1.5` (×ATR), `Manipulation Detection Window = 5 bars`.
- **Confidence:** Hoch für die konzeptionelle Definition; die konkreten Schwellen (Wick-Überschuss, Fenster) sind **frei wählbar** → WF-Parameter.

### Claim 2.3 — CHoCH/MSS auf dem Entry-TF
- **Claim:** Nach dem Sweep: Displacement-Move in Bias-Richtung, der den letzten gegenläufigen LTF-Swing per **Body-Close** bricht. Displacement-Kriterien: ≥2–3 große gleichgerichtete Kerzen, Body ≥ 60–70 % der Kerzenrange ("Institutional Candle"), mittlere Kerze 1.5–2× durchschnittliche Kerzengröße, und ein FVG muss entstehen. MSS = CHoCH **mit** Sweep + Displacement; CHoCH allein = schwächeres, früheres Signal.
- **Source:** innercircletrader.net Displacement-Guide; FibAlgo ICT-Displacement; Strike.money FVG-Guide
- **URL:** https://innercircletrader.net/tutorials/ict-displacement-move/ ; https://fibalgo.com/library/ict-displacement ; https://www.strike.money/technical-analysis/fair-value-gap
- **Date:** 2024-04-22 / 2025-08-01 / 2025-12-18
- **Excerpt:** "At least three consecutive same-direction candles with large bodies. Small wicks … A fair value gap somewhere between those candles." / "body is at least 60–70% of the total candle range" / "middle candle … typically 1.5x-2x of average candle size … 70% body".
- **Confidence:** Mittel-Hoch (mehrere Quellen, konsistente Schwellen; didaktische, nicht empirische Herkunft).

### Claim 2.4 — Entry am FVG/OB
- **Claim:** Entry-Varianten: (a) **Limit-Order am FVG** — 50 % der Gap ("Consequent Encroachment") als Standard-Entry, alternativ Gap-Rand; (b) Limit am OB (50 % des Bodies = "Mean Threshold"); (c) Markt-Entry erst nach LTF-Bestätigung in der Zone (Rejection-Kerze / Mikro-CHoCH auf M5). FVG-Filter: Mindestgröße 0.1–0.5× ATR(14) bzw. 0.1 % des Preises; max. Alter 10–25 Bars (77 % der handelbaren FVG-Bounces innerhalb der ersten 12 Kerzen; >20 Bars → verwerfen). OTE-Check: Retracement sollte 62–79 % der Displacement-Strecke erreichen (Sweet Spot 70.5 %); FVG/OB in dieser Zone = A+-Setup. ≥4 Konfluenzen (Sweep, Displacement, CHoCH, OB, FVG, OTE) als Qualitätsregel.
- **Source:** AgenticTraders FVG-Guide; ClickAlgo FVG-Indikator-Defaults; AMD-FVG; FXNX FVG-Fill-Rate-Studie; FXNX OTE-Guide; TradingWyckoff SMC-Guide
- **URL:** https://agentictraders.io/learn/how-to-trade-fair-value-gaps-fvg-spotting-and-filling-market-imbalances ; https://clickalgo.com/fair-value-gap ; https://fxnx.com/en/blog/fair-value-gap-fill-rate-measured-across-thousands-gaps ; https://fxnx.com/en/blog/ict-fibonacci-ote-your-precision-entry-guide ; https://tradingwyckoff.com/en/smart-money-concepts/
- **Date:** 2026-07-24 / 2026-06-04 / 2026-08-23 / 2026-07-18 / 2026-04-27
- **Excerpt:** "Discard any gap smaller than roughly 0.25x ATR(14)… Limit order at the 50% midpoint of the gap… Stop beyond the far edge of the gap, padded by 0.5x to 1x ATR(14)." / "over 77% of all successful, tradeable FVG bounces occur within the first 12 candles… implement a 20-bar purge rule" / "0.62…0.705…0.79 — the area between the 0.62 and 0.79 levels forms the Optimal Trade Entry Zone".
- **Confidence:** Mittel-Hoch. FXNX-Fill-Rate als Vendor-Datenpunkt (nicht peer-reviewt), aber konsistent mit Edgeful (60 %+ der Session-FVGs bleiben unmitigiert → Limit-Orders verpassen oft Fill; Markt-mit-Bestätigung hat Trade-off weniger Trades vs. bessere Qualität) [^13^].

### Claim 2.5 — Breaker-Block-Variante
- **Claim:** Breaker = **fehlgeschlagener OB**: (1) valider OB, (2) Preis schließt per **Body-Close** durch die OB-Zone (Wick reicht nicht), (3) MSS/CHoCH in die neue Richtung, idealerweise mit vorherigem Sweep des Swing-Extrems, (4) Entry am Retest der gebrochenen Zone (Limit 30–100 % Pullback bzw. 50 % Body = Mean Threshold), SL hinter dem **Sweep-Wick** (nicht knapp hinter der Zone: "Stops one pip past the Breaker candle are routinely tagged"), TP an der nächsten gegenüberliegenden Liquidität. Breaker + FVG in derselben Zone = "Unicorn"-Setup (höhere Wahrscheinlichkeit). Beste TFs laut Quelle: H1/H15 mit D1-Kontext.
- **Source:** Plisio Breaker-Guide; innercircletrader.net Breaker-Guide; FXNX Breaker-Guide
- **URL:** https://plisio.net/education/breaker-block-trading ; https://innercircletrader.net/tutorials/ict-breaker-block-trading/ ; https://fxnx.com/en/blog/ict-breaker-blocks-master-art-trading-failed-order-blocks
- **Date:** 2026-05-11 / 2026-07-29 / 2026-07-18
- **Excerpt:** "A body close beyond the order block boundary… A wick that pierces and closes back inside is rejection." / "Four conditions: a liquidity sweep, a valid order block at the swept extreme, a body close past the OB extreme, and a Market Structure Shift in the new direction."
- **Confidence:** Mittel-Hoch (Definition sehr konsistent). Performance-Kontext aus wide02: Backtrex Breaker EURUSD PF 1.62 (n=87), NAS100 PF 1.74 (n=64), **ohne FVG-Filter PF < 1.2** → FVG-Konfluenz Pflichtfilter.

### Claim 2.6 — Stop & Take-Profit
- **Claim:** SL hinter dem Sweep-Wick-Extrem + Buffer 0.5–1.0× ATR(14) (engere Puffer werden routinemäßig ausgestoppt). TP-Hierarchie: TP1 = nächste interne/gegenseitige Liquidität (typisch 1:2), TP2 = HTF-Liquidität/Range-Gegenseite (1:3+); alternativ ICT-Fib-Extensions -0.27/-0.62/-1.0. Mindest-RR-Vorab-Check: Setup nur nehmen, wenn struktureller TP ≥ 2R ergibt.
- **Source:** Quantum Algo SMC-Guide; DocsBot Multi-Phase-SMC-Engine (Referenz-Implementierung); TradingWyckoff; innercircletrader.net Fib-Settings
- **URL:** https://www.quantum-algo.com/de/blog/smart-money-concepts-complete-guide-2026/ ; https://docsbot.ai/prompts/technical/multi-phase-smart-money-concepts-engine ; https://innercircletrader.net/tutorials/ict-fibonacci-levels/
- **Date:** 2026-04-08 / 2025-06-18 / 2026-05-07
- **Excerpt:** "Stop just beyond the liquidity sweep. Target the next HTF liquidity level. This naturally produces 1:3+ risk-to-reward ratios." / Referenz-Engine: "SL below last protected structure/OB or liquidity sweep zone with buffer (e.g., 0.5 ATR). TP targets include first opposite liquidity zone (TP1) and opposing OB/FVG on higher timeframe (TP2). Enforce minimum RR fallback (e.g., 1.5:1)."
- **Confidence:** Mittel-Hoch.

---

## 3) Session-Filter (Killzones) & News-Filter

### Claim 3.1 — Killzone-Zeiten: in New-York-Zeit definiert, UTC wandert mit DST
- **Claim:** ICT-Killzones sind fix in **New Yorker Lokalzeit (ET)**: London KZ 02:00–05:00 ET, NY AM KZ 07:00–10:00 ET (Forex) bzw. 08:30–11:00 ET (Indizes, an 8:30-Daten + 9:30-Cash-Open verankert), London Close 10:00–12:00 ET, Asian 19/20:00–00:00 ET. In UTC bei Winterzeit: London 07:00–10:00, NY 12:00–15:00; Sommerzeit: 06:00–09:00 bzw. 11:00–14:00. **"Killzones are defined in New York time, and they never move from it. Any table of times quoted in GMT or UTC becomes wrong twice a year."** Das `smartmoneyconcepts`-Paket nutzt fixe UTC-Zeiten (London-KZ 06:00–09:00, NY-KZ 11:00–14:00) — entspricht der Sommerzeit-Variante; für den Bot DST-sichere ET→UTC-Konvertierung (z. B. `zoneinfo("America/New_York")`) implementieren, nicht die Paket-Defaults blind übernehmen.
- **Source:** Captain Trading ICT-Killzones; FXNX Killzone-2026; innercircletrader.net Killzones; smartmoneyconcepts smc.py
- **URL:** https://captain-trading.com/en/free-trading-course/ict-killzones ; https://fxnx.com/en/blog/ict-killzones-2026-exact-times-smart-timing ; https://innercircletrader.net/tutorials/master-ict-kill-zones/
- **Date:** 2026-08-16 / 2026-06-10 / 2026-06-15
- **Excerpt:** "the London killzone runs 2:00–5:00 AM ET and the New York AM killzone 7:00–10:00 AM ET… for indices, the morning window becomes 8:30–11:00 AM New York time — anchored to the 8:30 AM US data releases and the 9:30 AM equities open. If you trade the Nasdaq or Bitcoin, this is the version that counts."
- **Confidence:** Hoch (mehrere unabhängige Quellen, konsistent; Grenzen variieren quellenabhängig ±30–90 min → als WF-Parameter).

### Claim 3.2 — Instrumenten-Killzone-Mapping & Silver-Bullet-Fenster
- **Claim:** London-KZ = EURUSD/GBPUSD/Gold (Sweep der Asian-Range, oft Tagesextrem); NY-AM-KZ = USD-Majors, NQ/ES, XAUUSD. Silver Bullet: zeitfixierte Fenster 10:00–11:00 ET (und 03:00–04:00, 14:00–15:00 ET), Setup = Sweep → MSS → FVG-Retracement mit 2R-Ziel, M1/M5-FVG — "am einfachsten automatisierbar" (wide02). Für NAS100 ist die 08:30–11:00-ET-Variante maßgeblich.
- **Source:** FXNX Silver-Bullet-Guide; innercircletrader.net Killzones; FXNX Gold-Sessions
- **URL:** https://fxnx.com/en/blog/ict-silver-bullet-master-10-11-am-setup ; https://fxnx.com/en/blog/gold-trading-sessions-master-xauusd-liquidity
- **Date:** 2026-07-17 / 2026-08-28
- **Excerpt:** "1. Wait for the Time Window… 2. Identify a Liquidity Sweep… 3. Wait for a Market Structure Shift (MSS)… Entry on pullback into the highlighted FVG."
- **Confidence:** Hoch (Konzept), Niedrig für jede Win-Rate-Behauptung ohne Regelset (Secuora-Warnung, wide02).

### Claim 3.3 — News-Filter-Anforderungen
- **Claim:** High-Impact-Events (NFP, CPI, FOMC, Zentralbanken): Handelspause **≥15 min vorher bis ≥10–15 min nachher**; Pending Orders und offene Positionen auf betroffenen + korrelierten Instrumenten 10 min vorher schließen/löschen; bei Top-Tier-Events global über alle Paare blockieren. Begründung: Spreads auf Gold weiten sich auf 30–50 Pips, Slippage >15 Pips, Orderbuch-Tiefe kollabiert (30 → <2 Lots Top-of-Book); Prop-Firmen werten Fills im Restricted Window (±2–5 min) als Regelverstoß → Kontoverlust. Post-News: erste M15-Kerze abwarten (filtert ~80 % Fakeouts). Kalenderquelle: MT5-Wirtschaftskalender-API oder Forex-Factory/Investing.com, wöchentlich in Broker-Server-Zeit konvertieren; bei Feed-Ausfall fail-safe = Trading deaktiviert.
- **Source:** FXNX EA-News-Filter; FXPropTech News-Trading-Filter; pro-scalper.com News-Trading-Gold; FXNX NFP/CPI-Guide
- **URL:** https://fxnx.com/en/blog/ea-news-filters-how-many-trades-break-prop-firm-rules ; https://fxproptech.com/risk-engine/news-trading-filter.html ; https://www.pro-scalper.com/xauusd-strategies/news-trading-gold
- **Date:** 2026-09-02 / o. D. / 2025-01-01
- **Excerpt:** "Configure your news filter to pause trading at least 15 minutes before high-impact events and 10 minutes after… Exactly 10 minutes before a high-impact event, your EA must execute a purge routine that closes active market positions and cancels all pending orders."
- **Confidence:** Hoch (operative Konsens-Praxis, mehrere Quellen).

---

## 4) Dokumentierte Performance-Zahlen — kritisch bewertet

| Claim | Zahlen | Quelle / URL / Datum | Bewertung / Confidence |
|---|---|---|---|
| **4.1** Ungefiltertes FVG-Retracement (mechanisch) | BTC/ETH 5m, 12 Mon., n=2.232, **WR 29,4 %, PF 0,43, −97,4 % netto** | Secuora via ColibriTrader; https://www.colibritrader.com/fvg-trading-strategy/ (2026-08-03); Original https://secuora.net/strategy/fvg-strategy | Methodisch transparentester Negativ-Befund: nackte FVG-Kette ohne Filter = kein Edge. **Hoch** |
| **4.2** Breaker-Block mit voller Kette | EURUSD 2022–24: WR 54 %, **PF 1,62**, n=87, RR 1:2,1; NAS100: WR 57 %, **PF 1,74**, n=64; **ohne FVG-Konfluenz PF < 1,2** | Backtrex; https://backtrex.com/en/blog/ict-breaker-block-trading-guide (2026-07-07) | Vendor (verkauft Backtest-Tool) + kleine n → Hypothese, muss repliziert werden. **Mittel** |
| **4.3** ICT mechanisch vs. AI-diskretionär | Mechanisch EURUSD M15 Killzones: **WR 29,6 % (unprofitabel)**; AI-diskretionär: **PF 1,99, WR 40,4 %**, Ø +2,93R, n=47 | OffbeatForex; https://offbeatforex.com/is-ict-strategy-profitable/ (2026-08-02) | Replizierbar/Open-Source, aber n=47/2 Monate — nicht belastbar; Kernbotschaft: Selektion schlägt Mechanik. **Mittel** |
| **4.4** HAW-Bachelorarbeit | ICT-Konzept-Nachbau, ~20 J. Backtest: **kein ICT-Konzept mit Prognosekraft über Standardmethoden hinaus**; Gewinn nur aus Trade-Management | Steinkamp, HAW Hamburg; https://schumann.mt.haw-hamburg.de/BachelorArbeitJonSteinkamp.pdf | Einzige akademische Quelle. **Hoch** (als Warnung), siehe wide02 |
| **4.5** FVG-Mitigation-Statistik | YM-Futures 30-min-FVGs, 6 Mon.: 60,7 % (bullish) / 63,2 % (bearish) bleiben **in derselben NY-Session unmitigiert** (Close-Basis); Wick-Basis 52,4 %/50,4 %. Euro Stoxx 600 Qi-FVG-Strategie: 61,3 % Hit-Rate, +0,7 %/Trade | Edgeful via ColibriTrader; https://www.edgeful.com/blog/posts/fair-value-gap-best-practices-guide (2025-07-12) | Vendor-Daten; wichtige Implikation: Limit-Order am FVG hat ~40–50 % Fill-Chance; FVG als S/R-Zone statt Fill-Ziel lesen. **Mittel** |
| **4.6** FVG-Alterung | >77 % der handelbaren FVG-Bounces innerhalb der ersten 12 Kerzen; ab 20–25 Bars verworfen; IFVG (durchbrochener FVG als Inversion) 63,8 % Fortsetzungsrate bei Struktur-Shift | FXNX FVG-Fill-Rate; https://fxnx.com/en/blog/fair-value-gap-fill-rate-measured-across-thousands-gaps (2026-08-23) | Vendor, plausibel, als Purge-Regel-Designgrundlage nutzbar. **Mittel** |
| **4.7** Community-Winrates mit voller Konfluenz | "Independent backtests… typically report win rates between 50 % and 65 % when strict rules are applied (OB + FVG + liquidity sweep + killzone)" | TradingWyckoff SMC-Guide; https://tradingwyckoff.com/en/smart-money-concepts/ (2026-04-27) | Sekundärbehauptung ohne verlinkte Studien — als Erwartungs-Korridor, nicht als Beleg. **Niedrig-Mittel** |
| **4.8** Silver Bullet (PineScriptForge) | MNQ: PF 2,03, WR 47,1 %, n=646 | https://pinescriptforge.com/mnq/ict-silver-bullet/backtest (2024-12) | Auto-generiert, intern inkonsistent (wide02) → nur Hypothese. **Niedrig** |
| **4.9** Secuora-SVS-Rahmen | 49 Strategien/154 Backtests/127.817 Trades; Score-Formel: Edge (PF nach Kosten, 35 Pt), Robustheit über Märkte (20), Sample (20), DD (15), Konsistenz (10) | https://secuora.xyz/methodology | Guter Bewertungsrahmen für eigene WF-Akzeptanzkriterien (PF ≥ 1,5 nach Kosten, ≥2 Märkte profitabel, n ≥ 300). **Hoch** als Methodik-Referenz |

**Synthese (konsistent mit wide02):** Die Kette Sweep→CHoCH→FVG/OB ist nur **mit** allen Filtern (HTF-Bias + Sweep + Displacement + Killzone + FVG-Konfluenz + RR-Gate) profitabel-kandidat; jede Stufe weglassen kostet nachweislich PF (4.1, 4.2, 4.3). Erwartbares OOS-Profil bei sauberer Umsetzung: WR 40–55 %, Ø 2–3R, PF 1,3–1,8 — die PF-1,6–2,0-Vendorzahlen als **Oberkante**, nicht Erwartungswert.

---

## 5) Instrumenten-Fit

- **XAUUSD:** Guter Fit für Killzone-Logik (London + NY-AM, COMEX/LBMA-Volumen) [^10^]. Aber: Spread 0,15–0,50 USD (Raw-ECN London/NY), bei News 30–50 Pips Spread, Slippage >15 Pips; "Gold and volatile pairs require more breathing room — standard pips don't apply" (Breaker-SL) [^14^][^15^][^16^]. Konsequenz: SL-Buffer eher 1,0× ATR, Mindest-FVG 0,3–0,5× ATR, EQH/EQL-Toleranz 1–5 USD, Max-Deviation 20–30 Points bei Market-Orders, bevorzugt Limit-Orders. NAS100-typische 8:30–11:00-ET-Fenster auch für Gold relevant (US-Daten).
- **NAS100 (NQ/USTEC):** Bestes dokumentiertes Breaker-Resultat (PF 1,74, Backtrex, n=64 — Vendor). NY-AM-KZ 08:30–11:00 ET maßgeblich; Pre-Market-Sweep (Asia-High/Low, PDH/PDL) als Pflichtkontext [^12^]. CFD-Varianten: Overnight-Gaps und Spread außerhalb der Cash-Hours beachten; ggf. nur 14:30–17:00 UTC (Sommer) handeln.
- **Forex-Majors (EURUSD/GBPUSD):** London-KZ primär (07:00–10:00 UTC Winter), EQH/EQL-Toleranz 10–20 Pips (Quantum Algo), engste Spreads → kostengünstigste Umsetzung; Backtrex EURUSD PF 1,62.
- **Kosten-Sensitivität:** Enge SMC-Stops sind spread-/slippage-sensitiv (wide02: PF 0,71→0,54 im Stresstest). Pflicht: Backtest mit variablem Spread + Slippage-Modell; Live nur mit Spread-Filter (Signal verwerfen, wenn Spread > k × Median-Spread, k≈2) [^15^].

---

## 6) Parameter-Räume für Walk-Forward

Walk-Forward-Disziplin: 70–80 % In-Sample / 20–30 % OOS rollierend; **Walk-Forward-Efficiency = OOS/IS-Performance ≥ 0,5** als Akzeptanzschwelle; Re-Optimierung nicht zu häufig (Noise) [^17^].

| Parameter | Default | WF-Raum | Begründung |
|---|---|---|---|
| `swing_length` Entry-TF (M15) | 10 | {5, 10, 15, 20} | smc-Default 50 zu träge für M15; Pivot-Latenz = swing_length Bars |
| `swing_length` Bias-TF (H4) | 10 | {5, 10, 20} | H4-Struktur grob |
| HTF-Bias-Modus | H4-Struktur | {H4-BOS, D1-Close-vs-PDH/PDL, H4+SMA200} | Claim 2.1 |
| EQH/EQL-Toleranz | 0,15 × ATR(14) | {0,1; 0,15; 0,25} × ATR (FX zusätzlich 10–20-Pips-Cap, Gold 1–5 USD) | Claim 1.5/2.2 |
| Min. Sweep-Wick-Überschuss | 0,1 × ATR | {0,05; 0,1; 0,2} × ATR über Level | AMD-FVG: 1,5× ATR Wick-Mult (Manip.) [^7^] |
| Sweep-Validity-Fenster | 12 Bars | {8, 12, 24} | Zeit zwischen Sweep und CHoCH |
| Displacement: Body/Range | ≥ 60 % | {50, 60, 70} % | Institutional-Candle-Schwelle [^8^] |
| Displacement: Kerzengröße | ≥ 1,5 × Ø-Body(20) | {1,2; 1,5; 2,0}× | Strike.money [^9^] |
| FVG-Mindestgröße | 0,25 × ATR | {0,1; 0,25; 0,5} × ATR | AgenticTraders/ClickAlgo/eafxstore [^6^] |
| FVG-Max-Alter (Purge) | 20 Bars | {12, 20, 30} | FXNX 77 %-Regel [^11^] |
| Entry-Typ | Limit @ FVG-50 % (CE) | {FVG-CE-Limit, FVG-Rand-Limit, OB-50 %-Body-Limit, Markt nach M5-CHoCH} | Claim 2.4 |
| OTE-Gate | FVG/OB ∩ [0,62–0,79]-Retracement | {an, aus} | OTE-Konfluenz [^2^] |
| SL-Buffer | 0,5 × ATR hinter Sweep-Wick | {0,3; 0,5; 1,0} × ATR | Claim 2.6 |
| TP-Modus | TP1 = gegens. interne Liquidität, min 2R | {2R fix, 3R fix, Liquidität mit 2R-Gate, TP1 1R + Runner} | Prop-Firm-Profil: min 1:2 |
| Killzone-Fenster | London 02–05 ET + NY 07–10 ET (Forex) / 08:30–11 ET (NAS100/Gold) | {nur London, nur NY, beide, ±30 min} | Claim 3.1/3.2 |
| News-Blackout | −15 min / +15 min | {−10/+10, −15/+15, −30/+30} | Claim 3.3 |
| Risiko/Trade | 0,5 % | {0,25; 0,5; 0,75} % | Prop: Daily-Loss 3–5 % → persönliche Cap 1,5–2 %, max 3 Verluste/Tag [^21^] |

---

## IMPLEMENTIERUNGS-SPEZIFIKATION (Pseudo-Code, bot-tauglich)

```text
# === SMC-KONFLUENZ-BOT (H4-Bias, M15-Entry; Variante B = Breaker) ===
# Anti-Repaint-Prinzip: ALLE Detektionen nur auf geschlossenen Kerzen;
# Swings sind erst L Bars nach ihrem Extrem "confirmed" (L = swing_length).

INPUTS: symbol, L_htf, L_ltf, tol_atr_k, min_fvg_atr, fvg_max_age,
        body_ratio_min, disp_mult, sl_buf_atr, rr_min, killzones, risk_pct

# --- 1) HTF-BIAS (einmal je H4-Close) ---
swings_H4 = pivot_swings(H4, L=L_htf)          # confirmed-only: Pivots bis t-L_htf
bos_H4, choch_H4 = bos_choch_closed(swings_H4, close_break=True)
bias = direction(last_confirmed(bos_H4 | choch_H4))
# Optional/Variante: bias = sign(D1.close[-1] > PDH) bzw. zusätzlich close vs SMA200(H4)
if bias == 0: NO_TRADE

# --- 2) LIQUIDITY-MAP (M15, confirmed-only) ---
pools = []
pools += equal_highs_lows(swings_M15, tol = tol_atr_k * ATR14)   # >=2 Swings in tol
pools += [PDH, PDL, asia_high, asia_low, prev_session_high/low]  # smc.previous_high_low/sessions-Logik

# --- 3) SWEEP (nur innerhalb Killzone, nur GEGEN Bias gerichteter Sweep) ---
if now in killzone_ET(dst_safe):               # Zeiten in America/New_York definiert!
    for pool in pools_against(bias):
        if candle.high > pool.level + 0.1*ATR and candle.close < pool.level:   # BSL-Sweep (für Shorts)
            sweep = {level: pool.level, wick: candle.high, t: now, dir: -1}    # spiegelverkehrt für Longs

# --- 4) CHoCH/MSS AUF M15 (innerhalb sweep_validity_bars nach Sweep) ---
# CHoCH = Close durch letztes gegenläufiges Swing-Extrem (close_break=True)
# MSS-Pflicht: Close-Bruch + Displacement:
disp = (body/range >= body_ratio_min) and (body >= disp_mult * avg_body(20)) and fvg_exists(3-candle)
if choch(bias.direction) and disp: mss_confirmed = True; mark displacement_leg

# --- 5) ENTRY-ZONE (FVG oder OB oder Breaker) ---
zone_fvg = first_unmitigated_FVG(displacement_leg, size >= min_fvg_atr*ATR)
zone_ob  = last_opposite_candle_before(displacement_leg)          # smc.ob-Logik, confirmed
# Breaker-Variante B: OB der alten Richtung, per Body-Close durchbrochen, Retest abwarten
ote_ok   = overlap(zone, fib_retracement(sweep_wick -> disp_extreme, [0.62, 0.79]))   # optional Gate
if not ote_ok and OTE_GATE_ON: SKIP
if age(zone) > fvg_max_age: PURGE zone                            # 20-Bar-Regel

# --- 6) ORDER ---
entry = midpoint(zone_fvg)                    # CE; Limit-Order (kein Market: Slippage-Kosten)
sl    = sweep.wick + sl_buf_atr * ATR  (Short) / - (Long)
tp_struct = nearest_opposite_liquidity(bias.direction)
if (tp_struct - entry) / (entry - sl) < rr_min: SKIP              # 2R-Gate
tp = min(tp_struct, entry + rr_min * risk)    # konservativ: 2R; Runner-Variante optional
size = (equity * risk_pct) / (|entry - sl| * pip_value)
place_limit(entry, sl, tp, expiry = fvg_max_age bars)

# --- 7) GUARDS (jede Kerze) ---
if minutes_to_red_news(symbol_currencies) in [-15, +15]: CANCEL pendings; NO new entries   # fail-safe bei Feed-Ausfall: blockieren
if spread > 2 * median_spread(session): SKIP signal
if daily_loss >= 1.5 % or losses_today >= 3: HALT until next day        # Prop-Firm-Schutz
if n_trades_today >= max_trades (z.B. 3): HALT
```

**Bekannte Implementierungs-Fallen (aus Code-Analyse):**
1. `smc.fvg/swing_highs_lows/bos_choch/liquidity` sind **nicht live-sicher** (shift(-1), Look-forward-Pivots, globaler Range-Percent, nachträgliches Löschen ungebrochener BOS). Entweder eigene kausale Implementierung (Pivots via rolling-max auf geschlossene Fenster, Latenz L akzeptieren) oder Paket nur für Backtest-Labeling mit striktem `confirmed_index = event_index + L`.
2. Killzone-Zeiten **nicht** aus dem Paket übernehmen (fixe UTC) → DST-sichere ET-Konvertierung.
3. Wick-basierte Stops in Close-only-Backtests zu optimistisch → im Backtest High/Low-Intrabar-Pfad konservativ annehmen (SL vor TP bei Überlappung).

---

## Quellen

[^1^]: joshyattridge/smart-money-concepts — Source smc.py v0.0.27 (fvg, swing_highs_lows, bos_choch, ob, liquidity, sessions, previous_high_low, retracements), https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/smartmoneyconcepts/smc.py + https://pypi.org/project/smartmoneyconcepts/ (abgerufen 2026-06)
[^2^]: FXNX — ICT Fibonacci OTE Guide (0.62/0.705/0.79), https://fxnx.com/en/blog/ict-fibonacci-ote-your-precision-entry-guide (2026-07-18); Ergänzung: liquidityscan.io OTE, https://liquidityscan.io/blog/ote-explained-the-ict-optimal-trade-entry-zone (2026-06-24); innercircletrader.net Fib-Settings, https://innercircletrader.net/tutorials/ict-fibonacci-levels/ (2026-05-07)
[^3^]: Backtrex — ICT MSS Guide (MSS = Sweep + Close-Bruch + FVG/OB; HTF/LTF-Rollen), https://backtrex.com/en/blog/ict-market-structure-shift-mss-guide (2026-06-11)
[^4^]: FXNX — ICT MSS vs CHoCH (extern/intern, Displacement-Pflicht), https://fxnx.com/en/blog/ict-mss-vs-choch-demystifying-precision-entries (2026-07-18)
[^5^]: LuxAlgo Library — Equal Highs/Lows as Liquidity (keine feste Toleranz; ATR-Bruchteil), https://www.luxalgo.com/library/concept/equal-highs-lows-as-liquidity/ (o. D.)
[^6^]: AgenticTraders — FVG 6-Zeilen-Detection, 0,25×ATR-Mindestgröße, CE-Limit-Entry, SL 0,5–1×ATR, https://agentictraders.io/learn/how-to-trade-fair-value-gaps-fvg-spotting-and-filling-market-imbalances (2026-07-24); ClickAlgo FVG-Defaults (5 Pips / 0,5×ATR, Mitigation Touch/Midline/Full), https://clickalgo.com/fair-value-gap (2026-06-04); eafxstore Super-Hybrid-EA (Min FVG 0,1 ATR, Ignore nach 45 Bars, EMA200-HTF, ADX-Filter), https://eafxstore.com/product/super-hybrid-ultimate-with-5-ai-engine-version-ea-mt5/ (2026-08)
[^7^]: GitHub rehanqx/AMD-FVG — AMD-Zyklus-Indikator (Wick-Mult 1,5×ATR Sweep, Manipulationsfenster 5 Bars, FVG min 0,1 %, max Alter 10 Bars, SL 0,5×ATR hinter Manipulations-Wick), https://github.com/rehanqx/AMD-FVG (2026-06-29)
[^8^]: FibAlgo — ICT Displacement (Institutional Candle: Body ≥ 60–70 % der Range; Streak 2–3+), https://fibalgo.com/library/ict-displacement (2025-08-01)
[^9^]: Strike.money — FVG-Validität (mittlere Kerze 1,5–2× Ø, 70 % Body; Kontextfilter), https://www.strike.money/technical-analysis/fair-value-gap (2025-12-18); innercircletrader.net Displacement (3 gleichgerichtete Big-Body-Kerzen + FVG), https://innercircletrader.net/tutorials/ict-displacement-move/ (2024-04-22)
[^10^]: FXNX — Gold Trading Sessions (XAUUSD-Killzone-Mapping, UTC Winter/Sommer), https://fxnx.com/en/blog/gold-trading-sessions-master-xauusd-liquidity (2026-08-28)
[^11^]: FXNX — FVG Fill Rate Studie (77 % der Bounces ≤12 Kerzen; 20-Bar-Purge; IFVG 63,8 %), https://fxnx.com/en/blog/fair-value-gap-fill-rate-measured-across-thousands-gaps (2026-08-23)
[^12^]: SmartMoneyTrader — ICT NQ Futures Strategy (Weekly/Daily/Monday-Range-Bias; Pre-Market-Sweep Pflicht; CISD-Entry), https://www.smartmoneytrader.co/blog/ict-nq-futures-strategy (2026-05-31)
[^13^]: Edgeful — FVG Best Practices (YM: 60,7 %/63,2 % unmitigiert in Session; Wick-Basis 52,4 %/50,4 %), https://www.edgeful.com/blog/posts/fair-value-gap-best-practices-guide (2025-07-12); via ColibriTrader, https://www.colibritrader.com/fvg-trading-strategy/ (2026-08-03)
[^14^]: FXNX — Breaker Blocks (Mean Threshold 50 % Body; SL hinter Sweep-Wick; Gold braucht mehr Raum), https://fxnx.com/en/blog/ict-breaker-blocks-master-art-trading-failed-order-blocks (2026-07-18)
[^15^]: Pro-Scalper — Spread/Slippage (XAUUSD Raw-Spread-Benchmarks <0,15–0,5 Pips; Spread-Filter 2,5–3,5 Pips Default), https://www.pro-scalper.com/spread-and-slippage-ea-trading (2026-03-12); fazencapital XAUUSD-Scalping (Spread ~0,50 USD Planungswert; News 10–15 min vorher schließen), https://fazencapital.com/learn/en/xauusd-scalping-5-minute-london-ny-overlap (2026-05-15)
[^16^]: FXNX — XAUUSD Slippage (News: Spread 30–50 Pips, Top-of-Book 30→<2 Lots; Max Deviation 20–30 Points), https://fxnx.com/en/blog/xauusd-slippage-measured-fill-quality-volatile-windows (2026-08-27) + https://fxnx.com/en/blog/xauusd-slippage-mt5-why-gold-fills-miss-price (2026-08-28)
[^17^]: ClearEdge — Walk-Forward-Optimization (70–80 % IS, Efficiency ≥ 0,5), https://clearedge.trading/post/walk-forward-optimization-futures-strategy-validation (o. D.)
[^18^]: DocsBot — SRZZ Non-Repainting (ta.pivothigh(high, L, L), Bestätigung erst L Bars später), https://docsbot.ai/prompts/technical/srzz-non-repainting-indicator (2025-12-12)
[^19^]: LuxAlgo Library — Zigzag Structure (Reversal-Schwelle %- / Fix- / ATR-Multiple k=2–3, ATR 14), https://www.luxalgo.com/library/concept/zigzag-structure/ (o. D.)
[^20^]: Altrady — EMA 20/50/200 als Trendfilter-Framework, https://www.altrady.com/blog/crypto-trading-strategies/ema-20-50-200 (2024-07-12); BarracudaTrader 200-SMA-Strategie, https://barracudatrader.com/200-sma-trading-strategy-for-tradingview/ (2025-06-18)
[^21^]: Prop-Risk-Konsens: 0,25–0,5 % Risiko/Trade, Daily-Cap ~60–80 % des Firmenlimits, max 3 Verluste/Tag — ThePropFirmGuide, https://thepropfirmguide.com/prop-firm-risk-management/ (2026-06-07); MarketsHQ Gold-Prop, https://marketshq.net/en/academy/prop-firm-trading/gold-strategies (2026-07-17); DamnPropFirms NQ, https://damnpropfirms.com/trading-guides/how-to-trade-nq-pullbacks-without-chasing-like-an-idiot/ (2026-07-11)
[^22^]: News-Filter: FXNX EA News Filters (−15/+10 min, Purge-Routine, Global-Halt), https://fxnx.com/en/blog/ea-news-filters-how-many-trades-break-prop-firm-rules (2026-09-02); FXPropTech Risk Engine (Kalender-Ingestion, ±1 min konfigurierbar, Force-Close-Optionen), https://fxproptech.com/risk-engine/news-trading-filter.html (o. D.); FXNX NFP/CPI (15-Minuten-Regel post-news), https://fxnx.com/en/blog/5-pro-tips-forex-news-trading-nfp-cpi (2026-08-29)
[^23^]: Killzone-Zeiten: Captain Trading (ET-fixiert, DST-Warnung), https://captain-trading.com/en/free-trading-course/ict-killzones (2026-08-16); FXNX Killzones 2026, https://fxnx.com/en/blog/ict-killzones-2026-exact-times-smart-timing (2026-06-10); innercircletrader.net, https://innercircletrader.net/tutorials/master-ict-kill-zones/ (2026-06-15)
[^24^]: Konfluenz-Workflows: Quantum Algo SMC Guide DE (5-Schritte: Bias→Liquidity→Sweep→LTF-CHoCH→SL/TP 1:3+), https://www.quantum-algo.com/de/blog/smart-money-concepts-complete-guide-2026/ (2026-04-08); TradingWyckoff (7-Schritte, ≥4-Konfluenzen-Regel, OTE-Check), https://tradingwyckoff.com/en/smart-money-concepts/ (2026-04-27); Oboe 2022-Mentorship-Model (HTF-DOL→KZ-Sweep→LTF-MSS→FVG-Limit→TP HTF-Pool), https://oboe.com/learn/icc-trading-strategy-1jyl3pl/study-guide (2026-04-01); TradeCalcPro (Entry mid/far edge, TP1 nächste Liquidität), https://tradecalcpro.in/smc-concepts.html (2025-10-15)
[^25^]: Breaker: Plisio (4-Schritte-Sequenz, Body-Close-Pflicht, Unicorn = Breaker+FVG), https://plisio.net/education/breaker-block-trading (2026-05-11); innercircletrader.net Breaker (4 Bedingungen; H1/M15 mit D1-Kontext; SL hinter Sweep-Wick), https://innercircletrader.net/tutorials/ict-breaker-block-trading/ (2026-07-29); CrypOptionHub, https://crypoptionhub.com/ict-breaker-block/ (2026-03-20)
[^26^]: DocsBot — Multi-Phase SMC Engine (Referenz-Regelwerk: Bias-Engine, Sweep 20–50 Bars, FVG 0,3 ATR, SL 0,5 ATR, TP1/TP2, Min-RR 1,5, Trail nach internem BOS), https://docsbot.ai/prompts/technical/multi-phase-smart-money-concepts-engine (2025-06-18)
[^27^]: Secuora SVS-Methodik (Bewertungsrahmen: PF nach Kosten, ≥2 Märkte, n-Schwellen), https://secuora.xyz/methodology (o. D.)
[^28^]: TradeZella — Daily Bias (Close vs. PDH/PDL; Sweep+Reclaim-Varianten), https://www.tradezella.com/learning-items/timing-context (2025-12-19); Quantum Algo HTF-Bias (4–6× TF-Ratio), https://www.quantum-algo.com/blog/guides/higher-timeframe-bias-complete-guide/ (2026-06-17)
