#!/usr/bin/env python3
"""scripts/fetch_data.py — Historie laden (MT5, Dukascopy oder HistData.com).

Beispiele:
    python scripts/fetch_data.py --symbol XAUUSD --timeframe H4 \
        --start 2020-01-01 --end 2025-01-01 --source mt5 --out data/
    python scripts/fetch_data.py --symbol EURUSD --timeframe M15 \
        --start 2023-01-01 --end 2024-01-01 --source dukascopy --out data/
    python scripts/fetch_data.py --symbol XAUUSD --timeframe H1 \
        --start 2020-01-01 --end 2025-01-01 --source histdata --out data/

Dukascopy (kostenlose Fallback-Quelle, tick-genau, aber ~5-10 req/s/IP
rate-limitiert — siehe RateLimiter/DUKASCOPY_MAX_RPS):
    URL: https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{year}/{month-1:02d}/
         {day:02d}/{hour:02d}h_ticks.bi5   (Monat ist 0-basiert!)
    .bi5 = LZMA-komprimiert, Records à 20 Bytes big-endian ">IIIff":
        (ms_offset_in_hour, ask_int, bid_int, ask_vol, bid_vol)
    Preis-Skalierung: Forex/JPY-Paare ×1000, XAUUSD ×1000, Indizes ×1
    (PRICE_SCALE unten, je Dukascopy-Symbol).

HistData.com (schnellere Alternative — fertige M1-Bars, ~1 Request/Jahr statt
24/Tag, kein bekanntes hartes Rate-Limit): siehe Abschnitt weiter unten.
Kein echtes Tick-Volumen (immer 0) — NICHT fuer S2 VWAPPullback geeignet.

ACHTUNG Instrumenten-Fit: Dukascopy USATECHIDXUSD und HistData nsxusd sind
BEIDE nur Anbieter-Proxys fuer NAS100 (anderes Underlying-Niveau als der
Broker-Kontrakt). Nur fuer Entwicklungs-Backtests — finale Validierung immer
auf MT5-Brokerdaten (siehe README).

Ausgabe: CSV mit UTC-tz-aware-Index, Spalten exakt per SPEC §3
(open, high, low, close, tick_volume). Gap-Audit wird am Ende ausgegeben.
"""

from __future__ import annotations

import argparse
import io
import logging
import lzma
import struct
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.connector import (  # noqa: E402
    OHLCV_COLUMNS,
    TF_MINUTES,
    MT5Connector,
    audit_gaps,
    validate_ohlcv,
)

log = logging.getLogger("fetch_data")
UTC = timezone.utc

DUKASCOPY_BASE = "https://datafeed.dukascopy.com/datafeed"

# Broker-Symbol -> Dukascopy-Symbol
DUKASCOPY_SYMBOL_MAP = {
    "US100": "USATECHIDXUSD",
    "NAS100": "USATECHIDXUSD",
}

# Preis-Skalierung je Dukascopy-Symbol (Default Forex/Gold: 1000, Indizes: 1)
PRICE_SCALE = {
    "USATECHIDXUSD": 1.0,
}
DEFAULT_PRICE_SCALE = 1000.0

REQUEST_PAUSE_SECONDS = 0.2   # Rate-Limit-freundlich zwischen Stunden-Requests
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 2
RATE_LIMIT_BACKOFF = 5.0      # 429: Basis-Backoff (x Versuch)
DUKASCOPY_MAX_RPS = 4.0       # empirisch: Server blockt ab ~5-10 req/s/IP (429)


class RateLimiter:
    """Thread-sicherer globaler Min-Interval-Limiter (Token-Bucket mit N=1).

    ``--workers`` Threads teilen sich EINE Rate — ohne das haelt jeder Thread
    seine eigene ``--pause`` ein, aber die SUMME ueber alle Threads reisst
    Dukascopys IP-Limit trotzdem (das war die Ursache der 429-Flut: 4
    Worker x 0.2s Pause = ~20 req/s combined, weit ueber dem ~5-10 req/s
    Server-Limit)."""

    def __init__(self, max_per_second: float):
        self._min_interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + self._min_interval
            wait = start - now
        if wait > 0:
            time.sleep(wait)


class DownloadError(Exception):
    """Stunden-Datei nach allen Retries nicht ladbar (Netz/Rate-Limit)."""


class DayIncompleteError(Exception):
    """Tag hatte fehlgeschlagene Stunden und wurde NICHT gecacht."""

_RESAMPLE_RULE = {"M1": "1min", "M5": "5min", "M15": "15min",
                  "H1": "1h", "H4": "4h", "D1": "1D"}


# ---------------------------------------------------------------------------
# .bi5-Parser
# ---------------------------------------------------------------------------
def parse_bi5(blob: bytes, hour_start: pd.Timestamp, price_scale: float) -> pd.DataFrame:
    """Parst einen LZMA-komprimierten .bi5-Blob in einen Tick-DataFrame.

    Records à 20 Bytes, big-endian ">IIIff":
    (ms_offset_in_hour, ask_int, bid_int, ask_vol, bid_vol).
    Rueckgabe: DataFrame mit UTC-tz-aware-Index und Spalte ``mid``.
    """
    try:
        raw = lzma.decompress(blob)
    except lzma.LZMAError:
        raw = blob  # manche Stunden sind unkomprimiert leer/ungueltig
    record_size = struct.calcsize(">IIIff")
    n = len(raw) // record_size
    records = []
    for i in range(n):
        ms, ask_i, bid_i, _ask_vol, _bid_vol = struct.unpack_from(">IIIff", raw, i * record_size)
        records.append((hour_start + pd.Timedelta(milliseconds=int(ms)),
                        ask_i / price_scale, bid_i / price_scale))
    if not records:
        return pd.DataFrame(columns=["ask", "bid", "mid"],
                            index=pd.DatetimeIndex([], tz=UTC))
    df = pd.DataFrame(records, columns=["time", "ask", "bid"]).set_index("time")
    df.index = pd.DatetimeIndex(df.index, tz=UTC)
    df["mid"] = (df["ask"] + df["bid"]) / 2.0
    return df


# ---------------------------------------------------------------------------
# Download + Cache
# ---------------------------------------------------------------------------
def dukascopy_symbol(symbol: str) -> str:
    return DUKASCOPY_SYMBOL_MAP.get(symbol.upper(), symbol.upper())


# Ein Limiter fuer den gesamten Prozess: alle ThreadPoolExecutor-Worker
# (siehe fetch_dukascopy) teilen sich EIN Rate-Budget gegen die Dukascopy-IP-
# Sperre (~5-10 req/s), statt dass jeder Thread unabhaengig seine eigene
# --pause einhaelt und die Summe ueber alle Worker das Limit trotzdem reisst.
_DUKASCOPY_LIMITER = RateLimiter(DUKASCOPY_MAX_RPS)


def _download_hour(symbol_duka: str, dt_utc: datetime) -> bytes | None:
    """Laedt eine Stunden-Datei. None bei 404/leer (Wochenende/Feiertag).

    Bei 429 (Rate-Limit) laengeres Backoff; nach allen Retries wird
    ``DownloadError`` geworfen, damit der Tag nicht partiell gecacht wird.
    """
    import requests  # lazy

    # Monat ist 0-basiert!
    url = (f"{DUKASCOPY_BASE}/{symbol_duka}/{dt_utc.year:04d}/"
           f"{dt_utc.month - 1:02d}/{dt_utc.day:02d}/{dt_utc.hour:02d}h_ticks.bi5")
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            _DUKASCOPY_LIMITER.acquire()
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                wait = RATE_LIMIT_BACKOFF * (attempt + 1)
                log.warning("429 Rate-Limit %s – Backoff %.0fs", url, wait)
                if attempt >= REQUEST_RETRIES:
                    raise DownloadError(f"429 nach Retries: {url}")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.content if resp.content else None
        except DownloadError:
            raise
        except Exception as exc:  # noqa: BLE001
            if attempt >= REQUEST_RETRIES:
                log.warning("Download fehlgeschlagen %s: %s", url, exc)
                raise DownloadError(f"{url}: {exc}") from exc
            time.sleep(1.0 * (attempt + 1))
    raise DownloadError(f"Retries erschoepft: {url}")


def _day_cache_paths(cache_dir: Path, symbol: str, day) -> tuple[Path, Path]:
    csv_path = cache_dir / symbol / f"{day:%Y-%m-%d}.csv"
    empty_path = cache_dir / symbol / f"{day:%Y-%m-%d}.empty"
    return csv_path, empty_path


def fetch_ticks_day(symbol: str, day, cache_dir: str | Path,
                    pause: float = REQUEST_PAUSE_SECONDS,
                    downloader=_download_hour) -> pd.DataFrame:
    """Laedt alle Ticks eines UTC-Tages (24 Stunden-Requests), cache-faehig.

    Bereits geladene Tage werden aus ``cache_dir`` gelesen (Resume); Tage
    ohne Daten (Wochenende) werden als ``.empty``-Marker gecacht.
    """
    cache_dir = Path(cache_dir)
    symbol_duka = dukascopy_symbol(symbol)
    csv_path, empty_path = _day_cache_paths(cache_dir, symbol, day)
    if empty_path.exists():
        return pd.DataFrame(columns=["ask", "bid", "mid"], index=pd.DatetimeIndex([], tz=UTC))
    if csv_path.exists():
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df.index = pd.DatetimeIndex(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize(UTC)
        return df

    scale = PRICE_SCALE.get(symbol_duka, DEFAULT_PRICE_SCALE)
    day_start = pd.Timestamp(day, tz=UTC)
    frames = []
    failed_hours = 0
    for hour in range(24):
        dt = (day_start + pd.Timedelta(hours=hour)).to_pydatetime()
        try:
            blob = downloader(symbol_duka, dt)
        except DownloadError as exc:
            failed_hours += 1
            log.warning("Tag %s Stunde %02d fehlgeschlagen: %s", day, hour, exc)
            blob = None
        if blob:
            frame = parse_bi5(blob, day_start + pd.Timedelta(hours=hour), scale)
            if len(frame):
                frames.append(frame)
        if pause > 0:
            time.sleep(pause)

    if failed_hours:
        # Kein partielles Cachen: fehlende Stunden wuerden sonst als
        # vollstaendiger Tag im Cache landen (still falsche Bars).
        raise DayIncompleteError(
            f"{symbol} {day}: {failed_hours}/24 Stunden fehlgeschlagen")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not frames:
        empty_path.touch()  # leeren Tag cachen (Wochenende)
        return pd.DataFrame(columns=["ask", "bid", "mid"], index=pd.DatetimeIndex([], tz=UTC))
    df = pd.concat(frames).sort_index()
    df.to_csv(csv_path)
    return df


# ---------------------------------------------------------------------------
# Ticks -> Bars
# ---------------------------------------------------------------------------
def ticks_to_bars(ticks: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregiert Ticks (mid) zu Bars. OHLC aus Mid, tick_volume = Tick-Anzahl."""
    tf = timeframe.upper()
    if tf not in TF_MINUTES:
        raise ValueError(f"Unbekannter Timeframe: {timeframe}")
    if ticks.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([], tz=UTC))
    # Immer erst M1, dann resample (SPEC: M1 -> M5/M15/H1/H4/D1)
    m1 = ticks["mid"].resample("1min").ohlc()
    m1["tick_volume"] = ticks["mid"].resample("1min").count()
    m1 = m1.dropna(subset=["close"])
    if tf == "M1":
        bars = m1
    else:
        agg = {"open": "first", "high": "max", "low": "min",
               "close": "last", "tick_volume": "sum"}
        bars = m1.resample(_RESAMPLE_RULE[tf]).agg(agg).dropna(subset=["close"])
    bars = bars[OHLCV_COLUMNS].astype("float64")
    bars.index = pd.DatetimeIndex(bars.index, tz=UTC)
    return bars


def fetch_dukascopy(symbol: str, timeframe: str, start: datetime, end: datetime,
                    cache_dir: str | Path = "data/dukascopy_cache",
                    pause: float = REQUEST_PAUSE_SECONDS,
                    downloader=None, workers: int = 1) -> pd.DataFrame:
    """Laedt Dukascopy-Ticks fuer [start, end) und aggregiert zu Bars (UTC).

    ``workers`` > 1 parallelisiert die Tages-Downloads (Threads, IO-bound;
    Cache ist tagesgranular und damit worker-sicher)."""
    if downloader is None:
        downloader = _download_hour
    start_utc = pd.Timestamp(start)
    end_utc = pd.Timestamp(end)
    if start_utc.tzinfo is None:
        start_utc = start_utc.tz_localize(UTC)
    if end_utc.tzinfo is None:
        end_utc = end_utc.tz_localize(UTC)

    symbol_duka = dukascopy_symbol(symbol)
    if symbol_duka != symbol.upper():
        log.warning("Symbol-Mapping: %s -> Dukascopy %s (ACHTUNG: anderes "
                    "Underlying-Niveau als Broker-%s! Nur Entwicklungs-Backtests.)",
                    symbol, symbol_duka, symbol)

    days = pd.date_range(start_utc.normalize(), end_utc.normalize(), freq="D", tz=UTC)
    failed_days: list = []

    def _load(day):
        try:
            return fetch_ticks_day(symbol, day.date(), cache_dir, pause=pause,
                                   downloader=downloader)
        except DayIncompleteError as exc:
            log.warning("%s", exc)
            failed_days.append(day)
            return pd.DataFrame(columns=["ask", "bid", "mid"],
                                index=pd.DatetimeIndex([], tz=UTC))

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor

        log.info("Dukascopy %s: %d Tage, %d Worker", symbol_duka, len(days), workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            frames = [t for t in pool.map(_load, days) if len(t)]
    else:
        frames = []
        for i, day in enumerate(days):
            log.info("Dukascopy %s: Tag %s (%d/%d)", symbol_duka, day.date(), i + 1, len(days))
            ticks = _load(day)
            if len(ticks):
                frames.append(ticks)

    if failed_days:
        # Serieller Nachlauf mit laengerer Pause (Rate-Limit abkuehlen)
        log.info("Nachlauf: %d fehlgeschlagene Tage seriell nachladen", len(failed_days))
        retry_pause = max(pause, 1.0)
        still_failed = []
        for day in failed_days:
            try:
                ticks = fetch_ticks_day(symbol, day.date(), cache_dir,
                                        pause=retry_pause, downloader=downloader)
                if len(ticks):
                    frames.append(ticks)
            except DayIncompleteError as exc:
                log.error("Tag weiterhin unvollstaendig: %s", exc)
                still_failed.append(day.date())
        if still_failed:
            log.error("%d Tage endgueltig unvollstaendig (erneut ausfuehren): %s",
                      len(still_failed), still_failed)

    if not frames:
        log.warning("Keine Ticks fuer %s im Zeitraum", symbol)
        return pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([], tz=UTC))
    all_ticks = pd.concat(frames).sort_index()
    bars = ticks_to_bars(all_ticks, timeframe)
    bars = bars.loc[(bars.index >= start_utc) & (bars.index < end_utc)]
    return validate_ohlcv(bars, timeframe)


# ---------------------------------------------------------------------------
# HistData.com (schnellere Alternative zu Dukascopy fuer Entwicklungs-Backtests)
#
# HistData liefert bereits fertige M1-Bars als EIN Zip je Jahr (Vergangenheit)
# bzw. je Monat (laufendes Jahr) — statt Dukascopys 24 Tick-Requests/Tag ist
# das ~1 Request je Symbol-Jahr. Kein bekanntes hartes Rate-Limit wie bei
# Dukascopy (~5-10 req/s/IP), aber trotzdem ``pause`` zwischen Requests
# (guter Stil, kein eigener globaler Limiter noetig bei dieser Request-Zahl).
#
# ACHTUNG Tick-Volumen: die "Volume"-Spalte ist bei HistData-M1-Daten immer 0
# (keine echten Tick-Zaehlungen) — fuer S2 VWAPPullback (tick_volume-
# gewichtetes VWAP, SPEC §5 S2) ist diese Quelle NICHT geeignet; dort weiter
# Dukascopy oder MT5 verwenden. Fuer S1/S4/S5 (kein Volumen-Filter) unkritisch.
#
# ACHTUNG Instrumenten-Fit NAS100: HistData fuehrt keinen "NAS100"/"US100",
# sondern einen eigenen Nasdaq-100-Proxy unter dem Pair-Code "nsxusd"
# (empirisch verifiziert: Kursniveau 2023 ~11.000, deckungsgleich mit NDX) —
# genau wie Dukascopys "USATECHIDXUSD" ein ANDERER Anbieter-Proxy als der
# Broker-Kontrakt, nur fuer Entwicklungs-Backtests (README/SPEC unveraendert:
# finale Validierung immer auf MT5-Brokerdaten).
# ---------------------------------------------------------------------------
HISTDATA_SYMBOL_MAP = {
    "NAS100": "nsxusd",
    "US100": "nsxusd",
}

_HISTDATA_RESAMPLE_AGG = {"open": "first", "high": "max", "low": "min",
                          "close": "last", "tick_volume": "sum"}


def histdata_symbol(symbol: str) -> str:
    return HISTDATA_SYMBOL_MAP.get(symbol.upper(), symbol.lower())


def _histdata_periods(start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> list[tuple[int, int | None]]:
    """(Jahr, Monat|None) je Download: volle Vergangenheitsjahre (Monat=None,
    1 Request/Jahr laut HistData-API), laufendes Jahr monatsweise (Pflicht
    der zugrundeliegenden histdata-Bibliothek)."""
    current_year = datetime.now(UTC).year
    periods: list[tuple[int, int | None]] = []
    for year in range(start_utc.year, end_utc.year + 1):
        if year < current_year:
            periods.append((year, None))
        else:
            m_start = start_utc.month if year == start_utc.year else 1
            m_end = end_utc.month if year == end_utc.year else 12
            for month in range(m_start, m_end + 1):
                periods.append((year, month))
    return periods


def _histdata_cache_path(cache_dir: str | Path, symbol_hd: str, year: int, month: int | None) -> Path:
    stem = f"{year}" if month is None else f"{year}{month:02d}"
    return Path(cache_dir) / symbol_hd / f"{stem}.csv"


def _parse_histdata_csv(raw: str) -> pd.DataFrame:
    """Parst HistData-ASCII-M1 (';'-getrennt: Zeit;O;H;L;C;Volumen).

    Zeitstempel-Format ``YYYYMMDD HHMMSS`` in EST OHNE Sommerzeit-Umstellung
    (laut HistData-Doku ganzjaehrig fixer UTC-5-Offset) — bewusst KEIN
    zoneinfo/DST wie core/time_engine.py fuer Handelssessions: das waere
    hier falsch, weil HistData den DST-Wechsel selbst nicht nachvollzieht.
    Daher einfach +5h -> UTC.
    """
    if not raw.strip():
        return pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([], tz=UTC))
    df = pd.read_csv(io.StringIO(raw), sep=";", header=None,
                     names=["time", "open", "high", "low", "close", "tick_volume"])
    ts = pd.to_datetime(df["time"], format="%Y%m%d %H%M%S") + pd.Timedelta(hours=5)
    out = df[OHLCV_COLUMNS].astype("float64").copy()
    out.index = pd.DatetimeIndex(ts).tz_localize(UTC)
    return out.sort_index()


def _download_histdata_period(symbol_hd: str, year: int, month: int | None) -> pd.DataFrame:
    """Laedt + entpackt ein Jahres-/Monats-Zip von HistData.com."""
    import tempfile
    import zipfile

    from histdata import download_hist_data  # lazy (optionale Dependency)
    from histdata.api import Platform, TimeFrame

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = download_hist_data(
            year=str(year), month=(str(month) if month is not None else None),
            pair=symbol_hd, platform=Platform.GENERIC_ASCII,
            time_frame=TimeFrame.ONE_MINUTE, output_directory=tmp, verbose=False)
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            raw = zf.read(csv_name).decode("ascii", errors="ignore")
    return _parse_histdata_csv(raw)


def _resample_bars(m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregiert bereits fertige M1-Bars (nicht Ticks) auf den Ziel-TF."""
    tf = timeframe.upper()
    if tf not in TF_MINUTES:
        raise ValueError(f"Unbekannter Timeframe: {timeframe}")
    if tf == "M1" or m1.empty:
        return m1
    bars = m1.resample(_RESAMPLE_RULE[tf]).agg(_HISTDATA_RESAMPLE_AGG).dropna(subset=["close"])
    return bars


def fetch_histdata(symbol: str, timeframe: str, start: datetime, end: datetime,
                   cache_dir: str | Path = "data/histdata_cache",
                   pause: float = 1.0, downloader=None) -> pd.DataFrame:
    """Laedt HistData.com-M1-Bars fuer [start, end) und aggregiert (UTC).

    ``downloader(symbol_hd, year, month) -> DataFrame`` injizierbar fuer
    Tests (kein Live-Download noetig)."""
    if downloader is None:
        downloader = _download_histdata_period
    start_utc = pd.Timestamp(start)
    end_utc = pd.Timestamp(end)
    if start_utc.tzinfo is None:
        start_utc = start_utc.tz_localize(UTC)
    if end_utc.tzinfo is None:
        end_utc = end_utc.tz_localize(UTC)

    symbol_hd = histdata_symbol(symbol)
    if symbol_hd != symbol.lower():
        log.warning("Symbol-Mapping: %s -> HistData %s (ACHTUNG: eigener "
                    "Anbieter-Proxy, anderes Underlying als Broker-%s! Nur "
                    "Entwicklungs-Backtests.)", symbol, symbol_hd, symbol)

    cache_dir = Path(cache_dir)
    frames = []
    failed_periods: list[str] = []
    for year, month in _histdata_periods(start_utc, end_utc):
        label = f"{year}" if month is None else f"{year}-{month:02d}"
        cpath = _histdata_cache_path(cache_dir, symbol_hd, year, month)
        if cpath.exists():
            df = pd.read_csv(cpath, index_col=0, parse_dates=True)
            df.index = pd.DatetimeIndex(df.index)
            if df.index.tz is None:
                df.index = df.index.tz_localize(UTC)
        else:
            log.info("HistData %s: lade %s", symbol_hd, label)
            try:
                df = downloader(symbol_hd, year, month)
            except Exception as exc:  # noqa: BLE001
                # Wie Dukascopys DayIncompleteError: EIN fehlgeschlagener
                # Zeitraum (z.B. laufender Monat noch ohne Daten bei
                # HistData) bricht NICHT den gesamten Mehrjahres-Fetch ab.
                # Nichts wird gecacht — naechster Lauf versucht es erneut.
                log.warning("HistData %s %s fehlgeschlagen: %s", symbol_hd, label, exc)
                failed_periods.append(label)
                continue
            cpath.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cpath)
            if pause > 0:
                time.sleep(pause)
        if len(df):
            frames.append(df)

    if failed_periods:
        log.warning("HistData %s: %d Zeitraum(e) uebersprungen (erneut "
                    "ausfuehren zum Nachladen): %s", symbol_hd,
                    len(failed_periods), failed_periods)

    if not frames:
        log.warning("Keine Daten fuer %s im Zeitraum (HistData)", symbol)
        return pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([], tz=UTC))
    m1 = pd.concat(frames).sort_index()
    m1 = m1[~m1.index.duplicated(keep="first")]
    bars = _resample_bars(m1, timeframe)
    bars = bars.loc[(bars.index >= start_utc) & (bars.index < end_utc)]
    return validate_ohlcv(bars, timeframe)


# ---------------------------------------------------------------------------
# Speichern + CLI
# ---------------------------------------------------------------------------
def save_csv(df: pd.DataFrame, out_dir: str | Path, symbol: str, timeframe: str) -> Path:
    """Speichert als ``out_dir/{SYMBOL}_{TF}.parquet`` (UTC-Index, SPEC §3).

    Parquet statt CSV: ~80 % kleiner, deutlich schneller beim Laden.
    Der Loader (core.connector.load_ohlcv) liest CSV als Fallback weiter.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{symbol}_{timeframe.upper()}.parquet"
    df = validate_ohlcv(df, timeframe)
    df.index.name = "time"
    df.to_parquet(path, index=True)
    log.info("Gespeichert: %s (%d Bars)", path, len(df))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Historie laden (MT5 oder Dukascopy)")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True, choices=sorted(TF_MINUTES))
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD (exklusiv)")
    parser.add_argument("--out", default="data", help="Ausgabeverzeichnis (default: data/)")
    parser.add_argument("--source", choices=["mt5", "dukascopy", "histdata"], default="mt5")
    parser.add_argument("--host", default="localhost", help="RPyC-Host (nur --source mt5)")
    parser.add_argument("--port", type=int, default=18812, help="RPyC-Port (nur --source mt5)")
    parser.add_argument("--cache-dir", default=None,
                        help="Tick-/Bar-Cache (default: data/dukascopy_cache bzw. "
                             "data/histdata_cache je nach --source)")
    parser.add_argument("--pause", type=float, default=None,
                        help="Pause zwischen Requests in s (default: "
                             f"Dukascopy {REQUEST_PAUSE_SECONDS}, HistData 1.0)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallele Tages-Downloads (nur --source dukascopy, IO-bound)")
    parser.add_argument("--rate-limit", type=float, default=DUKASCOPY_MAX_RPS,
                        help="Globales Requests/s-Limit ueber ALLE --workers hinweg "
                             f"(nur --source dukascopy; default {DUKASCOPY_MAX_RPS} req/s, "
                             "Server blockt ab ~5-10 req/s/IP mit 429)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)

    start = pd.Timestamp(args.start, tz=UTC)
    end = pd.Timestamp(args.end, tz=UTC)

    if args.source == "mt5":
        connector = MT5Connector(host=args.host, port=args.port)
        try:
            connector.connect()
            df = connector.fetch_ohlcv(args.symbol, args.timeframe, start, end)
        finally:
            connector.disconnect()
    elif args.source == "histdata":
        df = fetch_histdata(args.symbol, args.timeframe, start, end,
                            cache_dir=args.cache_dir or "data/histdata_cache",
                            pause=args.pause if args.pause is not None else 1.0)
    else:
        global _DUKASCOPY_LIMITER
        _DUKASCOPY_LIMITER = RateLimiter(args.rate_limit)
        df = fetch_dukascopy(args.symbol, args.timeframe, start, end,
                             cache_dir=args.cache_dir or "data/dukascopy_cache",
                             pause=args.pause if args.pause is not None else REQUEST_PAUSE_SECONDS,
                             workers=args.workers)

    if df.empty:
        log.error("Keine Daten — nichts gespeichert")
        return 1
    path = save_csv(df, args.out, args.symbol, args.timeframe)

    # Gap-Audit (SPEC §3)
    report = audit_gaps(df, args.timeframe)
    print(report.summary())
    if not report.ok:
        log.warning("Daten enthalten Luecken — Qualitaet pruefen!")
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
