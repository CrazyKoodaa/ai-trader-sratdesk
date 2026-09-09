"""tests/test_connector.py — Connector-Tests gegen ein Fake-RPyC-Objekt.

KEIN echter MT5/RPyC noetig: ``FakeMT5`` mimt die mt5linux-MetaTrader5-API
(namedtuple-artige Rueckgaben, numpy-structured-arrays bei copy_rates_range).
"""

from __future__ import annotations

import calendar
import logging
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from core.connector import (
    MT5Connector,
    RETCODE_DONE,
    RETCODE_INVALID_PRICE,
    RETCODE_INVALID_STOPS,
    RETCODE_UNSUPPORTED_FILLING,
    audit_gaps,
    load_ohlcv,
    validate_ohlcv,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fake-RPyC-Objekt (mimt mt5linux.MetaTrader5 serverseitig)
# ---------------------------------------------------------------------------
class FakeMT5:
    """Fake des pymt5linux-RPyC-Clients.

    Server laeuft mit Offset ``server_offset_hours`` gegenueber UTC
    (typisch EET/EEST = +2/+3). copy_rates_range liefert server-epoch Zeiten.
    """

    # Konstanten wie das echte mt5-Modul
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_D1 = 16408
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    def __init__(self, server_offset_hours: int = 2):
        self.offset = timedelta(hours=server_offset_hours)
        self.bid, self.ask = 1999.90, 2000.10
        self.order_send_calls: list[dict] = []
        self.retcode_script: list[int] = []      # verbraucht sich bei order_send
        self.default_retcode = RETCODE_DONE
        self._positions: list[SimpleNamespace] = []
        self.tick_calls = 0

    # -- Verbindung -------------------------------------------------------
    def initialize(self):
        return True

    def shutdown(self):
        return True

    def last_error(self):
        return (0, "ok")

    # -- Marktdaten ---------------------------------------------------------
    def symbol_info_tick(self, symbol):
        self.tick_calls += 1
        server_now = time.time() + self.offset.total_seconds()
        return SimpleNamespace(time=int(server_now), ask=self.ask, bid=self.bid,
                               time_msc=int(server_now * 1000))

    def symbols_get(self):
        return [SimpleNamespace(name="XAUUSD")]

    def symbol_info(self, symbol):
        return SimpleNamespace(
            point=0.01, digits=2, trade_tick_size=0.01, trade_tick_value=1.0,
            volume_step=0.01, volume_min=0.01, volume_max=50.0,
            trade_stops_level=10, trade_contract_size=100.0,
        )

    def copy_rates_range(self, symbol, timeframe, dt_from, dt_to):
        """Liefert M5-Bars (server-epoch) im [dt_from, dt_to) (naive Serverzeit)."""
        assert isinstance(dt_from, datetime) and dt_from.tzinfo is None
        tf_minutes = {1: 1, 5: 5, 15: 15, 16385: 60, 16388: 240, 16408: 1440}[timeframe]
        start_epoch = calendar.timegm(dt_from.timetuple())
        end_epoch = calendar.timegm(dt_to.timetuple())
        rows = []
        t = start_epoch
        price = 2000.0
        while t < end_epoch:
            rows.append((t, price, price + 1.0, price - 1.0, price + 0.5, 100.0, 2, 0.5))
            price += 0.1
            t += tf_minutes * 60
        dtype = [("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                 ("close", "f8"), ("tick_volume", "f8"), ("spread", "i4"),
                 ("real_volume", "f8")]
        return np.array(rows, dtype=dtype)

    # -- Konto/Positionen ---------------------------------------------------
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2

    def account_info(self):
        return SimpleNamespace(login=12345, balance=100_000.0, equity=100_100.0,
                               margin=100.0, margin_free=99_900.0, margin_level=1000.0,
                               currency="USD", leverage=100, profit=100.0,
                               server="Fake-Server", name="Demo",
                               trade_mode=getattr(self, "trade_mode", self.ACCOUNT_TRADE_MODE_DEMO))

    def terminal_info(self):
        return SimpleNamespace(connected=True, trade_allowed=True)

    def positions_get(self, **kwargs):
        if "ticket" in kwargs:
            return [p for p in self._positions if p.ticket == kwargs["ticket"]]
        if "symbol" in kwargs:
            return [p for p in self._positions if p.symbol == kwargs["symbol"]]
        return list(self._positions)

    # -- Historie (Journal/Dashboard) ----------------------------------------
    def history_select(self, date_from, date_to):
        return True

    def history_deals_get(self, *args, **kwargs):
        return list(getattr(self, "_deals", []))

    # -- Orders --------------------------------------------------------------
    def order_send(self, request):
        self.order_send_calls.append(dict(request))
        retcode = self.retcode_script.pop(0) if self.retcode_script else self.default_retcode
        return SimpleNamespace(retcode=retcode, order=4711, deal=4712,
                               price=request.get("price", 0.0), comment="done")

    def order_calc_profit(self, action, symbol, volume, price_open, price_close):
        sign = 1.0 if action == self.ORDER_TYPE_BUY else -1.0
        return sign * volume * 100.0 * (price_close - price_open)  # contract 100


@pytest.fixture()
def fake():
    return FakeMT5(server_offset_hours=2)


@pytest.fixture()
def connector(fake):
    return MT5Connector(client=fake, dry_run=True, backoff_base=0.0)


# ---------------------------------------------------------------------------
# UTC-Konvertierung (UTC-at-ingestion, SPEC §3)
# ---------------------------------------------------------------------------
def test_server_offset_rounded(connector):
    offset = connector.server_offset("XAUUSD")
    assert offset == timedelta(hours=2)


def test_fetch_ohlcv_converts_server_time_to_utc(connector, fake):
    start = datetime(2024, 1, 8, 0, 0)     # UTC
    end = datetime(2024, 1, 8, 2, 0)       # 24 M5-Bars
    df = connector.fetch_ohlcv("XAUUSD", "M5", start, end)
    assert len(df) == 24
    assert str(df.index.tz) == "UTC"
    # Erster Bar: Serverzeit 02:00 (UTC+2) -> UTC 00:00
    assert df.index[0] == pd.Timestamp("2024-01-08 00:00", tz=UTC)
    assert df.index[-1] == pd.Timestamp("2024-01-08 01:55", tz=UTC)
    assert list(df.columns) == ["open", "high", "low", "close", "tick_volume"]
    assert all(df.dtypes == "float64")


def test_fetch_ohlcv_requests_in_server_time(connector, fake, monkeypatch):
    seen = {}

    orig = fake.copy_rates_range

    def spy(symbol, tf, dt_from, dt_to):
        seen.setdefault("from", dt_from)
        return orig(symbol, tf, dt_from, dt_to)

    monkeypatch.setattr(fake, "copy_rates_range", spy)
    connector.fetch_ohlcv("XAUUSD", "M5", datetime(2024, 1, 8), datetime(2024, 1, 8, 1))
    # Anfrage muss in Serverzeit (UTC+2) erfolgen: 00:00 UTC -> 02:00 Server
    assert seen["from"] == datetime(2024, 1, 8, 2, 0)


def test_fetch_ohlcv_capping_warning(connector, fake, caplog, monkeypatch):
    """Server liefert Historie erst deutlich nach 'start' -> Capping-Warnung."""

    def capped(symbol, tf, dt_from, dt_to):
        dt_from = max(dt_from, datetime(2024, 1, 5, 2, 0))  # Server kappt
        if dt_from >= dt_to:
            return np.array([], dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"),
                                       ("low", "f8"), ("close", "f8"),
                                       ("tick_volume", "f8"), ("spread", "i4"),
                                       ("real_volume", "f8")])
        return FakeMT5.copy_rates_range(fake, symbol, tf, dt_from, dt_to)

    monkeypatch.setattr(fake, "copy_rates_range", capped)
    with caplog.at_level(logging.WARNING):
        df = connector.fetch_ohlcv("XAUUSD", "M5",
                                   datetime(2024, 1, 1), datetime(2024, 1, 6))
    assert len(df) > 0
    assert df.index[0] == pd.Timestamp("2024-01-05 00:00", tz=UTC)
    assert any("CAPPING" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Retcode-Retry-Logik (10015/10016/10030, max 3, exponential backoff)
# ---------------------------------------------------------------------------
def _live_connector(fake):
    return MT5Connector(client=fake, dry_run=False, backoff_base=0.0)


def test_send_market_success_first_try(fake):
    conn = _live_connector(fake)
    res = conn.send_market("XAUUSD", +1, 1.0, sl=1990.0, tp=2010.0, deviation=5)
    assert res["retcode"] == RETCODE_DONE
    assert len(fake.order_send_calls) == 1
    req = fake.order_send_calls[0]
    assert req["price"] == fake.ask            # Buy -> Ask
    assert req["sl"] == 1990.0 and req["tp"] == 2010.0
    assert req["type_filling"] == FakeMT5.ORDER_FILLING_IOC


def test_retry_10030_cycles_filling_mode(fake):
    conn = _live_connector(fake)
    fake.retcode_script = [RETCODE_UNSUPPORTED_FILLING, RETCODE_DONE]
    res = conn.send_market("XAUUSD", +1, 1.0, sl=1990.0, tp=2010.0)
    assert res["retcode"] == RETCODE_DONE
    assert len(fake.order_send_calls) == 2
    assert fake.order_send_calls[0]["type_filling"] == FakeMT5.ORDER_FILLING_IOC
    assert fake.order_send_calls[1]["type_filling"] == FakeMT5.ORDER_FILLING_FOK


def test_retry_10015_requotes_price(fake):
    conn = _live_connector(fake)
    fake.retcode_script = [RETCODE_INVALID_PRICE, RETCODE_DONE]
    res = conn.send_market("XAUUSD", -1, 1.0, sl=2010.0, tp=1990.0)
    assert res["retcode"] == RETCODE_DONE
    assert len(fake.order_send_calls) == 2
    assert fake.order_send_calls[0]["price"] == fake.bid  # Sell -> Bid
    # Nach 10015 wird neu quotiert (symbol_info_tick erneut aufgerufen)
    assert fake.tick_calls >= 2


def test_retry_10016_snaps_stops(fake):
    conn = _live_connector(fake)
    fake.retcode_script = [RETCODE_INVALID_STOPS, RETCODE_DONE]
    res = conn.send_market("XAUUSD", +1, 1.0, sl=2000.05, tp=2000.15)  # zu nah
    assert res["retcode"] == RETCODE_DONE
    first, second = fake.order_send_calls
    # stops_level=10 Punkte + 1 -> Mindestabstand 0.11 um Ask 2000.10
    assert second["sl"] <= first["price"] - 0.11 + 1e-9
    assert second["tp"] >= first["price"] + 0.11 - 1e-9
    assert second["sl"] != first["sl"]


def test_retry_gives_up_after_max_retries(fake):
    conn = _live_connector(fake)
    conn.max_retries = 3
    fake.default_retcode = RETCODE_INVALID_PRICE
    res = conn.send_market("XAUUSD", +1, 1.0, sl=1990.0, tp=2010.0)
    assert res["retcode"] == RETCODE_INVALID_PRICE
    assert len(fake.order_send_calls) == 3  # max. 3 Versuche


def test_non_retryable_retcode_no_retry(fake):
    conn = _live_connector(fake)
    fake.default_retcode = 10006  # TRADE_RETCODE_REJECT
    res = conn.send_market("XAUUSD", +1, 1.0, sl=1990.0, tp=2010.0)
    assert res["retcode"] == 10006
    assert len(fake.order_send_calls) == 1


def test_backoff_is_exponential(fake, monkeypatch):
    conn = _live_connector(fake)
    conn.backoff_base = 0.5
    sleeps = []
    monkeypatch.setattr("core.connector.time.sleep", sleeps.append)
    fake.retcode_script = [RETCODE_INVALID_PRICE, RETCODE_INVALID_PRICE, RETCODE_DONE]
    conn.send_market("XAUUSD", +1, 1.0, sl=1990.0, tp=2010.0)
    assert sleeps == [0.5, 1.0]  # 0.5 * 2**attempt


def test_send_limit_uses_pending_action(fake):
    conn = _live_connector(fake)
    res = conn.send_limit("XAUUSD", +1, 0.5, limit_price=1995.0,
                          sl=1990.0, tp=2005.0)
    assert res["retcode"] == RETCODE_DONE
    req = fake.order_send_calls[0]
    assert req["action"] == FakeMT5.TRADE_ACTION_PENDING
    assert req["type"] == FakeMT5.ORDER_TYPE_BUY_LIMIT
    assert req["price"] == 1995.0


# ---------------------------------------------------------------------------
# Sizing-Validierung (SPEC §4.10: order_calc_profit-Aequivalent)
# ---------------------------------------------------------------------------
def test_normalize_volume_rounds_and_clamps(connector):
    assert connector.normalize_volume("XAUUSD", 1.234) == 1.23     # step 0.01
    assert connector.normalize_volume("XAUUSD", 0.001) == 0.01     # min
    assert connector.normalize_volume("XAUUSD", 999.0) == 50.0     # max (fake)


def test_validate_sizing_uses_order_calc_profit(connector):
    # Long, Entry 2000, SL 1990 -> 10 USD Abstand * 100 (contract) * 1 lot = 1000
    risk = connector.validate_sizing("XAUUSD", +1, 1.0, 2000.0, 1990.0)
    assert risk == pytest.approx(1000.0)
    risk_short = connector.validate_sizing("XAUUSD", -1, 2.0, 2000.0, 2010.0)
    assert risk_short == pytest.approx(2000.0)


def test_symbol_spec_keys(connector):
    spec = connector.symbol_spec("XAUUSD")
    for key in ("point", "tick_size", "tick_value", "volume_step",
                "volume_min", "volume_max", "stops_level"):
        assert key in spec, key
    assert spec["point"] == 0.01
    assert spec["stops_level"] == 10


# ---------------------------------------------------------------------------
# Dry-Run-Verhalten (Klassen-Default True — Orders werden NUR geloggt)
# ---------------------------------------------------------------------------
def test_dry_run_is_class_default():
    assert MT5Connector.dry_run is True
    assert MT5Connector().dry_run is True


def test_dry_run_send_market_logs_only(fake, caplog):
    conn = MT5Connector(client=fake)  # dry_run bleibt True
    with caplog.at_level(logging.INFO):
        res = conn.send_market("XAUUSD", +1, 1.0, sl=1990.0, tp=2010.0)
    assert res["dry_run"] is True
    assert res["retcode"] == RETCODE_DONE
    assert fake.order_send_calls == []           # NICHTS zum Server
    assert any("DRY-RUN" in r.message for r in caplog.records)


def test_dry_run_modify_and_close_log_only(fake):
    conn = MT5Connector(client=fake)
    assert conn.modify_sltp(123, sl=1.0, tp=2.0) is True
    assert conn.close(123) is True
    assert fake.order_send_calls == []


# ---------------------------------------------------------------------------
# Health / Account / Positions
# ---------------------------------------------------------------------------
def test_health_true_and_false(connector, fake, monkeypatch):
    assert connector.health() is True

    def boom():
        raise RuntimeError("rpyc connection lost")

    monkeypatch.setattr(fake, "terminal_info", boom)
    monkeypatch.setattr(fake, "account_info", boom)
    assert connector.health() is False


def test_account_info_subset(connector):
    info = connector.account_info()
    assert info["balance"] == 100_000.0
    assert info["currency"] == "USD"
    assert info["trade_mode"] == FakeMT5.ACCOUNT_TRADE_MODE_DEMO


# ---------------------------------------------------------------------------
# Kontotyp-Erkennung (SICHERHEITSSTOPP fuer core.live: kein Echtgeld ohne Opt-in)
# ---------------------------------------------------------------------------
def test_is_demo_account_true_on_demo(connector):
    assert connector.is_demo_account() is True


def test_is_demo_account_false_on_real(fake):
    fake.trade_mode = FakeMT5.ACCOUNT_TRADE_MODE_REAL
    conn = MT5Connector(client=fake, dry_run=True)
    assert conn.is_demo_account() is False


def test_is_demo_account_none_when_trade_mode_missing(fake, monkeypatch):
    def no_trade_mode():
        return SimpleNamespace(login=12345, balance=100_000.0, equity=100_100.0,
                               currency="USD", server="Fake-Server")

    monkeypatch.setattr(fake, "account_info", no_trade_mode)
    conn = MT5Connector(client=fake, dry_run=True)
    assert conn.is_demo_account() is None


# ---------------------------------------------------------------------------
# Deal-Historie (Journal/Dashboard, nur Lesezugriff)
# ---------------------------------------------------------------------------
def test_history_deals_range_returns_dicts(connector, fake):
    fake._deals = [SimpleNamespace(ticket=1, magic=20260904, profit=10.0, entry=1)]
    deals = connector.history_deals_range(datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert deals == [{"ticket": 1, "magic": 20260904, "profit": 10.0, "entry": 1}]


def test_history_deals_for_position_filters_out_entries(connector, fake):
    fake._deals = [
        SimpleNamespace(ticket=1, entry=0, profit=0.0, commission=-1.0, swap=0.0,
                        price=150.0, reason=0),
        SimpleNamespace(ticket=2, entry=1, profit=650.0, commission=0.0, swap=0.0,
                        price=151.95, reason=4),
    ]
    deals = connector.history_deals_for_position(4711)
    assert len(deals) == 2
    exit_deals = [d for d in deals if d["entry"] == 1]
    assert exit_deals[0]["price"] == 151.95


def test_close_uses_opposite_market_order(fake):
    conn = _live_connector(fake)
    fake._positions = [SimpleNamespace(ticket=42, symbol="XAUUSD",
                                       type=FakeMT5.ORDER_TYPE_BUY, volume=1.5)]
    assert conn.close(42) is True
    req = fake.order_send_calls[0]
    assert req["type"] == FakeMT5.ORDER_TYPE_SELL   # Gegenrichtung
    assert req["volume"] == 1.5


# ---------------------------------------------------------------------------
# Gap-Audit + load_ohlcv (Daten-Kontrakt SPEC §3)
# ---------------------------------------------------------------------------
def _m5_df(times, price=2000.0):
    n = len(times)
    return pd.DataFrame({
        "open": [price] * n, "high": [price + 1] * n,
        "low": [price - 1] * n, "close": [price + 0.5] * n,
        "tick_volume": [100.0] * n,
    }, index=pd.DatetimeIndex(times, tz=UTC))


def test_audit_gaps_detects_weekday_gap_only():
    # Mo 2024-01-08 00:00 UTC, durchgehend M5 bis Fr 12.01. 20:55
    idx = pd.date_range("2024-01-08 00:00", "2024-01-12 20:55", freq="5min", tz=UTC)
    # Werktags-Luecke: Mi 10.01. 12:00-13:00 (12 Bars) entfernen
    hole = pd.date_range("2024-01-10 12:00", "2024-01-10 12:55", freq="5min", tz=UTC)
    idx = idx.difference(hole)
    # Naechster Block: So 14.01. 21:00 - Mo 15.01. 01:00 (uebers Wochenende)
    idx2 = pd.date_range("2024-01-14 21:00", "2024-01-15 01:00", freq="5min", tz=UTC)
    df = _m5_df(idx.append(idx2))
    report = audit_gaps(df, "M5")
    assert not report.ok
    assert report.n_missing == 12                    # nur Werktags-Luecke
    first, last, n = report.gaps[0]
    assert first == pd.Timestamp("2024-01-10 12:00", tz=UTC)
    assert n == 12
    # Wochenend-Gap (Fr 21:00 -> So 21:00) wird NICHT gemeldet
    assert all(g[0].weekday() != 5 for g in report.gaps)


def test_audit_gaps_ok_on_continuous_data():
    idx = pd.date_range("2024-01-08 00:00", "2024-01-09 00:00", freq="5min", tz=UTC)
    report = audit_gaps(_m5_df(idx), "M5")
    assert report.ok
    assert "OK" in report.summary()


def test_load_ohlcv_from_cache(tmp_path):
    idx = pd.date_range("2024-01-08 00:00", periods=20, freq="h", tz=UTC)
    _m5_df(idx).to_csv(tmp_path / "XAUUSD_H1.csv", index_label="time")
    df = load_ohlcv("XAUUSD", "H1", datetime(2024, 1, 8, 5), datetime(2024, 1, 8, 10),
                    source="cache", data_dir=tmp_path)
    assert len(df) == 5
    assert str(df.index.tz) == "UTC"
    assert list(df.columns) == ["open", "high", "low", "close", "tick_volume"]


def test_load_ohlcv_prefers_parquet(tmp_path):
    """Parquet ist das bevorzugte Cache-Format (SPEC §3), CSV nur Fallback."""
    idx = pd.date_range("2024-01-08 00:00", periods=20, freq="h", tz=UTC)
    df_pq = _m5_df(idx)
    df_pq.index.name = "time"
    df_pq.to_parquet(tmp_path / "XAUUSD_H1.parquet", index=True)
    # CSV mit anderem Inhalt daneben: Parquet muss gewinnen
    _m5_df(idx, price=999.0).to_csv(tmp_path / "XAUUSD_H1.csv", index_label="time")
    df = load_ohlcv("XAUUSD", "H1", datetime(2024, 1, 8, 5), datetime(2024, 1, 8, 10),
                    source="cache", data_dir=tmp_path)
    assert len(df) == 5
    assert str(df.index.tz) == "UTC"
    assert float(df["close"].iloc[0]) > 999.0  # Inhalt aus Parquet, nicht CSV


def test_validate_ohlcv_rejects_naive_index():
    df = _m5_df(pd.date_range("2024-01-08", periods=3, freq="5min"))
    df.index = df.index.tz_localize(None)
    with pytest.raises(ValueError, match="tz-aware"):
        validate_ohlcv(df)
