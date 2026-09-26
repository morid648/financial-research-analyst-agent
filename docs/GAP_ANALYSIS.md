# Gap Analysis: Smart AI-Based Financial Analyzer

> ⚠️ **Historical planning document (2026-03-22), annotated 2026-09-26.**
> The gaps below were identified at planning time. Most have since been built,
> so each table now carries a **Status today** column checked against the
> current `src/` tree. Items that referred to since-removed parts of the stack —
> the Streamlit `frontend/`, PostgreSQL/SQLAlchemy/Alembic, and Redis — are
> marked *No longer applicable*. See the main [`README.md`](../README.md) for
> what runs today and [`ROOT_CAUSE_ANALYSIS.md`](ROOT_CAUSE_ANALYSIS.md) for
> the accuracy audit.

> **Date**: 2026-03-22 (status column added 2026-09-26)
> **Status**: Planning phase at time of writing; see per-item status below
> **Goal**: Transform from a data aggregation/visualization platform into a truly smart AI-based financial analyzer

---

## Current State Summary

**At the time of writing (2026-03-22)** the project had:

- 10 specialized agents (Orchestrator, Data Collector, Technical, Fundamental, Sentiment, Risk, Thematic, Disruption, Earnings, Dividend)
- 17+ analysis tools covering market data, indicators, metrics, peer comparison, options, backtesting
- 12 Streamlit frontend pages with Bloomberg-inspired dark theme
- 30+ FastAPI endpoints
- Multi-provider LLM support (Ollama, LM Studio, vLLM, Groq, OpenAI, Anthropic)
- Data provider abstraction (YFinanceProvider implemented)
- 5,379 lines of test code

**Today (2026-09-26)**, for comparison:

- 12 agents in `src/agents/` — the 10 above plus Options and Report Generator
- 39 tool modules in `src/tools/`
- No Streamlit app — the UI is static HTML/CSS/JS in `static/`, served by FastAPI
- ~50 API endpoints (the exact count depends on the FastAPI version, see note at the end)
- Four market-data providers (yfinance, FMP, Alpha Vantage, OpenBB) with an optional fallback chain
- 375 tests across 19 files (6,583 lines)

**The main gap (as framed in March)**: The system was a **data aggregation and visualization platform**, not yet a **smart AI analyzer**. The "AI" part needed RAG, predictive models, agentic reasoning, alternative data, and portfolio math. Most of that now exists as tool modules; see the status columns.

---

## Gap Categories

### 1. LLM-Powered Intelligence (The "Smart AI" Gap)

These were described but not assigned a priority in the original plan.

| Gap | Description | State at writing | Status today |
|-----|-------------|------------------|--------------|
| **Rule-based Insight Engine** | `src/tools/insight_engine.py` uses hardcoded rules, not LLM reasoning | No LLM-driven synthesis | ✅ `llm_insight_engine.py` adds LLM synthesis, with the rule-based engine as fallback |
| **No RAG Pipeline** | ChromaDB configured but no document ingestion, embedding, or retrieval for SEC filings, earnings transcripts, or research reports | Infrastructure exists, pipeline missing | ✅ `src/rag/` (ingester, embedder, retriever). Needs ChromaDB + sentence-transformers, so it is not available on the slim Vercel deployment |
| **No Memory/Learning** | Agents don't remember past analyses or track prediction accuracy | Stateless per-request | ⬜ Open — analyses are still not persisted |
| **No Conversational Depth** | AI Advisor chat doesn't maintain context across sessions | Session-only context | ⬜ Open — the Streamlit chat UI it referred to was removed |
| **No Agentic Reasoning Chains** | Agents call tools but don't do multi-step reasoning ("if X worsened, investigate Y") | Single-step tool calling | 🟡 Partial — agents run a tool-calling loop and their prompts direct follow-up investigation; there is no explicit reasoning-chain planner |

### 2. Alternative Data Sources

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **No SEC/EDGAR Filings** | 10-K, 10-Q, 8-K parsing for fundamental analysis | P0 | ✅ `src/rag/ingester.py` pulls filings from SEC EDGAR |
| **No Earnings Call Transcripts** | NLP on management commentary (tone, guidance language) | P0 | 🟡 Partial — transcripts can be ingested into RAG; no dedicated tone/guidance NLP |
| **No Social Media Sentiment** | Reddit (r/wallstreetbets), Twitter/X, StockTwits | P1 | ✅ `social_sentiment.py` |
| **No Macroeconomic Data** | Fed rates, CPI, GDP, unemployment (FRED API) | P1 | ✅ `macro_data.py` (FRED) |
| **No Institutional Flow Data** | 13F filings, dark pool activity | P2 | 🟡 Partial — institutional holdings and insider (Form 4) activity in `insider_activity.py`; no dark-pool data |
| **No Supply Chain Analysis** | Supplier/customer relationship mapping | P3 | ✅ `supply_chain.py` |

### 3. Predictive & Quantitative Models

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **No ML Price Prediction** | No time-series forecasting (LSTM, Prophet, ARIMA) | P1 | ✅ `ml_forecast.py` — scikit-learn gradient boosting on engineered features (not LSTM/Prophet/ARIMA) |
| **No Anomaly Detection** | No unusual volume/price movement detection | P1 | ✅ `anomaly_detector.py` (Z-score and regime-change methods) |
| **No Factor Modeling** | No Fama-French, momentum, or quality factor exposure | P2 | ✅ `factor_model.py` |
| **No Monte Carlo Simulation** | Missing despite having risk analysis | P2 | ✅ `monte_carlo.py` |
| **No Correlation Regime Detection** | Static correlation matrix, no regime-switching models | P3 | 🟡 Partial — volatility/trend/volume regime changes are detected; no regime-switching correlation model |
| **No DCF Model** | Fundamental agent mentions DCF but no actual implementation | P1 | ✅ `dcf_model.py` and `market_data.get_company_dcf_profile()`, with the interactive `/dcf` page |

### 4. Portfolio Intelligence

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **No Portfolio Optimization** | No mean-variance, efficient frontier, or Black-Litterman | P1 | ✅ `portfolio_optimizer.py` (max Sharpe, min volatility, risk parity) |
| **No Rebalancing Suggestions** | No target allocation vs actual drift detection | P2 | ✅ In `portfolio_optimizer.py` |
| **No Tax-Loss Harvesting** | No tax-aware recommendations | P3 | ✅ `tax_loss_harvesting.py` |
| **No Benchmark Comparison** | No alpha/beta vs S&P 500 over time | P1 | ✅ `benchmark.py` |
| **No Position Sizing** | No Kelly criterion or risk-parity allocation | P2 | 🟡 Partial — risk-parity allocation exists; no Kelly criterion |

### 5. Backtesting & Strategy

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **Basic Backtesting** | Only 3 strategies (RSI, MACD, SMA), no walk-forward analysis | P2 | ✅ More strategies in `strategy_definitions.py`; walk-forward analysis in `backtesting_engine.py` |
| **No Strategy Optimization** | No parameter sweep or genetic optimization | P3 | ✅ `strategy_optimizer.py` |
| **No Multi-Asset Strategies** | Single-stock only | P2 | ✅ Multi-asset backtest in `backtesting_engine.py` |
| **No Performance Attribution** | No Brinson attribution | P3 | ✅ `brinson_attribution.py` |

### 6. Report & Export Quality

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **PDF Generation ~75%** | ReportGenerator references PDF but not fully integrated | P2 | ✅ `report_export.py` (reportlab) |
| **No Scheduled Reports** | No automated daily/weekly email digests | P3 | ✅ `scheduled_reports.py` (SMTP email digests) |
| **No Excel Export** | Analysts need spreadsheet exports | P2 | ✅ `report_export.py` (openpyxl) |
| **No Shareable Report Links** | No report persistence or sharing | P3 | ⬜ Open |

### 7. Data Reliability & Quality

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **Single Data Source** | Everything relies on yfinance (rate limits, missing data, delays) | P0 | ✅ yfinance, FMP, Alpha Vantage, and OpenBB providers in `src/data/` |
| **No Data Validation** | No checks for stale data, missing fields, or outliers | P1 | ✅ `src/data/validator.py` |
| **No Fallback Chain** | Provider abstraction exists but only YFinanceProvider implemented | P0 | ✅ `MultiProvider` via `DATA_FALLBACK_PROVIDER` |
| **Sample Data Fallback** | News fetcher returns hardcoded sample news when API fails | P1 | ⬜ Open — still on by default (`NEWS_FALLBACK_SAMPLE=true`) |

### 8. Real-Time & Streaming Data

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **No WebSocket/Streaming** | All data is request-response with cache TTLs | P3 (deferred) | 🟡 Partial — one WebSocket endpoint, `/ws/alerts`; market data is still request-response |
| **No Real-Time Alerts** | No price alerts, volume spikes, breaking news notifications | P3 (deferred) | ✅ `alerts.py`, pushed over `/ws/alerts` |
| **No Intraday Tick Data** | Only daily/periodic historical data | P3 (deferred) | ⬜ Open |

> **Note**: Third-party streaming integrations (Polygon.io, Alpaca, IEX Cloud) are deferred to a later stage.

### 9. Security & Production Readiness

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **No Authentication** | API has no auth/API keys | P2 | ⬜ Open |
| **No Rate Limiting** | Configured but not applied to routes | P2 | ⬜ Open — settings exist in `config.py`, still not enforced |
| **No Audit Logging** | No tracking of who analyzed what | P3 | ⬜ Open |
| **No Data Encryption** | Sensitive portfolio data in plain SQLite | P3 | ➖ No longer applicable — the database layer was removed; nothing is persisted |
| **Missing ORM Models** | Alembic configured but no models for persisting analyses | P2 | ➖ No longer applicable — SQLAlchemy/Alembic were removed |

### 10. User Experience Gaps

| Gap | Description | Priority | Status today |
|-----|-------------|----------|--------------|
| **No Watchlist Persistence** | Resets each session | P2 | ⬜ Open (`/api/v1/shorts/watchlist` is a short-squeeze screen, not a user watchlist) |
| **No User Accounts** | No ability to save and track portfolios over time | P2 | ⬜ Open |
| **No Overlay Charts** | Can compare metrics but no overlaid price charts | P2 | ⬜ Open |
| **No Mobile Responsiveness** | Streamlit default isn't mobile-optimized | P3 | ➖ No longer applicable — Streamlit was replaced by the static web UI |

---

## Priority Summary

Counts below are taken directly from the tables above. The original summary
listed 5 / 10 / 12 / 10 (37 items); that did not match its own tables, and it
counted RAG and agentic reasoning as P0 even though section 1 assigned them no
priority.

| Priority | Count | Focus Area | Status today |
|----------|-------|------------|--------------|
| **P0** | 4 | SEC filings, earnings transcripts, multi-source data, provider fallback | 3 done, 1 partial |
| **P1** | 9 | Social sentiment, macro data, ML forecasting, anomaly detection, DCF, portfolio optimization, benchmarking, data validation, sample-news fallback | 8 done, 1 open |
| **P2** | 15 | Institutional flow, factors, Monte Carlo, rebalancing, position sizing, backtesting, multi-asset, PDF/Excel, auth, rate limiting, ORM, watchlist, accounts, overlay charts | 7 done, 2 partial, 5 open, 1 no longer applicable |
| **P3** | 13 | Supply chain, correlation regimes, tax-loss, strategy optimization, attribution, scheduled reports, share links, streaming, alerts, intraday, audit logs, encryption, mobile | 6 done, 2 partial, 3 open, 2 no longer applicable |
| *Unprioritized* | 5 | Section 1: LLM insight, RAG, memory, conversation, reasoning chains | 2 done, 1 partial, 2 open |

> **Endpoint-count note**: several routes in `src/api/routes.py` are declared
> *after* `app.include_router(router)`. FastAPI ≥ 0.141 still serves them;
> older FastAPI versions silently drop them. On FastAPI 0.136 the OpenAPI
> schema lists 48 paths; on 0.141 it lists 64.
