"""Unit-Tests S3 — SilverBullet (SPEC §5/S3) auf handgebauten Mini-Serien.

- Sweep + MSS/Displacement + FVG erzeugt genau ein Limit-Signal (Short).
- RR>=2-Gate blockiert bei zu knappem Ziel.
- Kausalitaet: Signale auf Praefix identisch, kein Signal vor Bestaetigung.
- Zeitzone: Fenster greift in America/New_York, nicht UTC — inkl.
  DST-Asynchronwoche (US-DST ab 10.03.2024, EU erst ab 31.03.2024).
Synthetische Daten inline (numpy, seed-kontrolliert).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from strategies.s3_silver_bullet import S3SilverBullet, _in_window

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
rng = np.random.default_rng(42)

BASE_PARAMS = dict(
    symbol="NAS100",
    risk_pct=0.005,
    window="10:00-11:00",
    sweep_ref="hour9",
    htf_bias="off",
)


def _ts(day: date, hh: int, mm: int) -> pd.Timestamp:
    """Lokale NY-Zeit -> UTC Timestamp."""
    return pd.Timestamp(datetime(day.year, day.month, day.day, hh, mm), tz=NY).tz_convert(UTC)


def build_s3_frame(day: date) -> pd.DataFrame:
    """M5-Serie eines NY-Handelstages mit Short-Silver-Bullet-Sequenz.

    Lokalzeit (America/New_York):
      08:00–08:55  ruhige Bars (TR 0.4), Niveau ~100.8
      09:00–09:55  Referenz-Stunde: Dip auf 95.8, Recovery auf 100.4
                   -> ref_high 100.9 / ref_low 95.8
      10:00        Sweep ueber ref_high (High 101.4, Close 100.5 < 100.9)
      10:05–10:20  Swing-Tief 99.9 (k=2, bestaetigt 10:20)
      10:25        Displacement down (Body 1.55, Body/Range 0.91, Close 98.9 < 99.9)
      10:30        FVG wird sichtbar (Zone [99.6, 100.15]); core.smc: formed_at
      10:35        FVG confirmed_at (= formed + 1 Bar, SPEC §4.6) -> Signal;
                   gleichzeitig zweites Displacement (darf NICHT erneut
                   signalisieren: max 1 Trade/Fenster)
      10:40        zweites FVG wird sichtbar (confirmed 10:45)
    """
    rows: list[tuple] = []

    def add(hh: int, mm: int, o: float, h: float, l: float, c: float) -> None:
        rows.append((_ts(day, hh, mm), float(o), float(h), float(l), float(c)))

    # 08:00-Stunde: flach
    for m in range(0, 60, 5):
        add(8, m, 100.8, 101.0, 100.6, 100.8)

    # 09:00-Stunde: 7 Bars down (Schritt 0.7), 5 Bars up (Schritt 0.9)
    px = 100.8
    for m in range(0, 35, 5):  # 09:00–09:30 down
        o = px
        c = o - 0.7
        add(9, m, o, o + 0.1, c - 0.1, c)
        px = c
    assert abs(px - 95.9) < 1e-9
    for m in range(35, 60, 5):  # 09:35–09:55 up
        o = px
        c = o + 0.9
        add(9, m, o, c + 0.1, o - 0.1, c)
        px = c
    assert abs(px - 100.4) < 1e-9

    # Fenster 10:00–10:55
    add(10, 0, 100.4, 101.4, 100.2, 100.5)   # Sweep (Wick-Exzess 0.5, Close < ref)
    add(10, 5, 100.5, 100.7, 100.3, 100.55)
    add(10, 10, 100.55, 100.65, 99.9, 100.1)  # Swing-Tief 99.9
    add(10, 15, 100.1, 100.4, 100.0, 100.35)
    add(10, 20, 100.35, 100.55, 100.15, 100.45)  # bestaetigt Swing-Tief
    add(10, 25, 100.45, 100.5, 98.8, 98.9)   # Displacement (MSS per Close)
    add(10, 30, 98.9, 99.6, 98.6, 99.1)      # FVG wird sichtbar (core: formed_at)
    # 10:35 = confirmed_at des FVG (formed + 1 Bar, SPEC §4.6) -> Signal;
    # ab hier zweite Sequenz, darf nicht mehr signalisieren
    add(10, 35, 99.1, 99.2, 97.5, 97.6)      # erneutes Displacement
    add(10, 40, 97.6, 98.1, 97.3, 97.9)      # erneutes FVG wird sichtbar
    add(10, 45, 97.9, 98.2, 97.6, 98.0)
    add(10, 50, 98.0, 98.3, 97.8, 98.1)
    add(10, 55, 98.1, 98.4, 97.9, 98.2)
    # ausserhalb des Fensters (Killzone)
    add(11, 0, 98.2, 98.5, 98.0, 98.3)
    add(11, 5, 98.3, 98.6, 98.1, 98.4)

    df = pd.DataFrame(
        [r[1:] for r in rows],
        index=pd.DatetimeIndex([r[0] for r in rows]),
        columns=["open", "high", "low", "close"],
    ).astype(np.float64)
    df["tick_volume"] = rng.integers(50, 150, len(df)).astype(np.float64)
    return df


def run_strategy(df: pd.DataFrame, **overrides) -> list:
    params = {**BASE_PARAMS, **overrides}
    strat = S3SilverBullet(params)
    sigs = []
    for i in range(len(df)):
        s = strat.on_bar({"M5": df}, i)
        if s is not None:
            sigs.append(s)
    return sigs


# ---------------------------------------------------------------------------
# 1. Sweep + MSS + FVG -> genau ein Limit-Signal
# ---------------------------------------------------------------------------
def test_sweep_mss_fvg_erzeugt_genau_ein_limit_signal():
    day = date(2024, 3, 13)  # EDT (UTC-4), DST-Asynchronwoche
    df = build_s3_frame(day)
    sigs = run_strategy(df)
    assert len(sigs) == 1, f"erwartet 1 Signal, got {len(sigs)}"
    s = sigs[0]
    assert s.direction == -1
    assert s.entry_type == "limit"
    assert s.symbol == "NAS100"
    assert s.risk_pct == pytest.approx(0.005)
    assert s.expires_bars == 12
    # Signal auf dem Bestaetigungs-Bar 10:35 ET (kausal): core.smc legt
    # formed_at auf die 3. Bar des FVG-Musters (10:30, Luecke wird sichtbar)
    # und confirmed_at = formed + 1 Bar (SPEC §4.6) -> Signal erst 10:35.
    assert s.time == _ts(day, 10, 35)
    # Entry = 50 % CE der FVG-Zone [99.6, 100.15]
    assert s.entry_price == pytest.approx(99.875)
    # SL hinter Sweep-Extrem (101.4) + 0.3 x ATR
    assert s.stop_loss > 101.4
    assert s.stop_loss < 101.4 + 0.3 * 1.5  # ATR-Puffer plausibel
    # TP = Gegen-Liquiditaet = ref_low 95.8
    assert s.take_profit == pytest.approx(95.8)
    # RR-Gate erfuellt
    rr = (s.entry_price - s.take_profit) / (s.stop_loss - s.entry_price)
    assert rr >= 2.0
    assert s.meta["rr"] == pytest.approx(rr)
    assert s.meta["sweep_extreme"] == pytest.approx(101.4)
    assert s.meta["window"] == "10:00-11:00"


def test_max_ein_trade_pro_fenster_trotz_zweiter_sequenz():
    """Die zweite Displacement+FVG-Sequenz (10:35/10:40) darf kein Signal geben."""
    df = build_s3_frame(date(2024, 3, 13))
    sigs = run_strategy(df)
    assert len(sigs) == 1


def test_rr_gate_blockiert():
    """rr_min=3.0 -> Setup mit RR~2.3 wird abgelehnt."""
    df = build_s3_frame(date(2024, 3, 13))
    sigs = run_strategy(df, rr_min=3.0)
    assert sigs == []


def test_kein_signal_ohne_sweep():
    """Ohne Sweep-Bar kein Trade (Sweep-Regel ist Pflicht-Glied)."""
    df = build_s3_frame(date(2024, 3, 13))
    # Sweep-Bar entschaerfen: High unter ref_high
    sweep_ts = _ts(date(2024, 3, 13), 10, 0)
    df.loc[sweep_ts, "high"] = 100.85
    sigs = run_strategy(df)
    assert sigs == []


# ---------------------------------------------------------------------------
# 2. Kausalitaet: Praefix-Stabilitaet, kein Signal vor Bestaetigung
# ---------------------------------------------------------------------------
def test_kausalitaet_prefix_stabil():
    day = date(2024, 3, 13)
    df = build_s3_frame(day)
    sigs_full = run_strategy(df)
    assert len(sigs_full) == 1
    sig_pos = df.index.get_loc(sigs_full[0].time)
    # kein Signal vor dem Bestaetigungs-Bar
    for cut in range(1, sig_pos + 1):
        assert run_strategy(df.iloc[:cut]) == []
    # abgeschnittene Serie direkt nach Signal-Bar -> identisches Signal
    sigs_cut = run_strategy(df.iloc[: sig_pos + 1])
    assert len(sigs_cut) == 1
    a, b = sigs_full[0], sigs_cut[0]
    assert a.time == b.time
    assert a.entry_price == pytest.approx(b.entry_price)
    assert a.stop_loss == pytest.approx(b.stop_loss)
    assert a.take_profit == pytest.approx(b.take_profit)
    # Shift-Test: zusaetzliche Bars am Ende aendern nichts
    extra = df.copy()
    last = extra.index[-1]
    rows = {}
    px = float(extra["close"].iloc[-1])
    for k in range(1, 8):
        t = last + pd.Timedelta(minutes=5 * k)
        noise = rng.normal(0, 0.05)
        rows[t] = (px, px + 0.2, px - 0.2, px + noise, 100.0)
        px += noise
    ext = pd.DataFrame(
        [r[:4] + (r[4],) for r in rows.values()],
        index=pd.DatetimeIndex(list(rows)),
        columns=["open", "high", "low", "close", "tick_volume"],
    )
    extra = pd.concat([extra, ext])
    sigs_ext = run_strategy(extra)
    assert len(sigs_ext) == 1
    assert sigs_ext[0].time == sigs_full[0].time
    assert sigs_ext[0].entry_price == pytest.approx(sigs_full[0].entry_price)


# ---------------------------------------------------------------------------
# 3. Zeitzone: Fenster in America/New_York, inkl. DST-Asynchronwoche
# ---------------------------------------------------------------------------
def test_fenster_ny_zeit_nicht_utc():
    # Winter (EST, UTC-5): 10:00 ET = 15:00 UTC
    assert _in_window(pd.Timestamp("2024-01-17 15:30", tz=UTC), "America/New_York", "10:00", "11:00")
    assert not _in_window(pd.Timestamp("2024-01-17 14:30", tz=UTC), "America/New_York", "10:00", "11:00")
    # DST-Asynchronwoche (EDT, UTC-4; US seit 10.03., EU erst ab 31.03.):
    # 10:00 ET = 14:00 UTC — NICHT 15:00 UTC
    assert _in_window(pd.Timestamp("2024-03-13 14:30", tz=UTC), "America/New_York", "10:00", "11:00")
    assert not _in_window(pd.Timestamp("2024-03-13 15:30", tz=UTC), "America/New_York", "10:00", "11:00")
    # Fenster-Ende exklusiv
    assert not _in_window(pd.Timestamp("2024-03-13 15:00", tz=UTC), "America/New_York", "10:00", "11:00")


@pytest.mark.parametrize(
    "day, expected_signal_utc",
    # Signal-Zeit = FVG-confirmed_at 10:35 ET (core.smc: confirmed = formed + 1
    # Bar, SPEC §4.6; Luecke wird bereits 10:30 ET sichtbar).
    [
        (date(2024, 1, 17), "2024-01-17 15:35"),  # EST: 10:35 ET = 15:35 UTC
        (date(2024, 3, 13), "2024-03-13 14:35"),  # EDT (Asynchronwoche): 14:35 UTC
        (date(2024, 7, 10), "2024-07-10 14:35"),  # EDT Sommer
    ],
)
def test_signal_zur_ny_lokalzeit_unabhaengig_von_dst(day, expected_signal_utc):
    """Gleiche NY-Lokalzeit-Sequenz -> Signal unabhaengig von der UTC-Verschiebung."""
    df = build_s3_frame(day)
    sigs = run_strategy(df)
    assert len(sigs) == 1
    assert sigs[0].time == pd.Timestamp(expected_signal_utc, tz=UTC)
    assert sigs[0].time.tz_convert(NY).hour == 10
    assert sigs[0].time.tz_convert(NY).minute == 35


# ---------------------------------------------------------------------------
# 3b. Performance-Fix: LOOKBACK_BARS-Deckelung veraendert das Ergebnis nicht
# ---------------------------------------------------------------------------
def test_lookback_bound_matches_unbounded_view(monkeypatch):
    """on_bar() deckelt die an ATR/FVG/Referenz-Level uebergebene View auf
    LOOKBACK_BARS (Performance-Fix gegen O(n^2) bei M5-Mehrjahres-Backtests
    — core.smc.fair_value_gaps ist ein Python-Loop O(len(df)) pro Aufruf).
    Mit > LOOKBACK_BARS Bars unbezogener Vorgeschichte muss die bekannte
    Silver-Bullet-Sequenz aus build_s3_frame() IDENTISCH zur ungedeckelten
    Variante (LOOKBACK_BARS -> sehr gross) ausgeloest werden — die Deckelung
    darf nur Performance, nie das Ergebnis aendern."""
    default_lookback = S3SilverBullet.LOOKBACK_BARS
    day = date(2024, 3, 13)
    real_day = build_s3_frame(day)

    n_noise = default_lookback + 500  # > Deckel, mit Marge
    step = pd.Timedelta(minutes=5)
    # Noise muss auf einem ANDEREN NY-Kalendertag enden als die echte Sequenz,
    # sonst reset't _reset_day() nicht -> Rauschen kann self._sweep/
    # _trades_today kontaminieren (Tages-State ueberlebt sonst in den echten
    # Tag hinein — reines Test-Artefakt, keine Strategie-Aussage).
    end = _ts(day - timedelta(days=1), 23, 55)
    start = end - step * (n_noise - 1)
    idx = pd.date_range(start, end, freq=step, tz=UTC)
    # Ruhig oszillierende Bars (TR ~0.4), gleiche Groessenordnung wie
    # build_s3_frame()s eigene 08:00-Stunde — ein hochvolatiler Random-Walk
    # wuerde den ATR(20) an der echten Sequenz anheben und deren eigene,
    # knapp bemessene FVG-Min-Groesse (0.3xATR) verfehlen; das waere ein
    # Artefakt der Rausch-Wahl, keine Aussage ueber die Deckelung selbst.
    level = 100.0 + 0.2 * np.sin(np.arange(n_noise) / 7.0)
    noise = pd.DataFrame(
        {"open": level, "high": level + 0.2, "low": level - 0.2,
         "close": level, "tick_volume": 100.0},
        index=idx,
    )
    df = pd.concat([noise[real_day.columns], real_day])
    assert df.index.is_monotonic_increasing
    assert not df.index.duplicated().any()

    def run(lookback: int) -> list:
        monkeypatch.setattr(S3SilverBullet, "LOOKBACK_BARS", lookback)
        return run_strategy(df)

    sigs_bounded = run(default_lookback)
    sigs_unbounded = run(10**9)
    assert len(sigs_bounded) == 1  # bekannte Sequenz aus build_s3_frame()
    assert sigs_bounded == sigs_unbounded


# ---------------------------------------------------------------------------
# 4. Smoke-Import core-Module (xfail solange parallel entwickelt)
# ---------------------------------------------------------------------------
def test_core_module_importierbar():
    try:
        import core.indicators  # noqa: F401
        import core.smc  # noqa: F401
        import core.time_engine  # noqa: F401
    except ImportError:
        pytest.xfail("core-Module noch nicht vorhanden (parallele Entwicklung)")
