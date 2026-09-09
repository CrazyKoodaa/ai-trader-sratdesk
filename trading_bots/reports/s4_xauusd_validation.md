# S4 LondonBreakout auf XAUUSD — Validierungsbericht

**Datum:** 2026-09-06
**Strategie:** `strategies/s4_london_breakout.py` (S4, SPEC §5/S4)
**Config:** `configs/s4_london_breakout_xau.yaml` (neu, Variante von `s4_london_breakout.yaml`/USDJPY)
**Verdikt: NICHT TRAGFÄHIG — nicht für Live-Betrieb freigegeben.** Gleiche Kategorie wie S6.

Nebenbefund mit größerer Tragweite: der erste Validierungslauf hat einen echten
Bug im Backtest-Engine (`core/backtester.py`) aufgedeckt, der bei Retest-Limit-
Strategien mit engem Stop-Loss beliebig hohe Profit-Faktoren vortäuschen kann.
Der Bug ist behoben (siehe unten), betrifft potenziell jede künftige Strategie
mit `entry_type="limit"`.

---

## 1. Zeitlinie

1. **Konfiguration angelegt** — `configs/s4_london_breakout_xau.yaml`: XAUUSD-
   Kostenmodell (Spread 35 Pts, wie S1/S3/S5), `pip_size` von USDJPYs 0.01 auf
   0.1 umgerechnet (Konvention: 1 Pip = 10 Points, wie bei USDJPY point 0.001→
   pip 0.01).
2. **Smoke-Test** (nur `tp_r` im Grid, Rest auf plausible Startwerte fixiert:
   `entry_mode=close`, Filter an) — plausible Größenordnung, 2 von 11 Gates
   verfehlt.
3. **Volles WFO-Grid** (576 Parameterkombinationen × 12 Folds) — Ergebnis
   PF bis `inf`. Auf den ersten Blick ein Traumergebnis, tatsächlich ein
   Backtester-Bug (Abschnitt 3).
4. **Root-Cause-Analyse** → Bug in `core/backtester.py` gefunden und behoben
   (Abschnitt 4).
5. **S3 SilverBullet gegengeprüft** — vom selben Bug nicht betroffen
   (Abschnitt 5).
6. **Volles WFO-Grid erneut, mit korrigiertem Engine** — plausible, aber
   klar negative Zahlen (Abschnitt 6). Endverdikt.

---

## 2. Lauf 1 — Smoke-Test (Referenzgröße)

Fixe Werte (`range_min_pips=30`, `range_max_adr=0.5`, `retest_sl_pips=30`,
`atr_filter=on`, `ema_filter=on`, `entry_mode=close`), nur `tp_r` im Grid.

```
Folds: 12 | OOS-Trades: 350 | OOS-PF: 1.348 | WFE-Median: 1.206
PF(2x): 1.254 | PF(3x): 1.175 | DSR: 0.957 | PBO: 0.0
```

| Gate | Wert | Status |
|---|---|---|
| n(OOS) ≥ 300 | 350 | PASS |
| WFE-Median ≥ 0.5 | 1.206 | PASS |
| WFE ≤ 1.0 (Lookahead-Verdacht) | 1.206 | **FAIL** |
| ≥60% Folds WFE≥0.5 | 92% | PASS |
| PF(1x) ≥ 1.5 | 1.348 | **FAIL** |
| PF(2x)/(3x) | 1.254 / 1.175 | PASS |
| DSR ≥ 0.95 | 0.957 | PASS |
| PBO < 0.1 | 0.0 | PASS |
| MC p95-MaxDD ≤ 8% | 7.0% | PASS |

9/11 Gates bestanden — deutlich besser als das spätere Endergebnis, aber mit
einer Auffälligkeit (WFE>1: OOS schneidet im Mittel besser ab als IS), die
sich im Nachhinein durch den außergewöhnlichen Gold-Bullenmarkt 2026 in den
jüngsten Fold-Fenstern erklärt (Fold 11: IS-PF 1.31 → OOS-PF 4.77).

---

## 3. Lauf 2 — Volles Grid, Backtester-Bug

576 Parameterkombinationen je Fold, keine Einschränkung.

```
Folds: 12 | OOS-Trades: 226 | OOS-PF: 17.086 | WFE-Median: 0.946
PF(2x): 8.168 | PF(3x): 4.574 | DSR: 1.0 | PBO: 0.0
```

Gewinner-Parameter in den meisten Folds: `entry_mode=retest`, `atr_filter=off`,
`ema_filter=off`, `range_min_pips=20`, `retest_sl_pips=20`.

Fold-OOS-PF: `31.62, inf, 122.88, inf, 438.68, 130.75, inf, inf, inf, inf, 1.62, 1.40`

9 von 10 Gates PASS — aber **`n(OOS) ≥ 300` FAIL (n=226)**, deshalb
`ERGEBNIS: GATES NICHT BESTANDEN` trotz der spektakulären PF-Werte. Ein PF von
`inf` (null Verlust-Trades über 6 Monate) ist in echten Märkten praktisch
ausgeschlossen — starkes Indiz für ein Artefakt im Messverfahren, nicht für
echten Edge.

---

## 4. Root Cause & Fix

**Fundstelle:** `core/backtester.py`, Pending-Limit-Fill-Logik (vormals
Zeile 393–395, dupliziert in der nie aufgerufenen `_try_fill_limit`):

```python
sl_touched = (l <= order.sl) if d > 0 else (h >= order.sl)
if sl_touched:
    continue  # konservativ: verworfen (SL waere zuerst dran)
```

Wenn ein Limit-Entry (Retest) **und** der Stop-Loss **in derselben Bar**
berührt wurden, wurde der Trade komplett verworfen — nicht als Verlust
gezählt, sondern so behandelt, als hätte er nie stattgefunden. Ein
bestehender Test (`test_limit_and_sl_same_bar_discards_order`) erwartete
genau dieses Verhalten; es war eine bewusste, aber in der Wirkung
nicht-konservative Designentscheidung (sie senkt die gemessene Verlustquote,
statt sie im Zweifel zu überschätzen).

**Warum das bei XAUUSD explodiert:** `retest_sl_pips=20 × pip_size=0.1` =
2 USD SL-Abstand. XAUUSD-H1-Bars bewegen sich routinemäßig $5–30+. Ein derart
enger Stop wurde fast immer in derselben Bar getroffen wie der Retest-
Einstieg → reihenweise Verlierer verschwanden aus der Stichprobe, nur die
Gewinner blieben übrig → PF bis `inf`. Bei USDJPY tritt derselbe Mechanismus
auf, fällt aber praktisch nicht auf, weil dort SL-Distanz und Bar-Volatilität
besser zueinander passen.

**Fix** (`core/backtester.py`):

- `BacktestConfig.intrabar` generalisiert von hart `"m1"` auf jede in
  `TF_MINUTES` bekannte feinere Zeitreihe (`"m1"`, `"m5"`, …), sofern deren
  Daten geladen sind.
- Neue Methode `_try_fill_limit_fine()`: löst Fill **und** SL/TP-Kollision
  chronologisch über die feineren Bars auf (Fill zuerst, danach ab exakt
  dieser Fine-Bar auf SL/TP prüfen — konservativ SL vor TP bei Gleichstand,
  wie im bestehenden `_resolve_sl_tp`), statt bei Kollision in der groben
  Bar zu raten.
- Ohne geladene Feindaten bleibt der bisherige `stop_first`-Fallback
  unverändert (Discard bei Kollision — die einzig mögliche Annahme ohne
  bessere Datengrundlage).
- Neuer Diagnose-Zähler `BacktestResult.diagnostics["limit_sl_collision_discards"]`
  für zukünftige Sichtbarkeit dieses Effekts bei anderen Strategien/Symbolen.
- `configs/s4_london_breakout_xau.yaml`: `timeframes` um `M5` ergänzt,
  `intrabar: m5` gesetzt.

**Verifiziert:**
- 4 neue Tests (`tests/test_backtester.py::TestLimitOrdersFineIntrabar`) +
  alle 390 bestehenden Tests grün.
- Der ursprüngliche Bug-Fall (`entry_mode=retest`, `range_min_pips=20`,
  `retest_sl_pips=20`, Filter aus, Fold 2019–2021) lieferte vorher PF=inf
  bei einem Bruchteil der eigentlichen Trades; mit dem Fix: **PF=1.11 bei
  447 Trades** (vorher summierten sich alle 12 Folds zusammen auf nur 226
  Trades — der Großteil der echten Verlierer fehlte).

---

## 5. Gegenprobe: S3 SilverBullet

S3 nutzt ebenfalls `entry_type="limit"` (NAS100 + XAUUSD). Geprüft, ob die
bereits "verifizierten" S3-Zahlen vom selben Effekt profitiert haben könnten.

| Symbol | Trades | PF (1x) | Kollisions-Discards |
|---|---|---|---|
| NAS100 | 6 | 0.417 | **0** |
| XAUUSD | 3 | 0.824 | **0** |

**Nicht betroffen.** S3 handelt bereits nativ auf M5 (12× feiner als S4s H1)
und nutzt einen ATR-relativen SL-Puffer (`sl_buffer_atr: 0.3`) statt eines
starren Mini-Pip-Werts — beides senkt die Kollisionswahrscheinlichkeit
drastisch. Die Zahlen stimmen exakt mit dem bestehenden Stress-Report
(`reports/strategies.s3_silver_bullet_*/stress.md`) überein: S3 war mit
n=3–6 Trades und PF<1 schon vorher schwach, nicht durch den Bug
schöngerechnet. Kein WFA-Rerun für S3 nötig — eine feinere Zeitreihe als M5
existiert für NAS100/XAUUSD ohnehin nicht (kein M1-Datensatz vorhanden), der
neue Auflösungsmechanismus hätte also keine Datengrundlage.

---

## 6. Lauf 3 — Volles Grid, korrigierter Engine (Endergebnis)

576 Parameterkombinationen × 12 Folds, identisches Grid wie Lauf 2, jetzt mit
dem gefixten Backtester.

```
Folds: 12 | OOS-Trades: 1309 | OOS-PF: 0.942 | WFE-Median: 1.029
PF(2x): 0.877 | PF(3x): 0.816 | DSR: 0.0 | PBO: 0.0
```

Gewinner-Parameter in 11 von 12 Folds identisch: `entry_mode=close`,
`atr_filter=off`, `ema_filter=off`, `range_min_pips=20`, `range_max_adr=0.4`,
`tp_r` wechselnd 1.5/2.0.

| Fold | IS-Fenster | IS-PF | OOS-Fenster | OOS-PF |
|---|---|---|---|---|
| 0 | 2019-01–2021-01 | 0.92 | 2021-01–2021-07 | 1.03 |
| 1 | 2019-07–2021-07 | 0.93 | 2021-07–2022-01 | 0.81 |
| 2 | 2020-01–2022-01 | 0.94 | 2022-01–2022-07 | 1.17 |
| 3 | 2020-07–2022-07 | 0.94 | 2022-07–2023-01 | 0.91 |
| 4 | 2021-01–2023-01 | 0.97 | 2023-01–2023-07 | 0.82 |
| 5 | 2021-07–2023-07 | 0.93 | 2023-07–2024-01 | 0.78 |
| 6 | 2022-01–2024-01 | 0.93 | 2024-01–2024-07 | 1.00 |
| 7 | 2022-07–2024-07 | 0.89 | 2024-07–2025-01 | 1.14 |
| 8 | 2023-01–2025-01 | 0.93 | 2025-01–2025-07 | 0.95 |
| 9 | 2023-07–2025-07 | 0.98 | 2025-07–2026-01 | 0.74 |
| 10 | 2024-01–2026-01 | 0.96 | 2026-01–2026-07 | 1.31 |
| 11 | 2024-07–2026-07 | 1.01 | 2026-07–2026-08 | 1.05 |

| Gate | Wert | Status |
|---|---|---|
| n(OOS) ≥ 300 | 1309 | PASS |
| WFE-Median ≥ 0.5 | 1.029 | PASS |
| WFE ≤ 1.0 (Lookahead-Verdacht) | 1.029 | **FAIL** (hauchdünn, kein Alarmsignal mehr) |
| ≥60% Folds WFE≥0.5 | 100% | PASS |
| PF(1x) ≥ 1.5 | 0.942 | **FAIL** — unter 1.0 |
| PF(2x) ≥ 1.2 | 0.877 | **FAIL** |
| PF(3x) ≥ 1.0 | 0.816 | **FAIL** |
| DSR ≥ 0.95 | 0.000 | **FAIL** — kein signifikanter Edge |
| PBO < 0.1 | 0.0 | PASS |
| Params ≤ Limit | 7/43 | PASS |
| MC p95-MaxDD ≤ 8% | 33.13% | **FAIL** — Tail-Risiko |

**5 von 10 Gates verfehlt.** `ERGEBNIS: GATES NICHT BESTANDEN`.

---

## 7. Verdikt

PF pendelt in praktisch jedem einzelnen Fold — IS wie OOS — um 0.9–1.0: im
Mittel ein Nullsummenspiel, unter realistischem Kostenstress (2x/3x)
leicht verlustträchtig. DSR=0 bedeutet: kein von Zufall unterscheidbarer
Edge. Die Monte-Carlo-Drawdown-Simulation zeigt ein Tail-Risiko von 33 %
Kontoverlust (Grenze: 8 %).

Dass 11 von 12 Folds auf praktisch denselben Parametersatz konvergieren
(`entry_mode=close`, beide Filter aus), spricht gegen ein Parametrisierungs-
problem — eher gegen eine strukturelle Grenze: die London-Range-Breakout-
Logik von S4 überträgt sich nicht auf Golds Volatilitätsregime.

**Empfehlung:**
- S4/XAUUSD nicht live schalten — gleiche Kategorie wie S6 (nicht tragfähig).
- Der laufende S4/USDJPY-Live-Bot (Magic 20260904) ist **nicht** betroffen —
  er nutzt `entry_mode=close`, keine Retest-Limits, daher außerhalb des
  Bug-Wirkungsbereichs.
- Backtester-Fix bleibt im Code — unabhängig vom S4/XAUUSD-Ausgang korrekt
  und relevant für jede künftige Retest-/Limit-Strategie auf einem Symbol
  mit engem SL relativ zur Bar-Volatilität.

## Anhang: Geänderte/neue Dateien

- `core/backtester.py` — Fix (Fine-Intrabar-Auflösung für Pending-Limits)
- `tests/test_backtester.py` — 4 neue Tests (`TestLimitOrdersFineIntrabar`)
- `configs/s4_london_breakout_xau.yaml` — neu
- `reports/wfa_s4_xau_full.log`, `reports/wfa_s4_xau_full/` — finaler WFA-Lauf
- `reports/s4_xauusd_validation.md` — dieser Bericht
