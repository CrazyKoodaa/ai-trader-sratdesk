"""core/connector.py — pymt5linux/RPyC-Abstraktion (SPEC §4.10) + Daten-Kontrakt (SPEC §3).

Architektur (SPEC §1/§2):
- MT5 laeuft unter Wine; dort serviert ein Windows-Python den RPyC-Server
  (``wine python -m pymt5linux``). Diese Seite ist der *Client* (natives Linux).
- Die rpyc-Version muss BEIDSEITIG identisch sein (Major-Versionen 5.x/6.x
  sind wire-inkompatibel; Stand 2026-09-04: 6.0.2, siehe SPEC §1).
- Import von ``pymt5linux``/``rpyc`` ist LAZY (erst in connect()), damit
  Backtest-Code und Tests ohne MT5-Stack laufen (SPEC §1).

UTC-at-ingestion (SPEC §3): ``fetch_ohlcv`` konvertiert die Serverzeit via
``server_offset()`` (Tick-Zeit vs. utc_now) sofort nach UTC, tz-aware.

Capping: MT5 kappt History gemaess "Max bars in chart". ``fetch_ohlcv``
laedt in Zeit-Chunks (umgeht per-Request-Caps) und WARNT, wenn der Server
weniger Historie liefert als angefordert (=> Setting auf "Unlimited").
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

UTC = timezone.utc

# SPEC §3
OHLCV_COLUMNS = ["open", "high", "low", "close", "tick_volume"]
TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}

# MT5-ENUM-Fallbacks (werden bevorzugt vom pymt5linux-Modul gelesen).
_MT5_CONSTANTS = {
    "TIMEFRAME_M1": 1,
    "TIMEFRAME_M5": 5,
    "TIMEFRAME_M15": 15,
    "TIMEFRAME_H1": 16385,
    "TIMEFRAME_H4": 16388,
    "TIMEFRAME_D1": 16408,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
    "ORDER_TYPE_BUY_LIMIT": 2,
    "ORDER_TYPE_SELL_LIMIT": 3,
    "TRADE_ACTION_DEAL": 1,
    "TRADE_ACTION_PENDING": 5,
    "TRADE_ACTION_SLTP": 6,
    "ORDER_TIME_GTC": 0,
    "ORDER_FILLING_FOK": 0,
    "ORDER_FILLING_IOC": 1,
    "ORDER_FILLING_RETURN": 2,
    "ACCOUNT_TRADE_MODE_DEMO": 0,
    "ACCOUNT_TRADE_MODE_CONTEST": 1,
    "ACCOUNT_TRADE_MODE_REAL": 2,
    "DEAL_ENTRY_OUT": 1,
}

# Retcodes (ENUM_TRADE_RETURN_CODES)
RETCODE_DONE = 10009
RETCODE_INVALID_PRICE = 10015   # Preis veraltet -> neu quotieren, Retry
RETCODE_INVALID_STOPS = 10016   # SL/TP zu nah -> auf stops_level snappen, Retry
RETCODE_UNSUPPORTED_FILLING = 10030  # Filling-Mode -> naechsten Modus, Retry
RETRY_RETCODES = {RETCODE_INVALID_PRICE, RETCODE_INVALID_STOPS, RETCODE_UNSUPPORTED_FILLING}


# ---------------------------------------------------------------------------
# Daten-Kontrakt (SPEC §3): Validierung + Gap-Audit
# ---------------------------------------------------------------------------
@dataclass
class GapReport:
    """Ergebnis von ``audit_gaps`` (SPEC §3)."""

    timeframe: str
    n_bars: int
    n_missing: int
    # (erster_fehlender_bar, letzter_fehlender_bar, anzahl)
    gaps: list[tuple[pd.Timestamp, pd.Timestamp, int]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.n_missing == 0

    def summary(self) -> str:
        if self.ok:
            return f"Gap-Audit {self.timeframe}: OK ({self.n_bars} Bars, keine Luecken)"
        lines = [
            f"Gap-Audit {self.timeframe}: {self.n_missing} fehlende Bars "
            f"in {len(self.gaps)} Luecken (gesamt {self.n_bars} Bars)"
        ]
        for first, last, n in self.gaps[:20]:
            lines.append(f"  - {first} .. {last} ({n} Bars)")
        if len(self.gaps) > 20:
            lines.append(f"  ... und {len(self.gaps) - 20} weitere")
        return "\n".join(lines)


def _is_market_closed(ts: pd.Timestamp, close_fri_hour: int = 21, open_sun_hour: int = 21) -> bool:
    """Grobe FX-Wochenend-Regel (UTC): Fr ab 21:00 bis So 21:00 geschlossen."""
    wd = ts.weekday()
    if wd == 5:  # Samstag
        return True
    if wd == 4 and ts.hour >= close_fri_hour:  # Freitag ab close
        return True
    if wd == 6 and ts.hour < open_sun_hour:  # Sonntag vor open
        return True
    return False


def audit_gaps(df: pd.DataFrame, timeframe: str) -> GapReport:
    """Meldet fehlende Bars ausserhalb des Wochenendes (SPEC §3).

    Erwartet den Daten-Kontrakt: tz-aware UTC-Index, OHLCV-Spalten.
    """
    tf = timeframe.upper()
    if tf not in TF_MINUTES:
        raise ValueError(f"Unbekannter Timeframe: {timeframe}")
    freq = pd.Timedelta(minutes=TF_MINUTES[tf])
    report = GapReport(timeframe=tf, n_bars=len(df), n_missing=0)
    if len(df) < 2:
        return report

    idx = df.index.sort_values()
    gaps: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []
    for prev, cur in zip(idx[:-1], idx[1:]):
        delta = cur - prev
        if delta <= freq:
            continue
        # Alle erwarteten Bar-Zeiten zwischen prev und cur
        n_missing_total = int(delta / freq) - 1
        expected = pd.date_range(prev + freq, periods=n_missing_total, freq=freq, tz=UTC)
        outside_weekend = [t for t in expected if not _is_market_closed(t)]
        if outside_weekend:
            gaps.append((outside_weekend[0], outside_weekend[-1], len(outside_weekend)))
    report.gaps = gaps
    report.n_missing = sum(g[2] for g in gaps)
    return report


def validate_ohlcv(df: pd.DataFrame, timeframe: str | None = None) -> pd.DataFrame:
    """Erzwingt den SPEC-§3-Kontrakt: Spalten + tz-aware UTC-Index, sortiert."""
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV-Spalten fehlen: {missing}")
    out = df[OHLCV_COLUMNS].astype("float64").copy()
    if out.index.tz is None:
        raise ValueError("Index muss tz-aware (UTC) sein — UTC-at-ingestion (SPEC §3)")
    out.index = out.index.tz_convert(UTC)
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def load_ohlcv(symbol: str, timeframe: str, start: datetime, end: datetime,
               source: str = "cache", data_dir: str | Path = "data",
               connector: "MT5Connector | None" = None) -> pd.DataFrame:
    """Daten-Kontrakt-Funktion (SPEC §3).

    source:
      - "cache": ``data_dir/{SYMBOL}_{TF}.parquet`` (bevorzugt) oder
        ``.csv`` (Fallback), UTC-Index, gefiltert.
      - "mt5":   live via MT5Connector (``connector`` injizierbar fuer Tests).
    """
    tf = timeframe.upper()
    if tf not in TF_MINUTES:
        raise ValueError(f"Unbekannter Timeframe: {timeframe}")
    start_utc = pd.Timestamp(start)
    end_utc = pd.Timestamp(end)
    if start_utc.tzinfo is None:
        start_utc = start_utc.tz_localize(UTC)
    if end_utc.tzinfo is None:
        end_utc = end_utc.tz_localize(UTC)

    if source == "cache":
        base = Path(data_dir) / f"{symbol}_{tf}"
        pq = base.with_suffix(".parquet")
        if pq.exists():
            df = pd.read_parquet(pq)
        else:
            path = base.with_suffix(".csv")
            if not path.exists():
                raise FileNotFoundError(
                    f"Keine Cache-Datei: {pq} oder {path} "
                    "(erst scripts/fetch_data.py ausfuehren)"
                )
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.DatetimeIndex(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize(UTC)
        df = validate_ohlcv(df, tf)
        return df.loc[(df.index >= start_utc) & (df.index < end_utc)]

    if source == "mt5":
        conn = connector or MT5Connector()
        try:
            conn.connect()
            return conn.fetch_ohlcv(symbol, tf, start_utc, end_utc)
        finally:
            if connector is None:
                conn.disconnect()

    raise ValueError(f"Unbekannte Quelle: {source!r} (cache|mt5)")


# ---------------------------------------------------------------------------
# MT5Connector (SPEC §4.10)
# ---------------------------------------------------------------------------
class MT5Connector:
    """Wrappt den rpyc-Client von pymt5linux (``pymt5linux.MetaTrader5``).

    Harte Regeln:
    - ``dry_run`` ist True per Default (Klassenebene + Instanz). Im Dry-Run
      werden Orders NUR geloggt — nichts geht zum Server.
    - Retry bei Retcodes 10015/10016/10030: max. ``max_retries`` Versuche,
      exponential backoff (``backoff_base * 2**attempt`` s).
    """

    dry_run: bool = True  # Klassen-Default: SICHER (nur Loggen)

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        dry_run: bool | None = None,
        magic: int = 20260903,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        chunk_bars: int = 5000,
        client=None,
    ):
        self.host = host
        self.port = port
        if dry_run is not None:
            self.dry_run = bool(dry_run)
        self.magic = magic
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.chunk_bars = chunk_bars
        self._mt5 = client          # Fake-Client injizierbar (Tests)
        self._connected = client is not None

    # -- Konstanten ------------------------------------------------------
    def _const(self, name: str) -> int:
        if self._mt5 is not None and hasattr(self._mt5, name):
            return int(getattr(self._mt5, name))
        return _MT5_CONSTANTS[name]

    # -- Verbindung ------------------------------------------------------
    def connect(self, host: str | None = None, port: int | None = None) -> None:
        """Verbindet zum RPyC-Server (``wine python -m pymt5linux``)."""
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if self._mt5 is None:
            try:
                from pymt5linux import MetaTrader5  # lazy, SPEC §1
            except ImportError as exc:
                raise ConnectionError(
                    "pymt5linux nicht installiert (braucht Python >= 3.13). "
                    "Client: pip install pymt5linux rpyc==6.0.2; Server (Wine): "
                    "wine python -m pymt5linux --host localhost --port <port> "
                    "<pfad-zu-python.exe>. rpyc-Version muss beidseitig identisch sein."
                ) from exc
            try:
                self._mt5 = MetaTrader5(host=self.host, port=self.port)
            except Exception as exc:
                raise ConnectionError(
                    f"RPyC-Connect zu {self.host}:{self.port} fehlgeschlagen: {exc}. "
                    "Laueft der pymt5linux-Server unter Wine? rpyc-Version beidseitig identisch?"
                ) from exc
        try:
            if hasattr(self._mt5, "initialize"):
                ok = self._mt5.initialize()
                if ok is False:
                    raise ConnectionError(f"mt5.initialize() fehlgeschlagen: {self._mt5.last_error()}")
        except ConnectionError:
            raise
        except Exception as exc:
            raise ConnectionError(f"MT5-Init fehlgeschlagen: {exc}") from exc
        self._connected = True
        log.info("MT5 verbunden (%s:%s, dry_run=%s)", self.host, self.port, self.dry_run)

    def disconnect(self) -> None:
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            except Exception:  # noqa: BLE001 - Server evtl. schon weg
                pass
        self._mt5 = None
        self._connected = False

    def _require_conn(self):
        if self._mt5 is None:
            raise ConnectionError("Nicht verbunden — connect() zuerst aufrufen")
        return self._mt5

    # -- Zeit / Offset ---------------------------------------------------
    def server_offset(self, symbol: str | None = None) -> timedelta:
        """Offset Serverzeit − UTC via symbol_info_tick().time vs. utc_now.

        Gerundet auf 15 min (Latenz-robust), konsistent zu
        ``core.time_engine.estimate_server_offset_utc``.
        """
        mt5 = self._require_conn()
        if symbol is None:
            symbol = self._default_symbol()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Kein Tick fuer {symbol} (Markt geschlossen/Symbol fehlt?)")
        try:
            from core.time_engine import estimate_server_offset_utc
            return estimate_server_offset_utc(int(tick.time))
        except ImportError:
            pass
        server_as_utc = datetime.fromtimestamp(int(tick.time), tz=UTC)
        raw = server_as_utc - datetime.now(UTC)
        return timedelta(minutes=15 * round(raw.total_seconds() / 900.0))

    def _default_symbol(self) -> str:
        mt5 = self._require_conn()
        symbols = mt5.symbols_get()
        if not symbols:
            raise RuntimeError("Keine Symbole vom Server")
        return symbols[0].name

    # -- Historie --------------------------------------------------------
    def fetch_ohlcv(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Laedt OHLCV, konvertiert Serverzeit->UTC (UTC-at-ingestion, SPEC §3).

        Chunking umgeht per-Request-Caps; "Max bars in chart"-Capping des
        Servers wird erkannt und als WARNUNG geloggt (Setting: Unlimited).
        """
        mt5 = self._require_conn()
        tf = timeframe.upper()
        if tf not in TF_MINUTES:
            raise ValueError(f"Unbekannter Timeframe: {timeframe}")
        tf_min = TF_MINUTES[tf]
        tf_const = self._const(f"TIMEFRAME_{tf}")

        start_utc = pd.Timestamp(start)
        end_utc = pd.Timestamp(end)
        if start_utc.tzinfo is None:
            start_utc = start_utc.tz_localize(UTC)
        if end_utc.tzinfo is None:
            end_utc = end_utc.tz_localize(UTC)

        offset = self.server_offset(symbol)
        chunk = pd.Timedelta(minutes=tf_min * self.chunk_bars)
        frames: list[pd.DataFrame] = []
        cur = start_utc
        while cur < end_utc:
            nxt = min(cur + chunk, end_utc)
            dt_from = (cur + offset).tz_localize(None).to_pydatetime()
            dt_to = (nxt + offset).tz_localize(None).to_pydatetime()
            rates = mt5.copy_rates_range(symbol, tf_const, dt_from, dt_to)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(np.asarray(rates))
                if "time" in df.columns:
                    # Server-Epoch -> UTC-Epoch -> tz-aware UTC
                    utc_epoch = df["time"].astype("int64") - int(offset.total_seconds())
                    df.index = pd.to_datetime(utc_epoch, unit="s", utc=True)
                    frames.append(df)
            cur = nxt

        if not frames:
            log.warning("fetch_ohlcv(%s %s): KEINE Daten vom Server "
                        "(Markt zu? Symbol falsch? 'Max bars in chart' zu klein?)",
                        symbol, tf)
            return pd.DataFrame(columns=OHLCV_COLUMNS,
                                index=pd.DatetimeIndex([], tz=UTC))

        out = pd.concat(frames)
        keep = [c for c in OHLCV_COLUMNS if c in out.columns]
        out = out[keep]
        for col in set(OHLCV_COLUMNS) - set(keep):
            out[col] = np.nan
        out = validate_ohlcv(out, tf)
        out = out.loc[(out.index >= start_utc) & (out.index < end_utc)]

        # --- "Max bars in chart"-Capping erkennen (Warnung) --------------
        tolerance = pd.Timedelta(minutes=tf_min * 10) + pd.Timedelta(days=2)  # Wochenende
        if len(out) and out.index[0] > start_utc + tolerance:
            log.warning(
                "CAPPING VERDACHT %s %s: erster Bar %s, angefordert ab %s — "
                "%d Bars fehlen am Anfang. MT5: Extras > Optionen > Charts > "
                "'Max bars in chart' = Unlimited setzen, dann neu fetchen.",
                symbol, tf, out.index[0], start_utc,
                int((out.index[0] - start_utc) / pd.Timedelta(minutes=tf_min)),
            )
        expected = int((end_utc - start_utc) / pd.Timedelta(minutes=tf_min)) * 5 // 7
        if expected > 100 and len(out) < expected * 0.5:
            log.warning(
                "CAPPING VERDACHT %s %s: nur %d von ~%d erwarteten Bars "
                "(Wochenenden grob abgezogen) — 'Max bars in chart' pruefen.",
                symbol, tf, len(out), expected,
            )
        return out

    # -- Konto / Positionen / Specs --------------------------------------
    @staticmethod
    def _as_dict(obj) -> dict:
        if obj is None:
            return {}
        if hasattr(obj, "_asdict"):
            return dict(obj._asdict())
        if isinstance(obj, dict):
            return dict(obj)
        return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}

    def account_info(self) -> dict:
        mt5 = self._require_conn()
        info = self._as_dict(mt5.account_info())
        keys = ("login", "balance", "equity", "margin", "margin_free",
                "margin_level", "currency", "leverage", "profit", "server", "name",
                "trade_mode")
        return {k: info[k] for k in keys if k in info}

    def is_demo_account(self) -> bool | None:
        """True/False, wenn ``trade_mode`` vom Server geliefert wird — sonst
        None (unbekannt). Sicherheitscheck fuer Live-Bots (SPEC: kein
        Echtgeld ohne explizites Opt-in), siehe ``core.live``."""
        info = self.account_info()
        if "trade_mode" not in info:
            return None
        return int(info["trade_mode"]) == self._const("ACCOUNT_TRADE_MODE_DEMO")

    def positions(self, symbol: str | None = None) -> list[dict]:
        mt5 = self._require_conn()
        pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return [self._as_dict(p) for p in (pos or [])]

    def history_deals_range(self, date_from: datetime, date_to: datetime) -> list[dict]:
        """Alle Deals im Zeitfenster (NICHT nach Magic gefiltert — Aufrufer
        filtert selbst, z.B. fuers Dashboard je Bot). Nur Lesezugriff."""
        mt5 = self._require_conn()
        if hasattr(mt5, "history_select"):
            mt5.history_select(date_from, date_to)
        deals = mt5.history_deals_get(date_from, date_to)
        return [self._as_dict(d) for d in (deals or [])]

    def history_deals_for_position(self, ticket: int, lookback_days: int = 30) -> list[dict]:
        """Deals genau einer (typischerweise gerade geschlossenen) Position —
        fuers Trade-Journal (Exit-Preis/Grund/P&L), nur Lesezugriff."""
        mt5 = self._require_conn()
        if hasattr(mt5, "history_select"):
            now = datetime.now(UTC)
            mt5.history_select(now - timedelta(days=lookback_days), now + timedelta(days=1))
        deals = mt5.history_deals_get(position=ticket)
        return [self._as_dict(d) for d in (deals or [])]

    def symbol_spec(self, symbol: str) -> dict:
        """point/tick_size/tick_value/volume_step/min/max/stops_level (SPEC §4.10)."""
        mt5 = self._require_conn()
        if hasattr(mt5, "symbol_select"):
            mt5.symbol_select(symbol, True)
        info = self._as_dict(mt5.symbol_info(symbol))
        if not info:
            raise RuntimeError(f"symbol_info({symbol}) leer — Symbol nicht verfuegbar?")
        return {
            "symbol": symbol,
            "point": float(info.get("point", 0.0)),
            "digits": int(info.get("digits", 0)),
            "tick_size": float(info.get("trade_tick_size", info.get("point", 0.0))),
            "tick_value": float(info.get("trade_tick_value", 0.0)),
            "volume_step": float(info.get("volume_step", 0.01)),
            "volume_min": float(info.get("volume_min", 0.01)),
            "volume_max": float(info.get("volume_max", 100.0)),
            "stops_level": int(info.get("trade_stops_level", 0)),
            "contract_size": float(info.get("trade_contract_size", 1.0)),
        }

    # -- Sizing / Validierung --------------------------------------------
    def normalize_volume(self, symbol: str, lots: float) -> float:
        """Rundet auf volume_step, clamped auf [volume_min, volume_max]."""
        spec = self.symbol_spec(symbol)
        step = spec["volume_step"] or 0.01
        steps = int(lots / step + 1e-12)
        lots = steps * step
        lots = max(spec["volume_min"], min(spec["volume_max"], lots))
        return round(lots, 8)

    def validate_sizing(self, symbol: str, direction: int, lots: float,
                        entry_price: float, sl_price: float) -> float:
        """Risiko-Validierung via order_calc_profit-Aequivalent (SPEC §4.10).

        Rueckgabe: Verlust in Kontowaehrung, wenn SL getroffen wird (> 0).
        """
        mt5 = self._require_conn()
        action = self._const("ORDER_TYPE_BUY") if direction > 0 else self._const("ORDER_TYPE_SELL")
        profit = mt5.order_calc_profit(action, symbol, lots, entry_price, sl_price)
        if profit is None:
            raise RuntimeError(f"order_calc_profit fehlgeschlagen: {mt5.last_error()}")
        return abs(float(profit))

    def _snap_stops(self, symbol: str, direction: int, price: float,
                    sl: float | None, tp: float | None) -> tuple[float | None, float | None]:
        """Retcode 10016: SL/TP auf Mindestabstand (stops_level) snappen."""
        spec = self.symbol_spec(symbol)
        min_dist = (spec["stops_level"] + 1) * spec["point"]
        if direction > 0:
            if sl is not None:
                sl = min(sl, price - min_dist)
            if tp is not None:
                tp = max(tp, price + min_dist)
        else:
            if sl is not None:
                sl = max(sl, price + min_dist)
            if tp is not None:
                tp = min(tp, price - min_dist)
        return sl, tp

    # -- Order-Versand mit Retry ------------------------------------------
    def _send_with_retry(self, request: dict) -> dict:
        """order_send mit Retcode-Handling 10015/10016/10030 (max. 3, exp. backoff)."""
        mt5 = self._require_conn()
        filling_modes = [
            self._const("ORDER_FILLING_IOC"),
            self._const("ORDER_FILLING_FOK"),
            self._const("ORDER_FILLING_RETURN"),
        ]
        filling_idx = filling_modes.index(request["type_filling"]) if request.get("type_filling") in filling_modes else 0
        last: dict = {}
        for attempt in range(self.max_retries):
            result = mt5.order_send(request)
            res = self._as_dict(result)
            retcode = int(res.get("retcode", -1))
            last = res
            if retcode == RETCODE_DONE:
                log.info("Order ausgefuehrt: ticket=%s %s %s %.2f @ %s",
                         res.get("order"), request.get("symbol"),
                         request.get("type"), request.get("volume"), res.get("price"))
                return res
            if retcode not in RETRY_RETCODES:
                log.error("Order abgelehnt (retcode=%s, nicht retryfaehig): %s",
                          retcode, res.get("comment"))
                return res
            # --- retryfaehige Retcodes ------------------------------------
            if retcode == RETCODE_UNSUPPORTED_FILLING:
                filling_idx = (filling_idx + 1) % len(filling_modes)
                request["type_filling"] = filling_modes[filling_idx]
                log.warning("Retcode 10030: Filling-Mode gewechselt auf %s",
                            filling_modes[filling_idx])
            elif retcode == RETCODE_INVALID_PRICE:
                tick = mt5.symbol_info_tick(request["symbol"])
                if tick is not None and request.get("action") == self._const("TRADE_ACTION_DEAL"):
                    request["price"] = float(tick.ask if request["type"] == self._const("ORDER_TYPE_BUY") else tick.bid)
                log.warning("Retcode 10015: Preis neu quotiert -> %s", request.get("price"))
            elif retcode == RETCODE_INVALID_STOPS:
                direction = 1 if request["type"] in (self._const("ORDER_TYPE_BUY"), self._const("ORDER_TYPE_BUY_LIMIT")) else -1
                ref = float(request.get("price") or 0.0)
                sl, tp = self._snap_stops(request["symbol"], direction, ref,
                                          request.get("sl"), request.get("tp"))
                request["sl"], request["tp"] = sl or 0.0, tp or 0.0
                log.warning("Retcode 10016: Stops gesnappt sl=%s tp=%s", sl, tp)
            if attempt < self.max_retries - 1:
                time.sleep(self.backoff_base * (2 ** attempt))
        log.error("Order nach %d Versuchen aufgegeben, letzter retcode=%s",
                  self.max_retries, last.get("retcode"))
        return last

    def _market_request(self, symbol: str, direction: int, lots: float,
                        sl: float, tp: float | None, deviation: int) -> dict:
        mt5 = self._require_conn()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Kein Tick fuer {symbol}")
        order_type = self._const("ORDER_TYPE_BUY") if direction > 0 else self._const("ORDER_TYPE_SELL")
        price = float(tick.ask) if direction > 0 else float(tick.bid)
        return {
            "action": self._const("TRADE_ACTION_DEAL"),
            "symbol": symbol,
            "volume": float(lots),
            "type": order_type,
            "price": price,
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "deviation": int(deviation),
            "magic": self.magic,
            "comment": "bot",
            "type_time": self._const("ORDER_TIME_GTC"),
            "type_filling": self._const("ORDER_FILLING_IOC"),
        }

    def send_market(self, symbol: str, direction: int, lots: float,
                    sl: float, tp: float | None, deviation: int = 10) -> dict:
        """Market-Order. SL/TP IMMER serverseitig (Crash-Netz, SPEC: live.py)."""
        lots = self.normalize_volume(symbol, lots)
        if self.dry_run:
            log.info("[DRY-RUN] MARKET %s %+d %.2f lots sl=%s tp=%s dev=%s",
                     symbol, direction, lots, sl, tp, deviation)
            return {"dry_run": True, "retcode": RETCODE_DONE, "symbol": symbol,
                    "direction": direction, "volume": lots, "sl": sl, "tp": tp}
        request = self._market_request(symbol, direction, lots, sl, tp, deviation)
        return self._send_with_retry(request)

    def send_limit(self, symbol: str, direction: int, lots: float,
                   limit_price: float, sl: float, tp: float | None,
                   deviation: int = 10, expiration: datetime | None = None) -> dict:
        """Pending-Limit-Order mit serverseitigem SL/TP."""
        lots = self.normalize_volume(symbol, lots)
        if self.dry_run:
            log.info("[DRY-RUN] LIMIT %s %+d %.2f lots @ %s sl=%s tp=%s",
                     symbol, direction, lots, limit_price, sl, tp)
            return {"dry_run": True, "retcode": RETCODE_DONE, "symbol": symbol,
                    "direction": direction, "volume": lots, "price": limit_price,
                    "sl": sl, "tp": tp}
        order_type = (self._const("ORDER_TYPE_BUY_LIMIT") if direction > 0
                      else self._const("ORDER_TYPE_SELL_LIMIT"))
        request = {
            "action": self._const("TRADE_ACTION_PENDING"),
            "symbol": symbol,
            "volume": float(lots),
            "type": order_type,
            "price": float(limit_price),
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "deviation": int(deviation),
            "magic": self.magic,
            "comment": "bot",
            "type_time": self._const("ORDER_TIME_GTC"),
            "type_filling": self._const("ORDER_FILLING_IOC"),
        }
        if expiration is not None:
            request["expiration"] = expiration
        return self._send_with_retry(request)

    def modify_sltp(self, ticket: int, sl: float, tp: float | None) -> bool:
        if self.dry_run:
            log.info("[DRY-RUN] MODIFY ticket=%s sl=%s tp=%s", ticket, sl, tp)
            return True
        mt5 = self._require_conn()
        pos = None
        for p in mt5.positions_get(ticket=ticket) or []:
            pos = self._as_dict(p)
            break
        if pos is None:
            log.error("modify_sltp: Position ticket=%s nicht gefunden", ticket)
            return False
        request = {
            "action": self._const("TRADE_ACTION_SLTP"),
            "position": int(ticket),
            "symbol": pos["symbol"],
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "magic": self.magic,
        }
        res = self._send_with_retry(request)
        return int(res.get("retcode", -1)) == RETCODE_DONE

    def close(self, ticket: int, deviation: int = 10) -> bool:
        if self.dry_run:
            log.info("[DRY-RUN] CLOSE ticket=%s", ticket)
            return True
        mt5 = self._require_conn()
        pos = None
        for p in mt5.positions_get(ticket=ticket) or []:
            pos = self._as_dict(p)
            break
        if pos is None:
            log.error("close: Position ticket=%s nicht gefunden", ticket)
            return False
        direction = -1 if pos["type"] == self._const("ORDER_TYPE_BUY") else 1
        res = self.send_market(pos["symbol"], direction, float(pos["volume"]),
                               sl=0.0, tp=0.0, deviation=deviation)
        return int(res.get("retcode", -1)) == RETCODE_DONE

    # -- Health (Watchdog) -------------------------------------------------
    def health(self) -> bool:
        """True wenn Server erreichbar und Terminal verbunden (SPEC §4.10)."""
        try:
            mt5 = self._require_conn()
            info = mt5.terminal_info() if hasattr(mt5, "terminal_info") else None
            if info is None:
                # Fallback: account_info als Lebenszeichen
                return mt5.account_info() is not None
            d = self._as_dict(info)
            return bool(d.get("connected", True))
        except Exception as exc:  # noqa: BLE001 - Watchdog darf nie werfen
            log.warning("Health-Check fehlgeschlagen: %s", exc)
            return False
