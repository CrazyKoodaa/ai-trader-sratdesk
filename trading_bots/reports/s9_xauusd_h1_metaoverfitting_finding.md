# S9 DonchianTrend XAUUSD H1 — Meta-Overfitting durch iterative Grid-Suche, 2026-09-09

**Zusammenfassung:** Ueber acht aufeinanderfolgende WFA-Laeufe (S9h bis
S9p) wurde das WFO-Grid jeweils auf Basis des VORHERIGEN Laufs
Fold-Logs (das die GESAMTE Historie abdeckt, nicht nur "In-Sample") von
Hand nachjustiert — Werte, die wiederholt gewannen, wurden im Grid
behalten/verfeinert, selten gewinnende Werte entfernt. PF(1x) stieg dabei
nahezu monoton von 1.105 auf 1.582. **PBO stieg im selben Zeitraum fast
im Gleichschritt von 0.0 auf 0.829** (mit einer Ausnahme, S9j/S9k):

| Lauf | PF(1x) | PBO |
|---|---:|---:|
| S9h  | 1.105 | 0.000 |
| S9i  | 1.197 | 0.186 |
| S9j  | 1.324 | 0.029 |
| S9k  | 1.386 | 0.029 |
| S9l  | 1.419 | 0.386 |
| S9n  | 1.579 | 0.529 |
| S9o  | 1.540 | 0.629 |
| S9p  | 1.582 | 0.829 |

## Warum das kein Zufall ist

`pbo_cscv()` wird je Lauf korrekt NUR auf die IS-Performance-Matrix
DIESES EINEN Laufs angewendet (Folds x Kombos) — jeder einzelne WFA-Lauf
fuer sich ist methodisch sauber (echtes Rolling-WFO, keine
In-Run-Bugs, s. `reports/s21_xauusd_pbo_investigation.md` fuer die
Verifikation der PBO-Mechanik selbst). Das Problem sitzt eine Ebene
hoeher: die ENTSCHEIDUNG, welches Grid der NAECHSTE Lauf bekommt, wurde
jedes Mal auf Basis des Fold-Logs des vorherigen Laufs getroffen — und
dieses Fold-Log zeigt explizit, welche Parameter in WELCHEN historischen
Perioden (inkl. der dort jeweiligen "OOS"-Fenster) gut abschnitten. Wer
das Grid daraufhin manuell in Richtung der Gewinner verengt, betreibt
De-facto-Kurvenanpassung an das GESAMTE Sample — ein klassisches
Multiple-Comparisons-Problem ueber die Lauf-Sequenz, das in KEINER der
einzelnen `n_trials`/DSR/PBO-Zahlen auftaucht (DSR zaehlt nur die
Kombinationen INNERHALB des jeweils finalen Grids, hier z. B. 12 bei
S9p — nicht die kumulierten Kombinationen aller acht Explorations-
Laeufe, die in Wirklichkeit "ausprobiert" wurden, bevor S9p entstand).

PBO ist dabei zufaellig genau die Metrik, die dieses Muster am
empfindlichsten aufdeckt: sie misst IS/OOS-Rang-Instabilitaet innerhalb
eines Laufs, und ein Grid, das ueber mehrere Runden hinweg gezielt auf
das gesamte Sample hin optimiert wurde, tendiert dazu, genau dort
schlechter zu werden, selbst wenn seine OOS-PF-Zahl (innerhalb des
jeweils letzten, sauberen Rolling-WFO) gut aussieht.

## Konsequenz

**S9p (reports/wfa_s9p_donchian_xauusd_h1_trimmed, "9/10 Gates" auf dem
Papier) ist trotz technisch bestandener Einzelwerte KEIN vertrauenswuerdiger
Fund.** Die drei zusaetzlich durchgefuehrten Robustheits-Checks (Determinismus-
Re-Run bit-identisch, Unit-Level-Anti-Lookahead-Tests gruen,
Shift-Test PF 1.55->1.26 bei +1 Bar Delay, moderater, nicht
kollabierender Rueckgang) zeigen, dass der MECHANISMUS selbst kausal
korrekt implementiert ist — das WFE>1.0-Sanity-Flag ist wahrscheinlich
benigne (verteilte, nicht einseitig geclusterte Fold-Ratios, gleiches
Muster wie beim dokumentierten S4-Praezedenzfall). Das eigentliche
Problem ist NICHT ein Code-Bug, sondern der SUCH-PROZESS: acht Runden
Hindsight-informierter manueller Grid-Verengung ueber das volle Sample
hinweg, und PBOs Verschlechterung im Gleichschritt mit PF(1x)s
Verbesserung ist genau das Warnsignal, das dieser Prozess erzeugen
WUERDE, wenn er tatsaechlich vor allem Kurvenanpassung statt echten
Edge-Fund waere.

## Empfehlung fuer das weitere Vorgehen

1. **Keine weitere manuelle Grid-Verengung basierend auf vollen
   Fold-Logs.** Jede weitere Iteration in diese Richtung wuerde PBO
   voraussichtlich weiter verschlechtern, unabhaengig vom Signal.
2. Ein sauberer naechster Schritt waere ein ECHTER Hold-out: Grid-Design
   nur mit Daten bis zu einem festen Cutoff (z. B. 2023), EIN
   einzelner, danach eingefrorener WFA-Lauf auf den vollen Datensatz
   (inkl. 2024-2026) als ehrlicher Test. Diese Session hat den vollen
   Datensatz (inkl. 2024-2026) bereits mehrfach fuer Grid-Entscheidungen
   gesehen (z. B. `adx_min=15` wurde explizit wegen starker Folds 17-19
   im Grid behalten) -- ein Hold-out ist fuer S9 daher in DIESER Session
   nicht mehr moeglich, sondern muesste in einer neuen Session mit
   diszipliniert VORAB festgelegtem Cutoff wiederholt werden.
3. Alternative: EIN priori (nicht aus den Fold-Logs dieser Session
   abgeleitetes) Grid fest waehlen -- z. B. grosszuegig breite, runde
   Werte (don_len=250/500, sl_atr_mult=2.0/3.0, adx_min=0/25 -- bewusst
   NICHT die aus der Sequenz "gelernten" Werte 300/500/3.0/4.0/15/20/25)
   -- EIN Lauf, EIN Ergebnis, keine Nachjustierung danach, unabhaengig
   vom Ausgang.
4. Der urspruengliche S21-GoldReaper-Befund
   (`reports/s21_xauusd_pbo_investigation.md`) bleibt unberuehrt von
   diesem Fund -- dort wurde EIN Grid pro Struktur-Hypothese getestet
   (ATR-Filter, Plateau-Selektion, Grid-Groesse), nicht iterativ auf
   Basis wiederholter Fold-Log-Beobachtung verengt.
