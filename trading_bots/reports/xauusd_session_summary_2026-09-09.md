# XAUUSD Edge-Suche — Session-Zusammenfassung, 2026-09-09

**Ziel:** eine XAUUSD-Strategie finden, die alle Gates aus
`configs/validation_gates.yaml` (SPEC §7) besteht. **Ergebnis: nicht
erreicht.** Diese Zusammenfassung dokumentiert, was tatsaechlich
gefunden wurde -- zwei echte Framework-Bugs (behoben) und zwei
ehrliche negative Resultate (S21, S9) -- als Grundlage fuer die
Fortsetzung.

## 1. Framework-Fixes (unabhaengig vom XAUUSD-Ergebnis, betreffen alle Strategien)

- **Plateau-Selektion nie verdrahtet** (Commit "Wire up plateau-selection
  in WFA fold selector"): `core/validation.py::walk_forward` nutzte
  immer Max-IS-PF fuer die Fold-Parameterwahl, obwohl `plateau_select()`
  (SPEC §4.9) implementiert und getestet war, aber nie aufgerufen wurde.
  Jetzt ueber `wfo.selection: plateau` opt-in verfuegbar
  (Default `"pf"`, rueckwaertskompatibel).
- **Plateau-Selektion degenerierte bei PF-Metriken** (Commit "Fix
  plateau-selection degeneration for PF metric"): `plateau_select`s
  "positive Nachbarn"-Kriterium ist fuer PnL/Returns gedacht (koennen
  negativ sein); PF ist immer >= 0, daher war jede Nachbarzelle
  "positiv" und die Plateau-Bedingung degenerierte zu Arg-Max. Gefixt
  durch Verschiebung um -1.0 vor dem Plateau-Check (Breakeven-zentriert).
- **`Signal.risk_pct` nie mit Sizing verdrahtet** (Commit "Fix:
  Signal.risk_pct was never wired into position sizing"): sowohl
  `core/backtester.py` als auch `core/live.py` sizeten Positionen NUR
  ueber `RiskConfig.risk_per_trade_pct` (Account-/Config-Ebene) --
  `Signal.risk_pct` wurde entgegengenommen, aber nie tatsaechlich zur
  Sizing-Berechnung durchgereicht (nur ins Journal geloggt). Betraf
  potenziell auch die vier aktuell laufenden Live-Bots, aber alle vier
  hielten ihre `risk_per_trade_pct`/`risk_pct`-Werte manuell numerisch
  synchron -- kein tatsaechlicher Sizing-Unterschied fuer sie. Gefixt:
  `RiskManager.calc_lots` nimmt jetzt optional `signal_risk_pct` an,
  nutzt `min(signal_risk_pct, config-Obergrenze)`.

Volle Test-Suite nach allen drei Fixes: 427 bestanden (0 fehlgeschlagen).

## 2. S21 GoldReaper (EMA/RSI-Momentum, XAUUSD H1) — strukturell blockiert

Bestes Ergebnis: 7/10 Gates (mc5-Baseline und Varianten). Drei
unabhaengige Interventionen getestet, keine loeste das PBO- oder
PF(1x)-Problem:
- ATR-Volatilitaets-Filter als 4. WFO-Dimension: auf allen offenen
  Gates SCHLECHTER (PF 1.26 vs. 1.42, PBO 0.46 vs. 0.34).
- Plateau- statt Max-PF-Selektion: PBO bit-identisch (0.343) --
  **direkt im Code nachgewiesen**, dass PBO rechnerisch unabhaengig
  von der Fold-Selektionsmethode ist (es nutzt sein eigenes internes
  Arg-Max ueber die volle IS-Matrix).
- Kleineres Grid (12->6 Kombos): PBO wieder bit-identisch 0.343 --
  **direkt nachgewiesen**, dass das 6-Kombo-Grid eine exakte Teilmenge
  des 12-Kombo-Grids ist und in KEINEM der 70 CSCV-Splits die
  zusaetzlichen Spalten je den Ausschlag gaben (`min_rr=2.0` dominiert
  durchgehend).

**Fazit:** PBO=0.343 ist eine echte, reproduzierbare Eigenschaft des
`rsi_min` x `sl_atr_mult`-Unterraums dieses Signals -- kein Artefakt,
kein Bug (dreifach direkt verifiziert, s.
`reports/s21_xauusd_pbo_investigation.md`). Der Edge sitzt
konzentriert in seltenen Gap-Continuation-Exits (~16% der Trades, PF
37.6 auf diesem Segment) -- strukturell schwer robust zu machen ohne
einen komplett anderen Signal-Mechanismus.

## 3. S9 DonchianTrend (Turtle-Breakout, XAUUSD H1) — Meta-Overfitting-Falle

H4-Original hatte zu wenige Trades (n=228 < 300). Pivot auf H1 loeste
das Trade-Count-Problem, aber acht aufeinanderfolgende Runden manueller
Grid-Verengung (S9h bis S9p) zeigten PF(1x) und PBO in fast perfektem
Gleichlauf: PF(1x) 1.10->1.58 waehrend PBO 0.0->0.83 -- der Rahmen hat
korrekt erkannt, dass die Grid-Wahl jeder Runde auf Basis des VOLLEN
Fold-Logs der Vorrunde getroffen wurde (Hindsight-Kurvenanpassung ueber
die Lauf-Sequenz, s.
`reports/s9_xauusd_h1_metaoverfitting_finding.md`).

**Disziplinierter Einzel-Lauf** (S9q, Grid-Werte aus Konvention statt
aus den beobachteten Gewinnern dieser Session): **6/10 Gates.**
PBO=0.000 (perfekt -- bestaetigt, dass ohne Hindsight-Verengung kein
Overfitting-Signal vorliegt), n=573, WFE/Folds/Params PASS,
PF(3x)=1.010 knapp PASS. Aber PF(1x)=1.173, PF(2x)=1.087, DSR=0.226,
MC-DD=12.43% -- der rohe Edge reicht (ehrlich gemessen) noch nicht.

**Fazit:** S9 auf XAUUSD H1 hat einen echten, generalisierbaren
Mechanismus (PBO=0 bei ehrlicher Grid-Wahl beweist das), aber die
Signal-Qualitaet selbst ist noch nicht stark genug fuer die
Performance-Gates. Kein Bug, keine Kurvenanpassung -- einfach (noch)
nicht genug Edge.

## 4. Offene naechste Schritte

1. **S9 weiter verbessern, aber diszipliniert**: echte kausale
   Verbesserungshypothesen (nicht aus Fold-Logs dieser Session
   abgeleitet) einzeln testen -- z. B. Session-Filter, HTF-Bias,
   Volume-Profile-Konfluenz (bereits in `core/volume_profile.py`
   vorhanden, fuer S9 nie genutzt). Jede Hypothese: EIN Lauf, Ergebnis
   akzeptieren, nicht nachjustieren.
2. **Genauer Hold-out fuer S9** in einer neuen Session: Grid-Design nur
   mit Daten bis zu einem festen Cutoff, EIN eingefrorener Lauf auf den
   vollen Datensatz als Test.
3. **Andere Strategie-Familien** (S14 Squeeze-Volume, S17 David V2, S19
   Lizard) haben eigene, in dieser Session nicht vertiefte
   Historie -- s. `reports/wfa_s14_xauusd_v5_session`,
   `reports/wfa_s17_david_v2_xauusd`, `reports/wfa_s19_lizard_xauusd`
   fuer den Stand vor dieser Session.
4. S21s strukturelles PBO-Problem ist wahrscheinlich nicht ohne einen
   fundamental anderen Signal-Mechanismus loesbar (nicht nur weitere
   Filter auf demselben EMA/RSI-Kern).
