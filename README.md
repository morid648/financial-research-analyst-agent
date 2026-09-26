# FinResearch

**Equity fundamentals, a DCF model, and risk metrics for any listed company — computed from real filings and price history, not templated placeholders.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational)](LICENSE)
[![Tests](https://github.com/morid648/financial-research-analyst-agent/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)

**[Live pages](#run-it) once running:** Overview · Ratios · DCF model · Dashboard · About

---

## What it does

Type a ticker — `AAPL`, `TCS`, `RELIANCE.NS` — and get:

- **Sixteen financial ratios** (valuation, returns, solvency, cash flow), each computed from the company's actual balance sheet and income statement, not a lookup table. Where a company doesn't report what's needed, the ratio shows `N/A` instead of guessing.
- **A discounted cash flow model** you can see and adjust line by line: five-year free cash flow projection, WACC via CAPM, an enterprise-to-equity bridge, and a bear/base/bull sensitivity grid. D&A, capex and working-capital assumptions are pulled from the company's own trailing cash flow statement, not a fixed industry guess.
- **Historical risk**: annualized volatility, 95% historical VaR, and Sharpe ratio from a year of actual daily returns — not a canned "Moderate Risk" badge.
- **News sentiment**: recent headlines scored individually with FinBERT (a finance-domain transformer model), aggregated into a signal you can trace back to each article.

Everything above is computed fresh on each request from live market data. Nothing on these pages is a static fixture.

## Why this repo is worth a look

This started as a fairly typical "AI agent" portfolio project and, over the course of a real debugging pass, turned into something more interesting: **a documented audit that found and fixed 17 genuine accuracy bugs** — a crash that silently zeroed out every DCF valuation, four ratios that were hardcoded strings dressed up as calculations, a 100x unit-conversion error, a dashboard whose headline numbers were disconnected from the ticker you searched. The full writeup, with root cause, fix, and verification for each one, is in **[`docs/ROOT_CAUSE_ANALYSIS.md`](docs/ROOT_CAUSE_ANALYSIS.md)**.

A second pass then went the other direction — a repo-wide audit for *over-engineering* — and deleted an orphaned Streamlit dashboard, an unused SQLAlchemy persistence layer, dead auth middleware, an unused Redis dependency, and an unreferenced mixin class. Roughly 10,000 lines and three dependencies removed with zero functional change, verified by re-testing every page afterward.

If you're evaluating this as a portfolio piece: the interesting part isn't the feature count, it's that both passes are written down, and every claim in this README is something that was actually run and checked, not something that sounded plausible.

## Run it

```bash
git clone https://github.com/morid648/financial-research-analyst-agent.git
cd financial-research-analyst-agent
pip install -r requirements.txt
python -m src.main api
```

Open **http://localhost:8000**. No API key required — pricing and statements come from Yahoo Finance via `yfinance`, and news sentiment runs locally via FinBERT (downloads once on first use, then cached). Works for NSE, BSE and US tickers.

```bash
# or with Docker
docker compose up -d
```

### Quick API check

```bash
curl "http://localhost:8000/api/v1/quote/AAPL"
curl "http://localhost:8000/api/v1/ratios/RELIANCE.NS"
curl "http://localhost:8000/api/v1/dcf/AAPL"
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "TCS.NS"}'
```

Interactive docs at [`/docs`](http://localhost:8000/docs) (Swagger) or [`/redoc`](http://localhost:8000/redoc).

## Pages

| Page | What it shows |
|---|---|
| **Overview** (`/`) | Live quote, 10-session chart, a rule-based signal, and headline valuation/profitability/leverage figures |
| **Ratios** (`/ratios`) | All 16 ratios, grouped into four themes, each with a plain-language explanation and a data-confidence score |
| **DCF model** (`/dcf`) | The full five-year cash flow build, WACC breakdown, enterprise-to-equity bridge, and a bear/base/bull sensitivity grid you can drag |
| **Dashboard** (`/dashboard/`) | RSI/MACD technicals, a year of price history, historical VaR and Sharpe ratio, and per-article scored news |
| **About** (`/about`) | A plain-English glossary of every term and formula used on the site — written for someone with no finance background |

Every number is traceable: the About page explains the formula, the DCF page shows every intermediate step, and the Ratios page tells you outright when a figure isn't available rather than filling in a plausible-looking guess.

## Architecture

```
Browser  ──►  FastAPI (src/api/routes.py)  ──►  Data provider  ──►  Yahoo Finance
                     │                              (src/data/, swappable:
                     │                               FMP / Alpha Vantage / OpenBB)
                     ├─► src/tools/market_data.py      ratios, DCF, quote
                     ├─► src/tools/technical_indicators.py  RSI, MACD, moving averages
                     ├─► src/tools/sentiment_engine.py  FinBERT / VADER news scoring
                     └─► src/tools/news_impact.py       headline aggregation

static/*.html + vanilla JS  ──►  same REST API, no build step
```

The four pages and their REST endpoints (`/api/v1/quote`, `/ratios`, `/dcf`, `/history`, `/analyze`) run standalone — no LLM, no API keys, no database. That's the part this README makes claims about, because it's the part that's been tested end to end.

**A separate, larger layer** (`src/agents/`, `src/rag/`) implements a LangChain-based multi-agent system — specialized agents for technicals, fundamentals, sentiment, risk, thematic investing, disruption analysis, and more, each exposed as its own tool in `src/tools/` (40+ modules: Monte Carlo simulation, portfolio optimization, backtesting, factor models, SEC filing retrieval via RAG, and others). It requires an LLM provider (Ollama locally, or OpenAI/Anthropic/Groq) to orchestrate. This layer is real and substantial, but wasn't part of this session's verification pass — treat it as an extension point rather than a tested surface. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how it's wired.

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI, Pydantic |
| Market data | `yfinance` (default), with Financial Modeling Prep / Alpha Vantage / OpenBB as swappable providers |
| Sentiment | FinBERT (`transformers`), VADER fallback |
| Numerics | NumPy, pandas |
| Frontend | Static HTML + vanilla JS, Chart.js — no build step, no framework |
| Agent layer (optional) | LangChain / LangGraph, ChromaDB for RAG, `sentence-transformers` for embeddings |

## Project structure

```
src/
├── main.py, cli.py           # entry points
├── config.py                 # typed settings (pydantic-settings)
├── api/
│   ├── routes.py              # all REST endpoints
│   └── schemas.py             # request/response models
├── tools/                    # ~40 standalone analysis functions
│   ├── market_data.py          # quote, ratios, DCF
│   ├── technical_indicators.py # RSI, MACD, moving averages
│   ├── sentiment_engine.py     # FinBERT / VADER
│   └── ...                     # portfolio optimization, backtesting, macro data, etc.
├── agents/                   # LangChain multi-agent layer (requires an LLM)
├── data/                     # provider abstraction (yfinance / FMP / Alpha Vantage / OpenBB)
├── rag/                      # SEC filing retrieval for the agent layer
└── models/                   # Pydantic data models

static/                       # the 5 pages above — plain HTML/CSS/JS
docs/
├── ROOT_CAUSE_ANALYSIS.md     # the 17-bug audit — start here
├── ARCHITECTURE.md            # system design notes
└── ...
tests/
config/agents.yaml            # agent tuning (indicator params, recommendation weights)
```

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html
```

## Configuration

Copy `.env.example` to `.env`. Nothing is required to run the four core pages — `DATA_PROVIDER` defaults to `yfinance`, which needs no key. Everything else (LLM provider, alternate data providers, FRED, Reddit) is optional and only used by the agent layer.

## Known limitations

- Ratios and the DCF depend entirely on what a company reports; small-caps and banks will show more `N/A` values, by design (see the data-confidence score on the Ratios page).
- The "signal" shown on the Overview and Dashboard pages is a simple, disclosed rule (P/E + price direction, or RSI + MACD) — not a model prediction. It's labeled as such on the page.
- FinBERT takes 10–90 seconds to load into memory on the first request after a server restart; subsequent requests are fast.
- The full list of open items from the accuracy audit — what's fixed vs. what's a known, documented gap — is in [`docs/ROOT_CAUSE_ANALYSIS.md`](docs/ROOT_CAUSE_ANALYSIS.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues and PRs welcome — this is a learning project and reviews are genuinely useful.

## License

[MIT](LICENSE)

---

**Built by:**
- [Anshul Chaudhary](https://github.com/morid648)
- [LinkedIn Profile](https://www.linkedin.com/in/anshul-chaudhary-508138308/)

---

*For research and education. Not investment advice.*

