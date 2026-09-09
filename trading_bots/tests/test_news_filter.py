"""Tests core/news_filter.py — lokale Fixture-XML, KEIN Live-Download."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone

import pandas as pd
import pytest

from core.news_filter import (
    NewsFilter,
    currencies_for_symbol,
    parse_ff_xml,
)

UTC = timezone.utc

# US-DST 2025: beginnt 09.03. (EST -> EDT), endet 02.11.
FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<weeklyevents>
  <event>
    <title><![CDATA[Non-Farm Employment Change]]></title>
    <country><![CDATA[USD]]></country>
    <date><![CDATA[03-07-2025]]></date>
    <time><![CDATA[8:30am]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[160K]]></forecast>
    <previous><![CDATA[143K]]></previous>
  </event>
  <event>
    <title><![CDATA[CPI m/m]]></title>
    <country><![CDATA[USD]]></country>
    <date><![CDATA[03-12-2025]]></date>
    <time><![CDATA[8:30am]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[0.3%]]></forecast>
    <previous><![CDATA[0.5%]]></previous>
  </event>
  <event>
    <title><![CDATA[FOMC Statement]]></title>
    <country><![CDATA[USD]]></country>
    <date><![CDATA[01-29-2025]]></date>
    <time><![CDATA[2:00pm]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[]]></forecast>
    <previous><![CDATA[]]></previous>
  </event>
  <event>
    <title><![CDATA[CPI Flash Estimate y/y]]></title>
    <country><![CDATA[EUR]]></country>
    <date><![CDATA[07-01-2025]]></date>
    <time><![CDATA[5:00am]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[2.0%]]></forecast>
    <previous><![CDATA[1.9%]]></previous>
  </event>
  <event>
    <title><![CDATA[CPI y/y]]></title>
    <country><![CDATA[JPY]]></country>
    <date><![CDATA[03-21-2025]]></date>
    <time><![CDATA[7:30pm]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[]]></forecast>
    <previous><![CDATA[4.0%]]></previous>
  </event>
  <event>
    <title><![CDATA[Retail Sales m/m]]></title>
    <country><![CDATA[USD]]></country>
    <date><![CDATA[07-15-2025]]></date>
    <time><![CDATA[8:30am]]></time>
    <impact><![CDATA[Medium]]></impact>
    <forecast><![CDATA[0.1%]]></forecast>
    <previous><![CDATA[-0.9%]]></previous>
  </event>
  <event>
    <title><![CDATA[ECB Press Conference]]></title>
    <country><![CDATA[EUR]]></country>
    <date><![CDATA[03-06-2025]]></date>
    <time><![CDATA[8:45am]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[]]></forecast>
    <previous><![CDATA[]]></previous>
  </event>
  <event>
    <title><![CDATA[BOJ Policy Rate]]></title>
    <country><![CDATA[JPY]]></country>
    <date><![CDATA[01-24-2025]]></date>
    <time><![CDATA[Tentative]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[]]></forecast>
    <previous><![CDATA[0.25%]]></previous>
  </event>
  <event>
    <title><![CDATA[Bank Holiday]]></title>
    <country><![CDATA[USD]]></country>
    <date><![CDATA[01-20-2025]]></date>
    <time><![CDATA[All Day]]></time>
    <impact><![CDATA[Low]]></impact>
    <forecast><![CDATA[]]></forecast>
    <previous><![CDATA[]]></previous>
  </event>
</weeklyevents>
"""


class CountingFetcher:
    def __init__(self, payload: bytes = FIXTURE_XML.encode(), fail: bool = False):
        self.payload = payload
        self.fail = fail
        self.calls = 0

    def __call__(self, url: str) -> bytes:
        self.calls += 1
        if self.fail:
            raise ConnectionError("offline")
        return self.payload


def make_filter(tmp_path, fetcher=None, **kw) -> NewsFilter:
    nf = NewsFilter(str(tmp_path), {}, fetcher=fetcher or CountingFetcher(), **kw)
    nf.update()
    return nf


# ------------------------------------------------------------------ Parsing/TZ
def test_parse_all_events_incl_untimed():
    events = parse_ff_xml(FIXTURE_XML)
    assert len(events) == 9
    timed = [e for e in events if e.time_utc is not None]
    assert len(timed) == 7  # Tentative + All Day ohne Zeit
    assert all(e.time_utc.tzinfo is not None for e in timed)


def test_ff_et_to_utc_est_winter():
    events = {e.title: e for e in parse_ff_xml(FIXTURE_XML)}
    # 29.01.2025 14:00 EST (UTC-5) -> 19:00 UTC
    assert events["FOMC Statement"].time_utc == pd.Timestamp("2025-01-29 19:00", tz="UTC")


def test_ff_et_to_utc_dst_transition_week():
    events = {e.title: e for e in parse_ff_xml(FIXTURE_XML)}
    # 07.03.2025 08:30 EST (UTC-5, vor DST-Start 09.03.) -> 13:30 UTC
    assert events["Non-Farm Employment Change"].time_utc == pd.Timestamp(
        "2025-03-07 13:30", tz="UTC")
    # 12.03.2025 08:30 EDT (UTC-4, nach DST-Start) -> 12:30 UTC
    assert events["CPI m/m"].time_utc == pd.Timestamp("2025-03-12 12:30", tz="UTC")


def test_ff_et_to_utc_edt_summer():
    events = {e.title: e for e in parse_ff_xml(FIXTURE_XML)}
    # 01.07.2025 05:00 EDT (UTC-4) -> 09:00 UTC
    assert events["CPI Flash Estimate y/y"].time_utc == pd.Timestamp(
        "2025-07-01 09:00", tz="UTC")


def test_symbol_ccy_mapping():
    assert currencies_for_symbol("XAUUSD") == {"USD"}
    assert currencies_for_symbol("EURUSD") == {"EUR", "USD"}
    assert currencies_for_symbol("USDJPY") == {"USD", "JPY"}
    assert currencies_for_symbol("NAS100") == {"USD"}
    assert currencies_for_symbol("BTC") == {"USD"}
    assert currencies_for_symbol("GBPJPY") == {"GBP", "JPY"}


# ------------------------------------------------------------------ Blackout
def test_blackout_window_default_minus15_plus10(tmp_path):
    nf = make_filter(tmp_path)
    nfp = pd.Timestamp("2025-03-07 13:30", tz="UTC")  # USD High
    assert nf.is_blackout(nfp - pd.Timedelta(minutes=15), "EURUSD")   # Grenze inklusiv
    assert not nf.is_blackout(nfp - pd.Timedelta(minutes=15, seconds=1), "EURUSD")
    assert nf.is_blackout(nfp + pd.Timedelta(minutes=10), "EURUSD")
    assert not nf.is_blackout(nfp + pd.Timedelta(minutes=10, seconds=1), "EURUSD")
    assert nf.is_blackout(nfp, "EURUSD")


def test_blackout_symbol_ccy_mapping(tmp_path):
    nf = make_filter(tmp_path)
    nfp = pd.Timestamp("2025-03-07 13:30", tz="UTC")        # USD
    ecb = pd.Timestamp("2025-03-06 13:45", tz="UTC")        # EUR
    assert nf.is_blackout(nfp, "XAUUSD")                    # XAU -> USD
    assert nf.is_blackout(nfp, "USDJPY")                    # USD-Seite
    assert nf.is_blackout(ecb, "EURUSD")                    # EUR-Seite
    assert not nf.is_blackout(ecb, "GBPUSD")                # EUR betrifft GBP nicht
    assert not nf.is_blackout(ecb, "XAUUSD")                # EUR betrifft Gold nicht


def test_blackout_medium_impact_ignored(tmp_path):
    nf = make_filter(tmp_path)
    retail = pd.Timestamp("2025-07-15 12:30", tz="UTC")  # USD Medium
    assert not nf.is_blackout(retail, "EURUSD")


def test_blackout_untimed_events_ignored(tmp_path):
    nf = make_filter(tmp_path)
    # BOJ Policy Rate = Tentative -> den ganzen Tag kein Blackout
    for hh in (0, 8, 16, 23):
        assert not nf.is_blackout(
            datetime(2025, 1, 24, hh, tzinfo=UTC), "USDJPY")


def test_blackout_prop_profile_overrides_window(tmp_path):
    nf = NewsFilter(str(tmp_path / "pp"),
                    {"news_blackout_min_before": 60, "news_blackout_min_after": 30},
                    fetcher=CountingFetcher())
    nf.update()
    nfp = pd.Timestamp("2025-03-07 13:30", tz="UTC")
    assert nf.is_blackout(nfp - pd.Timedelta(minutes=59), "EURUSD")
    assert not nf.is_blackout(nfp - pd.Timedelta(minutes=61), "EURUSD")
    assert nf.is_blackout(nfp + pd.Timedelta(minutes=29), "EURUSD")
    assert not nf.is_blackout(nfp + pd.Timedelta(minutes=31), "EURUSD")


def test_blackout_accepts_naive_ts_as_utc(tmp_path):
    nf = make_filter(tmp_path)
    assert nf.is_blackout(datetime(2025, 3, 7, 13, 30), "EURUSD")


# ------------------------------------------------------------------ Tier1
def test_tier1_halt_keywords_global(tmp_path):
    nf = make_filter(tmp_path)
    assert nf.tier1_halt(pd.Timestamp("2025-01-29 19:00", tz="UTC"))   # FOMC
    assert nf.tier1_halt(pd.Timestamp("2025-03-07 13:30", tz="UTC"))   # Non-Farm
    assert nf.tier1_halt(pd.Timestamp("2025-03-12 12:30", tz="UTC"))   # CPI (USD)
    # JPY-CPI ist Tier1 -> global, haelt auch ohne JPY-Bezug
    assert nf.tier1_halt(pd.Timestamp("2025-03-21 23:30", tz="UTC"))


def test_tier1_halt_non_tier1_events_false(tmp_path):
    nf = make_filter(tmp_path)
    assert not nf.tier1_halt(pd.Timestamp("2025-03-06 13:45", tz="UTC"))  # ECB Press
    assert not nf.tier1_halt(pd.Timestamp("2025-07-15 12:30", tz="UTC"))  # Retail
    assert not nf.tier1_halt(pd.Timestamp("2025-01-29 22:00", tz="UTC"))  # nach Fenster


# ------------------------------------------------------------------ Cache/Fail
def test_rate_limit_one_fetch_per_start(tmp_path):
    fetcher = CountingFetcher()
    nf = NewsFilter(str(tmp_path), {}, fetcher=fetcher)
    nf.update()
    nf.update()
    nf.update()
    assert fetcher.calls == 1


def test_cache_reused_across_instances(tmp_path):
    make_filter(tmp_path)  # schreibt Cache
    failing = CountingFetcher(fail=True)
    nf = NewsFilter(str(tmp_path), {}, fetcher=failing)
    nf.update()  # frischer Cache -> kein Fetch noetig
    assert failing.calls == 0
    assert nf.is_blackout(pd.Timestamp("2025-03-07 13:30", tz="UTC"), "EURUSD")


def test_fail_closed_live_without_feed(tmp_path):
    nf = NewsFilter(str(tmp_path), {}, fetcher=CountingFetcher(fail=True),
                    fail_closed=True)
    nf.update()
    assert nf.is_blackout(pd.Timestamp("2020-01-01 00:00", tz="UTC"), "EURUSD")
    assert nf.tier1_halt(pd.Timestamp("2020-01-01 00:00", tz="UTC"))


def test_fail_open_option(tmp_path):
    nf = NewsFilter(str(tmp_path), {}, fetcher=CountingFetcher(fail=True),
                    fail_closed=False)
    nf.update()
    assert not nf.is_blackout(pd.Timestamp("2020-01-01 00:00", tz="UTC"), "EURUSD")


def test_backtest_mode_reads_csv_only(tmp_path):
    make_filter(tmp_path)  # Cache anlegen
    bt = NewsFilter(str(tmp_path), {}, backtest=True,
                    fetcher=CountingFetcher(fail=True))
    bt.update()
    assert bt.is_blackout(pd.Timestamp("2025-03-07 13:30", tz="UTC"), "EURUSD")
    assert not bt.is_blackout(pd.Timestamp("2025-03-07 14:00", tz="UTC"), "EURUSD")
    assert bt.tier1_halt(pd.Timestamp("2025-03-07 13:30", tz="UTC"))


def test_backtest_mode_empty_cache_fail_open(tmp_path):
    bt = NewsFilter(str(tmp_path), {}, backtest=True,
                    fetcher=CountingFetcher(fail=True))
    bt.update()
    assert not bt.is_blackout(pd.Timestamp("2025-03-07 13:30", tz="UTC"), "EURUSD")


# ------------------------------------------------------------------ Smoke
_HAS_CORE_IND = importlib.util.find_spec("core.indicators") is not None


@pytest.mark.xfail(not _HAS_CORE_IND, strict=False,
                   reason="core.indicators in paralleler Entwicklung")
def test_smoke_imports():
    import core.indicators  # noqa: F401
    from core.news_filter import NewsFilter as NF  # noqa: F401
