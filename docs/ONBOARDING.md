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

You ask the system: *"Should I buy Apple?"*

It responds with:

```
✅ Recommendation: BUY
📊 Confidence: 85%
💬 Reasoning: Strong fundamentals + positive news sentiment

Technical Analysis: RSI at 58.3, bullish MACD
Fundamental Analysis: P/E ratio 28.5 (reasonable)
Sentiment Analysis: News is 68% positive
Risk Analysis: Medium volatility
```

That's it! The system did all the research automatically.

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
┌──────────────────────────────────────────────┐
│  User makes request via REST API             │
│  (e.g., "Analyze AAPL")                      │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  FastAPI Routes (src/api/routes.py)          │
│  Receives request, validates input           │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  FinancialResearchAgent                      │
│  Main entry point, creates orchestrator      │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  OrchestratorAgent (The Conductor)           │
│  "I'll coordinate all the specialists"       │
└──────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
        ▼            ▼            ▼            ▼
    ┌─────┐     ┌─────┐      ┌─────┐      ┌─────┐
    │Data │     │Tech │      │Fund │      │Sent │  (Run in
    │Coll │     │Anal │      │Anal │      │Anal │   parallel)
    └─────┘     └─────┘      └─────┘      └─────┘
        │            │            │            │
        └────────────┼────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │  Report Generator       │
        │  Combines all results   │
        └────────────┬────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Final Result to User  │
        │  Recommendation: BUY   │
        │  Confidence: 85%       │
        └────────────────────────┘
```

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

- `POST /api/v1/analyze` → Analyze a stock
- `GET /api/v1/technical/AAPL` → Get just technical analysis
- `GET /api/v1/health` → Check if system is working
- `POST /api/v1/portfolio` → Analyze multiple stocks

### 4. **Configuration** - The Settings

**Location**: `src/config.py` and `.env` file

This is where you configure **settings**:

```
What LLM to use? (OpenAI? Ollama? Local?)
What temperature? (0 = deterministic, 1 = creative)
What database? (PostgreSQL? SQLite?)
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

#### **Step 2: Initialize the Main Agent**

```
File: src/api/routes.py

agent = FinancialResearchAgent()
# This is like saying "Hire the head chef"
```

**What happens internally**:

- Creates the Orchestrator Agent (project manager)
- Initializes the LLM (AI model)
- Loads all tools
- Prepares for work

---

#### **Step 3: Orchestrator Delegates Tasks**

```
File: src/agents/orchestrator.py

# Head chef says: "I need analysis of AAPL"
# Delegates to all specialists in parallel

results = await asyncio.gather(
    data_collector.execute("AAPL"),      # Get price & history
    technical_analyst.execute("AAPL"),   # Calculate indicators
    fundamental_analyst.execute("AAPL"), # Get P/E, earnings, etc.
    sentiment_analyst.execute("AAPL"),   # Analyze news
    risk_analyst.execute("AAPL"),        # Calculate risk
)

# All 5 agents work at the SAME TIME (parallel)
# Faster than if they worked one-by-one
```

**Timeline**:

```
WITHOUT parallel (sequential):
DataCollector:    ████░░░░░░░░░░░ (2 sec)
Technical:              ████░░░░░░░░░░░ (2 sec)
Fundamental:                ████░░░░░░░░░░░ (2 sec)
Sentiment:                      ████░░░░░░░░░░░ (2 sec)
Risk:                               ████░░░░░░░░░░░ (2 sec)
Total:                                          ████ 10 seconds ❌

WITH parallel (async):
DataCollector:    ████░░░░░░░░░░░░░░░░░░░░
Technical:        ████░░░░░░░░░░░░░░░░░░░░
Fundamental:      ████░░░░░░░░░░░░░░░░░░░░
Sentiment:        ████░░░░░░░░░░░░░░░░░░░░
Risk:             ████░░░░░░░░░░░░░░░░░░░░
Total:            ████░░░░░░░░░░░░░░░░░░░░
                  2-3 seconds ✅ Much faster!
```

---

#### **Step 4: Each Agent Works**

**Example: DataCollector Agent**

```
Agent thinks:
"I need AAPL stock data"

Calls tools:
1. get_stock_price("AAPL")
   → Yahoo Finance returns: {"price": 185.50, "change": +2.3%}

2. get_historical_data("AAPL", period="1y")
   → Returns: [180, 182, 183, 185, 187, 190, ...]

3. get_company_info("AAPL")
   → Returns: {"sector": "Technology", "market_cap": 2.8T, ...}

Returns result:
{
  "success": True,
  "data": {
    "current_price": 185.50,
    "history": [...],
    "company_info": {...}
  }
}
```

---

#### **Step 5: Report Generator Combines Results**

```
Generator receives all results:

DataCollector result: {current_price: 185.50, ...}
TechnicalAnalyst result: {rsi: 58.3, macd: positive, ...}
FundamentalAnalyst result: {pe_ratio: 28.5, eps_growth: 12.1%, ...}
SentimentAnalyst result: {score: 0.72, news: positive, ...}
RiskAnalyst result: {volatility: medium, sharpe: 1.8, ...}

Generator thinks:
"Good fundamentals (0.35 weight) = +30 points
 Positive sentiment (0.20 weight) = +15 points
 Technical signals buy (0.25 weight) = +20 points
 Medium risk acceptable (0.20 weight) = +20 points
 Total score: 85 points out of 100"

Recommendation:
{
  "recommendation": "BUY",
  "confidence": 0.85,
  "reasoning": "Strong fundamentals combined with positive momentum...",
  "target_price": 195.00
}
```

---

#### **Step 6: Response Sent Back to User**

```json
{
  "symbol": "AAPL",
  "recommendation": "BUY",
  "confidence": 0.85,
  "current_price": 185.50,
  "technical": {
    "rsi": 58.3,
    "macd": "positive",
    "trend": "bullish"
  },
  "fundamental": {
    "pe_ratio": 28.5,
    "eps_growth": 12.1,
    "roe": 147.3
  },
  "sentiment": {
    "score": 0.72,
    "news": "positive"
  },
  "risk": {
    "volatility": "medium"
  },
  "execution_time_seconds": 2.5
}
```

**User receives**: Professional stock analysis in 2.5 seconds! ⚡

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

git clone https://github.com/YOUR_USERNAME/financial-research-analyst-agent.git
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
API_PORT=8000                # API will run on port 8000
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

- Downloading a 7B parameter model (~4GB)
- Starting the AI server on localhost:11434
- This is completely free and runs locally!

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
    "agent_engine": "healthy"
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
http://localhost:8000/docs
```

This opens Swagger UI - an interactive API explorer where you can test endpoints!

---

## 📁 Project Structure Explained

```
financial-research-analyst-agent/
│
├── src/                          # 👈 All source code here
│   │
│   ├── main.py                   # 📍 START HERE
│   │                             # Entry point (runs the API)
│   │
│   ├── agents/                   # 🤖 The AI specialists
│   │   ├── base.py               # Template for all agents
│   │   ├── orchestrator.py        # Project manager agent
│   │   ├── data_collector.py      # Gets market data
│   │   ├── technical.py           # Technical analysis
│   │   ├── fundamental.py         # Company analysis
│   │   ├── sentiment.py           # News analysis
│   │   ├── risk.py                # Risk analysis
│   │   └── report_generator.py    # Combines results
│   │
│   ├── tools/                    # 🔧 Agent's instruments
│   │   ├── market_data.py         # Fetch stock prices
│   │   ├── technical_indicators.py # Calculate RSI, MACD
│   │   ├── news_fetcher.py        # Get news articles
│   │   └── financial_metrics.py   # Calculate metrics
│   │
│   ├── api/                      # 🌐 REST API
│   │   ├── routes.py              # Define endpoints (/analyze, /health, etc.)
│   │   └── schemas.py             # Validate requests/responses
│   │
│   ├── config.py                 # ⚙️ Configuration settings
│   │
│   └── utils/                    # 🛠️ Helper functions
│       ├── logger.py              # Logging
│       └── helpers.py             # Utilities
│
├── tests/                        # 🧪 Unit tests
│   ├── test_agents.py
│   ├── test_tools.py
│   └── test_api.py
│
├── docs/                         # 📚 Documentation
│   ├── ONBOARDING.md             # This file!
│   ├── architecture.md           # Detailed architecture
│   └── api_reference.md          # API documentation
│
├── config/                       # ⚙️ Configuration files
│   └── agents.yaml               # Agent settings
│
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker config
├── docker-compose.yml            # Multi-container setup
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
agent = TechnicalAnalyst(tools=[get_stock_price])

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

API_PORT=8000                # API listens on port 8000
LOG_LEVEL=INFO               # Show info-level logs
DEBUG=false                  # Disable debug mode
```

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

# Or using Python:
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

**Example: Add "Dividend Yield" to fundamental analysis**

```python
# Step 1: Create tool in src/tools/financial_metrics.py
@tool
def get_dividend_yield(symbol: str) -> float:
    """Get dividend yield percentage"""
    stock = yfinance.Ticker(symbol)
    return stock.info.get('dividendYield', 0)

# Step 2: Add to FundamentalAnalyst's tools
# File: src/agents/fundamental.py
class FundamentalAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            tools=[
                calculate_pe_ratio,
                calculate_eps,
                get_dividend_yield,  # ← Add here
            ]
        )

# Step 3: Test it
curl http://localhost:8000/api/v1/fundamental/AAPL
# Response will now include dividend yield!
```

---

## 🧪 Testing: How to Verify Things Work

### Run All Tests

```bash
pytest tests/ -v
```

**Output example:**

```
test_agents.py::TestTechnicalAnalyst::test_rsi PASSED ✓
test_agents.py::TestFundamentalAnalyst::test_pe_ratio PASSED ✓
test_api.py::test_health_endpoint PASSED ✓
==================== 3 passed in 0.24s ====================
```

---

### Run Specific Tests

```bash
# Just test technical analysis
pytest tests/test_agents.py::TestTechnicalAnalyst -v

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

**A:** 2-3 seconds for a single stock (parallel execution).

### Q: Can I analyze multiple stocks at once?

**A:** Yes! Use the portfolio endpoint: `POST /api/v1/portfolio`

### Q: Is my API key safe?

**A:** Yes! Never commit `.env` to git - it's in `.gitignore`

### Q: What if Ollama is slow?

**A:** Use a cloud LLM (OpenAI, Groq) - faster but costs money.

### Q: Can I modify agent logic?

**A:** Yes! Edit `src/agents/*.py` and restart API.

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
- **Code questions?** Check docs/ folder
- **Don't understand something?** Re-read relevant section (it gets clearer!)
- **Found a bug?** Open GitHub issue
- **Have ideas?** Discuss in team channels

---

## 🎓 Learning Resources

### For This Project

- README.md - Project overview
- docs/architecture.md - Deep technical details
- docs/api_reference.md - API endpoints
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

**Last Updated**: February 7, 2026
**Document Version**: 2.0 (Beginner-Friendly)
**Audience**: Engineers with minimal project knowledge
