"""tests/test_risk.py — Sizing, Prop-Profile, Circuit-Breaker (SPEC §4.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
import yaml

from core.risk import RiskConfig, RiskManager, calc_lots, load_prop_profile


def utc(y, mo, d, h, mi=0):
    return pd.Timestamp(datetime(y, mo, d, h, mi, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------
class TestCalcLots:
    def test_exact(self):
        # risk 100 / (50 pts * 1.0) = 2.0 lots
        assert calc_lots(100.0, 50.0, 1.0) == 2.0

    def test_rounds_down_to_step(self):
        # raw = 100 / (30*1) = 3.333 -> 3.3 bei step 0.1
        assert calc_lots(100.0, 30.0, 1.0, volume_step=0.1) == pytest.approx(3.3)
        # step 1.0 -> 3
        assert calc_lots(100.0, 30.0, 1.0, volume_step=1.0) == 3.0

    def test_clamps_min_max(self):
        assert calc_lots(0.0001, 50.0, 1.0, volume_step=0.01,
                         volume_min=0.01, volume_max=100.0) == 0.01
        assert calc_lots(1e9, 1.0, 1.0, volume_step=0.01,
                         volume_min=0.01, volume_max=50.0) == 50.0

    def test_invalid_sl(self):
        with pytest.raises(ValueError):
            calc_lots(100.0, 0.0, 1.0)
        with pytest.raises(ValueError):
            calc_lots(100.0, -5.0, 1.0)

    def test_manager_sizing_uses_risk_pct(self):
        rm = RiskManager(RiskConfig(risk_per_trade_pct=0.5), initial_balance=10_000)
        # risk_amount = 50; sl 25 pts, point_value 2 -> 50/(25*2) = 1.0
        lots = rm.calc_lots(10_000, entry_price=100.0, stop_loss=75.0, point_value=2.0)
        assert lots == 1.0


# ---------------------------------------------------------------------------
# Prop-Profile (YAML)
# ---------------------------------------------------------------------------
class TestPropProfiles:
    def test_none(self):
        assert load_prop_profile("none") == {}

    def test_builtin_default(self):
        p = load_prop_profile("ftmo_2step")
        assert p["daily_loss_pct"] == 5.0
        assert p["daily_loss_basis"] == "prev_day_balance"
        assert p["overall_loss_pct"] == 10.0

    def test_from_yaml(self, tmp_path):
        cfg_dir = tmp_path / "configs"
        cfg_dir.mkdir()
        payload = {
            "daily_loss_pct": 4.0,
            "overall_loss_pct": 8.0,
            "profit_target_pct": 6.0,
            "leverage": 50,
            "news_blackout_min_before": 5,
            "news_blackout_min_after": 3,
        }
        (cfg_dir / "prop_acme.yaml").write_text(yaml.safe_dump(payload))
        p = load_prop_profile("acme", config_dir=cfg_dir)
        assert p["daily_loss_pct"] == 4.0
        assert p["leverage"] == 50
        assert p["daily_loss_basis"] == "prev_day_balance"  # Default ergaenzt

    def test_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_prop_profile("does_not_exist", config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Daily-Loss-Halt (Basis: Vortages-Bilanz, Reset 00:00 Server-Tag)
# ---------------------------------------------------------------------------
class TestDailyLossHalt:
    def _rm(self, **kw):
        cfg = RiskConfig(daily_loss_halt_pct=2.0, eod_flat=False, friday_flat=False)
        return RiskManager(cfg, initial_balance=100_000, **kw)

    def test_halt_on_floating_loss(self):
        rm = self._rm()
        t = utc(2024, 1, 2, 10)  # Dienstag
        rm.update(t, 100_000, floating_pnl=0)
        assert rm.can_open(t)
        # Equity (inkl. Floating) 2 % unter Tagesstart-Bilanz
        rm.update(t, 100_000, floating_pnl=-2_100)
        assert rm.daily_halt
        assert not rm.can_open(t)

    def test_reset_next_server_day(self):
        rm = self._rm()
        rm.update(utc(2024, 1, 2, 10), 100_000, 0)  # Tagesstart-Basis 100k
        rm.update(utc(2024, 1, 2, 23), 98_000, 0)   # -2 % Tag 1 -> Halt
        assert rm.daily_halt
        # Neuer Server-Tag (00:00 UTC): Reset, Basis = Vortages-Bilanz 98k
        t2 = utc(2024, 1, 3, 0, 1)
        rm.update(t2, 98_000, 0)
        assert not rm.daily_halt
        assert rm.can_open(t2)
        assert rm.day_start_balance == 98_000

    def test_server_day_offset(self):
        # Server-Tag = UTC+2h: UTC 22:30 gehoert schon zum naechsten Server-Tag
        rm = self._rm(server_day_offset_hours=2.0)
        assert rm.server_day(utc(2024, 1, 2, 22, 30)) == datetime(2024, 1, 3).date()
        assert rm.server_day(utc(2024, 1, 2, 21, 30)) == datetime(2024, 1, 2).date()

    def test_halt_basis_prev_day_balance_not_intraday_high(self):
        rm = self._rm()
        rm.update(utc(2024, 1, 2, 9), 100_000, 0)
        rm.update(utc(2024, 1, 2, 12), 101_000, 0)   # Gewinn zwischendurch
        # Rueckgang auf 98.5k = -1.5 % vs Tagesstart-Basis -> KEIN Halt
        rm.update(utc(2024, 1, 2, 15), 98_500, 0)
        assert not rm.daily_halt


# ---------------------------------------------------------------------------
# EOD-Flat (NY-Zeit) / Friday-Flat — inkl. DST
# ---------------------------------------------------------------------------
class TestFlatRules:
    def _rm(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=True,
                         eod_flat_time_ny="16:55", friday_flat=True)
        return RiskManager(cfg, initial_balance=100_000)

    def test_eod_flat_ny_winter(self):
        rm = self._rm()
        # Januar: EST = UTC-5 -> 16:55 NY = 21:55 UTC
        assert not rm.force_flat(utc(2024, 1, 3, 21, 54))  # Mittwoch
        assert rm.force_flat(utc(2024, 1, 3, 21, 55))

    def test_eod_flat_ny_summer_dst(self):
        rm = self._rm()
        # Juli: EDT = UTC-4 -> 16:55 NY = 20:55 UTC
        assert not rm.force_flat(utc(2024, 7, 3, 20, 54))
        assert rm.force_flat(utc(2024, 7, 3, 20, 55))

    def test_friday_flat(self):
        rm = self._rm()
        # Freitag (NY) nach EOD-Zeit -> flat; Donnerstag VOR EOD-Zeit nicht
        assert rm.force_flat(utc(2024, 1, 5, 22, 0))    # Fr 17:00 EST
        assert not rm.force_flat(utc(2024, 1, 4, 20, 0))  # Do 15:00 EST

    def test_no_new_entries_after_eod(self):
        rm = self._rm()
        rm.update(utc(2024, 1, 3, 20, 0), 100_000, 0)
        assert rm.can_open(utc(2024, 1, 3, 20, 0))
        assert not rm.can_open(utc(2024, 1, 3, 22, 0))  # nach 16:55 NY


# ---------------------------------------------------------------------------
# eod_flat_time_utc — feste Trade-Desk-UTC-Zeit statt NY-Lokalzeit (Bug-Fix:
# S4-Config setzte diesen Schluessel, RiskConfig hatte ihn nicht -> wurde
# von build_backtest_config() stillschweigend gefiltert, Default 16:55 NY
# griff ungewollt).
# ---------------------------------------------------------------------------
class TestFlatRulesUtcFixed:
    def _rm(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=True,
                         eod_flat_time_utc="21:00", friday_flat=True)
        return RiskManager(cfg, initial_balance=100_000)

    def test_fixed_utc_time_no_dst_shift(self):
        rm = self._rm()
        # 21:00 UTC ist 21:00 UTC — Winter UND Sommer identisch (anders als
        # eod_flat_time_ny, das mit der DST-Verschiebung wandert).
        assert not rm.force_flat(utc(2024, 1, 3, 20, 59))
        assert rm.force_flat(utc(2024, 1, 3, 21, 0))
        assert not rm.force_flat(utc(2024, 7, 3, 20, 59))
        assert rm.force_flat(utc(2024, 7, 3, 21, 0))

    def test_friday_uses_utc_weekday_not_ny(self):
        rm = self._rm()
        # Sa 00:30 UTC = Fr 19:30 EST (NY) — im NY-Modus waere das noch
        # Freitag; im UTC-Modus zaehlt der UTC-Wochentag (Samstag), also
        # KEIN Friday-Flat (eod_flat greift natuerlich trotzdem taeglich).
        rm2 = RiskManager(RiskConfig(daily_loss_halt_pct=0, eod_flat=False,
                                     eod_flat_time_utc="21:00", friday_flat=True),
                          initial_balance=100_000)
        assert not rm2.force_flat(utc(2024, 1, 6, 0, 30))  # Sa UTC

    def test_eod_flat_time_utc_takes_precedence_over_ny(self):
        # Wenn beide gesetzt sind, gewinnt eod_flat_time_utc (S4-Fall).
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=True,
                         eod_flat_time_ny="16:55", eod_flat_time_utc="21:00",
                         friday_flat=True)
        rm = RiskManager(cfg, initial_balance=100_000)
        assert rm._eod_use_utc
        assert (rm._eod_hh, rm._eod_mm) == (21, 0)

    def test_force_flat_gap_uses_utc_deadline(self):
        rm = self._rm()
        # Letzte Bar Fr 20:00 UTC (vor der 21:00-UTC-Deadline), naechste Bar
        # So 20:00 UTC (ebenfalls vor der eigenen Sonntags-Deadline) — die
        # Freitags-Deadline (21:00 UTC) faellt dazwischen.
        prev = utc(2024, 1, 5, 20, 0)
        cur = utc(2024, 1, 7, 20, 0)
        assert not rm.force_flat(cur)
        assert rm.force_flat_gap(prev, cur)


# ---------------------------------------------------------------------------
# force_flat_gap — Bug-Fix: Deadline stillschweigend zwischen zwei Bars
# verschluckt (Wochenend-Luecke), s. reports/gates_matrix_s1_s5.md (S4)
# ---------------------------------------------------------------------------
class TestForceFlatGap:
    def _rm(self, **kw):
        defaults = dict(daily_loss_halt_pct=0, eod_flat=True,
                        eod_flat_time_ny="16:55", friday_flat=True)
        defaults.update(kw)
        return RiskManager(RiskConfig(**defaults), initial_balance=100_000)

    def test_weekend_gap_swallows_friday_deadline(self):
        rm = self._rm()
        # Fr 5.1.2024 15:00 EST (20:00 UTC, VOR der 16:55-NY-Deadline) ->
        # So 7.1.2024 15:00 EST (20:00 UTC, ebenfalls vor der eigenen
        # Sonntags-Deadline). Die Freitags-Deadline (21:55 UTC) faellt
        # dazwischen, ohne dass eine Bar direkt darauf liegt.
        prev = utc(2024, 1, 5, 20, 0)
        cur = utc(2024, 1, 7, 20, 0)
        assert not rm.force_flat(cur)  # der normale Pfad sieht es nicht
        assert rm.force_flat_gap(prev, cur)

    def test_no_gap_same_day(self):
        rm = self._rm()
        # Normaler stuendlicher Bar-Uebergang weit vor der Deadline.
        assert not rm.force_flat_gap(utc(2024, 1, 3, 10, 0), utc(2024, 1, 3, 11, 0))

    def test_no_double_trigger_on_normal_adjacent_bar(self):
        """Regression (KORRIGIERT, siehe Docstring von force_flat_gap): der
        Guard darf NICHT ``not force_flat(cur)`` sein, sondern muss an der
        tatsaechlichen Luecke haengen (bar_interval). Bei einem normalen
        Ein-Bar-Schritt (hier 1h, kein Gap) — selbst wenn ``cur`` bereits
        selbst ueber der Deadline liegt — deckt der bestehende
        force_flat(t_open)-Pfad das schon ab, force_flat_gap muss False
        liefern, wenn bar_interval das als Nicht-Luecke erkennt."""
        rm = self._rm()
        prev = utc(2024, 1, 5, 21, 0)
        cur = utc(2024, 1, 5, 22, 0)  # Freitag, genau 1 Bar spaeter, selbst schon nach der Deadline
        assert rm.force_flat(cur)
        assert not rm.force_flat_gap(prev, cur, bar_interval=pd.Timedelta(hours=1))

    def test_gap_still_fires_even_when_current_bar_already_past_deadline(self):
        """Der eigentliche Bug (erster Fix-Versuch, jetzt behoben): nach
        einer echten Luecke (Wochenende) ist die aktuelle Bar so gut wie
        immer selbst schon ueber der Deadline — das darf den Gap-Trigger
        NICHT unterdruecken, sonst wird exakt der S4-Ausreisser (-4.79R,
        reports/gates_matrix_s1_s5.md) wieder reproduziert. Nutzt bewusst
        eod_flat_time_utc (die tatsaechliche S4-Konfiguration, an der der
        erste Fix-Versuch nachweislich scheiterte — 21:00 UTC Deadline
        trifft fast jede Wochenend-Wiedereroeffnungs-Bar trivial)."""
        rm = RiskManager(RiskConfig(daily_loss_halt_pct=0, eod_flat=True,
                                    eod_flat_time_utc="21:00", friday_flat=True),
                         initial_balance=100_000)
        prev = utc(2024, 1, 5, 20, 0)   # letzte Bar vor dem Wochenende (Freitag)
        cur = utc(2024, 1, 7, 21, 0)    # Sonntag-Wiedereroeffnung, selbst schon >= 21:00-Deadline
        assert rm.force_flat(cur)  # trivial wahr — genau das Problem
        assert rm.force_flat_gap(prev, cur, bar_interval=pd.Timedelta(hours=1))
        assert rm.force_flat_gap(prev, cur)  # auch ohne bar_interval (Tages-Luecke ist unmissverstaendlich)

    def test_none_prev_returns_false(self):
        rm = self._rm()
        assert not rm.force_flat_gap(None, utc(2024, 1, 5, 20, 0))

    def test_multi_day_gap_with_eod_flat_only(self):
        # Nur eod_flat (kein friday_flat): eine mehrtaegige Luecke (z.B.
        # Feiertag) muss trotzdem jeden uebersprungenen Tag pruefen, nicht
        # nur Freitage.
        rm = self._rm(friday_flat=False)
        prev = utc(2024, 1, 4, 20, 0)   # Donnerstag, vor der Deadline
        cur = utc(2024, 1, 8, 20, 0)    # Montag, vor der eigenen Deadline
        assert not rm.force_flat(cur)
        assert rm.force_flat_gap(prev, cur)  # Freitags eigene taegliche Deadline verpasst

    def test_no_gap_when_disabled(self):
        rm = self._rm(eod_flat=False, friday_flat=False)
        prev = utc(2024, 1, 5, 20, 0)
        cur = utc(2024, 1, 7, 20, 0)
        assert not rm.force_flat_gap(prev, cur)


# ---------------------------------------------------------------------------
# Streak-Limiter & max_concurrent
# ---------------------------------------------------------------------------
class TestStreakLimiter:
    def test_pause_bis_naechster_tag(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=False,
                         friday_flat=False, streak_limiter=2)
        rm = RiskManager(cfg, initial_balance=100_000)
        t = utc(2024, 1, 2, 10)
        rm.update(t, 100_000, 0)
        rm.register_closed_trade(-100, t)
        assert rm.can_open(t)
        rm.register_closed_trade(-50, t)  # 2 in Folge -> Pause
        assert not rm.can_open(t)
        assert not rm.can_open(utc(2024, 1, 2, 23))
        # Naechster Server-Tag: wieder erlaubt
        t2 = utc(2024, 1, 3, 1)
        rm.update(t2, 99_850, 0)
        assert rm.can_open(t2)

    def test_win_resets_streak(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=False,
                         friday_flat=False, streak_limiter=2)
        rm = RiskManager(cfg, initial_balance=100_000)
        t = utc(2024, 1, 2, 10)
        rm.update(t, 100_000, 0)
        rm.register_closed_trade(-100, t)
        rm.register_closed_trade(+200, t)
        rm.register_closed_trade(-100, t)
        assert rm.can_open(t)  # Streak = 1 < 2

    def test_max_concurrent(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=False,
                         friday_flat=False, max_concurrent=1)
        rm = RiskManager(cfg, initial_balance=100_000)
        t = utc(2024, 1, 2, 10)
        rm.update(t, 100_000, 0)
        assert rm.can_open(t, open_positions=0)
        assert not rm.can_open(t, open_positions=1)


# ---------------------------------------------------------------------------
# Prop-Breach (hart, kein Reset)
# ---------------------------------------------------------------------------
class TestPropBreach:
    def test_daily_breach_hard(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=False, friday_flat=False)
        profile = {"daily_loss_pct": 5.0, "overall_loss_pct": 10.0}
        rm = RiskManager(cfg, initial_balance=100_000, prop_profile=profile)
        t = utc(2024, 1, 2, 10)
        rm.update(t, 100_000, 0)
        rm.update(t, 100_000, floating_pnl=-5_500)  # -5.5 % Floating
        assert rm.prop_breached
        assert rm.prop_breach_reason == "daily_loss"
        assert not rm.can_open(t)
        assert rm.force_flat(t)

    def test_overall_breach(self):
        cfg = RiskConfig(daily_loss_halt_pct=0, eod_flat=False, friday_flat=False)
        profile = {"daily_loss_pct": 5.0, "overall_loss_pct": 10.0}
        rm = RiskManager(cfg, initial_balance=100_000, prop_profile=profile)
        # ueber mehrere Tage gestreut: kein Daily-Breach, aber -10 % gesamt
        for d in range(2, 6):  # 4 Tage a -2.6k
            t = utc(2024, 1, d, 10)
            bal = 100_000 - 2_600 * (d - 1)
            rm.update(t, bal, 0)
        assert rm.prop_breached
        assert rm.prop_breach_reason == "overall_loss"
