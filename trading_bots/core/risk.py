"""core/risk.py — Sizing, Prop-Limits, Circuit-Breaker (SPEC §4.3).

Alle Zeiten intern UTC tz-aware. Server-Tag im Backtest = UTC-Tag plus
konfigurierbarer Offset (``server_day_offset_hours``). EOD-Flat-Zeit wird in
America/New_York interpretiert (SPEC: "EOD-Flat (NY-Zeit!)").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

NY_TZ = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Konfiguration (SPEC §4.3 — Feldnamen exakt)
# ---------------------------------------------------------------------------
@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 0.5
    min_rr: float = 2.0
    daily_loss_halt_pct: float = 1.5      # bot-interner Halt
    eod_flat: bool = True
    eod_flat_time_ny: str = "16:55"
    eod_flat_time_utc: str | None = None  # falls gesetzt: feste Trade-Desk-
                                          # UTC-Zeit statt DST-sicherer NY-
                                          # Lokalzeit — hat Vorrang vor
                                          # eod_flat_time_ny, wenn beide
                                          # gesetzt sind (nur fuer Bots mit
                                          # explizit fixem Desk-Close, SPEC-
                                          # Default bleibt NY-Zeit)
    friday_flat: bool = True
    max_concurrent: int = 1
    streak_limiter: int = 0               # 0=aus; N Verluste in Folge -> Pause bis naechster Tag
    prop_profile: str = "none"            # z.B. "ftmo_2step"


# Default-Prop-Profile (werden von YAML-Dateien ueberschrieben).
DEFAULT_PROP_PROFILES: dict[str, dict] = {
    "none": {},
    "ftmo_2step": {
        "daily_loss_pct": 5.0,
        "daily_loss_basis": "prev_day_balance",
        "overall_loss_pct": 10.0,
        "profit_target_pct": 10.0,
        "best_day_consistency_pct": 45.0,
        "news_blackout_min_before": 2,
        "news_blackout_min_after": 2,
        "leverage": 100,
    },
}

PROP_KEYS = (
    "daily_loss_pct",
    "daily_loss_basis",
    "overall_loss_pct",
    "profit_target_pct",
    "best_day_consistency_pct",
    "news_blackout_min_before",
    "news_blackout_min_after",
    "leverage",
)


def load_prop_profile(name: str, config_dir: str | Path = "configs") -> dict:
    """Laedt ein Prop-Profil aus YAML (``configs/prop_<name>.yaml``).

    Faellt auf ``DEFAULT_PROP_PROFILES`` zurueck, wenn keine Datei existiert.
    ``name`` darf auch ein direkter Pfad zu einer YAML-Datei sein.
    Rueckgabe: dict mit den SPEC-§4.3-Schluesseln (fehlende = nicht aktiv).
    """
    if name in (None, "", "none"):
        return {}

    path = Path(name)
    if not path.suffix:
        path = Path(config_dir) / f"prop_{name}.yaml"

    profile: dict = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        # Erlaube Verschachtelung unter dem Profilnamen.
        if name in raw and isinstance(raw[name], dict):
            raw = raw[name]
        profile = {k: raw[k] for k in PROP_KEYS if k in raw}
    elif name in DEFAULT_PROP_PROFILES:
        profile = dict(DEFAULT_PROP_PROFILES[name])
    else:
        raise FileNotFoundError(f"Prop-Profil '{name}' nicht gefunden ({path})")

    profile.setdefault("daily_loss_basis", "prev_day_balance")
    profile["name"] = path.stem.replace("prop_", "") if path.suffix else str(name)
    return profile


# ---------------------------------------------------------------------------
# Sizing (SPEC §4.3): lots = risk_amount / (sl_points * point_value)
# ---------------------------------------------------------------------------
def calc_lots(
    risk_amount: float,
    sl_points: float,
    point_value: float,
    volume_step: float = 0.01,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
) -> float:
    """Positionsgroesse auf ``volume_step`` abgerundet, auf [min, max] geclamped.

    Wirft ``ValueError`` bei ungueltigem SL-Abstand. Wenn selbst ``volume_min``
    das Risiko ueberschreitet, wird trotzdem ``volume_min`` geliefert (Clamp)
    — Aufrufer entscheidet, ob der Trade dann uebersprungen wird.
    """
    if sl_points <= 0 or point_value <= 0:
        raise ValueError(f"sl_points/point_value muessen > 0 sein: {sl_points}, {point_value}")
    raw = risk_amount / (sl_points * point_value)
    steps = math.floor(raw / volume_step + 1e-12)
    lots = steps * volume_step
    lots = max(volume_min, min(volume_max, lots))
    # Float-Artefakte glattziehen (z.B. 0.30000000000000004).
    decimals = max(0, -int(math.floor(math.log10(volume_step))) if volume_step < 1 else 0)
    return round(lots, decimals + 2)


# ---------------------------------------------------------------------------
# RiskManager — Circuit-Breaker, Prop-Limits, Flat-Regeln
# ---------------------------------------------------------------------------
class RiskManager:
    """Zustandsbehaftete Risiko-Engine fuer Backtest und Live.

    Parameter
    ---------
    config : RiskConfig
    initial_balance : Startkontostand (Account-Waehrung)
    server_day_offset_hours : Offset des Server-Tages gegenueber UTC
        (Backtest-Konvention; Live: aus connector.server_offset()).
    prop_profile : dict aus ``load_prop_profile`` oder None.
    """

    def __init__(
        self,
        config: RiskConfig | None = None,
        initial_balance: float = 100_000.0,
        server_day_offset_hours: float = 0.0,
        prop_profile: dict | None = None,
    ) -> None:
        self.config = config or RiskConfig()
        self.initial_balance = float(initial_balance)
        self.server_offset = timedelta(hours=float(server_day_offset_hours))
        if prop_profile is None and self.config.prop_profile not in (None, "", "none"):
            prop_profile = load_prop_profile(self.config.prop_profile)
        self.prop_profile = prop_profile or {}

        self._eod_use_utc = self.config.eod_flat_time_utc is not None
        hh, mm = (self.config.eod_flat_time_utc if self._eod_use_utc
                 else self.config.eod_flat_time_ny).split(":")
        self._eod_hh, self._eod_mm = int(hh), int(mm)

        # Tages-State
        self._current_day: date | None = None
        self._day_start_balance: float = self.initial_balance
        self._daily_halt: bool = False
        self._streak_pause_day: date | None = None  # Pause bis Ende dieses Tages
        self._losing_streak: int = 0

        # Prop-Tracking
        self.prop_breached: bool = False
        self.prop_breach_reason: str | None = None
        self.max_balance: float = self.initial_balance

    # -- Zeit-Hilfen -------------------------------------------------------
    def server_day(self, ts_utc: pd.Timestamp) -> date:
        """Server-Tag = UTC-Zeit + Offset, Datum davon."""
        ts = pd.Timestamp(ts_utc)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return (ts + self.server_offset).date()

    def _ny_time(self, ts_utc: pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(ts_utc)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert(NY_TZ)

    def _flat_ref_time(self, ts_utc: pd.Timestamp) -> pd.Timestamp:
        """Zeitbasis fuer EOD-/Friday-Flat: feste UTC-Uhrzeit
        (``eod_flat_time_utc`` — Trade-Desk-Fixzeit, kein DST) ODER
        NY-Lokalzeit (``eod_flat_time_ny`` — SPEC-Default, DST-sicher).
        Weekday-Checks (Freitag) verwenden konsequent dieselbe Basis."""
        ts = pd.Timestamp(ts_utc)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts if self._eod_use_utc else ts.tz_convert(NY_TZ)

    def _past_eod_time(self, ts_utc: pd.Timestamp) -> bool:
        ref = self._flat_ref_time(ts_utc)
        return (ref.hour, ref.minute) >= (self._eod_hh, self._eod_mm)

    # -- Tageswechsel / Reset ----------------------------------------------
    def _roll_day(self, ts_utc: pd.Timestamp, balance: float) -> None:
        day = self.server_day(ts_utc)
        if self._current_day is None or day > self._current_day:
            # Reset 00:00 Server-Tag: Basis = Vortages-Bilanz (letzte bekannte
            # Balance vor Tagesbeginn).
            self._current_day = day
            self._day_start_balance = balance
            self._daily_halt = False

    # -- Update / Tracking ---------------------------------------------------
    def update(self, ts_utc: pd.Timestamp, balance: float, floating_pnl: float = 0.0) -> None:
        """Trackt Equity inkl. Floating PnL; setzt Daily-Loss-Halt / Prop-Breach."""
        self._roll_day(ts_utc, balance)
        self.max_balance = max(self.max_balance, balance)
        equity = balance + floating_pnl

        halt_pct = self.config.daily_loss_halt_pct
        if halt_pct and halt_pct > 0:
            dd_pct = (self._day_start_balance - equity) / self._day_start_balance * 100.0
            if dd_pct >= halt_pct:
                self._daily_halt = True

        # Prop-Limits (hard breach, kein Reset)
        p = self.prop_profile
        if p and not self.prop_breached:
            if p.get("daily_loss_pct"):
                dd = (self._day_start_balance - equity) / self._day_start_balance * 100.0
                if dd >= p["daily_loss_pct"]:
                    self.prop_breached = True
                    self.prop_breach_reason = "daily_loss"
            if p.get("overall_loss_pct") and not self.prop_breached:
                dd = (self.initial_balance - equity) / self.initial_balance * 100.0
                if dd >= p["overall_loss_pct"]:
                    self.prop_breached = True
                    self.prop_breach_reason = "overall_loss"

    # -- Trade-Registrierung -------------------------------------------------
    def register_closed_trade(self, pnl: float, ts_utc: pd.Timestamp) -> None:
        """Aktualisiert Streak-Limiter nach Trade-Close."""
        if pnl < 0:
            self._losing_streak += 1
        else:
            self._losing_streak = 0
        n = self.config.streak_limiter
        if n and n > 0 and self._losing_streak >= n:
            self._streak_pause_day = self.server_day(ts_utc)

    # -- Gates -----------------------------------------------------------------
    def can_open(self, ts_utc: pd.Timestamp, open_positions: int = 0) -> bool:
        """Darf ein neuer Trade eroeffnet werden?"""
        self._roll_day(ts_utc, self._day_start_balance)
        if self.prop_breached or self._daily_halt:
            return False
        if open_positions >= self.config.max_concurrent:
            return False
        if self._streak_pause_day is not None and self.server_day(ts_utc) <= self._streak_pause_day:
            return False
        # Keine neuen Entries nach EOD-Flat-Zeit ...
        if self.config.eod_flat and self._past_eod_time(ts_utc):
            return False
        # ... und Freitag (dieselbe Zeitbasis wie _past_eod_time) ab
        # EOD-Zeit gar nichts mehr, wenn friday_flat.
        if self.config.friday_flat:
            ref = self._flat_ref_time(ts_utc)
            if ref.weekday() == 4 and self._past_eod_time(ts_utc):
                return False
        return True

    def force_flat(self, ts_utc: pd.Timestamp) -> bool:
        """Muss eine offene Position jetzt geschlossen werden (EOD/Friday)?"""
        if self.prop_breached:
            return True
        ref = self._flat_ref_time(ts_utc)
        if self.config.eod_flat and self._past_eod_time(ts_utc):
            return True
        if self.config.friday_flat and ref.weekday() == 4 and self._past_eod_time(ts_utc):
            return True
        return False

    def force_flat_gap(self, prev_ts_utc: "pd.Timestamp | None", ts_utc: pd.Timestamp,
                       bar_interval: "pd.Timedelta | None" = None) -> bool:
        """Wurde zwischen der letzten und der aktuellen Bar eine
        Flatten-Deadline STILLSCHWEIGEND verschluckt (Bug-Fix)?

        force_flat()/can_open() werten die Deadline nur AM OPEN einer Bar
        aus. Liegt zwischen zwei aufeinanderfolgenden Bars eine Luecke, in
        der eine Deadline faellt, ohne dass eine Bar direkt darauf liegt —
        der Standardfall ist die Wochenend-Luecke: letzte Bar Freitag 20:00,
        naechste Bar Sonntag 21:00, Freitags-EOD-Zeit faellt dazwischen —
        wuerde force_flat() nie True liefern: an der Freitag-Bar ist es noch
        nicht so weit, an der Sonntag-Bar ist es kein Freitag mehr. Live
        wuerde trotzdem rechtzeitig geschlossen (dort laeuft die Pruefung
        nicht bar-getaktet, sondern per Timer/Health-Check). Ohne diese
        Nachbildung realisiert der Backtester Wochenend-Gap-Risiko, das die
        Regel eigentlich verhindern soll (siehe reports/gates_matrix_s1_s5.md,
        S4-Ausreisser -4.79R).

        WICHTIG (Regression, erster Fix-Versuch war falsch): der Trigger
        darf NICHT ``not force_flat(ts_utc)`` sein — nach einer echten
        Luecke ist die aktuelle Bar so gut wie IMMER schon selbst "nach der
        Deadline" (Sonntag 21:00 UTC ist trivial >= 21:00-Deadline), das
        haette den Bug-Fix komplett wirkungslos gemacht (verifiziert: exakt
        derselbe -4.79R-Trade trat nach dem ersten Fix-Versuch identisch
        wieder auf, mit exit_reason='force_flat' statt 'force_flat_gap').
        Der Trigger muss stattdessen an der eigentlichen LUECKENGROESSE
        haengen: ``bar_interval`` ist der erwartete Abstand zur Vorbar
        (Timeframe-Delta); nur wenn (ts_utc - prev_ts_utc) das deutlich
        ueberschreitet (> 1.5x), fehlen echte Bars dazwischen (Wochenende/
        Feiertag) — bei normalem Bar-zu-Bar-Abstand (auch wenn eine nicht
        bar-ausgerichtete Deadline wie 16:55 zwischen zwei Bars faellt)
        bleibt die bestehende force_flat(t_open)-Pruefung an der naechsten
        Bar korrekt und ausreichend, kein Gap-Fall.

        Rueckgabe True nur, wenn eine Deadline in (prev_ts_utc, ts_utc)
        liegt UND die Luecke tatsaechlich groesser als ein normaler
        Bar-Schritt ist."""
        if prev_ts_utc is None:
            return False
        if bar_interval is not None and (ts_utc - prev_ts_utc) <= bar_interval * 1.5:
            return False  # normaler Bar-zu-Bar-Abstand, keine echte Luecke
        prev_ref = self._flat_ref_time(prev_ts_utc)
        cur_ref = self._flat_ref_time(ts_utc)
        day = prev_ref.normalize()
        last_day = cur_ref.normalize()
        while day <= last_day:
            deadline = day + pd.Timedelta(hours=self._eod_hh, minutes=self._eod_mm)
            applies = self.config.eod_flat or (self.config.friday_flat and day.weekday() == 4)
            if applies and prev_ref < deadline < cur_ref:
                return True
            day += pd.Timedelta(days=1)
        return False

    # -- Sizing ------------------------------------------------------------------
    def calc_lots(
        self,
        balance: float,
        entry_price: float,
        stop_loss: float,
        point_value: float,
        volume_step: float = 0.01,
        volume_min: float = 0.01,
        volume_max: float = 100.0,
    ) -> float:
        risk_amount = balance * self.config.risk_per_trade_pct / 100.0
        sl_points = abs(entry_price - stop_loss)
        return calc_lots(risk_amount, sl_points, point_value, volume_step, volume_min, volume_max)

    # -- State fuer Reporting ------------------------------------------------------
    @property
    def day_start_balance(self) -> float:
        return self._day_start_balance

    @property
    def daily_halt(self) -> bool:
        return self._daily_halt

    @property
    def losing_streak(self) -> int:
        return self._losing_streak
