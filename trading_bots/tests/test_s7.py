"""Unit-Tests S7 — FomcDrift (EURUSD, H1) auf handgebauten Mini-Serien.

- load_fomc_decisions(): echte data/fomc_dates.csv, DST-sichere ET->UTC-
  Konvertierung (Winter/Sommer).
- Momentum-Gate: Long/Short-Signal bei Move > min_momentum x ATR(H1,10) ab
  London-Session-Open bis zur Check-Bar (entry_check_hour vor Decision);
  kein Signal bei zu kleinem Move.
- Kausalitaet: Praefix-Stabilitaet, kein Signal vor der Check-Bar, Shift-Test.
- Flatten-Pflicht: End-to-End-Backtest zeigt, dass die Position via
  meta["time_exit_bars"] VOR der FOMC-Decision (inkl. exit_buffer_min)
  geschlossen wird — unabhaengig von SL/TP-Status (hier: kein TP, SL nicht
  beruehrt).
Synthetische Daten inline (deterministisch, kein numpy-Random noetig).
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from core.backtester import Backtester, BacktestConfig, CostModel
from core.risk import RiskConfig
from strategies.s7_fomc_drift import S7FomcDrift, load_fomc_decisions

UTC = ZoneInfo("UTC")

# FOMC-Decision aus der echten data/fomc_dates.csv: 2024-01-31, 14:00 ET.
# Januar = EST (UTC-5) -> 19:00 UTC.
FOMC_DAY = date(2024, 1, 31)
DECISION_TS = pd.Timestamp("2024-01-31 19:00", tz=UTC)

BASE_PARAMS = dict(
    symbol="EURUSD",
    risk_pct=0.005,
    entry_check_hour=4,     # Check-Bar 15:00 UTC (Decision - 4h)
    min_momentum=0.5,
    stop_mult=0.4,
    exit_buffer_min=15,     # Deadline 18:45 UTC
)


def _ts(day: date, hh: int) -> pd.Timestamp:
    return pd.Timestamp(datetime(day.year, day.month, day.day, hh), tz=UTC)


def build_fomc_day(day: date, drift: float, base: float = 1.10000,
                   half_range: float = 0.00015) -> pd.DataFrame:
    """24 H1-Bars fuer ``day`` (UTC):
      00:00-07:59  ruhig, Niveau ``base`` (vor London-Open)
      08:00        London-Session-Open-Bar -> Anker = Bar-Open = ``base``
      09:00-14:59  linearer Ramp ueber 6 Bars: Close(14:00-Bar) = base+drift
                   (14:00-Bar schliesst 15:00 UTC = Check-Bar bei
                   entry_check_hour=4, Decision 19:00 UTC)
      15:00-23:59  flach auf dem erreichten Niveau (kein SL-Touch danach)
    """
    rows = []
    closes = [base] * 24
    step = drift / 6.0
    for k in range(1, 7):  # Bars 9..14 (Index 9-14) rampen
        closes[8 + k] = base + k * step
    for idx in range(15, 24):
        closes[idx] = closes[14]

    prev_close = base  # Open der ersten Bar = base (kausale Kontinuitaet)
    for idx in range(24):
        o = prev_close
        c = closes[idx]
        h = max(o, c) + half_range
        l = min(o, c) - half_range
        rows.append((_ts(day, idx), o, h, l, c))
        prev_close = c

    df = pd.DataFrame(
        [r[1:] for r in rows],
        index=pd.DatetimeIndex([r[0] for r in rows]),
        columns=["open", "high", "low", "close"],
    ).astype("float64")
    df["tick_volume"] = 100.0
    return df


def run_strategy(df: pd.DataFrame, **overrides) -> list:
    params = {**BASE_PARAMS, **overrides}
    strat = S7FomcDrift(params)
    sigs = []
    for i in range(len(df)):
        s = strat.on_bar({"H1": df}, i)
        if s is not None:
            sigs.append(s)
    return sigs


# ---------------------------------------------------------------------------
# 1. FOMC-Datenquelle: echte data/fomc_dates.csv, DST-sichere Konvertierung
# ---------------------------------------------------------------------------
def test_load_fomc_decisions_real_file_dst_safe():
    decisions = load_fomc_decisions("data/fomc_dates.csv")
    assert len(decisions) >= 60
    # Winter (EST, UTC-5): 2024-01-31 14:00 ET -> 19:00 UTC
    assert decisions[date(2024, 1, 31)] == pd.Timestamp("2024-01-31 19:00", tz="UTC")
    # Sommer (EDT, UTC-4): 2024-07-31 14:00 ET -> 18:00 UTC
    assert decisions[date(2024, 7, 31)] == pd.Timestamp("2024-07-31 18:00", tz="UTC")
    # Alle Zeiten tz-aware UTC
    assert all(ts.tzinfo is not None for ts in decisions.values())


def test_no_fabricated_dates_only_documented_source():
    """Jede Zeile in data/fomc_dates.csv muss aus dem dokumentierten Header
    (echte federalreserve.gov-Quelle) stammen — Sanity-Check: Datei beginnt
    mit einem Quellen-Header-Kommentar, keine Silent-Fabrication."""
    with open("data/fomc_dates.csv", encoding="utf-8") as fh:
        head = fh.read(2000)
    assert "federalreserve.gov" in head
    assert head.lstrip().startswith("#")


# ---------------------------------------------------------------------------
# 2. Momentum-Gate -> Signal (Long/Short), kein Signal bei zu kleinem Move
# ---------------------------------------------------------------------------
def test_long_signal_on_strong_upward_drift():
    df = build_fomc_day(FOMC_DAY, drift=0.0060)  # deutlich > ATR
    sigs = run_strategy(df, fomc_decisions_obj={FOMC_DAY: DECISION_TS})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == 1
    assert s.symbol == "EURUSD"
    assert s.entry_type == "market"
    assert s.entry_price is None
    assert s.time == _ts(FOMC_DAY, 14)          # Check-Bar (Open), 15:00 Close
    assert s.take_profit is None                 # nur Time-Exit (Signal §4.1)
    close_at_check = float(df.loc[_ts(FOMC_DAY, 14), "close"])
    assert s.stop_loss < close_at_check           # SL unter Entry-Referenz (Long)
    assert s.meta["session_open_price"] == pytest.approx(1.10000)
    assert s.meta["move"] == pytest.approx(0.0060)
    assert s.meta["fomc_decision_date"] == str(FOMC_DAY)


def test_short_signal_on_strong_downward_drift():
    df = build_fomc_day(FOMC_DAY, drift=-0.0060)
    sigs = run_strategy(df, fomc_decisions_obj={FOMC_DAY: DECISION_TS})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == -1
    close_at_check = float(df.loc[_ts(FOMC_DAY, 14), "close"])
    assert s.stop_loss > close_at_check           # SL ueber Entry-Referenz (Short)


def test_no_signal_below_momentum_threshold():
    df = build_fomc_day(FOMC_DAY, drift=0.0001)   # << ATR
    sigs = run_strategy(df, fomc_decisions_obj={FOMC_DAY: DECISION_TS})
    assert sigs == []


def test_no_signal_on_non_fomc_day():
    other_day = date(2024, 2, 1)  # kein FOMC-Termin
    df = build_fomc_day(other_day, drift=0.0060)
    sigs = run_strategy(df, fomc_decisions_obj={FOMC_DAY: DECISION_TS})
    assert sigs == []


def test_time_exit_bars_computed_correctly_in_meta():
    """entry_check_hour=4, exit_buffer_min=15, Decision 19:00 UTC:
    Check-Bar schliesst 15:00 (= Entry-Fill, SPEC §4.2 Open naechste Bar).
    Deadline = 18:45 UTC. Letzte Bar, deren CLOSE <= Deadline liegt: 18:00
    (Bar 17:00-18:00) -> time_exit_bars = 2 (Bars 15:00-16:00 und
    16:00-17:00 dazwischen, Exit an der dritten post-Entry-Bar)."""
    df = build_fomc_day(FOMC_DAY, drift=0.0060)
    sigs = run_strategy(df, fomc_decisions_obj={FOMC_DAY: DECISION_TS})
    assert sigs[0].meta["time_exit_bars"] == 2
    assert sigs[0].meta["flatten_deadline_utc"] == pd.Timestamp(
        "2024-01-31 18:45", tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# 3. Kausalitaet: Praefix-Stabilitaet, kein Signal vor der Check-Bar, Shift
# ---------------------------------------------------------------------------
def test_kausalitaet_prefix_stabil():
    df = build_fomc_day(FOMC_DAY, drift=0.0060)
    kwargs = dict(fomc_decisions_obj={FOMC_DAY: DECISION_TS})
    sigs_full = run_strategy(df, **kwargs)
    assert len(sigs_full) == 1
    sig_pos = df.index.get_loc(sigs_full[0].time)

    # Kein Signal vor der Check-Bar (Bar 14, 14:00 Open / 15:00 Close)
    for cut in range(1, sig_pos + 1):
        assert run_strategy(df.iloc[:cut], **kwargs) == []

    # Abgeschnitten direkt NACH der Signal-Bar -> identisches Signal
    sigs_cut = run_strategy(df.iloc[: sig_pos + 1], **kwargs)
    assert len(sigs_cut) == 1
    a, b = sigs_full[0], sigs_cut[0]
    assert a.time == b.time
    assert a.direction == b.direction
    assert a.stop_loss == pytest.approx(b.stop_loss)
    assert a.meta["time_exit_bars"] == b.meta["time_exit_bars"]

    # Shift-Test: zusaetzliche Bars am Ende aendern das bereits gefundene
    # Signal nicht (kein Lookahead).
    extra_day = date(2024, 2, 1)
    extra = build_fomc_day(extra_day, drift=0.0)
    extended = pd.concat([df, extra])
    sigs_ext = run_strategy(extended, **kwargs)
    assert len(sigs_ext) == 1
    assert sigs_ext[0].time == sigs_full[0].time
    assert sigs_ext[0].stop_loss == pytest.approx(sigs_full[0].stop_loss)


# ---------------------------------------------------------------------------
# 4. Flatten-Pflicht: Position wird VOR der Decision geschlossen — Backtest
# ---------------------------------------------------------------------------
def test_flattened_before_fomc_time_regardless_of_stop_target():
    """End-to-End ueber core.backtester.Backtester: kein TP (nur Time-Exit),
    SL wird durch die flache Nachbewegung nie beruehrt -> der einzige Weg,
    wie die Position ueberhaupt geschlossen wird, ist meta["time_exit_bars"].
    Das muss VOR der Decision-Zeit (inkl. exit_buffer_min-Puffer) passieren,
    nie danach, unabhaengig vom Preisverlauf."""
    df = build_fomc_day(FOMC_DAY, drift=0.0060)
    strat = S7FomcDrift({**BASE_PARAMS, "fomc_decisions_obj": {FOMC_DAY: DECISION_TS}})

    cfg = BacktestConfig(
        symbol="EURUSD",
        timeframes=["H1"],
        start=_ts(FOMC_DAY, 0),
        end=_ts(FOMC_DAY, 23),
        costs=CostModel(spread_points=8.0, commission_per_lot_rt=7.0),
        risk=RiskConfig(risk_per_trade_pct=0.5, eod_flat=True,
                        eod_flat_time_ny="16:55", friday_flat=True),
        point=0.00001,
        point_value=100000.0,
        initial_balance=100_000.0,
    )
    bt = Backtester(strat, cfg, data={"H1": df})
    result = bt.run()

    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["meta"]["exit_reason"] == "time_exit"
    exit_time = pd.Timestamp(trade["exit_time"])
    # Muss klar vor der Decision liegen (inkl. Puffer) — nie danach.
    deadline = DECISION_TS - pd.Timedelta(minutes=BASE_PARAMS["exit_buffer_min"])
    assert exit_time <= deadline
    assert exit_time < DECISION_TS
    assert exit_time == pd.Timestamp("2024-01-31 18:00", tz=UTC)
    assert trade["entry_time"] == pd.Timestamp("2024-01-31 15:00", tz=UTC)
    assert trade["direction"] == 1


# ---------------------------------------------------------------------------
# 5. Smoke-Import core-Module
# ---------------------------------------------------------------------------
def test_core_module_importierbar():
    try:
        import core.indicators  # noqa: F401
        import core.backtester  # noqa: F401
    except ImportError:
        pytest.xfail("core-Module noch nicht vorhanden (parallele Entwicklung)")
