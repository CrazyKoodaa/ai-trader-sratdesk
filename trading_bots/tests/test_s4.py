"""Unit-Tests S4 — LondonBreakout (SPEC §5/S4) auf handgebauten Mini-Serien.

- Range-Breakout (00:00–06:59 UTC Range, Close jenseits im Fenster 07:00–16:59)
  erzeugt Market-Signal, 1 Trade/Tag.
- Filter: skip_monday, range_band, atr_filter, ema_filter (einzeln schaltbar).
- Archetyp B: entry_mode=retest (Limit an Range-Grenze).
- Kausalitaet: Praefix-Stabilitaet.
- Zeitzone: Fenster/Range strikt UTC (DST-Asynchronwoche verschiebt nichts).
Synthetische Daten inline (numpy, seed-kontrolliert).
"""
from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from strategies.s4_london_breakout import S4LondonBreakout

UTC = ZoneInfo("UTC")
rng = np.random.default_rng(7)

BASE_PARAMS = dict(
    symbol="USDJPY",
    risk_pct=0.005,
    tp_r=2.0,
    pip_size=0.01,
    entry_mode="close",
    atr_filter="off",
    ema_filter="off",
    range_band="off",
    skip_monday="off",
)


def bdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _bars(rows):
    df = pd.DataFrame(
        [r[1:] for r in rows],
        index=pd.DatetimeIndex([r[0] for r in rows]),
        columns=["open", "high", "low", "close"],
    ).astype(np.float64)
    df["tick_volume"] = rng.integers(80, 200, len(df)).astype(np.float64)
    return df


def h1_day(
    rows: list,
    day: date,
    range_high: float = 150.50,
    range_low: float = 150.00,
    breakout: str | None = None,
    breakout_close: float | None = None,
    second_close: float | None = None,
) -> None:
    """Ein UTC-Handelstag: Range 00–06 Uhr, optionalem Breakout-Close 07:00."""

    def add(hh: int, o: float, h: float, l: float, c: float) -> None:
        rows.append((pd.Timestamp(day.isoformat() + f" {hh:02d}:00", tz=UTC), o, h, l, c))

    mid = (range_high + range_low) / 2
    for hh in range(0, 7):  # Range 00:00–06:59 UTC
        add(hh, mid, range_high, range_low, mid)
    if breakout == "long":
        bc = breakout_close if breakout_close is not None else range_high + 0.15
        add(7, range_high + 0.02, bc + 0.05, range_high - 0.02, bc)
        # 08:00 schliesst ebenfalls jenseits (Test: nur 1 Trade/Tag)
        sc = second_close if second_close is not None else bc + 0.15
        add(8, bc, sc + 0.05, bc - 0.05, sc)
    elif breakout == "short":
        bc = breakout_close if breakout_close is not None else range_low - 0.15
        add(7, range_low - 0.02, range_low + 0.02, bc - 0.05, bc)
        sc = second_close if second_close is not None else bc - 0.15
        add(8, bc, bc + 0.05, sc - 0.05, sc)
    else:
        for hh in range(7, 17):  # kein Breakout: Closes innerhalb der Range
            add(hh, mid, range_high - 0.02, range_low + 0.02, mid)
    # Rest des Tages ruhig
    last_c = rows[-1][4]
    existing = {r[0].hour for r in rows if r[0].date() == day}
    for hh in range(9, 24):
        if hh not in existing:
            add(hh, last_c, last_c + 0.1, last_c - 0.1, last_c)


def build_h1(plan: list[tuple]) -> pd.DataFrame:
    rows: list = []
    for day, kwargs in plan:
        h1_day(rows, day, **kwargs)
    return _bars(rows)


def build_d1(end_exclusive: date, n: int, ranges: list[float] | float) -> pd.DataFrame:
    """n abgeschlossene D1-Bars vor end_exclusive; close=open (TR = Range)."""
    days = [d for d in bdays(date(2024, 1, 2), 80) if d < end_exclusive][-n:]
    if isinstance(ranges, (int, float)):
        ranges = [float(ranges)] * len(days)
    rows = []
    px = 150.0
    for d, r in zip(days, ranges):
        rows.append((pd.Timestamp(d.isoformat(), tz=UTC), px, px + r, px, px))
    return _bars(rows)


def build_h4_declining(end_day: date, n: int = 230) -> pd.DataFrame:
    """Fallende H4-Serie (Close < EMA200) bis inkl. end_day 04:00 UTC."""
    end_ts = pd.Timestamp(end_day.isoformat() + " 04:00", tz=UTC)
    idx = pd.date_range(end=end_ts, periods=n, freq="4h", tz=UTC)
    closes = np.linspace(152.0, 149.8, n)
    rows = [(t, c + 0.02, c + 0.1, c - 0.1, c) for t, c in zip(idx, closes)]
    return _bars(rows)


def run(df_h1, params_over=None, bars_extra=None):
    params = {**BASE_PARAMS, **(params_over or {})}
    strat = S4LondonBreakout(params)
    bars = {"H1": df_h1}
    if bars_extra:
        bars.update(bars_extra)
    sigs = []
    for i in range(len(df_h1)):
        s = strat.on_bar(bars, i)
        if s is not None:
            sigs.append(s)
    return sigs


WED, THU, FRI = date(2024, 3, 13), date(2024, 3, 14), date(2024, 3, 15)
MON, TUE = date(2024, 3, 11), date(2024, 3, 12)


# ---------------------------------------------------------------------------
# 1. Range-Breakout -> Signal, 1 Trade/Tag
# ---------------------------------------------------------------------------
def test_breakout_long_signal_und_ein_trade_pro_tag():
    df = build_h1([
        (TUE, {}),                      # kein Breakout
        (WED, {"breakout": "long", "breakout_close": 150.65}),
        (THU, {"breakout": "short", "breakout_close": 149.35}),
    ])
    sigs = run(df)
    assert len(sigs) == 2
    s = sigs[0]
    assert s.time == pd.Timestamp("2024-03-13 07:00", tz=UTC)
    assert s.direction == 1
    assert s.entry_type == "market"
    assert s.entry_price is None
    assert s.stop_loss == pytest.approx(150.00)      # Range-Gegenseite
    assert s.take_profit == pytest.approx(150.65 + 2.0 * 0.65)  # 2R
    assert s.meta["eod_flat_utc"] == "21:00"
    s2 = sigs[1]
    assert s2.time == pd.Timestamp("2024-03-14 07:00", tz=UTC)
    assert s2.direction == -1
    assert s2.stop_loss == pytest.approx(150.50)
    assert s2.take_profit == pytest.approx(149.35 - 2.0 * (150.50 - 149.35))
    # 08:00-Bar schliesst ebenfalls jenseits -> kein zweites Signal am selben Tag
    times = [s.time.date() for s in sigs]
    assert len(times) == len(set(times))


def test_kein_signal_innerhalb_der_range():
    df = build_h1([(WED, {}), (THU, {})])
    assert run(df) == []


def test_tp_r_param():
    df = build_h1([(WED, {"breakout": "long", "breakout_close": 150.65})])
    sigs = run(df, {"tp_r": 1.5})
    assert sigs[0].take_profit == pytest.approx(150.65 + 1.5 * 0.65)


# ---------------------------------------------------------------------------
# 2. Filter-Layer
# ---------------------------------------------------------------------------
def test_skip_monday():
    df = build_h1([(MON, {"breakout": "long"}), (TUE, {"breakout": "long"})])
    sigs_on = run(df, {"skip_monday": "on"})
    assert [s.time.date() for s in sigs_on] == [TUE]
    sigs_off = run(df, {"skip_monday": "off"})
    assert [s.time.date() for s in sigs_off] == [MON, TUE]


def test_range_band_filter():
    d1 = build_d1(WED, 30, 1.2)  # ADR20 = 1.2 -> Cap 0.5 x 1.2 = 0.6 (60 Pips)
    df = build_h1([
        (WED, {"range_high": 150.10, "range_low": 150.00, "breakout": "long"}),  # 10 Pips < 20
        (THU, {"range_high": 150.70, "range_low": 150.00, "breakout": "long"}),  # 70 Pips > 60
        (FRI, {"breakout": "long"}),                                             # 50 Pips ok
    ])
    sigs = run(df, {"range_band": "on"}, bars_extra={"D1": d1})
    assert [s.time.date() for s in sigs] == [FRI]
    # ohne Filter alle drei Tage
    sigs_off = run(df, {"range_band": "off"}, bars_extra={"D1": d1})
    assert len(sigs_off) == 3


def test_atr_filter():
    # steigende Volatilitaet: ATR14 > 20d-Median -> Trade erlaubt
    d1_up = build_d1(WED, 40, [0.8] * 35 + [1.5] * 5)
    df = build_h1([(WED, {"breakout": "long"})])
    assert len(run(df, {"atr_filter": "on"}, bars_extra={"D1": d1_up})) == 1
    # fallende Volatilitaet: ATR14 < Median -> blockiert
    d1_dn = build_d1(WED, 40, [1.5] * 35 + [0.6] * 5)
    assert run(df, {"atr_filter": "on"}, bars_extra={"D1": d1_dn}) == []


def test_ema_filter_h4_alignment():
    h4 = build_h4_declining(THU)  # Close < EMA200
    df = build_h1([
        (WED, {"breakout": "long"}),    # Long gegen H4-EMA200 -> blockiert
        (THU, {"breakout": "short"}),   # Short im Alignment -> erlaubt
    ])
    sigs = run(df, {"ema_filter": "on"}, bars_extra={"H4": h4})
    assert len(sigs) == 1
    assert sigs[0].direction == -1
    assert sigs[0].time.date() == THU
    # ohne Filter beide
    assert len(run(df, {"ema_filter": "off"}, bars_extra={"H4": h4})) == 2


# ---------------------------------------------------------------------------
# 3. Archetyp B: Retest-Entry (Limit an Range-Grenze, SL dahinter)
# ---------------------------------------------------------------------------
def test_retest_entry_mode():
    df = build_h1([(WED, {"breakout": "long", "breakout_close": 150.65})])
    sigs = run(df, {"entry_mode": "retest", "tp_r": 1.5, "retest_sl_pips": 10})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry_type == "limit"
    assert s.entry_price == pytest.approx(150.50)   # Limit an Range-Grenze
    assert s.stop_loss == pytest.approx(150.40)     # 10 Pips dahinter
    assert s.take_profit == pytest.approx(150.50 + 1.5 * 0.10)
    assert s.expires_bars == 6


# ---------------------------------------------------------------------------
# 4. Kausalitaet
# ---------------------------------------------------------------------------
def test_kausalitaet_prefix_stabil():
    df = build_h1([
        (TUE, {}),
        (WED, {"breakout": "long", "breakout_close": 150.65}),
        (THU, {"breakout": "short", "breakout_close": 149.35}),
    ])
    sigs_full = run(df)
    assert len(sigs_full) == 2
    first_pos = df.index.get_loc(sigs_full[0].time)
    # vor dem Breakout-Bar kein Signal
    assert run(df.iloc[:first_pos]) == []
    sigs_cut = run(df.iloc[: first_pos + 1])
    assert len(sigs_cut) == 1
    assert sigs_cut[0].stop_loss == pytest.approx(sigs_full[0].stop_loss)
    assert sigs_cut[0].take_profit == pytest.approx(sigs_full[0].take_profit)
    # Shift-Test: angehaengte Bars aendern fruehere Signale nicht
    extra = pd.concat([df, build_h1([(FRI, {"breakout": "long"})])])
    sigs_ext = run(extra)
    assert [s.time for s in sigs_ext[:2]] == [s.time for s in sigs_full]
    assert sigs_ext[0].take_profit == pytest.approx(sigs_full[0].take_profit)


# ---------------------------------------------------------------------------
# 5. Zeitzone: Range/Fenster strikt UTC (DST-Asynchronwoche irrelevant)
# ---------------------------------------------------------------------------
def test_fenster_utc_nicht_serverzeit():
    # Breakout-Close bereits auf der 06:00-Bar -> noch Range-Stunde, kein Entry
    rows: list = []
    h1_day(rows, WED)
    # 06:00-Bar manuell jenseits der Range schliessen lassen
    for r in rows:
        if r[0] == pd.Timestamp("2024-03-13 06:00", tz=UTC):
            pass
    df = _bars(rows)
    assert run(df) == []  # kein Breakout -> kein Signal

    df2 = build_h1([(WED, {"breakout": "long"})])
    sigs = run(df2)
    # DST-Asynchronwoche (US seit 10.03.2024 in DST, EU nicht): Entry bleibt 07:00 UTC
    assert sigs[0].time == pd.Timestamp("2024-03-13 07:00", tz=UTC)
    assert sigs[0].time.hour == 7
    # Range nur aus Bars 00:00–06:59 UTC
    assert sigs[0].meta["range_high"] == pytest.approx(150.50)
    assert sigs[0].meta["range_low"] == pytest.approx(150.00)

    # Breakout-Close auf der 06:00-Bar (noch Range-Stunde) -> kein Entry
    rows: list = []
    h1_day(rows, WED)
    ts06 = pd.Timestamp("2024-03-13 06:00", tz=UTC)
    rows = [r if r[0] != ts06 else (ts06, 150.4, 150.8, 150.3, 150.75) for r in rows]
    assert run(_bars(rows)) == []


def test_entry_fenster_ende_1659():
    """Breakout-Close erst auf der 17:00-Bar -> ausserhalb 07:00–16:59, kein Trade."""
    rows: list = []
    h1_day(rows, WED)  # kein Breakout
    ts17 = pd.Timestamp("2024-03-13 17:00", tz=UTC)
    # 17:00-Bar jenseits der Range schliessen lassen (ausserhalb 07:00–16:59)
    rows = [r if r[0] != ts17 else (ts17, 150.4, 150.8, 150.3, 150.75) for r in rows]
    df = _bars(rows)
    assert run(df) == []


# ---------------------------------------------------------------------------
# 6. explain() — Live-Diagnose ("warum kein Signal?"), rein lesend
# ---------------------------------------------------------------------------
def test_explain_matches_on_bar_ready_and_signal():
    """explain() muss an genau der Bar 'ready' melden, an der on_bar
    tatsaechlich ein Signal liefert — und darf _traded_today NICHT mutieren."""
    df = build_h1([(WED, {"breakout": "long", "breakout_close": 150.65})])
    params = {**BASE_PARAMS}
    strat = S4LondonBreakout(params)
    bars = {"H1": df}
    signal_pos = df.index.get_loc(pd.Timestamp("2024-03-13 07:00", tz=UTC))

    info_before = strat.explain(bars, signal_pos)
    assert info_before["ready"] is True
    assert info_before["blocked_by"] == []
    assert info_before["breakout_direction"] == 1
    assert info_before["range_high"] == pytest.approx(150.50)
    assert info_before["range_low"] == pytest.approx(150.00)
    # explain() darf keinen State setzen — _traded_today bleibt False
    assert strat._traded_today is False

    sig = strat.on_bar(bars, signal_pos)
    assert sig is not None
    # Nach dem echten Signal: explain() an derselben Bar meldet "schon gehandelt"
    info_after = strat.explain(bars, signal_pos)
    assert info_after["already_traded_today"] is True
    assert info_after["blocked_by"] == ["already_traded_today"]


def test_explain_outside_entry_window():
    df = build_h1([(WED, {})])
    strat = S4LondonBreakout(dict(BASE_PARAMS))
    bars = {"H1": df}
    night_pos = df.index.get_loc(pd.Timestamp("2024-03-13 03:00", tz=UTC))
    info = strat.explain(bars, night_pos)
    assert info["in_entry_window"] is False
    assert info["blocked_by"] == ["outside_entry_window"]
    assert info["ready"] is False


def test_explain_inside_range_no_breakout():
    df = build_h1([(WED, {})])  # kein Breakout: Closes bleiben in der Range
    strat = S4LondonBreakout(dict(BASE_PARAMS))
    bars = {"H1": df}
    pos = df.index.get_loc(pd.Timestamp("2024-03-13 09:00", tz=UTC))
    info = strat.explain(bars, pos)
    assert info["blocked_by"] == ["inside_range"]
    assert info["breakout_direction"] is None


def test_explain_reports_blocking_filter():
    """Breakout vorhanden, aber ema_filter blockiert -> explain() nennt genau
    dieses Gate (nicht 'ready')."""
    h4 = build_h4_declining(WED)  # Close < EMA200 -> Long-Breakout ist gegen den H4-Trend
    df = build_h1([(WED, {"breakout": "long", "breakout_close": 150.65})])
    strat = S4LondonBreakout({**BASE_PARAMS, "ema_filter": "on"})
    bars = {"H1": df, "H4": h4}
    pos = df.index.get_loc(pd.Timestamp("2024-03-13 07:00", tz=UTC))
    info = strat.explain(bars, pos)
    assert info["breakout_direction"] == 1
    assert info["blocked_by"] == ["ema_filter"]
    assert info["ready"] is False
    # on_bar() muss konsistent dasselbe Ergebnis liefern (kein Signal)
    assert strat.on_bar(bars, pos) is None


# ---------------------------------------------------------------------------
# 7. Smoke-Import core-Module (xfail solange parallel entwickelt)
# ---------------------------------------------------------------------------
def test_core_module_importierbar():
    try:
        import core.indicators  # noqa: F401
        import core.time_engine  # noqa: F401
    except ImportError:
        pytest.xfail("core-Module noch nicht vorhanden (parallele Entwicklung)")
