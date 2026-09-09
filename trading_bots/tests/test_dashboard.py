"""tests/test_dashboard.py — reine Aggregations-/Parsing-Funktionen aus
dashboard.py. KEIN echtes MT5/RPyC noetig (dashboard.py importiert
core.connector nur fuer den Typ/lazy connect(), ruft ihn hier nicht auf)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dashboard as dash  # noqa: E402
from core.journal import TradeJournal  # noqa: E402

UTC = timezone.utc


def _deal(**kw):
    base = dict(magic=20260904, profit=0.0, commission=0.0, swap=0.0, entry=0,
               position_id=1)
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# bot_stats
# ---------------------------------------------------------------------------
def test_bot_stats_empty_snapshot():
    stats = dash.bot_stats(20260904, None)
    assert stats == {
        "open_count": 0, "floating_pl": 0.0, "closed_trades": 0,
        "wins": 0, "losses": 0, "winrate": None, "netto": 0.0, "profit_factor": None,
    }


def test_bot_stats_filters_by_magic_and_groups_by_position():
    live = {
        "positions": [
            {"magic": 20260904, "profit": 12.5},
            {"magic": 100042, "profit": -99.0},  # anderer Bot -> ignoriert
        ],
        "deals": [
            _deal(position_id=1, entry=0, profit=0.0, commission=-1.0),   # OPEN (S4)
            _deal(position_id=1, entry=1, profit=650.0, swap=-2.0),       # CLOSE win (S4)
            _deal(position_id=2, entry=0, profit=0.0, commission=-1.0),   # OPEN (S4)
            _deal(position_id=2, entry=1, profit=-300.0),                 # CLOSE loss (S4)
            _deal(position_id=3, magic=100042, entry=1, profit=999.0),    # anderer Bot -> ignoriert
            _deal(position_id=4, entry=0, profit=0.0),                    # noch offen (kein Exit) -> nicht gezaehlt
        ],
    }
    stats = dash.bot_stats(20260904, live)
    assert stats["open_count"] == 1
    assert stats["floating_pl"] == 12.5
    assert stats["closed_trades"] == 2
    assert stats["wins"] == 1 and stats["losses"] == 1
    assert stats["winrate"] == 50.0
    assert stats["netto"] == round((0.0 - 1.0 + 650.0 - 2.0) + (0.0 - 1.0 - 300.0), 2)
    assert stats["profit_factor"] == round(647.0 / 301.0, 2)


# ---------------------------------------------------------------------------
# bot_freshness
# ---------------------------------------------------------------------------
def test_bot_freshness_missing_file(tmp_path):
    info = dash.bot_freshness(tmp_path / "nope.log")
    assert info == {"alive": False, "last_line": None, "age_seconds": None}


def test_bot_freshness_recent_file(tmp_path):
    p = tmp_path / "bot.log"
    p.write_text("2026-09-05 10:00:00,000 [INFO] letzte Zeile\n", encoding="utf-8")
    info = dash.bot_freshness(p)
    assert info["alive"] is True
    assert info["last_line"].endswith("letzte Zeile")
    assert info["age_seconds"] < 5


def test_bot_freshness_stale_file(tmp_path):
    import os
    p = tmp_path / "bot.log"
    p.write_text("x\n", encoding="utf-8")
    old = 1_600_000_000  # weit in der Vergangenheit
    os.utime(p, (old, old))
    info = dash.bot_freshness(p)
    assert info["alive"] is False


# ---------------------------------------------------------------------------
# read_equity_series
# ---------------------------------------------------------------------------
def test_read_equity_series_parses_heartbeat(tmp_path):
    p = tmp_path / "s4.log"
    p.write_text(
        "2026-09-05 10:00:00,123 [INFO] ♥ Bot laeuft — Equity 100000.00 USD, 0 Position(en) offen.\n"
        "2026-09-05 10:30:00,456 [INFO] ♥ Bot laeuft — Equity 100643.00 USD, 1 Position(en) offen.\n"
        "2026-09-05 10:31:00,000 [INFO] SIGNAL LONG: USDJPY -- irrelevant\n",
        encoding="utf-8",
    )
    pts = dash.read_equity_series(p)
    assert len(pts) == 2
    assert pts[0]["v"] == 100000.0
    assert pts[1]["v"] == 100643.0
    assert pts[0]["t"].startswith("2026-09-05T10:00:00")


def test_read_equity_series_missing_file(tmp_path):
    assert dash.read_equity_series(tmp_path / "nope.log") == []


# ---------------------------------------------------------------------------
# autopsy_for_trade
# ---------------------------------------------------------------------------
def test_autopsy_filters_by_symbol_and_time_window():
    lines = [
        "2026-09-05 06:50:00,000 [INFO] KEIN EINSTIEG: USDJPY | Range 150-150.5",
        "2026-09-05 07:00:00,000 [INFO] SIGNAL LONG: USDJPY -- Breakout",
        "2026-09-05 07:00:01,000 [INFO] ORDER AUSGEFUEHRT: LONG USDJPY 0.10 Lots",
        "2026-09-05 07:00:02,000 [INFO] EURUSD unrelated line",
        "2026-09-05 09:00:00,000 [INFO] TRADE GESCHLOSSEN: USDJPY #4711",
        "2026-09-05 12:00:00,000 [INFO] KEIN EINSTIEG: USDJPY | outside window",
    ]
    out = dash.autopsy_for_trade(lines, "USDJPY", "2026-09-05T07:00:00", "2026-09-05T09:00:00")
    msgs = [o["msg"] for o in out]
    assert any("SIGNAL LONG" in m for m in msgs)
    assert any("TRADE GESCHLOSSEN" in m for m in msgs)
    assert any("Range 150" in m for m in msgs)  # 15-min Vorlauf faengt das
    assert not any("EURUSD" in m for m in msgs)
    assert not any("outside window" in m for m in msgs)


def test_autopsy_empty_without_open_time():
    assert dash.autopsy_for_trade(["x"], "USDJPY", None, None) == []


# ---------------------------------------------------------------------------
# build_trades (Journal-Reader)
# ---------------------------------------------------------------------------
def test_build_trades_pairs_open_close(tmp_path):
    j = TradeJournal(tmp_path / "trades.csv")
    j.open(symbol="USDJPY", direction=1, ticket=1, lots=0.1, entry=150.65,
          sl=150.0, tp=151.95, risk_pct=0.005, reason="r1", equity=100_000.0)
    j.close(symbol="USDJPY", ticket=1, exit_price=151.95, profit=650.0,
           fees=-7.0, reason="Take-Profit getroffen", equity=100_643.0)
    from core.journal import read_journal
    trades = dash.build_trades(read_journal(tmp_path / "trades.csv"))
    assert len(trades) == 1
    assert trades[0]["ticket"] == "1"
    assert trades[0]["offen"] is False
    assert trades[0]["gewinn"] == "650.00"


def test_build_trades_open_without_close_stays_open(tmp_path):
    j = TradeJournal(tmp_path / "trades.csv")
    j.open(symbol="USDJPY", direction=-1, ticket=2, lots=0.1, entry=150.0,
          sl=150.5, tp=149.0, risk_pct=0.005, reason="r", equity=100_000.0)
    from core.journal import read_journal
    trades = dash.build_trades(read_journal(tmp_path / "trades.csv"))
    assert trades[0]["offen"] is True
    assert trades[0]["close_zeit"] is None


# ---------------------------------------------------------------------------
# s4_gates_summary
# ---------------------------------------------------------------------------
def test_s4_gates_summary_parses_report_row(tmp_path, monkeypatch):
    report = tmp_path / "gates_matrix_s1_s5.md"
    report.write_text(
        "| Bot | Symbol | OOS-Trades | PF(1x) | PF(2x) | PF(3x) | WFE-Median | DSR | PBO | MC p95-DD | Gates |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---|\n"
        "| **S4 LondonBreakout** | **USDJPY** | **621** | **2.25 ✅** | **1.51 ✅** | "
        "**1.00 ✅** | 1.021 | **1.00 ✅** | **0.00 ✅** | **0.03% ✅** | **10/11** (1 Sanity-Flag) |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dash, "GATES_REPORT", report)
    summary = dash.s4_gates_summary()
    assert summary["oos_trades"] == "621"
    assert "2.25" in summary["pf_1x"]
    assert summary["gates"].startswith("10/11")


def test_s4_gates_summary_missing_report(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "GATES_REPORT", tmp_path / "nope.md")
    assert dash.s4_gates_summary() == {}
