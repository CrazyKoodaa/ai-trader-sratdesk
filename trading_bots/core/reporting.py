"""core/reporting.py — Metriken, Trade-Stats, Reports (SPEC §4.11).

``compute_metrics`` arbeitet auf dem Trades-DataFrame des Backtesters
(Spalten: entry_time, exit_time, direction, entry, exit, sl, tp, lots, pnl,
r_multiple, meta). Optional kann eine Equity-Kurve (inkl. Floating PnL)
uebergeben werden, damit MaxDD(Equity) != MaxDD(Balance) moeglich ist.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TRADE_COLUMNS = [
    "entry_time", "exit_time", "direction", "entry", "exit",
    "sl", "tp", "lots", "pnl", "r_multiple", "meta",
]


def _max_drawdown(curve: pd.Series | np.ndarray) -> float:
    """Maximaler Peak-to-Trough-Drawdown (absolut, in Kurven-Einheiten)."""
    arr = np.asarray(curve, dtype=float)
    if arr.size == 0:
        return 0.0
    peak = np.maximum.accumulate(arr)
    dd = peak - arr
    return float(dd.max())


def _longest_losing_streak(pnls: np.ndarray) -> int:
    best = cur = 0
    for p in pnls:
        cur = cur + 1 if p < 0 else 0
        best = max(best, cur)
    return best


def _profit_factor(pnls: np.ndarray) -> float:
    gross_win = pnls[pnls > 0].sum()
    gross_loss = -pnls[pnls < 0].sum()
    if gross_loss <= 0:
        return float("inf") if gross_win > 0 else 0.0
    return float(gross_win / gross_loss)


def compute_metrics(
    trades: pd.DataFrame,
    equity_curve: pd.Series | None = None,
    periods_per_year: int = 252,
) -> dict:
    """Kennzahlen gemaess SPEC §4.11.

    PF, Winrate, avgR, MaxDD (Balance + Equity), Sharpe, Sortino, n,
    laengste Verlustserie, PF nach Richtung (long/short getrennt),
    PF nach Jahr.
    """
    m: dict = {
        "n": 0, "pf": 0.0, "winrate": 0.0, "avg_r": 0.0,
        "max_dd_balance": 0.0, "max_dd_equity": 0.0,
        "sharpe": 0.0, "sortino": 0.0, "longest_losing_streak": 0,
        "pf_long": 0.0, "pf_short": 0.0, "n_long": 0, "n_short": 0,
        "pf_by_year": {},
        "total_pnl": 0.0, "avg_pnl": 0.0,
    }
    if trades is None or len(trades) == 0:
        return m

    t = trades.sort_values("exit_time").reset_index(drop=True)
    pnl = t["pnl"].to_numpy(dtype=float)

    m["n"] = int(len(t))
    m["pf"] = _profit_factor(pnl)
    m["winrate"] = float((pnl > 0).mean())
    m["total_pnl"] = float(pnl.sum())
    m["avg_pnl"] = float(pnl.mean())
    if "r_multiple" in t.columns:
        m["avg_r"] = float(t["r_multiple"].astype(float).mean())
    m["longest_losing_streak"] = _longest_losing_streak(pnl)

    # MaxDD Balance: kumulierte geschlossene PnL
    balance = pnl.cumsum()
    m["max_dd_balance"] = _max_drawdown(balance)

    # MaxDD Equity: echte Equity-Kurve (inkl. Floating), sonst Balance-Proxy
    if equity_curve is not None and len(equity_curve) > 0:
        m["max_dd_equity"] = _max_drawdown(np.asarray(equity_curve, dtype=float))
    else:
        m["max_dd_equity"] = m["max_dd_balance"]

    # Sharpe/Sortino auf Tages-PnL (nach exit_time resampelt), annualisiert
    exits = pd.to_datetime(t["exit_time"], utc=True)
    daily = pd.Series(pnl, index=exits).resample("1D").sum()
    daily = daily[daily.index >= exits.min().normalize()]
    if len(daily) >= 2 and daily.std(ddof=1) > 0:
        m["sharpe"] = float(daily.mean() / daily.std(ddof=1) * np.sqrt(periods_per_year))
        downside = daily[daily < 0]
        dd_std = downside.std(ddof=1) if len(downside) >= 2 else 0.0
        m["sortino"] = (
            float(daily.mean() / dd_std * np.sqrt(periods_per_year)) if dd_std > 0 else 0.0
        )

    # PF nach Richtung — getrennt (Long-Bias-Falle!)
    long_pnl = t.loc[t["direction"] > 0, "pnl"].to_numpy(dtype=float)
    short_pnl = t.loc[t["direction"] < 0, "pnl"].to_numpy(dtype=float)
    m["pf_long"] = _profit_factor(long_pnl)
    m["pf_short"] = _profit_factor(short_pnl)
    m["n_long"] = int(len(long_pnl))
    m["n_short"] = int(len(short_pnl))

    # PF nach Jahr (exit_time)
    years = exits.dt.year
    m["pf_by_year"] = {
        int(y): _profit_factor(pnl[(years == y).to_numpy()]) for y in sorted(years.unique())
    }
    return m


# ---------------------------------------------------------------------------
# Report-Rendering
# ---------------------------------------------------------------------------
def render_report(result, path: str | Path) -> Path:
    """Markdown-Report + Equity-PNG (matplotlib).

    ``result`` ist ein BacktestResult (oder beliebiges Objekt mit Attributen
    ``trades``, ``equity_curve``, ``metrics``).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    metrics = result.metrics
    eq = result.equity_curve
    if isinstance(eq, pd.DataFrame):
        eq_series = eq["equity"] if "equity" in eq.columns else eq.iloc[:, 0]
    else:
        eq_series = pd.Series(eq)

    png_path = path / "equity.png"
    fig, ax = plt.subplots(figsize=(10, 4))
    eq_series.plot(ax=ax, lw=1.2)
    ax.set_title("Equity Curve")
    ax.set_xlabel("Zeit (UTC)")
    ax.set_ylabel("Equity")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)

    lines = [
        "# Backtest-Report",
        "",
        f"- Trades (n): **{metrics['n']}**",
        f"- Profit Factor: **{metrics['pf']:.3f}**",
        f"- Winrate: **{metrics['winrate'] * 100:.1f} %**",
        f"- avgR: **{metrics['avg_r']:.3f}**",
        f"- Total PnL: **{metrics['total_pnl']:.2f}**",
        f"- MaxDD (Balance): **{metrics['max_dd_balance']:.2f}**",
        f"- MaxDD (Equity): **{metrics['max_dd_equity']:.2f}**",
        f"- Sharpe: **{metrics['sharpe']:.2f}** | Sortino: **{metrics['sortino']:.2f}**",
        f"- Laengste Verlustserie: **{metrics['longest_losing_streak']}**",
        "",
        "## PF nach Richtung (Long-Bias-Check)",
        "",
        "| Richtung | n | PF |",
        "|---|---|---|",
        f"| Long | {metrics['n_long']} | {metrics['pf_long']:.3f} |",
        f"| Short | {metrics['n_short']} | {metrics['pf_short']:.3f} |",
        "",
        "## PF nach Jahr",
        "",
        "| Jahr | PF |",
        "|---|---|",
    ]
    for year, pf in metrics["pf_by_year"].items():
        lines.append(f"| {year} | {pf:.3f} |")
    lines += ["", f"![Equity]({png_path.name})", ""]

    md_path = path / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def ab_compare(results: dict) -> pd.DataFrame:
    """Filter-Layer-Vergleichstabelle (A/B).

    ``results``: {label: BacktestResult}. Rueckgabe: DataFrame (eine Zeile
    pro Variante) mit den Kernmetriken; ``.to_markdown()`` fuer Reports.
    """
    rows = {}
    for label, res in results.items():
        m = res.metrics
        rows[label] = {
            "n": m["n"],
            "pf": m["pf"],
            "winrate": m["winrate"],
            "avg_r": m["avg_r"],
            "max_dd_balance": m["max_dd_balance"],
            "max_dd_equity": m["max_dd_equity"],
            "sharpe": m["sharpe"],
            "sortino": m["sortino"],
            "pf_long": m["pf_long"],
            "pf_short": m["pf_short"],
        }
    return pd.DataFrame(rows).T
