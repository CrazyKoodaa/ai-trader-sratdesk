"""strategies/s22_session_close_drift.py — S22 Session-Close-Drift (XAUUSD, H1).

Voellig andere Signal-Familie als S1-S21: KEIN Indikator, KEIN Preis-Trigger,
KEINE Struktur — eine reine Kalender-/Uhrzeit-Wette (Tageszeit-Saisonalitaet,
verwandt zum dokumentierten "Overnight-Drift"-Effekt in Aktienindizes).

**Herkunft (Transparenz-Pflicht, damit das Ergebnis richtig eingeordnet
wird):** Ein deskriptiver Scan von mittleren H1-Log-Returns je UTC-Stunde
ueber `data_mt5/XAUUSD_H1.parquet` (2015-2026, echtes Broker-Volumen) UND
unabhaengig ueber `data/XAUUSD_H1.parquet` (andere Fetch-Pipeline,
2019-2026) zeigte in BEIDEN Datensaetzen einen auffaelligen, statistisch
sehr signifikanten Ausschlag bei Stunde 22 UTC (t=6.05 bzw. t=4.89 ueber
n=1978-3002 Tage, konsistent in 9 von 11 Einzeljahren 2015-2026, nicht nur
an einem einzelnen Wochentag/Sonntag-Wiedereroeffnungs-Gap-Artefakt
haengend). Das ist eine ECHTE Hindsight-Entdeckung (volle Historie
gescannt, nicht aus Theorie hergeleitet) -- **exakt der Fall, fuer den
PBO/DSR/WFA-Gates existieren**. Deshalb hier bewusst NICHT der exakte
Gewinner-Wert (Stunde 22, Hold 1-2h) hart eingefroren, sondern als WFO-
Parameter ueber einen BREITEN, a priori plausiblen Kandidatensatz gewaehlt
(SPEC-analog zu S1-S21: der WFO waehlt je Fold, das Ergebnis steht und
faellt mit WFE/PBO, nicht mit der Deskriptiv-Statistik selbst).

**Idee:** taeglich (jeden Handelstag) zur Stunde ``entry_hour_utc`` Long-
Entry (Signal auf der Bar VOR Entry-Stunde, Fill = Open der Entry-Stunde,
SPEC-Konvention "naechste Bar"), Exit nach ``hold_hours`` (Time-Exit) ODER
ATR-Stop als Sicherheitsnetz (unconditionale Richtungswette -- kein
Preis-Signal filtert sie, daher braucht sie einen harten Stop gegen
Tail-Risiko). Kein TP (das Signal ist "Drift ueber eine feste Haltedauer",
kein Ziel-Preis-Konzept).

Long-only (der entdeckte Effekt war positiv/asymmetrisch; ein
symmetrisches Short-Pendant bei einer anderen Stunde waere eine
GESONDERTE, eigene Hypothese und wird hier nicht mit hineingemischt).

**Trigger-Design (Datenqualitaets-Stolperstein):** ein naiver Trigger auf
der Bar "entry_hour-1" (Signal -> Fill am Open der naechsten Bar =
entry_hour) scheitert an einer echten Luecke im Broker-Feed:
`data_mt5/XAUUSD_H1.parquet` hat fuer die meisten Stunden ~3000 Bars ueber
die Historie, aber Stunde 21 UTC nur 101 (fast immer fehlend — verifiziert
als DST-Umstellungswochen-Artefakt: die ~101 Treffer liegen fast alle in
US-DST-Wechselwochen; ausserhalb davon "springt" der Feed von Stunde 20
direkt auf Stunde 22, kein Bar dazwischen). Ein Trigger auf Stunde 21 wuerde
daher fast nie feuern. Stattdessen: Trigger direkt auf ``entry_hour_utc``
selbst (die zuverlaessig existiert, s. o.), zustandsbehaftet auf 1x/Tag
begrenzt -- Fill ist dann am Open der NAECHSTEN tatsaechlich vorhandenen
Bar (typischerweise, aber nicht garantiert, die Folgestunde). Das
verschiebt den Entry effektiv um ~1 Bar spaeter als "ideal" (verpasst die
Eigenbewegung der ``entry_hour_utc``-Bar selbst, faengt aber die
fortlaufende Drift der Folgestunden ein, die der Hold-Perioden-Scan im
Docstring oben ueber viele Stunden hinweg anhaltend zeigte) -- robuster
gegen die Feed-Luecke als der exaktere, aber fragile "-1"-Trigger.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr


class S22SessionCloseDrift(Strategy):
    name = "s22_session_close_drift"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "H1")
        self.required_timeframes = [self.primary_tf]

        self.entry_hour_utc = int(p.get("entry_hour_utc", 22))
        self.hold_hours = int(p.get("hold_hours", 2))
        self.atr_len = int(p.get("atr_len", 14))
        self.sl_atr_mult = float(p.get("sl_atr_mult", 2.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        self._window = self.atr_len + 5
        self._last_fired_date: date | None = None

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        if i < self.atr_len:
            return None
        ts = df.index[i]
        if ts.hour != self.entry_hour_utc:
            return None
        d = ts.date()
        if d == self._last_fired_date:
            return None  # bereits heute gefeuert (Sicherheitsnetz, sollte
                          # bei stuendlichen Bars ohnehin nicht doppelt vorkommen)
        self._last_fired_date = d

        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]
        atr_val = float(_atr(win, self.atr_len).iloc[-1])
        if not (atr_val > 0):
            return None

        c = float(win["close"].iloc[-1])
        direction = 1  # long-only, s. Docstring
        sl = c - direction * self.sl_atr_mult * atr_val

        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=None, risk_pct=self.risk_pct,
            meta={"time_exit_bars": self.hold_hours, "atr": atr_val,
                  "entry_hour_utc": self.entry_hour_utc},
            expires_bars=0,
        )
