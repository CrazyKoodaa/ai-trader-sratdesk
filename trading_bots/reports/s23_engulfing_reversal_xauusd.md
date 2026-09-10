# S23 Engulfing-Reversal an Donchian-Extremen (XAUUSD) — negativ, 2026-09-09

**Verdikt: nicht tragfaehig.** Die Drei-Filter-Kombination (Struktur-
Extrem + echtes 2-Kerzen-Engulfing + Volumen-Bestaetigung) hat auf H4
einen erkennbaren, mit staerkeren Filtern steigenden PF -- aber
strukturell zu wenige Trades fuer das n≥300-Gate, mit einem klaren
Qualitaet-vs-Menge-Tradeoff, den keine der getesteten Parametrisierungen
aufloest.

## Idee

Neu in diesem Projekt: klassisches 2-Kerzen-Engulfing-Reversal, aber nur
gewertet an einem echten Donchian-Struktur-Extrem UND mit echter
MT5-Tick-Volumen-Bestaetigung (>= `vol_mult` x Durchschnitt) -- strenger
als S9 (reine Struktur, kein Muster) und S15 (Ein-Kerzen-Muster ohne
Struktur-Erfordernis, PF~0.98, s. `reports/s14_xauusd_squeeze_volume.md`).

## Triage (Vollhistorie XAUUSD, `data/` = echtes Volumen)

**H4 (Default-Params):** n=44, PF=1.204 -- PF(1x)/PF(2x) FAIL, PF(3x) PASS.
**H1 (identische Params):** n=148, PF=0.519, WR=27% -- klar unprofitabel
(Muster funktioniert auf H1 nicht, vermutlich zu verrauscht fuer
"Struktur-Extrem" auf dieser Aufloesung).

## Parameter-Nachbarschaft (H4, 9 Kombos, um Reichweite vs. Guete zu pruefen)

| don_len | vol_mult | n | PF | WR |
|---:|---:|---:|---:|---:|
| 10 | 1.0 | 103 | 0.815 | 36.9% |
| 10 | 1.2 |  82 | 0.978 | 41.5% |
| 10 | 1.5 |  60 | **1.420** | 48.3% |
| 15 | 1.0 |  84 | 0.966 | 40.5% |
| 15 | 1.2 |  67 | 1.155 | 44.8% |
| 15 | 1.5 |  50 | **1.830** | 54.0% |
| 20 | 1.0 |  71 | 0.675 | 38.0% |
| 20 | 1.2 |  59 | 0.770 | 42.4% |
| 20 | 1.5 |  44 | 1.204 | 52.3% |

**Klares Muster:** straffere Volumen-Schwelle (1.5) gibt durchgehend
besseren PF UND bessere Winrate als lockere (1.0) -- die Volumen-
Bestaetigung traegt echt zur Signal-Qualitaet bei, kein Zufall. Aber genau
das treibt `n` in die falsche Richtung: die beste PF-Zelle (don_len=15,
vol_mult=1.5, PF=1.83) hat nur n=50 -- selbst die LOCKERSTE getestete
Zelle (don_len=10, vol_mult=1.0, n=103) bleibt bei ~1/3 des 300er-Gates
UND ist bereits unprofitabel (PF=0.815). Es gibt in dieser
Parameter-Nachbarschaft keine Zelle, die beides zugleich erfuellt.

## Fazit

Kein WFA-Lauf investiert -- waere reine Kurvenanpassung an eine Handvoll
Trades. Die Drei-Filter-Kombination ist vermutlich ein echtes, aber zu
seltenes Muster fuer XAUUSD H4 (nur ~1900 H4-Bars in der gesamten
7,5-Jahres-Historie verfuegbar -- zu wenig Gelegenheiten fuer ein derart
konjunktives Signal, um das 300er-Gate zu erreichen, ohne die
qualitaetsentscheidende Volumen-Schwelle so weit zu senken, dass der Edge
verschwindet). Gleiche Kategorie wie S3 SilverBullet (M5-ICT, 3 Trades/7,5J)
und S18 (Scalp Signal Bot, 3 Trades/7,5J) -- interessant, aber mit den in
diesem Projekt verfuegbaren Datenmengen nicht validierbar.

## Artefakte

`strategies/s23_engulfing_reversal.py` (8 Unit-Tests, alle gruen),
`configs/s23_engulfing_reversal_xauusd_h4.yaml`/`_h1.yaml`,
`reports/s23_xauusd_h4_triage`, `reports/s23_xauusd_h1_triage`.
