"""core/backtester.py — Event-Engine, Kostenmodell, Stress (SPEC §4.2).

Ablauf je Bar des primaeren (Execution-)Timeframes — ``config.timeframes[0]``:

1. Bar-Open: Force-Flat durch Risk-Engine (EOD-NY / Friday / Prop-Breach),
   Market-Entries aus dem Signal der Vortags-Bar (Open dieser Bar).
2. Intrabar: Pending-Limit-Fills bei Range-Touch, SL/TP-Handling. Modus
   ``stop_first`` (ohne feinere Daten: Limit+SL-Touch in derselben Bar ->
   SL zuerst, Order verwirft — die einzig moegliche Annahme ohne Datengrundlage)
   oder eine feinere Aufloesung (``m1``/``m5``, je nach geladenen Daten): dort
   wird die Bar-fuer-Bar-Reihenfolge von Fill/SL/TP tatsaechlich aufgeloest,
   statt bei einer Kollision in der groben Bar zu raten.
2c. Trailing-Stop (optional, via ``Signal.meta["trail_atr_mult"]``): Chandelier-
    Stil, Ratchet-only (Stop wird nie gelockert), aktualisiert mit der gerade
    geschlossenen Bar, wirkt ab der naechsten Bar — kein Lookahead.
3. Bar-Close: Floating-PnL-Update an Risk-Engine, Time-Exits, dann
   ``strategy.on_bar(bars, i)`` mit aligned Views (nur geschlossene Bars).
   ``i`` ist die Position der aktuellen Bar im View ``bars[timeframes[0]]``
   (SPEC §4.1); die Views enthalten Warmup-Historie vor dem Backtest-Fenster,
   d.h. ``i`` ist bei Fensterläufen (WFA) groesser als der Fenster-Index.

Keine Abhaengigkeit vom MetaTrader5-Pip-Paket. Daten werden injiziert
(``data``) oder lazy ueber ``core.connector.load_ohlcv`` geladen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from core.reporting import TRADE_COLUMNS, compute_metrics
from core.risk import RiskConfig, RiskManager


def _wilder_atr_series(df: pd.DataFrame, n: int) -> pd.Series:
    """ATR nach Wilder (SMA-Seed), lokale Kopie fuer den Trailing-Stop —
    bewusst kein Import aus core.indicators/strategies.base (Engine bleibt
    frei von Strategie-Layer-Abhaengigkeiten, wie im Rest dieser Datei)."""
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    v = tr.to_numpy(dtype="float64")
    out = np.full(len(v), np.nan, dtype="float64")
    valid = np.flatnonzero(~np.isnan(v))
    if len(valid) < n:
        return pd.Series(out, index=df.index, dtype="float64")
    seed_pos = int(valid[n - 1])
    prev = float(np.mean(v[valid[:n]]))
    out[seed_pos] = prev
    for t in range(seed_pos + 1, len(v)):
        if np.isnan(v[t]):
            continue
        prev = (prev * (n - 1) + v[t]) / n
        out[t] = prev
    return pd.Series(out, index=df.index, dtype="float64")

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}


# ---------------------------------------------------------------------------
# Kontrakte (SPEC §4.2)
# ---------------------------------------------------------------------------
@dataclass
class CostModel:
    # Alle *_points-Angaben in MT5-Punkten (point = kleinste Preiseinheit des
    # Symbols, BacktestConfig.point). Die Umrechnung in Preiseinheiten
    # (x point) erfolgt in _spread_cost.
    spread_points: float                 # halber Spread beim Entry, halber beim Exit
    slippage_multiplier: float = 1.0     # Stress-Faktor
    commission_per_lot_rt: float = 0.0
    swap_long_pts: float = 0.0
    swap_short_pts: float = 0.0
    triple_swap_weekday: int = 2         # Mittwoch
    slippage_extra_points: float = 0.0   # zusaetzlich fix, nur Market-Orders


@dataclass
class BacktestConfig:
    symbol: str
    timeframes: list[str]
    start: datetime
    end: datetime
    costs: CostModel
    risk: RiskConfig
    intrabar: str = "stop_first"         # oder "m1"/"m5" wenn die Daten geladen sind
    point_value: float = 1.0             # aus Symbol-Spec, siehe connector
    account_ccy_rate: float = 1.0
    # Ergaenzungen (additive Defaults, kein Kontrakt-Bruch):
    point: float = 1.0                   # kleinste Preiseinheit (MT5-point);
                                         # 1.0 = Points sind Preiseinheiten
    initial_balance: float = 100_000.0
    volume_step: float = 0.01
    volume_min: float = 0.01
    volume_max: float = 100.0
    server_day_offset_hours: float = 0.0  # Server-Tag = UTC-Tag + Offset


@dataclass
class BacktestResult:
    trades: pd.DataFrame                 # Spalten: siehe reporting.TRADE_COLUMNS
    equity_curve: pd.DataFrame           # index=UTC ts, Spalten [balance, equity]
    metrics: dict                        # via core.reporting.compute_metrics
    config: BacktestConfig | None = None
    # Beobachtbarkeit fuer den stop_first-Fallback (kein feineres TF geladen):
    # "limit_sl_collision_discards" zaehlt Pending-Limits, die verworfen statt
    # als Verlust gezaehlt wurden, weil Limit+SL in derselben Grob-Bar beruehrt
    # wurden (s. Docstring oben). Hoher Wert relativ zu n(trades) -> Kandidat
    # fuer intrabar=m1/m5, falls feinere Daten verfuegbar sind.
    diagnostics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Interne Position / Pending-Order
# ---------------------------------------------------------------------------
@dataclass
class _Position:
    direction: int
    entry: float
    sl: float
    tp: float | None
    lots: float
    entry_time: pd.Timestamp
    entry_bar: int
    signal_time: pd.Timestamp
    risk_money: float
    time_exit_bars: int = 0
    meta: dict = field(default_factory=dict)
    # Trailing-Stop (Chandelier-Stil, optional via Signal.meta): 0 = aus.
    trail_atr_mult: float = 0.0
    trail_atr_len: int = 14
    trail_extreme: float = float("nan")
    # "Move-to-Trail": TP-Beruehrung schliesst NICHT — stattdessen wird der SL
    # sofort auf das TP-Niveau gezogen (Mindest-RR gesichert) und das TP
    # geloescht; ab dann uebernimmt der Trailing-Stop von diesem Niveau aus
    # (s. Backtester._resolve_sl_tp). Ohne den SL-Lock waere das wirkungsgleich
    # mit "gar kein TP" — ein Rueckschlag koennte den Gewinn wieder auffressen.
    tp_converts_to_trail: bool = False


@dataclass
class _PendingLimit:
    direction: int
    limit_price: float
    sl: float
    tp: float | None
    risk_pct: float
    signal_time: pd.Timestamp
    expires_bars: int
    placed_bar: int
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------
class Backtester:
    def __init__(self, strategy, config: BacktestConfig, data: dict[str, pd.DataFrame] | None = None):
        self.strategy = strategy
        self.config = config
        if config.intrabar != "stop_first" and config.intrabar.upper() not in TF_MINUTES:
            raise ValueError(f"intrabar unbekannt: {config.intrabar}")
        if data is None:
            from core.connector import load_ohlcv  # lazy: kein MT5-Import im Test
            data = {
                tf: load_ohlcv(config.symbol, tf, config.start, config.end)
                for tf in config.timeframes
            }
        self.data = {tf: self._validate(df, tf) for tf, df in data.items()}
        if config.timeframes[0] not in self.data:
            raise ValueError(f"Execution-TF {config.timeframes[0]} fehlt in Daten")
        self._diag = {"limit_sl_collision_discards": 0}
        self._atr_full_cache: dict[int, pd.Series] = {}
        self.risk = RiskManager(
            config.risk,
            initial_balance=config.initial_balance,
            server_day_offset_hours=config.server_day_offset_hours,
        )

    def _atr_full(self, n: int) -> pd.Series:
        """ATR(n) ueber die volle Primary-TF-Reihe, je Laenge einmal berechnet
        und gecacht (fuer den Trailing-Stop, s. _Position.trail_atr_*)."""
        if n not in self._atr_full_cache:
            full = self.data[self.config.timeframes[0]]
            self._atr_full_cache[n] = _wilder_atr_series(full, n)
        return self._atr_full_cache[n]

    # -- Daten-Validierung (§3 Daten-Kontrakt) -------------------------------
    @staticmethod
    def _validate(df: pd.DataFrame, tf: str) -> pd.DataFrame:
        if tf not in TF_MINUTES:
            raise ValueError(f"Timeframe unbekannt: {tf}")
        missing = {"open", "high", "low", "close", "tick_volume"} - set(df.columns)
        if missing:
            raise ValueError(f"Spalten fehlen ({tf}): {missing}")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(f"{tf}: Index muss DatetimeIndex sein")
        if df.index.tz is None:
            raise ValueError(f"{tf}: Index muss tz-aware UTC sein")
        df = df.sort_index()
        if str(df.index.tz) != "UTC":
            df = df.tz_convert("UTC")
        return df

    # -- Kosten ---------------------------------------------------------------
    def _spread_cost(self, market_order: bool) -> float:
        """Spread-/Slippage-Kosten in Preiseinheiten (Points x point)."""
        c = self.config.costs
        point = self.config.point
        mult = c.slippage_multiplier if market_order else 1.0
        cost = 0.5 * c.spread_points * point * mult
        if market_order:
            cost += c.slippage_extra_points * point
        return cost

    def _swap_cost(self, pos: _Position, exit_time: pd.Timestamp) -> float:
        """Swap in Account-CCY: je gehaltener Server-Mitternacht 1x, am
        ``triple_swap_weekday`` (Ende des Tages) 3x."""
        c = self.config.costs
        pts = c.swap_long_pts if pos.direction > 0 else c.swap_short_pts
        if pts == 0.0:
            return 0.0
        offset = pd.Timedelta(hours=self.config.server_day_offset_hours)
        entry_srv = pos.entry_time + offset
        exit_srv = exit_time + offset
        # Mitternaechte (Server), die waehrend der Haltedauer ueberschritten werden
        first_midnight = entry_srv.normalize() + pd.Timedelta(days=1)
        total = 0.0
        m = first_midnight
        while m <= exit_srv:
            day_ending = (m - pd.Timedelta(seconds=1)).date()
            mult = 3 if day_ending.weekday() == c.triple_swap_weekday else 1
            total += pts * mult
            m += pd.Timedelta(days=1)
        # Swap-Punkte -> Preiseinheiten (x point) -> Account-CCY
        return (total * self.config.point * pos.lots
                * self.config.point_value * self.config.account_ccy_rate)

    # -- Entry ------------------------------------------------------------------
    def _open_position(self, sig_direction: int, raw_price: float, ts: pd.Timestamp,
                       bar_i: int, signal_time: pd.Timestamp, sl: float, tp,
                       risk_pct: float, meta: dict, market_order: bool) -> _Position | None:
        # Market: Slippage adverse (x slippage_multiplier + extra);
        # Limit: Fill zum Limit-Preis, nur halber Spread (multiplier-neutral).
        cost = self._spread_cost(market_order)
        fill = raw_price + sig_direction * cost
        balance = self._balance
        lots = self.risk.calc_lots(
            balance, fill, sl, self.config.point_value,
            self.config.volume_step, self.config.volume_min, self.config.volume_max,
        )
        risk_money = abs(fill - sl) * lots * self.config.point_value * self.config.account_ccy_rate
        if lots <= 0 or risk_money <= 0:
            return None
        self._balance -= self.config.costs.commission_per_lot_rt * lots / 2.0  # halbe RT beim Entry
        return _Position(
            direction=sig_direction, entry=fill, sl=sl, tp=tp, lots=lots,
            entry_time=ts, entry_bar=bar_i, signal_time=signal_time,
            risk_money=risk_money, time_exit_bars=int(meta.get("time_exit_bars", 0) or 0),
            meta=dict(meta),
            trail_atr_mult=float(meta.get("trail_atr_mult", 0.0) or 0.0),
            trail_atr_len=int(meta.get("trail_atr_len", 14) or 14),
            trail_extreme=fill,
            tp_converts_to_trail=bool(meta.get("tp_converts_to_trail", False)),
        )

    # -- Exit ---------------------------------------------------------------------
    def _close_position(self, pos: _Position, raw_price: float, ts: pd.Timestamp,
                        reason: str, market_order: bool) -> dict:
        cost = self._spread_cost(market_order)
        exit_fill = raw_price - pos.direction * cost
        pnl_pts = pos.direction * (exit_fill - pos.entry)
        gross = pnl_pts * pos.lots * self.config.point_value * self.config.account_ccy_rate
        commission = self.config.costs.commission_per_lot_rt * pos.lots / 2.0  # zweite Haelfte
        swap = self._swap_cost(pos, ts)
        pnl = gross - commission - swap
        self._balance += pnl
        trade = {
            "entry_time": pos.entry_time, "exit_time": ts,
            "direction": pos.direction, "entry": pos.entry, "exit": exit_fill,
            "sl": pos.sl, "tp": pos.tp, "lots": pos.lots, "pnl": pnl,
            "r_multiple": pnl / pos.risk_money if pos.risk_money > 0 else 0.0,
            "meta": {**pos.meta, "exit_reason": reason, "signal_time": pos.signal_time},
        }
        self.risk.register_closed_trade(pnl, ts)
        cb = getattr(self.strategy, "on_trade_closed", None)
        if callable(cb):
            cb(trade)
        return trade

    # -- Intrabar-Aufloesung ---------------------------------------------------------
    def _resolve_sl_tp(self, pos: _Position, o: float, h: float, l: float,
                       m1_slice: pd.DataFrame | None) -> tuple[float, str, bool] | None:
        """Liefert (exit_raw_price, reason, is_market) oder None.

        Konservativ: Gap-Open jenseits SL/TP fuellt zum Open; SL-Touch vor
        TP-Touch, wenn beide in derselben Bar (stop_first). Im m1-Modus wird
        die Reihenfolge ueber M1-Bars aufgeloest.

        ``pos.tp_converts_to_trail``: eine TP-Beruehrung schliesst NICHT die
        Position. Stattdessen wird der SL SOFORT auf das TP-Niveau gezogen
        (Lock-in — ohne das waere "Move-to-Trail" wirkungsgleich mit "gar
        kein TP", da der Trail sonst ab dem urspruenglichen, weit entfernten
        SL weiterlaeuft und ein Rueckschlag den gesamten Gewinn wieder
        auffressen koennte) und ``pos.tp`` geloescht (mutiert ``pos`` direkt)
        — ab dann greift nur noch der Trailing-Stop (Schritt 2c in run()),
        der von diesem bereits gesicherten Niveau aus nur noch guenstiger
        nachzieht. SL hat weiterhin Prioritaet, falls beide in derselben Bar
        beruehrt werden.
        """
        d = pos.direction
        convert = pos.tp_converts_to_trail and pos.trail_atr_mult > 0

        def lock_and_convert() -> None:
            pos.sl = pos.tp  # Mindest-RR sichern, bevor TP geloescht wird
            pos.tp = None

        def touches(bar_h, bar_l) -> tuple[bool, bool]:
            tp = pos.tp
            if d > 0:
                return bar_l <= pos.sl, (tp is not None and bar_h >= tp)
            return bar_h >= pos.sl, (tp is not None and bar_l <= tp)

        def gap_check(bar_o) -> tuple[float, str, bool] | None:
            tp = pos.tp
            if d > 0:
                if bar_o <= pos.sl:
                    return bar_o, "sl_gap", True
                if tp is not None and bar_o >= tp:
                    return bar_o, "tp_gap", True
            else:
                if bar_o >= pos.sl:
                    return bar_o, "sl_gap", True
                if tp is not None and bar_o <= tp:
                    return bar_o, "tp_gap", True
            return None

        if m1_slice is not None and len(m1_slice) > 0:
            for ts, row in m1_slice.iterrows():
                g = gap_check(row["open"])
                if g is not None:
                    if g[1] == "tp_gap" and convert:
                        lock_and_convert()
                    else:
                        return g
                hit_sl, hit_tp = touches(row["high"], row["low"])
                if hit_sl:  # konservativ auch innerhalb der M1-Bar: SL zuerst
                    return pos.sl, "sl", True
                if hit_tp:
                    if convert:
                        lock_and_convert()
                    else:
                        return pos.tp, "tp", False
            return None

        g = gap_check(o)
        if g is not None:
            if g[1] == "tp_gap" and convert:
                lock_and_convert()
            else:
                return g
        hit_sl, hit_tp = touches(h, l)
        if hit_sl:
            return pos.sl, "sl", True
        if hit_tp:
            if convert:
                lock_and_convert()
            else:
                return pos.tp, "tp", False
        return None

    # -- Pending-Limit-Fill ------------------------------------------------------------
    def _try_fill_limit_fine(self, order: _PendingLimit,
                             fine_slice: pd.DataFrame) -> tuple[bool, tuple | None]:
        """Loest Fill + SL/TP ueber die feineren Bars (m1/m5) chronologisch auf,
        statt bei Kollision in der groben Bar zu raten.

        Liefert (filled, res): ``filled`` False solange der Limit-Preis noch
        nicht beruehrt wurde; sobald gefuellt, wird ab genau dieser Fine-Bar
        (inklusive) weiter auf SL/TP geprueft — konservativ SL vor TP, wie
        ``_resolve_sl_tp``. ``res`` ist ``None``, wenn gefuellt aber bis zum
        Ende dieser Grob-Bar keine SL/TP-Beruehrung folgte (Position bleibt
        offen, normale Weiterfuehrung ab der naechsten Grob-Bar); sonst
        ``(exit_raw_price, reason, is_market)`` wie bei ``_resolve_sl_tp``.
        """
        d = order.direction
        sl, tp = order.sl, order.tp
        filled = False
        for _ts, row in fine_slice.iterrows():
            o_, h_, l_ = row["open"], row["high"], row["low"]
            if not filled:
                if not (l_ <= order.limit_price <= h_):
                    continue
                filled = True
            if d > 0:
                if l_ <= sl:
                    return True, (sl, "sl", True)
                if tp is not None and h_ >= tp:
                    return True, (tp, "tp", False)
            else:
                if h_ >= sl:
                    return True, (sl, "sl", True)
                if tp is not None and l_ <= tp:
                    return True, (tp, "tp", False)
        return filled, None

    @staticmethod
    def _as_utc(ts) -> pd.Timestamp:
        t = pd.Timestamp(ts)
        return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")

    # -- Hauptlauf ------------------------------------------------------------------------
    def run(self) -> BacktestResult:
        cfg = self.config
        tf_primary = cfg.timeframes[0]
        df = self.data[tf_primary]
        start, end = self._as_utc(cfg.start), self._as_utc(cfg.end)
        df = df.loc[(df.index >= start) & (df.index <= end)]
        if len(df) == 0:
            raise ValueError("Keine Bars im Backtest-Zeitraum")
        idx = df.index
        delta = pd.Timedelta(minutes=TF_MINUTES[tf_primary])
        n = len(df)

        required = getattr(self.strategy, "required_timeframes", None) or cfg.timeframes
        required = [tf for tf in required if tf in self.data]
        if tf_primary not in required:
            required = [tf_primary] + required

        # Aligned Views: Anzahl geschlossener Bars je TF zum Close jeder Primary-Bar
        # searchsorted direkt auf DatetimeIndex (unit-sicher, pandas 3 nutzt
        # je nach Index s/ms/us/ns statt immer ns)
        close_primary = idx + delta
        counts: dict[str, np.ndarray] = {}
        for tf in required:
            tdf = self.data[tf]
            close_tf = tdf.index + pd.Timedelta(minutes=TF_MINUTES[tf])
            counts[tf] = close_tf.searchsorted(close_primary, side="right")

        fine_tf = cfg.intrabar.upper() if cfg.intrabar != "stop_first" else None
        fine = self.data.get(fine_tf) if fine_tf else None
        fine_idx = fine.index if fine is not None else None

        opens = df["open"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()

        # Lauf-lokaler ATR-Cache je angefragter Laenge fuer Trailing-Stops,
        # auf dieses Fenster (idx) ausgerichtet — Basisreihe je Laenge nur
        # einmal berechnet (self._atr_full), hier nur reindiziert.
        trail_atr_arrays: dict[int, np.ndarray] = {}

        def _trail_atr_at(n: int, pos_i: int) -> float | None:
            arr = trail_atr_arrays.get(n)
            if arr is None:
                arr = self._atr_full(n).reindex(idx).to_numpy()
                trail_atr_arrays[n] = arr
            v = arr[pos_i]
            return None if np.isnan(v) else float(v)

        self._balance = float(cfg.initial_balance)
        positions: list[_Position] = []
        pendings: list[_PendingLimit] = []
        next_market_signals: list = []  # Signale der Vorbar, Entry am Open
        trades: list[dict] = []
        eq_ts, eq_bal, eq_eq = [], [], []
        prev_t_open: pd.Timestamp | None = None

        for i in range(n):
            t_open = idx[i]
            t_close = t_open + delta
            o, h, l, cl = opens[i], highs[i], lows[i], closes[i]

            # 1a) Force-Flat-Luecke: eine Deadline, die STILLSCHWEIGEND
            # zwischen der Vorbar und dieser Bar verschluckt wurde (typisch:
            # Wochenend-Luecke schluckt die Freitags-EOD-Zeit). Exit zum
            # letzten bekannten Preis (Close der Vorbar) — sonst wuerde die
            # Wochenend-Gap-Bewegung faelschlich als PnL realisiert, obwohl
            # die Position live laengst geschlossen gewesen waere.
            if positions and self.risk.force_flat_gap(prev_t_open, t_open, bar_interval=delta):
                for pos in positions:
                    trades.append(self._close_position(
                        pos, closes[i - 1], prev_t_open + delta, "force_flat_gap", True))
                positions = []
                pendings = []

            # 1b) Force-Flat durch Risk-Engine (EOD-NY, Friday, Prop-Breach)
            if positions and self.risk.force_flat(t_open):
                for pos in positions:
                    trades.append(self._close_position(pos, o, t_open, "force_flat", True))
                positions = []
                pendings = []

            # 1b) Market-Entries am Open (Signal der geschlossenen Vorbar)
            if next_market_signals:
                sigs, next_market_signals = next_market_signals, []
                for sig in sigs:
                    if self.risk.can_open(t_open, len(positions)):
                        pos = self._open_position(
                            sig.direction, o, t_open, i, sig.time, sig.stop_loss,
                            sig.take_profit, sig.risk_pct, sig.meta, market_order=True)
                        if pos is not None:
                            positions.append(pos)

            # Feinere Bars (m1/m5) fuer diese Grob-Bar — einmal berechnet,
            # von 2a (Pending-Fill) und 2b (SL/TP offener Positionen) genutzt.
            fine_slice = None
            if fine is not None:
                lo = fine_idx.searchsorted(t_open, side="left")
                hi = fine_idx.searchsorted(t_close, side="left")
                fine_slice = fine.iloc[lo:hi]

            # 2a) Pending-Limit-Fills auf dieser Bar
            still_pending = []
            just_filled_open: set[int] = set()  # id(pos): schon in dieser Bar via Fine-Aufloesung geprueft
            for order in pendings:
                if order.expires_bars and (i - order.placed_bar) > order.expires_bars:
                    continue
                d = order.direction
                if fine_slice is not None and len(fine_slice) > 0:
                    filled, res = self._try_fill_limit_fine(order, fine_slice)
                    if not filled:
                        still_pending.append(order)
                        continue
                    if not self.risk.can_open(t_open, len(positions)):
                        continue
                    pos = self._open_position(
                        d, order.limit_price, t_open, i, order.signal_time,
                        order.sl, order.tp, order.risk_pct, order.meta, market_order=False)
                    if pos is None:
                        continue
                    if res is None:
                        # Gefuellt, aber bis Bar-Ende (Fine-Aufloesung) kein SL/TP-Touch
                        # -> offen, in 2b NICHT nochmal mit der groben Bar-Range pruefen
                        # (die enthaelt auch die Zeit VOR dem Fill).
                        positions.append(pos)
                        just_filled_open.add(id(pos))
                    else:
                        raw, reason, is_market = res
                        trades.append(self._close_position(pos, raw, t_close, reason, is_market))
                    continue
                # Fallback ohne feinere Daten (stop_first): grobe Bar-Range,
                # Kollision Limit+SL in derselben Bar -> verworfen (einzig
                # moegliche konservative Annahme ohne bessere Datengrundlage).
                touched = (l <= order.limit_price) if d > 0 else (h >= order.limit_price)
                if not touched:
                    still_pending.append(order)
                    continue
                sl_touched = (l <= order.sl) if d > 0 else (h >= order.sl)
                if sl_touched:
                    self._diag["limit_sl_collision_discards"] += 1
                    continue  # konservativ: verworfen (SL waere zuerst dran)
                if self.risk.can_open(t_open, len(positions)):
                    pos = self._open_position(
                        d, order.limit_price, t_open, i, order.signal_time,
                        order.sl, order.tp, order.risk_pct, order.meta, market_order=False)
                    if pos is not None:
                        positions.append(pos)

            pendings = still_pending

            # 2b) SL/TP intrabar
            if positions:
                survivors = []
                for pos in positions:
                    if id(pos) in just_filled_open:
                        survivors.append(pos)  # bereits fuer diese Bar aufgeloest (s.o.)
                        continue
                    res = self._resolve_sl_tp(pos, o, h, l, fine_slice)
                    if res is None:
                        survivors.append(pos)
                    else:
                        raw, reason, is_market = res
                        # Exit-Zeit = Bar-Close (Touch-Zeitpunkt intrabar unbekannt)
                        trades.append(self._close_position(pos, raw, t_close, reason, is_market))
                positions = survivors

            # 2c) Trailing-Stop-Update — NACH der SL/TP-Pruefung dieser Bar,
            # mit dieser (jetzt geschlossenen) Bar; wirkt erst ab der naechsten
            # Bar (kein Lookahead, gleiches Prinzip wie Signal->Fill naechste Bar).
            # Ratchet-only: der Stop wird nie gelockert, nur in Gewinnrichtung
            # nachgezogen (Chandelier-Stil).
            for pos in positions:
                if pos.trail_atr_mult <= 0:
                    continue
                atr_val = _trail_atr_at(pos.trail_atr_len, i)
                if atr_val is None or atr_val <= 0:
                    continue
                if pos.direction > 0:
                    pos.trail_extreme = max(pos.trail_extreme, h)
                    candidate = pos.trail_extreme - pos.trail_atr_mult * atr_val
                    if candidate > pos.sl:
                        pos.sl = candidate
                else:
                    pos.trail_extreme = min(pos.trail_extreme, l)
                    candidate = pos.trail_extreme + pos.trail_atr_mult * atr_val
                    if candidate < pos.sl:
                        pos.sl = candidate

            # 3a) Floating-PnL-Update (Bar-Close) an Risk-Engine
            floating = sum(
                p.direction * (cl - p.entry) * p.lots * cfg.point_value * cfg.account_ccy_rate
                for p in positions
            )
            self.risk.update(t_close, self._balance, floating)
            eq_ts.append(t_close)
            eq_bal.append(self._balance)
            eq_eq.append(self._balance + floating)

            # 3b) Time-Exit (Strategie-deklariert via meta["time_exit_bars"])
            survivors = []
            for pos in positions:
                if pos.time_exit_bars and (i - pos.entry_bar) >= pos.time_exit_bars:
                    trades.append(self._close_position(pos, cl, t_close, "time_exit", True))
                else:
                    survivors.append(pos)
            positions = survivors

            # 3c) Strategie-Callback (nur geschlossene Bars bis inkl. i)
            # i_abs: Position der aktuellen Bar im View (SPEC §4.1: "bars bis
            # inkl. Index i"). Views enthalten Warmup-Historie VOR dem Fenster,
            # darum ist i_abs != i, sobald start > Datenanfang (WFA-Folds!).
            i_abs = int(counts[tf_primary][i]) - 1
            bars = {tf: self.data[tf].iloc[: counts[tf][i]] for tf in required}
            sig = self.strategy.on_bar(bars, i_abs)
            if sig is not None:
                st = pd.Timestamp(sig.time)
                if st.tzinfo is None:
                    st = st.tz_localize("UTC")
                if st > t_open:
                    raise ValueError(f"Lookahead: Signal-Zeit {st} > aktuelle Bar {t_open}")
                if sig.entry_type == "market":
                    next_market_signals.append(sig)
                elif sig.entry_type == "limit":
                    pendings = [p for p in pendings]  # neuere Signale ersetzen gleiche Richtung
                    pendings.append(_PendingLimit(
                        direction=sig.direction, limit_price=float(sig.entry_price),
                        sl=sig.stop_loss, tp=sig.take_profit, risk_pct=sig.risk_pct,
                        signal_time=st, expires_bars=int(sig.expires_bars or 0),
                        placed_bar=i, meta=dict(sig.meta)))
                else:
                    raise ValueError(f"entry_type unbekannt: {sig.entry_type}")

            prev_t_open = t_open

        # Ende der Daten: Restpositionen zum letzten Close glattstellen
        t_final = idx[-1] + delta
        for pos in positions:
            trades.append(self._close_position(pos, closes[-1], t_final, "end_of_data", True))

        trades_df = pd.DataFrame(trades, columns=TRADE_COLUMNS)
        if len(trades_df):
            trades_df = trades_df.sort_values("exit_time").reset_index(drop=True)
        equity_curve = pd.DataFrame(
            {"balance": eq_bal, "equity": eq_eq},
            index=pd.DatetimeIndex(eq_ts, tz="UTC", name="time"),
        )
        metrics = compute_metrics(trades_df, equity_curve=equity_curve["equity"])
        return BacktestResult(trades=trades_df, equity_curve=equity_curve,
                              metrics=metrics, config=cfg, diagnostics=dict(self._diag))
