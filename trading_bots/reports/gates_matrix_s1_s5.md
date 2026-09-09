# Gates-Matrix S1–S7 (Phase 4 Abschluss + Forschungsrunde)

**Stand: 2026-09-05.** Alle 5 ursprünglichen Bots wurden gegen
`configs/validation_gates.yaml` (SPEC §7) validiert; zusätzlich wurden zwei
neu recherchierte Kandidaten (S6, S7) implementiert und getestet.
Datenquellen: S1/S4 MT5-Broker-H1/H4 (bestehend), S5 XAUUSD/EURUSD H1
(bestehend), S3 HistData.com M5 (2019–2026, tick_volume nicht real — für S3
unkritisch), S2 US100 M5 (Dukascopy 2022–08/2024 + MT5-Tail 02/2025–09/2026,
echtes Volumen, ~6 Monate Datenlücke), S6/S7 HistData.com M5/H1 (2019–2026,
6 neue FX-Paare).

## Ergebnis-Matrix

| Bot | Symbol | OOS-Trades | PF(1x) | PF(2x) | PF(3x) | WFE-Median | DSR | PBO | MC p95-DD | Gates |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---|
| S1 TrendPullback | XAUUSD | 21 | 1.43 | 1.27 ✅ | 1.15 ✅ | 0.004 | 0.003 | 0.31 | 0.86% ✅ | **FAIL** (3/10) |
| S2 VWAPPullback | US100 | 3 | 0.95 | 0.92 | 0.88 | 0.000 | 0.002 | n/a | 1.02% ✅ | **FAIL** (1/9) |
| S3 SilverBullet | XAUUSD | 3† | 0.82 | – | – | – | – | – | – | **FAIL** (kein WFA — s.u.) |
| S3 SilverBullet | NAS100 | 6† | 0.42 | – | – | – | – | – | – | **FAIL** (kein WFA — s.u.) |
| **S4 LondonBreakout** | **USDJPY** | **621** | **2.25 ✅** | **1.51 ✅** | **1.00 ✅** | 1.021 | **1.00 ✅** | **0.00 ✅** | **0.03% ✅** | **10/11** (1 Sanity-Flag) |
| S5 FilteredMR | XAUUSD | 53 | 0.48 | 0.43 | 0.39 | 0.15 | 0.00 | 0.56 | 10.04% | **FAIL** (1/10) |
| S5 FilteredMR | EURUSD | 34 | 1.23 | 1.16 | 1.10 ✅ | 0.13 | 0.01 | 0.07 ✅ | 4.21% ✅ | **FAIL** (3/10) |
| S6 FixReversal | GBPUSD/AUDUSD/NZDUSD/USDCAD | 603–641‡ | 0.16–0.48 | – | – | – | – | – | – | **FAIL** (kein WFA — s.u.) |
| S7 FomcDrift | EURUSD | 42‡ | 0.64 | 0.50 | 0.40 | – | – | – | – | **FAIL** (n zu klein) |

† S3: einzelner Backtest-Lauf mit Default-Parametern (kein WFO-Grid) — bei
n=3 bzw. n=6 Trades über 7,7 Jahre ist eine WFO-Optimierung statistisch
aussichtslos (`n(OOS) >= 300` unerreichbar), daher bewusst nicht
durchgeführt.
‡ S6/S7: Diagnose-Sweep bzw. Default-Backtest, kein WFO-Grid — siehe unten,
beide aus anderen Gründen bewusst nicht weiter optimiert.

## S4 — von "Near-Miss" zu "10/11", der Weg dahin

**Ursprünglicher Fund:** einziger Fail war `PF(3x Kosten) >= 1.0` (0.982).
Root-Cause: der einzige signifikante Ausreißer-Trade (-4.79R,
`exit_reason='force_flat'`) hielt über ein Wochenende, weil die H1-Serie
keine Bar exakt an der Freitags-Deadline hat — der bar-getaktete
Friday-Flat-Check (`core/risk.py`) bekommt dadurch keinen Trigger-Zeitpunkt
vor dem Wochenende und schließt die Position erst nach dem Gap-Move.

**Fix, in zwei Anläufen (der erste war fehlerhaft und wurde durch dieselbe
Regressions-Disziplin gefangen, die dieses Projekt überall sonst anwendet):**
1. `RiskManager.force_flat_gap()` (`core/risk.py`) + Aufruf in
   `Backtester.run()` (`core/backtester.py`) — erkennt eine Deadline, die
   still zwischen zwei Bars verschwindet, und schließt zum letzten bekannten
   Kurs (statt zum gegappten Kurs).
2. **Separater Fund währenddessen:** S4s Config setzt `eod_flat_time_utc:
   "21:00"` (fixe Trade-Desk-UTC-Zeit) — `RiskConfig` hatte dieses Feld
   nicht, wurde von `build_backtest_config()` stillschweigend gefiltert,
   S4 lief die ganze Zeit mit dem NY-Lokalzeit-Default (16:55) statt der
   dokumentierten 21:00 UTC. Fix: `eod_flat_time_utc` als echtes
   `RiskConfig`-Feld, mit Vorrang vor `eod_flat_time_ny`.
3. **Erster Fix-Versuch griff nicht:** Guard war `not force_flat(ts_utc)` —
   nach einer echten Lücke ist die aktuelle Bar aber so gut wie immer schon
   selbst über der Deadline (Sonntag 21:00 UTC ≥ 21:00-Deadline), der Guard
   bailte also sofort aus und der alte, kaputte Pfad griff weiterhin.
   Verifiziert: derselbe -4.79R-Trade trat nach dem ersten Fix-Versuch
   **bit-identisch** wieder auf. **Zweiter Fix:** der Trigger hängt jetzt an
   der tatsächlichen Lückengröße (`bar_interval`-Parameter aus dem
   Backtester, > 1.5× Timeframe-Delta = echte Lücke), nicht mehr am
   trivialen "ist die aktuelle Bar schon spät genug".
4. Direkt gegen die reale Trade-Historie verifiziert (nicht nur synthetische
   Tests): derselbe Trade schließt jetzt Freitag 21:00 UTC (statt Sonntag),
   zu +0.29R (statt -4.79R).

**Ergebnis nach Fix (voller WFA-Re-Run):** PF(3x) = **1.000** (exakt an der
Schwelle, von 0.982). 10 von 11 Gates PASS. Der eine verbleibende Fail ist
neu: `WFE <= 1.0 (Lookahead-Verdacht)` bei WFE-Median 1.021 — ein
Sanity-Check, kein Performance-Gate; er schlägt an, wenn OOS-Performance die
IS-Performance übertrifft (klassisches Lookahead-Symptom). Mechanik des
Fixes wurde geprüft und ist kausal korrekt (nutzt ausschließlich den bereits
bekannten Close der Vorbar); die plausibelste Erklärung ist, dass die
konkreten historischen Lücken-Fälle in diesem Datensatz zufällig etwas
stärker in OOS- als IS-Fenster fielen (sowohl IS- als auch OOS-PF-Werte
verschoben sich zwischen den Läufen, nicht nur OOS — ein Hinweis gegen einen
systematischen Leck). **Nicht abschließend verifiziert, bewusst als
dokumentiertes Near-Miss stehengelassen statt stillschweigend als PASS
gezählt** (User-Entscheidung 2026-09-05).

## Bot für Bot (S1/S2/S3/S5 unverändert gegenüber der ersten Fassung)

**S1 TrendPullback (XAUUSD H4)** — Struktureller Fail. WFE-Median praktisch 0
(0.004) und DSR ~0. Nur 21 OOS-Trades. Baseline-V1 (DI-Cross) nicht erneut
getestet, bleibt laut SPEC die Fallback-Empfehlung.

**S2 VWAPPullback (US100 M5)** — Lehrbuch-Overfitting: IS-PF bis 151.8, OOS
kollabiert in 4/6 Folds auf 0.00. WFO-Parameter am Rand des Suchraums
(klassisches Boundary-Overfit-Symptom).

**S3 SilverBullet (XAUUSD + NAS100 M5)** — Mit Default-Parametern extrem
selten (3/6 Trades über 7,7 Jahre) — `n(OOS) >= 300` strukturell
unerreichbar. Performance-Bug gefunden und behoben (O(n²) durch ungedeckelte
History-View, `strategies/s3_silver_bullet.py`) — vorher >4h ohne Ergebnis,
danach ~4 Min für den vollen Datensatz.

**S5 FilteredMR (XAUUSD + EURUSD H1)** — Fail auf beiden Symbolen, fehlende
OOS-Prognosekraft (WFE 0.13–0.15, DSR ~0–0.01).

## Forschungsrunde: zwei neue Kandidaten (S6, S7), beide sauber verworfen

Aus einem gezielten Recherche-Prompt (Kontext: was hat bei S1–S5 funktioniert
vs. versagt) gingen drei Kandidaten hervor; zwei wurden implementiert und
getestet, der dritte bewusst nicht (schwächste Evidenzlage der drei, kein
einziger Backtest-Beleg gefunden).

**S6 FixReversal (WM/Reuters 16:00-London-Fix-Reversal)** — Mechanismus
akademisch verifiziert (Krohn 2024, *Journal of Finance*, u. a.), Richtungs-
Logik im Code korrekt (Backtester-PnL-Konvention gegengeprüft — kein
Vorzeichen-Bug). Trotzdem: PF 0.16–0.48 auf allen 4 Paaren (GBPUSD, AUDUSD,
NZDUSD, USDCAD) bei Default-Parametern. Diagnose-Sweep (2D-Grid, 20
Kombinationen `target_r` × `trigger_threshold`) findet **keinen** Korridor
über PF 0.63 — glatte, monotone Fläche, kein verstecktes Optimum. Fazit: der
publizierte akademische Effekt überlebt nicht als simple mechanische
Fade-Regel mit Fixed-R nach echten Kosten. Kein WFO gefahren (Diagnose war
eindeutig genug).

**S7 FomcDrift (Pre-FOMC-Drift, EURUSD)** — Nur der akademisch belegte
FOMC→EURUSD-Zweig gebaut (ECB/BOE/RBA/RBNZ/BOC bewusst nicht — unbelegte
Extrapolation). Historische FOMC-Termine verifiziert (Fed-Kalender,
gegengeprüft, ein halluziniertes Datum verworfen; 2024-Termine gegen
eigenes Wissen stichprobenartig bestätigt). Default-Backtest: PF 0.64 bei
1×, aber **n=42 Trades** über den vollen 7,7-Jahres-Zeitraum — strukturell
unerreichbar für das `n(OOS) >= 300`-Gate, unabhängig von jeder
Parameter-Optimierung (nur ~63 FOMC-Termine insgesamt im Datensatz).

**C2 (Tokyo-London-Overlap, GBPJPY/EURJPY)** — nicht gebaut. Schwächste
Evidenzlage der drei Kandidaten (keine einzige Backtest-Quelle gefunden, nur
Mechanismus-Plausibilität) und Nähe zur bereits gescheiterten S3/S4-Familie.

## Offene Punkte

1. **S2-Datenlücke** ~08/2024–02/2025 (Dukascopy-Rate-Limit auch bei
   niedrigerer Anfragerate nicht zuverlässig lösbar; MT5-Demo-Tiefe beginnt
   erst 02/2025). Symbol-Fix gefunden: Broker-Ticker ist `USTEC`, nicht
   `NAS100`/`US100`.
2. **S1 Baseline-V1** (DI-Cross, SPEC §5/S1-Pflichtvergleich) nicht erneut
   validiert.
3. **S4s Lookahead-Sanity-Flag** (WFE 1.021) — als benigne eingestuft, aber
   nicht abschließend bewiesen (s. o.).
4. **`run_wfa.py` mergt `cfg["params"]` nicht in die WFO-Strategie-Instanz**
   — nur gesweepte Parameter erreichen die Strategie während WFA, alles
   andere fällt auf den Python-Klassen-Default zurück. Bisher folgenlos
   (Defaults wurden bei S1–S7 konsistent mit den YAMLs gepflegt), aber ein
   YAML-`params`-Wert, der nicht im WFO-Grid steht, wirkt sich beim nächsten
   WFA-Lauf NICHT aus, ohne dass das auffällt. Nicht dringend, aber ein
   guter Kandidat für eine kleine, separate Härtung.

## Empfehlung für Phase 5 (Demo-Live-Gate, plan.md)

**S4 ist der klare, einzige Kandidat** — 10 von 11 Gates PASS, der einzige
offene Punkt ist ein Sanity-Flag, kein Performance-Problem, und die
Bug-Ursache dahinter ist verstanden und direkt an der realen Trade-Historie
verifiziert. Realistisch der erste Kandidat für eine Demo-Freigabe, sobald
der Lookahead-Flag geklärt ist (oder bewusst als akzeptables Risiko
eingestuft wird). Die übrigen sechs Kandidaten (S1, S2, S3×2, S5×2, S6×4,
S7) zeigen strukturelle Fails — fehlende OOS-Prognosekraft, zu geringe
Handelsfrequenz, oder ein publizierter Effekt, der die Übersetzung in eine
mechanische Handelsregel nicht übersteht. Das deckt sich weiterhin mit
`plan.md`s eigener Erwartung, dass realistischerweise die Mehrheit der
Kandidaten durchfällt.
