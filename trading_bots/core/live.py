"""core/live.py — Live-Loop (Demo) fuer MT5 via MT5Connector (SPEC §4.10).

Ablauf je Poll:
1. Health-Check alle ``health_interval_seconds`` (30–60 s) mit Reconnect.
2. Neue geschlossene Bars je Strategie-Timeframe pollen (Copy-Range, die
   letzte — unfertige — Bar wird verworfen).
3. ``strategy.on_bar(bars, i)`` mit aligned Views (nur geschlossene Bars).
4. News-Filter (fail-closed) + Risk-Engine (Daily-Halt, EOD-Flat,
   Friday-Flat, max_concurrent) anwenden.
5. Orders via Connector — IMMER mit serverseitigem SL/TP (Crash-Netz).
6. Strukturiertes Logging (jsonl). Graceful shutdown via SIGINT/SIGTERM.

CLI:
    python -m core.live --config configs/s1_trend_pullback.yaml --dry-run
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import logging.handlers
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from core.connector import MT5Connector, RETCODE_DONE, TF_MINUTES
from core.journal import TradeJournal

log = logging.getLogger("core.live")
UTC = timezone.utc

_STRATEGY_REGISTRY = {
    "s1_trend_pullback": ("strategies.s1_trend_pullback", "TrendPullback"),
    "s2_vwap_pullback": ("strategies.s2_vwap_pullback", "VWAPPullback"),
    "s3_silver_bullet": ("strategies.s3_silver_bullet", "S3SilverBullet"),
    "s4_london_breakout": ("strategies.s4_london_breakout", "S4LondonBreakout"),
    "s5_filtered_mr": ("strategies.s5_filtered_mr", "S5FilteredMR"),
    "s6_fix_reversal": ("strategies.s6_fix_reversal", "S6FixReversal"),
    "s7_fomc_drift": ("strategies.s7_fomc_drift", "S7FomcDrift"),
    "s8_dayflow_vwap_relay": ("strategies.s8_dayflow_vwap_relay", "S8DayflowVwapRelay"),
    "s9_donchian_trend": ("strategies.s9_donchian_trend", "S9DonchianTrend"),
    "s10_ema_cross_trend": ("strategies.s10_ema_cross_trend", "S10EmaCrossTrend"),
    "s11_momentum_trend": ("strategies.s11_momentum_trend", "S11MomentumTrend"),
    "s12_rsi_scalp": ("strategies.s12_rsi_scalp", "S12RsiScalp"),
    "s13_vwap_fade_scalp": ("strategies.s13_vwap_fade_scalp", "S13VwapFadeScalp"),
    "s14_squeeze_volume_breakout": ("strategies.s14_squeeze_volume_breakout", "S14SqueezeVolumeBreakout"),
    "s15_volume_climax_reversion": ("strategies.s15_volume_climax_reversion", "S15VolumeClimaxReversion"),
    "s16_mtf_squeeze_breakout": ("strategies.s16_mtf_squeeze_breakout", "S16MtfSqueezeBreakout"),
    "s17_david_v2_trend_pullback": ("strategies.s17_david_v2_trend_pullback", "S17DavidV2TrendPullback"),
    "s18_scalp_signal_bot": ("strategies.s18_scalp_signal_bot", "S18ScalpSignalBot"),
    "s19_lizard_swing_breakout": ("strategies.s19_lizard_swing_breakout", "S19LizardSwingBreakout"),
    "s20_sgh_momentum_breakout": ("strategies.s20_sgh_momentum_breakout", "S20SghMomentumBreakout"),
    "s21_goldreaper_momentum_stack": ("strategies.s21_goldreaper_momentum_stack", "S21GoldReaperMomentumStack"),
    "analyze_98946a741100": ("strategies.analyze_98946a741100", "AnalyzeUniversalMacdTrend"),
    "analyze_2166fb052559": ("strategies.analyze_2166fb052559", "AnalyzeXauVelocityF7"),
    "analyze_a3d5ea031833": ("strategies.analyze_a3d5ea031833", "AnalyzeXauVelocityF7Full"),
    "analyze_95443742cec6": ("strategies.analyze_95443742cec6", "AnalyzeXauVelocityF7Profiles"),
    "analyze_e241bb189fa2": ("strategies.analyze_e241bb189fa2", "AnalyzeXauTrendPullbackAtr"),
    "analyze_7e9787b27c5c": ("strategies.analyze_7e9787b27c5c", "AnalyzeXauTrendPullbackPresets"),
}


def load_strategy_class(name: str):
    """Laedt die Strategy-Klasse — per Registry-Key oder dotted path
    (``strategies.s1_trend_pullback.TrendPullback``), lazy ohne Modul-Import
    beim Laden."""
    if "." in name:
        module_name, class_name = name.rsplit(".", 1)
        return getattr(importlib.import_module(module_name), class_name)
    if name not in _STRATEGY_REGISTRY:
        raise ValueError(f"Unbekannte Strategie: {name!r} (bekannt: {sorted(_STRATEGY_REGISTRY)})")
    module_name, class_name = _STRATEGY_REGISTRY[name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


class JsonlLogger:
    """Strukturiertes Event-Logging (eine JSON-Zeile pro Event)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **fields) -> None:
        record = {"ts": datetime.now(UTC).isoformat(), "event": kind, **fields}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")


def _attach_narrative_handler(path: Path) -> None:
    """Haengt einen taeglich rotierenden Text-Log an ``log`` (Traderbook-Stil:
    Klartext statt JSON, wie ``bot.log`` bei den Desktop-Bots). Idempotent —
    ein zweiter Aufruf mit demselben Pfad haengt keinen doppelten Handler an
    (z.B. wenn in Tests mehrere LiveRunner-Instanzen entstehen)."""
    target = str(path)
    for h in log.handlers:
        if getattr(h, "_narrative_path", None) == target:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(
        target, when="midnight", backupCount=30, encoding="utf-8", utc=True,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    handler._narrative_path = target  # type: ignore[attr-defined]
    log.addHandler(handler)
    log.setLevel(min(log.level or logging.INFO, logging.INFO))


def _describe_signal(signal) -> str:
    """Klartext-Begruendung eines Signals fuers Journal/Log — nutzt die
    Meta-Felder von S4 (range/tp_r/entry_mode), faellt sonst generisch
    zurueck (andere Strategien liefern ggf. andere Meta-Keys)."""
    meta = signal.meta or {}
    richtung = "LONG" if signal.direction > 0 else "SHORT"
    if "range_high" in meta and "range_low" in meta:
        seite = "ueber" if signal.direction > 0 else "unter"
        return (f"London-Breakout {richtung} ({seite} Range "
                f"{meta['range_low']:.5g}-{meta['range_high']:.5g}, "
                f"{meta.get('range_pips', 0):.1f} Pips), "
                f"TP {meta.get('tp_r', '?')}R, Entry {meta.get('entry_mode', signal.entry_type)}")
    return f"Signal {richtung} ({signal.entry_type})"


def _atr_now(df: pd.DataFrame, n: int) -> float | None:
    """ATR (Wilder-aequivalent via EWM) auf den zuletzt geschlossenen Bars —
    fuers Live-Trailing (core.live), gleiche Semantik wie der Backtester,
    aber ohne dessen exakte SMA-Seed-Rekursion (bei history_bars>=500
    vernachlaessigbarer Unterschied)."""
    if len(df) < n + 1:
        return None
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    val = atr.iloc[-1]
    return float(val) if pd.notna(val) else None


def _format_explain(symbol: str, info: dict) -> str | None:
    """Klartext-Zeile aus ``Strategy.explain()`` fuers Traderbook-Log.

    ``info["kind"]`` waehlt das Rueckgabeschema der jeweiligen Strategie
    (jede Strategie hat ihre eigenen Diagnose-Felder); ohne ``kind`` gilt
    das urspruengliche S4-Breakout-Schema (range/breakout_direction) als
    Default, damit bestehende Strategien ohne ``kind``-Feld weiterlaufen."""
    kind = info.get("kind")
    if kind == "rsi_ema_momentum":
        return _format_explain_rsi_ema(symbol, info)
    if kind == "ema_cross":
        return _format_explain_ema_cross(symbol, info)

    if not info.get("in_entry_window", True):
        return None
    parts = [symbol]
    if info.get("range_high") is not None:
        parts.append(f"Range {info['range_low']:.5g}-{info['range_high']:.5g} "
                     f"({info.get('range_pips') or 0:.1f} Pips)")
    if info.get("breakout_direction"):
        parts.append("Breakout " + ("LONG" if info["breakout_direction"] > 0 else "SHORT"))
    blocked = info.get("blocked_by") or []
    if info.get("ready"):
        parts.append("BEREIT — Signal wird ausgeloest")
    elif blocked:
        parts.append("blockiert: " + ", ".join(blocked))
    else:
        parts.append("kein Breakout")
    return " | ".join(parts)


_RSI_EMA_FILTER_LABELS = {
    "mid_slow_misaligned": "EMA50/200 nicht ausgerichtet",
    "rsi_below_threshold": "RSI unter Schwelle",
    "rsi_above_threshold": "RSI ueber Schwelle",
    "no_fresh_cross": "kein frischer RSI-Cross",
    "no_trend_alignment": "kein EMA-Trend-Alignment",
    "atr_vol_filter": "ATR-Vol-Perzentil zu niedrig",
    "outside_session": "ausserhalb Session-Fenster",
}


def _format_explain_rsi_ema(symbol: str, info: dict) -> str | None:
    """Diagnose-Zeile fuer RSI/EMA-Momentum-Strategien (z.B. S21) — zeigt
    Trendrichtung, RSI-Stand, Setup-Richtung und was noch fehlt/blockiert."""
    blocked = [b for b in (info.get("blocked_by") or []) if b != "warmup"]
    if "warmup" in (info.get("blocked_by") or []) and not blocked:
        return None  # noch nicht genug Historie -- kein Mehrwert
    trend_arrow = {"up": "↑", "down": "↓", "flat": "~"}.get(info.get("trend"), "?")
    parts = [f"{symbol}: Trend {trend_arrow}"]
    if info.get("rsi") is not None:
        parts.append(f"RSI {info['rsi']:.0f}")
    bias = info.get("direction_bias")
    if bias == 1:
        parts.append("LONG-Setup")
    elif bias == -1:
        parts.append("SHORT-Setup")
    needed = info.get("rsi_points_needed")
    if needed and needed > 0.05:
        richtung = "steigen" if bias == 1 else "fallen"
        parts.append(f"RSI muss noch {needed:.0f} Punkte {richtung}")
    if info.get("ready"):
        parts.append("BEREIT — Signal wird ausgeloest")
    if blocked:
        parts.append("FILTER: " + ", ".join(_RSI_EMA_FILTER_LABELS.get(b, b) for b in blocked))
    return " | ".join(parts)


_EMA_CROSS_FILTER_LABELS = {
    "no_fresh_cross": "kein frischer Kreuzungspunkt",
}


def _format_explain_ema_cross(symbol: str, info: dict) -> str | None:
    """Diagnose-Zeile fuer reine EMA-Cross-Trendfolge-Strategien (z.B. S10) —
    zeigt Trendrichtung (EMA schnell vs. langsam), Abstand und ob gerade
    ein frischer Kreuzungspunkt vorliegt."""
    blocked = [b for b in (info.get("blocked_by") or []) if b != "warmup"]
    if "warmup" in (info.get("blocked_by") or []) and not blocked:
        return None  # noch nicht genug Historie -- kein Mehrwert
    trend_arrow = {"up": "↑", "down": "↓"}.get(info.get("trend"), "?")
    parts = [f"{symbol}: EMA-Trend {trend_arrow}"]
    if info.get("ema_fast") is not None and info.get("ema_slow") is not None:
        parts.append(f"EMA {info['ema_fast']:.5g}/{info['ema_slow']:.5g}")
    if info.get("gap_pct") is not None:
        parts.append(f"Abstand {info['gap_pct']:.2f}%")
    if info.get("ready"):
        parts.append("BEREIT — Signal wird ausgeloest")
    if blocked:
        parts.append("FILTER: " + ", ".join(_EMA_CROSS_FILTER_LABELS.get(b, b) for b in blocked))
    return " | ".join(parts)


class LiveRunner:
    """Live-Loop fuer genau eine Strategie-Config (ggf. mehrere Symbole)."""

    def __init__(self, config_path: str | Path, dry_run: bool = True,
                 host: str | None = None, port: int | None = None):
        self.config_path = Path(config_path)
        with open(self.config_path, "r", encoding="utf-8") as fh:
            self.cfg = yaml.safe_load(fh)
        self.live_cfg = self.cfg.get("live", {})
        self.dry_run = dry_run
        self.host = host or self.live_cfg.get("host", "localhost")
        self.port = int(port or self.live_cfg.get("port", 18812))
        self.poll_seconds = float(self.live_cfg.get("poll_seconds", 10))
        self.health_interval = float(self.live_cfg.get("health_interval_seconds", 45))
        self.heartbeat_seconds = float(self.live_cfg.get("heartbeat_seconds", 1800))
        self.history_bars = int(self.live_cfg.get("history_bars", 500))
        self.magic = int(self.live_cfg.get("magic", 20260903))
        self.flatten_on_stop = bool(self.live_cfg.get("flatten_on_stop", False))
        self.deviation = int(self.live_cfg.get("deviation", 10))
        # Sicherheitsschalter (SPEC: kein Echtgeld ohne explizites Opt-in) —
        # Default False: der Bot verweigert den Start auf einem Echtgeldkonto
        # (siehe _connect_with_retry -> _enforce_account_safety), analog zum
        # ALLOW_REAL_ACCOUNT-Schalter der Desktop-Bots.
        self.allow_real_account = bool(self.live_cfg.get("allow_real_account", False))

        self.symbols: list[str] = list(self.cfg["symbols"])
        self.timeframes: list[str] = list(self.cfg["timeframes"])
        self.primary_tf = self.timeframes[0]

        self._stop = False
        self._last_bar: dict[str, pd.Timestamp] = {}      # symbol -> letzte verarbeitete (geschlossene) Bar
        self._processed_signals: set[tuple] = set()       # (symbol, bar_time, direction, entry_type)
        self._known_tickets: set[int] = set()
        self._pending_close: dict[int, str] = {}          # ticket -> symbol; Journal-Close, Broker-Historie hinkt oft nach
        # Trailing-Stop-Zustand je Ticket (Chandelier + Move-to-Trail, spiegelt
        # core/backtester.py._resolve_sl_tp/2c — dort simuliert, hier live via
        # connector.modify_sltp). Nur im Prozessspeicher: ueberlebt einen
        # Neustart NICHT (dann startet der Trail konservativ ab dem aktuellen
        # Preis neu — kein Sicherheitsproblem, der Broker-SL bleibt ja aktiv).
        self._trail_state: dict[int, dict] = {}

        logs_dir = Path(self.live_cfg.get("logs_dir", "logs"))
        strategy_name = self.cfg.get("strategy", "bot")
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        self.jlog = JsonlLogger(logs_dir / f"live_{strategy_name}_{stamp}.jsonl")
        # Menschenlesbares Traderbook-Log (Klartext, taeglich rotierend) —
        # ergaenzt das JSONL um die "warum" -Nachvollziehbarkeit (User-Anforderung).
        _attach_narrative_handler(logs_dir / f"{strategy_name}.log")
        self.journal = TradeJournal(logs_dir / f"trades_{strategy_name}.csv")

        # --- Komponenten (lazy Imports: Repo-Module sind optional im Branch) ---
        strategy_cls = load_strategy_class(self.cfg["strategy"])
        self.strategy = strategy_cls(dict(self.cfg.get("params", {})))

        from core.risk import RiskConfig, RiskManager, load_prop_profile  # lazy
        risk_cfg = RiskConfig(**{k: v for k, v in (self.cfg.get("risk") or {}).items()
                                 if k in RiskConfig.__dataclass_fields__})
        prop_name = risk_cfg.prop_profile
        prop_profile = load_prop_profile(prop_name) if prop_name not in (None, "", "none") else {}
        self.risk = RiskManager(risk_cfg, prop_profile=prop_profile,
                                initial_balance=float(self.live_cfg.get("initial_balance", 100_000.0)))

        self.news_filter = None
        meta = self.cfg.get("meta_layer", {})
        nf_setting = meta.get("news_filter", "on")
        if nf_setting is True or str(nf_setting).lower() in ("on", "true", "1"):
            try:
                from core.news_filter import NewsFilter  # lazy
                cache_dir = self.live_cfg.get("news_cache_dir", "data/news")
                self.news_filter = NewsFilter(cache_dir, prop_profile)
                self.news_filter.update()
            except ImportError:
                log.warning("core.news_filter nicht verfuegbar — FAIL-CLOSED: keine Entries")
                self.jlog.event("news_filter_missing", mode="fail_closed")
                self.news_filter = "fail_closed"

        self.connector = MT5Connector(host=self.host, port=self.port,
                                      dry_run=self.dry_run, magic=self.magic)

    # -- Shutdown ----------------------------------------------------------
    def request_stop(self, *_args) -> None:
        log.info("Shutdown angefordert")
        self._stop = True

    # -- Daten -------------------------------------------------------------
    def _fetch_bars(self, symbol: str) -> dict[str, pd.DataFrame]:
        """Laedt die letzten ``history_bars`` je TF; verwirft unfertige Bar."""
        now_utc = pd.Timestamp.now(UTC)
        bars: dict[str, pd.DataFrame] = {}
        for tf in self.timeframes:
            tf_min = TF_MINUTES[tf]
            start = now_utc - pd.Timedelta(minutes=tf_min * (self.history_bars + 5))
            df = self.connector.fetch_ohlcv(symbol, tf, start, now_utc)
            if len(df):
                # Letzte Bar nur behalten, wenn sie geschlossen ist.
                last_open = df.index[-1]
                if last_open + pd.Timedelta(minutes=tf_min) > now_utc:
                    df = df.iloc[:-1]
            bars[tf] = df
        return bars

    # -- News / Risiko Gates -------------------------------------------------
    def _news_blocked(self, ts_utc: pd.Timestamp, symbol: str) -> bool:
        if self.news_filter is None:
            return False
        if self.news_filter == "fail_closed":
            return True  # Feed fehlt -> keine neuen Entries (SPEC §4.7)
        try:
            return bool(self.news_filter.is_blackout(ts_utc, symbol)
                        or self.news_filter.tier1_halt(ts_utc))
        except Exception as exc:  # noqa: BLE001
            log.warning("News-Filter-Fehler (%s) — fail-closed", exc)
            return True

    def _force_flat_all(self, symbol: str) -> None:
        for pos in self.connector.positions(symbol):
            if int(pos.get("magic", 0)) != self.magic:
                continue
            ticket = int(pos["ticket"])
            self.jlog.event("force_flat", symbol=symbol, ticket=ticket)
            log.warning("FORCE-FLAT: %s Position #%s wird geschlossen "
                       "(Risk-Engine: EOD-Flat/Friday-Flat/Daily-Halt).", symbol, ticket)
            self.connector.close(ticket, deviation=self.deviation)

    # -- Signal-Verarbeitung ---------------------------------------------------
    def _handle_signal(self, symbol: str, signal) -> None:
        key = (symbol, str(signal.time), signal.direction, signal.entry_type)
        if key in self._processed_signals:
            return
        self._processed_signals.add(key)
        self.jlog.event("signal", symbol=symbol, time=str(signal.time),
                        direction=signal.direction, entry_type=signal.entry_type,
                        sl=signal.stop_loss, tp=signal.take_profit,
                        meta=signal.meta)
        log.info("SIGNAL %s: %s — %s", "LONG" if signal.direction > 0 else "SHORT",
                 symbol, _describe_signal(signal))
        ts_utc = pd.Timestamp.now(UTC)
        if self._news_blocked(ts_utc, symbol):
            self.jlog.event("signal_blocked", reason="news", symbol=symbol)
            log.info("%s: Signal verworfen — News-Blackout aktiv (fail-closed).", symbol)
            return
        open_positions = [p for p in self.connector.positions(symbol)
                          if int(p.get("magic", 0)) == self.magic]
        if not self.risk.can_open(ts_utc, open_positions=len(open_positions)):
            self.jlog.event("signal_blocked", reason="risk", symbol=symbol)
            log.info("%s: Signal verworfen — Risk-Engine blockiert "
                     "(Daily-Halt/EOD-Flat/Max-Concurrent).", symbol)
            return
        if not signal.stop_loss:
            self.jlog.event("signal_blocked", reason="no_sl", symbol=symbol)
            log.error("Signal ohne SL verworfen — SL ist Pflicht (Crash-Netz)")
            return

        # Sizing via RiskManager + Broker-Spec
        spec = self.connector.symbol_spec(symbol)
        point_value = spec["tick_value"] / spec["tick_size"] if spec["tick_size"] else 1.0
        entry_ref = signal.entry_price or self._last_price(symbol, signal.direction)
        if entry_ref is None:
            return
        lots = self.risk.calc_lots(
            balance=float(self.connector.account_info().get("balance", 0.0)
                          or self.live_cfg.get("initial_balance", 100_000.0)),
            entry_price=entry_ref, stop_loss=signal.stop_loss,
            point_value=point_value,
            volume_step=spec["volume_step"], volume_min=spec["volume_min"],
            volume_max=spec["volume_max"],
            signal_risk_pct=signal.risk_pct,
        )
        if signal.entry_type == "limit" and signal.entry_price is not None:
            result = self.connector.send_limit(symbol, signal.direction, lots,
                                               signal.entry_price, signal.stop_loss,
                                               signal.take_profit, deviation=self.deviation)
        else:
            # IMMER serverseitiger SL/TP (Crash-Netz)
            result = self.connector.send_market(symbol, signal.direction, lots,
                                                signal.stop_loss, signal.take_profit,
                                                deviation=self.deviation)
        self.jlog.event("order_sent", symbol=symbol, lots=lots, result=dict(result))
        if int(result.get("retcode", -1)) == RETCODE_DONE:
            ticket = int(result.get("order") or result.get("deal") or 0)
            entry_price = float(result.get("price") or entry_ref)
            acc = self.connector.account_info()
            equity = float(acc.get("equity", 0.0) or 0.0)
            reason = _describe_signal(signal)
            self.journal.open(symbol=symbol, direction=signal.direction, ticket=ticket,
                              lots=lots, entry=entry_price, sl=signal.stop_loss,
                              tp=signal.take_profit, risk_pct=signal.risk_pct,
                              reason=reason, equity=equity)
            log.info("ORDER AUSGEFUEHRT: %s %s %.2f Lots @ %s | SL %s | TP %s | %s",
                     "LONG" if signal.direction > 0 else "SHORT", symbol, lots,
                     entry_price, signal.stop_loss, signal.take_profit, reason)
            trail_mult = float(signal.meta.get("trail_atr_mult", 0.0) or 0.0)
            if trail_mult > 0:
                self._trail_state[ticket] = {
                    "trail_atr_mult": trail_mult,
                    "trail_atr_len": int(signal.meta.get("trail_atr_len", 14) or 14),
                    "direction": signal.direction,
                    "extreme": entry_price,
                    "tp_locked": signal.take_profit is None,
                }
        else:
            log.warning("%s: Order abgelehnt (retcode=%s) — kein Journal-Eintrag, "
                       "keine Position eroeffnet.", symbol, result.get("retcode"))

    def _update_trailing_stops(self, symbol: str, df: pd.DataFrame) -> None:
        """Chandelier-Trail + Move-to-Trail live nachbilden (s. core/backtester.py
        _resolve_sl_tp/2c): TP-Beruehrung sperrt den SL aufs TP-Niveau statt zu
        schliessen (Mindest-RR gesichert), danach nur noch guenstigere Ratchets.
        Rein additiv zum Broker-SL/TP — nie strenger als das serverseitige
        Crash-Netz, das beim Entry gesetzt wurde."""
        if not self._trail_state or len(df) < 2:
            return
        positions = {int(p["ticket"]): p for p in self.connector.positions(symbol)
                    if int(p.get("magic", 0)) == self.magic}
        for ticket in list(self._trail_state):
            if ticket not in positions:
                del self._trail_state[ticket]  # zwischenzeitlich geschlossen
        if not positions:
            return
        h, l = float(df["high"].iloc[-1]), float(df["low"].iloc[-1])
        for ticket, state in self._trail_state.items():
            pos = positions.get(ticket)
            if pos is None:
                continue
            atr_val = _atr_now(df, state["trail_atr_len"])
            if atr_val is None or not (atr_val > 0):
                continue
            direction = state["direction"]
            cur_sl = float(pos.get("sl") or 0.0)
            cur_tp = float(pos.get("tp") or 0.0) or None

            if not state["tp_locked"] and cur_tp:
                touched = (h >= cur_tp) if direction > 0 else (l <= cur_tp)
                if touched:
                    if self.connector.modify_sltp(ticket, cur_tp, None):
                        state["tp_locked"] = True
                        cur_sl = cur_tp
                        cur_tp = None
                        self.jlog.event("trail_lock", ticket=ticket, symbol=symbol, sl=cur_sl)
                        log.info("TRAIL-LOCK %s #%s: SL auf TP-Niveau %.5f gezogen, TP aufgehoben "
                                "(Mindest-RR gesichert, Trail uebernimmt).", symbol, ticket, cur_sl)

            if direction > 0:
                state["extreme"] = max(state["extreme"], h)
                candidate = state["extreme"] - state["trail_atr_mult"] * atr_val
                favorable = candidate > cur_sl
            else:
                state["extreme"] = min(state["extreme"], l)
                candidate = state["extreme"] + state["trail_atr_mult"] * atr_val
                favorable = candidate < cur_sl
            if favorable:
                tp_arg = None if state["tp_locked"] else cur_tp
                if self.connector.modify_sltp(ticket, candidate, tp_arg):
                    self.jlog.event("trail_update", ticket=ticket, symbol=symbol, sl=candidate)
                    log.info("TRAIL %s #%s: SL -> %.5f", symbol, ticket, candidate)

    def _last_price(self, symbol: str, direction: int) -> float | None:
        mt5 = self.connector._require_conn()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            log.error("Kein Tick fuer %s", symbol)
            return None
        return float(tick.ask if direction > 0 else tick.bid)

    # -- Trade-Close-Tracking (Streak-Limiter etc.) -----------------------------
    def _track_closed(self, symbol: str) -> None:
        tickets = {int(p["ticket"]) for p in self.connector.positions(symbol)
                   if int(p.get("magic", 0)) == self.magic}
        for closed in self._known_tickets - tickets:
            self.jlog.event("trade_closed_detected", ticket=closed)
            self._pending_close[closed] = symbol
        self._known_tickets = tickets

    def _drain_pending_closes(self) -> None:
        """Versucht, wartende Schliessungen ins Journal einzutragen. Die
        Broker-Historie ist manchmal ein paar Sekunden nach dem Schliessen
        noch nicht befuellt — bei Fehlschlag bleibt der Ticket in
        ``_pending_close`` fuer den naechsten Loop-Durchlauf stehen."""
        for ticket, symbol in list(self._pending_close.items()):
            try:
                if self._journal_close(ticket, symbol):
                    del self._pending_close[ticket]
            except Exception as exc:  # noqa: BLE001 — darf den Loop nie stoppen
                log.warning("Journal-Close fuer #%s (%s) fehlgeschlagen: %s",
                           ticket, symbol, exc)

    def _journal_close(self, ticket: int, symbol: str) -> bool:
        """Holt die Abschlussdaten einer verschwundenen Position aus der
        Broker-Historie und traegt sie ins Journal ein. True bei Erfolg."""
        deals = self.connector.history_deals_for_position(ticket)
        if not deals:
            return False
        exit_deals = [d for d in deals if int(d.get("entry", -1)) == 1]  # DEAL_ENTRY_OUT
        if not exit_deals:
            return False
        d = exit_deals[-1]
        profit = sum(float(x.get("profit", 0.0) or 0.0) for x in deals)
        fees = sum(float(x.get("commission", 0.0) or 0.0)
                  + float(x.get("swap", 0.0) or 0.0) for x in deals)
        net = profit + fees  # Kommission/Swap sind negativ
        reason_map = {3: "Stop-Loss getroffen", 4: "Take-Profit getroffen"}
        reason = reason_map.get(int(d.get("reason", -1)), "geschlossen (manuell/force_flat)")
        acc = self.connector.account_info()
        equity = float(acc.get("equity", 0.0) or 0.0)
        self.journal.close(symbol=symbol, ticket=ticket, exit_price=float(d.get("price", 0.0) or 0.0),
                          profit=net, fees=fees, reason=reason, equity=equity)
        log.info("TRADE GESCHLOSSEN: %s #%s @ %s | %s %.2f (brutto %.2f, Kosten %.2f) | %s",
                 symbol, ticket, d.get("price"), "GEWINN" if net >= 0 else "VERLUST",
                 net, profit, fees, reason)
        return True

    # -- Hauptloop ---------------------------------------------------------------
    def run(self, once: bool = False) -> None:
        signal.signal(signal.SIGINT, self.request_stop)
        signal.signal(signal.SIGTERM, self.request_stop)
        self.jlog.event("startup", config=str(self.config_path), dry_run=self.dry_run,
                        symbols=self.symbols, timeframes=self.timeframes)
        log.info("Live-Loop startet (dry_run=%s, Symbole=%s)", self.dry_run, self.symbols)

        self._connect_with_retry()
        if self.news_filter not in (None, "fail_closed"):
            try:
                self.news_filter.update()
            except Exception as exc:  # noqa: BLE001
                log.warning("News-Feed-Update fehlgeschlagen: %s (fail-closed)", exc)

        last_health = 0.0
        last_heartbeat = 0.0
        while not self._stop:
            loop_start = time.monotonic()
            now = pd.Timestamp.now(UTC)

            # 1) Health + Reconnect (alle 30–60 s)
            if loop_start - last_health >= self.health_interval:
                last_health = loop_start
                if not self.connector.health():
                    self.jlog.event("health_fail")
                    log.warning("Health-Check fehlgeschlagen — Reconnect")
                    self._connect_with_retry()
                    continue

            # Herzschlag: Equity + offene Positionen (Dashboard liest dies aus
            # dem Traderbook-Log fuer die Equity-Kurve, wie bei den Desktop-Bots).
            if loop_start - last_heartbeat >= self.heartbeat_seconds:
                last_heartbeat = loop_start
                try:
                    acc = self.connector.account_info()
                    equity = float(acc.get("equity", 0.0) or 0.0)
                    open_n = sum(1 for p in self.connector.positions()
                                if int(p.get("magic", 0)) == self.magic)
                    log.info("♥ [%s] Bot laeuft — Equity %.2f %s, %d Position(en) offen.",
                             self.strategy.name, equity, acc.get("currency", ""), open_n)
                    self.jlog.event("heartbeat", equity=equity, open_positions=open_n)
                except Exception as exc:  # noqa: BLE001 — Heartbeat darf nie den Loop stoppen
                    log.warning("Heartbeat fehlgeschlagen: %s", exc)

            # 2) Risiko-Update + Force-Flat
            for symbol in self.symbols:
                try:
                    info = self.connector.account_info()
                    floating = float(info.get("profit", 0.0) or 0.0)
                    balance = float(info.get("balance", 0.0) or 0.0)
                    if balance:
                        self.risk.update(now, balance, floating)
                    if self.risk.force_flat(now):
                        self._force_flat_all(symbol)
                    self._track_closed(symbol)
                except Exception as exc:  # noqa: BLE001
                    log.exception("Risiko-Update %s fehlgeschlagen: %s", symbol, exc)
            self._drain_pending_closes()

            # 3) Neue geschlossene Bars -> on_bar -> Orders
            for symbol in self.symbols:
                try:
                    bars = self._fetch_bars(symbol)
                    df = bars[self.primary_tf]
                    if df.empty:
                        continue
                    self._update_trailing_stops(symbol, df)  # jede Poll-Runde, nicht nur bei neuer Bar
                    last_closed = df.index[-1]
                    if self._last_bar.get(symbol) is not None and last_closed <= self._last_bar[symbol]:
                        continue  # keine neue geschlossene Bar
                    self._last_bar[symbol] = last_closed
                    i = len(df) - 1
                    self.jlog.event("new_bar", symbol=symbol, tf=self.primary_tf,
                                    bar=str(last_closed))
                    sig = self.strategy.on_bar(bars, i)
                    if sig is not None:
                        self._handle_signal(symbol, sig)
                    elif hasattr(self.strategy, "explain"):
                        # Traderbook-Diagnose: WARUM kein Signal? Rein lesend,
                        # beeinflusst die Handelsentscheidung nicht.
                        try:
                            explanation = self.strategy.explain(bars, i)
                            line = _format_explain(symbol, explanation)
                            if line:
                                log.info("KEIN EINSTIEG [%s]: %s", self.strategy.name, line)
                        except Exception as exc:  # noqa: BLE001 — Diagnose darf nie den Loop stoppen
                            log.debug("explain() fehlgeschlagen fuer %s: %s", symbol, exc)
                except Exception as exc:  # noqa: BLE001
                    self.jlog.event("loop_error", symbol=symbol, error=str(exc))
                    log.exception("Loop-Fehler %s: %s", symbol, exc)

            if once:
                break
            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.5, self.poll_seconds - elapsed))

        # --- Graceful Shutdown ---
        self.jlog.event("shutdown")
        if self.flatten_on_stop:
            for symbol in self.symbols:
                self._force_flat_all(symbol)
        self.connector.disconnect()
        log.info("Live-Loop beendet")

    def _connect_with_retry(self, max_attempts: int = 5) -> None:
        for attempt in range(max_attempts):
            try:
                self.connector.disconnect()
                self.connector.connect()
                self._enforce_account_safety()
                self.jlog.event("connected", host=self.host, port=self.port)
                log.info("Verbunden: %s:%s (Magic %s, dry_run=%s)",
                         self.host, self.port, self.magic, self.dry_run)
                return
            except SystemExit:
                raise  # Sicherheitsstopp: NICHT retryen, NICHT weiterlaufen
            except Exception as exc:  # noqa: BLE001
                wait = min(60, 5 * (2 ** attempt))
                log.warning("Connect fehlgeschlagen (%s), retry in %ds", exc, wait)
                self.jlog.event("connect_retry", attempt=attempt, error=str(exc))
                time.sleep(wait)
        raise ConnectionError("MT5 nicht erreichbar nach mehreren Versuchen")

    def _enforce_account_safety(self) -> None:
        """SICHERHEITSSTOPP: verweigert den Start (bzw. den Weiterbetrieb nach
        einem Reconnect) auf einem Echtgeldkonto, solange
        ``live.allow_real_account`` nicht explizit auf true steht (SPEC: kein
        Echtgeld ohne explizites Opt-in). Ist der Kontotyp nicht ermittelbar
        (``trade_mode`` fehlt beim Broker), wird NICHT hart gestoppt — aber
        laut gewarnt, da der Check dann nichts bestaetigen konnte."""
        is_demo = self.connector.is_demo_account()
        info = self.connector.account_info()
        login, server = info.get("login"), info.get("server")
        if is_demo is False and not self.allow_real_account:
            msg = (f"SICHERHEITSSTOPP: Konto {login} ({server}) ist ein ECHTGELDKONTO. "
                  f"Dieser Bot ist per Default auf Demo-Betrieb beschraenkt "
                  f"(live.allow_real_account=false). Zum Zulassen explizit in der "
                  f"Config setzen.")
            log.critical(msg)
            self.jlog.event("safety_stop", reason="real_account", login=login, server=server)
            self.connector.disconnect()
            raise SystemExit(msg)
        if is_demo is None:
            log.warning("Kontotyp (Demo/Echtgeld) nicht ermittelbar (trade_mode fehlt "
                       "vom Broker) — Sicherheitscheck konnte NICHT bestaetigen, dass "
                       "dies ein Demo-Konto ist. Konto %s (%s).", login, server)
            self.jlog.event("safety_warning", reason="trade_mode_unknown", login=login)
        else:
            log.info("Kontotyp bestaetigt: DEMO (Konto %s, %s)", login, server)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.live",
        description="Live-Loop (Demo) — MT5 via pymt5linux/RPyC",
    )
    parser.add_argument("--config", required=True, help="Pfad zur Strategie-YAML")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                        help="Orders nur loggen (DEFAULT, sicher)")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                        help="ECHTE Orders — nur nach expliziter Freigabe!")
    parser.add_argument("--host", default=None, help="RPyC-Host (default: aus Config/localhost)")
    parser.add_argument("--port", type=int, default=None, help="RPyC-Port (default: 18812)")
    parser.add_argument("--once", action="store_true", help="nur ein Loop-Durchlauf (Debug)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not args.dry_run:
        log.warning("!!! ECHTER MODUS (--no-dry-run) — Orders gehen zum Server !!!")

    runner = LiveRunner(args.config, dry_run=args.dry_run, host=args.host, port=args.port)
    runner.run(once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
