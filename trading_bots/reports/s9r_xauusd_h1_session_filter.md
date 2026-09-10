# S9r — Session-Filter-Hypothese auf S9 DonchianTrend (XAUUSD H1), 2026-09-09

**Verdikt: negativ.** Der Session-Filter (Asian-Session ausblenden,
nur London/NY 07:00-21:00 UTC handeln) macht S9 **schlechter, nicht
besser** — auf jeder einzelnen offenen Gate-Metrik. **5/10 Gates**
(vs. S9q-Baseline: 6/10). Einzige echte Verbesserung: keine.

## Ausgangslage

`reports/s9_xauusd_h1_metaoverfitting_finding.md` (dieselbe Session,
frueher) hatte nach dem Meta-Overfitting-Fund (S9h-p) eine disziplinierte
Baseline (S9q, `configs/s9q_donchian_trend_h1_disciplined.yaml`) etabliert:
6/10 Gates, PBO=0.000 (kein Overfitting — echter, aber zu schwacher Edge),
und als naechsten Schritt empfohlen: "echte kausale Verbesserungs-
hypothesen ... z. B. Session-Filter ... EIN Lauf, Ergebnis akzeptieren,
nicht nachjustieren."

## Hypothese

XAUUSD-H1-Breakouts waehrend der Asian-Session (00:00-07:00 UTC, duenne
Liquiditaet) reissen haeufiger ab / reverten, statt zu laufen, als
Breakouts waehrend London/NY. Ein Filter, der nur London/NY-Breakouts
zulaesst, sollte PF(1x) heben und MC-DD senken (Kosten: weniger Trades).

## Implementierung

`strategies/s9_donchian_trend.py`: neuer optionaler Parameter
`session_filter` (Default `"off"`, rueckwaertskompatibel) +
`session_start_utc`/`session_end_utc` (Default `"07:00"`/`"21:00"`).
Nutzt `core/time_engine.in_session` (DST-sicher, hier `session="UTC"`
also ohne DST-Verschiebung). Fenster **07:00-21:00 UTC ist nicht aus
dieser Session abgeleitet** — es ist SPEC.md's eigene Konvention
(identisch zu S1 "Session 07-17 UTC" / S5 "Session 07-21 UTC"),
wiederverwendet statt neu gefittet. 5 neue Unit-Tests
(`tests/test_s9.py`), volle Suite danach 435/435 gruen.

## Config (`configs/s9r_donchian_trend_h1_session.yaml`)

**Wortwoertlich S9q's Grid**, nur `session_filter: [off, on]` als NEUE
5. WFO-Dimension ergaenzt (54 -> 108 Kombos). `don_len`/`sl_atr_mult`/
`trail_atr_mult`/`adx_min`-Werte unveraendert — jede Gate-Differenz zu
S9q ist damit ausschliesslich dem neuen Filter zuzurechnen, nicht einem
nachjustierten Kern-Grid.

## Wichtiger Stolperstein (Methodik, nicht Ergebnis)

Der erste Lauf (`--data-dir` weggelassen -> Default `"data"`, XAUUSD H1
dort nur 2019-2026) lieferte nur 12 Folds/n=319 statt S9q's 20 Folds/
n=573 — **nicht vergleichbar**, verworfen ohne Ergebnis zu werten.
S9q (und die S21-Serie, s. `configs/s21e_goldreaper_plateau_only.yaml`
Kommentar "mc5-Baseline auf data_mt5, 2015-2026") liefen gegen
`data_mt5/XAUUSD_H1.parquet` (2015-2026, echte Broker-Daten). Re-Run mit
`--data-dir data_mt5` explizit gesetzt, s. unten. **Für jeden künftigen
XAUUSD-H1-Vergleich mit S9q/S21 gilt: `--data-dir data_mt5` ist Pflicht**
— der CLI-Default `"data"` zeigt auf einen anderen (kürzeren) Datensatz
und liefert stillschweigend falsche Fold-/Trade-Zahlen ohne Fehlermeldung.

## Ergebnis (`reports/wfa_s9r_donchian_xauusd_h1_session_mt5`, `--data-dir data_mt5`, 20 Folds)

| Metrik | S9q (Baseline, kein Session-Filter) | S9r (+ Session-Filter-Dimension) | Delta |
|---|---:|---:|---:|
| n(OOS) | 573 | 526 | -47 |
| PF(1x) | 1.173 | 1.084 | **schlechter** |
| PF(2x) | 1.087 | 1.003 | **schlechter** |
| PF(3x) | 1.010 (PASS) | 0.933 (**FAIL, kippt**) | **schlechter** |
| WFE-Median | 0.823 | 0.583 | schlechter (beide PASS) |
| DSR | 0.226 | 0.040 | **schlechter** |
| PBO | 0.000 | 0.000 | gleich (beide sauber) |
| MC p95-MaxDD | 12.43% | 15.86% | **schlechter** |
| **Gates** | **6/10** | **5/10** | **-1** |

Fold-Log zeigt: `session_filter` gewinnt in der IS-Grid-Search
uneinheitlich (mal "on", mal "off" je Fold, kein stabiler Sieger) — die
zusaetzliche Dimension fuegt der WFO Waehl-Flaeche eher Rauschen hinzu,
als robusteres Signal zu liefern. Das Ausblenden der Asian-Session hat
in diesem konkreten Donchian/H1-Aufbau keinen der befuerchteten
"Fehlausbrueche" gefiltert, die stattdessen offenbar ueber alle Sessions
verteilt auftreten.

## Fazit

Hypothese widerlegt (fuer diesen konkreten Signal-Mechanismus). Per
Vereinbarung: kein Nachjustieren des Fensters, keine feinere
Session-Sweep — das Ergebnis wird als ehrlicher Negativ-Befund
akzeptiert. **S9q bleibt der beste disziplinierte XAUUSD-H1-Donchian-
Stand dieser Linie (6/10 Gates).**

## Offene naechste Schritte (nicht in dieser Session verfolgt)

1. Andere kausale Hypothesen fuer S9 einzeln testen (Volume-Profile-
   Konfluenz aus `core/volume_profile.py`, HTF-H4-Bias) — je EIN
   disziplinierter Lauf.
2. S21 GoldReaper bleibt die gate-technisch beste Einzelmetrik (7/10),
   aber mit dokumentiertem strukturellem PBO=0.343-Problem
   (`reports/s21_xauusd_pbo_investigation.md`) — nicht durch weitere
   Filter auf demselben EMA/RSI-Kern loesbar.
3. M5 bleibt weitgehend unerforscht: die einzige XAUUSD-M5-Strategie im
   Projekt (S3 SilverBullet/ICT) erzeugt nur 3 Trades in 7,5 Jahren
   (strukturell zu selten fuer das n>=300-Gate) — S12/S13/S18
   (RSI-Scalp/VWAP-Fade-Scalp/Scalp-Signal-Bot) haben Code, aber noch
   keine XAUUSD-Config/keinen WFA-Lauf.
