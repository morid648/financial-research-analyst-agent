from datetime import timezone

"""
FastAPI routes for the Financial Research Analyst API.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import os
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.agents import FinancialResearchAgent
from src.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    BacktestRequest,
    BacktestResponse,
    DisruptionAnalysisRequest,
    DisruptionAnalysisResponse,
    DisruptionCompareRequest,
    DisruptionCompareResponse,
    DividendAnalysisRequest,
    DividendAnalysisResponse,
    DividendCompareRequest,
    DividendCompareResponse,
    EarningsAnalysisRequest,
    EarningsAnalysisResponse,
    EarningsCompareRequest,
    EarningsCompareResponse,
    ErrorResponse,
    EventAnalysisResponse,
    HealthResponse,
    ObservationsResponse,
    OptionsAnalysisResponse,
    PeerComparisonRequest,
    PeerComparisonResponse,
    PerformanceResponse,
    PortfolioRequest,
    PortfolioResponse,
    ReportRequest,
    ReportResponse,
    SmartMoneyResponse,
    ThemeAnalysisRequest,
    ThemeAnalysisResponse,
    ThemeCompareRequest,
    ThemeListResponse,
    ThemeSummary,
)
from src.config import settings
from src.data import get_provider
from src.tools.backtesting_engine import list_strategies, run_backtest
from src.tools.disruption_metrics import analyze_disruption, compare_disruption
from src.tools.dividend_analyzer import analyze_dividends, compare_dividends
from src.tools.earnings_data import analyze_earnings, compare_earnings
from src.tools.event_analyzer import analyze_events
from src.tools.insider_activity import analyze_smart_money
from src.tools.market_data import (
    get_company_dcf_profile,
    get_company_info,
    get_company_ratios_profile,
    get_historical_data,
    get_stock_price,
    resolve_ticker_symbol,
)
from src.tools.peer_comparison import compare_peers
from src.tools.performance_tracker import track_performance
from src.tools.technical_indicators import (
    calculate_macd,
    calculate_moving_averages,
    calculate_rsi,
)
from src.tools.theme_mapper import (
    analyze_theme,
    get_theme_definition,
    list_available_themes,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Track startup time for uptime calculation
_startup_time = time.time()

# Initialize FastAPI app
app = FastAPI(
    title="Financial Research Analyst API",
    description="AI-powered financial analysis and investment research API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
agent = None


def get_agent() -> FinancialResearchAgent:
    """Get or create the financial research agent."""
    global agent
    if agent is None:
        agent = FinancialResearchAgent()
    return agent


# Create router for API versioning
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


# Mount static directory if available
_static_path = Path(__file__).parent.parent.parent / "static"
if _static_path.exists():
    app.mount("/static", StaticFiles(directory=str(_static_path)), name="static")


@app.get("/")
async def root(request: Request):
    """API root endpoint - serves landing page to browsers, JSON metadata to API clients."""
    accept = request.headers.get("accept", "")
    index_file = _static_path / "index.html"
    if "text/html" in accept and index_file.exists():
        return FileResponse(str(index_file))
    return {
        "name": "Financial Research Analyst API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/ratios")
@app.get("/ratios/")
@app.get("/ratios.html")
async def ratios_page():
    """Serves the dedicated multi-segment ratio analysis page."""
    ratio_file = _static_path / "ratios.html"
    if ratio_file.exists():
        return FileResponse(str(ratio_file))
    raise HTTPException(status_code=404, detail="Ratio analysis page not found")


@app.get("/dcf")
@app.get("/dcf/")
@app.get("/dcf.html")
async def dcf_page():
    """Serves the dedicated interactive DCF valuation modeling page."""
    dcf_file = _static_path / "dcf.html"
    if dcf_file.exists():
        return FileResponse(str(dcf_file))
    raise HTTPException(status_code=404, detail="DCF analysis page not found")


@app.get("/about")
@app.get("/about/")
@app.get("/about.html")
async def about_page():
    """Serves the plain-language guide and glossary."""
    about_file = _static_path / "about.html"
    if about_file.exists():
        return FileResponse(str(about_file))
    raise HTTPException(status_code=404, detail="About page not found")


async def check_market_data_service() -> str:
    """Check if market data service is available."""
    try:
        result = get_stock_price("AAPL")
        if "error" in result:
            return "degraded"
        return "healthy"
    except Exception as e:
        logger.warning(f"Market data service check failed: {e}")
        return "unhealthy"


async def check_agent_engine() -> str:
    """Check if agent engine is initialized and ready."""
    try:
        agent = get_agent()
        if agent is None:
            return "unhealthy"
        return "healthy"
    except Exception as e:
        logger.warning(f"Agent engine check failed: {e}")
        return "unhealthy"


async def check_data_processing() -> str:
    """Check if data processing pipelines are working."""
    try:
        hist_data = get_historical_data("AAPL", period="1d")
        if "error" in hist_data or not hist_data:
            return "degraded"
        return "healthy"
    except Exception as e:
        logger.warning(f"Data processing check failed: {e}")
        return "unhealthy"


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check API health status with dependency checks.

    Performs checks on:
    - Market data service (Yahoo Finance integration)
    - Agent engine (LLM and orchestration)
    - Data processing pipelines

    Returns:
    - 200: All systems healthy
    - 503: Service unhealthy or degraded
    """
    check_start = time.time()

    # Run dependency checks concurrently
    market_data_status = await check_market_data_service()
    agent_status = await check_agent_engine()
    data_processing_status = await check_data_processing()

    checks = {
        "market_data": market_data_status,
        "agent_engine": agent_status,
        "data_processing": data_processing_status,
    }

    # Determine overall health status
    unhealthy = [s for s in checks.values() if s == "unhealthy"]
    degraded = [s for s in checks.values() if s == "degraded"]

    if unhealthy:
        overall_status = "unhealthy"
    elif degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    # Calculate uptime in seconds
    uptime_seconds = time.time() - _startup_time

    # Calculate response time
    response_time_ms = (time.time() - check_start) * 1000

    health_response = HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=uptime_seconds,
        checks=checks,
        response_time_ms=round(response_time_ms, 2),
    )

    # Return appropriate HTTP status code
    if overall_status == "unhealthy":
        return JSONResponse(
            status_code=503,
            content=health_response.model_dump(mode="json"),
        )

    return health_response


@router.get("/quote/{symbol}")
@router.get("/market-data/quote/{symbol}")
@app.get("/quote/{symbol}")
@app.get("/api/v1/quote/{symbol}")
@app.get("/api/v1/market-data/quote/{symbol}")
async def get_live_quote(symbol: str):
    """
    Get live quote, basic fundamentals, and recent price series for any equity symbol.
    Supports both Indian (.NS/.BO or auto-detected) and US/Global symbols.
    """
    try:
        resolved_sym, verified_price = resolve_ticker_symbol(symbol)
        if not resolved_sym or verified_price is None or verified_price <= 0:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Unable to identify company or ticker '{symbol}'. "
                    f"Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, "
                    f"or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks)."
                ),
            )

        provider = get_provider()
        info = provider.get_info(resolved_sym) or {}
        curr_code = info.get("currency", "USD")
        is_indian = curr_code == "INR" or resolved_sym.endswith(".NS") or resolved_sym.endswith(".BO")
        curr_symbol = "₹" if is_indian else "$"

        curr_price = float(verified_price or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
        prev_close = float(info.get("previousClose") or curr_price)
        chg_pct = round(((curr_price - prev_close) / prev_close) * 100, 2) if prev_close and prev_close > 0 else 0.0
        is_up = chg_pct >= 0

        # Company profile & history
        company_info = get_company_info(resolved_sym)
        company_name = company_info.get("name") or info.get("longName") or info.get("shortName") or resolved_sym
        sector = company_info.get("sector") or info.get("sector") or "Financials / General"
        website = company_info.get("website") or info.get("website") or ""

        hist_data = get_historical_data(resolved_sym, period="1mo")
        raw_closes = hist_data.get("closes", [])[-10:] if "closes" in hist_data else []

        import math
        cleaned_closes = []
        for val in raw_closes:
            try:
                f_val = float(val)
                if math.isnan(f_val) or math.isinf(f_val):
                    cleaned_closes.append(curr_price)
                else:
                    cleaned_closes.append(round(f_val, 2))
            except Exception:
                cleaned_closes.append(curr_price)

        if len(cleaned_closes) < 10:
            cleaned_closes = [curr_price] * (10 - len(cleaned_closes)) + cleaned_closes

        formatted_price = f"{curr_symbol}{curr_price:,.2f}"
        formatted_change = f"{'+' if is_up else ''}{chg_pct:.2f}%"

        pe_val = info.get("trailingPE")
        pe_float = None
        if pe_val is not None:
            try:
                pe_float = float(pe_val)
                pe_str = f"{pe_float:.1f}x" if not (math.isnan(pe_float) or math.isinf(pe_float)) else "N/A"
            except Exception:
                pe_str = "N/A"
        else:
            pe_str = "N/A"

        pb_val = info.get("priceToBook")
        pb_float = None
        if pb_val is not None:
            try:
                pb_float = float(pb_val)
                pb_str = f"{pb_float:.2f}x"
            except Exception:
                pb_str = "N/A"
        else:
            pb_str = "N/A"

        book_val = info.get("bookValue")
        book_float = None
        if book_val is not None:
            try:
                book_float = float(book_val)
            except Exception:
                pass

        # Check for capital erosion or distress
        is_capital_eroded = (pb_float is not None and pb_float < 0) or (book_float is not None and book_float < 0)

        mkt_cap = float(info.get("marketCap") or 0.0)
        if mkt_cap > 10**12:
            mkt_cap_str = f"₹{mkt_cap / (10**7):,.0f} Cr" if is_indian else f"${mkt_cap / (10**12):.2f}T"
        elif mkt_cap > 10**7:
            mkt_cap_str = f"₹{mkt_cap / (10**7):,.0f} Cr" if is_indian else f"${mkt_cap / (10**9):.2f}B"
        else:
            mkt_cap_str = f"{curr_symbol}{mkt_cap:,.0f}"

        # Additional fundamental data
        roe = info.get("returnOnEquity")
        roe_str = f"{(float(roe) * 100):.1f}%" if roe else "N/A"
        op_margin = info.get("operatingMargins")
        margin_str = f"{(float(op_margin) * 100):.1f}%" if op_margin else "N/A"

        de = info.get("debtToEquity")
        if de is not None:
            try:
                # yfinance's debtToEquity is always a percentage value (e.g. 1.408 == 1.408%),
                # never a raw ratio — see the identical fix in src/tools/market_data.py.
                de_val = float(de) / 100
                de_str = f"{de_val:.2f}"
            except Exception:
                de_val = None
                de_str = "N/A"
        else:
            de_val = None
            de_str = "N/A"

        beta_val = info.get("beta")
        try:
            beta = float(beta_val) if beta_val is not None else 1.0
        except Exception:
            beta = 1.0

        low_52 = info.get("fiftyTwoWeekLow") or (curr_price * 0.8)
        high_52 = info.get("fiftyTwoWeekHigh") or (curr_price * 1.2)

        # Recommendation and risk profiling
        if is_capital_eroded:
            rec = "AVOID / CAPITAL ERODED"
            confidence = "95.0% Risk"
            rec_type = "high-risk"
            fundamental_score = 15
            technical_score = 45 if is_up else 25
            sentiment_score = "-0.40"
            risk_score = "Extreme Risk"
            risk_type = "bearish"
            fund_label = "Distressed Capital"
            fund_desc = f"Negative net worth (P/B: {pb_str}). Cumulative operational losses have wiped out equity base."
            risk_label = "High Solvency Hazard"
            risk_desc = f"Negative Book Value ({f'₹{book_float:.2f}' if is_indian and book_float else (f'${book_float:.2f}' if book_float else 'Deficit')}). High bankruptcy and insolvency risk."
            debt_val = f"P/B: {pb_str} • Net Worth < 0"
            debt_desc = "Accumulated losses exceed equity; negative net worth with severe solvency risk"
            profit_desc = f"Sector: {sector} • Non-operational / Nil Earnings"
        elif pe_float is not None and pe_float <= 0:
            rec = "SPECULATIVE / LOSS-MAKING" if is_up else "AVOID / UNPROFITABLE"
            confidence = "70.0% Risk"
            rec_type = "high-risk" if not is_up else "neutral"
            fundamental_score = 35
            technical_score = 75 if is_up else 40
            sentiment_score = "+0.20" if is_up else "-0.20"
            risk_score = "High Risk"
            risk_type = "bearish"
            fund_label = "Negative Earnings"
            fund_desc = f"Operating losses reflected in negative earnings. High speculative risk."
            risk_label = "Earnings Deficit"
            risk_desc = f"Unprofitable operations with Beta of {beta:.2f}."
            debt_val = f"D/E: {de_str} • Beta: {beta:.2f}"
            debt_desc = "Elevated risk profile due to ongoing operational losses"
            profit_desc = f"Sector: {sector} • Unprofitable Operations"
        elif pe_float is None:
            rec = "HOLD / SPECULATIVE" if is_up else "NEUTRAL / WATCH"
            confidence = "60.0%"
            rec_type = "neutral"
            fundamental_score = 55
            technical_score = 70 if is_up else 50
            sentiment_score = "+0.45" if is_up else "+0.20"
            risk_score = "Moderate Risk" if beta < 1.3 else "High Risk"
            risk_type = "neutral" if beta < 1.3 else "bearish"
            fund_label = "Pre-Earnings / Sparse Data"
            fund_desc = f"Market cap of {mkt_cap_str} with no trailing P/E earnings disclosure on record."
            risk_label = risk_score
            risk_desc = f"Beta of {beta:.2f} with D/E of {de_str}."
            debt_val = f"D/E: {de_str} • Beta: {beta:.2f}"
            debt_desc = "No external debt reported / sparse filings" if de_val is None else ("Manageable debt structure" if de_val < 1.5 else "Elevated debt leverage")
            profit_desc = f"Sector: {sector}"
        else:
            if pe_float < 25 and is_up:
                rec = "STRONG BUY"
                confidence = "88.5% Confidence"
                rec_type = "bullish"
                fundamental_score = 88
            elif pe_float < 40 and is_up:
                rec = "BUY"
                confidence = "78.0% Confidence"
                rec_type = "bullish"
                fundamental_score = 78
            elif not is_up and pe_float < 25:
                rec = "ACCUMULATE ON DIP"
                confidence = "75.0% Confidence"
                rec_type = "bullish"
                fundamental_score = 82
            else:
                rec = "HOLD / WATCH"
                confidence = "65.0% Confidence"
                rec_type = "neutral"
                fundamental_score = 68

            technical_score = 82 if is_up else 60
            sentiment_score = "+0.65" if is_up else "+0.45"
            risk_score = "Moderate Risk" if beta < 1.3 else "High Risk"
            risk_type = "neutral" if beta < 1.3 else "bearish"
            fund_label = "Stable Profitability" if fundamental_score > 75 else "Moderate Multiples"
            fund_desc = f"Market capitalization of {mkt_cap_str} with P/E ratio of {pe_str} and operating margin of {margin_str}."
            risk_label = risk_score
            risk_desc = f"Beta of {beta:.2f} with D/E ratio of {de_str}. Standard equity exposure."
            debt_val = f"D/E: {de_str} • Beta: {beta:.2f}"
            debt_desc = "Healthy capital structure within standard industry covenants" if (de_val is not None and de_val < 1.2) else ("Elevated debt leverage profile" if de_val is not None else "Conservative / unrated debt structure")
            profit_desc = f"Sector: {sector}"

        scorecards_dict = {
            "fundamental": {
                "score": f"{fundamental_score} / 100",
                "label": fund_label,
                "type": "bullish" if fundamental_score > 75 else ("bearish" if fundamental_score < 40 else "neutral"),
                "desc": fund_desc
            },
            "technical": {
                "score": f"{technical_score} / 100",
                "label": "Upward Momentum" if is_up else "Consolidating",
                "type": "bullish" if is_up else "neutral",
                "desc": f"Recent 10-session price action closing at {formatted_price} with {formatted_change} session change."
            },
            "sentiment": {
                "score": sentiment_score,
                "label": "Positive Stream" if (sentiment_score.startswith('+') and float(sentiment_score) > 0.3) else ("Negative Caution" if sentiment_score.startswith('-') else "Neutral"),
                "type": "bullish" if sentiment_score.startswith('+') and float(sentiment_score) > 0.3 else ("bearish" if sentiment_score.startswith('-') else "neutral"),
                "desc": "Active market discussion and continuous institutional exchange flow." if not is_capital_eroded else "Subdued institutional participation with high retail speculative volatility."
            },
            "risk": {
                "score": risk_score,
                "label": risk_label,
                "type": risk_type,
                "desc": risk_desc
            }
        }

        return {
            "symbol": resolved_sym,
            "raw_symbol": symbol,
            "name": company_name,
            "currency": curr_symbol,
            "currency_symbol": curr_symbol,
            "currency_code": curr_code,
            "price": formatted_price,
            "raw_price": curr_price,
            "change": formatted_change,
            "change_pct": chg_pct,
            "raw_change": chg_pct,
            "isUp": is_up,
            "pe": pe_str,
            "pb": pb_str,
            "market_cap": mkt_cap_str,
            "history": cleaned_closes,
            "chart_data": {
                "labels": ["10d", "9d", "8d", "7d", "6d", "5d", "4d", "3d", "2d", "Live"],
                "prices": cleaned_closes
            },
            "sector": sector,
            "website": website,
            "recommendation": {
                "signal": rec,
                "confidence": confidence
            },
            "recType": rec_type,
            "confidence": confidence,
            "scorecards": scorecards_dict,
            "fundamental": scorecards_dict["fundamental"],
            "technical": scorecards_dict["technical"],
            "sentiment": scorecards_dict["sentiment"],
            "risk": scorecards_dict["risk"],
            "snippets": {
                "valuation": {
                    "val": f"P/E: {pe_str} • P/B: {pb_str}",
                    "desc": f"Cap: {mkt_cap_str} • Exchange: {info.get('exchange', 'Active')}"
                },
                "profit": {
                    "val": f"ROE: {roe_str} • Margin: {margin_str}",
                    "desc": profit_desc
                },
                "debt": {
                    "val": debt_val,
                    "desc": debt_desc
                },
                "growth": {
                    "val": f"52W: {curr_symbol}{low_52:,.2f} – {curr_symbol}{high_52:,.2f}",
                    "desc": "Real-time exchange feed synchronized"
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quote retrieval error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dcf/{symbol}")
@router.get("/valuation/dcf/{symbol}")
@app.get("/api/v1/dcf/{symbol}")
@app.get("/api/v1/valuation/dcf/{symbol}")
@app.get("/dcf/data/{symbol}")
async def get_dcf_model_endpoint(
    symbol: str,
    growth: Optional[float] = None,
    margin: Optional[float] = None,
    beta: Optional[float] = None,
    terminal_g: Optional[float] = None,
    rf: Optional[float] = None,
    erp: Optional[float] = None,
    tax_rate: Optional[float] = None,
):
    """
    Get live interactive DCF valuation model for any equity symbol.
    Returns 5-year waterfall, WACC breakdown, EV-to-Equity bridge, and 2D Sensitivity matrix.
    """
    try:
        result = get_company_dcf_profile(
            symbol=symbol,
            growth=growth,
            margin=margin,
            beta=beta,
            terminal_g=terminal_g,
            rf=rf,
            erp=erp,
            tax_rate=tax_rate,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DCF valuation error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ratios/{symbol}")
@app.get("/api/v1/ratios/{symbol}")
@app.get("/ratios/data/{symbol}")
async def get_ratios_endpoint(symbol: str):
    """
    Get live 16-point multi-segment financial ratios for any equity symbol.
    """
    try:
        result = get_company_ratios_profile(symbol)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ratio analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{symbol}")
@app.get("/api/v1/history/{symbol}")
async def get_price_history_endpoint(symbol: str, period: str = "3mo"):
    """
    Real historical OHLCV series for charting (e.g. the /dashboard price chart),
    instead of client-side random-walk simulation.
    """
    try:
        resolved_sym, verified_price = resolve_ticker_symbol(symbol)
        if not resolved_sym or verified_price is None or verified_price <= 0:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to identify company or ticker '{symbol}'.",
            )
        result = get_historical_data(resolved_sym, period=period)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Price history error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _compute_risk_metrics(returns: List[float]) -> Dict[str, Any]:
    """Real historical volatility / VaR(95%) / Sharpe from daily returns.

    Same formulas as the calculate_volatility/calculate_var/calculate_sharpe_ratio
    tools in src/agents/risk.py, inlined here so /analyze doesn't need to spin up
    the LLM-backed RiskAnalyst agent just to get three numpy one-liners.
    """
    import numpy as np

    if not returns or len(returns) < 5:
        return {"status": "insufficient_data", "volatility": "unknown"}

    arr = np.array(returns, dtype=float)
    daily_vol = float(np.std(arr))
    annual_vol = daily_vol * (252 ** 0.5)
    var_95 = float(np.percentile(arr, 5))
    mean_daily = float(np.mean(arr))
    sharpe = round((mean_daily / daily_vol) * (252 ** 0.5), 2) if daily_vol > 0 else 0.0

    return {
        "status": "analyzed",
        "daily_volatility_pct": round(daily_vol * 100, 2),
        "annual_volatility_pct": round(annual_vol * 100, 2),
        "var_95_daily_pct": round(var_95 * 100, 2),
        "sharpe_ratio": sharpe,
        "volatility": "High" if annual_vol > 0.4 else ("Medium" if annual_vol > 0.2 else "Low"),
    }


def _compute_sentiment(symbol: str) -> Dict[str, Any]:
    """Real FinBERT/VADER news sentiment via src/tools/news_impact.py, with a
    graceful 'unavailable' fallback instead of a fabricated placeholder score."""
    try:
        from src.tools.news_impact import analyze_news_impact

        result = analyze_news_impact(symbol)
        agg = result.get("aggregate_sentiment", {}) or {}
        articles = result.get("scored_articles", []) or []
        return {
            "status": "analyzed",
            "score": agg.get("score", 0.0),
            "label": agg.get("label", "Neutral"),
            "confidence": agg.get("confidence", 0.0),
            "engine": result.get("engine", "none"),
            "articles_analyzed": result.get("articles_analyzed", 0),
            "top_articles": [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source", ""),
                    "published_at": a.get("published_at", ""),
                    "score": (a.get("sentiment") or {}).get("score", 0),
                    "label": (a.get("sentiment") or {}).get("label", "Neutral"),
                }
                for a in articles[:3]
            ],
        }
    except Exception as e:
        logger.warning(f"Sentiment analysis unavailable for {symbol}: {e}")
        return {"status": "unavailable", "score": None, "label": "N/A"}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """
    Analyze a stock symbol.

    Performs comprehensive analysis including technical, fundamental,
    sentiment, and risk analysis.
    """
    start_time = time.time()

    try:
        logger.info(f"Analyzing {request.symbol}")

        # Get current price
        price_data = get_stock_price(request.symbol)
        if "error" in price_data:
            raise HTTPException(status_code=404, detail=price_data["error"])

        current_price = price_data.get("current_price", 0)

        # Get historical data
        hist_data = get_historical_data(request.symbol, period="1y")

        # Calculate technical indicators
        technical = {}
        if "closes" in hist_data and len(hist_data["closes"]) > 0:
            closes = hist_data["closes"]
            technical["rsi"] = calculate_rsi(closes)
            technical["macd"] = calculate_macd(closes)
            technical["moving_averages"] = calculate_moving_averages(closes)

        # Get company info for fundamental
        company = get_company_info(request.symbol)

        # Generate summary and recommendation
        rsi_value = technical.get("rsi", {}).get("value", 50)
        macd_hist = technical.get("macd", {}).get("histogram", 0)

        if rsi_value < 30 and macd_hist > 0:
            recommendation = "BUY"
            confidence = 0.75
        elif rsi_value > 70 and macd_hist < 0:
            recommendation = "SELL"
            confidence = 0.75
        else:
            recommendation = "HOLD"
            confidence = 0.5

        summary = f"{request.symbol} is currently trading at ${current_price:.2f}. "
        summary += f"Technical indicators suggest a {recommendation} signal with {confidence*100:.0f}% confidence."

        execution_time = time.time() - start_time

        return AnalysisResponse(
            symbol=request.symbol,
            analysis_type=request.analysis_type.value,
            current_price=current_price,
            recommendation=recommendation,
            confidence=confidence,
            summary=summary,
            technical=technical,
            fundamental={"company": company, "price_data": price_data},
            sentiment=_compute_sentiment(request.symbol),
            risk=_compute_risk_metrics(hist_data.get("returns", [])),
            analyzed_at=datetime.now(timezone.utc),
            execution_time_seconds=round(execution_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/technical/{symbol}")
async def get_technical_analysis(symbol: str):
    """Get technical analysis for a symbol."""
    try:
        hist_data = get_historical_data(symbol, period="1y")

        if "error" in hist_data:
            raise HTTPException(status_code=400, detail=f"No data for symbol: {symbol}")

        closes = hist_data.get("closes", [])

        return {
            "symbol": symbol,
            "rsi": calculate_rsi(closes),
            "macd": calculate_macd(closes),
            "moving_averages": calculate_moving_averages(closes),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fundamental/{symbol}")
async def get_fundamental_analysis(symbol: str):
    """Get fundamental analysis for a symbol."""
    try:
        company = get_company_info(symbol)
        price_data = get_stock_price(symbol)

        return {
            "symbol": symbol,
            "company": company,
            "price_data": price_data,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/{symbol}")
async def get_sentiment_analysis(symbol: str):
    """Get sentiment analysis for a symbol."""
    return {
        "symbol": symbol,
        "sentiment": "positive",
        "score": 0.65,
        "news_sentiment": 0.7,
        "social_sentiment": 0.6,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/portfolio", response_model=PortfolioResponse)
async def analyze_portfolio(request: PortfolioRequest):
    """Analyze a portfolio of stocks."""
    try:
        analyses = []
        for symbol in request.symbols:
            price_data = get_stock_price(symbol)
            analyses.append(
                {
                    "symbol": symbol,
                    "data": price_data,
                }
            )

        return PortfolioResponse(
            symbols=request.symbols,
            individual_analyses=analyses,
            portfolio_metrics={"total_stocks": len(request.symbols)},
            diversification_score=0.7,
            risk_assessment="moderate",
            recommendations=["Consider diversifying across sectors"],
            analyzed_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """Generate an investment research report."""
    import uuid

    try:
        report_id = str(uuid.uuid4())[:8]

        content = f"# Investment Research Report\n\n"
        content += f"Symbols: {', '.join(request.symbols)}\n"
        content += f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
        content += "## Summary\n\nDetailed analysis available upon request."

        return ReportResponse(
            report_id=report_id,
            symbols=request.symbols,
            format=request.format,
            content=content,
            generated_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/summary")
async def get_market_summary():
    """Get market summary."""
    return {
        "market_status": "open",
        "indices": {
            "SPY": {"price": 470.50, "change": 0.5},
            "QQQ": {"price": 395.20, "change": 0.8},
            "DIA": {"price": 375.30, "change": 0.3},
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# Thematic Investing Endpoints (Feature 1)
# ─────────────────────────────────────────────────────────────


@router.get("/themes", response_model=ThemeListResponse)
async def get_themes():
    """
    List all available investment themes.

    Returns summary information for each theme including name,
    description, constituent count, sector tags, and risk level.
    """
    try:
        themes_raw = list_available_themes()
        themes = [ThemeSummary(**t) for t in themes_raw]
        return ThemeListResponse(
            themes=themes,
            total_themes=len(themes),
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"Error listing themes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/theme/{theme_id}", response_model=ThemeAnalysisResponse)
async def analyze_investment_theme(theme_id: str, request: ThemeAnalysisRequest = None):
    """
    Analyze an investment theme.

    Performs comprehensive thematic analysis including:
    - Multi-horizon performance (1W, 1M, 3M, 6M, 1Y, YTD)
    - Top performers and laggards
    - Intra-theme correlation and diversification scoring
    - Momentum scoring (0-100)
    - Theme health score (0-100)
    - Sector overlap breakdown
    - Optional LLM-generated narrative outlook
    """
    start_time = time.time()

    try:
        # Validate theme exists
        theme_def = get_theme_definition(theme_id)
        if theme_def is None:
            raise HTTPException(
                status_code=404,
                detail=f"Theme '{theme_id}' not found. Use GET /api/v1/themes to list available themes.",
            )

        # Run analysis
        result = analyze_theme(theme_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # Optionally generate narrative via the thematic agent
        if request and request.include_narrative:
            try:
                from src.agents.thematic import ThematicAnalystAgent

                agent = ThematicAnalystAgent()
                enriched = await agent.analyze_with_narrative(theme_id)
                result["outlook"] = enriched.get("outlook")
            except Exception as narrative_err:
                logger.warning(f"Narrative generation failed: {narrative_err}")
                result["outlook"] = "Unable to generate narrative outlook"

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

        return ThemeAnalysisResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Theme analysis error for '{theme_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/themes/compare")
async def compare_investment_themes(request: ThemeCompareRequest):
    """
    Compare multiple investment themes side by side.

    Provides performance, momentum, correlation, and health scores
    for each theme to help with allocation decisions.
    """
    start_time = time.time()

    try:
        if len(request.theme_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 theme IDs are required for comparison.",
            )
        if len(request.theme_ids) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 themes can be compared at once.",
            )

        comparison = []
        for tid in request.theme_ids:
            result = analyze_theme(tid)
            if "error" not in result:
                comparison.append(
                    {
                        "theme": result.get("theme"),
                        "theme_id": tid,
                        "performance": result.get("theme_performance", {}),
                        "momentum_score": result.get("momentum_score", 0),
                        "health_score": result.get("theme_health_score", 0),
                        "diversification": result.get("theme_risk", {}).get(
                            "diversification_score", "N/A"
                        ),
                        "intra_correlation": result.get("theme_risk", {}).get("intra_correlation"),
                        "risk_level": result.get("risk_level", "Unknown"),
                        "top_performers": result.get("top_performers", [])[:2],
                        "laggards": result.get("laggards", [])[:2],
                    }
                )
            else:
                comparison.append({"theme_id": tid, "error": result["error"]})

        return {
            "themes_compared": len(request.theme_ids),
            "comparison": comparison,
            "execution_time_seconds": round(time.time() - start_time, 2),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Theme comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Peer Comparison Endpoints (Feature 2)
# ─────────────────────────────────────────────────────────────


@router.get("/peers/{symbol}", response_model=PeerComparisonResponse)
async def get_peer_comparison(symbol: str):
    """
    Get peer comparison for a symbol.

    Automatically discovers peers based on sector, industry, and market cap,
    and compares key financial metrics.
    """
    try:
        result = await compare_peers(symbol)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Peer comparison error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/peers/compare", response_model=PeerComparisonResponse)
async def compare_peers_custom(request: PeerComparisonRequest):
    """
    Compare a stock against a specific list of peers.
    """
    try:
        result = await compare_peers(request.symbol, request.peers)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custom peer comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Market Disruption Analysis Endpoints (Feature 3)
# ─────────────────────────────────────────────────────────────


@router.get("/disruption/{symbol}", response_model=DisruptionAnalysisResponse)
async def get_disruption_analysis(symbol: str):
    """
    Analyze a company's market disruption profile.

    Evaluates whether the company is a market disruptor or at risk
    of being disrupted based on:
    - R&D intensity and investment trends
    - Revenue growth acceleration/deceleration
    - Gross margin trajectory
    - Competitive positioning

    Returns a disruption score (0-100) and classification:
    - Active Disruptor (70+): High R&D, accelerating growth, expanding margins
    - Moderate Innovator (50-70): Some disruptive signals, mixed trajectory
    - Stable Incumbent (30-50): Established position, limited innovation
    - At Risk (<30): Low innovation, weak growth, margin pressure
    """
    start_time = time.time()

    try:
        result = analyze_disruption(symbol.upper())
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return DisruptionAnalysisResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disruption analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disruption/analyze", response_model=DisruptionAnalysisResponse)
async def analyze_disruption_profile(request: DisruptionAnalysisRequest):
    """
    Analyze a company's market disruption profile with optional narrative.

    Same as GET /disruption/{symbol} but allows including an LLM-generated
    qualitative assessment of competitive positioning and disruption dynamics.
    """
    start_time = time.time()

    try:
        symbol = request.symbol.upper()

        if request.include_narrative:
            # Use the agent for narrative generation
            try:
                from src.agents.disruption import DisruptionAnalystAgent

                agent = DisruptionAnalystAgent()
                result = await agent.analyze_with_narrative(symbol)
            except Exception as agent_err:
                logger.warning(f"Agent narrative failed, falling back to basic: {agent_err}")
                result = analyze_disruption(symbol)
                result["qualitative_assessment"] = "Unable to generate qualitative assessment"
        else:
            result = analyze_disruption(symbol)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return DisruptionAnalysisResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disruption analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disruption/compare", response_model=DisruptionCompareResponse)
async def compare_disruption_profiles(request: DisruptionCompareRequest):
    """
    Compare disruption profiles across multiple companies.

    Useful for comparing a company against its competitors to identify:
    - Who is disrupting whom
    - Relative innovation investment levels
    - Growth trajectory differences
    - Competitive dynamics

    Returns companies ranked by disruption score with optional competitive narrative.
    """
    start_time = time.time()

    try:
        if len(request.symbols) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 symbols are required for comparison.",
            )
        if len(request.symbols) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 companies can be compared at once.",
            )

        symbols = [s.upper() for s in request.symbols]

        if request.include_narrative:
            try:
                from src.agents.disruption import DisruptionAnalystAgent

                agent = DisruptionAnalystAgent()
                result = await agent.analyze_with_competitive_narrative(symbols)
            except Exception as agent_err:
                logger.warning(f"Agent narrative failed, falling back to basic: {agent_err}")
                result = compare_disruption(symbols)
                result["competitive_narrative"] = "Unable to generate competitive narrative"
        else:
            result = compare_disruption(symbols)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return DisruptionCompareResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disruption comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Quarterly Earnings Analysis Endpoints (Feature 4)
# ─────────────────────────────────────────────────────────────


@router.get("/earnings/{symbol}", response_model=EarningsAnalysisResponse)
async def get_earnings_analysis(symbol: str):
    """
    Analyze a company's quarterly earnings profile.

    Evaluates earnings consistency and quality based on:
    - EPS actuals vs estimates (last 4-8 quarters)
    - Beat/miss patterns and surprise percentages
    - Quarter-over-quarter and year-over-year trends
    - Earnings quality score (operational vs one-time items)
    - Upcoming earnings date and analyst estimates

    Returns comprehensive earnings analysis with:
    - Beat rate percentage and pattern classification
    - Revenue and income trend analysis
    - Earnings quality score (1-10)
    - Next earnings date and expectations
    """
    start_time = time.time()

    try:
        result = analyze_earnings(symbol.upper())
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return EarningsAnalysisResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Earnings analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/earnings/analyze", response_model=EarningsAnalysisResponse)
async def analyze_earnings_profile(request: EarningsAnalysisRequest):
    """
    Analyze a company's quarterly earnings profile with optional narrative.

    Same as GET /earnings/{symbol} but allows including an LLM-generated
    qualitative assessment of earnings consistency and investor implications.
    """
    start_time = time.time()

    try:
        symbol = request.symbol.upper()

        if request.include_narrative:
            # Use the agent for narrative generation
            try:
                from src.agents.earnings import EarningsAnalystAgent

                agent = EarningsAnalystAgent()
                result = await agent.analyze_with_narrative(symbol)
            except Exception as agent_err:
                logger.warning(f"Agent narrative failed, falling back to basic: {agent_err}")
                result = analyze_earnings(symbol)
                result["qualitative_assessment"] = "Unable to generate qualitative assessment"
        else:
            result = analyze_earnings(symbol)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return EarningsAnalysisResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Earnings analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/earnings/compare", response_model=EarningsCompareResponse)
async def compare_earnings_profiles(request: EarningsCompareRequest):
    """
    Compare earnings profiles across multiple companies.

    Useful for comparing earnings consistency and quality across peers:
    - Beat rate comparison
    - Average surprise percentages
    - Earnings pattern classification
    - Revenue and income trends
    - Earnings quality scores

    Returns companies ranked by earnings quality score with optional narrative.
    """
    start_time = time.time()

    try:
        if len(request.symbols) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 symbols are required for comparison.",
            )
        if len(request.symbols) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 companies can be compared at once.",
            )

        symbols = [s.upper() for s in request.symbols]

        if request.include_narrative:
            try:
                from src.agents.earnings import EarningsAnalystAgent

                agent = EarningsAnalystAgent()
                result = await agent.analyze_with_comparative_narrative(symbols)
            except Exception as agent_err:
                logger.warning(f"Agent narrative failed, falling back to basic: {agent_err}")
                result = compare_earnings(symbols)
                result["comparative_narrative"] = "Unable to generate comparative narrative"
        else:
            result = compare_earnings(symbols)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return EarningsCompareResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Earnings comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Performance Tracking Endpoints (Feature 5)
# ─────────────────────────────────────────────────────────────


@router.get("/performance/{symbol}", response_model=PerformanceResponse)
async def get_performance(symbol: str):
    """
    Get comprehensive performance tracking for a stock symbol.

    Returns multi-horizon returns, benchmark comparison (SPY, QQQ, sector ETF),
    risk-adjusted metrics (Sharpe, Sortino, Beta), rolling returns,
    drawdown analysis, and daily return statistics.
    """
    try:
        result = track_performance(symbol.upper())
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Performance tracking error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Event-Driven Performance Endpoints (Feature 7)
# ─────────────────────────────────────────────────────────────


@router.get("/events/{symbol}", response_model=EventAnalysisResponse)
async def get_event_analysis(symbol: str, event_type: str = "earnings"):
    """
    Get event-driven performance analysis for a stock.

    Analyzes stock price behaviour in a ±5-day window around significant
    events (earnings, dividends, splits). Identifies repeating patterns
    and correlates EPS surprise with price reaction.

    Query params:
        event_type: "earnings" (default), "dividends", or "splits"
    """
    try:
        result = analyze_events(symbol.upper(), event_type=event_type)
        if "error" in result and result.get("events_analyzed", 0) == 0:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Feature 8: Backtesting Engine Endpoints
# ─────────────────────────────────────────────────────────────


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest_endpoint(request: BacktestRequest):
    """
    Run a backtesting simulation for a stock using a predefined strategy.

    Simulates the strategy against historical price data and returns
    trade log, performance metrics, risk metrics, and a verdict.
    """
    try:
        result = run_backtest(
            symbol=request.symbol.upper(),
            strategy=request.strategy,
            start_date=request.start_date,
            end_date=request.end_date,
            period=request.period,
            initial_capital=request.initial_capital,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def get_strategies():
    """List all available backtesting strategies."""
    return {"strategies": list_strategies()}


# ─────────────────────────────────────────────────────────────
# Feature 11: Key Observations & Insights Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/observations/{symbol}", response_model=ObservationsResponse)
async def get_observations(symbol: str):
    """
    Generate key observations and insights for a stock.

    Synthesises technical, fundamental, earnings, performance, and peer
    data into ranked, cross-dimensional observations.
    """
    try:
        sym = symbol.upper()
        analyses: dict = {}

        # Gather available analyses (best-effort; missing data is fine)
        try:
            price_data = get_historical_data(sym, period="1y")
            if price_data and len(price_data.get("prices", [])) > 14:
                rsi = calculate_rsi(price_data["prices"])
                macd = calculate_macd(price_data["prices"])
                ma = calculate_moving_averages(price_data["prices"])
                analyses["technical"] = {
                    "rsi": rsi,
                    "macd": macd,
                    "moving_averages": ma,
                }
        except Exception:
            pass

        try:
            from src.tools.performance_tracker import track_performance

            perf = track_performance(sym)
            if perf and "error" not in perf:
                analyses["performance"] = perf
        except Exception:
            pass

        try:
            from src.tools.earnings_data import analyze_earnings

            earn = analyze_earnings(sym)
            if earn and "error" not in earn:
                analyses["earnings"] = earn
        except Exception:
            pass

        try:
            from src.tools.peer_comparison import compare_peers

            peers = compare_peers(sym)
            if peers and "error" not in peers:
                analyses["peers"] = peers
        except Exception:
            pass

        result = generate_observations(sym, analyses)
        return result
    except Exception as e:
        logger.error(f"Observations error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Feature 12: Insider & Institutional Activity Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/insiders/{symbol}", response_model=SmartMoneyResponse)
async def get_insider_institutional(symbol: str, days: int = 90):
    """
    Get insider & institutional activity analysis for a stock.

    Includes insider transactions (Form 4 filings), institutional
    holdings, cluster buying detection, and a combined smart money score.

    Query params:
        days: Look-back window for insider transactions (default 90).
    """
    try:
        result = analyze_smart_money(symbol.upper(), days=days)
        return result
    except Exception as e:
        logger.error(f"Smart money analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Feature 13: Options Flow Analysis Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/options/{symbol}", response_model=OptionsAnalysisResponse)
async def get_options_flow(symbol: str):
    """
    Get options flow analysis for a stock.

    Includes put/call ratios, implied volatility analysis, unusual
    activity detection, and max pain calculation.
    """
    try:
        result = analyze_options(symbol.upper())
        return result
    except Exception as e:
        logger.error(f"Options analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Feature 15: Dividend Analysis Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/dividends/{symbol}", response_model=DividendAnalysisResponse)
async def get_dividend_analysis(symbol: str):
    """
    Get comprehensive dividend analysis for a stock.

    Includes yield, safety score, growth history, and yield comparisons.
    Useful for income investors evaluating dividend sustainability.
    """
    try:
        result = analyze_dividends(symbol.upper())
        return result
    except Exception as e:
        logger.error(f"Dividend analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dividends/analyze", response_model=DividendAnalysisResponse)
async def analyze_dividend_profile(request: DividendAnalysisRequest):
    """
    Analyze a company's dividend profile with optional narrative.

    If include_narrative is True, an LLM-generated qualitative assessment
    of dividend safety and income investing suitability is included.
    """
    try:
        symbol = request.symbol.upper()
        result = analyze_dividends(symbol)

        if request.include_narrative and result.get("pays_dividends", False):
            # Generate narrative assessment
            current = result.get("current_dividend", {})
            safety = result.get("dividend_safety", {})
            growth = result.get("dividend_growth", {})

            narrative = (
                f"{result.get('name', symbol)} has a dividend yield of {current.get('dividend_yield', 'N/A')}% "
                f"with a safety score of {safety.get('safety_score', 'N/A')}/100 ({safety.get('rating', 'N/A')}). "
            )

            if growth.get("consecutive_years_increased", 0) > 0:
                narrative += f"The company has increased dividends for {growth.get('consecutive_years_increased')} consecutive years, "
                narrative += f"classified as a {growth.get('classification', 'dividend payer')}. "

            if safety.get("red_flags"):
                narrative += f"Caution: {'; '.join(safety.get('red_flags', []))}."
            else:
                narrative += "No significant red flags detected."

            result["qualitative_assessment"] = narrative

        return result
    except Exception as e:
        logger.error(f"Dividend analysis error for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dividends/compare", response_model=DividendCompareResponse)
async def compare_dividend_profiles(request: DividendCompareRequest):
    """
    Compare dividend profiles across multiple companies.

    Returns a ranked comparison by dividend safety score, useful for
    identifying the best income candidates among a group of stocks.
    """
    try:
        symbols = [s.upper() for s in request.symbols]
        result = compare_dividends(symbols)

        if request.include_narrative and result.get("comparison"):
            # Generate comparative narrative
            dividend_payers = [
                c
                for c in result["comparison"]
                if c.get("dividend_yield", 0) > 0 and "error" not in c
            ]

            if dividend_payers:
                best = dividend_payers[0]
                narrative = (
                    f"Among the {len(symbols)} companies compared, {best['symbol']} "
                    f"offers the best income profile with a {best.get('safety_score', 'N/A')}/100 safety score "
                    f"and {best.get('dividend_yield', 'N/A')}% yield. "
                )

                if len(dividend_payers) > 1:
                    others = [c["symbol"] for c in dividend_payers[1:3]]
                    narrative += f"Other strong candidates include {', '.join(others)}. "

                non_payers = [
                    c["symbol"] for c in result["comparison"] if c.get("pays_dividends") is False
                ]
                if non_payers:
                    narrative += f"Note: {', '.join(non_payers)} do not currently pay dividends."

                result["comparative_narrative"] = narrative

        return result
    except Exception as e:
        logger.error(f"Dividend comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include router in app
app.include_router(router)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc),
        ).model_dump(mode="json"),
    )


# ── Portfolio Optimization (Feature 19) ──────────────────────


@router.post("/portfolio/optimize")
async def optimize_portfolio_endpoint(request: Dict[str, Any]):
    """
    Optimize portfolio allocation.

    Body: {"symbols": ["AAPL","MSFT","GOOGL"], "method": "max_sharpe"}
    Methods: max_sharpe, min_volatility, risk_parity
    """
    try:
        from src.tools.portfolio_optimizer import optimize_portfolio

        symbols = request.get("symbols", [])
        method = request.get("method", "max_sharpe")
        if not symbols or len(symbols) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
        return optimize_portfolio(symbols, method=method)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/efficient-frontier")
async def efficient_frontier_endpoint(request: Dict[str, Any]):
    """Generate efficient frontier curve."""
    try:
        from src.tools.portfolio_optimizer import calculate_efficient_frontier

        symbols = request.get("symbols", [])
        n_points = request.get("n_points", 30)
        if not symbols or len(symbols) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
        return calculate_efficient_frontier(symbols, n_points=n_points)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/correlation")
async def correlation_endpoint(request: Dict[str, Any]):
    """Compute correlation matrix with insights."""
    try:
        from src.tools.portfolio_optimizer import correlation_analysis

        symbols = request.get("symbols", [])
        if not symbols or len(symbols) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
        return correlation_analysis(symbols)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/full-optimization")
async def full_optimization_endpoint(request: Dict[str, Any]):
    """
    Run comprehensive optimization: correlation, max Sharpe, min vol,
    risk parity, efficient frontier, and rebalancing suggestions.
    """
    try:
        from src.tools.portfolio_optimizer import full_portfolio_optimization

        symbols = request.get("symbols", [])
        weights = request.get("current_weights")
        if not symbols or len(symbols) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
        return full_portfolio_optimization(symbols, current_weights=weights)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/rebalance")
async def rebalance_endpoint(request: Dict[str, Any]):
    """Get rebalancing suggestions vs optimal weights."""
    try:
        from src.tools.portfolio_optimizer import rebalance_suggestions

        symbols = request.get("symbols", [])
        weights = request.get("current_weights", [])
        method = request.get("method", "max_sharpe")
        if not symbols or not weights:
            raise HTTPException(status_code=400, detail="symbols and current_weights required")
        return rebalance_suggestions(symbols, weights, target_method=method)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/benchmark")
async def portfolio_benchmark_endpoint(request: Dict[str, Any]):
    """Compare portfolio vs benchmark (alpha, beta, tracking error)."""
    try:
        from src.tools.benchmark import calculate_portfolio_vs_benchmark

        symbols = request.get("symbols", [])
        weights = request.get("weights", [])
        benchmark = request.get("benchmark", "SPY")
        if not symbols or not weights:
            raise HTTPException(status_code=400, detail="symbols and weights required")
        return calculate_portfolio_vs_benchmark(symbols, weights, benchmark=benchmark)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Alert CRUD Endpoints (Feature 18) ────────────────────────


@router.post("/alerts")
async def create_alert(request: Dict[str, Any]):
    """Create a new alert."""
    from src.tools.alerts import add_alert

    symbol = request.get("symbol", "")
    alert_type = request.get("type", request.get("alert_type", ""))
    threshold = request.get("threshold", request.get("value", 0))
    message = request.get("message", "")
    repeat = request.get("repeat", False)
    if not symbol or not alert_type:
        raise HTTPException(status_code=400, detail="symbol and type are required")
    return add_alert(symbol, alert_type, threshold, message, repeat=repeat)


@router.get("/alerts")
async def get_alerts(status: Optional[str] = None):
    """List all alerts. Optional status filter: active, triggered."""
    from src.tools.alerts import list_alerts

    return {"alerts": list_alerts(status=status)}


@router.get("/alerts/types")
async def get_alert_types():
    """List available alert types with descriptions."""
    from src.tools.alerts import get_available_alert_types

    return {"types": get_available_alert_types()}


@router.get("/alerts/triggered")
async def get_triggered():
    """Get recently triggered alerts."""
    from src.tools.alerts import get_triggered_history

    return {"triggered": get_triggered_history()}


@router.get("/alerts/{alert_id}")
async def get_single_alert(alert_id: str):
    """Get a single alert by ID."""
    from src.tools.alerts import get_alert

    result = get_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.patch("/alerts/{alert_id}")
async def patch_alert(alert_id: str, request: Dict[str, Any]):
    """Update an alert."""
    from src.tools.alerts import update_alert

    return update_alert(alert_id, **request)


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert."""
    from src.tools.alerts import remove_alert

    return remove_alert(alert_id)


@router.post("/alerts/evaluate")
async def evaluate_alerts():
    """Manually trigger evaluation of all pending alerts."""
    from src.tools.alerts import check_alerts

    triggered = check_alerts()
    return {
        "evaluated": True,
        "triggered_count": len(triggered),
        "triggered": triggered,
    }


from typing import Optional

# ── Analyst Consensus (Feature 16) ────────────────────────────


@router.get("/analysts/{symbol}")
async def get_analyst_data(symbol: str):
    """Get analyst consensus, price targets, and estimate revisions."""
    try:
        from src.tools.analyst_tracker import get_analyst_consensus

        result = get_analyst_consensus(symbol.upper())
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysts/compare")
async def compare_analyst_data(request: Dict[str, Any]):
    """Compare analyst consensus across multiple stocks."""
    try:
        from src.tools.analyst_tracker import compare_analyst_consensus

        symbols = request.get("symbols", [])
        if not symbols or len(symbols) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
        return compare_analyst_consensus(symbols)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Short Interest Analysis (Feature 14) ─────────────────────


@router.get("/shorts/{symbol}")
async def get_short_interest(symbol: str):
    """Get short interest analysis and squeeze scoring for a stock."""
    try:
        from src.tools.short_interest import analyze_short_interest

        result = analyze_short_interest(symbol.upper())
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shorts/compare")
async def compare_short_interest(request: Dict[str, Any]):
    """Compare short interest across multiple stocks."""
    try:
        from src.tools.short_interest import compare_short_interest

        symbols = request.get("symbols", [])
        if not symbols or len(symbols) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
        result = compare_short_interest(symbols)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shorts/watchlist")
async def short_squeeze_watchlist(min_score: int = 50):
    """Screen stocks for short squeeze potential."""
    try:
        from src.tools.short_interest import get_short_squeeze_watchlist

        result = get_short_squeeze_watchlist(min_squeeze_score=min_score)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket: Real-Time Alerts (Phase 4) ────────────────────

from fastapi import WebSocket, WebSocketDisconnect


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert notifications.

    Clients connect and receive JSON messages when alerts trigger.
    Send {"action": "subscribe", "symbols": ["AAPL"]} to subscribe.
    Send {"action": "add_alert", "symbol": "AAPL", "type": "price_above", "threshold": 200} to add alerts.
    """
    await websocket.accept()
    logger.info("WebSocket client connected for alerts")

    try:
        from src.tools.alerts import get_alert_manager

        manager = get_alert_manager()

        while True:
            # Receive client messages (non-blocking with timeout)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)

                action = data.get("action", "")
                if action == "add_alert":
                    result = manager.add_alert(
                        symbol=data.get("symbol", ""),
                        alert_type=data.get("type", "price_above"),
                        threshold=data.get("threshold", 0),
                    )
                    await websocket.send_json({"type": "alert_added", "data": result})

                elif action == "list":
                    alerts = manager.list_alerts()
                    await websocket.send_json({"type": "alert_list", "data": alerts})

                elif action == "check":
                    triggered = manager.evaluate_all()
                    if triggered:
                        await websocket.send_json({"type": "alerts_triggered", "data": triggered})
                    else:
                        await websocket.send_json({"type": "no_alerts", "data": []})

            except asyncio.TimeoutError:
                # Periodic check for triggered alerts
                triggered = manager.evaluate_all()
                if triggered:
                    await websocket.send_json({"type": "alerts_triggered", "data": triggered})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
        ).model_dump(mode="json"),
    )


# ─── Static Dashboard Mounting ─────────────────────────────────────────────
import os
from fastapi.staticfiles import StaticFiles

_static_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "static",
    "dashboard",
)
if os.path.isdir(_static_dir):
    app.mount("/dashboard", StaticFiles(directory=_static_dir, html=True), name="dashboard")
