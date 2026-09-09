# Deep-Dive: "XAUUSD_TrendPullback_ATR.mq5"

**Quelle:** vollstaendiges MT5/MQL5-EA-Snippet. Portierung:
`strategies/analyze_e241bb189fa2.py` (Annahmen im Docstring). Config:
`configs/analyze_e241bb189fa2.yaml`. Kein Profil/Preset im Original — ein
einziger Parametersatz.

## Handelsidee (Original)

H4-EMA50-Trendfilter (Preis + 2-Bar-Steigung), Einstieg M15 bei
EMA20-Pullback + Bestaetigungskerze. SL = enger von ATR-Multiplikator und
Struktur-Extremum, TP = 2R fest. Session-/Spread-/Min-ATR-Filter,
Break-Even bei +1R.

## Wichtigste Portierungs-Annahmen

1. **Kein Break-Even** — Engine kennt nur festen SL/TP oder
   `tp_converts_to_trail`, keinen "SL auf B/E, TP haelt" Hook. SL/TP
   bleiben fest -> pessimistischer als Original.
2. Spread-Filter entfaellt (globales Kostenmodell statt Bar-Filter).
3. `InpMinATRPoints=100` -> Preis-Einheiten (`min_atr_price=1.00`) —
   die im Quick-Check bemaengelte Magic Number, hier nur explizit.
4. Session-Stunden als UTC statt unbekannter Broker-Serverzeit.
5. Sizing/One-Position/Magic-Number laufen ueber Engine-Config.

## Vorab-Triage (Vollhistorie, 27 Kombos: sl_atr_mult x risk_reward x min_atr_price, 32 Worker)

| Variante | n | PF | WR% | avgR |
|---|---|---|---|---|
| sl=2.0 rr=3.0 minatr=1.5 (bestes) | 1639 | 1.005 | 26.3 | 0.012 |
| sl=2.0 rr=2.0 minatr=1.5 | 1978 | 0.997 | 34.8 | 0.004 |
| … 24 weitere | | 0.87–0.98 | 25–41 | -0.01 bis -0.07 |
| sl=1.0 rr=2.0 minatr=0.5 (schlechtestes) | 2520 | 0.866 | 33.6 | -0.068 |

**Nur 1 von 27 Kombos knapp ueber PF=1.0 (trivial), Rest darunter** — kein
Edge erkennbar, kein Fall in Naehe von PF(1x)>=1.5.

## Vollstaendige WFA (12 Folds, 24M IS/6M OOS, 2019–2026, OOS n=1619)

| Gate | Ergebnis | Status |
|---|---|---|
| n(OOS)>=300 | 1619 | PASS |
| WFE-Median>=0.5 | 0.997 | PASS |
| Folds WFE>=0.5>=60% | 100% | PASS |
| PF(1x)>=1.5 | 0.985 | **FAIL** |
| PF(2x)>=1.2 | 0.913 | **FAIL** |
| PF(3x)>=1.0 | 0.848 | **FAIL** |
| DSR>=0.95 | 0.011 | **FAIL** |
| PBO<0.10 | 0.257 | **FAIL** |
| Params<=Budget | 3<=53 | PASS |
| MC p95-MaxDD<=8% | 54.79% | **FAIL** |

**GATES NICHT BESTANDEN** (6/10). IS-Bests je Fold: PF≈0.92–1.22, OOS-PF
schwankt 0.57–1.34 ohne Muster — Rauschen statt Edge. DSR=0.011: Erfolg
statistisch nicht von Zufall unterscheidbar. MC p95-MaxDD=54.79% (Gate 8%)
zeigt inakzeptables Tail-Risiko.

## Fazit

Solide Grundidee ohne Look-Ahead-Bias, aber **kein handelbarer Edge**:
Triage (26/27 Kombos PF<1.0) und WFA (PF=0.985, DSR=0.011, PBO=0.257)
stimmen ueberein — Ergebnis oszilliert um Break-even, unabhaengig vom
Parameter. Die Quick-Check-Magic-Numbers sind nicht die Ursache; selbst
die beste Grid-Kombination bleibt bei PF≈1. **Nicht live-tauglich.** Eine
erneute WFO mit anderem Parameterraum wird vermutlich nicht helfen — der
Kern-Trigger (EMA20-Pullback + H4-EMA50-Trend ohne Mindestabstand/Slope-
Schwelle) ist zu generisch, um sich von Marktrauschen abzuheben.
