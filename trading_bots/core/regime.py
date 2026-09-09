"""core/regime.py — RegimeFilter (SPEC §4.8).

method ∈ {"off", "adx_proxy", "atr_percentile", "hmm"}.

HMM: GaussianHMM(2 States, covariance_type="full") auf Features
[log_ret, RV20, ATR_norm]; monatlicher Refit (expanding, konfigurierbar);
State-Remapping nach Varianz (Label-Switching); Hysterese 0.4/0.6 auf der
*gefilterten* (forward-only) Posterior — strikt kausal (nur Daten ≤ t).
Sanity-Checks (Konvergenz, Occupancy > 2 %, Selbsttransition > 0.9) mit
automatischem Fallback auf adx_proxy.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

try:  # hmmlearn optional; bei Fehlen automatischer Fallback auf adx_proxy
    from hmmlearn.hmm import GaussianHMM

    _HAS_HMMLEARN = True
except Exception:  # pragma: no cover
    GaussianHMM = None
    _HAS_HMMLEARN = False

try:  # Parallel-Entwicklung: core.indicators ggf. noch nicht vorhanden
    from core import indicators as _core_ind
except Exception:  # pragma: no cover
    _core_ind = None

METHODS = ("off", "adx_proxy", "atr_percentile", "hmm")

DEFAULT_PARAMS: dict = {
    # Proxy
    "adx_len": 14,
    "adx_th": 25.0,
    # ATR-Percentil
    "atr_len": 14,
    "pct_len": 100,
    "pct_th": 50.0,
    # HMM
    "rv_len": 20,
    "min_train_bars": 500,
    "refit": "monthly",          # "monthly" | "weekly" | "none" | int (alle N Bars)
    "hmm_iter": 100,
    "random_state": 42,
    "p_enter_trend": 0.6,        # Hysterese: Trend ab P(high-vol) >= 0.6
    "p_exit_trend": 0.4,         #            Range ab P(high-vol) <= 0.4
    "occupancy_min": 0.02,       # Sanity: jeder State > 2 % der Trainings-Bars
    "self_trans_min": 0.9,       # Sanity: Diagonale der Transitionsmatrix > 0.9
    "warmup_neutral": True,      # vor erstem Fit / bei NaN: beide Richtungen offen
}


# ------------------------------------------------------------ Indikatoren
def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    if _core_ind is not None:
        return _core_ind.atr(df, n)
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()  # Wilder


def _adx(df: pd.DataFrame, n: int) -> pd.Series:
    if _core_ind is not None:
        out = _core_ind.adx(df, n)
        return out["adx"] if isinstance(out, pd.DataFrame) else out
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr_w = tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / atr_w
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / atr_w
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def _rolling_percentile(s: pd.Series, n: int) -> pd.Series:
    if _core_ind is not None and hasattr(_core_ind, "rolling_percentile"):
        return _core_ind.rolling_percentile(s, n)
    return s.rolling(n, min_periods=n).apply(
        lambda w: 100.0 * (w <= w[-1]).mean(), raw=True
    )


# ------------------------------------------------------------ HMM-Hilfen
def _log_gauss(X: np.ndarray, mean: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """log N(x | mean, cov) fuer alle Zeilen von X (n_samples, d)."""
    d = X.shape[1]
    try:
        L = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        cov = cov + 1e-9 * np.eye(d)
        L = np.linalg.cholesky(cov)
    diff = X - mean
    sol = np.linalg.solve(L, diff.T).T                       # (n, d)
    maha = (sol ** 2).sum(axis=1)
    log_det = 2.0 * np.log(np.diag(L)).sum()
    return -0.5 * (d * np.log(2.0 * np.pi) + log_det + maha)


@dataclass
class _RefitLog:
    time: pd.Timestamp
    ok: bool
    reason: str = ""
    extra: dict = field(default_factory=dict)


class RegimeFilter:
    """SPEC §4.8. fit() ist kausal: allow_*(i) haengt nur von Daten ≤ Bar i ab."""

    def __init__(self, method: str = "adx_proxy", params: dict | None = None):
        if method not in METHODS:
            raise ValueError(f"method muss in {METHODS} sein, nicht {method!r}")
        self.method = method
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.diagnostics_: list[_RefitLog] = []
        self._allow_trend: np.ndarray | None = None
        self._allow_range: np.ndarray | None = None
        self._method_used: np.ndarray | None = None  # je Bar: tatsaechliche Methode
        self._n = 0

    # ------------------------------------------------------------- API
    def fit(self, df: pd.DataFrame) -> "RegimeFilter":
        n = len(df)
        self._n = n
        self.diagnostics_ = []
        if n == 0:
            self._allow_trend = np.zeros(0, dtype=bool)
            self._allow_range = np.zeros(0, dtype=bool)
            self._method_used = np.array([], dtype=object)
            return self
        if self.method == "off":
            self._allow_trend = np.ones(n, dtype=bool)
            self._allow_range = np.ones(n, dtype=bool)
            self._method_used = np.array(["off"] * n, dtype=object)
        elif self.method == "adx_proxy":
            self._set_arrays(*self._proxy_arrays(df), method="adx_proxy")
        elif self.method == "atr_percentile":
            self._set_arrays(*self._atr_pct_arrays(df), method="atr_percentile")
        else:
            self._fit_hmm(df)
        return self

    def allow_trend(self, i: int) -> bool:
        return bool(self._allow_trend[i]) if 0 <= i < self._n else False

    def allow_range(self, i: int) -> bool:
        return bool(self._allow_range[i]) if 0 <= i < self._n else False

    def method_used(self, i: int) -> str:
        return str(self._method_used[i]) if 0 <= i < self._n else "none"

    # ------------------------------------------------------------- Proxys
    def _set_arrays(self, trend: np.ndarray, range_: np.ndarray, method: str) -> None:
        self._allow_trend = trend
        self._allow_range = range_
        self._method_used = np.array([method] * self._n, dtype=object)

    def _proxy_arrays(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        adx = _adx(df, int(self.params["adx_len"])).to_numpy(dtype=float)
        th = float(self.params["adx_th"])
        nan = np.isnan(adx)
        neutral = bool(self.params["warmup_neutral"])
        trend = np.where(nan, neutral, adx > th)
        range_ = np.where(nan, neutral, adx < th)
        return trend.astype(bool), range_.astype(bool)

    def _atr_pct_arrays(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        atr = _atr(df, int(self.params["atr_len"]))
        pct = _rolling_percentile(atr, int(self.params["pct_len"])).to_numpy(dtype=float)
        th = float(self.params["pct_th"])
        nan = np.isnan(pct)
        neutral = bool(self.params["warmup_neutral"])
        trend = np.where(nan, neutral, pct >= th)
        range_ = np.where(nan, neutral, pct <= th)
        return trend.astype(bool), range_.astype(bool)

    # ------------------------------------------------------------- HMM
    @staticmethod
    def _features(df: pd.DataFrame, rv_len: int, atr_len: int) -> pd.DataFrame:
        close = df["close"].astype(float)
        log_ret = np.log(close).diff()
        rv = log_ret.rolling(rv_len, min_periods=rv_len).std()
        atr_norm = _atr(df, atr_len) / close
        return pd.DataFrame(
            {"log_ret": log_ret, "rv": rv, "atr_norm": atr_norm}, index=df.index
        )

    def _refit_due(self, i: int, ts: pd.Timestamp, last: pd.Timestamp | None,
                   bars_since: int) -> bool:
        refit = self.params["refit"]
        if last is None:
            return True
        if isinstance(refit, int):
            return bars_since >= refit
        if refit == "monthly":
            return (ts.year, ts.month) != (last.year, last.month)
        if refit == "weekly":
            return (ts.isocalendar().year, ts.isocalendar().week) != (
                last.isocalendar().year, last.isocalendar().week)
        return False  # "none"

    def _fit_one(self, X_train: np.ndarray) -> tuple[object, int] | None:
        """Fit + Sanity-Checks + State-Remapping. Rueckgabe: (model, trend_state) oder None."""
        p = self.params
        if not _HAS_HMMLEARN:
            return None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = GaussianHMM(
                    n_components=2, covariance_type="full",
                    n_iter=int(p["hmm_iter"]), random_state=int(p["random_state"]),
                )
                model.fit(X_train)
                states = model.predict(X_train)
        except Exception as exc:
            return ("fail", f"fit-exception: {exc}")
        # Sanity 1: Konvergenz
        if not getattr(model.monitor_, "converged", False):
            return ("fail", "nicht konvergiert")
        # Sanity 2: finite Parameter
        if not (np.isfinite(model.means_).all() and np.isfinite(model.covars_).all()
                and np.isfinite(model.transmat_).all()):
            return ("fail", "nicht-finite Parameter")
        # Sanity 3: Occupancy > 2 %
        occ = np.bincount(states, minlength=2) / max(len(states), 1)
        if occ.min() <= float(p["occupancy_min"]):
            return ("fail", f"occupancy {occ.min():.4f} <= {p['occupancy_min']}")
        # Sanity 4: Selbsttransition > 0.9
        diag = np.diag(model.transmat_)
        if diag.min() <= float(p["self_trans_min"]):
            return ("fail", f"self-transition {diag.min():.3f} <= {p['self_trans_min']}")
        # State-Remapping nach Varianz des log_ret (Label-Switching!)
        var = np.array([X_train[states == s, 0].var() if (states == s).any() else np.nan
                        for s in range(2)])
        if not np.isfinite(var).all():
            return ("fail", "State-Varianz nicht endlich")
        trend_state = int(np.argmax(var))  # hoehere Varianz = Trend/Vol-Regime
        return (model, trend_state)

    def _fit_hmm(self, df: pd.DataFrame) -> None:
        p = self.params
        n = self._n
        neutral = bool(p["warmup_neutral"])
        trend = np.full(n, neutral, dtype=bool)
        range_ = np.full(n, neutral, dtype=bool)
        used = np.array(["warmup"] * n, dtype=object)

        feats = self._features(df, int(p["rv_len"]), int(p["atr_len"]))
        proxy_trend, proxy_range = self._proxy_arrays(df)

        if not _HAS_HMMLEARN:
            log.warning("RegimeFilter: hmmlearn fehlt -> Fallback adx_proxy")
            self.diagnostics_.append(
                _RefitLog(df.index[0], False, "hmmlearn nicht installiert"))
            self._set_arrays(proxy_trend, proxy_range, method="adx_proxy")
            return

        min_train = int(p["min_train_bars"])
        model = None
        trend_state = None
        alpha: np.ndarray | None = None   # gefilterte Posterior, inkrementell
        mu = sd = None                    # Standardisierung des Trainingsfensters
        last_refit: pd.Timestamp | None = None
        bars_since = 0
        in_trend = False                  # Hysterese-Zustand

        X_all = feats.to_numpy(dtype=float)
        valid_mask = feats.notna().all(axis=1).to_numpy()

        for i in range(n):
            ts = pd.Timestamp(df.index[i])
            if not valid_mask[i]:
                continue
            n_hist = int(valid_mask[: i + 1].sum())
            if n_hist < min_train:
                trend[i], range_[i] = proxy_trend[i], proxy_range[i]
                used[i] = "adx_proxy"
                continue
            if self._refit_due(i, ts, last_refit, bars_since):
                hist_idx = np.flatnonzero(valid_mask[: i + 1])  # expanding, nur <= i
                X_train_raw = X_all[hist_idx]
                mu = X_train_raw.mean(axis=0)   # Standardisierung nur aus Vergangenheit
                sd = X_train_raw.std(axis=0)
                sd[sd == 0] = 1e-12
                result = self._fit_one((X_train_raw - mu) / sd)
                last_refit = ts
                bars_since = 0
                alpha = None
                if isinstance(result, tuple) and len(result) == 2 and result[0] == "fail":
                    self.diagnostics_.append(_RefitLog(ts, False, result[1]))
                    model = None
                elif result is None:
                    self.diagnostics_.append(_RefitLog(ts, False, "hmmlearn fehlt"))
                    model = None
                else:
                    model, trend_state = result
                    self.diagnostics_.append(_RefitLog(ts, True, "ok"))
            bars_since += 1
            if model is None:
                trend[i], range_[i] = proxy_trend[i], proxy_range[i]
                used[i] = "adx_proxy"
                continue
            # Inkrementeller Forward-Filter: P(state_i | x_<=i, Modell aus Daten <= refit)
            x = (X_all[i] - mu) / sd
            log_b = np.array([_log_gauss(x[None, :], model.means_[s], model.covars_[s])[0]
                              for s in range(model.n_components)])
            b = np.exp(log_b - log_b.max())
            if alpha is None:
                a = model.startprob_ * b
            else:
                a = (alpha @ model.transmat_) * b
            total = a.sum()
            alpha = a / total if total > 0 else np.full(model.n_components,
                                                        1.0 / model.n_components)
            p_trend = float(alpha[trend_state])
            if in_trend:  # Hysterese 0.4/0.6
                in_trend = p_trend > float(p["p_exit_trend"])
            else:
                in_trend = p_trend >= float(p["p_enter_trend"])
            trend[i] = in_trend
            range_[i] = not in_trend
            used[i] = "hmm"
        self._allow_trend = trend
        self._allow_range = range_
        self._method_used = used
