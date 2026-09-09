"""core/fixtures.py — synthetische OHLCV-Generatoren für Tests (SPEC §2/§3).

Liefert DataFrames exakt im Daten-Kontrakt: Index = tz-aware UTC
DatetimeIndex, Spalten open/high/low/close/tick_volume (float64),
OHLC-Konsistenz (high >= max(open, close), low <= min(open, close),
tick_volume > 0). Deterministisch über ``seed``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_KINDS = ("random", "trend_up", "trend_down", "range", "breakout")
_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}


def _close_path(kind: str, n: int, rng: np.random.Generator) -> np.ndarray:
    vol = 0.6
    noise = rng.normal(0.0, vol, n)
    if kind == "random":
        drift = np.zeros(n)
    elif kind == "trend_up":
        drift = np.full(n, 0.25)
    elif kind == "trend_down":
        drift = np.full(n, -0.25)
    elif kind == "range":
        # Mean-Reversion: Sinus um Niveau + kleine Vol
        t = np.arange(n)
        path = 100.0 + 5.0 * np.sin(2.0 * np.pi * t / max(n / 4.0, 8.0))
        return path + np.cumsum(noise * 0.15)
    elif kind == "breakout":
        drift = np.zeros(n)
        split = int(n * 0.7)
        drift[split:] = 0.6  # Trendbruch im letzten Drittel
        noise[:split] *= 0.4  # enge Range vor dem Breakout
    else:  # pragma: no cover
        raise ValueError(f"unbekanntes kind: {kind}")
    return 100.0 + np.cumsum(drift + noise)


def make_synthetic_ohlcv(kind: str = "random", n: int = 500, seed: int = 42,
                         timeframe: str = "H1") -> pd.DataFrame:
    """Synthetisches OHLCV-DataFrame im Daten-Kontrakt (SPEC §3).

    ``kind`` ∈ {"random", "trend_up", "trend_down", "range", "breakout"};
    ``timeframe`` ∈ {"M1","M5","M15","H1","H4","D1"}.
    """
    if kind not in _KINDS:
        raise ValueError(f"kind muss in {_KINDS} sein, nicht {kind!r}")
    if timeframe not in _TF_MINUTES:
        raise ValueError(f"timeframe muss in {tuple(_TF_MINUTES)} sein, nicht {timeframe!r}")
    if n < 10:
        raise ValueError("n muss >= 10 sein")

    rng = np.random.default_rng(seed)
    index = pd.date_range("2020-01-01", periods=n,
                          freq=pd.Timedelta(minutes=_TF_MINUTES[timeframe]),
                          tz="UTC", name="time")

    close = _close_path(kind, n, rng)
    open_ = np.empty(n)
    open_[0] = close[0] - rng.normal(0.0, 0.3)
    open_[1:] = close[:-1]
    spread_hi = np.abs(rng.normal(0.0, 0.4, n)) + 0.05
    spread_lo = np.abs(rng.normal(0.0, 0.4, n)) + 0.05
    high = np.maximum(open_, close) + spread_hi
    low = np.minimum(open_, close) - spread_lo
    tick_volume = np.abs(rng.normal(1000.0, 250.0, n)) + 1.0

    return pd.DataFrame(
        {
            "open": open_.astype("float64"),
            "high": high.astype("float64"),
            "low": low.astype("float64"),
            "close": close.astype("float64"),
            "tick_volume": tick_volume.astype("float64"),
        },
        index=index,
    )
