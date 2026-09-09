"""tests/test_journal.py — Trade-Journal (CSV, Traderbook-Stil)."""
from __future__ import annotations

from datetime import datetime, timezone

from core.journal import TradeJournal, read_journal

UTC = timezone.utc


def test_open_and_close_roundtrip(tmp_path):
    path = tmp_path / "trades_s4.csv"
    j = TradeJournal(path)
    j.open(symbol="USDJPY", direction=1, ticket=4711, lots=0.5, entry=150.65,
          sl=150.00, tp=151.95, risk_pct=0.005,
          reason="London-Breakout LONG (ueber Range 150-150.5, 50.0 Pips), TP 2.0R",
          equity=100_000.0, ts=datetime(2024, 3, 13, 7, 0, tzinfo=UTC))
    j.close(symbol="USDJPY", ticket=4711, exit_price=151.95, profit=650.0,
           fees=-7.0, reason="Take-Profit getroffen", equity=100_643.0,
           ts=datetime(2024, 3, 13, 10, 0, tzinfo=UTC))

    rows = read_journal(path)
    assert len(rows) == 2
    assert rows[0]["ereignis"] == "OPEN"
    assert rows[0]["symbol"] == "USDJPY"
    assert rows[0]["richtung"] == "LONG"
    assert rows[0]["ticket"] == "4711"
    assert "London-Breakout" in rows[0]["grund"]
    assert rows[1]["ereignis"] == "CLOSE"
    assert rows[1]["gewinn"] == "650.00"
    assert rows[1]["grund"] == "Take-Profit getroffen"


def test_short_direction_label(tmp_path):
    j = TradeJournal(tmp_path / "trades.csv")
    j.open(symbol="USDJPY", direction=-1, ticket=1, lots=0.1, entry=150.0,
          sl=150.5, tp=149.0, risk_pct=0.005, reason="x", equity=100_000.0)
    rows = read_journal(tmp_path / "trades.csv")
    assert rows[0]["richtung"] == "SHORT"


def test_read_journal_missing_file_returns_empty(tmp_path):
    assert read_journal(tmp_path / "nope.csv") == []


def test_write_creates_header_once(tmp_path):
    path = tmp_path / "trades.csv"
    j = TradeJournal(path)
    for i in range(3):
        j.open(symbol="EURUSD", direction=1, ticket=i, lots=0.1, entry=1.1,
              sl=1.09, tp=1.12, risk_pct=0.005, reason="r", equity=100_000.0)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0].startswith("zeit;ereignis;symbol")
    assert len(lines) == 4  # 1 Header + 3 Zeilen
    assert len(read_journal(path)) == 3


def test_write_does_not_raise_on_unwritable_dir(tmp_path, monkeypatch):
    """Journal-Schreibfehler duerfen den Bot nicht crashen (Handeln > Loggen)."""
    j = TradeJournal(tmp_path / "sub" / "trades.csv")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", boom)
    j.open(symbol="EURUSD", direction=1, ticket=1, lots=0.1, entry=1.1,
          sl=1.09, tp=1.12, risk_pct=0.005, reason="r", equity=100_000.0)
