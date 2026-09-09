# Insight-Extraktion — Trading-Strategien-Recherche (Phase 6)

Cross-Dimension-Insights — keine Wiederholung von Einzelbefunden, nur Muster, die erst aus dem Zusammenführen der 6 Wide- + 12 Deep-Dive-Reports sichtbar werden.

## Insight 1 — Der Edge sitzt nie im Signal, sondern im Filter-Stack
**Abgeleitet aus:** dim01 (ADX als Filter zerstört Edge, als Gate belegt), dim03/dim04 (SMC ohne Konfluenz PF 0.14–0.50, mit Kette PF 1.6–1.74), dim05 (roher Breakout PF 1.25 → mit ATR/HTF-Filtern plausibel >1.5), wide01 (ORB-Edge = Selektionsfilter), dim09 (Meta-Labeling = Precision-Filter, kein Alpha).
**Muster:** Über alle fünf Strategiefamilien hinweg zeigt die Evidenz dasselbe Bild: Das nackte Entry-Signal ist austauschbar und meist edge-los; PF > 1.5 entsteht erst durch die Schichtung von Regime-Gate + Session-Filter + News-Blackout + Kosten-Guard.
**Implikation:** Die Bot-Architektur muss Filter als konfigurierbare, einzeln abschaltbare Layer bauen (A/B-testbar im Backtest), nicht als fest verdrahtete Monolithen. Jede Strategie wird in Varianten "roh → +Filter 1 → +Filter 2" getestet, um Filter-Beiträge zu messen statt zu glauben.
**Confidence:** hoch (5 unabhängige Dimensionen, konsistente Richtung).

## Insight 2 — Prop-Firm-Constraints sind ein *Design-Generator*, nicht nur eine Einschränkung
**Abgeleitet aus:** dim07 (News-Breach-Ursachen), dim11 (5er-Verluststreak @55 % WR ≈ 37 % Daily-Breach-Risiko bei falscher Sizing), dim06 (Weekend-Gap vs. Daily-Loss), dim08 (HMM als DD-Reducer), wide06 (FTMO 1-Step: 3 % Daily + 50 %-Best-Day-Consistency).
**Muster:** Die harten EOD-/Daily-Loss-Regeln erzwingen konkrete Design-Entscheidungen, die die Strategiewahl mitbestimmen: Intraday-Flat-Strategien (VWAP, Silver Bullet) sind strukturell überlegen gegenüber Overnight-Strategien; 0.5 %-Risiko ist nicht "konservativ", sondern die mathematisch notwendige Folge aus Streak-Statistik; Best-Day-Consistency-Regeln verbieten "ein großer Gewinntag"-Profile und bevorzugen viele mittlere Gewinntage.
**Implikation:** Risiko-Engine wird als eigenes, strategieübergreifendes Modul gebaut (Daily-Halt, Streak-Limiter, Consistency-Dämpfer, EOD-Flat) — die Strategien selbst bleiben "dumm".
**Confidence:** hoch.

## Insight 3 — Zeit ist der am meisten unterschätzte Bug-Vektor
**Abgeleitet aus:** dim02 (9:45–11:30 ET = 16:45–18:30 Server), dim03/dim04 (Killzones ET-fixiert, nicht UTC), dim11 (Verifikations-Backtests über DST-Wochen), dim12 (US/EU-DST-Asynchronwochen 2026, Server-Offset-Messung).
**Muster:** Fünf Dimensionen sind unabhängig auf dasselbe fundamentale Problem gestoßen: MT5-Bars folgen Server-Zeitzone (EET/EEST), API-Timestamps sind UTC-Epochs, Strategie-Fenster sind in NY-/London-Ortszeit definiert — und zweimal im Jahr driftet alles eine Woche lang auseinander. Falsche Zeitzonen produzieren *plausible, aber falsche* Backtests (schlimmer als Crash).
**Implikation:** Zentrales Time-Engine-Modul: alle Daten at-ingestion nach UTC, alle Session-Definitionen via `zoneinfo` in America/New_York bzw. Europe/London, NFP-Matching-Test zur Offset-Verifikation, Pflicht-Backtest über die März/Oktober-DST-Wochen.
**Confidence:** hoch.

## Insight 4 — Die Strategie-Instrument-Zuordnung ist asymmetrisch: XAUUSD trägt, NAS100 intraday, Forex diversifiziert
**Abgeleitet aus:** wide03/dim01 (Gold-Trend PF > 1.5 dokumentiert), dim02/wide06 (NAS100 nur Morning-Window), dim05 (USDJPY = einziges positives Breakout-Paar), dim06 (COT nur FX), dim10 (MR: XAUUSD+EURUSD), wide06 (EURUSD = DLL-schonendster Pfad).
**Muster:** Kein Instrument ist universell; jede Strategie hat genau 1–2 Heimat-Instrumente. Gold trägt die Trend-Strategien, NAS100 die Intraday-Setups, Forex Majors die Breakout-/MR-Varianten und die Prop-schonende Diversifikation. Crosses (GBPJPY) sind wegen Carry-Unwind-Gaps und weiter Stops für 0.5 %-Risiko schlecht geeignet.
**Implikation:** Top-5 wird als Strategie×Instrument-Matrix deployt, nicht als 5 Strategien × alle Symbole. GBPJPY/BTC/ETH werden explizit nicht in die ersten Bot-Generation aufgenommen (Kosten-/Gap-Profil vs. EOD-DD).
**Confidence:** hoch.

## Insight 5 — Ehrliche Open-Source-Backtests sind die beste Realitätskalibrierung
**Abgeleitet aus:** dim01 (maker-tung-EA: PF 1.17 ehrlich vs. PF 1.54-Studienanspruch), dim03 (sarahleesoffice: kanonisches Fenster schwächstes), dim05 (Trade-Desk: Autor warnt selbst vor Cherry-Picking), dim11 (daru.finance: 92.500 Strategien, DSR 0.03).
**Muster:** Überall dort, wo jemand Code + vollständige Daten + Kosten offenlegt, landet das Ergebnis 30–60 % unter dem Studien-/Vendor-Anspruch. Die Differenz ist systematisch: Kosten, Slippage, Regime-Bias der Testperiode, Selektionseffekte.
**Implikation:** Interne Zielkorrektur: Ein OOS-PF von 1.5 im *eigenen, vercosteten, slippage-gestressten* Backtest entspricht etwa einem dokumentierten Vendor-PF von 2.0–2.5. Das Gate bleibt bei PF > 1.5 OOS — aber wir erwarten, dass 2–3 der 5 Kandidaten am Gate scheitern, und bauen Ersatz-Kandidaten (DI-Cross D1 als einfache Baseline) ein.
**Confidence:** hoch.

## Insight 6 — Die Validierungspipeline ist das eigentliche Produkt
**Abgeleitet aus:** dim09 (Gates DSR/PBO/CPCV), dim11 (5-Phasen-Pipeline, 23 Schritte), dim08 (Ablations-Arme Pflicht: HMM vs. ADX-Proxy vs. ohne), wide05 (selbst bester Backtest unter Zufalls-Null).
**Muster:** Jede Dimension, die sich mit Evidenzqualität beschäftigt hat, konvergiert auf dieselbe Schlussfolgerung: Der Unterschied zwischen "Bot der funktioniert" und "Overfit-Artefakt" ist ausschließlich die Disziplin der Pipeline (kausale Features, Purged CV, Stress-Kosten, MC-DD, Prop-Sim, Demo-Gate mit Trade-by-Trade-Abgleich).
**Implikation:** Das Backtest-/Validierungs-Framework wird mit höherer Sorgfalt gebaut als jede einzelne Strategie; Strategien sind austauschbare Plugins darin. Demo-Live-Phase dient primär der Kalibrierung Backtest↔Live (Slippage-Realität), nicht der Profitabilität.
**Confidence:** hoch.

## Insight 7 — Lokale KI (Qwen3/Chronos) hat genau zwei legitime Rollen — und beide sind Assistenz
**Abgeleitet aus:** wide05 (TSFM-Richtung = nein, Vol = ja), dim09 (Meta-Labeling braucht XGBoost, kein LLM), wide04 (LLM-Sentiment IC≈0 bei Replikation), dim08 (HMM > LLM für Regime).
**Muster:** Die verfügbaren lokalen Modelle sind für (a) Volatilitätsprognose → Positions-Sizing (TTM-R2, CPU-tauglich) und (b) unstrukturierte Text-Klassifikation (News-Impact-Einstufung als Fallback, wenn FF-Feed Impact-Feld fehlt) geeignet — für nichts davon braucht man sie zwingend, und für Entry-Signale sind sie kontraindiziert.
**Implikation:** KI-Module werden als optionale Layer hinter Feature-Flags gebaut; das Kern-Portfolio läuft ohne sie. Das schont Komplexität und erfüllt die "egal ob Chronos/AI oder basic"-Vorgabe ehrlich: die Antwort der Evidenz ist "basic + Filter".
**Confidence:** mittel-hoch.
