# Plan: Top-5 Trading-Strategien → Python-Bots für MT5 (pymt5trade)

## Anforderungen (User-Briefing 2026-09-04)
- Recherche öffentlich dokumentierter Strategien (ORB, SMC/ICT, News/SEC-Analyse, KI/Chronos, klassische Indikatoren u.v.m.)
- Top-5-Auswahl, implementiert als eigenständige Python-Bots für MT5 unter Wine via pymt5trade
- Instrumente: XAUUSD, NAS100, Forex Majors (EURUSD, GBPUSD, USDJPY, USDCHF), Gold-nahe (AUDUSD, USDCAD, NZDUSD), Crosses (EURJPY, GBPJPY)
- Ziel: PF > 1.5, min. 1:2 RR
- Prop-Firm-Profil: 0,5 % Risiko/Trade, max. 10 % DD, EOD-Drawdown-Tracking, konfigurierbare Limits (Daily Loss / Overall Loss / Profit Target)
- Validierung: Backtest (MT5-Historie via pymt5trade) + Walk-Forward/Out-of-Sample → Demo-Live-Gate
- Ressourcen: nur freie Daten/APIs, lokale LLMs (Qwen3) / Kimi bevorzugt
- Timeframes: M5, M15, H1, H4 (Recherche entscheidet Zuordnung)
- Deployment später; Fokus auf Entwicklung + Backtest
- **KORREKTUR (User):** MT5-Anbindung = **pymt5linux** (RPyC-Bridge: MT5 + Windows-Python unter Wine, natives Linux-Python via RPyC). Kritisch: `rpyc==5.3.1` beidseitig pinnen (5.x/6.x wire-inkompatibel), `numpy<2.0`, MT5-Setting "Max bars in chart" auf Unlimited für Historie.

## Phase 1 — Deep Research (Skill: deep-research-swarm)
Breite Recherche öffentlich dokumentierter Trading-Strategien, gegliedert in parallele Stränge:
1. **Intraday/Session-Strategien**: ORB (Opening Range Breakout), London/NY-Session-Breakouts, ICT Killzones, Silver Bullet
2. **Smart Money / Price Action**: SMC, Order Blocks, FVG, Liquidity Sweeps, Market Structure (BOS/CHoCH), Supply/Demand
3. **Indikator-/Trend-/Mean-Reversion**: EMA/ADX/Supertrend-Trendfolge, RSI/Bollinger-Reversion, Donchian/Turtle, VWAP-Strategien
4. **News-/Event-/Sentiment**: News-Trading (ForexFactory-Kalender), SEC-Filing-Analyse (13F, 8-K, Insider), Sentiment-Strategien
5. **KI/ML-Strategien**: Chronos/TimesFM-Forecasting, LLM-gestützte Analyse (lokal: Qwen3), ML-Klassifikatoren für Regime/Signale
- Für jede Strategie: Regelwerk, dokumentierte Performance-Claims, bekannte Schwächen, Overfitting-Risiken, Eignung pro Instrument (XAUUSD/NAS100/Forex) und Timeframe
- Cross-Validierung der Claims; Output: strukturierter Research-Brief je Strang

## Phase 2 — Auswahl & Spezifikation (Stage-Gate)
- Scoring-Matrix: erwartete Robustheit, Kompatibilität mit Prop-Regeln (EOD-DD!), Instrumenten-Fit, Implementierbarkeit mit freien Daten, Diversifikation untereinander
- Auswahl Top 5 (verschiedene Strategien dürfen auf verschiedene Instrumente optimiert sein)
- Pro ausgewählter Strategie: vollständige Regel-Spezifikation (Entry/Exit/Filter/Risiko), Parameter-Räume, Timeframe-/Symbol-Zuordnung
- Gate: Spezifikationen müssen vollständig und eindeutig sein, bevor implementiert wird

## Phase 3 — Implementierung (Skill: vibecoding-general-swarm)
- Gemeinsames Framework: Datenabruf via pymt5trade/MT5, Backtester mit realistischen Kosten (Spread/Slippage/Kommission), Risiko-Engine (0,5 %/Trade, 1:2 RR min, EOD-DD-Tracker, konfigurierbare Prop-Limits), einheitliches Reporting (PF, DD, Sharpe, Trade-Stats)
- 5 Bot-Module (je Strategie ein Bot), parallel implementiert
- Je Bot: Backtest-Modus + Live-Modus (Demo) mit gleichem Signal-Code
- Output: Code-Repo unter /mnt/agents/output/

## Phase 4 — Backtest & Walk-Forward (Stage-Gate)
- Backtests auf MT5-Historiendaten: In-Sample / Out-of-Sample-Split, Walk-Forward-Analyse
- Overfitting-Checks: Parameter-Stabilität, Monte-Carlo/Trade-Shuffling wo sinnvoll
- Gate: Nur Strategien mit OOS-PF > 1.5 (Ziel) gehen in Demo-Phase; sonst Iteration (Parameter/Filter/Strategie-Tausch)

## Phase 5 — Demo-Live-Gate & Delivery
- Live-Modus gegen Demo-Account, EOD-DD-Überwachung, Logging
- Abschluss-Report: Strategie-Vergleich, PF/DD/RR je Instrument, Empfehlung für Prop-Einsatz
- Deliverables: Code-Repo + Research-Report (md)
