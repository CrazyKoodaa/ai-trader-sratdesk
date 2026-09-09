"""Unit-Tests S6 — FixReversal (WM/Reuters 4pm London Fix Reversal) auf
handgebauten Mini-Serien.

- Pre-Fix-Move >= trigger_threshold x ATR erzeugt ein Fade-Market-Signal mit
  exakt handgerechnetem SL/TP (Wilder-ATR auf konstantem True-Range-Rauschen
  konvergiert exakt, siehe build_day()-Kommentar).
- Kein Signal, wenn der Pre-Fix-Move unter der Schwelle bleibt.
- Kausalitaet: Praefix-Stabilitaet (kein Signal vor der Fix-Bar, Signal auf
  abgeschnittener/erweiterter Serie identisch).
- Zeitzone: 16:00 Europe/London ist Lokalzeit, DST-sicher (zoneinfo) — die
  UTC-Bar-Zeit des Fixes verschiebt sich BST/GMT um eine Stunde, das
  Verhalten (SL/TP/Richtung) bleibt exakt identisch.
- Performance-Regression: LOOKBACK_BARS-Deckelung der an atr() uebergebenen
  View aendert das Ergebnis nicht, auch mit > LOOKBACK_BARS Bars
  unbezogener Vorgeschichte (Muster wie
  tests/test_s3.py::test_lookback_bound_matches_unbounded_view).
Synthetische Daten inline (kein core.fixtures noetig, deterministisch).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from strategies.s6_fix_reversal import S6FixReversal

LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

BASE_PARAMS = dict(
    symbol="GBPUSD",
    risk_pct=0.005,
    min_rr=0.5,
    pre_window_min=15,
    trigger_threshold=1.0,
    stop_buffer=0.3,
    target_r=1.0,
    max_hold_min=30,
    atr_len=20,
    use_news_filter=False,
)

# Fix-Fenster der Rally-Sequenz (London-Lokalzeit): 3 Bars a 5 Min
# (15:45/15:50/15:55), Fix-Bar = 15:55 (schliesst 16:00 lokal).
RALLY_WINDOW = [
    (15, 45, 100.00, 100.30, 99.95, 100.20),
    (15, 50, 100.20, 100.55, 100.15, 100.45),
    (15, 55, 100.45, 100.90, 100.40, 100.80),
]
# Netto-Move = 100.80 - 100.00 = 0.80; window_high = 100.90 (Stop-Referenz
# fuer den Short-Fade), window_low = 99.95.

# Sell-off-Spiegelbild von RALLY_WINDOW um das Niveau 100.0 (open/close
# und high/low vertauscht reflektiert: reflect(v) = 200.0 - v) — identische
# True-Range-Betraege je Bar, daher exakt dieselbe ATR-Sequenz wie bei
# RALLY_WINDOW (0.10 -> 0.1125 -> 0.126875 -> 0.14553125), nur mit
# umgekehrtem Vorzeichen der Bewegung.
DOWN_WINDOW = [
    (15, 45, 100.00, 100.05, 99.70, 99.80),
    (15, 50, 99.80, 99.85, 99.45, 99.55),
    (15, 55, 99.55, 99.60, 99.10, 99.20),
]
# Netto-Move = 99.20 - 100.00 = -0.80; window_low = 99.10 (Stop-Referenz
# fuer den Long-Fade).

FLAT_WINDOW = [
    (15, 45, 100.00, 100.05, 99.98, 100.02),
    (15, 50, 100.02, 100.06, 99.99, 100.03),
    (15, 55, 100.03, 100.07, 100.00, 100.04),
]
# Netto-Move = 100.04 - 100.00 = 0.04 -> weit unter jeder plausiblen
# ATR-Schwelle (ATR bleibt in der Groessenordnung 0.10-0.15, s.u.).


def _ts_london(day: date, hh: int, mm: int) -> pd.Timestamp:
    """Lokale London-Zeit -> UTC-Timestamp (DST-sicher via zoneinfo)."""
    return pd.Timestamp(datetime(day.year, day.month, day.day, hh, mm), tz=LONDON).tz_convert(UTC)


def build_day(day: date, window: list[tuple], n_warmup: int = 40) -> pd.DataFrame:
    """Ein London-Handelstag: n_warmup ruhige Bars + Pre-Fix-Fenster (3 Bars).

    Die Warmup-Bars haben eine KONSTANTE True Range von exakt 0.10
    (open=close=level=100.0, high=level+0.05, low=level-0.05; erste Bar
    nutzt high-low, jede Folgebar |high/low - prev_close| < high-low). Mit
    >= atr_len (20) solcher Bars ist der Wilder-Seed (SMA der ersten n
    TR-Werte) EXAKT 0.10, und die Rekursion auf weiterem TR=0.10 bleibt
    EXAKT 0.10 (Fixpunkt einer Wilder-Glaettung auf konstantem Input) — die
    ATR-Werte in den Assertions sind daher exakt von Hand nachrechenbar
    (keine Konvergenz-Naeherung noetig), siehe
    test_ausloesung_long_short_mit_exaktem_sl_tp().
    """
    rows: list[tuple] = []
    start = _ts_london(day, 15, 45) - pd.Timedelta(minutes=5 * n_warmup)
    level = 100.0
    for k in range(n_warmup):
        t = start + pd.Timedelta(minutes=5 * k)
        rows.append((t, level, level + 0.05, level - 0.05, level))
    for hh, mm, o, h, l, c in window:
        rows.append((_ts_london(day, hh, mm), o, h, l, c))
    df = pd.DataFrame(
        [r[1:] for r in rows],
        index=pd.DatetimeIndex([r[0] for r in rows]),
        columns=["open", "high", "low", "close"],
    ).astype(np.float64)
    df["tick_volume"] = 100.0
    return df


def run_strategy(df: pd.DataFrame, **overrides) -> list:
    params = {**BASE_PARAMS, **overrides}
    strat = S6FixReversal(params)
    sigs = []
    for i in range(len(df)):
        s = strat.on_bar({"M5": df}, i)
        if s is not None:
            sigs.append(s)
    return sigs


# ---------------------------------------------------------------------------
# 1. Ausloesung: Rally in den Fix -> Short-Fade, exakt handgerechnetes SL/TP
# ---------------------------------------------------------------------------
def test_ausloesung_long_short_mit_exaktem_sl_tp():
    """Hand-Rechnung (n=atr_len=20, alpha=1/n):
    ATR direkt vor dem Fenster (Warmup) = 0.10 exakt (Fixpunkt).
    TR(15:45) = max(0.35, |100.30-100.00|=0.30, |99.95-100.00|=0.05) = 0.35
      -> atr = (0.10*19 + 0.35) / 20 = 0.1125
    TR(15:50) = max(0.40, |100.55-100.20|=0.35, |100.15-100.20|=0.05) = 0.40
      -> atr = (0.1125*19 + 0.40) / 20 = 0.126875
    TR(15:55) = max(0.50, |100.90-100.45|=0.45, |100.40-100.45|=0.05) = 0.50
      -> atr = (0.126875*19 + 0.50) / 20 = 0.14553125
    net_move = 100.80 - 100.00 = 0.80 >= 1.0 x 0.14553125 -> Trigger.
    Rally -> Fade Short: sl = window_high(100.90) + 0.3 x 0.14553125
           = 100.943659375
    risk = sl - fix_close = 100.943659375 - 100.80 = 0.143659375
    tp = fix_close - 1.0 x risk = 100.656340625 (target_r=1.0 -> RR=1.0)
    """
    day = date(2024, 3, 13)
    df = build_day(day, RALLY_WINDOW)
    sigs = run_strategy(df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.time == _ts_london(day, 15, 55)
    assert s.symbol == "GBPUSD"
    assert s.direction == -1               # Fade der Rally
    assert s.entry_type == "market"
    assert s.entry_price is None           # Fill = Open der naechsten Bar (Engine)
    assert s.risk_pct == pytest.approx(0.005)
    assert s.meta["atr"] == pytest.approx(0.14553125)
    assert s.meta["net_move"] == pytest.approx(0.80)
    assert s.stop_loss == pytest.approx(100.943659375)
    assert s.take_profit == pytest.approx(100.656340625)
    rr = (s.meta["fix_close"] - s.take_profit) / (s.stop_loss - s.meta["fix_close"])
    assert rr == pytest.approx(1.0)
    assert s.meta["rr"] == pytest.approx(1.0)
    assert s.meta["time_exit_bars"] == 6   # max_hold_min=30 / 5 Min je M5-Bar


def test_ausloesung_sell_off_erzeugt_long_fade():
    """Sell-off in den Fix -> Long-Fade (Vorzeichen-Spiegelbild von Test 1):
    identische ATR-Sequenz (0.14553125), sl = window_low(99.10) - 0.3xATR
    = 99.056340625, tp = fix_close(99.20) + 1.0x risk = 99.343659375."""
    day = date(2024, 3, 13)
    df = build_day(day, DOWN_WINDOW)
    sigs = run_strategy(df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == 1
    assert s.meta["atr"] == pytest.approx(0.14553125)
    assert s.meta["net_move"] == pytest.approx(-0.80)
    assert s.stop_loss == pytest.approx(99.056340625)
    assert s.take_profit == pytest.approx(99.343659375)
    assert s.stop_loss < s.meta["fix_close"]
    assert s.take_profit > s.meta["fix_close"]


# ---------------------------------------------------------------------------
# 2. Kein Signal unterhalb der Trigger-Schwelle
# ---------------------------------------------------------------------------
def test_kein_signal_unter_trigger_schwelle():
    day = date(2024, 3, 13)
    df = build_day(day, FLAT_WINDOW)
    assert run_strategy(df) == []


def test_trigger_threshold_param_veraendert_schwelle():
    """Netto-Move 0.80 mit ATR ~0.145 -> bei trigger_threshold=6.0 (Schwelle
    ~0.87) kein Trade mehr, bei 1.0 (Default oben) sehr wohl."""
    day = date(2024, 3, 13)
    df = build_day(day, RALLY_WINDOW)
    assert run_strategy(df, trigger_threshold=6.0) == []
    assert len(run_strategy(df, trigger_threshold=1.0)) == 1


# ---------------------------------------------------------------------------
# 3. RR-Gate
# ---------------------------------------------------------------------------
def test_rr_gate_blockiert():
    day = date(2024, 3, 13)
    df = build_day(day, RALLY_WINDOW)
    sigs = run_strategy(df, target_r=1.0, min_rr=1.5)  # rr==target_r==1.0 < 1.5
    assert sigs == []
    assert len(run_strategy(df, target_r=1.0, min_rr=0.5)) == 1


# ---------------------------------------------------------------------------
# 4. Max 1 Trade/Tag
# ---------------------------------------------------------------------------
def test_max_ein_trade_pro_tag():
    day1 = date(2024, 3, 13)
    day2 = date(2024, 3, 14)
    df = pd.concat([build_day(day1, RALLY_WINDOW), build_day(day2, RALLY_WINDOW)])
    sigs = run_strategy(df)
    assert len(sigs) == 2  # je Tag genau 1
    assert [s.time.date() for s in sigs] == [day1, day2]


# ---------------------------------------------------------------------------
# 5. Kausalitaet: Praefix-Stabilitaet
# ---------------------------------------------------------------------------
def test_kausalitaet_prefix_stabil():
    day = date(2024, 3, 13)
    df = build_day(day, RALLY_WINDOW)
    sigs_full = run_strategy(df)
    assert len(sigs_full) == 1
    sig_pos = df.index.get_loc(sigs_full[0].time)

    # kein Signal vor der Fix-Bar
    assert run_strategy(df.iloc[:sig_pos]) == []

    # abgeschnitten direkt nach der Fix-Bar -> identisches Signal
    sigs_cut = run_strategy(df.iloc[: sig_pos + 1])
    assert len(sigs_cut) == 1
    a, b = sigs_full[0], sigs_cut[0]
    assert a.time == b.time
    assert a.stop_loss == pytest.approx(b.stop_loss)
    assert a.take_profit == pytest.approx(b.take_profit)

    # Shift-Test: zusaetzliche Bars (naechster Handelstag) aendern das
    # bereits gefundene erste Signal nicht
    day2 = date(2024, 3, 14)
    extra = pd.concat([df, build_day(day2, RALLY_WINDOW)])
    sigs_ext = run_strategy(extra)
    assert sigs_ext[0].time == sigs_full[0].time
    assert sigs_ext[0].stop_loss == pytest.approx(sigs_full[0].stop_loss)
    assert sigs_ext[0].take_profit == pytest.approx(sigs_full[0].take_profit)


# ---------------------------------------------------------------------------
# 6. Zeitzone: 16:00 Europe/London ist Lokalzeit, DST-sicher
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "day, expected_fix_utc",
    # UK-DST-Wechsel 2024: letzter Sonntag im Maerz (31.03.) und Oktober
    # (27.10., hier nicht gebraucht) — ANDERE Daten als der US-DST-Wechsel
    # (10.03.). Fix-Bar (15:55-16:00 London-Lokalzeit) schliesst je nach
    # Jahreszeit auf einer anderen UTC-Stunde:
    [
        (date(2024, 1, 17), "2024-01-17 15:55"),  # GMT (Winter): UTC+0
        (date(2024, 3, 27), "2024-03-27 15:55"),  # GMT, unmittelbar VOR dem
                                                    # UK-Wechsel (31.03.)
        (date(2024, 4, 3), "2024-04-03 14:55"),   # BST, unmittelbar NACH
                                                    # dem UK-Wechsel: 1h frueher in UTC
        (date(2024, 7, 10), "2024-07-10 14:55"),  # BST (Sommer): UTC+1
    ],
)
def test_signal_zur_london_lokalzeit_unabhaengig_von_dst(day, expected_fix_utc):
    """Gleiche London-Lokalzeit-Sequenz -> identisches SL/TP, nur die
    UTC-Bar-Zeit des Signals verschiebt sich BST/GMT um eine Stunde."""
    df = build_day(day, RALLY_WINDOW)
    sigs = run_strategy(df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.time == pd.Timestamp(expected_fix_utc, tz=UTC)
    # Lokalzeit bleibt in jedem Fall 15:55 (Fix-Bar-Open, schliesst 16:00)
    assert s.time.tz_convert(LONDON).hour == 15
    assert s.time.tz_convert(LONDON).minute == 55
    assert s.stop_loss == pytest.approx(100.943659375)
    assert s.take_profit == pytest.approx(100.656340625)


# ---------------------------------------------------------------------------
# 7. Performance-Regression: LOOKBACK_BARS-Deckelung veraendert Ergebnis nicht
# ---------------------------------------------------------------------------
def test_lookback_bound_matches_unbounded_view(monkeypatch):
    """on_bar() deckelt die an atr() (und den Pre-Fix-Fenster-Scan)
    uebergebene View auf LOOKBACK_BARS, statt df.iloc[:i+1] unbegrenzt zu
    verwenden — auch wenn core.indicators.atr() selbst vektorisiert ist,
    waechst eine ungedeckelte View mit wachsendem i linear, und die
    Gesamtkosten ueber alle Fix-Events (~1 pro Handelstag) blieben ohne
    Deckelung quadratisch in der Bar-Anzahl. Mit > LOOKBACK_BARS Bars
    unbezogener Vorgeschichte muss die bekannte Rally-Sequenz aus
    build_day() IDENTISCH zur (quasi) ungedeckelten Variante
    (LOOKBACK_BARS -> sehr gross) ausgeloest werden — die Deckelung darf
    nur Performance, nie das Ergebnis aendern (Muster wie
    tests/test_s3.py::test_lookback_bound_matches_unbounded_view)."""
    default_lookback = S6FixReversal.LOOKBACK_BARS
    day = date(2024, 3, 13)
    real_day = build_day(day, RALLY_WINDOW)

    n_noise = default_lookback + 500  # > Deckel, mit Marge
    step = pd.Timedelta(minutes=5)
    # Noise endet auf einem ANDEREN London-Kalendertag als die echte
    # Sequenz, sonst kontaminiert er den Tages-State (_day/_traded_today)
    # nur als Test-Artefakt, keine Strategie-Aussage (wie test_s3.py).
    end = _ts_london(day - timedelta(days=1), 23, 55)
    start = end - step * (n_noise - 1)
    idx = pd.date_range(start, end, freq=step, tz=UTC)
    # Ruhig oszillierende Bars, gleiche Groessenordnung wie build_day()s
    # eigene Warmup-Bars (TR ~0.1-0.4) — verhindert, dass ein
    # hochvolatiler Random-Walk den ATR(20) an der echten Sequenz so weit
    # anhebt, dass die knapp bemessene Trigger-Schwelle (1.0 x ATR gegen
    # net_move=0.80) verfehlt wird; das waere ein Artefakt der Rausch-Wahl,
    # keine Aussage ueber die Deckelung selbst.
    level = 100.0 + 0.2 * np.sin(np.arange(n_noise) / 7.0)
    noise = pd.DataFrame(
        {"open": level, "high": level + 0.2, "low": level - 0.2,
         "close": level, "tick_volume": 100.0},
        index=idx,
    )
    df = pd.concat([noise[real_day.columns], real_day])
    assert df.index.is_monotonic_increasing
    assert not df.index.duplicated().any()
    assert len(df) > default_lookback

    def run(lookback: int) -> list:
        monkeypatch.setattr(S6FixReversal, "LOOKBACK_BARS", lookback)
        return run_strategy(df)

    t0 = time.time()
    sigs_bounded = run(default_lookback)
    elapsed = time.time() - t0
    sigs_unbounded = run(10**9)

    assert len(sigs_bounded) == 1  # bekannte Sequenz aus build_day()
    assert [(s.time, s.stop_loss, s.take_profit) for s in sigs_bounded] == \
           [(s.time, s.stop_loss, s.take_profit) for s in sigs_unbounded]
    # Grobe Performance-Wache: ein einzelner Bar-Loop ueber ~2500 Bars mit
    # gedeckelter View darf keinesfalls in den Sekundenbereich laufen
    # (die O(n^2)-Regression aus s3_silver_bullet.py brauchte Stunden statt
    # Minuten bei 500k+ Bars — hier reicht ein grosszuegiges Zeitbudget als
    # Rauchmelder, kein straffes Benchmark).
    assert elapsed < 10.0


# ---------------------------------------------------------------------------
# 8. News-Filter (optional injizierbar, Muster wie s5_filtered_mr.py)
# ---------------------------------------------------------------------------
class _NewsBlockAtWindowStart:
    def is_blackout(self, ts_utc, symbol) -> bool:
        return True

    def tier1_halt(self, ts_utc) -> bool:
        return False


def test_news_filter_blockiert_setup_im_pre_fix_fenster():
    day = date(2024, 3, 13)
    df = build_day(day, RALLY_WINDOW)
    sigs = run_strategy(df, use_news_filter=True, news_filter_obj=_NewsBlockAtWindowStart())
    assert sigs == []
    # Filter aus (Default in BASE_PARAMS) -> Setup feuert wieder
    assert len(run_strategy(df, use_news_filter=False,
                            news_filter_obj=_NewsBlockAtWindowStart())) == 1
