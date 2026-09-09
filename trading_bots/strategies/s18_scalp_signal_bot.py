"""strategies/s18_scalp_signal_bot.py — Portierung von "Scalp Signal Bot -
5 min v3.0.1" (TradingView, https://www.tradingview.com/script/1BmQAGQi-),
auf Nutzerwunsch A/B-getestet: Version A repliziert den STANDARD-Zustand
des Originals inkl. der "Backtest window"-Einstellung (nur die letzten
7 Tage werden gehandelt, `useWindow=true`/`backtestHours=168` im Original);
Version B ist identisch, nur mit deaktiviertem Zeitfenster (volle Historie),
um sauber zu vergleichen, wie stark dieser Default das Ergebnis verzerrt.

Portierte Kernlogik (1:1 aus dem Original-Pine-Code):
  - Struktur: kausal bestätigte Pivot-Hochs/-Tiefs (wie ta.pivothigh/low —
    Bestätigung erst `pivot_len` Bars im Nachhinein)
  - Liquidity Sweep: neues Tief/Hoch unter/ueber dem `sweep_lookback`-Fenster
    (das aktuelle Bar AUSGESCHLOSSEN), plus "Close back above/below"-Reclaim
  - Sweep-Age-Filter (`sweep_max_age_bars`), Sweep-Entry-Delay (blockt die
    Sweep-Bar selbst + `sweep_delay_bars` weitere)
  - Cluster+Reclaim-Unterdrueckung (mehrere Sweeps in eine Richtung +
    Reclaim -> Trades in der URSPRUENGLICHEN Sweep-Richtung fuer
    `sweep_max_age_bars` unterdruecken)
  - Entry: Bruch ueber/unter dem letzten bestaetigten Pivot (Break of
    Structure) + Sweep-Gate + Trend-Filter (Default CHOP = aus)
  - SL = Sweep-Preis (bzw. letzter Pivot als Fallback) +/- Puffer (Default:
    feste Tick-Anzahl, ATR-Puffer optional)
  - TP = R-Multiple auf den SL-Abstand (Default riskR=1.0 -> reines 1:1)

BEWUSST NICHT portiert: Volumen-Filter (Default "Off" im Original) und
Trend-Filter (Default "CHOP"=aus) — beide sind im Original bereits
deaktiviert, hier der Vollstaendigkeit halber trotzdem als Parameter
vorhanden, aber mit denselben (deaktivierten) Defaults.
"""
from __future__ import annotations

import pandas as pd

from strategies.base import Signal, Strategy, atr as _atr, ema as _ema


class S18ScalpSignalBot(Strategy):
    name = "s18_scalp_signal_bot"

    def __init__(self, params: dict):
        self.params = dict(params)
        p = self.params
        self.symbol = p.get("symbol", "XAUUSD")
        self.primary_tf = p.get("primary_tf", "M5")
        self.required_timeframes = [self.primary_tf]

        self.pivot_len = int(p.get("pivot_len", 3))
        self.sweep_lookback = int(p.get("sweep_lookback", 60))
        self.sweep_max_age_bars = int(p.get("sweep_max_age_bars", 12))
        self.sweep_delay_bars = int(p.get("sweep_delay_bars", 1))
        # "close_above" (Original-Default, strengere Variante: Schluss muss
        # von UNTER auf UEBER die Schwelle kreuzen) oder "same_bar" (lockerer:
        # reicht, wenn der Schluss DERSELBEN Sweep-Bar schon drueber liegt).
        self.sweep_confirm_mode = p.get("sweep_confirm_mode", "close_above")
        self.use_sweep_entry_delay = bool(p.get("use_sweep_entry_delay", True))
        self.use_reclaim_logic = bool(p.get("use_reclaim_logic", True))
        self.cluster_lookback_bars = int(p.get("cluster_lookback_bars", 20))
        self.min_sweep_cluster = int(p.get("min_sweep_cluster", 2))

        self.use_atr_buffer = bool(p.get("use_atr_buffer", False))
        self.atr_len = int(p.get("atr_len", 14))
        self.atr_mult = float(p.get("atr_mult", 0.15))
        self.tick_size = float(p.get("tick_size", 0.01))
        self.tick_buffer = int(p.get("tick_buffer", 10))

        self.use_long = bool(p.get("use_long", True))
        self.use_short = bool(p.get("use_short", True))
        self.risk_r = float(p.get("risk_r", 1.0))
        self.risk_pct = float(p.get("risk_pct", 0.005))

        # Backtest-Fenster (Original: useWindow=true/backtestHours=168 als
        # Default -> Version A). window_days=None -> Version B (voller Test).
        self.window_days = p.get("window_days")
        we = p.get("window_end")
        if we is not None:
            we = pd.Timestamp(we)
            we = we.tz_localize("UTC") if we.tzinfo is None else we.tz_convert("UTC")
        self.window_end = we

        # Muss tief genug sein, um sweep_max_age_bars RUECKWAERTS zu suchen,
        # und dabei fuer JEDEN dieser Kandidaten-Bars noch ein eigenes
        # sweep_lookback-Referenzfenster davor zu haben (sonst wird die
        # Sweep-Alter-Suche stillschweigend auf wenige Bars gekappt und
        # findet nie einen bestaetigten Sweep -> Signalzahl faelschlich 0).
        self._window = max(
            self.sweep_lookback + self.sweep_max_age_bars + self.sweep_delay_bars,
            self.cluster_lookback_bars + self.sweep_lookback,
            self.pivot_len * 2 + 5, self.atr_len + 5,
        ) + 20

    def _buffer(self, win: pd.DataFrame) -> float:
        if self.use_atr_buffer:
            a = float(_atr(win, self.atr_len).iloc[-1])
            return a * self.atr_mult if a > 0 else self.tick_size * self.tick_buffer
        return self.tick_size * self.tick_buffer

    def on_bar(self, bars: dict[str, pd.DataFrame], i: int) -> Signal | None:
        df = bars[self.primary_tf]
        min_i = self._window + self.pivot_len
        if i < min_i:
            return None
        ts = df.index[i]

        if self.window_days is not None and self.window_end is not None:
            if ts < self.window_end - pd.Timedelta(days=self.window_days):
                return None

        lo = max(0, i + 1 - self._window)
        win = df.iloc[lo : i + 1]
        highs, lows, closes = win["high"], win["low"], win["close"]

        # --- Pivot (kausal bestaetigt, wie ta.pivothigh/low) ---
        # Kandidaten-Bar ist pivot_len Bars zurueck, Fenster [-2*pivot_len-1:-1]
        # exkl. aktueller Bar (die Bestaetigung braucht pivot_len Bars NACH
        # dem Kandidaten, die aktuelle Bar ist die letzte davon).
        piv_win_h = highs.iloc[-(2 * self.pivot_len + 1) - 1 : -1]
        piv_win_l = lows.iloc[-(2 * self.pivot_len + 1) - 1 : -1]
        last_swing_high = last_swing_low = None
        if len(piv_win_h) == 2 * self.pivot_len + 1:
            cand_h = float(piv_win_h.iloc[self.pivot_len])
            if cand_h == piv_win_h.max():
                last_swing_high = cand_h
            cand_l = float(piv_win_l.iloc[self.pivot_len])
            if cand_l == piv_win_l.min():
                last_swing_low = cand_l
        # Fallback: letzter bestaetigter Pivot ueberhaupt (kausal rueckwaerts
        # gesucht), nicht nur der ggf. gerade an DIESER Bar bestaetigte.
        if last_swing_high is None or last_swing_low is None:
            for j in range(len(win) - self.pivot_len - 1, self.pivot_len, -1):
                seg_h = highs.iloc[j - self.pivot_len : j + self.pivot_len + 1]
                seg_l = lows.iloc[j - self.pivot_len : j + self.pivot_len + 1]
                if last_swing_high is None and float(highs.iloc[j]) == seg_h.max():
                    last_swing_high = float(highs.iloc[j])
                if last_swing_low is None and float(lows.iloc[j]) == seg_l.min():
                    last_swing_low = float(lows.iloc[j])
                if last_swing_high is not None and last_swing_low is not None:
                    break
        if last_swing_high is None or last_swing_low is None:
            return None

        c = float(closes.iloc[-1])
        buf = self._buffer(win)

        # --- Sweep-Erkennung (aktuelle Bar ausgeschlossen aus der Referenz) ---
        prior_lowest = float(lows.iloc[-self.sweep_lookback - 1 : -1].min())
        prior_highest = float(highs.iloc[-self.sweep_lookback - 1 : -1].max())
        is_new_lowest = float(lows.iloc[-1]) < prior_lowest
        is_new_highest = float(highs.iloc[-1]) > prior_highest

        # Sweep-Preis + Alter kausal rueckwaerts suchen (letzter Sweep <= sweep_max_age_bars)
        sweep_price = sweep_age = None
        high_sweep_price = high_sweep_age = None
        for age in range(0, min(self.sweep_max_age_bars, len(win) - self.sweep_lookback - 1) + 1):
            idx = -1 - age
            if -idx + self.sweep_lookback > len(win):
                break
            seg_low = float(lows.iloc[idx - self.sweep_lookback : idx].min()) if idx != -len(win) else None
            if seg_low is not None and float(lows.iloc[idx]) < seg_low and sweep_price is None:
                sweep_price, sweep_age = float(lows.iloc[idx]), age
            seg_high = float(highs.iloc[idx - self.sweep_lookback : idx].max()) if idx != -len(win) else None
            if seg_high is not None and float(highs.iloc[idx]) > seg_high and high_sweep_price is None:
                high_sweep_price, high_sweep_age = float(highs.iloc[idx]), age
            if sweep_price is not None and high_sweep_price is not None:
                break

        same_bar = self.sweep_confirm_mode == "same_bar"
        reclaim_ok = False
        if sweep_price is not None:
            reclaim_ok = (c > sweep_price + buf) if same_bar else \
                (float(closes.iloc[-2]) <= sweep_price + buf < c)
        high_reclaim_ok = False
        if high_sweep_price is not None:
            high_reclaim_ok = (c < high_sweep_price - buf) if same_bar else \
                (float(closes.iloc[-2]) >= high_sweep_price - buf > c)

        sweep_confirmed = sweep_price is not None and sweep_age is not None \
            and sweep_age <= self.sweep_max_age_bars and reclaim_ok
        high_sweep_confirmed = high_sweep_price is not None and high_sweep_age is not None \
            and high_sweep_age <= self.sweep_max_age_bars and high_reclaim_ok

        # --- Cluster-Zaehlung: wie viele der letzten cluster_lookback_bars
        # waren selbst ein "neues Tief/Hoch" (gleiche sweep_lookback-
        # Referenz wie is_new_lowest/is_new_highest oben, NICHT ein
        # verkuerztes lokales Fenster -- sonst zaehlt man etwas anderes
        # als das Original ("isNewLowest"-Events im Cluster-Fenster).
        down_count = up_count = 0
        for age in range(0, self.cluster_lookback_bars):
            idx = -1 - age
            if idx - self.sweep_lookback < -len(win):
                break
            if float(lows.iloc[idx]) < float(lows.iloc[idx - self.sweep_lookback : idx].min()):
                down_count += 1
            if float(highs.iloc[idx]) > float(highs.iloc[idx - self.sweep_lookback : idx].max()):
                up_count += 1
        cluster_down = down_count >= self.min_sweep_cluster
        cluster_up = up_count >= self.min_sweep_cluster

        reclaim_suppress_short = self.use_reclaim_logic and cluster_down and reclaim_ok
        reclaim_suppress_long = self.use_reclaim_logic and cluster_up and high_reclaim_ok

        # --- Sweep-Entry-Delay (blockt Sweep-Bar + N weitere) ---
        bars_since_any_sweep = 0 if (is_new_lowest or is_new_highest) else None
        if bars_since_any_sweep is None:
            for age in range(1, self.sweep_max_age_bars + 5):
                if -1 - age < -len(win):
                    break
                idx = -1 - age
                seg_l = lows.iloc[idx - self.sweep_lookback : idx]
                seg_h = highs.iloc[idx - self.sweep_lookback : idx]
                if len(seg_l) and (float(lows.iloc[idx]) < float(seg_l.min())
                                    or float(highs.iloc[idx]) > float(seg_h.max())):
                    bars_since_any_sweep = age
                    break
        sweep_delay_ok = (not self.use_sweep_entry_delay) or bars_since_any_sweep is None \
            or bars_since_any_sweep > self.sweep_delay_bars

        sweep_gate = sweep_confirmed  # useSweepFilter Default True (nicht parametrisiert, immer an)

        enter_long = (self.use_long and c > last_swing_high and sweep_gate
                      and sweep_delay_ok and not reclaim_suppress_long)
        enter_short = (self.use_short and c < last_swing_low and high_sweep_confirmed
                       and sweep_delay_ok and not reclaim_suppress_short)

        if enter_long:
            direction = 1
            sl = (sweep_price if sweep_price is not None else last_swing_low) - buf
        elif enter_short:
            direction = -1
            sl = (high_sweep_price if high_sweep_price is not None else last_swing_high) + buf
        else:
            return None

        risk = abs(c - sl)
        if risk <= 0:
            return None
        tp = c + direction * risk * self.risk_r

        return Signal(
            time=ts, symbol=self.symbol, direction=direction,
            entry_type="market", entry_price=None,
            stop_loss=sl, take_profit=tp, risk_pct=self.risk_pct,
            meta={"sweep_price": sweep_price, "high_sweep_price": high_sweep_price},
            expires_bars=0,
        )
