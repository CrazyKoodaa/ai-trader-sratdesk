"""tests/test_backtester.py — Event-Engine, Kostenmodell, Kausalitaet (SPEC §4.2).

Synthetische Daten inline (numpy seed), KEIN fixtures.py-Import (parallele
Entwicklung). Enthaelt das deterministische Mini-Szenario mit handkalkuliertem
PF, den Kosten-Stress-Test und den Lookahead-Test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from core.backtester import BacktestConfig, Backtester, CostModel
from core.risk import RiskConfig


# ---------------------------------------------------------------------------
# Helfer: Signal-Dataclass (§4.1-kompatibel) + DataFrame-Builder
# ---------------------------------------------------------------------------
@dataclass
class Signal:
    time: pd.Timestamp
    symbol: str
    direction: int
    entry_type: str
    entry_price: float | None
    stop_loss: float
    take_profit: float | None
    risk_pct: float
    meta: dict = field(default_factory=dict)
    expires_bars: int = 0


def make_df(bars, start="2024-01-02 09:00", freq="5min"):
    """bars: list[(o, h, l, c)] -> OHLCV-DataFrame, tz-aware UTC."""
    idx = pd.date_range(start, periods=len(bars), freq=freq, tz="UTC")
    arr = np.asarray(bars, dtype=float)
    return pd.DataFrame(
        {"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2], "close": arr[:, 3],
         "tick_volume": np.full(len(bars), 100.0)},
        index=idx,
    )


def relaxed_risk() -> RiskConfig:
    return RiskConfig(risk_per_trade_pct=1.0, daily_loss_halt_pct=0.0,
                      eod_flat=False, friday_flat=False)


def base_config(costs: CostModel, **kw) -> BacktestConfig:
    defaults = dict(
        symbol="TEST", timeframes=["M5"],
        start=datetime(2024, 1, 2, tzinfo=timezone.utc),
        end=datetime(2024, 1, 3, tzinfo=timezone.utc),
        costs=costs, risk=relaxed_risk(),
        point_value=1.0, initial_balance=10_000.0,
        volume_step=1.0, volume_min=1.0, volume_max=100.0,
    )
    defaults.update(kw)
    return BacktestConfig(**defaults)


# ---------------------------------------------------------------------------
# Deterministisches Mini-Szenario (handkalkuliert)
# ---------------------------------------------------------------------------
# Balance 10k, Risiko 1 % = 100, step 1.0, point_value 1, keine Kosten.
# T1: Long entry 100 (Open i2), SL 90, TP 120 -> TP in i3 -> lots=10, +200
# T2: Long entry 120 (Open i4), SL 110, TP 140 -> SL in i4 -> lots=10, -100
# T3: Long entry 110 (Open i5), SL 100, TP 130 -> TP in i6 -> lots=10, +200
# => PF = 400/100 = 4.0 exakt, n=3, WR=2/3, avgR=(2-1+2)/3=1.0
MINI_BARS = [
    (100, 100.5, 99.5, 100),   # i0
    (100, 100.5, 99.5, 100),   # i1  -> Signal 1
    (100, 119.0, 95.0, 110),   # i2  Entry T1 @100, kein Touch
    (110, 121.0, 105.0, 118),  # i3  TP 120 -> Exit T1; Signal 2
    (120, 122.0, 109.0, 115),  # i4  Entry T2 @120, SL 110 -> Exit; Signal 3
    (110, 125.0, 108.0, 120),  # i5  Entry T3 @110
    (120, 131.0, 118.0, 130),  # i6  TP 130 -> Exit T3
    (130, 130.5, 129.5, 130),  # i7
]
MINI_SCRIPT = {1: (90.0, 120.0), 3: (110.0, 140.0), 4: (100.0, 130.0)}


class MiniStrategy:
    name = "mini"
    required_timeframes = ["M5"]

    def __init__(self, params=None):
        self.params = params or {}

    def on_bar(self, bars, i):
        if i in MINI_SCRIPT:
            sl, tp = MINI_SCRIPT[i]
            return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                          entry_type="market", entry_price=None,
                          stop_loss=sl, take_profit=tp, risk_pct=1.0, meta={})
        return None


class TestHandCalculatedScenario:
    def test_pf_exact(self):
        data = {"M5": make_df(MINI_BARS)}
        cfg = base_config(CostModel(spread_points=0.0))
        res = Backtester(MiniStrategy(), cfg, data).run()
        t = res.trades
        assert len(t) == 3
        assert t["pnl"].tolist() == pytest.approx([200.0, -100.0, 200.0])
        assert res.metrics["pf"] == pytest.approx(4.0)
        assert res.metrics["n"] == 3
        assert res.metrics["winrate"] == pytest.approx(2 / 3)
        assert res.metrics["avg_r"] == pytest.approx(1.0)
        assert res.metrics["total_pnl"] == pytest.approx(300.0)

    def test_trade_columns_contract(self):
        data = {"M5": make_df(MINI_BARS)}
        cfg = base_config(CostModel(spread_points=0.0))
        res = Backtester(MiniStrategy(), cfg, data).run()
        expected = {"entry_time", "exit_time", "direction", "entry", "exit",
                    "sl", "tp", "lots", "pnl", "r_multiple", "meta"}
        assert expected.issubset(set(res.trades.columns))
        assert "balance" in res.equity_curve and "equity" in res.equity_curve

    def test_deterministic_rerun(self):
        data = {"M5": make_df(MINI_BARS)}
        cfg = base_config(CostModel(spread_points=1.0))
        r1 = Backtester(MiniStrategy(), cfg, data).run()
        r2 = Backtester(MiniStrategy(), cfg, data).run()
        pd.testing.assert_frame_equal(r1.trades, r2.trades)


# ---------------------------------------------------------------------------
# Kosten-Stress: 1x/2x/3x Slippage-Multiplikator -> PF monoton fallend
# ---------------------------------------------------------------------------
class TestCostStress:
    def test_pf_decreases_with_cost_multiplier(self):
        data = {"M5": make_df(MINI_BARS)}
        pfs = []
        for mult in (1.0, 2.0, 3.0):
            cfg = base_config(CostModel(spread_points=2.0, slippage_multiplier=mult))
            res = Backtester(MiniStrategy(), cfg, data).run()
            pfs.append(res.metrics["pf"])
        assert pfs[0] > pfs[1] > pfs[2]
        assert all(np.isfinite(pfs))

    def test_commission_and_spread_reduce_pnl(self):
        data = {"M5": make_df(MINI_BARS)}
        free = Backtester(MiniStrategy(), base_config(CostModel(0.0)), data).run()
        costly = Backtester(
            MiniStrategy(),
            base_config(CostModel(spread_points=2.0, commission_per_lot_rt=7.0)),
            data).run()
        assert costly.metrics["total_pnl"] < free.metrics["total_pnl"]


# ---------------------------------------------------------------------------
# Einheiten: CostModel.*_points sind MT5-Punkte (x BacktestConfig.point)
# ---------------------------------------------------------------------------
class TestSpreadPointConversion:
    def test_spread_points_scaled_by_point(self):
        """spread_points=20 bei point=0.01 -> halber Spread = 0.10 Preiseinheiten
        beim Entry (Market) und beim Limit-/TP-Exit — NICHT 10.0 (Regression:
        Punkte wurden frueher direkt als Preiseinheiten verrechnet)."""
        data = {"M5": make_df(MINI_BARS)}
        cfg = base_config(CostModel(spread_points=20.0), point=0.01)
        res = Backtester(MiniStrategy(), cfg, data).run()
        t1 = res.trades.iloc[0]  # Long: Entry Open i2=100, TP-Exit 120
        assert t1["entry"] == pytest.approx(100.10)
        assert t1["exit"] == pytest.approx(119.90)

    def test_point_default_preserves_price_units(self):
        """Default point=1.0 -> Points = Preiseinheiten (Legacy-Verhalten)."""
        data = {"M5": make_df(MINI_BARS)}
        cfg = base_config(CostModel(spread_points=2.0))
        res = Backtester(MiniStrategy(), cfg, data).run()
        assert res.trades["entry"].iloc[0] == pytest.approx(101.0)


# ---------------------------------------------------------------------------
# Lookahead / Kausalitaet
# ---------------------------------------------------------------------------
class EveryBarStrategy:
    """Signalisiert auf jeder Bar (wechselnde Richtung), nutzt close der
    aktuellen (geschlossenen) Bar — Entry darf fruehestens naechste Bar sein."""

    name = "everybar"
    required_timeframes = ["M5", "H1"]

    def __init__(self, params=None):
        self.params = params or {}
        self.alignment_violations = []

    def on_bar(self, bars, i):
        m5 = bars["M5"]
        h1 = bars["H1"]
        # Alignment-Check: letzte H1-Bar muss zum M5-Bar-Close geschlossen sein
        if len(h1):
            h1_last_close = h1.index[-1] + pd.Timedelta(hours=1)
            m5_close = m5.index[-1] + pd.Timedelta(minutes=5)
            if h1_last_close > m5_close:
                self.alignment_violations.append(i)
        if i < 5 or len(m5) < 2:
            return None
        px = m5["close"].iloc[-1]
        direction = 1 if i % 2 == 0 else -1
        return Signal(time=m5.index[-1], symbol="TEST", direction=direction,
                      entry_type="market", entry_price=None,
                      stop_loss=px - direction * 2.0,
                      take_profit=px + direction * 2.0,
                      risk_pct=0.5, meta={"signal_bar": m5.index[-1]})


def random_walk_df(n=400, seed=7, freq="5min", start="2024-01-02 00:00"):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.8, n)
    close = 100 + np.cumsum(rets)
    open_ = np.roll(close, 1)
    open_[0] = 100.0
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.4, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.4, n))
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": rng.uniform(50, 150, n)}, index=idx)


class TestLookahead:
    def test_entry_never_before_signal_bar_plus_1(self):
        m5 = random_walk_df()
        h1 = (m5.resample("1h")
              .agg({"open": "first", "high": "max", "low": "min",
                    "close": "last", "tick_volume": "sum"})
              .dropna())
        strat = EveryBarStrategy()
        cfg = base_config(CostModel(spread_points=1.0), timeframes=["M5", "H1"],
                          end=datetime(2024, 1, 5, tzinfo=timezone.utc))
        res = Backtester(strat, cfg, {"M5": m5, "H1": h1}).run()
        assert len(res.trades) > 10
        for _, tr in res.trades.iterrows():
            sig_time = tr["meta"]["signal_bar"]
            # Entry fruehestens Open der Bar NACH der Signal-Bar (M5 = 5 min)
            assert tr["entry_time"] >= sig_time + pd.Timedelta(minutes=5)
            assert tr["exit_time"] > tr["entry_time"]
        # Keine HTF-Alignment-Verletzung (nur geschlossene Bars sichtbar)
        assert strat.alignment_violations == []

    def test_signal_in_future_rejected(self):
        class BadStrategy(MiniStrategy):
            def on_bar(self, bars, i):
                if i == 1:
                    return Signal(time=bars["M5"].index[i] + pd.Timedelta(minutes=5),
                                  symbol="TEST", direction=1, entry_type="market",
                                  entry_price=None, stop_loss=90, take_profit=120,
                                  risk_pct=1.0, meta={})
                return None

        data = {"M5": make_df(MINI_BARS)}
        cfg = base_config(CostModel(0.0))
        with pytest.raises(ValueError, match="Lookahead"):
            Backtester(BadStrategy(), cfg, data).run()


# ---------------------------------------------------------------------------
# Limit-Orders: konservativ bei Limit+SL-Touch in einer Bar
# ---------------------------------------------------------------------------
class LimitStrategy:
    name = "limit"
    required_timeframes = ["M5"]

    def __init__(self, params=None):
        self.params = params or {}

    def on_bar(self, bars, i):
        if i == 1:
            return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                          entry_type="limit", entry_price=95.0,
                          stop_loss=90.0, take_profit=110.0,
                          risk_pct=1.0, meta={}, expires_bars=3)
        return None


class TestLimitOrders:
    PRE = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)]

    def test_limit_and_sl_same_bar_discards_order(self):
        # i2: low 89 beruehrt Limit 95 UND SL 90 -> konservativ: kein Fill
        # (nur im stop_first-Fallback OHNE feinere Daten so — s. Klasse
        # TestLimitOrdersFineIntrabar fuer die Aufloesung mit m1/m5)
        bars = self.PRE + [(96, 97, 89, 96), (96, 96.5, 95.5, 96)]
        res = Backtester(LimitStrategy(), base_config(CostModel(0.0)),
                         {"M5": make_df(bars)}).run()
        assert len(res.trades) == 0

    def test_limit_filled_on_range_touch(self):
        # i2: low 94.5 beruehrt nur Limit -> Fill @95; i3: TP 110
        bars = self.PRE + [(96, 97, 94.5, 96), (96, 111, 95, 110)]
        res = Backtester(LimitStrategy(), base_config(CostModel(0.0)),
                         {"M5": make_df(bars)}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["entry"] == pytest.approx(95.0)
        assert tr["exit"] == pytest.approx(110.0)
        assert tr["pnl"] > 0

    def test_limit_expiry(self):
        # Limit wird nie beruehrt; nach 3 Bars expired
        bars = self.PRE + [(100, 100.4, 99.6, 100)] * 6
        res = Backtester(LimitStrategy(), base_config(CostModel(0.0)),
                         {"M5": make_df(bars)}).run()
        assert len(res.trades) == 0


# ---------------------------------------------------------------------------
# Limit-Orders: Fine-Intrabar-Aufloesung (m1/m5) statt Kollision-Discard
# ---------------------------------------------------------------------------
class H1LimitStrategy:
    """Wie LimitStrategy, aber Primary-TF H1 (Signal auf Bar i1)."""
    name = "limit_h1"
    required_timeframes = ["H1"]

    def __init__(self, params=None):
        self.params = params or {}

    def on_bar(self, bars, i):
        if i == 1:
            return Signal(time=bars["H1"].index[i], symbol="TEST", direction=1,
                          entry_type="limit", entry_price=95.0,
                          stop_loss=90.0, take_profit=110.0,
                          risk_pct=1.0, meta={}, expires_bars=3)
        return None


class TestLimitOrdersFineIntrabar:
    """H1-Primary + M5-Fine: dieselbe Grob-Bar-Kollision wie oben (Limit 95 UND
    SL 90 in derselben H1-Bar beruehrt) wird jetzt ueber M5 chronologisch
    aufgeloest, statt verworfen zu werden — das war der S4/XAUUSD-Befund
    (enge SL relativ zur H1-Bar-Volatilitaet loeschte reihenweise Verlierer)."""
    H1_PRE = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)]
    H1_COLLISION = (96, 97, 89, 96)  # identisch zur stop_first-Kollisionsbar oben

    def _h1_bars(self):
        return make_df(self.H1_PRE + [self.H1_COLLISION], freq="1h")

    def test_m5_resolves_fill_then_sl_as_loss(self):
        # M5 09:00-10:00 (i0/i1): keine Beruehrung, irrelevant. 11:00-12:00 (i2):
        # sub1 fuellt Limit 95, sub3 beruehrt SL 90 ERST DANACH -> Verlust, kein Discard.
        m5 = make_df([
            (96, 96.5, 95.5, 96),   # 11:00 kein Touch
            (96, 96.5, 94.5, 95),   # 11:05 Fill @95 (low 94.5<=95<=96.5), SL(90)/TP(110) noch nicht beruehrt
            (95, 95.5, 93.0, 93),   # 11:10 weiter offen
            (93, 93.5, 89.0, 90),   # 11:15 SL 90 beruehrt (low 89) -> Exit
        ] + [(90, 90.5, 89.5, 90)] * 8, start="2024-01-02 11:00", freq="5min")
        cfg = base_config(CostModel(0.0), intrabar="m5", timeframes=["H1", "M5"])
        res = Backtester(H1LimitStrategy(), cfg,
                         {"H1": self._h1_bars(), "M5": m5}).run()
        assert len(res.trades) == 1
        assert res.trades.iloc[0]["exit"] == pytest.approx(90.0)
        assert res.trades.iloc[0]["pnl"] < 0

    def test_m5_resolves_fill_then_tp_as_win(self):
        # Gleiche Kollisionsbar, aber M5 zeigt: Fill @95, danach TP 110 OHNE
        # dass SL 90 zwischendurch beruehrt wird -> Gewinn, kein Discard.
        m5 = make_df([
            (96, 96.5, 95.5, 96),   # 11:00 kein Touch
            (96, 96.5, 94.5, 95),   # 11:05 Fill @95
            (95, 111.0, 94.0, 110),  # 11:10 TP 110 beruehrt (SL 90 nicht touched: low 94)
        ] + [(110, 110.5, 109.5, 110)] * 9, start="2024-01-02 11:00", freq="5min")
        cfg = base_config(CostModel(0.0), intrabar="m5", timeframes=["H1", "M5"])
        res = Backtester(H1LimitStrategy(), cfg,
                         {"H1": self._h1_bars(), "M5": m5}).run()
        assert len(res.trades) == 1
        assert res.trades.iloc[0]["exit"] == pytest.approx(110.0)
        assert res.trades.iloc[0]["pnl"] > 0

    def test_m5_no_fine_data_falls_back_to_stop_first(self):
        # intrabar=m5 konfiguriert, aber keine M5-Daten geladen -> Fallback
        # auf das grobe stop_first-Verhalten (Discard), kein Crash.
        cfg = base_config(CostModel(0.0), intrabar="m5", timeframes=["H1"])
        res = Backtester(H1LimitStrategy(), cfg, {"H1": self._h1_bars()}).run()
        assert len(res.trades) == 0


# ---------------------------------------------------------------------------
# Intrabar-Modi: stop_first vs m1
# ---------------------------------------------------------------------------
class TestIntrabarModes:
    M5_BARS = [
        (100, 100.5, 99.5, 100),   # i0
        (100, 100.5, 99.5, 100),   # i1 -> Signal (SL 90, TP 110)
        (100, 111.0, 88.0, 92),    # i2: TP UND SL in einer Bar
        (92, 93.0, 88.0, 90),      # i3
    ]
    # M1-Aufloesung fuer i2 (09:10-09:14): TP zuerst (09:11), SL spaeter (09:13)
    M1_BARS = [
        (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),  # 09:00, 09:05 (i0/i1)
        (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
        (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
        (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
        (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
        (100, 105.0, 99.0, 104),   # 09:10
        (104, 111.0, 103.0, 110),  # 09:11 -> TP 110
        (110, 110.0, 100.0, 101),  # 09:12
        (101, 102.0, 88.0, 90),    # 09:13 -> SL 90
        (90, 95.0, 88.0, 92),      # 09:14
        (92, 93.0, 89.0, 90),      # 09:15
        (90, 91.0, 88.0, 89),      # 09:16
        (89, 90.0, 88.0, 89.5),    # 09:17
        (89.5, 90.0, 88.5, 89),    # 09:18
        (89, 90.0, 88.5, 90),      # 09:19
    ]

    def _strategy(self):
        class S(MiniStrategy):
            def on_bar(self, bars, i):
                if i == 1:
                    return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=90.0, take_profit=110.0,
                                  risk_pct=1.0, meta={})
                return None
        return S()

    def test_stop_first_is_conservative(self):
        cfg = base_config(CostModel(0.0), intrabar="stop_first")
        res = Backtester(self._strategy(), cfg, {"M5": make_df(self.M5_BARS)}).run()
        assert len(res.trades) == 1
        assert res.trades.iloc[0]["exit"] == pytest.approx(90.0)
        assert res.trades.iloc[0]["pnl"] < 0

    def test_m1_resolves_correct_order(self):
        m1 = make_df(self.M1_BARS, start="2024-01-02 09:00", freq="1min")
        cfg = base_config(CostModel(0.0), intrabar="m1", timeframes=["M5", "M1"])
        res = Backtester(self._strategy(), cfg,
                         {"M5": make_df(self.M5_BARS), "M1": m1}).run()
        assert len(res.trades) == 1
        assert res.trades.iloc[0]["exit"] == pytest.approx(110.0)
        assert res.trades.iloc[0]["pnl"] > 0


# ---------------------------------------------------------------------------
# Time-Exit via meta + Force-Flat durch Risk-Engine
# ---------------------------------------------------------------------------
class TestEngineExits:
    def test_time_exit_bars(self):
        class HoldStrategy(MiniStrategy):
            def on_bar(self, bars, i):
                if i == 1:
                    return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=50.0, take_profit=None,
                                  risk_pct=1.0, meta={"time_exit_bars": 2})
                return None

        bars = [(100, 100.4, 99.6, 100)] * 8
        res = Backtester(HoldStrategy(), base_config(CostModel(0.0)),
                         {"M5": make_df(bars)}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["meta"]["exit_reason"] == "time_exit"
        # Entry am Open i2, Exit am Close i4 (2 Bars gehalten)
        idx = pd.date_range("2024-01-02 09:00", periods=8, freq="5min", tz="UTC")
        assert tr["entry_time"] == idx[2]
        assert tr["exit_time"] == idx[4] + pd.Timedelta(minutes=5)

    def test_eod_flat_forces_exit(self):
        class HoldStrategy(MiniStrategy):
            def on_bar(self, bars, i):
                if i == 0:
                    px = bars["M5"]["close"].iloc[-1]
                    return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=px - 50, take_profit=None,
                                  risk_pct=1.0, meta={})
                return None

        # Bars 15:00-17:00 UTC im Winter -> EOD 16:55 EST = 21:55 UTC NICHT
        # erreicht; wir nehmen Sommer (EDT=UTC-4): 16:55 NY = 20:55 UTC.
        idx = pd.date_range("2024-07-02 20:40", periods=5, freq="5min", tz="UTC")
        arr = np.array([(100, 100.4, 99.6, 100)] * 5)
        df = pd.DataFrame({"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2],
                           "close": arr[:, 3], "tick_volume": 100.0}, index=idx)
        cfg = base_config(CostModel(0.0),
                          risk=RiskConfig(risk_per_trade_pct=1.0, daily_loss_halt_pct=0,
                                          eod_flat=True, eod_flat_time_ny="16:55",
                                          friday_flat=False),
                          start=datetime(2024, 7, 2, tzinfo=timezone.utc),
                          end=datetime(2024, 7, 3, tzinfo=timezone.utc))
        res = Backtester(HoldStrategy(), cfg, {"M5": df}).run()
        assert len(res.trades) == 1
        assert res.trades.iloc[0]["meta"]["exit_reason"] == "force_flat"
        # Exit am Open der ersten Bar ab 20:55 UTC
        assert res.trades.iloc[0]["exit_time"] == idx[3]

    def test_force_flat_gap_weekend_swallows_deadline(self):
        """Bug-Fix: die Wochenend-Luecke (letzte Freitag-Bar VOR der
        EOD-Zeit, naechste Bar erst Sonntag) darf die Friday-Flat-Deadline
        nicht verschlucken. Ohne Fix wuerde die Position erst an der
        Sonntag-Bar geschlossen — zum gegappten Kurs, mit faelschlich
        realisiertem Wochenend-Gap-Verlust. Regressionsfall fuer den in
        S4/USDJPY gefundenen -4.79R-Ausreisser (exit_reason='force_flat')."""
        class HoldStrategy(MiniStrategy):
            def on_bar(self, bars, i):
                if i == 0:
                    px = bars["H1"]["close"].iloc[-1]
                    return Signal(time=bars["H1"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=px - 50, take_profit=None,
                                  risk_pct=1.0, meta={})
                return None

        # Freitag 14:00-20:00 UTC (Winter, EST=UTC-5: 16:55 NY = 21:55 UTC —
        # die letzte Bar 20:00 UTC liegt VOR der Deadline), dann Luecke bis
        # Sonntag 21:00 UTC (16:00 EST — ebenfalls noch vor 16:55 NY, damit
        # NICHT der normale force_flat()-Pfad an dieser Bar selbst greift).
        friday = pd.date_range("2024-01-05 14:00", "2024-01-05 20:00", freq="1h", tz="UTC")
        sunday = pd.DatetimeIndex(["2024-01-07 21:00"], tz="UTC")
        idx = friday.append(sunday)
        n = len(idx)
        # Alle Bars ruhig bei 100; nur die Sonntag-Bar gapped weit nach unten
        # (91) — ohne Fix realisiert das faelschlich einen Wochenend-Verlust.
        arr = np.array([(100, 100.4, 99.6, 100)] * (n - 1) + [(91, 91.4, 90.6, 91)])
        df = pd.DataFrame({"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2],
                           "close": arr[:, 3], "tick_volume": 100.0}, index=idx)
        cfg = base_config(CostModel(0.0), timeframes=["H1"],
                          risk=RiskConfig(risk_per_trade_pct=1.0, daily_loss_halt_pct=0,
                                          eod_flat=True, eod_flat_time_ny="16:55",
                                          friday_flat=True),
                          start=datetime(2024, 1, 5, tzinfo=timezone.utc),
                          end=datetime(2024, 1, 8, tzinfo=timezone.utc))
        res = Backtester(HoldStrategy(), cfg, {"H1": df}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["meta"]["exit_reason"] == "force_flat_gap"
        # Exit zum Close der letzten Freitag-Bar (100), NICHT zum gegappten
        # Sonntag-Open (91).
        assert tr["exit"] == pytest.approx(100.0)
        assert tr["exit_time"] == idx[n - 2] + pd.Timedelta(hours=1)
        assert tr["pnl"] == pytest.approx(0.0)

    def test_force_flat_gap_fixed_utc_deadline_matches_real_s4_bug(self):
        """Faithful reproduction of the actual S4/USDJPY production bug —
        NOT the case above. The first fix attempt used
        force_flat_gap(prev, cur) with a guard of `not force_flat(cur)`; it
        passed the test above (deliberately built so the Sunday bar itself
        is still BEFORE the deadline) but did NOT fix the real bug, because
        S4's actual config uses eod_flat_time_utc="21:00" (a fixed UTC
        trade-desk close, not NY-local) — and with that, a Sunday-reopen
        bar at 21:00 UTC is trivially already past the SAME day's deadline,
        so the old guard bailed out and deferred to the stale bar-open
        check, reproducing the exact -4.79R outlier bit-for-bit on the
        first fixed WFA re-run. Verified against the real
        reports/wfa_s4_postfix/oos_trades.csv entry before this second fix."""
        class HoldStrategy(MiniStrategy):
            def on_bar(self, bars, i):
                if i == 0:
                    px = bars["H1"]["close"].iloc[-1]
                    return Signal(time=bars["H1"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=px - 50, take_profit=None,
                                  risk_pct=1.0, meta={})
                return None

        # Letzte Freitag-Bar 20:00 UTC (vor der 21:00-UTC-Deadline), dann
        # Luecke bis Sonntag 21:00 UTC — die Sonntag-Bar selbst ist bereits
        # >= 21:00 UTC, also trivial "past deadline" (genau der Bug-Fall).
        friday = pd.date_range("2024-01-05 14:00", "2024-01-05 20:00", freq="1h", tz="UTC")
        sunday = pd.DatetimeIndex(["2024-01-07 21:00"], tz="UTC")
        idx = friday.append(sunday)
        n = len(idx)
        arr = np.array([(100, 100.4, 99.6, 100)] * (n - 1) + [(91, 91.4, 90.6, 91)])
        df = pd.DataFrame({"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2],
                           "close": arr[:, 3], "tick_volume": 100.0}, index=idx)
        cfg = base_config(CostModel(0.0), timeframes=["H1"],
                          risk=RiskConfig(risk_per_trade_pct=1.0, daily_loss_halt_pct=0,
                                          eod_flat=True, eod_flat_time_utc="21:00",
                                          friday_flat=True),
                          start=datetime(2024, 1, 5, tzinfo=timezone.utc),
                          end=datetime(2024, 1, 8, tzinfo=timezone.utc))
        res = Backtester(HoldStrategy(), cfg, {"H1": df}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["meta"]["exit_reason"] == "force_flat_gap"
        assert tr["exit"] == pytest.approx(100.0)  # NICHT der gegappte Sonntag-Open (91)
        assert tr["exit_time"] == idx[n - 2] + pd.Timedelta(hours=1)
        assert tr["pnl"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Fenster-Runs (start > Datenanfang): i muss auf die aktuelle Bar im View
# zeigen (SPEC §4.1) — Regression gegen WFA-Folds mit 2019er-Levels in 2024
# ---------------------------------------------------------------------------
class TestWindowedIndexContract:
    def test_i_points_to_current_bar_with_warmup(self):
        seen = []

        class Recorder(MiniStrategy):
            def on_bar(self, bars, i):
                seen.append(bars["M5"].index[i])
                return None

        # Daten ab 09:00, Fenster erst ab 10:00 -> 12 Bars Warmup
        bars = [(100, 100.4, 99.6, 100)] * 24
        cfg = base_config(CostModel(0.0),
                          start=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                          end=datetime(2024, 1, 3, tzinfo=timezone.utc))
        Backtester(Recorder(), cfg, {"M5": make_df(bars)}).run()
        idx = pd.date_range("2024-01-02 09:00", periods=24, freq="5min", tz="UTC")
        # Erster Callback muss auf die 10:00-Bar zeigen, nicht auf 09:00
        assert seen[0] == idx[12]
        assert seen[-1] == idx[-1]

    def test_windowed_matches_full_run(self):
        """Signal-Levels duerfen nicht vom Datenanfang stammen: Signale im
        Fenster muessen im Fenster-Run und Voll-Run identisch sein.
        (Trades selbst koennen abweichen: im Voll-Run kann eine Position aus
        der Vor-Fenster-Zeit noch offen sein und Entries blockieren.)"""
        signals = []

        class SigStrategy(MiniStrategy):
            def on_bar(self, bars, i):
                # Signal relativ zum AKTUELLEN Close (wie S1-S4 via i)
                c = float(bars["M5"]["close"].iloc[i])
                if i % 7 == 3:
                    sig = Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                 entry_type="market", entry_price=None,
                                 stop_loss=c - 2.0, take_profit=c + 4.0,
                                 risk_pct=1.0, meta={})
                    signals.append((sig.time, sig.stop_loss, sig.take_profit))
                    return sig
                return None

        # aufsteigende Preise: alte Levels waeren sofort "gap"-getriggert
        bars = [(100 + k, 100.4 + k, 99.6 + k, 100 + k) for k in range(40)]
        data = {"M5": make_df(bars)}
        Backtester(SigStrategy(), base_config(CostModel(0.0)), data).run()
        sigs_full = list(signals)
        signals.clear()
        win_cfg = base_config(CostModel(0.0),
                              start=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                              end=datetime(2024, 1, 3, tzinfo=timezone.utc))
        Backtester(SigStrategy(), win_cfg, data).run()
        cutoff = pd.Timestamp("2024-01-02 10:00", tz="UTC")
        sigs_full_window = [s for s in sigs_full if s[0] >= cutoff]
        assert len(signals) == len(sigs_full_window) > 0
        assert signals == sigs_full_window


# ---------------------------------------------------------------------------
# Trailing-Stop (Chandelier-Stil, meta["trail_atr_mult"])
# ---------------------------------------------------------------------------
class TrailStrategy:
    """Long-Signal bei i==2 mit weit entferntem Stop (50) + Trailing-Stop
    (1x ATR14->hier ATR2 fuer schnelle Konvergenz in Tests)."""
    name = "trail"
    required_timeframes = ["M5"]

    def __init__(self, params=None):
        self.params = params or {}

    def on_bar(self, bars, i):
        if i == 2:
            return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                          entry_type="market", entry_price=None,
                          stop_loss=50.0, take_profit=None, risk_pct=1.0,
                          meta={"trail_atr_mult": 1.0, "trail_atr_len": 2})
        return None


class TestTrailingStop:
    # TR=2 konstant (i0-i3) -> ATR2 konvergiert exakt auf 2.0. i4: Ausbruch
    # (TR=5) zieht den Trail auf 105-3.5=101.5 nach (weit ueber dem
    # statischen SL=50). i5 beruehrt 101.5, NICHT 50 -> beweist, dass der
    # Trail tatsaechlich greift statt des Original-Stops.
    BARS = [
        (100, 101, 99, 100),   # i0
        (100, 101, 99, 100),   # i1 (ATR2 seedet hier: mean(2,2)=2.0)
        (100, 101, 99, 100),   # i2 -> Signal
        (100, 101, 99, 100),   # i3 Entry @ Open=100; Bar-Ende: trail=101-2=99
        (100, 105, 100, 104),  # i4 TR=5 -> ATR=(2*1+5)/2=3.5; trail=105-3.5=101.5
        (104, 104, 96, 97),    # i5 low=96 <= 101.5 -> Exit @ 101.5 (Trail, nicht SL=50)
    ]

    def test_chandelier_trail_ratchets_and_exits_above_static_sl(self):
        cfg = base_config(CostModel(0.0))
        res = Backtester(TrailStrategy(), cfg, {"M5": make_df(self.BARS)}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["entry"] == pytest.approx(100.0)
        assert tr["exit"] == pytest.approx(101.5)
        assert tr["meta"]["exit_reason"] == "sl"
        assert tr["pnl"] > 0  # Trail sicherte Gewinn, statischer SL=50 waere ein Verlust gewesen

    def test_tp_converts_to_trail_locks_min_rr_then_trails(self):
        # Gleiches Szenario, TP=103 liegt VOR dem "natuerlichen" Trail-Niveau
        # (i4 high=105 >= 103, Trail waere dort erst bei 101.5). Mit
        # tp_converts_to_trail=True darf das NICHT bei 103 schliessen (echter
        # Push moeglich) — aber der SL MUSS sofort auf 103 gezogen werden
        # (Mindest-RR-Lock), NICHT beim schwaecheren Trail-Wert (101.5)
        # bleiben — sonst waere "Move-to-Trail" wirkungsgleich mit "kein TP".
        class ConvertStrategy(TrailStrategy):
            def on_bar(self, bars, i):
                if i == 2:
                    return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=50.0, take_profit=103.0, risk_pct=1.0,
                                  meta={"trail_atr_mult": 1.0, "trail_atr_len": 2,
                                        "tp_converts_to_trail": True})
                return None

        cfg = base_config(CostModel(0.0))
        res = Backtester(ConvertStrategy(), cfg, {"M5": make_df(self.BARS)}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["meta"]["exit_reason"] == "sl"  # nicht "tp" — TP wurde konvertiert
        assert tr["exit"] == pytest.approx(103.0)  # gelockt auf TP-Niveau, nicht 101.5
        assert tr["pnl"] > 0

    def test_tp_without_convert_flag_still_closes_normally(self):
        # Regression: dasselbe TP=103, aber OHNE tp_converts_to_trail ->
        # normales hartes TP, schliesst bei 103 (i4), Trail bleibt wirkungslos.
        class FixedTpStrategy(TrailStrategy):
            def on_bar(self, bars, i):
                if i == 2:
                    return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=50.0, take_profit=103.0, risk_pct=1.0,
                                  meta={"trail_atr_mult": 1.0, "trail_atr_len": 2})
                return None

        cfg = base_config(CostModel(0.0))
        res = Backtester(FixedTpStrategy(), cfg, {"M5": make_df(self.BARS)}).run()
        assert len(res.trades) == 1
        tr = res.trades.iloc[0]
        assert tr["meta"]["exit_reason"] == "tp"
        assert tr["exit"] == pytest.approx(103.0)

    def test_trail_disabled_by_default_uses_static_sl(self):
        # Gleiches Szenario ohne trail_atr_mult -> statischer SL=50 greift nicht
        # (Kurs faellt in diesem Fenster nie unter 96), Position bleibt offen
        # bis Backtest-Ende (end_of_data-Exit), NICHT bei 101.5.
        class NoTrailStrategy(TrailStrategy):
            def on_bar(self, bars, i):
                if i == 2:
                    return Signal(time=bars["M5"].index[i], symbol="TEST", direction=1,
                                  entry_type="market", entry_price=None,
                                  stop_loss=50.0, take_profit=None, risk_pct=1.0, meta={})
                return None

        cfg = base_config(CostModel(0.0))
        res = Backtester(NoTrailStrategy(), cfg, {"M5": make_df(self.BARS)}).run()
        assert len(res.trades) == 1
        assert res.trades.iloc[0]["meta"]["exit_reason"] == "end_of_data"
