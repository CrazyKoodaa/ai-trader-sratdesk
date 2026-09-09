# Deep-Dive: XAUUSD Multi-Timeframe Trendfolge/Pullback (Presets)

**Quelle:** extern eingereichtes MT5-EA-Snippet `XAUUSD_TrendPullback_Presets_v2.mq5`
(Research-EA mit explizitem Preset-System). Portierung: `strategies/analyze_7e9787b27c5c.py`,
Config: `configs/analyze_7e9787b27c5c.yaml`.

## Handelsidee & Annahmen

H4-Regime (EMA(50)-Slope, ATR-normalisiert, + ADX(14)) → H1-Impulserkennung
(Breakout ueber Swing-High/Low der letzten 8 Bars, Range ≥ Impuls-ATR-Min ×
ATR) mit Fibonacci-Retracement-Zone (0.382/0.500–0.618) → M15-Sweep/Reclaim
als Entry-Trigger. Fixe SL/TP (2R), kein Trail, kein Zeit-Exit (Original-
Eigenschaft). Annahmen (Details im Docstring): "Bars seit Impuls" via
Scan-Index statt des mehrdeutigen `iBarShift`-Off-by-ones im Original;
`EnforceMinimumStopDistance` nicht portiert (Engine kennt kein Stops-
Level); Konto-Schutzmechanismen (Daily-Loss/Equity-DD/Trades-pro-Tag)
nicht abgebildet (kein Portfolio-State in `on_bar`); `min_atr_price` und
`pullback_range_max_ratio` (Quick-Check: unbegruendet) fix, NICHT
gesweept; `trend_slope_min_atr` zusaetzlich als 2. `param_space`-Achse.

## Profilvergleich (5 Presets, s. Docstring-Tabelle)

Triage: Vollhistorie 2019-2026, 15 Kombis (5 Profile × 3 `trend_slope_min_atr`-
Werte), 32 parallele Worker, ~130s. Spannen unten = Range ueber die 3
Slope-Werte je Profil.

| Profil | ADX / Impuls-ATR / Retr.unten / Pullback-Bars / SL-Puffer | Triage n | Triage PF | Triage WR | WFA-Fold-Siege (von 12) |
|---|---|---|---|---|---|
| baseline | 20 / 1.25 / 0.382 / 6 / 0.15 | 80–93 | 0.83–0.89 | 30–32% | 0 |
| conservative | 25 / 1.50 / 0.382 / 4 / 0.25 | 43–47 | **1.37–1.60** | 43–47% | 4 |
| balanced (Original-Default) | 25 / 1.50 / 0.382 / 6 / 0.20 | 57–64 | 1.00–1.14 | 34–37% | 1 |
| fast_pullback | 20 / 1.25 / 0.500 / 4 / 0.15 | 37–41 | **1.26–1.38** | 42–44% | 5 |
| strong_trend | 25 / 1.50 / 0.500 / 6 / 0.25 | 36–39 | 0.93–1.06 | 33–36% | 2 |

`baseline` ist durchweg am schwaechsten und wird in der WFA nie gewaehlt —
konsistent mit der Triage. `conservative`/`fast_pullback` dominieren beide
Sichten.

## WFA (`is=24M/oos=6M`, `param_space` = `risk_profile`×`trend_slope_min_atr`, 12 Folds, 32 Worker)

| Gate | Ergebnis | Status |
|---|---|---|
| n(OOS) ≥ 300 | 34 | **FAIL** |
| WFE-Median ≥ 0.5 | 0.285 | **FAIL** |
| Folds WFE≥0.5 (≥60%) | 45% | **FAIL** |
| PF(1x) ≥ 1.5 | 1.293 | **FAIL** |
| PF(2x) ≥ 1.2 | 1.197 | **FAIL** |
| PF(3x) ≥ 1.0 | 1.105 | PASS |
| DSR ≥ 0.95 | 0.143 | **FAIL** |
| PBO < 0.10 | 0.014 | PASS |
| ≤1 Param/30 OOS-Trades | 2 Params bei n=34 | **FAIL** |
| MC p95-MaxDD ≤ 8% | 4.77% | PASS |

**7 von 10 Gates gefailed.** Fold-Sieger sind fast durchweg conservative/
fast_pullback, OOS-PF streut aber extrem (0.00 bis inf je Fold) bei nur
~2-3 Trades/Fold-OOS.

## Fazit

**Nicht bestanden.** Der Profilvergleich war der eigentliche Erkenntnis-
gewinn: `baseline` (laxestes Preset) ist eindeutig am schwaechsten,
`conservative`/`fast_pullback` (straffere ADX/Impuls-Schwellen, kuerzeres
Pullback-Fenster) sind in Triage UND WFA konsistent vorn. Trotzdem
scheitert selbst die beste Kombination am haertesten Problem: die Vier-
Filter-Kaskade (H4-Regime + H1-Impuls + Retracement-Zone + M15-Reclaim)
laesst ueber 7,7 Jahre XAUUSD nur 34-93 Trades zu — der WFA-OOS-Sample
(n=34, ~3/Fold) ist um eine Groessenordnung zu duenn fuer belastbare
Aussagen (DSR≈0.14, WFE-Median 0.285 zeigt IS/OOS-Bruch; PBO/MC-DD PASS
eher Artefakt geringer Teststaerke als echtes Robustheits-Signal). Die Idee
ist sauber, nicht-repainting implementiert, aber in dieser Form nicht
tragfaehig — am ehesten zu retten ueber eine gelockerte Filterkaskade oder
Pooling ueber mehrere Symbole/laengere Historie.
