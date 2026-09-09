# S14 Squeeze-Volume-Breakout auf XAUUSD — Validierungsbericht

**Datum:** 2026-09-07
**Strategie:** `strategies/s14_squeeze_volume_breakout.py` (neu, "3. Weg"),
`strategies/s16_mtf_squeeze_breakout.py` (Multi-Timeframe-Variante)
**Config:** `configs/s14_squeeze_volume_breakout.yaml`
**Verdikt (nach Korrektur, s. Abschnitt 9): 5 von 10 Gates bestanden, NICHT
live-freigegeben.** Bindender Engpass: zu wenige OOS-Trades (n≈200-260 statt
≥300) und DSR (0.15-0.28 statt ≥0.95). Jede getestete Erweiterung (Session-
Filter, Multi-Timeframe) verschlechtert das Ergebnis unter ehrlicher WFA-
Validierung weiter — der reine H4-Einzeltimeframe-Ansatz bleibt die beste
gefundene Variante dieser Signal-Familie.

> **Update 2026-09-07, später am Tag:** Der ursprünglich gemeldete Stand
> dieses Reports (6/10 Gates) beruhte auf einem echten Bug — s. Abschnitt 9.
> Der tatsächliche, korrigierte Bestwert ist 5/10, nicht 6/10.

---

## 1. Auftrag

"Nimm nur XAUUSD mit all den Daten, bastle an einer Idee mit oder ohne
Indikatoren, oder etwas komplett anderes, das noch niemand auf dem Schirm hat.
Ziel: fast alle Gates schaffen." Im Unterschied zu allen bisherigen Versuchen
(S1–S13, drei Portfolio-Varianten, Kronos-Zero-Shot) wurde bewusst NICHT auf
Symbol-Breite gesetzt, sondern auf ein qualitativ neues Signal für ein
einzelnes Symbol.

## 2. Idee

**S14 (Hauptkandidat):** ATR-Perzentil-Regimefilter ("Squeeze" — Vola muss
VOR dem Ausbruch historisch niedrig stehen) + Donchian-Breakout + echte
MT5-Volumen-Bestätigung der Ausbruchsbar (≥ `vol_mult`× gleitendem
Durchschnitt). Neu gegenüber S1–S13: erste Strategie im Projekt, die
(a) einen Vola-Regimefilter VOR dem Signal prüft und (b) echtes Volumen als
harte Eintrittsbedingung nutzt statt nur als VWAP-Gewichtung.

**S15 (Gegenkandidat, verworfen):** Volumen-Klimax-Erschöpfungs-Reversal
(Order-Flow-Muster: Volumen-Spitze + große Range + Schluss am Extrem gegen
das Momentum → Fade-Wette). Über 54 Parameter-Kombinationen auf H4 und H1
lag der beste PF bei 0.983 — durchgehend unrentabel. Gold reversiert nach
Volumen-Klimax-Bars in diesem Zeitrahmen nicht zuverlässig; die Fortsetzung
(genau das, was S14 handelt) dominiert. Kein weiterer Aufwand investiert.

## 3. Datenbasis

- XAUUSD H1/H4, 2015-01 bis 2026-09, **100 % echtes MT5-Tick-Volumen**
  (`data/XAUUSD_H4.parquet`, 18 585 Bars).
- Zusätzlich XAUUSD M1 angefragt für feinere Intrabar-Auflösung: MT5-seitig
  auf ~99 000 Bars (nur 22.05.–06.09.2026, ≈3,5 Monate) gekappt — das
  Terminal begrenzt `copy_rates_from_pos`/`_range` über die Einstellung
  "Max bars in chart". Für die volle 11-Jahres-Historie in M1 müsste diese
  im MT5-Terminal (Extras → Optionen → Charts) auf "Unlimited" gesetzt und
  die Charts einmal manuell durchgescrollt werden, damit der Broker die
  Tiefe überhaupt vorhält — das ist eine GUI-Einstellung auf dem laufenden,
  mit anderen Bots geteilten Terminal, die ich nicht automatisiert ändere.
  Für dieses Ergebnis ohne Bedeutung, da H4/H1 bereits vollständiges
  Volumen über die gesamte Historie haben.

## 4. Vorab-Triage (Voll-Historie, kein WFA-Split)

Parameter-Sweep über `don_len`, `squeeze_pct`, `vol_mult`, `sl_atr_mult`,
`trail_atr_mult` auf H4 und H1 (siehe `configs/s14_squeeze_volume_breakout.yaml`
Kommentar für die Kennzahlen). Bestes Ergebnis: **PF 1.53 bei n=392–419**
(H4, `don_len=15, squeeze_pct=0.35, vol_mult=1.0, sl_atr_mult=2.5,
trail_atr_mult=2.5–3.0`) — der höchste Voll-Historie-PF, der in dieser
gesamten Suche für ein XAUUSD-Solo-Signal gefunden wurde (Baseline
S9 Donchian ohne Filter: PF 1.31 bei n=684).

H1-Variante (Parameter ×4 skaliert, um vergleichbare Kalenderfenster
abzubilden): PF fällt auf 1.03–1.09 trotz n=600–1050 — mehr Signale, aber
der Edge verwässert fast bis zur Nulllinie. **H4 bleibt die richtige
Zeitebene für dieses Signal**, mehr Datenpunkte über H1 lösen das
OOS-Mengenproblem nicht, sie verschlechtern es qualitativ.

## 5. Volle WFA (`is_months=24`, `oos_months=6`, 20 Folds)

### Lauf 1 — enges Grid (`don_len∈{15,20}`, `squeeze_pct∈{0.2,0.35}`,
`sl_atr_mult∈{2.0,2.5}`, `trail_atr_mult∈{2.5,3.0}`, 16 Kombos)

```
Folds: 20 | OOS-Trades: 174 | OOS-PF: 1.405 | WFE-Median: 0.88
PF(2x): 1.34 | PF(3x): 1.282 | DSR: 0.492 | PBO: 0.143
```

| Gate | Ergebnis | Status |
|---|---|---|
| n(OOS) ≥ 300 | 174 | **FAIL** |
| WFE-Median ≥ 0.5 | 0.880 | PASS |
| ≥60 % Folds WFE≥0.5 | 80 % | PASS |
| PF(1x) ≥ 1.5 | 1.405 | **FAIL** (knapp) |
| PF(2x) ≥ 1.2 | 1.340 | PASS |
| PF(3x) ≥ 1.0 | 1.282 | PASS |
| DSR ≥ 0.95 | 0.492 | **FAIL** |
| PBO < 0.10 | 0.143 | **FAIL** (knapp) |
| Params ≤ n/30 | 4 ≤ 5 | PASS |
| MC p95-MaxDD ≤ 8 % | 7.22 % | PASS |

**6 von 10 Gates bestanden — bestes Ergebnis der gesamten Suche** (bisheriger
Bestwert: 5/10, Portfolio breit, DSR 0.382).

### Lauf 2 — Sensitivitäts-Check, breiteres Grid (`squeeze_pct` zusätzlich
0.5, 36 Kombos)

```
Folds: 20 | OOS-Trades: 197 | OOS-PF: 1.358 | WFE-Median: 0.85
PF(2x): 1.298 | PF(3x): 1.237 | DSR: 0.335 | PBO: 0.057
```

n(OOS) steigt nur marginal (174 → 197), DSR verschlechtert sich (0.49 → 0.34),
PBO verbessert sich (0.143 → 0.057, jetzt PASS), MC-MaxDD kippt knapp auf FAIL
(7.22 % → 8.00 %). Wieder 6/10 Gates, nur andere vier fallen durch. **Fazit:
das Grid ist nicht der Engpass — die WFO-Optimierung wählt pro Fold ohnehin
meist die engere Squeeze-Schwelle, weil die den höheren IS-PF liefert.**

## 6. Diagnose: warum bleibt n(OOS) zu niedrig?

Der Squeeze-Filter ist per Konstruktion selten (Kompressionsphase +
Volumen-Bestätigung gleichzeitig): ~15–20 Signale/Jahr auf XAUUSD H4. Bei
`oos_months=6` ergibt das im Schnitt nur ~8,7 Trades pro Fold-Fenster
(174 / 20 Folds) — einzelne Fenster liefern sogar 0 Trades (Fold 3: OOS-PF
0.00). Das ist strukturell, nicht zufällig: um n(OOS)≥300 zu erreichen,
bräuchte es entweder deutlich mehr Kalenderzeit (nicht verfügbar — die
MT5-Historie beginnt 2015) oder einen lockereren Filter, der wiederum
(siehe Lauf 2 und die H1-Variante) den PF und/oder DSR verschlechtert. Das
ist ein echter Frequenz/Qualität-Zielkonflikt, kein Bug.

Der naheliegende Ausweg aus früheren Versuchen — mehr Symbole ins Portfolio
nehmen, um die OOS-Stichprobe zu poolen — war für diese Untersuchung
explizit ausgeschlossen ("nur die XAUUSD"). Er bleibt aber die wahrscheinlichste
nächste Stufe, siehe Abschnitt 7.

## 7. Einordnung gegenüber der gesamten bisherigen Suche

| Versuch | Gates bestanden | PF(1x) | DSR | MC-MaxDD |
|---|---|---|---|---|
| S9 Donchian (Baseline, ungefiltert) | – (kein WFA-Gate-Lauf) | 1.31 (Voll-Historie) | – | – |
| Portfolio FX-only | 5/10 | 1.23 | 0.025 | 13.94 % |
| Portfolio Gold+Index+FX (früh) | 5/10 | 1.11 | 0.117 | 22.52 % |
| Portfolio breit (11y, Realvolumen) | 5/9 | 1.24 | 0.382 | 12.75 % |
| **S14 XAUUSD Squeeze+Volumen** | **6/10** | **1.41** | **0.492** | **7.22 %** |
| S15 Volumen-Klimax-Reversal | verworfen (PF<1.0 in Voll-Historie) | – | – | – |

S14 ist auf jeder einzelnen Kennzahl besser als jeder vorherige Versuch
dieser Session — DSR fast 20× höher als beim ersten Portfolio-Versuch, und
als einziger XAUUSD-fokussierter Test überhaupt, der die MC-MaxDD-Schwelle
unterbietet. `PF(2x)`/`PF(3x)` bestehen komfortabel — das Signal ist robust
gegen Kostenstress, kein Scalping-Artefakt.

## 8. Verdikt und nächster Schritt

**Nicht live-frei.** 4 von 10 Gates fehlschlagen, davon eines (n(OOS)) hart
strukturell und nicht durch Parameter-Tuning lösbar, solange nur XAUUSD H4
allein betrachtet wird. Die anderen drei (PF(1x), DSR, PBO) hängen alle
direkt an der niedrigen Stichprobengröße — mehr valide Trades würden
vermutlich alle drei gleichzeitig verbessern (DSR und PBO sind beide
Stichprobengrößen-sensitiv per Konstruktion).

**Um den nächsten Schritt zu machen, bräuchte es eine der beiden:**
1. Das gleiche Signal auf einem eng korrelierten Zweitinstrument
   parallel laufen lassen (z. B. XAGUSD oder XPTUSD als eigenständiges,
   nicht nur referenzierendes Symbol) und die OOS-Trades poolen — der
   naheliegende nächste Versuch, aber außerhalb des heutigen "nur
   XAUUSD"-Auftrags.
2. Tiefere Historie vor 2015 beschaffen (andere Datenquelle als MT5, das
   Terminal hat hier keine ältere H4/H1-Historie) — mehr Kalenderjahre
   statt mehr Symbole.

Beide sind neue Recherche-Aufträge, keine Parameter-Anpassung.

## 9. Nachtrag: echter Bug gefunden, drei weitere Ideen getestet, Ergebnis korrigiert

Auf Nutzerfrage ("haben wir evtl. ein Bug im Code, der das verhindert?") wurde
`scripts/run_wfa.py`/`scripts/run_portfolio_wfa.py` geprüft.

**Gefundener Bug:** `walk_forward()` (`core/validation.py`) reichte bei jeder
Grid-Kombination NUR die im `wfo.param_space` gesweepten Keys an den
Strategie-Konstruktor weiter. Der `params:`-Block der YAML wurde nie gemerged
— jeder nicht gesweepte Parameter fiel still auf den Python-Klassen-Default
zurück. Bei S14 betraf das `vol_mult`: YAML wollte `1.0`, die Klasse hatte
`1.5` als Default, und genau dieser Default lief während der gesamten
WFA in Abschnitt 5/6 — ohne dass es auffiel.

**Fix:** `walk_forward()` bekommt einen `base_params`-Parameter (Grid-Werte
überschreiben ihn); beide Aufrufer übergeben jetzt `cfg["params"]`. Dabei
einen zweiten Bug mitgefixt (Absturz bei 0 Trades in jedem Fold). 3 neue
Regressionstests (`tests/test_validation.py::TestWalkForwardBaseParams`),
volle Suite 402/402 grün. **Betroffen war nur S14** — S4/S9/S10/S11 wurden
gegengeprüft, deren Klassen-Defaults waren durchgehend mit den YAMLs
synchron gehalten (Konvention, nicht Zufall).

**Korrigiertes Ergebnis (`vol_mult=1.0` korrekt angewendet):**

```
Folds: 20 | OOS-Trades: 174 | OOS-PF: 1.208 | DSR: 0.278 | PBO: 0.357 | MC-MaxDD: 10.72%
```
→ **5/10 Gates**, nicht 6/10. `vol_mult` danach selbst mit ins WFO-Grid
aufgenommen (Optimierung darf ihn pro Fold frei wählen): n=208, PF 1.24,
DSR 0.15 — bleibt bei 5/10. Der ursprünglich gemeldete 6/10-Stand war ein
Bug-Artefakt: der zufällige, zu strenge Default-Filter (1.5×) filterte
zufällig besser als der bewusst gewählte Wert (1.0×).

**Idee A — Session-Zeitfenster-Filter:** Vor der WFA (feste Parameter, volle
Historie) sah der NY-Overlap (12–17 UTC) stark aus (PF 1.53→1.68). In der
echten WFA (Session als Wahlmöglichkeit im Grid, pro Fold neu optimiert):
**4/10 Gates** (n=229, PF 1.21, DSR 0.12, PBO 0.11, MaxDD 10.2%) — schlechter
als ohne Filter. Derselbe Fallstrick wie beim Bug: Voll-Historie-Optimierung
täuscht einen Vorteil vor, der unter ehrlicher Fold-für-Fold-Validierung
verschwindet.

**Idee B — Multi-Timeframe (`strategies/s16_mtf_squeeze_breakout.py`):** H4
für die Squeeze-Regime-Erkennung (dieselbe Logik wie S14), H1 für Entry-
Timing (Donchian-Breakout + Volumen auf der feineren Ebene) — bewusst anders
als der frühere H1-Test, der nur dieselbe H4-Logik auf H1 reskaliert hatte.
Hypothese: die Regime-Güte von H4 könnte die H1-Entry-Präzision "retten".
Vorab-Triage auf voller Historie (24 Kombos, H1+H4): **bestes PF nur 1.13**
bei n=507, die meisten Kombinationen liegen bei PF≈0.97–1.05 (praktisch
Nullsummenspiel) trotz n=500–1800. Deutlich schwächer als sogar der reine
H1-Test von vorhin — die H4-Regime-Bestätigung reicht nicht aus, um die
Masse an Fehlausbrüchen auf H1-Ebene zu kompensieren. Keine volle WFA
gestartet (Vorab-Triage eindeutig genug, um das nicht zu rechtfertigen).

**Gesamtbild nach allen getesteten Erweiterungen:**

| Variante | Gates | PF(1x) | DSR | n(OOS) |
|---|---|---|---|---|
| **S14 H4, korrekt (Referenz)** | **5/10** | 1.24 | 0.15 | 208 |
| S14 H4 + Session-Filter | 4/10 | 1.21 | 0.12 | 229 |
| S16 Multi-Timeframe (H4+H1) | nicht WFA-wuerdig | ~1.0-1.13 (Voll-Historie) | – | – |
| S14 H1 (reskaliert, Abschnitt 4) | nicht WFA-wuerdig | 1.03-1.09 | – | – |
| S14 M5 (echtes Volumen, 1.4J) | nicht WFA-wuerdig | 1.21 | – | – |
| S14 M5 ohne Volumen (7.5J) | nicht WFA-wuerdig | 0.42-0.50 | – | – |

**Fazit (Stand vor Abschnitt 10):** Diese Signal-Familie (ATR-Squeeze-Regime
+ Volumen-bestätigter Breakout) wurde jetzt in jeder sinnvollen Variation
getestet — Zeitebene (H4/H1/M5), Session-Filter, Multi-Timeframe. Keine
Variante verbessert den reinen H4-Einzeltimeframe-Ansatz; jede Erweiterung
verschlechtert ihn unter ehrlicher Walk-Forward-Validierung. Der Engpass
ist strukturell (zu wenige unabhängige OOS-Trades für DSR/PBO).

## 10. Nachtrag: Edelmetall-Pooling getestet — löst n(OOS), zerstört aber PF

Der in Abschnitt 8 genannte nächste Schritt ("Zweitinstrument poolen")
wurde tatsächlich ausgeführt: XAGUSD, XPTUSD, XPDUSD live von MT5
nachgeladen (11 Jahre, echtes Volumen), Kostenmodelle in `configs/
common.yaml` ergänzt (point_value = Broker-Kontraktgröße, Spread aus
Live-Snapshot, Swap direkt von MT5 — Silber: 5000oz/Lot, Platin/Palladium:
1oz/Lot bei diesem Broker), und derselbe S14-Mechanismus per
`run_portfolio_wfa.py` über alle vier Metalle gemeinsam optimiert
(unabhängig pro Leg) und gepoolt validiert.

**4 Legs (XAU+XAG+XPT+XPD):**
```
Folds: 19 | OOS-Trades: 775 | OOS-PF: 0.957 | DSR: 0.001 | MC-MaxDD: 28.65%
```
**2 Legs (nur XAU+XAG):**
```
Folds: 20 | OOS-Trades: 451 | OOS-PF: 1.020 | DSR: 0.011 | MC-MaxDD: 18.52%
```

**n(OOS) ≥ 300 ist damit zum ersten Mal in der gesamten Untersuchung
bestanden** (775 bzw. 451 statt 174–262 bei XAUUSD allein) — aber der
Preis dafür ist ein kompletter PF-Kollaps: von 1.24 (XAUUSD solo) auf
1.02 (Au+Ag) bzw. 0.96 (alle vier, sogar unter 1.0). DSR fällt auf
praktisch null, MC-MaxDD verdoppelt bis verdreifacht sich (9.3%→18.5%/
28.7%). Silber (und erst recht Platin/Palladium) tragen also nicht
"mehr vom selben guten Signal" bei, sondern verwässern es — der Squeeze-
+Volumen-Mechanismus, der auf Gold ein reales, kostenstress-festes Signal
zeigt, überträgt sich nicht auf die anderen Edelmetalle. Pooling tauscht
Stichprobengröße gegen Profitabilität, es erzeugt sie nicht gemeinsam.

**Damit ist auch der letzte der beiden in Abschnitt 8 genannten Hebel
ausprobiert und widerlegt** (Pooling), der zweite (tiefere Historie vor
2015) ist mit den verfügbaren Datenquellen (MT5) nicht erreichbar. Nach
S9–S18, drei Portfolio-Varianten, sechs geprüften externen Pine-Skripten
und einem externen Live-Bot bleibt der ehrliche Endstand: **kein
getesteter Ansatz hat alle Gates bestanden**, und der XAUUSD-Solo-
S14-Befund (5/10, PF 1.24, DSR 0.15) bleibt der beste, tatsächlich
erreichte Punkt der gesamten Suche.
