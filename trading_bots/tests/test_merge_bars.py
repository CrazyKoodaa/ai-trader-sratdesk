"""Tests fuer scripts/merge_bars.py (Dukascopy+MT5-Tail-Merge)."""

from datetime import datetime

import pandas as pd
import pytest

from core.connector import UTC
from scripts.merge_bars import merge_bars, read_bars


def _bars(idx, price=100.0):
    return pd.DataFrame(
        {"open": price, "high": price + 1, "low": price - 1,
         "close": price, "tick_volume": 10},
        index=pd.DatetimeIndex(idx, name="time"))


def test_merge_dedupes_overlap_keep_last(tmp_path):
    idx_a = pd.date_range("2024-01-01", periods=10, freq="5min", tz=UTC)
    idx_b = pd.date_range("2024-01-01 00:25", periods=10, freq="5min", tz=UTC)
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.csv"
    _bars(idx_a, price=100.0).to_parquet(a, index=True)
    _bars(idx_b, price=200.0).to_csv(b, index_label="time")

    df = merge_bars([a, b])
    assert len(df) == 15  # 10 + 5 neue, 5 Overlap dedupliziert
    assert df.index.is_monotonic_increasing
    assert str(df.index.tz) == "UTC"
    # Overlap: spaeterer Input (b, Preis 200) gewinnt
    assert float(df.loc[pd.Timestamp("2024-01-01 00:25", tz=UTC), "close"]) == 200.0


def test_merge_rejects_unsorted_or_invalid(tmp_path):
    df = _bars(pd.date_range("2024-01-01", periods=5, freq="5min", tz=UTC))
    df = df.drop(columns=["tick_volume"])
    p = tmp_path / "broken.parquet"
    df.to_parquet(p, index=True)
    with pytest.raises(ValueError, match="Spalten"):
        merge_bars([p])


def test_read_bars_localizes_naive_csv(tmp_path):
    p = tmp_path / "naive.csv"
    _bars(pd.date_range("2024-01-01", periods=3, freq="5min")).to_csv(p, index_label="time")
    df = read_bars(p)
    assert str(df.index.tz) == "UTC"


def test_merge_requires_inputs():
    with pytest.raises(ValueError, match="Keine Input"):
        merge_bars([])


def test_merged_output_loadable_via_load_ohlcv(tmp_path):
    from core.connector import load_ohlcv
    idx = pd.date_range("2024-01-08", periods=24, freq="5min", tz=UTC)
    a = tmp_path / "a.parquet"
    _bars(idx).to_parquet(a, index=True)
    out = tmp_path / "XAUUSD_M5.parquet"
    merged = merge_bars([a])
    merged.to_parquet(out, index=True)
    loaded = load_ohlcv("XAUUSD", "M5", datetime(2024, 1, 8, 0), datetime(2024, 1, 8, 1),
                        source="cache", data_dir=tmp_path)
    assert len(loaded) == 12
