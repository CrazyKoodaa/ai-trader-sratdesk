"""core/news_filter.py — ForexFactory-Kalender-Feed + Blackout-Logik (SPEC §4.7).

- update(): laedt https://nfs.faireconomy.media/ff_calendar_thisweek.xml
  (FF liefert Zeiten in America/New_York — werden nach UTC normalisiert).
  Rate-Limit-freundlich: max. 1 Fetch pro Start bzw. wenn Cache aelter als
  ``max_age_hours`` (default 24 h).
- Cache: CSV in ``cache_dir`` (ff_calendar_cache.csv).
- Backtest-Modus: liest historischen CSV-Cache mit identischer API,
  fuehrt niemals einen Live-Fetch aus.
- Fail-closed (Live): kein Feed/Cache -> is_blackout() == True.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

log = logging.getLogger(__name__)

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
FF_TZ = ZoneInfo("America/New_York")  # FF liefert ET (DST-aware)
UTC = timezone.utc

CACHE_FILE = "ff_calendar_cache.csv"

# SPEC §4.7: Symbol -> betroffene Waehrungen
SYMBOL_CCY: dict[str, frozenset[str]] = {
    "XAUUSD": frozenset({"USD"}),
    "NAS100": frozenset({"USD"}),
    "US100": frozenset({"USD"}),
    "EURUSD": frozenset({"EUR", "USD"}),
    "GBPUSD": frozenset({"GBP", "USD"}),
    "USDJPY": frozenset({"USD", "JPY"}),
    "USDCHF": frozenset({"USD", "CHF"}),
    "AUDUSD": frozenset({"AUD", "USD"}),
    "USDCAD": frozenset({"USD", "CAD"}),
    "NZDUSD": frozenset({"NZD", "USD"}),
    "EURJPY": frozenset({"EUR", "JPY"}),
    "GBPJPY": frozenset({"GBP", "JPY"}),
    "BTC": frozenset({"USD"}),
    "ETH": frozenset({"USD"}),
    "BTCUSD": frozenset({"USD"}),
    "ETHUSD": frozenset({"USD"}),
}

TIER1_KEYWORDS = ("FOMC", "Non-Farm", "CPI")

DEFAULT_BLACKOUT_BEFORE_MIN = 15
DEFAULT_BLACKOUT_AFTER_MIN = 10
DEFAULT_IMPACTS = ("High",)


@dataclass(frozen=True)
class NewsEvent:
    time_utc: pd.Timestamp | None  # None = untimed (All Day / Tentative)
    currency: str
    impact: str
    title: str


def currencies_for_symbol(symbol: str) -> frozenset[str]:
    """Symbol -> Ccy-Mapping exakt per SPEC §4.7; Fallback: AAAQBB -> {AAA, QBB}."""
    key = str(symbol).upper().split(".")[0]
    if key in SYMBOL_CCY:
        return SYMBOL_CCY[key]
    if len(key) == 6 and key.isalpha():
        return frozenset({key[:3], key[3:]})
    log.warning("NewsFilter: kein Ccy-Mapping fuer Symbol %r", symbol)
    return frozenset()


def _parse_ff_time(date_str: str, time_str: str) -> pd.Timestamp | None:
    """FF-Datum (mm-dd-yyyy) + ET-Zeit ('8:30am') -> tz-aware UTC Timestamp.

    'All Day' / 'Tentative' / leer -> None.
    """
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip()
    if not date_str or not time_str:
        return None
    low = time_str.lower()
    if "day" in low or "tentative" in low:
        return None
    try:
        d = datetime.strptime(date_str, "%m-%d-%Y")
        t = datetime.strptime(time_str.upper().replace(" ", ""), "%I:%M%p")
    except ValueError:
        log.warning("NewsFilter: unparsebare FF-Zeit %r %r", date_str, time_str)
        return None
    et = datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=FF_TZ)
    return pd.Timestamp(et.astimezone(UTC))


def parse_ff_xml(xml_bytes: bytes | str) -> list[NewsEvent]:
    """Robustes Parsing des FF-Weekly-XML; fehlerhafte Events werden uebersprungen."""
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    root = ET.fromstring(xml_bytes)
    events: list[NewsEvent] = []
    for ev in root.iter("event"):
        def txt(tag: str) -> str:
            el = ev.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""

        title, ccy, impact = txt("title"), txt("country").upper(), txt("impact")
        if not title or not ccy:
            continue
        ts = _parse_ff_time(txt("date"), txt("time"))
        events.append(NewsEvent(time_utc=ts, currency=ccy, impact=impact, title=title))
    return events


def _default_fetcher(url: str, timeout: float = 15.0) -> bytes:
    import requests

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


class NewsFilter:
    """SPEC §4.7.

    Args:
        cache_dir: Verzeichnis fuer den CSV-Cache.
        prop_profile: dict, kann Fenster ueberschreiben:
            news_blackout_min_before / news_blackout_min_after / news_impacts.
        backtest: True -> liest ausschliesslich CSV-Cache, kein Live-Fetch.
        fail_closed: None -> True im Live-, False im Backtest-Modus.
        url/fetcher: injizierbar fuer Tests (kein Live-Download noetig).
        cache_file: optionaler alternativer Cache-Dateiname (Backtest-History).
    """

    def __init__(
        self,
        cache_dir: str,
        prop_profile: dict | None = None,
        *,
        backtest: bool = False,
        fail_closed: bool | None = None,
        url: str = FF_URL,
        fetcher: Callable[[str], bytes] | None = None,
        cache_file: str | None = None,
        max_age_hours: float = 24.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / (cache_file or CACHE_FILE)
        self.prop_profile = prop_profile or {}
        self.backtest = backtest
        self.fail_closed = (not backtest) if fail_closed is None else fail_closed
        self.url = url
        self._fetcher = fetcher or _default_fetcher
        self.max_age_hours = float(max_age_hours)

        self._events: list[NewsEvent] = []
        self._fetched_at: pd.Timestamp | None = None
        self._fetch_attempted = False  # Rate-Limit: max 1 Fetch pro Start

    # ------------------------------------------------------------------ API
    def update(self) -> None:
        """Laedt Events: Backtest aus Cache, Live aus frischem Cache oder 1× Feed."""
        if self.backtest:
            self._load_cache()
            return
        if self._cache_fresh():
            self._load_cache()
            return
        if self._fetch_attempted and self._fetched_at is not None:
            age = pd.Timestamp.now(UTC) - self._fetched_at
            if age < timedelta(hours=self.max_age_hours):
                return  # Rate-Limit: taeglich reicht
        self._fetch_attempted = True
        try:
            xml_bytes = self._fetcher(self.url)
            events = parse_ff_xml(xml_bytes)
        except Exception as exc:  # Feed-Ausfall: Cache behalten, fail-closed greift
            log.error("NewsFilter: Feed-Fetch fehlgeschlagen: %s", exc)
            self._load_cache()
            return
        self._events = events
        self._fetched_at = pd.Timestamp.now(UTC)
        self._write_cache()

    def is_blackout(self, ts_utc: datetime, symbol: str) -> bool:
        """True, wenn ts innerhalb des Blackout-Fensters eines High-Impact-Events
        liegt, dessen Waehrung das Symbol betrifft. Fail-closed ohne Feed."""
        if not self._events:
            return self.fail_closed
        ccys = currencies_for_symbol(symbol)
        if not ccys:
            return self.fail_closed
        before, after = self._window()
        ts = _as_utc(ts_utc)
        for ev in self._events:
            if ev.time_utc is None or ev.currency not in ccys:
                continue
            if ev.impact not in self._impacts():
                continue
            if ev.time_utc - before <= ts <= ev.time_utc + after:
                return True
        return False

    def tier1_halt(self, ts_utc: datetime) -> bool:
        """True rund um FOMC / Non-Farm / CPI — global, alle Waehrungen."""
        if not self._events:
            return self.fail_closed
        before, after = self._window()
        ts = _as_utc(ts_utc)
        for ev in self._events:
            if ev.time_utc is None:
                continue
            if not any(kw in ev.title for kw in TIER1_KEYWORDS):
                continue
            if ev.time_utc - before <= ts <= ev.time_utc + after:
                return True
        return False

    @property
    def events(self) -> list[NewsEvent]:
        return list(self._events)

    # ------------------------------------------------------------- intern
    def _window(self) -> tuple[pd.Timedelta, pd.Timedelta]:
        before = self.prop_profile.get("news_blackout_min_before", DEFAULT_BLACKOUT_BEFORE_MIN)
        after = self.prop_profile.get("news_blackout_min_after", DEFAULT_BLACKOUT_AFTER_MIN)
        return pd.Timedelta(minutes=float(before)), pd.Timedelta(minutes=float(after))

    def _impacts(self) -> tuple[str, ...]:
        impacts: Iterable[str] = self.prop_profile.get("news_impacts", DEFAULT_IMPACTS)
        return tuple(impacts)

    def _cache_fresh(self) -> bool:
        if not self.cache_path.exists():
            return False
        try:
            df = pd.read_csv(self.cache_path, usecols=["fetched_at"])
            fetched_at = pd.to_datetime(df["fetched_at"].iloc[0], utc=True)
        except Exception:
            return False
        return (pd.Timestamp.now(UTC) - fetched_at) < timedelta(hours=self.max_age_hours)

    def _load_cache(self) -> None:
        self._events = []
        self._fetched_at = None
        if not self.cache_path.exists():
            log.warning("NewsFilter: kein Cache unter %s", self.cache_path)
            return
        try:
            df = pd.read_csv(self.cache_path)
        except Exception as exc:
            log.error("NewsFilter: Cache unlesbar: %s", exc)
            return
        times = pd.to_datetime(df["time_utc"], utc=True, errors="coerce")
        events = []
        for t, (_, row) in zip(times, df.iterrows()):
            events.append(
                NewsEvent(
                    time_utc=None if pd.isna(t) else t,
                    currency=str(row["currency"]).upper(),
                    impact=str(row["impact"]),
                    title=str(row["title"]),
                )
            )
        self._events = events
        if "fetched_at" in df.columns and len(df):
            fa = pd.to_datetime(df["fetched_at"].iloc[0], utc=True, errors="coerce")
            self._fetched_at = None if pd.isna(fa) else fa

    def _write_cache(self) -> None:
        rows = [
            {
                "time_utc": ev.time_utc.isoformat() if ev.time_utc is not None else "",
                "currency": ev.currency,
                "impact": ev.impact,
                "title": ev.title,
                "fetched_at": self._fetched_at.isoformat(),
            }
            for ev in self._events
        ]
        pd.DataFrame(rows, columns=["time_utc", "currency", "impact", "title", "fetched_at"]).to_csv(
            self.cache_path, index=False
        )


def _as_utc(ts: datetime) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize(UTC) if t.tzinfo is None else t.tz_convert(UTC)
