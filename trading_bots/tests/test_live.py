"""tests/test_live.py — LiveRunner: Sicherheitsstopp (Echtgeld), Journal-Wiring,
Traderbook-Diagnose (explain()-Logging). KEIN echtes MT5/RPyC noetig —
FakeMT5 wie in test_connector.py, per MT5Connector(client=fake) injiziert."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
import yaml

from core.connector import MT5Connector
from core.live import LiveRunner


@pytest.fixture(autouse=True)
def _cleanup_narrative_handlers():
    """Jeder Test haengt via LiveRunner.__init__ einen taeglich rotierenden
    File-Handler an den geteilten 'core.live'-Logger (eigener tmp_path je
    Test -> kein Dedup). Ohne Aufraeumen sammeln sich ueber die Testsuite
    hinweg offene Dateihandles an."""
    yield
    logger = logging.getLogger("core.live")
    for h in list(logger.handlers):
        if getattr(h, "_narrative_path", None):
            logger.removeHandler(h)
            h.close()


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(self, trade_mode=0):
        self.trade_mode = trade_mode
        self.bid, self.ask = 150.60, 150.62
        self._positions: list[SimpleNamespace] = []
        self._deals: list[SimpleNamespace] = []
        self.order_send_calls: list[dict] = []

    def initialize(self):
        return True

    def shutdown(self):
        return True

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        return SimpleNamespace(login=555, balance=100_000.0, equity=100_000.0,
                               margin=0.0, margin_free=100_000.0, margin_level=0.0,
                               currency="USD", leverage=100, profit=0.0,
                               server="Fake-Server", name="Demo",
                               trade_mode=self.trade_mode)

    def terminal_info(self):
        return SimpleNamespace(connected=True)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=0, ask=self.ask, bid=self.bid, time_msc=0)

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.001, digits=3, trade_tick_size=0.001,
                               trade_tick_value=100.0, volume_step=0.01,
                               volume_min=0.01, volume_max=50.0,
                               trade_stops_level=10, trade_contract_size=100_000.0)

    def positions_get(self, **kwargs):
        if "symbol" in kwargs:
            return [p for p in self._positions if p.symbol == kwargs["symbol"]]
        return list(self._positions)

    def order_send(self, request):
        self.order_send_calls.append(dict(request))
        return SimpleNamespace(retcode=10009, order=4711, deal=4712,
                               price=request.get("price", 0.0), comment="done")

    def history_select(self, date_from, date_to):
        return True

    def history_deals_get(self, *args, **kwargs):
        return list(self._deals)


def _write_config(tmp_path, **overrides) -> str:
    cfg = {
        "strategy": "s4_london_breakout",
        "symbols": ["USDJPY"],
        "timeframes": ["H1", "H4", "D1"],
        "risk": {"risk_per_trade_pct": 0.5, "max_concurrent": 1, "prop_profile": "none",
                "eod_flat": False, "friday_flat": False},
        "meta_layer": {"news_filter": "off"},
        "params": {"symbol": "USDJPY", "risk_pct": 0.005},
        "live": {"host": "localhost", "port": 8001, "magic": 20260904,
                "logs_dir": str(tmp_path / "logs"), "allow_real_account": False},
    }
    cfg.update(overrides)
    path = tmp_path / "s4_test.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(path)


def _runner_with_fake(tmp_path, fake) -> LiveRunner:
    runner = LiveRunner(_write_config(tmp_path), dry_run=False)
    runner.connector = MT5Connector(client=fake, dry_run=False, magic=runner.magic)
    return runner


# ---------------------------------------------------------------------------
# Sicherheitsstopp: kein Echtgeld ohne explizites Opt-in
# ---------------------------------------------------------------------------
def test_enforce_account_safety_stops_on_real_account(tmp_path):
    fake = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL)
    runner = _runner_with_fake(tmp_path, fake)
    with pytest.raises(SystemExit, match="ECHTGELDKONTO"):
        runner._enforce_account_safety()


def test_enforce_account_safety_allows_demo(tmp_path):
    fake = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_DEMO)
    runner = _runner_with_fake(tmp_path, fake)
    runner._enforce_account_safety()  # darf NICHT werfen


def test_enforce_account_safety_allow_real_account_flag(tmp_path):
    fake = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL)
    runner = _runner_with_fake(tmp_path, fake)
    runner.allow_real_account = True
    runner._enforce_account_safety()  # explizit erlaubt -> kein SystemExit


def test_enforce_account_safety_warns_when_unknown(tmp_path, caplog):
    fake = FakeMT5()

    def no_mode():
        return SimpleNamespace(login=555, balance=100_000.0, server="Fake-Server")

    fake.account_info = no_mode
    runner = _runner_with_fake(tmp_path, fake)
    with caplog.at_level(logging.WARNING):
        runner._enforce_account_safety()  # darf NICHT werfen, nur warnen
    assert any("nicht ermittelbar" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Journal-Wiring: erfolgreiche Order -> OPEN-Zeile; Fill -> CLOSE-Zeile
# ---------------------------------------------------------------------------
def test_handle_signal_writes_journal_open(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    from strategies.base import Signal
    import pandas as pd

    signal = Signal(time=pd.Timestamp("2024-03-13 07:00", tz="UTC"), symbol="USDJPY",
                    direction=1, entry_type="market", entry_price=None,
                    stop_loss=150.00, take_profit=151.95, risk_pct=0.005,
                    meta={"range_high": 150.50, "range_low": 150.00,
                          "range_pips": 50.0, "tp_r": 2.0, "entry_mode": "close"})
    runner._handle_signal("USDJPY", signal)
    from core.journal import read_journal
    rows = read_journal(runner.journal.path)
    assert len(rows) == 1
    assert rows[0]["ereignis"] == "OPEN"
    assert rows[0]["symbol"] == "USDJPY"
    assert rows[0]["richtung"] == "LONG"
    assert "London-Breakout" in rows[0]["grund"]
    assert len(fake.order_send_calls) == 1


def test_journal_close_on_position_disappearance(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    fake._deals = [
        SimpleNamespace(ticket=1, entry=0, profit=0.0, commission=-1.0, swap=0.0,
                       price=150.65, reason=0),
        SimpleNamespace(ticket=2, entry=1, profit=650.0, commission=0.0, swap=0.0,
                       price=151.95, reason=4),
    ]
    ok = runner._journal_close(4711, "USDJPY")
    assert ok is True
    from core.journal import read_journal
    rows = read_journal(runner.journal.path)
    assert rows[0]["ereignis"] == "CLOSE"
    assert rows[0]["gewinn"] == "649.00"  # 650 brutto - 1.00 Kommission
    assert rows[0]["grund"] == "Take-Profit getroffen"


def test_journal_close_returns_false_without_exit_deal(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    fake._deals = []  # Broker-Historie noch nicht befuellt
    assert runner._journal_close(4711, "USDJPY") is False


# ---------------------------------------------------------------------------
# Traderbook-Diagnose: explain() -> "KEIN EINSTIEG"-Log
# ---------------------------------------------------------------------------
def test_explain_blocked_reason_is_logged(tmp_path, caplog):
    import pandas as pd
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    idx = pd.date_range("2024-03-13 00:00", periods=10, freq="h", tz="UTC")
    df = pd.DataFrame({"open": 150.0, "high": 150.2, "low": 149.9, "close": 150.0,
                       "tick_volume": 100.0}, index=idx)
    bars = {"H1": df}
    i = 9  # 09:00 UTC -> im Entry-Fenster, aber Close bleibt in der Range
    with caplog.at_level(logging.INFO):
        sig = runner.strategy.on_bar(bars, i)
        assert sig is None
        info = runner.strategy.explain(bars, i)
        from core.live import _format_explain
        line = _format_explain("USDJPY", info)
        logging.getLogger("core.live").info("KEIN EINSTIEG: %s", line)
    assert any("KEIN EINSTIEG" in r.message for r in caplog.records)
    assert any("inside_range" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Live-Trailing-Stop: Chandelier + Move-to-Trail (spiegelt core/backtester.py)
# ---------------------------------------------------------------------------
def test_handle_signal_with_trail_meta_stores_trail_state(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    from strategies.base import Signal
    import pandas as pd

    signal = Signal(time=pd.Timestamp("2024-03-13 07:00", tz="UTC"), symbol="USDJPY",
                    direction=1, entry_type="market", entry_price=None,
                    stop_loss=148.0, take_profit=154.0, risk_pct=0.005,
                    meta={"trail_atr_mult": 3.0, "trail_atr_len": 14})
    runner._handle_signal("USDJPY", signal)
    assert 4711 in runner._trail_state
    state = runner._trail_state[4711]
    assert state["trail_atr_mult"] == 3.0
    assert state["direction"] == 1
    assert state["tp_locked"] is False


def test_handle_signal_without_trail_meta_no_trail_state(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    from strategies.base import Signal
    import pandas as pd

    signal = Signal(time=pd.Timestamp("2024-03-13 07:00", tz="UTC"), symbol="USDJPY",
                    direction=1, entry_type="market", entry_price=None,
                    stop_loss=148.0, take_profit=151.0, risk_pct=0.005, meta={})
    runner._handle_signal("USDJPY", signal)
    assert runner._trail_state == {}


def _mk_bars_df(highs_lows):
    """[(o,h,l,c), ...] -> DataFrame mit H1-Index, fuers Trail-ATR."""
    import numpy as np
    import pandas as pd
    idx = pd.date_range("2024-03-13 00:00", periods=len(highs_lows), freq="h", tz="UTC")
    arr = np.asarray(highs_lows, dtype=float)
    return pd.DataFrame({"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2],
                         "close": arr[:, 3], "tick_volume": 100.0}, index=idx)


def test_update_trailing_stops_locks_tp_then_ratchets(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    fake._positions = [SimpleNamespace(
        ticket=4711, symbol="USDJPY", magic=runner.magic, type=0, volume=0.5,
        price_open=150.0, sl=148.0, tp=154.0, time=0,
    )]
    runner._trail_state[4711] = {
        "trail_atr_mult": 1.0, "trail_atr_len": 2, "direction": 1,
        "extreme": 150.0, "tp_locked": False,
    }
    # 20 flache Bars (TR=0.2 konstant -> ATR2 ~0.2), letzte Bar beruehrt TP
    # (154.0) knapp -> Lock erwartet: SL auf 154.0, TP geloescht. Der ATR-
    # Ausschlag durch den TP-Touch selbst bleibt (bewusst) klein genug, dass
    # der anschliessende Ratchet-Check NICHT sofort erneut nachzieht (sonst
    # waeren es 2 statt 1 modify_sltp-Aufrufe in dieser Poll-Runde).
    flat = [(150, 150.1, 149.9, 150)] * 19
    bars = _mk_bars_df(flat + [(150, 154.05, 149.9, 154.0)])
    runner._update_trailing_stops("USDJPY", bars)

    sltp_calls = [c for c in fake.order_send_calls if c.get("position") == 4711]
    assert len(sltp_calls) == 1
    assert sltp_calls[0]["sl"] == pytest.approx(154.0)
    assert sltp_calls[0]["tp"] == 0.0  # TP geloescht (connector: 0.0 = kein TP)
    assert runner._trail_state[4711]["tp_locked"] is True


def test_update_trailing_stops_never_loosens(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    fake._positions = [SimpleNamespace(
        ticket=4711, symbol="USDJPY", magic=runner.magic, type=0, volume=0.5,
        price_open=150.0, sl=153.0, tp=None, time=0,
    )]
    runner._trail_state[4711] = {
        "trail_atr_mult": 1.0, "trail_atr_len": 2, "direction": 1,
        "extreme": 155.0, "tp_locked": True,  # bereits im Trail-Modus, SL schon bei 153
    }
    # Ruecklaeufige Bar (Extreme faellt NICHT unter 155 zurueck, ATR bleibt klein)
    # -> Kandidat waere <= aktueller SL -> KEIN modify_sltp-Aufruf (Ratchet-only).
    flat = [(150, 150.1, 149.9, 150)] * 19
    bars = _mk_bars_df(flat + [(154, 154.1, 153.9, 154)])
    runner._update_trailing_stops("USDJPY", bars)
    assert not [c for c in fake.order_send_calls if c.get("position") == 4711]
    assert runner._trail_state[4711]["extreme"] == 155.0  # unveraendert (154.1 < 155)


def test_update_trailing_stops_drops_closed_position(tmp_path):
    fake = FakeMT5()
    runner = _runner_with_fake(tmp_path, fake)
    fake._positions = []  # Position bereits geschlossen (SL/TP/Trail griff serverseitig)
    runner._trail_state[4711] = {
        "trail_atr_mult": 1.0, "trail_atr_len": 2, "direction": 1,
        "extreme": 150.0, "tp_locked": False,
    }
    bars = _mk_bars_df([(150, 150.1, 149.9, 150)] * 5)
    runner._update_trailing_stops("USDJPY", bars)
    assert runner._trail_state == {}
