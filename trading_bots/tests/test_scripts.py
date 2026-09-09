"""tests/test_scripts.py — CLI-Smoke-Tests mit synthetischen Daten (tmp_path).

Enthaelt den bi5-Parser-Test: selbst erzeugter LZMA-Blob mit bekannten
Records -> bekannte Bars. KEIN Live-Download, KEIN echter MT5.
"""

from __future__ import annotations

import lzma
import struct
from datetime import date, datetime

import pandas as pd
import pytest

from scripts import fetch_data
from scripts.fetch_data import (
    DayIncompleteError,
    DownloadError,
    RateLimiter,
    fetch_dukascopy,
    fetch_histdata,
    fetch_ticks_day,
    histdata_symbol,
    parse_bi5,
    save_csv,
    ticks_to_bars,
)
from core.connector import load_ohlcv

UTC = "UTC"


# ---------------------------------------------------------------------------
# Hilfen: synthetischer .bi5-Blob
# ---------------------------------------------------------------------------
def make_bi5(records: list[tuple[int, int, int, float, float]]) -> bytes:
    """records: (ms_offset_in_hour, ask_int, bid_int, ask_vol, bid_vol)."""
    raw = b"".join(struct.pack(">IIIff", *r) for r in records)
    return lzma.compress(raw)


HOUR = pd.Timestamp("2024-01-02 10:00", tz=UTC)  # Dienstag

# EURUSD-Preise x1000 (z.B. 110.050 == "1.10050" im x1000-Raum des Tasks)
TICKS = [
    (0,      110050, 110040, 1.0, 1.0),   # 10:00:00.000 mid=110.045
    (60_000, 110060, 110050, 1.0, 1.0),   # 10:01:00 mid=110.055
    (120_000, 110040, 110030, 1.0, 1.0),  # 10:02:00 mid=110.035
    (300_000, 110080, 110070, 1.0, 1.0),  # 10:05:00 mid=110.075
    (600_000, 110060, 110050, 1.0, 1.0),  # 10:10:00 mid=110.055
]


# ---------------------------------------------------------------------------
# bi5-Parser
# ---------------------------------------------------------------------------
def test_parse_bi5_known_records():
    blob = make_bi5(TICKS)
    df = parse_bi5(blob, HOUR, price_scale=1000.0)
    assert len(df) == 5
    assert str(df.index.tz) == "UTC"
    assert df.index[0] == HOUR
    assert df.index[3] == HOUR + pd.Timedelta(minutes=5)
    assert df["ask"].iloc[0] == pytest.approx(110.050)
    assert df["bid"].iloc[2] == pytest.approx(110.030)
    assert df["mid"].iloc[0] == pytest.approx(110.045)


def test_parse_bi5_empty_blob():
    df = parse_bi5(lzma.compress(b""), HOUR, 1000.0)
    assert df.empty


def test_ticks_to_bars_m1_known():
    ticks = parse_bi5(make_bi5(TICKS), HOUR, 1000.0)
    m1 = ticks_to_bars(ticks, "M1")
    assert list(m1.columns) == ["open", "high", "low", "close", "tick_volume"]
    assert str(m1.index.tz) == "UTC"
    # 4 belegte Minuten (10:00, 10:01, 10:02, 10:05, 10:10 -> 5 Bars)
    assert len(m1) == 5
    bar0 = m1.loc[HOUR]
    assert bar0["open"] == pytest.approx(110.045)
    assert bar0["tick_volume"] == 1.0
    assert all(m1.dtypes == "float64")


def test_ticks_to_bars_m5_aggregation():
    ticks = parse_bi5(make_bi5(TICKS), HOUR, 1000.0)
    m5 = ticks_to_bars(ticks, "M5")
    # Bar 10:00 deckt Ticks bei 0/60/120s ab; 10:05 den bei 300s; 10:10 den bei 600s
    assert len(m5) == 3
    bar = m5.loc[HOUR]
    assert bar["open"] == pytest.approx(110.045)          # erster Tick
    assert bar["high"] == pytest.approx(110.055)          # max mid
    assert bar["low"] == pytest.approx(110.035)           # min mid
    assert bar["close"] == pytest.approx(110.035)         # letzter Tick im Fenster
    assert bar["tick_volume"] == 3.0                      # Anzahl Ticks


# ---------------------------------------------------------------------------
# Tages-Fetch + Cache (kein Netz: Downloader injiziert)
# ---------------------------------------------------------------------------
def fake_downloader_factory(blobs_by_hour: dict[int, bytes]):
    calls = []

    def dl(symbol_duka: str, dt_utc: datetime):
        calls.append((symbol_duka, dt_utc))
        return blobs_by_hour.get(dt_utc.hour)

    dl.calls = calls
    return dl


def test_fetch_ticks_day_and_resume_cache(tmp_path):
    dl = fake_downloader_factory({10: make_bi5(TICKS)})
    ticks = fetch_ticks_day("EURUSD", date(2024, 1, 2), tmp_path, pause=0.0,
                            downloader=dl)
    assert len(ticks) == 5
    assert len(dl.calls) == 24                       # 24 Stunden-Requests
    assert (tmp_path / "EURUSD" / "2024-01-02.csv").exists()

    # Resume: zweiter Aufruf liest Cache, Downloader wird NICHT mehr aufgerufen
    dl2 = fake_downloader_factory({})
    ticks2 = fetch_ticks_day("EURUSD", date(2024, 1, 2), tmp_path, pause=0.0,
                             downloader=dl2)
    assert len(dl2.calls) == 0
    assert len(ticks2) == 5
    assert ticks2.index[0] == HOUR


def test_fetch_ticks_day_caches_empty_weekend(tmp_path):
    dl = fake_downloader_factory({})                 # keine Daten (Wochenende)
    ticks = fetch_ticks_day("EURUSD", date(2024, 1, 6), tmp_path, pause=0.0,
                            downloader=dl)
    assert ticks.empty
    assert (tmp_path / "EURUSD" / "2024-01-06.empty").exists()
    dl2 = fake_downloader_factory({})
    fetch_ticks_day("EURUSD", date(2024, 1, 6), tmp_path, pause=0.0, downloader=dl2)
    assert len(dl2.calls) == 0                       # .empty-Marker -> kein Request


def test_symbol_mapping_index():
    assert fetch_data.dukascopy_symbol("NAS100") == "USATECHIDXUSD"
    assert fetch_data.dukascopy_symbol("US100") == "USATECHIDXUSD"
    assert fetch_data.dukascopy_symbol("EURUSD") == "EURUSD"
    assert fetch_data.PRICE_SCALE["USATECHIDXUSD"] == 1.0   # Indizes x1


# ---------------------------------------------------------------------------
# Rate-Limit-Robustheit: kein partielles Tages-Caching, 429-Backoff
# ---------------------------------------------------------------------------
def test_download_hour_429_backoff_then_error(monkeypatch):
    """429 wird mit Backoff retried; nach Erschoepfung DownloadError."""
    import requests

    class Resp429:
        status_code = 429

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp429())
    # Globaler Rate-Limiter (RateLimiter) fuer diesen Test isoliert ausschalten
    # — hier wird nur das 429-Backoff geprueft, nicht das Requests/s-Limit.
    monkeypatch.setattr(fetch_data._DUKASCOPY_LIMITER, "acquire", lambda: None)
    sleeps = []
    monkeypatch.setattr(fetch_data.time, "sleep", lambda s: sleeps.append(s))
    with pytest.raises(DownloadError, match="429"):
        fetch_data._download_hour("EURUSD", datetime(2024, 1, 2, 10))
    assert len(sleeps) == fetch_data.REQUEST_RETRIES
    assert all(s >= fetch_data.RATE_LIMIT_BACKOFF for s in sleeps)


def test_download_hour_404_returns_none(monkeypatch):
    import requests

    class Resp404:
        status_code = 404

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp404())
    assert fetch_data._download_hour("EURUSD", datetime(2024, 1, 2, 10)) is None


def test_fetch_ticks_day_no_partial_cache(tmp_path):
    """Tag mit fehlgeschlagener Stunde: DayIncompleteError, kein Cache-File."""
    def dl(symbol_duka, dt_utc):
        if dt_utc.hour == 5:
            raise DownloadError("boom")
        return make_bi5(TICKS) if dt_utc.hour == 10 else None

    with pytest.raises(DayIncompleteError):
        fetch_ticks_day("EURUSD", date(2024, 1, 2), tmp_path, pause=0.0,
                        downloader=dl)
    assert not (tmp_path / "EURUSD" / "2024-01-02.csv").exists()
    assert not (tmp_path / "EURUSD" / "2024-01-02.empty").exists()


def test_fetch_dukascopy_retries_incomplete_days(tmp_path):
    """Nachlauf laedt fehlgeschlagene Tage seriell nach (dann gecacht)."""
    state = {"failed_once": False}

    def dl(symbol_duka, dt_utc):
        if dt_utc.day == 3 and dt_utc.hour == 5 and not state["failed_once"]:
            state["failed_once"] = True
            raise DownloadError("boom")
        return make_bi5(TICKS) if dt_utc.hour == 10 else None

    df = fetch_dukascopy("EURUSD", "M5", datetime(2024, 1, 2), datetime(2024, 1, 4),
                         cache_dir=tmp_path / "cache", pause=0.0, downloader=dl,
                         workers=4)
    assert state["failed_once"]
    assert (tmp_path / "cache" / "EURUSD" / "2024-01-03.csv").exists()
    assert len(df) == 6  # 2 Tage x 3 Bars


# ---------------------------------------------------------------------------
# End-to-End: fetch_dukascopy -> Parquet -> load_ohlcv (SPEC §3 Kontrakt)
# ---------------------------------------------------------------------------
def test_fetch_dukascopy_to_parquet_and_load(tmp_path):
    dl = fake_downloader_factory({10: make_bi5(TICKS)})
    df = fetch_dukascopy("EURUSD", "M5", datetime(2024, 1, 2), datetime(2024, 1, 3),
                         cache_dir=tmp_path / "cache", pause=0.0, downloader=dl)
    assert len(df) == 3
    assert str(df.index.tz) == "UTC"
    assert list(df.columns) == ["open", "high", "low", "close", "tick_volume"]

    out = tmp_path / "out"
    path = save_csv(df, out, "EURUSD", "M5")
    assert path.name == "EURUSD_M5.parquet"
    loaded = load_ohlcv("EURUSD", "M5", datetime(2024, 1, 2), datetime(2024, 1, 3),
                        source="cache", data_dir=out)
    pd.testing.assert_frame_equal(loaded, df)


def test_fetch_data_cli_dukascopy(tmp_path, monkeypatch, capsys):
    """CLI-Smoke-Test: --source dukascopy mit injiziertem Downloader."""
    dl = fake_downloader_factory({10: make_bi5(TICKS)})
    monkeypatch.setattr(fetch_data, "_download_hour", dl)
    rc = fetch_data.main([
        "--symbol", "EURUSD", "--timeframe", "M5",
        "--start", "2024-01-02", "--end", "2024-01-03",
        "--source", "dukascopy", "--out", str(tmp_path / "data"),
        "--cache-dir", str(tmp_path / "cache"), "--pause", "0",
    ])
    out = capsys.readouterr().out
    assert "Gap-Audit M5" in out
    assert rc == 0
    pq = (tmp_path / "data" / "EURUSD_M5.parquet")
    assert pq.exists()
    df = pd.read_parquet(pq)
    assert len(df) == 3


# ---------------------------------------------------------------------------
# run_backtest / run_wfa Smoke
# ---------------------------------------------------------------------------
def test_run_backtest_config_validation(tmp_path):
    from scripts.run_backtest import load_config
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text("strategy: s1_trend_pullback\n", encoding="utf-8")
    with pytest.raises(ValueError, match="symbols"):
        load_config(cfg_path)


def test_run_wfa_gate_logic():
    """check_gates ist rein (keine Backtest-Abhaengigkeit) — Logik testen."""
    from scripts.run_wfa import check_gates
    gates = {
        "min_oos_trades": 300,
        "wfe_median_min": 0.5,
        "pf_1x_min": 1.5,
        "mc_p95_maxdd_pct": 8.0,
    }
    metrics_ok = {"n_oos": 350, "wfe_median": 0.62, "wfe_folds_ge_05": 0.8,
                  "oos_pf": 1.7, "mc_p95_dd_pct": 5.0, "prop": None}
    checks = check_gates(metrics_ok, gates)
    assert checks and all(ok for _n, ok, _d in checks)

    metrics_bad = dict(metrics_ok, oos_pf=1.1, wfe_median=1.4)  # PF-FAIL + Lookahead
    checks = check_gates(metrics_bad, gates)
    by_name = {name: ok for name, ok, _d in checks}
    assert by_name["PF(1x) >= 1.5"] is False
    assert any("Lookahead" in n and not ok for n, ok, _d in checks)


def test_run_backtest_full_pipeline_synthetic(tmp_path, monkeypatch):
    """End-to-End: synthetische CSVs -> run_backtest (nur wenn core-Module da)."""
    pytest.importorskip("core.backtester")
    pytest.importorskip("core.risk")
    from scripts import run_backtest

    # Synthetische H1-Daten (SPEC-§3-Kontrakt)
    idx = pd.date_range("2024-01-01", periods=500, freq="h", tz=UTC)
    close = (2000 + pd.Series(range(500), dtype=float) * 0.1).to_numpy()
    df = pd.DataFrame({"open": close - 0.05, "high": close + 0.1,
                       "low": close - 0.1, "close": close,
                       "tick_volume": 100.0}, index=idx)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    df.to_csv(data_dir / "XAUUSD_H1.csv", index_label="time")

    cfg_path = tmp_path / "s1.yaml"
    cfg_path.write_text(
        "strategy: dummy\nsymbols: [XAUUSD]\ntimeframes: [H1]\n"
        "start: '2024-01-01'\nend: '2024-01-22'\nparams: {}\n"
        "risk: {risk_per_trade_pct: 0.5}\ncosts: {XAUUSD: {spread_points: 35}}\n",
        encoding="utf-8")

    class DummyStrategy:
        name = "dummy"
        required_timeframes = ["H1"]

        def __init__(self, params):
            self.params = params

        def on_bar(self, bars, i):
            if i == 100:  # genau ein Trade fuer den Smoke-Test
                from types import SimpleNamespace
                df = bars["H1"]
                close = float(df["close"].iloc[-1])
                return SimpleNamespace(
                    time=df.index[-1], symbol="XAUUSD", direction=1,
                    entry_type="market", entry_price=None,
                    stop_loss=close - 10.0, take_profit=close + 20.0,
                    risk_pct=0.005, meta={}, expires_bars=0)
            return None

    monkeypatch.setattr(run_backtest, "load_strategy_class",
                        lambda name: DummyStrategy)
    rc = run_backtest.main(["--config", str(cfg_path), "--data-dir", str(data_dir),
                            "--out", str(tmp_path / "reports"), "--common",
                            str(tmp_path / "missing_common.yaml")])
    assert rc == 0
    assert (tmp_path / "reports" / "report.md").exists()


# ---------------------------------------------------------------------------
# RateLimiter (globaler Dukascopy-Rate-Limiter)
# ---------------------------------------------------------------------------
def test_rate_limiter_enforces_min_interval(monkeypatch):
    """RateLimiter erzwingt Mindestabstand ueber mehrere acquire()-Aufrufe,
    unabhaengig davon, aus wie vielen Threads sie kommen (hier seriell mit
    Fake-Clock geprueft: kein reales Warten im Test)."""
    clock = [0.0]
    monkeypatch.setattr(fetch_data.time, "monotonic", lambda: clock[0])
    sleeps: list[float] = []

    def fake_sleep(s):
        sleeps.append(s)
        clock[0] += s

    monkeypatch.setattr(fetch_data.time, "sleep", fake_sleep)

    limiter = RateLimiter(4.0)  # 0.25s Mindestabstand
    for _ in range(3):
        limiter.acquire()
    # 1. Aufruf sofort (kein Sleep), 2./3. je 0.25s gewartet
    assert sleeps == pytest.approx([0.25, 0.25])


def test_rate_limiter_disabled_when_zero():
    limiter = RateLimiter(0.0)
    limiter.acquire()  # darf nicht blockieren/werfen


# ---------------------------------------------------------------------------
# HistData.com-Quelle (kein Netz: injizierter Downloader / synthetisches CSV)
# ---------------------------------------------------------------------------
def test_histdata_symbol_mapping():
    assert histdata_symbol("NAS100") == "nsxusd"
    assert histdata_symbol("US100") == "nsxusd"
    assert histdata_symbol("EURUSD") == "eurusd"
    assert histdata_symbol("XAUUSD") == "xauusd"


def test_parse_histdata_csv_converts_fixed_est_to_utc():
    """HistData-Zeitstempel sind EST OHNE DST (fix UTC-5) -> +5h fuer UTC."""
    raw = "20230102 180000;11047.869;11063.169;11019.519;11022.119;0\n"
    df = fetch_data._parse_histdata_csv(raw)
    assert list(df.columns) == fetch_data.OHLCV_COLUMNS
    assert df.index.tz is not None
    assert df.index[0] == pd.Timestamp("2023-01-02 23:00:00", tz="UTC")
    assert df["close"].iloc[0] == pytest.approx(11022.119)
    assert df["tick_volume"].iloc[0] == 0.0  # HistData: kein echtes Volumen


def test_parse_histdata_csv_empty():
    df = fetch_data._parse_histdata_csv("")
    assert df.empty
    assert list(df.columns) == fetch_data.OHLCV_COLUMNS


def test_histdata_periods_past_year_vs_current_year(monkeypatch):
    """Volle Vergangenheitsjahre: 1x (Jahr, None). Laufendes Jahr: je Monat."""
    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 3, 15, tzinfo=tz)

    monkeypatch.setattr(fetch_data, "datetime", FakeDatetime)
    start = pd.Timestamp("2023-06-01", tz="UTC")
    end = pd.Timestamp("2026-02-01", tz="UTC")
    periods = fetch_data._histdata_periods(start, end)
    assert (2023, None) in periods
    assert (2024, None) in periods
    assert (2025, None) in periods
    assert (2026, None) not in periods
    assert (2026, 1) in periods and (2026, 2) in periods
    assert (2026, 3) not in periods  # end ist exklusiv, Monat 2 ist letzter


def test_fetch_histdata_end_to_end(tmp_path):
    """fetch_histdata mit injiziertem Downloader (kein Netz): Cache + Resample
    auf H1, SPEC-§3-Kontrakt (UTC-tz-aware, exakte Spalten)."""
    calls = []

    def fake_downloader(symbol_hd, year, month):
        calls.append((symbol_hd, year, month))
        assert symbol_hd == "eurusd"
        idx = pd.date_range("2023-01-02 23:00", periods=180, freq="1min", tz="UTC")
        return pd.DataFrame({"open": 1.10, "high": 1.101, "low": 1.099,
                             "close": 1.1005, "tick_volume": 0.0}, index=idx)

    start = pd.Timestamp("2023-01-02", tz="UTC")
    end = pd.Timestamp("2023-01-04", tz="UTC")
    df = fetch_data.fetch_histdata("EURUSD", "H1", start, end,
                                   cache_dir=tmp_path / "cache", pause=0.0,
                                   downloader=fake_downloader)
    assert calls == [("eurusd", 2023, None)]  # 1 Request statt 24/Tag bei Dukascopy
    assert not df.empty
    assert list(df.columns) == fetch_data.OHLCV_COLUMNS
    assert df.index.tz is not None
    assert (df.index[1] - df.index[0]) >= pd.Timedelta(hours=1)
    cache_file = tmp_path / "cache" / "eurusd" / "2023.csv"
    assert cache_file.exists()

    # Zweiter Aufruf liest aus dem Cache (Downloader wird nicht erneut gerufen)
    calls.clear()
    fetch_data.fetch_histdata("EURUSD", "H1", start, end,
                              cache_dir=tmp_path / "cache", pause=0.0,
                              downloader=fake_downloader)
    assert calls == []


def test_fetch_histdata_nas100_proxy_warns(tmp_path, caplog):
    """NAS100 -> HistData nsxusd-Proxy, mit Warnung (wie Dukascopy USATECHIDXUSD)."""
    def fake_downloader(symbol_hd, year, month):
        assert symbol_hd == "nsxusd"
        idx = pd.date_range("2023-01-02 23:00", periods=5, freq="1min", tz="UTC")
        return pd.DataFrame({"open": 11000.0, "high": 11010.0, "low": 10990.0,
                             "close": 11005.0, "tick_volume": 0.0}, index=idx)

    with caplog.at_level("WARNING"):
        df = fetch_data.fetch_histdata("NAS100", "M1",
                                       pd.Timestamp("2023-01-02", tz="UTC"),
                                       pd.Timestamp("2023-01-03", tz="UTC"),
                                       cache_dir=tmp_path / "cache", pause=0.0,
                                       downloader=fake_downloader)
    assert not df.empty
    assert any("nsxusd" in r.message for r in caplog.records)


def test_fetch_histdata_one_failed_period_does_not_abort_fetch(tmp_path, caplog):
    """Ein fehlgeschlagener Zeitraum (z.B. laufender Monat noch ohne Daten
    bei HistData) bricht NICHT den gesamten Mehrjahres-Fetch ab — analog zu
    Dukascopys DayIncompleteError-Handling (ein Tag scheitert, der Rest
    laeuft weiter)."""
    def flaky_downloader(symbol_hd, year, month):
        if (year, month) == (2026, 9):
            raise AssertionError("There is no token.")  # wie histdata-Lib
        idx = pd.date_range(f"{year}-01-02 23:00", periods=5, freq="1min", tz="UTC")
        return pd.DataFrame({"open": 1.10, "high": 1.101, "low": 1.099,
                             "close": 1.1005, "tick_volume": 0.0}, index=idx)

    with caplog.at_level("WARNING"):
        df = fetch_data.fetch_histdata(
            "EURUSD", "M1", pd.Timestamp("2025-01-01", tz="UTC"),
            pd.Timestamp("2026-09-01", tz="UTC"),
            cache_dir=tmp_path / "cache", pause=0.0, downloader=flaky_downloader)
    assert not df.empty  # 2025 (voll) ist trotzdem da
    assert any("fehlgeschlagen" in r.message for r in caplog.records)
