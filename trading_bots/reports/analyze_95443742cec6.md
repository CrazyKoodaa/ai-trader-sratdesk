# Deep-Dive: "XAU Velocity External Validation F7" (Profil-Variante)

**Quelle:** extern eingereichtes, vollstaendiges MT5/MQL5-EA-Snippet (Teile
1-3B). Dieselbe EA-Familie wie `analyze_2166fb052559` (abgebrochenes Snippet,
dezidiert verworfen) und `analyze_a3d5ea031833` (vollstaendig, aber F7 fest
eingefroren). **Neu hier:** die 8 benannten FTMO-Management-Presets (F0-F7)
sind als expliziter Auswahlparameter `risk_profile` modelliert statt
verschmolzen — Portierung: `strategies/analyze_95443742cec6.py`, Config:
`configs/analyze_95443742cec6.yaml`.

## Handelsidee & Annahmen

XAUUSD-MTF-Trendfolge/Retracement (H4-Kontext, H1-3-EMA-Trend, M15-ADX/DI-
Regime + Struktur, Impuls-Erkennung + Retracement + FVG), additiver
Quality-Score mit adaptiver Mindestschwelle je Impuls-Guete (STANDARD/STRONG/
ELITE/REJECT, inkl. "Weak Raw Quality Exception" bei Score>=92). Volle
Annahmenliste im Docstring der Strategiedatei; wichtigste: M5-Entry-TF nicht
separat gefuehrt (M15 uebernimmt TF_SETUP+TF_ENTRY), und die Lock-Mechanik
(SL-Fixierung bei +Trigger-R auf +Lock-SL-R) wird durch `tp_converts_to_trail`
angenaehert — **`lock_sl_r` und `tp_target_r` fliessen dadurch NICHT in die
Engine ein**, nur `lock_trigger_r` (als TP-Trail-Trigger) ist wirksam.

## FTMO-Profile

| Profil | TP-Ziel | Lock-Trigger | Lock-SL | Engine-wirksam |
|---|---|---|---|---|
| F0/F1 | 8.0R | +2.75R | 0.75/1.00R | nur Trigger — F0≡F1 |
| F2/F3/F6 | 8.0/8.5R | +3.00R | 0.75/1.00R | nur Trigger — F2≡F3≡F6 |
| F4/F5/F7 | 8.0/8.5R | +3.25R | 0.75/1.00R | nur Trigger — F4≡F5≡F7 (Original-Default) |

Da `lock_sl_r`/`tp_target_r` nicht engine-wirksam sind, kollabieren die 8
Profile auf **3 tatsaechlich unterscheidbare Verhaltensgruppen** — dies ist
in der Triage direkt sichtbar (identische Kennzahlen je Gruppe) und eine
direkte Konsequenz der dokumentierten Annahme, kein Bug.

## Vorab-Triage (Vollhistorie XAUUSD, 16 Kombis, 16 parallele Worker, ~2 Min)

| Profil-Gruppe | n | PF | WR | avgR | MaxDD (Bal.) | PnL |
|---|---|---|---|---|---|---|
| F0/F1 (Trigger 2.75) | 286 | **1.089** | 33.9% | +0.052 | 19 181 | +8 969 |
| F2/F3/F6 (Trigger 3.00) | 284 | 1.046 | 33.5% | +0.031 | 22 413 | +4 461 |
| F4/F5/F7 (Trigger 3.25, **Original-Default**) | 284 | 0.974 | 32.7% | **-0.004** | 23 264 | -2 470 |

Bemerkenswert: das Original-Team fror den Live-Build auf **F7** ein — genau
die in dieser Python-Naeherung **schwaechste** Gruppe (PF<1, negativer avgR).
Ein looserer Expansion-Filter (1.20 statt 1.35, Score-Standard 78 statt 84)
aendert nichts an der Rangfolge. Trade-Zahl (~284-296 ueber ~7 Jahre) ist
generell sehr duenn.

## WFA (`configs/analyze_95443742cec6.yaml`, is=24M/oos=6M, param_space =
`risk_profile`×`trail_atr_mult`, 12 Folds)

Gewinner pro Fold ist fast immer **F0** (Trigger 2.75) — bestaetigt die
Triage. WFE-Median hoch (0.995), aber irrefuehrend: bei PF nahe 1.0 ist die
IS/OOS-Differenz trivial klein, WFE sagt hier nichts ueber echte Robustheit.

| Gate | Ergebnis | Status |
|---|---|---|
| n(OOS) >= 300 | 216 | **FAIL** |
| WFE-Median >= 0.5 | 0.995 | PASS |
| Folds WFE>=0.5 (>=60%) | 92% | PASS |
| PF(1x) >= 1.5 | 1.057 | **FAIL** |
| PF(2x) >= 1.2 | 0.895 | **FAIL** |
| PF(3x) >= 1.0 | 0.768 | **FAIL** |
| DSR >= 0.95 | 0.048 | **FAIL** |
| PBO < 0.10 | 0.186 | **FAIL** |
| MC p95-MaxDD <= 8% | 19.10% | **FAIL** |

**7 von 9 Gates gefailed**, inkl. der haertesten (PF-Stress, DSR, PBO,
MaxDD). Einzelne OOS-Folds streuen extrem (PF 0.33 bis 4.72) bei zu wenig
Trades pro Fold fuer belastbare Aussagen.

## Fazit

**Nicht bestanden.** Die Profil-Aufschluesselung war der eigentliche
Erkenntnisgewinn: sie zeigt, dass der frueher-triggernde Lock (F0/F1)
durchweg besser abschneidet als das vom Original als "Benchmark" gefuehrte
F7 — ein Hinweis, dass die Original-Preset-Wahl selbst nicht datengetrieben
war. Aber selbst die beste Gruppe (F0, PF=1.089 in Triage, WFA-OOS-PF=1.057)
bleibt weit unter der Gate-Schwelle (1.5), scheitert am Kosten-Stress (PF(3x)
<1) und zeigt hohe Overfitting-Indikatoren (DSR≈0.05, PBO=0.19). Kombiniert
mit dem in beiden Vorgaenger-Reviews festgehaltenen Overfitting-Verdacht der
Score-Schwellenlandschaft: die Handelsidee (adaptiver Quality-Router) ist
strukturell sauber implementiert, aber weder in der Gesamt- noch in der
Pro-Profil-Betrachtung als eigenstaendig handelbare Strategie tragfaehig.
