"""tests/test_s12_s13_be_trail.py — Break-Even/Trail-Meta-Wiring fuer S12/S13.

S12 (RSI-Scalp) und S13 (VWAP-Fade-Scalp) hatten bisher keine dedizierte
Testdatei (Luecke, s. reports/s12_s13_rr_be_variant.md). Dieser Test deckt
NICHT die komplette Signal-Logik ab (unveraendert von dieser Session), nur
die NEU hinzugefuegten optionalen Meta-Felder (``be_at_r``/``be_buffer``/
``trail_atr_mult``), die core/backtester.py's Break-Even- und
Trailing-Stop-Mechanik ansteuern -- rueckwaertskompatibel (Default aus).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.s12_rsi_scalp import S12RsiScalp
from strategies.s13_vwap_fade_scalp import S13VwapFadeScalp


def _rsi_oversold_df() -> pd.DataFrame:
    """10 Bars kleine Auf/Ab-Oszillation (RSI(5)-Seed, haelt RSI >= 20),
    danach scharfer, gleichmaessiger Abwaertstrend -> RSI(5) crosst genau
    einmal unter 20 (Long-Signal). Rein monoton fallend waere UNGEEIGNET:
    Wilder-RSI seedet dann direkt bei 0 (nie zuvor >= 20), die
    Cross-Bedingung (``prev_rsi >= oversold > rsi_val``) wuerde nie
    auftreten (empirisch verifiziert)."""
    seed = [100.0]
    for i in range(9):
        seed.append(seed[-1] + (0.2 if i % 2 == 0 else -0.1))
    decline = [seed[-1]]
    for _ in range(20):
        decline.append(decline[-1] - 0.8)
    close = np.array(seed + decline[1:])
    idx = pd.date_range("2023-01-02", periods=len(close), freq="5min", tz="UTC")
    high = close + 0.3
    low = close - 0.3
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": 0.0}, index=idx)


def _first_signal(strat, df):
    bars = {"M5": df}
    for i in range(len(df)):
        sig = strat.on_bar(bars, i)
        if sig is not None:
            return sig
    return None


class TestS12BeTrailMeta:
    def test_defaults_off_no_be_or_trail_in_meta(self):
        strat = S12RsiScalp({"symbol": "XAUUSD", "rsi_len": 5, "atr_len": 5})
        sig = _first_signal(strat, _rsi_oversold_df())
        assert sig is not None
        assert "be_at_r" not in sig.meta
        assert "trail_atr_mult" not in sig.meta

    def test_be_at_r_populates_meta_scaled_by_atr(self):
        strat = S12RsiScalp({"symbol": "XAUUSD", "rsi_len": 5, "atr_len": 5, "be_at_r": 1.0, "be_buffer_atr": 0.1})
        sig = _first_signal(strat, _rsi_oversold_df())
        assert sig is not None
        assert sig.meta["be_at_r"] == pytest.approx(1.0)
        assert sig.meta["be_buffer"] == pytest.approx(0.1 * sig.meta["atr"])

    def test_trail_atr_mult_populates_meta(self):
        strat = S12RsiScalp({"symbol": "XAUUSD", "rsi_len": 5, "atr_len": 5, "trail_atr_mult": 2.0})
        sig = _first_signal(strat, _rsi_oversold_df())
        assert sig is not None
        assert sig.meta["trail_atr_mult"] == pytest.approx(2.0)
        assert sig.meta["trail_atr_len"] == strat.atr_len


class TestS13BeTrailMeta:
    def _dev_df(self, n: int = 40) -> pd.DataFrame:
        """Erste Haelfte flach (VWAP-Seed), dann scharfer Abwaertssprung ->
        Preis weit unter VWAP -> Long-Fade-Signal."""
        idx = pd.date_range("2023-01-02 08:00", periods=n, freq="5min", tz="UTC")
        close = np.r_[np.full(n // 2, 100.0), np.full(n - n // 2, 90.0)]
        high = close + 0.3
        low = close - 0.3
        open_ = np.r_[close[0], close[:-1]]
        return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                             "tick_volume": 0.0}, index=idx)

    def test_defaults_off_no_be_or_trail_in_meta(self):
        strat = S13VwapFadeScalp({"symbol": "XAUUSD", "dev_atr_mult": 1.0})
        sig = _first_signal(strat, self._dev_df())
        assert sig is not None
        assert "be_at_r" not in sig.meta
        assert "trail_atr_mult" not in sig.meta

    def test_be_at_r_populates_meta_scaled_by_atr(self):
        strat = S13VwapFadeScalp({"symbol": "XAUUSD", "dev_atr_mult": 1.0, "be_at_r": 1.5, "be_buffer_atr": 0.0})
        sig = _first_signal(strat, self._dev_df())
        assert sig is not None
        assert sig.meta["be_at_r"] == pytest.approx(1.5)
        assert sig.meta["be_buffer"] == pytest.approx(0.0)
