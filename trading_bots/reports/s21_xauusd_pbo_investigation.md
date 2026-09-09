# S21 GoldReaper (XAUUSD H1) — PBO-Investigation, 2026-09-09

**Ausgangspunkt:** `s21_goldreaper_momentum_stack_mc5.yaml`, bisher bester
XAUUSD-Kandidat der gesamten Session (7/10 Gates, s.
`reports/wfa_s21_goldreaper_xauusd_mc5/wfa_gates.json`): PF(1x)=1.424,
PF(2x)=1.31 ✅, PF(3x)=1.20 ✅, WFE=0.876 ✅, DSR=1.000 ✅, n=1173 ✅,
Params ✅ — offene Fails: **PF(1x)<1.5**, **PBO=0.343 (Gate <0.10)**,
**MC p95-MaxDD=8.93% (Gate ≤8.0%)**.

## Experiment 1 — ATR-Volatilitaets-Filter als 4. WFO-Dimension (S21c)

Post-Hoc-Quintilanalyse der mc5-OOS-Trades zeigte das unterste
ATR-Quintil (niedrigste Vol bei Entry) klar am schwaechsten (PF 1.17 vs.
1.39-1.89 in den oberen vier). Hypothese: `atr_vol_min_percentile`
(existierender, aber fix auf 0 gesetzter Strategie-Parameter) als echten,
kausal-je-Fold gewaehlten WFO-Parameter scharfschalten sollte PF(1x) heben.

**Ergebnis (`reports/wfa_s21c_goldreaper_atrfilter_mt5`):** PF(1x)=1.262
(schlechter als Baseline 1.424), PBO=0.457 (schlechter als 0.343),
DSR=0.803 (schlechter als 1.000), MC-DD=9.94% (schlechter als 8.93%) —
**auf allen vier Metriken schlechter**. Die Post-Hoc-Beobachtung
generalisiert nicht kausal: sie war vermutlich ein Artefakt einzelner
Regime-Perioden im Voll-Sample, kein stabiler Fold-uebergreifender Effekt.
Zusaetzliche WFO-Dimension (12→36 Kombos) erhoehte eher die
Overfitting-Flaeche als dass der Filter half. **Verworfen.**

## Experiment 2 — Plateau-Selektion (SPEC §4.9) statt Max-IS-PF

Beim Bau von S21d fiel auf: `core/validation.py::walk_forward` hatte
`plateau_select()` (implementiert, unit-getestet) **nie aufgerufen** —
die Fold-Selektion war immer reines Arg-Max, obwohl SPEC §4.9 explizit
"Plateau-Selektion statt Max-PF" als Anti-Overfitting-Massnahme vorschreibt.
Gefixt in `core/validation.py::_select_best_params` (+ `wfo.selection`
Config-Key, Default `"pf"` bleibt rueckwaerts-kompatibel).

**Bug beim ersten Anlauf:** `plateau_select`s "positive Nachbarn"-Kriterium
ist fuer PnL/Returns gedacht (koennen negativ sein). Profit Factor ist
per Definition >= 0 — ohne Korrektur ist JEDE Nachbarzelle "positiv" und
die Plateau-Bedingung degeneriert zu Arg-Max (empirisch verifiziert:
S21c und S21d lieferten bit-identische Ergebnisse ueber alle 20 Folds).
Fix: PF wird vor dem Plateau-Check um -1.0 verschoben (Breakeven-zentriert);
`best_pf` bleibt der echte, unverschobene PF. Regressionstest:
`tests/test_validation.py::TestSelectBestParams::test_plateau_shift_matters_for_all_positive_pf`.

**Ergebnis nach Fix, isoliert (S21e, kein ATR-Filter, sonst identisch zu
mc5):** PF(1x)=1.452, MC-DD=8.31% — beide leicht besser als Baseline,
aber **PBO=0.342857142857142857... (=24/70), bit-identisch zur
Baseline (0.343)**.

## Experiment 3 — Kleineres WFO-Grid (S21f/S21g, 2 statt 3 Dimensionen)

Hypothese: CSCV/PBO bestraft tendenziell groessere Parameter-Raeume
(mehr Kombinationen = mehr Zufallschancen auf eine gute IS-Zelle).
`min_rr` fixiert auf 2.0 (Median-nah zur Reverse-Engineering-Beobachtung),
Grid schrumpft 12→6 Kombos. Zwei Kontrollarme: S21f (plateau), S21g (pf).

**Ergebnis:** PF(1x) 1.454 (S21f) / 1.428 (S21g), MC-DD 8.11% / 8.50%,
DSR ~1.000 beide — **PBO in BEIDEN Faellen wieder exakt
0.34285714285714286**.

## Kernbefund: PBO ist bei S21 invariant gegenueber Selektionsmethode UND Grid-Groesse

Fuenf unabhaengige Laeufe (mc5-Baseline: 12 Kombos/pf; S21e: 12 Kombos/
plateau; S21c: 36 Kombos/pf [ATR]; S21f: 6 Kombos/plateau; S21g: 6 Kombos/
pf) liefern **bit-identisches PBO = 24/70 ≈ 0.343** (Ausnahme S21c mit
zusaetzlicher ATR-Dimension: 0.457 — separater Effekt, s.o.).

**Erklaerung, im Code verifiziert:** `pbo_cscv()`
(`core/validation.py`) wird ausschliesslich auf `result.is_pf_matrix`
berechnet — der vollen Kombos-x-Folds-IS-PF-Tabelle. Diese Matrix wird
in `walk_forward()` unabhaengig von `best_params`/der Selektionsmethode
befuellt (`is_pf_matrix.append([float(p) for p in pfs])`, VOR dem Aufruf
von `_select_best_params`). `pbo_cscv()` bestimmt sein eigenes
"IS-bestes" Element intern selbst (`np.argmax(is_perf)`) — die Wahl der
Fold-Selektionsmethode in `walk_forward` (pf vs. plateau) fliesst in die
PBO-Berechnung **gar nicht ein**. Plateau-Selektion kann PBO bei diesem
Design also grundsaetzlich nicht direkt beeinflussen (sie bleibt trotzdem
sinnvoll fuer OOS-Robustheit und ist SPEC-konform — nur eben kein PBO-Hebel).

Dass PBO zusaetzlich ueber 12→6 Kombos hinweg (unterschiedliche Matrix-
Formen) bit-identisch bleibt, deutet auf einen tieferen strukturellen
Befund hin: die getesteten Parameter-Varianten (rsi_min, sl_atr_mult,
min_rr — alles Feintuning DESSELBEN EMA-Stack-Momentum-Signals) sind
untereinander so stark korreliert, dass ihre OOS-Rangfolge unabhaengig
von der konkreten Kombo-Auswahl gleich instabil ist. Kombiniert mit dem
frueheren Fund (S21-Edge konzentriert in seltenen `sl_gap`-Exits, ~16%
der Trades, PF 37.6 auf diesem Segment vs. ~0.94 auf dem Rest) und der
Jahres-Aufschluesselung (2018, 2021, 2022 klar unrentabel — Regime-
Abhaengigkeit) ist die plausibelste Erklaerung: **PBO misst hier
tatsaechlich Regime-Instabilitaet des zugrunde liegenden Signals, nicht
Overfitting durch die Parameterwahl.** Kein an diesen drei Parametern
ansetzender Hebel (Selektionsmethode, Grid-Groesse, ein zusaetzlicher
Filter aus derselben Signalfamilie) kann das beheben.

## Empfehlung

S21 GoldReaper auf XAUUSD H1 bleibt bei 7/10 Gates haengen (PF(1x), PBO,
MC-DD) und ist mit den bisher getesteten Hebeln (Filter-Zusatzdimensionen,
Selektionsmethode, Grid-Groesse, Risiko-Skalierung) nicht auf 10/10 zu
bringen. Der PBO-Fail scheint strukturell im Signal selbst zu sitzen.
Naechste sinnvolle Richtung: eine Strategie-Familie mit einem
grundlegend anderen Signal-Mechanismus (nicht nur andere Filter auf
demselben EMA/RSI-Momentum-Kern) — z. B. S9 DonchianTrend auf H1 statt
H4 (mehr Trades, einfacherer Trendfolge-Mechanismus, andere
Exit-Logik) als naechster Kandidat.

Die Plateau-Selektion-Implementierung (SPEC §4.9-Konformitaet) bleibt
unabhaengig davon ein legitimer, korrekter Framework-Fix und wird
beibehalten (`wfo.selection: plateau`, Default weiterhin `"pf"` fuer
Rueckwaertskompatibilitaet aller bestehenden Configs).
