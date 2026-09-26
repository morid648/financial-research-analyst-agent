# 📚 Financial Research Analyst Agent - Beginner's Onboarding Guide

**Welcome to the Financial Research Analyst Agent project!** 🚀

This guide is written for engineers with **minimal knowledge** of the project. We'll explain everything from the ground up, including concepts, architecture, and how to contribute.

---

## 🎯 Quick Overview (1 Minute Read)

**What is this project?**

Imagine you want to invest in a stock like Apple (AAPL). Normally, you'd:

1. Check the current price 📊
2. Read charts and technical patterns 📈
3. Research the company's earnings and debt 💼
4. Read news about the company 📰
5. Calculate the investment risk ⚠️
6. Make a decision

**This project automates all of that using AI!** 🤖

There are **two ways** to ask it about a stock, and they work differently:

| | REST API (`POST /api/v1/analyze`) | AI agent pipeline (Python / CLI) |
|---|---|---|
| How | Calls the analysis tools directly | 11 LLM-powered agents coordinated by an orchestrator |
| Recommendation | A fixed RSI + MACD rule (BUY / SELL / HOLD) | Weighted composite of technical, fundamental, sentiment, and risk scores |
| Needs an LLM? | No | Yes (Ollama, Groq, OpenAI, …) |
| Used by | The web UI and API clients | `FinancialResearchAgent`, `python -m src.cli analyze` |

A response from the REST API looks like this (numbers are illustrative):

```
✅ Recommendation: HOLD        (rule: BUY if RSI < 30 and MACD rising,
📊 Confidence: 50%              SELL if RSI > 70 and MACD falling, else HOLD)

Technical: RSI 58.3, MACD, moving averages     (computed from 1 year of prices)
Fundamental: company profile + price data
Sentiment: news headlines scored by FinBERT (with fallbacks)
Risk: annual volatility, 95% VaR, Sharpe ratio  (from real daily returns)
```

The system does the data gathering and the calculations automatically.

---

## 📚 Before You Start: Key Concepts Explained

If you're new to programming or finance, here are the essential concepts:

### What is an "Agent"?

An **agent** is like a **specialized worker** with expertise in one area:

```
Imagine a law firm with different lawyers:
- Criminal Lawyer → specializes in criminal cases
- Tax Lawyer → specializes in taxes
- Family Lawyer → specializes in family matters

Similarly, this system has different agents:
- DataCollector Agent → fetches data
- TechnicalAnalyst Agent → analyzes charts
- FundamentalAnalyst Agent → analyzes company finances
```

Each agent:

- ✅ Has ONE specific job
- ✅ Uses an AI model (LLM) to reason
- ✅ Can call tools to get data
- ✅ Returns results in a structured format

### What is an "LLM"?

**LLM** = Large Language Model (like ChatGPT)

It's an AI that can:

- Understand text
- Reason about problems
- Make decisions
- Explain reasoning

In this project, each agent uses an LLM to analyze data and make recommendations.

**Example:**

```
Agent: "Here's the stock data. RSI is 35, MACD is positive, price is at support."
LLM: "This signals a potential BOTTOM. The momentum indicators suggest
      a BULLISH trend. Recommendation: BUY with confidence 0.75"
```

### What is a "Tool"?

A **tool** is a function that an agent can call to get work done:

```
Analogy:
- A carpenter has tools: hammer, saw, drill
- An agent has tools: get_stock_price, calculate_rsi, fetch_news

When agent needs data, it calls the appropriate tool:
Agent: "I need Apple's stock price"
Tool: Calls Yahoo Finance API → Returns $185.50
```

### What is "Asynchronous" Execution?

**Synchronous** = Things happen one after another (slow)

```
Task 1: Download Apple data     (2 seconds)
Task 2: Calculate technicals    (2 seconds)
Task 3: Analyze fundamentals    (2 seconds)
Task 4: Check sentiment         (2 seconds)
Total: 8 seconds ❌ Too slow!
```

**Asynchronous** = Things happen in parallel (fast)

```
Task 1 ──┐
Task 2 ──┼─→ All at same time → 2 seconds ✅ Much faster!
Task 3 ──┤
Task 4 ──┘
```

This project uses **asynchronous execution** to run all agents in parallel, so analysis is fast.

---

## 🏗️ Architecture Explained Simply

### The Big Picture: A Restaurant Analogy

Imagine a restaurant with different roles:

```
CUSTOMER (You)
    │
    ↓
HEAD CHEF (Orchestrator Agent)
    │
    "I need a complete meal analysis"
    │
    ├─→ SOUS CHEF 1 (Data Collector)  → Gets ingredients
    ├─→ SOUS CHEF 2 (Technical)       → Checks quality
    ├─→ SOUS CHEF 3 (Fundamental)     → Analyzes nutrition
    ├─→ SOUS CHEF 4 (Sentiment)       → Taste test
    ├─→ SOUS CHEF 5 (Risk)            → Checks allergens
    │
    All work in parallel (fast! ⚡)
    │
    ↓
HEAD CHEF combines everything → Final dish
    │
    ↓
CUSTOMER gets final result
```

### The Technical Version

```
 PATH A — REST API / web UI                PATH B — AI agent pipeline
 ─────────────────────────                 ──────────────────────────
 POST /api/v1/analyze                      FinancialResearchAgent().analyze("AAPL")
        │                                  (Python, or: python -m src.cli analyze AAPL)
        ▼                                          │
 src/api/routes.py::analyze_stock                  ▼
   ├─ get_stock_price()                     OrchestratorAgent
   ├─ get_historical_data()                   1. DataCollector (runs first)
   ├─ calculate_rsi / macd / MAs              2. In parallel (asyncio.gather):
   ├─ get_company_info()                         Technical · Fundamental ·
   ├─ _compute_sentiment()  (FinBERT)            Sentiment · Risk
   ├─ _compute_risk_metrics()                 3. Confidence check (flags low scores)
   └─ RSI + MACD rule → BUY / SELL / HOLD     4. ReportGenerator → weighted
        │                                        composite → recommendation
        ▼                                          │
 JSON response (no LLM involved)                   ▼
                                           Result dict / report (LLM reasoning)
```

The REST API never calls `FinancialResearchAgent`. A few endpoints
(`/theme/{id}`, `/disruption/analyze`, `/earnings/analyze`, and their
`/compare` variants) can *optionally* ask a single agent for an LLM-written
narrative when you pass `include_narrative: true`.

---

## 🔧 Key Components Explained

### 1. **Agents** - The Specialists

**Location**: `src/agents/`

Think of agents as **specialized consultants**:

#### BaseAgent (`base.py`)

- **What it is**: The foundation/blueprint for all agents
- **What it does**: Handles common tasks like:
  - Setting up the AI model (LLM)
  - Managing state (what's it doing?)
  - Logging errors
  - Returning results

**Simple analogy**: Like a template for hiring consultants

```
Template:
- Name of consultant
- Area of expertise
- Tools available
- How to track progress
- How to report results

All specific consultants follow this template.
```

#### Specialized Agents

| Agent Name | Real-World Job | What It Does |
|---|---|---|
| **DataCollector** | Data Analyst | Fetches stock prices, company info, historical data from APIs |
| **TechnicalAnalyst** | Chart Analyst | Reads charts, calculates RSI, MACD, moving averages |
| **FundamentalAnalyst** | Financial Analyst | Analyzes P/E ratio, earnings, debt, cash flow |
| **SentimentAnalyst** | News Analyst | Reads news articles, determines if they're positive/negative |
| **RiskAnalyst** | Risk Manager | Calculates volatility, Value at Risk, correlation |
| **ReportGenerator** | Report Writer | Combines all findings into a coherent recommendation |
| **OrchestratorAgent** | Project Manager | Coordinates all other agents, manages workflow |
| **Thematic / Disruption / Earnings / Dividend / Options** | Specialist analysts | Theme exposure, disruption profile, earnings quality, dividend safety, options flow |

### 2. **Tools** - The Instruments

**Location**: `src/tools/`

Tools are **functions** agents can call to get things done:

```
Think of it like a hospital:

Agent = Doctor
Tools = Medical instruments

Doctor says: "I need patient's blood pressure"
Tool: Blood pressure machine → Returns 120/80

Doctor says: "I need stock price"
Tool: Yahoo Finance API → Returns $185.50

Doctor says: "I need to calculate RSI"
Tool: RSI calculator function → Returns 58.3
```

**Example Tool Code** (simplified):

```python
@tool
def get_stock_price(symbol: str) -> float:
    """Get current stock price"""
    # Calls Yahoo Finance
    return fetch_from_yahoo_finance(symbol)

# Agent can now call this automatically when needed
```

### 3. **API Layer** - The Front Door

**Location**: `src/api/`

This is how external users communicate with the system:

```
User's perspective:
"I want to analyze AAPL"
    ↓
Makes HTTP request to API
    ↓
API processes it
    ↓
Gets result back
```

**Available APIs**:

- `POST /api/v1/analyze` → Analyze a stock (real indicators, risk, and news sentiment; rule-based recommendation)
- `GET /api/v1/technical/AAPL` → Just the technical indicators
- `GET /api/v1/ratios/AAPL`, `GET /api/v1/dcf/AAPL` → 16-metric ratios profile, DCF valuation
- `GET /health` → Check if the system is working (note: no `/api/v1` prefix)
- `GET /docs` → Interactive list of every endpoint

> ⚠️ Four endpoints are still **placeholders** that return the same values for
> every input: `GET /api/v1/sentiment/{symbol}` (always "positive", 0.65),
> `GET /api/v1/market/summary` (fixed index prices), `POST /api/v1/portfolio`
> (fixed diversification score and advice), and `POST /api/v1/reports` (a stub
> report). Use `/analyze` for real sentiment. See the "Still Open" section of
> `docs/ROOT_CAUSE_ANALYSIS.md`.

### 4. **Configuration** - The Settings

**Location**: `src/config.py` and `.env` file

This is where you configure **settings**:

```
What LLM to use? (OpenAI? Ollama? Local?)
What temperature? (0 = deterministic, 1 = creative)
Which market-data provider? (yfinance, FMP, Alpha Vantage, OpenBB)
What API keys? (OpenAI, NewsAPI, etc.)
```

It's like **game settings** in a video game - configure how the system behaves.

---

## 🔄 How It Works: Request Flow (Step by Step)

Let's walk through exactly what happens when someone analyzes a stock.

### User Request

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "analysis_type": "comprehensive"
  }'
```

**Translation**: "Please analyze Apple stock comprehensively"

---

### Step-by-Step Execution

#### **Step 1: API Route Receives Request**

```
File: src/api/routes.py (line ~175)

@app.post("/api/v1/analyze")
async def analyze_stock(request: AnalysisRequest):
    # FastAPI automatically validates the request
    # Checks: Is symbol provided? Is analysis_type valid?

    # If validation passes, continue
    print(f"Analyzing {request.symbol}...")
```

**Why this step?** To make sure the request is valid before wasting resources.

---

#### **Step 2: Fetch Market Data**

```
File: src/api/routes.py::analyze_stock

price_data = get_stock_price("AAPL")                 # current price
hist_data  = get_historical_data("AAPL", "1y")       # a year of closes + returns
company    = get_company_info("AAPL")                # sector, market cap, …
```

These are plain tool functions from `src/tools/market_data.py`, which read
through the configured data provider (`DATA_PROVIDER`, default yfinance).
**No agent and no LLM is involved in this path.**

---

#### **Step 3: Compute Indicators, Risk, and Sentiment**

```
technical = {
    "rsi": calculate_rsi(closes),
    "macd": calculate_macd(closes),
    "moving_averages": calculate_moving_averages(closes),
}
risk      = _compute_risk_metrics(hist_data["returns"])  # volatility, VaR 95%, Sharpe
sentiment = _compute_sentiment("AAPL")                    # FinBERT-scored headlines
```

Sentiment uses FinBERT, a ~440 MB model. The **first** request after starting
the server can take 10–90 seconds while it loads; later requests are fast.
(On the Vercel deployment FinBERT isn't installed, so a lighter fallback is used.)

---

#### **Step 4: Apply the Recommendation Rule**

```
if rsi < 30 and macd_histogram > 0:   recommendation, confidence = "BUY", 0.75
elif rsi > 70 and macd_histogram < 0: recommendation, confidence = "SELL", 0.75
else:                                 recommendation, confidence = "HOLD", 0.50
```

This is a simple, transparent rule — not an AI vote.

---

#### **Step 5: Response Sent Back to User**

```json
{
  "symbol": "AAPL",
  "analysis_type": "comprehensive",
  "current_price": 185.50,
  "recommendation": "HOLD",
  "confidence": 0.5,
  "summary": "AAPL is currently trading at $185.50. Technical indicators suggest a HOLD signal with 50% confidence.",
  "technical": {"rsi": {...}, "macd": {...}, "moving_averages": {...}},
  "fundamental": {"company": {...}, "price_data": {...}},
  "sentiment": {"score": 0.21, "label": "Positive", "engine": "finbert", ...},
  "risk": {"annual_volatility_pct": 24.5, "var_95_daily_pct": -2.0, "sharpe_ratio": 1.3, "volatility": "Medium"},
  "execution_time_seconds": 2.5
}
```

(Values are illustrative.)

---

### The Other Path: The AI Agent Pipeline

When you run `FinancialResearchAgent().analyze("AAPL")` from Python, or
`python -m src.cli analyze AAPL`, the multi-agent system runs instead:

```
File: src/agents/orchestrator.py::OrchestratorAgent.analyze

1. data_result = await data_collector.collect_comprehensive_data(symbol)  # first, on its own

2. results = await asyncio.gather(                              # then 4 in parallel
       technical_analyst.analyze_stock(...),
       fundamental_analyst.analyze_company(...),
       sentiment_analyst.analyze_sentiment(...),
       risk_analyst.analyze_risk(...),
   )

3. Confidence check: any analyst with confidence below 0.4 is flagged in
   results["confidence_warnings"]

4. report = await report_generator.generate_report(symbol, results)
```

The report generator blends the four scores with the weights in
`config/agents.yaml`:

```
composite = technical × 0.25 + fundamental × 0.35 + sentiment × 0.20 + (1 − risk) × 0.20

≥ 0.80 Strong Buy · ≥ 0.65 Buy · ≥ 0.45 Hold · ≥ 0.30 Sell · below that Strong Sell
```

Each analyst is an LLM agent that decides which tools to call, so this path
needs a working LLM provider and is much slower than the REST API.

---

## 🚀 Getting Started: Baby Steps

### Prerequisites (What You Need)

1. **Python 3.11+** - Programming language
   - Check: `python --version`
   - Download: [python.org](https://www.python.org)

2. **pip** - Package manager (comes with Python)
   - Check: `pip --version`

3. **Ollama** (Optional) - Local AI model
   - Why? To run the AI locally without paying for API calls
   - Download: [ollama.ai](https://ollama.ai)

4. **API Key** (Optional) - If using cloud LLM
   - OpenAI: [openai.com](https://openai.com)
   - Groq: [groq.com](https://groq.com)

**Estimated Time**: 15-20 minutes for full setup

---

### Installation Guide

#### Step 1: Clone the Repository (2 minutes)

```bash
# Copy-paste this into terminal

git clone https://github.com/morid648/financial-research-analyst-agent.git
cd financial-research-analyst-agent
```

**What happened?**

- Downloaded the project code
- Navigated into the project folder

#### Step 2: Create Virtual Environment (1 minute)

```bash
# Virtual environment = isolated Python workspace
# (Like a separate folder for this project's dependencies)

python -m venv venv
```

**On Mac/Linux:**

```bash
source venv/bin/activate
```

**On Windows:**

```bash
venv\Scripts\activate
```

**How to know it worked?** Your terminal should show `(venv)` at the start.

#### Step 3: Install Dependencies (3-5 minutes)

```bash
# Install all required Python packages
pip install -r requirements.txt
```

**What's happening?**

- Reading `requirements.txt` (list of packages needed)
- Downloading and installing each package
- This includes: FastAPI, LangChain, Pydantic, etc.

#### Step 4: Configure Environment (2 minutes)

```bash
# Copy the example config to create your own
cp .env.example .env

# Open .env in your editor and review settings
# (Usually already configured for local Ollama, which is free!)
```

**What's in .env?**

```
LLM_PROVIDER=ollama          # Use local Ollama
OLLAMA_MODEL=llama4:latest   # Which model to use
DATA_PROVIDER=yfinance       # Free market data, no API key
DEBUG=false                  # Production mode
```

#### Step 5 (Optional): Start Ollama (2 minutes)

**Only needed if you want to use local AI (free)**

```bash
# In a SEPARATE terminal window:

ollama pull llama4:latest  # Download the model (first time only)
ollama serve               # Start the server
```

**What's happening?**

- Downloading the Llama 4 model. It is **large** (tens of GB) and needs a
  powerful machine; on a laptop, pull a smaller model (for example
  `ollama pull llama3.2`) and set `OLLAMA_MODEL` to match
- Starting the AI server on localhost:11434
- This is completely free and runs locally!

> The REST API and web UI work **without** an LLM. You only need one for the
> AI agent pipeline and the optional `include_narrative` outlooks.

#### Step 6: Start the API (1 minute)

**In your original terminal:**

```bash
python -m src.main api
```

**Expected output:**

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### Step 7: Test It Works! (1 minute)

**Open a new terminal and run:**

```bash
# Check if API is alive
curl http://localhost:8000/health
```

**Expected response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 5.2,
  "checks": {
    "market_data": "healthy",
    "agent_engine": "healthy",
    "data_processing": "healthy"
  }
}
```

**Success!** 🎉 Your system is running!

---

### First Analysis: Your First API Call

**Try analyzing Apple:**

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "analysis_type": "comprehensive"}'
```

**Or visit in browser:**

```
http://localhost:8000/        # the web UI (quote, /ratios, /dcf, /dashboard)
http://localhost:8000/docs    # Swagger UI - interactive API explorer
```

---

## 📁 Project Structure Explained

```
financial-research-analyst-agent/
│
├── src/                          # 👈 All source code here
│   ├── main.py                   # 📍 START HERE — `api` or `demo`
│   ├── cli.py                    # `analyze`, `portfolio`, `dashboard` commands
│   ├── config.py                 # ⚙️ Pydantic settings (reads .env)
│   │
│   ├── agents/                   # 🤖 The AI specialists (LLM agents)
│   │   ├── base.py               # BaseAgent: LLM setup, tools, state
│   │   ├── orchestrator.py       # Coordinates the pipeline
│   │   ├── data_collector.py, technical.py, fundamental.py,
│   │   │   sentiment.py, risk.py, report_generator.py
│   │   └── thematic.py, disruption.py, earnings.py, dividend.py, options.py
│   │
│   ├── tools/                    # 🔧 39 analysis modules (plain Python functions)
│   │   ├── market_data.py        # Prices, history, ratios profile, DCF profile
│   │   ├── technical_indicators.py
│   │   ├── financial_metrics.py
│   │   └── …                     # DCF, Monte Carlo, portfolio optimizer, etc.
│   │
│   ├── data/                     # Market-data providers (yfinance, FMP, …)
│   ├── rag/                      # SEC-filing search (optional, needs ChromaDB)
│   ├── models/                   # Data models
│   ├── api/
│   │   ├── routes.py             # All HTTP endpoints + static page routes
│   │   └── schemas.py            # Request/response models
│   └── utils/
│       ├── logger.py
│       └── helpers.py
│
├── static/                       # 🌐 Web UI (HTML/CSS/JS)
├── tests/                        # 🧪 375 tests across 19 files
├── config/                       # agents.yaml (weights), themes.yaml (17 themes)
├── docs/                         # 📚 This guide, ARCHITECTURE.md, audit reports
│
├── .env.example                  # Environment template
├── requirements.txt              # Full Python dependencies (local, Docker, CI)
├── pyproject.toml                # Slim dependencies (Vercel only)
├── Dockerfile, docker-compose.yml
├── CLAUDE.md                     # Developer guidelines
└── README.md                     # Project README
```

**Key folders to explore first:**

1. `src/main.py` - How does it start?
2. `src/agents/base.py` - How do agents work?
3. `src/api/routes.py` - How does API work?
4. `src/config.py` - How is it configured?

---

## 💡 Understanding Key Concepts

### What is "Async" and Why Do We Use It?

**Regular (Synchronous) Code:**

```python
# One thing at a time
result1 = get_price()        # Wait... wait... done! (2 sec)
result2 = get_technicals()   # Wait... wait... done! (2 sec)
result3 = get_fundamentals() # Wait... wait... done! (2 sec)
# Total: 6 seconds ❌
```

**Async Code:**

```python
# Multiple things at the same time
result1, result2, result3 = await asyncio.gather(
    get_price(),             # 2 sec
    get_technicals(),        # 2 sec (happens at SAME time)
    get_fundamentals()       # 2 sec
)
# Total: 2 seconds ✅ (Not 6!)
```

**Real-world analogy:**

- **Synchronous**: One waiter serves all customers one-by-one
- **Async**: Multiple waiters serve customers in parallel

---

### What is "Tool Binding"?

Agents can't do everything - they need tools.

**The mechanism:**

```python
# Step 1: Define a tool
@tool
def get_stock_price(symbol: str) -> float:
    """Get stock price"""
    return yahoo_finance.fetch(symbol)

# Step 2: Register tool with agent
# (each agent returns its tools from _get_default_tools(); you can also
#  pass tools=[...] to the BaseAgent constructor)
agent = TechnicalAnalystAgent()

# Step 3: Agent uses it automatically!
agent.analyze("AAPL")
# Agent internally: "I need stock price, I'll call get_stock_price tool"
# Tool: Returns $185.50
# Agent: "Now I can calculate RSI based on this price"
```

---

### What is "State Management"?

Every agent tracks its status:

```python
class AgentState:
    agent_name: str          # "TechnicalAnalyst"
    status: str              # "idle" / "running" / "completed" / "error"
    current_task: str        # "Calculating RSI"
    messages: list           # Conversation with the LLM
    started_at: datetime     # When did it start?
    completed_at: datetime   # When did it finish?
    results: dict            # What were the results?
    errors: list             # Any errors?

# Example:
agent.state.status = "running"
agent.state.current_task = "Fetching AAPL price"
# ... work ...
agent.state.status = "completed"
agent.state.results = {"price": 185.50}
```

**Why?** So we can:

- Track progress
- Debug when something goes wrong
- Know how long it took
- Display status to users

---

### What is "Configuration"?

Settings that control how the system behaves:

```python
# In .env file:
LLM_PROVIDER=openai          # Use OpenAI's GPT-4
LLM_TEMPERATURE=0.1          # Low = deterministic (consistent)
LLM_TEMPERATURE=0.9          # High = creative (different each time)

PORT=8000                    # API port (see note below)
LOG_LEVEL=INFO               # Show info-level logs
DEBUG=false                  # Disable debug mode
```

> ⚠️ **Known issue:** `.env.example` lists `API_PORT`, `API_HOST`, and
> `API_RELOAD`, but `src/config.py` currently reads `PORT`, `HOST`, and
> `RELOAD` instead (Pydantic v2 ignores the `env=` aliases), so the `API_*`
> names have no effect. Use the short names until that is fixed.

**Why?** So you can change behavior without touching code:

- Use Ollama in development (free, local)
- Use OpenAI in production (more powerful)

---

## 🛠️ Common Tasks

### Task 1: How to Analyze a Stock

```bash
# Using curl:
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "analysis_type": "comprehensive"}'

# Or run the full AI agent pipeline from Python (needs an LLM):
from src.agents import FinancialResearchAgent

agent = FinancialResearchAgent()
result = agent.analyze("AAPL")
print(result)
```

---

### Task 2: Change the LLM Provider

**Example: Switch from Ollama to OpenAI (to use GPT-4)**

```bash
# 1. Edit .env file
nano .env

# Change these lines:
# FROM:
LLM_PROVIDER=ollama

# TO:
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here

# 2. Restart API
python -m src.main api

# That's it! Everything else works the same.
```

---

### Task 3: Add a New Analysis Metric

**Example: Give the FundamentalAnalyst agent a dividend-yield tool**

```python
# File: src/agents/fundamental.py
# Agents define their tools inside _get_default_tools(). Add one:

class FundamentalAnalystAgent(BaseAgent):
    def _get_default_tools(self) -> List[BaseTool]:

        @tool("get_dividend_yield")
        def get_dividend_yield_tool(symbol: str) -> Dict[str, Any]:
            """Get the dividend yield (in percent) for a stock."""
            from src.data import get_provider
            info = get_provider().get_info(symbol)
            # yfinance already reports dividendYield as a percentage
            return {"symbol": symbol, "dividend_yield_pct": info.get("dividendYield")}

        return [
            calculate_valuation_ratios_tool,
            # … existing tools …
            get_dividend_yield_tool,          # ← add here
        ]
```

Then test it through the **agent pipeline** (the REST endpoint
`/api/v1/fundamental/{symbol}` does not use agents, so it won't change):

```python
from src.agents.fundamental import FundamentalAnalystAgent
agent = FundamentalAnalystAgent()
print([t.name for t in agent.tools])   # should include "get_dividend_yield"
```

Dividend data is also already available without agents via
`GET /api/v1/dividends/{symbol}`.

---

## 🧪 Testing: How to Verify Things Work

### Run All Tests

```bash
pytest tests/ -v
```

**Output example:**

```
tests/test_agents.py::TestTechnicalAnalystAgent::... PASSED
tests/test_api.py::TestHealthEndpoint::test_health_check PASSED
...
==================== 375 passed in ~2-3 min ====================
```

---

### Run Specific Tests

```bash
# Just test technical analysis
pytest tests/test_agents.py::TestTechnicalAnalystAgent -v

# Just test API endpoints
pytest tests/test_api.py -v

# With coverage report
pytest tests/ --cov=src --cov-report=html
# Then open: htmlcov/index.html
```

---

## 📦 Deployment: Running in Production

### Option 1: Local Machine (Development)

```bash
python -m src.main api
```

Runs on: `http://localhost:8000`

---

### Option 2: Docker (Recommended)

```bash
# Build
docker build -t financial-analyst .

# Run
docker run -p 8000:8000 --env-file .env financial-analyst

# Access: http://localhost:8000
```

---

### Option 3: Full Stack with Docker Compose

```bash
# Includes API + ChromaDB (vector store, used by the optional RAG/agent layer)

docker-compose up -d

# Services:
# - API on http://localhost:8000
# - ChromaDB on http://localhost:8001

docker-compose logs -f api  # View logs
docker-compose down         # Stop all
```

---

### Option 4: Vercel (serverless)

Pushing to `main` deploys to Vercel. Vercel installs the **slim** dependency
list in `pyproject.toml` (the full `requirements.txt` is ~6 GB, over Vercel's
500 MB limit, and is hidden by `.vercelignore`). So on Vercel:

- FinBERT, RAG/ChromaDB, and PDF/Excel export are unavailable
- Ollama can't be reached — set `LLM_PROVIDER=groq` and `GROQ_API_KEY`
- Empty environment variables fall back to their defaults

---

## 📚 Glossary: Technical Terms Explained

| Term | Meaning | Example |
|------|---------|---------|
| **LLM** | Large Language Model - AI that understands text | ChatGPT, GPT-4, Llama |
| **API** | Application Programming Interface - how apps talk | REST API with endpoints |
| **Async** | Asynchronous - things happen in parallel | Multiple tasks at once |
| **Agent** | AI worker with specific expertise | TechnicalAnalyst, DataCollector |
| **Tool** | Function an agent can call | get_stock_price() |
| **Orchestrator** | Manager that coordinates other agents | Assigns tasks, combines results |
| **Pydantic** | Python library for data validation | Validates request/response format |
| **FastAPI** | Python framework for building APIs | Web server for REST endpoints |
| **State** | Current status of something | agent.status = "running" |
| **RSI** | Relative Strength Index - momentum indicator | 0-100 scale, >70 = overbought |
| **MACD** | Technical indicator for trend changes | Shows momentum shifts |
| **P/E Ratio** | Price-to-Earnings ratio - valuation metric | Stock price ÷ Earnings per share |
| **Sentiment** | Overall feeling about something | Positive/negative/neutral |
| **VaR** | Value at Risk - potential loss estimate | "95% chance of loss < $5K" |
| **HTTP Status** | Response code from API | 200 = OK, 503 = error |

---

## ❓ Frequently Asked Questions

### Q: Do I need to know finance?

**A:** No! The system explains everything. But basic stock knowledge helps.

### Q: Do I need Ollama installed?

**A:** No! You can use OpenAI, Groq, or any other LLM instead.

### Q: How long does analysis take?

**A:** `POST /api/v1/analyze` usually takes a few seconds, but the first call
after a server start can take 10–90 s while the FinBERT model loads. The AI
agent pipeline takes much longer, because each agent makes several LLM calls.

### Q: Can I analyze multiple stocks at once?

**A:** Partly. `POST /api/v1/portfolio` returns each stock's price, but its
portfolio metrics are placeholders today. For real portfolio math use
`POST /api/v1/portfolio/optimize` (and `/rebalance`, `/benchmark`, …), or
`python -m src.cli portfolio AAPL MSFT` for the agent pipeline.

### Q: Is my API key safe?

**A:** Yes! Never commit `.env` to git - it's in `.gitignore`

### Q: What if Ollama is slow?

**A:** Use a cloud LLM (OpenAI, Groq) - faster but costs money.

### Q: Can I modify agent logic?

**A:** Yes! Edit `src/agents/*.py`. Note that agent changes affect the Python/CLI
pipeline and the `include_narrative` outlooks, not `POST /api/v1/analyze`.

### Q: How do I add a new agent?

**A:** Create new file in `src/agents/`, extend `BaseAgent`, add to orchestrator.

### Q: How do I debug?

**A:** Check logs in terminal, add print statements, use IDE debugger.

---

## 🎯 Your First Week Plan

### Day 1: Setup & Understand

- [ ] Install everything
- [ ] Run demo analysis
- [ ] Read this document
- [ ] Open Swagger UI at `/docs`

### Day 2: Explore Code

- [ ] Read `src/agents/base.py`
- [ ] Read `src/api/routes.py`
- [ ] Read `src/config.py`
- [ ] Make one API call and trace the code

### Day 3: Understand Architecture

- [ ] Read `src/agents/orchestrator.py`
- [ ] Draw your own architecture diagram
- [ ] Explain it to someone else

### Day 4: Make Small Change

- [ ] Add a new log message
- [ ] Change a configuration value
- [ ] Run tests
- [ ] Submit a small PR

### Day 5: Deeper Dive

- [ ] Read one agent implementation (`technical.py` or `fundamental.py`)
- [ ] Understand how it uses tools
- [ ] Add a new tool or metric
- [ ] Write a test for it

---

## 🚀 Next Steps

1. **Complete Getting Started** (above) - Set up locally ✅
2. **Run Demo**: `python -m src.main demo` ✅
3. **Test API**: Visit `http://localhost:8000/docs` ✅
4. **Read Architecture**: Understand how pieces fit together ✅
5. **Make PR**: Contribute something (even small!) ✅

---

## 📞 Getting Help

- **Setup issues?** Check CLAUDE.md
- **Code questions?** Check `docs/ARCHITECTURE.md`
- **Don't understand something?** Re-read relevant section (it gets clearer!)
- **Found a bug?** Open GitHub issue
- **Have ideas?** Discuss in team channels

---

## 🎓 Learning Resources

### For This Project

- README.md - Project overview
- docs/ARCHITECTURE.md - Deep technical details
- `http://localhost:8000/docs` - Live API reference (Swagger UI)
- docs/ROOT_CAUSE_ANALYSIS.md - The accuracy audit (17 findings)
- CLAUDE.md - Developer guidelines
- tests/ - Working code examples

### For Related Technologies

- [LangChain Docs](https://python.langchain.com/) - AI agents framework
- [FastAPI Docs](https://fastapi.tiangolo.com/) - Web framework
- [Python AsyncIO](https://docs.python.org/3/library/asyncio.html) - Parallel execution
- [Investopedia](https://www.investopedia.com/) - Finance basics

---

## 🎉 Congratulations

You now understand:

- ✅ What this project does
- ✅ How it's structured
- ✅ How agents work
- ✅ How to set it up
- ✅ How to make your first change
- ✅ Where to find help

**You're ready to contribute!** Welcome to the team! 🚀

---

**Last Updated**: September 26, 2026 (checked against the code)
**Document Version**: 2.1 (Beginner-Friendly)
**Audience**: Engineers with minimal project knowledge
