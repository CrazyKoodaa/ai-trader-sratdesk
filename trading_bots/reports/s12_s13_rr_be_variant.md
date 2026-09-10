# S12/S13 XAUUSD M5 Scalps — RR-Widening & Break-Even/Trail-Varianten, 2026-09-09

**Verdikt: negativ, aber mit einem echten (zu kleinen) Teileffekt.**
Sowohl RR-Verbreiterung (1:3 statt ~1:1) als auch Break-Even+Trail heben
PF messbar an — aber selbst die beste Variante bleibt bei PF 0.47-0.54,
himmelweit von der 1.5-Gate-Schwelle und sogar von PF=1.0 (Breakeven)
entfernt. Kein Grid-Search auf diesen Achsen investiert — das Signal
selbst hat auf ausreichend grosser Stichprobe (25k-53k Trades) keinen
brauchbaren Rohedge, den Exit-Management retten koennte.

## Ausgangslage

Baseline-Triage (`reports/s12_rsi_scalp_xauusd_triage.log`,
`reports/s13_vwap_fade_scalp_xauusd_triage.log`, Vollhistorie XAUUSD M5
2019-2026, Strategie-eigene SPEC-Defaults) war strukturell unprofitabel:

| Strategie | n (7.5J) | PF | WR | avgR |
|---|---:|---:|---:|---:|
| S12 RSI-Scalp (tp=1.2xATR, sl=1.0xATR) | 26 296 | 0.331 | 45.5% | -0.241 |
| S13 VWAP-Fade-Scalp (tp=1.0xATR, sl=1.0xATR) | 53 541 | 0.419 | 48.9% | -0.222 |

Nutzer-Hypothese: hoehere RR (1:3+) oder Break-Even+Trailing-Stop statt
festem TP koennte "die langen Bars mitnehmen" und PF retten.

## Framework-Ergaenzung (generisch, nicht S12/S13-spezifisch)

`core/backtester.py` hatte bereits Trailing-Stop (`meta["trail_atr_mult"]`),
aber **keinen Break-Even-Mechanismus** — `strategies/s3_silver_bullet.py`
setzte zwar `meta["move_to_be_at_r"]`, aber die Engine las das nie (toter
Code, gleiche Kategorie wie der fruehere `Signal.risk_pct`-Bug dieser
Session). Neu implementiert: `Signal.meta["be_at_r"]`/`["be_buffer"]` —
einmaliger Ratchet-Move des SL auf Entry+Buffer, sobald die guenstige
Exkursion `be_at_r` x urspruenglichen SL-Abstand erreicht; kombinierbar
mit Trailing-Stop (beide ratchet-only, der jeweils guenstigere SL
gewinnt). 4 neue Unit-Tests (`tests/test_backtester.py::TestBreakEvenStop`),
danach in S12/S13 als optionale Params (`be_at_r`, `be_buffer_atr`,
`trail_atr_mult`, Default aus, rueckwaertskompatibel) verdrahtet + 5 neue
Meta-Wiring-Tests (`tests/test_s12_s13_be_trail.py`). Volle Suite danach
444/444 gruen.

## Ergebnis (Vollhistorie-Triage, XAUUSD M5 2019-2026, je Variante EIN Lauf)

| Variante | n | PF | WR | avgR | PnL |
|---|---:|---:|---:|---:|---:|
| **S12** Baseline (tp=1.2xATR) | 26 296 | 0.331 | 45.5% | -0.241 | -107 664 |
| S12 RR 1:3 (tp=3.0xATR) | 25 726 | **0.473** | 31.1% | -0.232 | -106 740 |
| S12 BE(1R)+Trail(1.5xATR) | 25 473 | 0.376 | 28.5% | -0.237 | -107 193 |
| S12 BE(0.5R)+Trail(1.0xATR) | 26 800 | 0.285 | 27.2% | -0.236 | -107 526 |
| **S13** Baseline (tp=1.0xATR) | 53 541 | 0.419 | 48.9% | -0.222 | -119 589 |
| S13 RR 1:3 (tp=3.0xATR) | 35 743 | **0.542** | 31.0% | -0.215 | -113 037 |
| S13 BE(1R)+Trail(1.5xATR) | 43 127 | 0.478 | 29.0% | -0.212 | -116 081 |

**Der Teileffekt ist real:** RR-Verbreiterung hebt PF bei beiden
Strategien um +43% (S12) bzw. +29% (S13) — Win-Rate faellt zwar deutlich
(45%→31%, 49%→31%, wie erwartet bei groesserem TP-Abstand), aber die
selteneren Gewinner sind gross genug, um netto etwas weniger zu
verlieren. Break-Even+Trail hilft ebenfalls, aber weniger als reine
RR-Verbreiterung.

**Aber:** `avgR` bleibt in JEDER Variante fest zwischen -0.21 und -0.24 —
der durchschnittliche Trade verliert weiterhin ~22% seines Risikos,
unabhaengig vom Exit-Management. Das ist der eigentliche Befund: PF
0.28-0.54 ist so weit von 1.0 (Breakeven) entfernt, dass kein
Exit-Tuning (weder RR-Grid noch BE/Trail-Parametrisierung) das auf 1.5
heben wird, ohne in Kurvenanpassung an eine mittlerweile 25k-53k-Trades-
grosse Stichprobe zu kippen, die strukturell KEINEN Rohedge zeigt. Der
Fehler sitzt im Entry (RSI-Extremwert- bzw. VWAP-Abweichungs-Reversal auf
XAUUSD M5 hat bei diesen Schwellen keine Vorhersagekraft), nicht im Exit.

## Fazit

Hypothese teilweise bestaetigt (RR/BE helfen messbar), aber nicht
ausreichend — kein Kandidat fuer eine volle WFA-Validierung. Kein
weiteres Exit-Grid-Search investiert (waere Kurvenanpassung an ein
Signal ohne Rohedge). Die generische Break-Even-Engine-Ergaenzung bleibt
unabhaengig von diesem negativen Ergebnis nuetzlich fuer kuenftige
Strategien (S3s `move_to_be_at_r` kann jetzt z. B. korrekt verdrahtet
werden).

## Offene naechste Schritte

1. S12/S13s RSI/VWAP-Reversal-Kern selbst muesste sich aendern (andere
   Schwellen, zusaetzliche Kontext-Filter wie Regime/Session), nicht nur
   der Exit — ausserhalb des Umfangs dieser Session.
2. S18 (Scalp Signal Bot, XAUUSD M5) separat gepruefte: nur 3 Trades in
   7,5 Jahren bei Default-Parametern (strukturell zu selten, s.
   `reports/s18_scalp_signal_bot_xauusd_triage.log`) UND rechnerisch sehr
   teuer (~20 CPU-Minuten fuer einen einzigen Vollhistorie-Lauf) — fuer
   eine volle WFA in dieser Form nicht praktikabel.
3. M5 als Zeitebene fuer XAUUSD bleibt insgesamt ohne Erfolg: weder das
   ICT-Setup (S3, 3 Trades/7,5J) noch die drei getesteten Scalp-Signale
   (S12/S13/S18) zeigen einen validierbaren Edge. H1 (S9q, 6/10 Gates)
   bleibt der staerkste XAUUSD-Kandidat dieses Projekts insgesamt.
