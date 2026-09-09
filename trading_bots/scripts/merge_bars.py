"""Merge mehrerer OHLCV-Dateien (CSV/Parquet) zu einer Parquet-Datei.

Use-Case: Dukascopy-Historie (2022→2025-04) mit dem MT5-Tail
(2025-03→heute) zu ``data/{SYMBOL}_{TF}.parquet`` zusammenfuehren.

Regeln:
- Index wird auf UTC normalisiert (naive Zeitstempel werden als UTC
  interpretiert).
- Duplikate im Zeit-Index: der zuletzt uebergebene Input gewinnt
  (keep="last"), d. h. Inputs in aufsteigender Prioritaet angeben.
- Ausgabe ist aufsteigend sortiert und wird durch
  ``core.connector.validate_ohlcv`` geprueft.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from core.connector import OHLCV_COLUMNS, UTC, validate_ohlcv

log = logging.getLogger("merge_bars")


def read_bars(path: str | Path) -> pd.DataFrame:
    """Liest eine CSV- oder Parquet-Bar-Datei mit UTC-Index."""
    path = Path(path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.DatetimeIndex(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize(UTC)
    else:
        df.index = df.index.tz_convert(UTC)
    df.index.name = "time"
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV-Spalten fehlen in {path}: {missing}")
    return df[OHLCV_COLUMNS]


def merge_bars(inputs: list[str | Path]) -> pd.DataFrame:
    """Merged Bar-Dateien; bei Index-Konflikten gewinnt der spaetere Input."""
    if not inputs:
        raise ValueError("Keine Input-Dateien")
    frames = [read_bars(p) for p in inputs]
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    return validate_ohlcv(df)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OHLCV-Dateien zu Parquet mergen")
    parser.add_argument("inputs", nargs="+", help="CSV/Parquet-Dateien (steigende Prioritaet)")
    parser.add_argument("--out", required=True, help="Ziel-Parquet, z.B. data/XAUUSD_M5.parquet")
    parser.add_argument("--timeframe", default="M5")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    df = merge_bars(args.inputs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=True)
    log.info("Gespeichert: %s (%d Bars, %s .. %s)", out, len(df), df.index[0], df.index[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
