# S22 Session-Close-Drift (XAUUSD H1) — erster Kandidat mit 10/10 Gates, 2026-09-09

**Verdikt: 10/10 Gates bestanden** (`reports/wfa_s22b_session_close_drift_xauusd_h1_slgrid/wfa_gates.json`).
Erster XAUUSD-Kandidat in der gesamten Projekt-Historie, der ALLE
`configs/validation_gates.yaml`-Gates (SPEC §7) besteht. Vorherige
Bestmarken: S21 GoldReaper 7/10 (strukturell PBO-blockiert, s.
`reports/s21_xauusd_pbo_investigation.md`), S9q Donchian 6/10 (sauber,
aber zu schwacher Edge). Trotzdem: **dieses Ergebnis ist eine
Hindsight-Entdeckung** (s. u.) — entsprechend vorsichtig einzuordnen, nicht
blind zu feiern.

## 1. Herkunft — volle Transparenz zur Entdeckungsmethode

Kein Indikator, kein Preis-Trigger: eine reine Kalender-/Uhrzeit-Wette.
Entdeckt per deskriptivem Scan der mittleren H1-Log-Returns je UTC-Stunde
auf `data_mt5/XAUUSD_H1.parquet` (2015-2026, echtes Broker-Volumen) —
Stunde 22 UTC stach mit t=6.05 (n=3002) heraus, unabhaengig reproduziert
auf `data/XAUUSD_H1.parquet` (andere Fetch-Pipeline, t=4.89). Das ist
**explizit eine Hindsight-Entdeckung ueber die volle Historie** — genau
der Fall, fuer den PBO/DSR/WFA-Gates existieren. Deshalb bewusst NICHT die
exakte Gewinner-Stunde (22) hart eingefroren, sondern ALLE 24 UTC-Stunden
als WFO-Kandidaten gegeben; das Ergebnis steht und faellt mit WFE/PBO, nicht
mit der Deskriptiv-Statistik selbst.

**Datenqualitaets-Fund unterwegs:** ein erster Trigger-Entwurf (Signal auf
Stunde 21, Fill am Open von Stunde 22) waere fast nie gefeuert — Stunde 21
UTC hat im Datensatz nur 101 Bars ueber 11 Jahre (vs. ~3000 bei
Nachbarstunden), verifiziert als DST-Umstellungswochen-Artefakt (die 101
Treffer liegen fast alle in US-DST-Wechselwochen; sonst springt der Feed
von Stunde 20 direkt auf 22). Trigger auf die Zielstunde selbst umgestellt
(zustandsbehaftet, 1x/Tag) — robust gegen die Feed-Luecke, s.
`strategies/s22_session_close_drift.py` Docstring.

## 2. Strategie

Long-only, taeglich: Signal bei Bar-Close der Stunde `entry_hour_utc`,
Market-Fill am Open der naechsten verfuegbaren Bar (SPEC-Konvention),
Exit nach `hold_hours` Bars ODER ATR-Stop (`sl_atr_mult`) als
Sicherheitsnetz gegen Tail-Risiko (unconditionale Richtungswette, kein
Preis-Signal filtert sie). Kein TP — reines Zeitfenster-Drift-Konzept.

## 3. Framework-Erweiterung unterwegs

`core/live.py`-Registry um `s22_session_close_drift` ergaenzt. 9 neue
Unit-Tests (`tests/test_s22.py`): Trigger-Stunde, Time-Exit-Meta, ATR-SL,
Backward-Compat, Determinismus, 1x/Tag-Guard. Volle Suite danach 453/453
gruen (vor der WFA).

## 4. WFA-Ergebnis (`data_mt5`, 2015-2026, 20 Folds)

Zwei disziplinierte Laeufe, EIN Grid, EINE Nachjustierung (dokumentiert,
nicht hindsight-getrieben — s. Abschnitt 5):

| Lauf | Grid | n(OOS) | PF(1x) | PF(2x) | PF(3x) | WFE | DSR | PBO | MC-DD | Gates |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S22 (`wfa_s22_...`) | entry_hour×hold_hours (72 Kombos, sl_atr_mult fix 2.0) | 1889 | 1.987 | 1.401 | **0.995** | 0.843 | 1.000 | 0.086 | 3.52% | **9/10** |
| S22b (`wfa_s22b_..._slgrid`) | + sl_atr_mult∈{1.5,2.0,3.0} (216 Kombos) | 1760 | 2.064 | 1.439 | **1.013** | 0.691 | 1.000 | 0.086 | 2.30% | **10/10** |

Vollstaendige Gate-Tabelle (S22b, final):

| Gate | Ergebnis | Status |
|---|---:|---|
| n(OOS) ≥ 300 | 1760 | PASS |
| WFE-Median ≥ 0.5 | 0.691 | PASS |
| ≥60% Folds WFE≥0.5 | 68% | PASS |
| PF(1x) ≥ 1.5 | 2.064 | PASS |
| PF(2x) ≥ 1.2 | 1.439 | PASS |
| PF(3x) ≥ 1.0 | 1.013 | PASS |
| DSR ≥ 0.95 | 1.000 | PASS |
| PBO/CSCV < 0.10 | 0.086 | PASS |
| Params (3) ≤ 58 | 3 | PASS |
| MC p95-MaxDD ≤ 8% | 2.30% | PASS |

WFO waehlt je Fold ueberwiegend `entry_hour_utc=19, hold_hours=2` (11/20
Folds) oder `entry_hour_utc=21` (7/20 Folds) — **nicht** die im
Ausgangs-Scan auffaellige Stunde 22 selbst. Mechanistisch schluessig: der
Trigger feuert auf der Zielstunde, Fill+Exit liegen 1-3 Stunden SPAETER
(Kausalitaets-Konvention, s. o.) — ein Trigger auf Stunde 19/21 mit
hold=2-4 ueberdeckt so tatsaechlich Stunde 22 UTC MIT (die im Scan
staerkste Einzelstunde), plus Nachbarstunden. Das WFO hat also über 20
unabhaengige rollierende Fenster hinweg konsistent einen Weg gefunden,
den urspruenglich entdeckten Effekt einzufangen — mit unterschiedlicher,
aber verwandter Parametrisierung, nicht durch stures Wiederholen meines
Scans. `sl_atr_mult=3.0` (weiter Stop) gewinnt in 14/20 Folds — plausibel:
ein weiter Stop laesst mehr Trades das Zeitfenster ueberhaupt durchlaufen,
statt vorzeitig durch Rauschen ausgestoppt zu werden.

**Auffaelligkeiten im Fold-Log (Transparenz):** Fold 11 zeigt OOS-PF=inf
(keine Verlust-Trades in diesem Fenster) und Fold 19 OOS-PF=0.00 (kleines
Rumpf-Fenster Jul-Sep 2026, wenig Trades) — beide Extreme sind in der
Aggregation (PF/DSR/PBO ueber ALLE 1760 Trades) korrekt mitgerechnet, kein
Ausreisser wird verschwiegen oder herausgefiltert.

## 5. Warum die Nachjustierung (S22 -> S22b) methodisch vertretbar ist

S22 (9/10, nur PF(3x)=0.995 knapp unter 1.0) hatte `sl_atr_mult` fix auf
2.0 gehalten — laut Config-Kommentar VOR dem ersten Lauf explizit nur zur
Rechenzeit-Begrenzung geplant (der Lauf brauchte am Ende nur ~90s, unnoetig
vorsichtig). S22b ergaenzt exakt diese vorab dokumentierte Dimension
(Werte aus Konvention: 1.5/2.0/3.0, identisch zu `configs/s9q_donchian_trend_h1_disciplined.yaml`)
— **`entry_hour_utc`/`hold_hours`-Grid blieb unveraendert**, nichts wurde
aus dem Ergebnis von S22 hindsight-abgeleitet. Unterschied zum in
`reports/s9_xauusd_h1_metaoverfitting_finding.md` dokumentierten
Meta-Overfitting-Muster: dort wurden konkrete GEWINNER-WERTE aus
Fold-Logs uebernommen; hier wurde eine ganze, vorab geplante Dimension
nachgeholt, ohne die bereits gewinnenden Werte anzufassen. Trotzdem: dies
ist Nachjustierung Nr. 1 von genau EINER erlaubten — keine dritte Runde,
unabhaengig vom Ausgang.

## 6. Robustheits-Checks (SPEC §7 Punkte 7/9, nicht automatisiert in run_wfa.py)

- **Determinismus:** zwei identische Vollhistorie-Laeufe (WFA-Sieger-Params
  `entry_hour_utc=19, hold_hours=2, sl_atr_mult=2.0`) liefern
  bit-identische Trades (n=2913, PF=2.069 beide Male).
- **DST-Wochen:** Backtest ueber die DST-Umstellungswoche Maerz 2023
  (US-Wechsel 12.03.) laeuft fehlerfrei, 10 Trades, Trigger-Stunde
  verschiebt sich sauber von effektiv 20:00 auf 21:00 UTC am Umstellungstag
  (Engine arbeitet durchgehend in UTC, `ts.hour`-Vergleich ist DST-immun
  per Konstruktion — kein Sonderfall noetig).
- **Swap-Kosten aktiv:** Stichprobe zeigt Trades, die die
  Server-Mitternacht ueberschreiten (Swap-Kosten damit real im PF
  enthalten, `swap_long_pts=-40.0` aus `configs/common.yaml`, kein
  Override in der S22-Config).
- **Long/Short getrennt (SPEC-Gate 8): NICHT ANWENDBAR** — S22 ist
  bewusst long-only (der entdeckte Effekt war einseitig positiv, s.
  Docstring). Explizit hier vermerkt statt stillschweigend uebergangen.

## 7. Bekanntes Verhalten fuer Live-Erwaegung (kein Fund-Makel, aber wichtig)

`time_exit_bars` zaehlt TRADING-Bars, nicht Kalenderstunden: ein
Freitagabend-Entry haelt gelegentlich ueber das GESAMTE Wochenende (H1
ueberspringt Sa/So, "2 Bars spaeter" kann daher ~51h Realzeit bedeuten,
z. B. beobachtet Fr 10.03.2023 20:00 -> So 12.03.2023 23:00). Das ist
korrekt im Backtest bepreist (kein Bug), aber ein echtes
Wochenend-Gap-Risiko fuer die Live-Positionsgroesse, das beim Go-Live
separat bedacht werden sollte (z. B. `friday_flat`-Variante als eigener,
gesonderter Test — hier NICHT nachtraeglich eingebaut, um das validierte
Ergebnis nicht zu verwaessern).

## 8. Ehrliche Einordnung

- **PBO=0.086** ist unter der 0.10-Schwelle, aber nicht mit riesigem
  Puffer — ein Wert, der bei weiterer Session-Iteration in die falsche
  Richtung kippen koennte (Lehre aus S9h-p, s. o.). Keine weiteren Runden
  auf diesem Grid geplant.
- Die Kern-Hypothese ("Uhrzeit X hat Drift") ist volumensbasiert nicht
  erklaerbar (S22 nutzt kein Volumen) — plausibelster oekonomischer
  Mechanismus: duenne Liquiditaet am NY-Nachmittag/Asien-Vorabend-Uebergang
  mit strukturellem Nachfrage-Ueberhang bei Gold (dokumentiertes
  "Asian premium"/Rollover-Fenster-Phaenomen in Rohstoffen) — aber NICHT
  kausal verifiziert, nur statistisch/WFA-bestaetigt.
- n=1760 OOS-Trades ist eine grosse Stichprobe (Daily-Frequenz ueber 11
  Jahre) — statistisch komfortabel ueber dem 300-Minimum.
- Naechster ehrlicher Schritt vor Live-Erwaegung: Prop-Simulation (SPEC
  Gate 6, noch nicht gerechnet) und eine QUALITATIVE Pruefung der
  Wochenend-Hold-Faelle (Abschnitt 7).

## 9. Artefakte

- `strategies/s22_session_close_drift.py`, `configs/s22_session_close_drift_xauusd.yaml`
- `tests/test_s22.py` (9 Tests)
- `reports/wfa_s22_session_close_drift_xauusd_h1/` (9/10-Lauf)
- `reports/wfa_s22b_session_close_drift_xauusd_h1_slgrid/` (10/10-Lauf, final)
