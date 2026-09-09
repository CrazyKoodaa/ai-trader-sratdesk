"""Tests für core/reporting.py — Fokus: 0-Trades-Robustheit (SPEC §4.11)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from core.reporting import TRADE_COLUMNS, compute_metrics, render_report


@dataclass
class _DummyResult:
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict


def _empty_result() -> _DummyResult:
    trades = pd.DataFrame(columns=TRADE_COLUMNS)
    idx = pd.DatetimeIndex([], tz="UTC")
    equity = pd.DataFrame({"balance": [], "equity": []}, index=idx)
    metrics = compute_metrics(trades, equity_curve=equity["equity"])
    return _DummyResult(trades=trades, equity_curve=equity, metrics=metrics)


def test_compute_metrics_zero_trades_hat_alle_schluessel():
    """Früh-Return bei 0 Trades muss dieselben Keys liefern wie der
    Normalpfad (sonst KeyError in render_report — Bug: n_long/n_short fehlten)."""
    m = compute_metrics(pd.DataFrame(columns=TRADE_COLUMNS))
    for key in ("n", "pf", "winrate", "avg_r", "max_dd_balance", "max_dd_equity",
                "sharpe", "sortino", "longest_losing_streak",
                "pf_long", "pf_short", "n_long", "n_short",
                "pf_by_year", "total_pnl", "avg_pnl"):
        assert key in m, f"Key fehlt im 0-Trades-Metrics-Dict: {key}"
    assert m["n"] == 0
    assert m["n_long"] == 0
    assert m["n_short"] == 0


def test_render_report_zero_trades(tmp_path):
    """0-Trades-Report rendert ohne Fehler (Markdown + Equity-PNG)."""
    res = _empty_result()
    md_path = render_report(res, tmp_path / "report")
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "Trades (n): **0**" in text
    assert (tmp_path / "report" / "equity.png").exists()


def test_render_report_mit_trades(tmp_path):
    """Regression: normaler Report-Pfad bleibt unveraendert funktionsfaehig."""
    exits = pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True)
    trades = pd.DataFrame({
        "entry_time": exits, "exit_time": exits,
        "direction": [1, -1], "entry": 100.0, "exit": 101.0,
        "sl": 99.0, "tp": 102.0, "lots": 1.0,
        "pnl": [100.0, -50.0], "r_multiple": [1.0, -0.5], "meta": [{}] * 2,
    })
    equity = pd.DataFrame(
        {"balance": [100100.0, 100050.0], "equity": [100100.0, 100050.0]},
        index=exits,
    )
    res = _DummyResult(trades=trades, equity_curve=equity,
                       metrics=compute_metrics(trades, equity_curve=equity["equity"]))
    md_path = render_report(res, tmp_path / "report2")
    text = md_path.read_text(encoding="utf-8")
    assert "Trades (n): **2**" in text
    assert "| Long | 1 |" in text
    assert "| Short | 1 |" in text
