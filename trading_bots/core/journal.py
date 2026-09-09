"""core/journal.py — Menschenlesbares Trade-Journal (CSV) fuer Live-Bots.

Ergaenzt das strukturierte JSONL-Logging aus ``core.live`` (Maschinen-Format,
ein Event pro Zeile) um ein CSV-Journal im Stil der Desktop-Bots
(``trades.csv`` bei David V2): eine Zeile pro OPEN/CLOSE-Ereignis mit
Klartext-Begruendung ("grund"), damit sich im Nachhinein nachvollziehen
laesst, WARUM ein Trade eroeffnet bzw. geschlossen wurde ("Traderbook"-
Backlog, User-Anforderung).

Schreibfehler duerfen den Bot nicht stoppen — Handeln hat Vorrang vor
Protokollieren (siehe ``_write``).
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
UTC = timezone.utc

JOURNAL_COLUMNS = [
    "zeit", "ereignis", "symbol", "richtung", "ticket",
    "lots", "entry", "sl", "tp", "exit",
    "risiko_pct", "grund", "equity", "gewinn", "gebuehren",
]


class TradeJournal:
    """Haengt Zeilen an eine CSV-Datei an (Excel-kompatibel, Semikolon-getrennt,
    UTF-8-BOM). Dieselbe Datei kann parallel vom Dashboard gelesen werden
    (nur Anhaengen, kein Ueberschreiben)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, row: dict) -> None:
        try:
            new_file = not self.path.exists()
            with open(self.path, "a", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(
                    fh, fieldnames=JOURNAL_COLUMNS, delimiter=";",
                    extrasaction="ignore", restval="",
                )
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as exc:
            log.error("Journal konnte nicht geschrieben werden: %s", exc)

    def open(self, *, symbol: str, direction: int, ticket: int, lots: float,
             entry: float, sl: float, tp: float | None, risk_pct: float,
             reason: str, equity: float, ts: datetime | None = None) -> None:
        self._write({
            "zeit": (ts or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M:%S"),
            "ereignis": "OPEN",
            "symbol": symbol,
            "richtung": "LONG" if direction > 0 else "SHORT",
            "ticket": ticket,
            "lots": lots,
            "entry": entry,
            "sl": sl,
            "tp": tp if tp is not None else "",
            "risiko_pct": risk_pct,
            "grund": reason,
            "equity": f"{equity:.2f}",
        })

    def close(self, *, symbol: str, ticket: int, exit_price: float,
              profit: float, fees: float, reason: str, equity: float,
              ts: datetime | None = None) -> None:
        self._write({
            "zeit": (ts or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M:%S"),
            "ereignis": "CLOSE",
            "symbol": symbol,
            "ticket": ticket,
            "exit": exit_price,
            "gewinn": f"{profit:.2f}",
            "gebuehren": f"{fees:.2f}",
            "grund": reason,
            "equity": f"{equity:.2f}",
        })


def read_journal(path: str | Path) -> list[dict]:
    """Liest das Journal zurueck (fuers Dashboard) — leere Liste, wenn die
    Datei (noch) nicht existiert."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh, delimiter=";") if row.get("zeit")]
