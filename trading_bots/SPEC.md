# SPEC.md — MT5 Trading-Bot-Framework + 5 Strategien (Single Source of Truth)

**Version 1.0 · 2026-09-03 · Status: verbindlich für alle Implementierungs-Agenten**

## 0. Mission
5 eigenständige, eigenvalidierte Python-Trading-Bots für MT5 (Demo, später Prop-Firm) auf Linux. Anbindung via **pymt5linux (RPyC-Bridge)**. Ziel: OOS Profit Factor > 1.5, min. 1:2 RR, Prop-tauglich (0,5 % Risiko/Trade, EOD-Drawdown-fokussiert).

**Evidenz-Prinzip:** Der Edge sitzt im Filter-Stack, nicht im Signal. Alle Filter sind konfigurierbare, einzeln abschaltbare Layer (A/B-testbar). Jede Strategie läuft im selben Backtester mit identischem Kostenmodell.

## 1. Tech-Stack & harte Constraints
- Python ≥ 3.10 (Backtest-Pfad), Live-/Fetch-Pfad ≥ 3.13 (pymt5linux). Pakete: pandas, numpy, scipy, scikit-learn, hmmlearn, xgboost, pyyaml, requests, matplotlib, rpyc (nur Live-Seite; Version beidseitig identisch, Stand 2026-09-04: 6.0.2 — ursprünglich 5.3.1 geplant, angepasst an den laufenden pymt5linux-Server; numpy-Pin <2.0 entfallen, gegen diesen Server empirisch verifiziert)
- KEINE Abhängigkeit vom MetaTrader5-Pip-Paket im Backtest-Code (Windows-only); MT5-Zugriff ausschließlich über `core/connector.py`-Abstraktion
- Alle Zeitreihen intern **UTC, tz-aware** ("UTC-at-ingestion"). Sessions ausschließlich via `zoneinfo` ("America/New_York", "Europe/London") definiert — NIEMALS Serverzeit hardcoden (DST-Asynchronwochen!)
- Kein Lookahead: Indikatoren/Signale nutzen ausschließlich abgeschlossene Bars (close[1]-Prinzip); SMC-Events erst nach Bestätigungs-Lag sichtbar
- Kostenmodell IMMER aktiv: Spread (konfigurierbar je Symbol) + Slippage-Multiplikator (Stress 0.5×/1×/2×/3×) + Kommission + Swap
- Determinismus: gleiche Daten + gleiche Config = identisches Ergebnis (seed-kontrolliert)

## 2. Repo-Layout
```
/mnt/agents/output/trading_bots/
├── core/
│   ├── time_engine.py      # Zeitzonen, Sessions, Server-Offset
│   ├── indicators.py       # ATR, EMA/SMA, RSI, ADX/DI, VWAP, Donchian, Swings
│   ├── smc.py              # kausale FVG/OB/BOS/CHoCH/Sweep-Detection
│   ├── risk.py             # Sizing, Prop-Limits, Circuit-Breaker
│   ├── news_filter.py      # FF-XML-Feed, Blackout-Logik
│   ├── regime.py           # HMM-Filter + Proxy-Fallback
│   ├── backtester.py       # Event-Engine, Kostenmodell, Stress
│   ├── validation.py       # WFA, WFE, DSR, PBO, Monte-Carlo, Prop-Sim
│   ├── connector.py        # pymt5linux-Abstraktion (fetch + live)
│   ├── live.py             # Live-Loop für Demo
│   ├── reporting.py        # Metriken, Trade-Stats, Reports
│   └── fixtures.py         # synthetische OHLCV-Generatoren für Tests
├── strategies/
│   ├── base.py             # Strategy-ABC + Signal-Dataclass
│   ├── s1_trend_pullback.py
│   ├── s2_vwap_pullback.py
│   ├── s3_silver_bullet.py
│   ├── s4_london_breakout.py
│   └── s5_filtered_mr.py
├── configs/                # YAML: common.yaml, prop_ftmo.yaml, pro Bot eine Datei
├── scripts/                # fetch_data.py, run_backtest.py, run_wfa.py, run_live.py
├── tests/                  # pytest, nutzt fixtures.py
├── data/                   # Cache (CSV/parquet), NICHT im git
└── README.md
```

## 3. Daten-Kontrakt
OHLCV-DataFrame: Index = `pd.DatetimeIndex` tz-aware UTC, Spalten exakt: `open, high, low, close, tick_volume` (float64). Cache-Format: **Parquet** (`data/{SYMBOL}_{TF}.parquet`, bevorzugt — kleiner/schneller; Stand 2026-09-04 umgestellt), CSV wird als Fallback weiter gelesen. Funktionssignatur:
```python
def load_ohlcv(symbol: str, timeframe: str, start: datetime, end: datetime,
               source: str = "cache") -> pd.DataFrame
```
`timeframe ∈ {"M1","M5","M15","H1","H4","D1"}`. MT5-Fetch konvertiert Serverzeit→UTC bei Ingestion. Gap-Audit-Funktion `audit_gaps(df, timeframe) -> GapReport` (fehlende Bars außerhalb Wochenende melden).

## 4. Interface-Kontrakte

### 4.1 strategies/base.py
```python
@dataclass
class Signal:
    time: pd.Timestamp          # UTC, Signal-Bar (geschlossen)
    symbol: str
    direction: int              # +1 long, -1 short
    entry_type: str             # "market" | "limit"
    entry_price: float | None   # None bei market
    stop_loss: float
    take_profit: float | None   # None = nur Time/Structure-Exit
    risk_pct: float             # i.d.R. 0.005
    meta: dict                  # Filter-Infos, Regime, News-State
    expires_bars: int = 0       # für limit-Orders

class Strategy(ABC):
    name: str
    params: dict                # aus YAML, alle Parameter hier
    def __init__(self, params: dict): ...
    @abstractmethod
    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        """bars: {'M5': df, 'H1': df, ...} bis inkl. Index i (nur geschlossene Bars).
           i ist die Position der aktuellen Bar im View des Primaer-TF. Die Views
           koennen Warmup-Historie VOR dem Backtest-Fenster enthalten (WFA-Folds) —
           immer ueber i bzw. vom Ende her zugreifen, nie Fenster-Indizes annehmen.
           Gibt Signal oder None. REIN kausal."""
    def on_trade_closed(self, trade: dict) -> None: ...   # optional State
```
Multi-Timeframe: Strategie deklariert `required_timeframes: list[str]`. Engine liefert aligned Views.

### 4.2 core/backtester.py
```python
@dataclass
class CostModel:
    # Alle *_points-Angaben in MT5-Punkten (kleinste Preiseinheit des Symbols);
    # Umrechnung in Preiseinheiten via BacktestConfig.point
    spread_points: float        # halber Spread beim Entry, halber beim Exit
    slippage_multiplier: float = 1.0   # Stress-Faktor
    commission_per_lot_rt: float = 0.0
    swap_long_pts: float = 0.0
    swap_short_pts: float = 0.0
    triple_swap_weekday: int = 2       # Mittwoch

@dataclass
class BacktestConfig:
    symbol: str
    timeframes: list[str]
    start: datetime; end: datetime
    costs: CostModel
    risk: "RiskConfig"
    intrabar: str = "stop_first"   # oder "m1" wenn M1-Daten geladen
    point_value: float = 1.0       # aus Symbol-Spec, siehe connector
    account_ccy_rate: float = 1.0
    point: float = 1.0             # kleinste Preiseinheit (MT5-point, z. B. 0.01
                                   # fuer XAUUSD); 1.0 = Points = Preiseinheiten

class Backtester:
    def __init__(self, strategy: Strategy, config: BacktestConfig): ...
    def run(self) -> "BacktestResult"
```
Regeln: Market-Entry = Open der nächsten Bar; Limit-Entry nur wenn Bar-Range das Limit berührt (konservativ: bei Limit UND SL-Touch in derselben Bar → SL zuerst); Slippage = `slippage_multiplier × 0.5 × spread_points × point` auf Market-Orders, zusätzlich fester `slippage_extra_points × point`; Swap = `swap_*_pts × point` je Server-Mitternacht; TP/SL-Prüfung auf High/Low der Bar ("stop_first"-Annahme) oder M1-Pfad. Time-Exits und EOD-Flat werden von der Risiko-Engine erzwungen. KEINE Position über das Wochenende, wenn `friday_flat: true`.

### 4.3 core/risk.py
```python
@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 0.5
    min_rr: float = 2.0
    daily_loss_halt_pct: float = 1.5     # bot-interner Halt
    eod_flat: bool = True
    eod_flat_time_ny: str = "16:55"
    friday_flat: bool = True
    max_concurrent: int = 1
    streak_limiter: int = 0              # 0=aus; N Verluste in Folge → Pause bis nächster Tag
    prop_profile: str = "none"           # z.B. "ftmo_2step"
```
Prop-Profile (YAML): `daily_loss_pct`, `daily_loss_basis: "prev_day_balance"`, `overall_loss_pct`, `profit_target_pct`, `best_day_consistency_pct`, `news_blackout_min_before/after`, `leverage`. Engine trackt Equity inkl. Floating PnL; bei Verletzung von `daily_loss_halt` → keine neuen Entries bis nächster Server-Tag 00:00 (Reset-Logik konfigurierbar). Sizing: `lots = risk_amount / (sl_points × point_value)` gerundet auf `volume_step`, begrenzt durch `volume_min/max`.

### 4.4 core/time_engine.py
```python
def to_utc(ts: pd.Timestamp | pd.Series, from_tz: str) -> ...
def in_session(ts_utc: pd.Timestamp, session: str, start_hhmm: str, end_hhmm: str) -> bool
   # session ∈ {"America/New_York","Europe/London","UTC",...}
def ny_time(ts_utc) -> pd.Timestamp  # Shortcut
def session_window_mask(index_utc: DatetimeIndex, tz: str, start: str, end: str) -> np.ndarray
def estimate_server_offset_utc(tick_time_epoch: int) -> timedelta
```
Tests müssen DST-Übergänge (März/November, US≠EU-Wochen) abdecken.

### 4.5 core/indicators.py (alle vektorisiert, kausal, ohne externe TA-Libs)
`ema(s, n)`, `sma(s, n)`, `rsi(s, n)` (Wilder), `atr(df, n)` (Wilder), `adx(df, n)` → DataFrame[adx, plus_di, minus_di], `vwap_session(df, session_tz)` (tick_volume-gewichtet, Reset je Session), `donchian(df, n)` → upper/lower, `swing_points(df, left, right, confirmed_lag)` → kausale Swing-High/Low-Serien (erst nach `right` Bars sichtbar!), `fib_zone(df_or_swing, lo=0.382, hi=0.618)`, `rolling_percentile(s, n)`.

### 4.6 core/smc.py (kausale Reimplementierung — NICHT das PyPI-Paket, das repaintet)
`fair_value_gaps(df, min_size_atr: float, atr: Series) -> DataFrame[fvg_top, fvg_bottom, direction, formed_at, confirmed_at]` — confirmed_at = formed + 1 Bar. `swing_structure(df, left, right)` → BOS/CHoCH-Events (kausal). `liquidity_sweep(df, level, wick_excess_min)` → bool/Events (Wick über Level, Close zurück). `order_blocks(df, bos_events, ...)`. `equal_highs_lows(df, tolerance_atr, lookback)`.

### 4.7 core/news_filter.py
```python
class NewsFilter:
    def __init__(self, cache_dir: str, prop_profile: dict): ...
    def update(self) -> None   # lädt https://nfs.faireconomy.media/ff_calendar_thisweek.xml
                               # Rate-Limit: 1×/Start + täglich; parst impact/currency/time(→UTC)
    def is_blackout(self, ts_utc: datetime, symbol: str) -> bool
    def tier1_halt(self, ts_utc: datetime) -> bool   # FOMC/NFP/CPI → global
```
Symbol→Ccy-Mapping: XAUUSD→{USD}, NAS100/US100→{USD}, EURUSD→{EUR,USD}, GBPUSD→{GBP,USD}, USDJPY→{USD,JPY}, USDCHF→{USD,CHF}, AUDUSD→{AUD,USD}, USDCAD→{USD,CAD}, NZDUSD→{NZD,USD}, EURJPY→{EUR,JPY}, GBPJPY→{GBP,JPY}, BTC/ETH→{USD}. Default-Fenster: −15/+10 min, High-Impact; prop_profile kann Fenster überschreiben. Backtest-Modus: liest historischen Event-Cache (CSV) — gleiche API. Fail-closed: bei fehlendem Feed im Live-Betrieb → keine neuen Entries.

### 4.8 core/regime.py
```python
class RegimeFilter:
    def __init__(self, method: str = "adx_proxy", params: dict = ...):
        # method ∈ {"off", "adx_proxy", "atr_percentile", "hmm"}
    def fit(self, df: pd.DataFrame) -> None      # kausal, nur Vergangenheit
    def allow_trend(self, i: int) -> bool
    def allow_range(self, i: int) -> bool
```
HMM: GaussianHMM(2 States, full cov), Features [log-ret, RV20, ATR_norm], Refit-Frequenz konfigurierbar (default monatlich, expanding), State-Remapping nach Varianz (Label-Switching!), Hysterese 0.4/0.6, Sanity-Checks (Konvergenz, Occupancy>2 %, Selbsttransition>0.9) mit Fallback auf `adx_proxy`. Proxy: `allow_trend = adx>25`, `allow_range = adx<25`.

### 4.9 core/validation.py
```python
def walk_forward(strategy_cls, param_grid, data, cfg, is_months=24, oos_months=6,
                 anchored=False) -> WFAResult    # rolling default, ≥6 Folds
def wfe(result) -> float                          # OOS-PF / IS-PF; Gate: median ≥ 0.5
def deflated_sharpe(returns, n_trials, ...) -> float   # Gate ≥ 0.95
def pbo_cscv(perf_matrix, S=8) -> float           # Gate < 0.10
def monte_carlo_dd(trades, n=10000) -> dict        # Trade-Shuffle: p95 MaxDD
def block_bootstrap(trades, block_len=None) -> dict
def prop_simulation(trades, profile) -> dict       # P(Daily-Breach), P(Overall-Breach),
                                                   # P(Target in X Tagen), EOD-DD-Verlauf
def plateau_select(grid_results) -> dict           # Parameter mit ≥60 % pos. Nachbarzellen
```
Plateau-Selektion statt Max-PF (Anti-Overfitting). Alle Gates in `configs/validation_gates.yaml`.

### 4.10 core/connector.py (Live + Fetch via pymt5linux)
```python
class MT5Connector:            # Wrappt rpyc-Client auf mt5linux
    def connect(self, host, port) -> None
    def fetch_ohlcv(self, symbol, timeframe, start, end) -> pd.DataFrame  # UTC!
    def account_info(self) -> dict
    def positions(self, symbol=None) -> list[dict]
    def send_market(self, symbol, direction, lots, sl, tp, deviation) -> dict
    def send_limit(self, ...) -> dict
    def modify_sltp(self, ticket, sl, tp) -> bool
    def close(self, ticket) -> bool
    def symbol_spec(self, symbol) -> dict   # point, tick_size, tick_value, volume_step/min/max, stops_level
    def server_offset(self) -> timedelta    # via symbol_info_tick().time vs utc_now
    def health(self) -> bool
```
Sizing nutzt `order_calc_profit`-Äquivalent zur Validierung. Retcode-Handling 10015/10016/10030 (Retry-Logik). Live nur für Demo; Dry-Run-Flag Pflicht.

### 4.11 core/reporting.py
`compute_metrics(trades) -> dict`: PF, Winrate, avgR, MaxDD (Balance + Equity), Sharpe, Sortino, n, längste Verlustserie, PF nach Richtung (Long/Short getrennt — Long-Bias-Falle!), PF nach Jahr. `render_report(result, path)` → Markdown-Tabelle + Equity-PNG (matplotlib). `ab_compare(results: dict[str, BacktestResult])` → Filter-Layer-Vergleichstabelle.

## 5. Strategie-Spezifikationen (verbindlich, aus dim-Reports)

### S1 — TrendPullback (XAUUSD, H4; Bias D1) — Basis: dim01 "V5"
- **Bias (D1):** Close > SMA200 UND DI-State long (plus_di > minus_di seit letztem Cross) UND ADX ≥ 20 (Regime-Gate, NICHT Entry-Filter). Short spiegelverkehrt.
- **Setup (H4):** Pullback in Zone = EMA20(H4) ∩ Fib 38.2–61.8 % des letzten Impuls-Swings; Touch = Bar-Low/High in Zone.
- **Trigger:** Reversal-Close in Bias-Richtung (Close > Open bei Long) nach Zone-Touch.
- **Entry:** Market nächste Bar. **SL:** max(1.5×ATR14(H4), hinter Swing-Extrem). **TP1:** 2R (50 %), Runner: Trail unter/über H4-Swing-Pivots. **Time-Exit:** 30 H4-Bars. 
- **Filter-Layer (A/B):** Session 07–17 UTC nur Entries; News-Filter; Regime-Filter; Freitag-flat.
- **Baseline-Vergleichsarm (Pflicht):** "V1" = DI-Cross D1 pur, SL 2×ATR, TP 2:1 (dokumentierter PF-1.54-Beleg). V5 muss V1 OOS schlagen, sonst V1 deployen.
- Param-Raum (WFO): ema_len {20,30,50}, sl_atr {1.25,1.5,2.0,2.5}, time_exit {15,30,60}, tp1_r {1.5,2.0,2.5}. Stabil: SMA200, ATR14, RR≥2.

### S2 — VWAPPullback (NAS100, M5; nur 9:45–11:30 America/New_York) — Basis: dim02
- Session-VWAP (tick_volume) ab 9:30 ET. **Kontext:** ≥3 M5-Closes ober-/unterhalb VWAP seit 9:45.
- **Setup:** Pullback-Touch VWAP + RSI(2) < 25 (Long) / > 75 (Short).
- **Trigger:** nächste M5 schließt in Trendrichtung über/unter VWAP → Market-Entry.
- **SL:** 1.5×ATR14(M5). **TP:** Vortages-High/Low (PDH/PDL), Fallback 2×ATR → muss ≥ 2R ergeben, sonst kein Trade. **Time-Exit:** 11:30 ET hart; EOD-Flat spätestens 16:55 ET. Max 1 Long + 1 Short/Tag. Kein Trailing.
- **Filter-Layer:** News-Filter (USD); Spread-Guard (max 2.0 Punkte US100); Freitag-Short-Bias als WFO-Variante.
- Param-Raum: rsi_th {15,20,25,30,35}, atr_mult {1.0,1.5,2.0,2.5}, trend_buffer_pct {0,0.2,0.4,0.6}, tp_mode {pdh,2atr,3atr}.

### S3 — SilverBullet (NAS100 + XAUUSD, M5) — Basis: dim03/dim04
- **Fenster (America/New_York, WFO wählt):** {10:00–11:00} Default; Alternativen {03:00–04:00}, {08:30–09:10}, {14:00–15:00}.
- **Referenz-Liquidität:** High/Low der 09:00-ET-Stundenkerze (Default; Alt: Asian-Range/Pre-Market).
- **Sweep:** Wick > Level + Close zurück in Range (Wick-Exzess ≥ 0.1×ATR).
- **MSS (Displacement):** Body ≥ 1.5×ATR20 UND Body/Range ≥ 0.7 UND bricht Swing (Fraktal k=2) per Close.
- **FVG-Entry:** FVG ≥ 0.3×ATR aus Displacement-Leg; Limit am 50 % CE; Expiry 12 Bars (Purge-Regel).
- **SL:** hinter Sweep-Extrem + 0.3×ATR. **TP:** Gegen-Liquidität, Gate RR ≥ 2. Max 1 Trade/Fenster. BE bei 3R (Runner-Option).
- **Filter-Layer:** HTF-Bias H4 (letztes BOS/CHoCH) als A/B-Arm; News-Filter; Killzone=ausserhalb Fenster kein Trade.
- Param-Raum: window, sweep_ref, disp_body_atr {1.0,1.5,2.0}, fvg_min {0.1,0.3,0.5}, expiry {8,12,20}, rr_min {2.0,2.5,3.0}, htf_bias {off,on}.

### S4 — LondonBreakout (USDJPY, H1) — Basis: dim05 (Trade-Desk-Replikation + Filter)
- **Range:** 00:00–06:59 UTC (H1). **Entry:** Market am H1-Close jenseits Range im Fenster 07:00–16:59 UTC. 1 Trade/Tag (erste Seite).
- **SL:** Range-Gegenseite. **TP:** 1.5R–2R (WFO). **EOD-Flat:** 21:00 UTC (Fix vs. Trade-Desk: kein Wochenend-Risiko). 
- **Filter-Layer (einzeln addierbar, Reihenfolge im WFO):** (a) ATR14(D1) > 20d-Median, (b) HTF-EMA200(H4)-Alignment, (c) Range-Band: 20 Pips ≤ Range ≤ 0.5×ADR20, (d) Skip Montag, (e) News-Filter.
- **Archetyp B (Retest-Variante):** Entry erst am Retest der Range-Grenze (Limit), SL dahinter. Als separate Config messbar.
- Param-Raum: tp_r {1.5,2.0}, range_min_pips {15,20,25}, range_max_adr {0.4,0.5,0.6}, atr_filter {off,on}, ema_filter {off,on}, entry_mode {close,retest}.

### S5 — FilteredMR (XAUUSD + EURUSD, H1) — Basis: dim10
- **Kontext-Gates (Pflicht):** ADX14 < 25 UND ATR14 ≤ 20er-Median UND EMA200(H1)-Bias (Long nur über EMA200 — Pullback-in-Trend-Logik, kein Range-Fading).
- **Signal:** RSI14 kreuzt unter 30 (Long) / über 70 (Short).
- **Entry:** Market nächste Bar. **SL:** 1.5×ATR14. **TP:** 2×SL (1:2 RR). **Time-Stop:** 48 H1-Bars.
- **Filter-Layer:** News-Filter; Session 07–21 UTC; Regime-Filter `allow_range` als A/B-Arm.
- Param-Raum: rsi_len {7,10,14,21}, rsi_th {(25,75),(30,70),(35,65)}, adx_max {20,25,30}, atr_mult {1.0,1.5,2.0}, time_stop {24,48,72}.

## 6. Meta-Layer (alle Strategien, A/B via Config)
1. `news_filter`: on/off (Pflicht-Default: on)
2. `regime_filter`: off/adx_proxy/hmm (Ablations-Pflicht: jede Strategie 1× ohne, 1× Proxy, HMM nur wenn Proxy geschlagen)
3. `cot_bias` (nur S4/S5-Forex): Wochen-Bias-Gate aus CFTC-Daten (`scripts/fetch_cot.py`, Socrata-Endpoints), A/B
4. `meta_labeling`: XGBoost-Secondary über Primary-Signalen — NUR wenn ≥300 Primary-Signale OOS-Edge zeigen; separater Schritt nach Bot-Validierung (Phase 4b)

## 7. Validierungs-Gates (Hard Gates, configs/validation_gates.yaml)
1. n(OOS) ≥ 300 Trades gesamt (Intraday ≥ 500 angestrebt); ≤ 1 optimierter Parameter pro 30 Trades
2. PF(1×Kosten) ≥ 1.5 OOS; PF(2×Kosten) ≥ 1.2; PF(3×Kosten) ≥ 1.0
3. WFE-Median ≥ 0.5, ≥ 3/5 Folds ≥ 0.5; WFE > 1.0 → Lookahead-Verdachtsprüfung
4. DSR ≥ 0.95 (ehrliche Trial-Zählung); PBO(CSCV, S=8) < 0.10
5. Monte-Carlo: p95-MaxDD ≤ 8 % Balance
6. Prop-Sim: P(Daily-Breach) ≤ 5 %, P(Overall-Breach) ≤ 10 %, Consistency-Rule-Check
7. Anti-Repaint-Tests: Shift-Test (+1 Bar → Ergebnis darf nicht kollabieren), deterministischer Re-Run identisch
8. Long/Short getrennt profitabel gemeldet (Long-Bias-Inflation dokumentieren)
9. DST-Wochen-Backtest (März/November) fehlerfrei

## 8. Definition of Done (Phase 3)
- `pytest` grün (Unit-Tests für indicators/smc/time_engine/risk; Integrations-Test: jede Strategie auf synthetischen Daten mit bekanntem Ergebnis)
- Jede Strategie läuft End-to-End im Backtester auf Synthetik-Daten + produziert Report
- `run_backtest.py --config configs/s1.yaml` CLI funktioniert
- README mit Setup (pymt5linux, rpyc-Pinning, MT5 "Max bars unlimited"), Daten-Fetch, Backtest, Live-Dry-Run
