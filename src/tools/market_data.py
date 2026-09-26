from datetime import timezone

"""
Market data tools for fetching financial data from various sources.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.data import get_provider
from src.utils.logger import get_logger

logger = get_logger(__name__)


COMMON_TICKER_ALIASES: Dict[str, str] = {
    # Indian Equities & Common Variations
    "RELIANCE": "RELIANCE.NS",
    "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "RIL": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "TATA CONSULTANCY": "TCS.NS",
    "TATA CONSULTANCY SERVICES": "TCS.NS",
    "CANBK": "CANBK.NS",
    "CANARA": "CANBK.NS",
    "CANARA BANK": "CANBK.NS",
    "532483": "CANBK.BO",
    "TATAMOTORS": "TMCV.NS",
    "TATA MOTORS": "TMCV.NS",
    "TMCV": "TMCV.NS",
    "TMPV": "TMPV.NS",
    "RPEL": "RPEL.NS",
    "RAGHAV": "RPEL.NS",
    "RAGHAV PRODUCTIVITY": "RPEL.NS",
    "RAGHAV PRODUCTIVITY ENHANCERS": "RPEL.NS",
    "TIPSMUSIC": "TIPSMUSIC.NS",
    "TIPS": "TIPSMUSIC.NS",
    "TIPS MUSIC": "TIPSMUSIC.NS",
    "VIKRAMSOLAR": "VIKRAMSOLAR.NS",
    "VIKRAM": "VIKRAMSOLAR.NS",
    "VIKRAM SOLAR": "VIKRAMSOLAR.NS",
    "HDFC": "HDFCBANK.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "INFY": "INFY.NS",
    "INFOSYS": "INFY.NS",
    "SBIN": "SBIN.NS",
    "SBI": "SBIN.NS",
    "STATE BANK OF INDIA": "SBIN.NS",
    "ITC": "ITC.NS",
    "ITC LIMITED": "ITC.NS",
    "WIPRO": "WIPRO.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "AIRTEL": "BHARTIARTL.NS",
    "BHARTI AIRTEL": "BHARTIARTL.NS",
    "ICICI": "ICICIBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "KOTAK": "KOTAKBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "KOTAK MAHINDRA BANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "L&T": "LT.NS",
    "LARSEN": "LT.NS",
    "MARUTI": "MARUTI.NS",
    "MARUTI SUZUKI": "MARUTI.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "BAJAJ FINANCE": "BAJFINANCE.NS",
    "ZOMATO": "ETERNAL.NS",
    "ETERNAL": "ETERNAL.NS",
    "PAYTM": "PAYTM.NS",
    "SUZLON": "SUZLON.NS",
    # Global & US Equities
    "APPLE": "AAPL",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "MICROSOFT": "MSFT",
    "TESLA": "TSLA",
    "AMAZON": "AMZN",
    "NVIDIA": "NVDA",
    "NETFLIX": "NFLX",
    "META": "META",
    "FACEBOOK": "META",
    "BERKSHIRE": "BRK-B",
    "BRKB": "BRK-B",
}


def _check_ticker_price(sym: str) -> Optional[float]:
    """Safely check if a ticker symbol yields a valid live price."""
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
        if hasattr(t, "fast_info"):
            try:
                p = t.fast_info.last_price
                if p and p > 0:
                    return float(p)
            except Exception:
                pass
        try:
            inf = t.info or {}
            p = inf.get("currentPrice") or inf.get("regularMarketPrice")
            if p and p > 0:
                return float(p)
        except Exception:
            pass
        try:
            h = t.history(period="5d")
            if not h.empty and "Close" in h:
                c = h["Close"].dropna()
                if len(c) > 0 and float(c.iloc[-1]) > 0:
                    return float(c.iloc[-1])
        except Exception:
            pass
    except Exception:
        pass
    return None


def resolve_ticker_symbol(query: str) -> tuple[Optional[str], Optional[float]]:
    """
    Resolve any user input (ticker or company name) to a valid exchange ticker symbol.
    Supports Indian stocks (NSE .NS, BSE .BO) and US/Global symbols.
    Returns (resolved_symbol, valid_price) or (None, None) if not found.
    """
    if not query or not query.strip():
        return None, None

    clean = query.strip().upper().replace(" ", "").replace("_", "").replace("-", "")
    raw_upper = query.strip().upper()

    # 1. Check known aliases
    if raw_upper in COMMON_TICKER_ALIASES:
        target = COMMON_TICKER_ALIASES[raw_upper]
        p = _check_ticker_price(target)
        if p is not None:
            return target, p

    if clean in COMMON_TICKER_ALIASES:
        target = COMMON_TICKER_ALIASES[clean]
        p = _check_ticker_price(target)
        if p is not None:
            return target, p

    # 2. Try the symbol directly as provided
    p = _check_ticker_price(raw_upper)
    if p is not None:
        return raw_upper, p

    p = _check_ticker_price(clean)
    if p is not None:
        return clean, p

    # 3. If no exchange suffix present, try Indian exchanges (.NS then .BO)
    if "." not in clean:
        p_ns = _check_ticker_price(f"{clean}.NS")
        if p_ns is not None:
            return f"{clean}.NS", p_ns

        p_bo = _check_ticker_price(f"{clean}.BO")
        if p_bo is not None:
            return f"{clean}.BO", p_bo

    return None, None


def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Get current stock price and basic metrics.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dictionary with current price data or error if unidentifiable
    """
    try:
        resolved_sym, verified_price = resolve_ticker_symbol(symbol)
        if not resolved_sym or verified_price is None or verified_price <= 0:
            return {
                "symbol": symbol,
                "current_price": 0,
                "error": (
                    f"Unable to identify company or ticker '{symbol}'. "
                    f"Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, "
                    f"or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks)."
                ),
            }

        provider = get_provider()
        info = provider.get_info(resolved_sym) or {}

        curr_price = (
            verified_price
            or info.get("currentPrice")
            or info.get("regularMarketPrice")
            or 0
        )
        prev_close = info.get("previousClose") or curr_price
        open_price = info.get("open") or info.get("regularMarketOpen") or curr_price
        day_high = info.get("dayHigh") or info.get("regularMarketDayHigh") or curr_price
        day_low = info.get("dayLow") or info.get("regularMarketDayLow") or curr_price
        volume = info.get("volume") or info.get("regularMarketVolume") or 0
        market_cap = info.get("marketCap") or 0

        change = round(curr_price - prev_close, 2) if prev_close else 0.0
        change_pct = (
            round(((curr_price - prev_close) / prev_close) * 100, 2)
            if prev_close and prev_close > 0
            else 0.0
        )

        return {
            "symbol": resolved_sym,
            "raw_symbol": symbol,
            "current_price": curr_price,
            "previous_close": prev_close,
            "open": open_price,
            "day_high": day_high,
            "day_low": day_low,
            "volume": volume,
            "market_cap": market_cap,
            "pe_ratio": info.get("trailingPE", None),
            "eps": info.get("trailingEps", None),
            "52_week_high": info.get("fiftyTwoWeekHigh", day_high),
            "52_week_low": info.get("fiftyTwoWeekLow", day_low),
            "change": change,
            "change_percent": change_pct,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching stock price for {symbol}: {e}")
        return {
            "symbol": symbol,
            "current_price": 0,
            "error": (
                f"Unable to identify company or ticker '{symbol}'. "
                f"Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, "
                f"or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks)."
            ),
        }


def get_historical_data(symbol: str, period: str = "1y") -> Dict[str, Any]:
    """
    Get historical price data for a stock.

    Args:
        symbol: Stock ticker symbol
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        Dictionary with historical OHLCV data
    """
    try:
        resolved_sym, _ = resolve_ticker_symbol(symbol)
        lookup_sym = resolved_sym or symbol
        provider = get_provider()
        hist = provider.get_history(lookup_sym, period=period)

        # The most recent row can come back with OHLC = NaN (volume already posted,
        # prices not yet settled for the session) — most common on NSE/BSE tickers
        # right after close. Drop it rather than serializing NaN into the JSON response.
        hist = hist.dropna(subset=["Open", "High", "Low", "Close"])

        if hist.empty:
            return {
                "symbol": lookup_sym,
                "error": f"No historical data available for {symbol}",
            }

        return {
            "symbol": lookup_sym,
            "period": period,
            "data_points": len(hist),
            "start_date": hist.index[0].strftime("%Y-%m-%d"),
            "end_date": hist.index[-1].strftime("%Y-%m-%d"),
            "opens": hist["Open"].tolist(),
            "highs": hist["High"].tolist(),
            "lows": hist["Low"].tolist(),
            "closes": hist["Close"].tolist(),
            "volumes": hist["Volume"].tolist(),
            "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            "returns": hist["Close"].pct_change().dropna().tolist(),
        }
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


def get_company_info(symbol: str) -> Dict[str, Any]:
    """
    Get detailed company information.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dictionary with company profile
    """
    try:
        resolved_sym, _ = resolve_ticker_symbol(symbol)
        if not resolved_sym:
            return {
                "symbol": symbol,
                "error": (
                    f"Unable to identify company or ticker '{symbol}'. "
                    f"Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, "
                    f"or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks)."
                ),
            }

        provider = get_provider()
        info = provider.get_info(resolved_sym) or {}

        return {
            "symbol": resolved_sym,
            "raw_symbol": symbol,
            "name": info.get("longName", info.get("shortName", resolved_sym)),
            "sector": info.get("sector", "Financials / General"),
            "industry": info.get("industry", "N/A"),
            "description": info.get("longBusinessSummary", "")[:500],
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees", 0),
            "country": info.get("country", ""),
            "city": info.get("city", ""),
            "exchange": info.get("exchange", ""),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap", 0),
            "enterprise_value": info.get("enterpriseValue", 0),
        }
    except Exception as e:
        logger.error(f"Error fetching company info for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


def get_financial_statements(symbol: str) -> Dict[str, Any]:
    """
    Get company financial statements.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dictionary with financial statement data
    """
    try:
        resolved_sym, _ = resolve_ticker_symbol(symbol)
        lookup_sym = resolved_sym or symbol
        provider = get_provider()

        # Get financial statements
        income_stmt = provider.get_income_statement(lookup_sym)
        balance_sheet = provider.get_balance_sheet(lookup_sym)
        cash_flow = provider.get_cash_flow(lookup_sym)

        result: Dict[str, Any] = {"symbol": lookup_sym}

        # Income statement metrics
        if not income_stmt.empty:
            latest = income_stmt.iloc[:, 0]
            result["income_statement"] = {
                "total_revenue": float(latest.get("Total Revenue", 0)),
                "gross_profit": float(latest.get("Gross Profit", 0)),
                "operating_income": float(latest.get("Operating Income", 0)),
                "net_income": float(latest.get("Net Income", 0)),
                "ebitda": float(latest.get("EBITDA", 0)),
            }

        # Balance sheet metrics
        if not balance_sheet.empty:
            latest = balance_sheet.iloc[:, 0]
            result["balance_sheet"] = {
                "total_assets": float(latest.get("Total Assets", 0)),
                "total_liabilities": float(
                    latest.get("Total Liabilities Net Minority Interest", 0)
                ),
                "total_equity": float(latest.get("Total Equity Gross Minority Interest", 0)),
                "cash": float(latest.get("Cash And Cash Equivalents", 0)),
                "total_debt": float(latest.get("Total Debt", 0)),
            }

        # Cash flow metrics
        if not cash_flow.empty:
            latest = cash_flow.iloc[:, 0]
            result["cash_flow"] = {
                "operating_cash_flow": float(latest.get("Operating Cash Flow", 0)),
                "capital_expenditure": float(latest.get("Capital Expenditure", 0)),
                "free_cash_flow": float(latest.get("Free Cash Flow", 0)),
            }

        return result

    except Exception as e:
        logger.error(f"Error fetching financial statements for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


def get_company_dcf_profile(
    symbol: str,
    growth: Optional[float] = None,
    margin: Optional[float] = None,
    beta: Optional[float] = None,
    terminal_g: Optional[float] = None,
    rf: Optional[float] = None,
    erp: Optional[float] = None,
    tax_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute live interactive DCF valuation model with 5-year waterfall,
    WACC decomposition, Enterprise-to-Equity bridge, and 2D Sensitivity matrix.
    """
    import math

    resolved_sym, verified_price = resolve_ticker_symbol(symbol)
    if not resolved_sym or verified_price is None or verified_price <= 0:
        return {
            "error": (
                f"Unable to identify company or ticker '{symbol}'. "
                f"Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, "
                f"or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks)."
            )
        }

    provider = get_provider()
    info = provider.get_info(resolved_sym) or {}
    cmp_price = verified_price or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0

    curr_code = info.get("currency", "USD")
    is_inr = curr_code == "INR" or resolved_sym.endswith(".NS") or resolved_sym.endswith(".BO")
    unit_div = 1e7 if is_inr else 1e6
    unit = "Cr" if is_inr else "M"
    currency = "₹" if is_inr else "$"

    # Revenue
    raw_rev = float(info.get("totalRevenue") or 0)
    if raw_rev <= 0:
        try:
            fin = provider.get_income_statement(resolved_sym)
            if fin is not None and not fin.empty:
                for rev_key in ["Total Revenue", "Operating Revenue", "Gross Revenue"]:
                    if rev_key in fin.index:
                        series = fin.loc[rev_key].dropna()
                        if not series.empty and float(series.iloc[0]) > 0:
                            raw_rev = float(series.iloc[0])
                            break
        except Exception:
            pass

    # If raw_rev is still <= 0, do not fabricate numbers with marketCap * 0.4.
    base_rev = (raw_rev / unit_div) if raw_rev > 0 else 0.0

    # Shares
    raw_shares = float(info.get("sharesOutstanding") or 0)
    if raw_shares <= 0 and cmp_price > 0:
        raw_shares = float(info.get("marketCap") or 0) / cmp_price
    if raw_shares <= 0:
        raw_shares = 100 * unit_div
    shares = max(0.1, raw_shares / unit_div)

    # Debt & Cash
    debt = max(0.0, float(info.get("totalDebt") or 0) / unit_div)
    cash = max(0.0, float(info.get("totalCash") or 0) / unit_div)

    # Parameters (use overrides if provided, else company figures).
    # Track *where* each assumption came from — the financial-analyst rule "state your
    # assumptions before your conclusions" only means something if a reader can tell a
    # company-reported figure apart from a generic fallback guess.
    growth_source = "override" if growth is not None else ("company-reported" if info.get("revenueGrowth") else "sector-default")
    def_growth = float(info.get("revenueGrowth") or 0.12) * 100
    param_growth = float(growth if growth is not None else max(2.0, min(50.0, def_growth)))

    margin_source = "override" if margin is not None else ("company-reported" if info.get("operatingMargins") else "sector-default")
    def_margin = float(info.get("operatingMargins") or 0.15) * 100
    param_margin = float(margin if margin is not None else max(2.0, min(70.0, def_margin)))

    def_beta = float(info.get("beta") or 1.1)
    param_beta = float(beta if beta is not None else max(0.4, min(3.0, def_beta)))

    def_term_g = 4.5 if is_inr else 2.5
    param_term_g = float(terminal_g if terminal_g is not None else def_term_g)

    def_rf = 6.8 if is_inr else 4.2
    param_rf = float(rf if rf is not None else def_rf)

    def_erp = 5.5 if is_inr else 5.0
    param_erp = float(erp if erp is not None else def_erp)

    def_tax = 25.0 if is_inr else 21.0
    param_tax = float(tax_rate if tax_rate is not None else def_tax)

    # D&A / CapEx / NWC as % of revenue: derive from the company's own trailing
    # actuals when available, falling back to generic defaults otherwise.
    da_rate, capex_rate, nwc_rate = 3.0, 4.0, 2.0
    da_rate_source, capex_rate_source, nwc_rate_source = "generic-default", "generic-default", "generic-default"
    if raw_rev > 0:
        try:
            cf = provider.get_cash_flow(resolved_sym)
            if cf is not None and not cf.empty:
                def _pct_of_rev(keys):
                    for k in keys:
                        if k in cf.index:
                            vals = cf.loc[k].dropna()
                            if not vals.empty:
                                return abs(float(vals.iloc[0])) / raw_rev * 100
                    return None

                da_pct = _pct_of_rev(["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation"])
                capex_pct = _pct_of_rev(["Capital Expenditure", "Purchase Of PPE"])
                nwc_pct = _pct_of_rev(["Change In Working Capital"])
                if da_pct:
                    da_rate = max(0.5, min(15.0, da_pct))
                    da_rate_source = "trailing-actual"
                if capex_pct:
                    capex_rate = max(0.5, min(20.0, capex_pct))
                    capex_rate_source = "trailing-actual"
                if nwc_pct is not None:
                    nwc_rate = max(0.0, min(10.0, nwc_pct))
                    nwc_rate_source = "trailing-actual"
        except Exception:
            pass

    # 1. Cost of Capital (WACC)
    ke = param_rf + (param_beta * param_erp)
    kd_pre_tax = param_rf + 2.0
    kd_after_tax = kd_pre_tax * (1 - (param_tax / 100))
    total_cap = debt + (cmp_price * shares)
    we = (cmp_price * shares) / total_cap if total_cap > 0 else 0.85
    wd = 1.0 - we
    wacc = (we * ke) + (wd * kd_after_tax)
    wacc_dec = max(0.04, wacc / 100)
    g_dec = param_term_g / 100

    g_steps = [
        param_term_g - 1.0,
        param_term_g - 0.5,
        param_term_g,
        param_term_g + 0.5,
        param_term_g + 1.0,
    ]
    wacc_steps = [wacc - 1.5, wacc - 0.75, wacc, wacc + 0.75, wacc + 1.5]

    years = [1, 2, 3, 4, 5]

    def _project(growth_pct: float, margin_pct: float, term_g_pct: float):
        """Run the 5-year FCF waterfall + terminal value + EV-to-equity bridge for a
        given growth/margin/terminal-growth trio. Shared by the base case and the
        bull/bear scenarios below so all three use one, tested code path."""
        curr_r = base_rev
        fc = []
        pv_sum = 0.0
        for y in years:
            curr_r = curr_r * (1 + (growth_pct / 100))
            ebit = curr_r * (margin_pct / 100)
            tax = ebit * (param_tax / 100)
            nopat = ebit - tax
            da = curr_r * (da_rate / 100)
            capex = curr_r * (capex_rate / 100)
            nwc = curr_r * (nwc_rate / 100)
            fcf = nopat + da - capex - nwc
            discount_factor = 1.0 / math.pow(1.0 + wacc_dec, y)
            pv_fcf = fcf * discount_factor
            pv_sum += pv_fcf
            fc.append({
                "year": y, "rev": round(curr_r, 2), "ebit": round(ebit, 2),
                "nopat": round(nopat, 2), "da": round(da, 2), "capex": round(capex, 2),
                "nwc": round(nwc, 2), "fcf": round(fcf, 2), "df": round(discount_factor, 4),
                "pv": round(pv_fcf, 2),
            })
        fcf_last = fc[-1]["fcf"]
        g_d = term_g_pct / 100
        denom = max(0.01, wacc_dec - g_d)
        tv = (fcf_last * (1 + g_d)) / denom
        pv_tv = tv / math.pow(1.0 + wacc_dec, 5)
        ev = pv_sum + pv_tv
        eq = ev - debt + cash
        fv = max(0.0, eq / shares) if shares > 0 else 0.0
        return fc, pv_sum, tv, pv_tv, ev, eq, fv

    if base_rev <= 0:
        # Zero-revenue company (shell, pre-revenue, or non-operational)
        forecast = []
        for y in years:
            discount_factor = 1.0 / math.pow(1.0 + wacc_dec, y)
            forecast.append({
                "year": y,
                "rev": 0.0,
                "ebit": 0.0,
                "nopat": 0.0,
                "da": 0.0,
                "capex": 0.0,
                "nwc": 0.0,
                "fcf": 0.0,
                "df": round(discount_factor, 4),
                "pv": 0.0,
            })
        total_pv_fcf = 0.0
        terminal_value = 0.0
        pv_terminal_value = 0.0
        enterprise_value = 0.0
        equity_value = cash - debt
        fair_value = max(0.0, equity_value / shares) if shares > 0 else 0.0
        gap_pct = ((fair_value - cmp_price) / cmp_price * 100) if cmp_price > 0 else -100.0
        verdict = "Distressed / Insolvent (No Active Operations)" if equity_value <= 0 else "Pre-Revenue (Net Asset Backing)"
        matrix = [[round(fair_value, 2)] * 5 for _ in range(5)]
        # No active operations to flex a bull/bear case around — all three collapse
        # to the same net-asset-backing figure.
        scenarios = {
            "bull": {"growth": 0.0, "margin": 0.0, "fair_value_per_share": round(fair_value, 2), "upside_pct": round(gap_pct, 1)},
            "base": {"growth": 0.0, "margin": 0.0, "fair_value_per_share": round(fair_value, 2), "upside_pct": round(gap_pct, 1)},
            "bear": {"growth": 0.0, "margin": 0.0, "fair_value_per_share": round(fair_value, 2), "upside_pct": round(gap_pct, 1)},
        }
        probability_weighted_fair_value = round(fair_value, 2)
    else:
        # 2-4. Base case: 5-year FCF waterfall, terminal value, EV-to-equity bridge
        forecast, total_pv_fcf, terminal_value, pv_terminal_value, enterprise_value, equity_value, fair_value = _project(
            param_growth, param_margin, param_term_g
        )
        fcf5 = forecast[-1]["fcf"]
        gap_pct = ((fair_value - cmp_price) / cmp_price * 100) if cmp_price > 0 else 0.0
        verdict = "Undervalued (Upside)" if gap_pct >= 0 else "Overvalued (Caution)"

        # 5. Sensitivity Matrix (5x5) — WACC vs terminal growth, base-case operating assumptions
        matrix = []
        for w in wacc_steps:
            row = []
            w_dec = max(0.03, w / 100)
            for g in g_steps:
                g_d = g / 100
                denom_s = max(0.01, w_dec - g_d)
                pv_f = sum(f["fcf"] / math.pow(1 + w_dec, f["year"]) for f in forecast)
                tv_s = (fcf5 * (1 + g_d)) / denom_s
                pv_tv_s = tv_s / math.pow(1 + w_dec, 5)
                ev_s = pv_f + pv_tv_s
                eq_s = ev_s - debt + cash
                fv_s = max(0.0, eq_s / shares) if shares > 0 else 0.0
                row.append(round(fv_s, 2))
            matrix.append(row)

        # 6. Bull / Base / Bear scenario table (financial-analyst rule: never present a
        # single-point forecast; investment-researcher rule: quantify the downside).
        # Growth and margin — the two operational levers a reader can actually reason
        # about — are flexed; WACC and the discount mechanics stay fixed so the three
        # cases are comparable apples-to-apples.
        bull_growth = min(60.0, param_growth * 1.3 + 2.0)
        bull_margin = min(75.0, param_margin + 3.0)
        bull_term_g = min(param_term_g + 0.5, wacc - 1.0) if wacc > 1.0 else param_term_g
        _, _, _, _, _, _, bull_fv = _project(bull_growth, bull_margin, bull_term_g)

        bear_growth = max(0.0, param_growth * 0.5 - 2.0)
        bear_margin = max(1.0, param_margin - 3.0)
        bear_term_g = max(0.0, param_term_g - 0.5)
        _, _, _, _, _, _, bear_fv = _project(bear_growth, bear_margin, bear_term_g)

        scenarios = {
            "bull": {
                "growth": round(bull_growth, 1), "margin": round(bull_margin, 1), "terminal_g": round(bull_term_g, 2),
                "fair_value_per_share": round(bull_fv, 2), "weight": 0.25,
                "upside_pct": round(((bull_fv - cmp_price) / cmp_price * 100) if cmp_price > 0 else 0.0, 1),
            },
            "base": {
                "growth": round(param_growth, 1), "margin": round(param_margin, 1), "terminal_g": round(param_term_g, 2),
                "fair_value_per_share": round(fair_value, 2), "weight": 0.50,
                "upside_pct": round(gap_pct, 1),
            },
            "bear": {
                "growth": round(bear_growth, 1), "margin": round(bear_margin, 1), "terminal_g": round(bear_term_g, 2),
                "fair_value_per_share": round(bear_fv, 2), "weight": 0.25,
                "upside_pct": round(((bear_fv - cmp_price) / cmp_price * 100) if cmp_price > 0 else 0.0, 1),
            },
        }
        probability_weighted_fair_value = round(0.25 * bull_fv + 0.50 * fair_value + 0.25 * bear_fv, 2)

    company_name = info.get("longName") or info.get("shortName") or resolved_sym

    return {
        "symbol": resolved_sym,
        "name": company_name,
        "currency": currency,
        "currency_code": curr_code,
        "currencyCode": curr_code,
        "unit": unit,
        "cmp": round(cmp_price, 2),
        "base_revenue": round(base_rev, 2),
        # Rounded to 4dp, not the 1-2dp used elsewhere for display: the interactive
        # DCF page feeds these numbers straight back into its own client-side
        # recompute engine, so rounding them for display here would silently make
        # every slider-driven recalculation less precise than the server's own.
        "growth": round(param_growth, 4),
        "margin": round(param_margin, 4),
        "beta": round(param_beta, 4),
        "terminal_g": round(param_term_g, 4),
        "rf": round(param_rf, 4),
        "erp": round(param_erp, 4),
        "tax_rate": round(param_tax, 1),
        "da_rate": da_rate,
        "capex_rate": capex_rate,
        "nwc_rate": nwc_rate,
        "debt": round(debt, 2),
        "cash": round(cash, 2),
        "shares": round(shares, 2),
        "wacc": round(wacc, 2),
        "ke": round(ke, 2),
        "kd_after_tax": round(kd_after_tax, 2),
        "we": round(we, 3),
        "wd": round(wd, 3),
        "fair_value_per_share": round(fair_value, 2),
        "upside_pct": round(gap_pct, 1),
        "verdict": verdict,
        "forecast": forecast,
        "total_pv_fcf": round(total_pv_fcf, 2),
        "terminal_value": round(terminal_value, 2),
        "pv_terminal_value": round(pv_terminal_value, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "sensitivity_wacc_steps": [round(w, 2) for w in wacc_steps],
        "sensitivity_g_steps": [round(g, 1) for g in g_steps],
        "sensitivity_matrix": matrix,
        "scenarios": scenarios,
        "probability_weighted_fair_value": probability_weighted_fair_value,
        "assumption_sources": {
            "growth": growth_source,
            "margin": margin_source,
            "da_rate": da_rate_source,
            "capex_rate": capex_rate_source,
            "nwc_rate": nwc_rate_source,
        },
    }


def get_company_ratios_profile(symbol: str) -> Dict[str, Any]:
    """
    Compute comprehensive 16-point financial ratios profile for multi-segment analysis.
    """
    resolved_sym, verified_price = resolve_ticker_symbol(symbol)
    if not resolved_sym or verified_price is None or verified_price <= 0:
        return {
            "error": (
                f"Unable to identify company or ticker '{symbol}'. "
                f"Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, "
                f"or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks)."
            )
        }

    provider = get_provider()
    info = provider.get_info(resolved_sym) or {}
    cmp_price = verified_price or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0

    curr_code = info.get("currency", "USD")
    is_inr = curr_code == "INR" or resolved_sym.endswith(".NS") or resolved_sym.endswith(".BO")
    curr_sym = "₹" if is_inr else "$"
    name = info.get("longName") or info.get("shortName") or resolved_sym
    sector = info.get("sector", "General")

    # Metrics extraction
    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    ev_ebitda = info.get("enterpriseToEbitda")
    div_yield = info.get("dividendYield")
    roe = info.get("returnOnEquity")
    opm = info.get("operatingMargins")
    npm = info.get("profitMargins")
    de = info.get("debtToEquity")
    rev_growth = info.get("revenueGrowth")
    earn_growth = info.get("earningsGrowth")
    fcf = info.get("freeCashflow")

    # Deep balance sheet and financials inspection (via the configured provider,
    # so a non-default DATA_PROVIDER is honored instead of silently ignored)
    bs_df = provider.get_balance_sheet(resolved_sym)
    fin_df = provider.get_income_statement(resolved_sym)
    bs = bs_df if bs_df is not None and not bs_df.empty else None
    fin = fin_df if fin_df is not None and not fin_df.empty else None

    def _first_row(df, keys):
        """First non-null value (most recent period) for the first matching row label."""
        if df is None:
            return None
        for k in keys:
            if k in df.index:
                try:
                    vals = df.loc[k].dropna()
                    if len(vals) > 0:
                        return float(vals.iloc[0])
                except Exception:
                    continue
        return None

    stockholders_equity = _first_row(bs, ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest'])
    total_debt_bs = _first_row(bs, ['Total Debt', 'Long Term Debt And Capital Lease Obligation', 'Long Term Debt'])

    # Shared fundamentals for ROCE / Interest Coverage / Altman Z / CCC below
    ebit_val = _first_row(fin, ["EBIT", "Operating Income"])
    total_assets_val = _first_row(bs, ["Total Assets"])
    current_assets_val = _first_row(bs, ["Current Assets"])
    current_liabilities_val = _first_row(bs, ["Current Liabilities"])
    total_liabilities_val = _first_row(bs, ["Total Liabilities Net Minority Interest", "Total Liab"])
    retained_earnings_val = _first_row(bs, ["Retained Earnings"])
    revenue_val = _first_row(fin, ["Total Revenue", "Operating Revenue"])
    interest_expense_val = _first_row(fin, ["Interest Expense"])
    inventory_val = _first_row(bs, ["Inventory"])
    receivables_val = _first_row(bs, ["Accounts Receivable", "Receivables"])
    payables_val = _first_row(bs, ["Accounts Payable", "Payables"])
    cogs_val = _first_row(fin, ["Cost Of Revenue", "Reconciled Cost Of Revenue"])
    if cogs_val is None and revenue_val is not None:
        gross_profit_val = _first_row(fin, ["Gross Profit"])
        if gross_profit_val is not None:
            cogs_val = revenue_val - gross_profit_val
    market_cap_val = info.get("marketCap") or (cmp_price * float(info.get("sharesOutstanding") or 0))

    # Return on Capital Employed = EBIT / (Total Assets - Current Liabilities)
    capital_employed = (
        total_assets_val - current_liabilities_val
        if total_assets_val is not None and current_liabilities_val is not None
        else None
    )
    if ebit_val is not None and capital_employed and capital_employed > 0:
        roce_val = (ebit_val / capital_employed) * 100
        roce_str = f"{roce_val:.1f}%"
        roce_pill = "good" if roce_val > 15 else ("caution" if roce_val > 8 else "danger")
        roce_exp = f"Return on capital employed of {roce_str} (EBIT ÷ [Total Assets − Current Liabilities])."
    else:
        roce_str = "N/A"
        roce_pill = "caution"
        roce_exp = "Return on capital employed not available (insufficient balance sheet data)."

    # Interest Coverage Ratio = EBIT / Interest Expense
    if ebit_val is not None and interest_expense_val:
        icr_val = ebit_val / abs(interest_expense_val)
        icr_str = f"{icr_val:.1f}x"
        icr_pill = "good" if icr_val > 5 else ("caution" if icr_val > 1.5 else "danger")
        icr_exp = f"EBIT covers interest expense {icr_str} (EBIT ÷ Interest Expense)."
    elif ebit_val is not None and ebit_val < 0:
        icr_str = "< 0 (Deficit)"
        icr_pill = "danger"
        icr_exp = "Negative operating income; operations cannot cover financing costs."
    else:
        icr_str = "N/A"
        icr_pill = "caution"
        icr_exp = "Interest coverage ratio not available (interest expense not reported)."

    # Altman Z-Score = 1.2*(WC/TA) + 1.4*(RE/TA) + 3.3*(EBIT/TA) + 0.6*(MVE/TL) + 1.0*(Sales/TA)
    if (
        total_assets_val and total_assets_val > 0
        and current_assets_val is not None
        and current_liabilities_val is not None
        and retained_earnings_val is not None
        and ebit_val is not None
        and total_liabilities_val and total_liabilities_val > 0
        and revenue_val is not None
    ):
        working_capital = current_assets_val - current_liabilities_val
        altman_z = (
            1.2 * (working_capital / total_assets_val)
            + 1.4 * (retained_earnings_val / total_assets_val)
            + 3.3 * (ebit_val / total_assets_val)
            + 0.6 * ((market_cap_val or 0) / total_liabilities_val)
            + 1.0 * (revenue_val / total_assets_val)
        )
        altman_str = f"{altman_z:.2f}"
        altman_pill = "good" if altman_z > 2.99 else ("caution" if altman_z > 1.81 else "danger")
        altman_exp = (
            f"Altman Z-Score of {altman_str}: "
            + ("Safe zone, low near-term bankruptcy risk." if altman_z > 2.99
               else "Grey zone, moderate financial distress risk." if altman_z > 1.81
               else "Distress zone, elevated bankruptcy risk.")
        )
    else:
        altman_str = "N/A"
        altman_pill = "caution"
        altman_exp = "Altman Z-Score not available (insufficient statement data)."

    # Cash Conversion Cycle = DIO + DSO - DPO
    if (
        cogs_val and cogs_val > 0 and revenue_val and revenue_val > 0
        and inventory_val is not None and receivables_val is not None and payables_val is not None
    ):
        dio = (inventory_val / cogs_val) * 365
        dso = (receivables_val / revenue_val) * 365
        dpo = (payables_val / cogs_val) * 365
        ccc_val = dio + dso - dpo
        ccc_str = f"{ccc_val:.0f} Days"
        ccc_pill = "good" if ccc_val < 60 else ("caution" if ccc_val < 120 else "danger")
        ccc_exp = f"Cash conversion cycle of {ccc_str} (DIO {dio:.0f} + DSO {dso:.0f} − DPO {dpo:.0f})."
    else:
        ccc_str = "N/A"
        ccc_pill = "caution"
        ccc_exp = "Cash conversion cycle not available (inventory/receivables/payables not reported)."

    # P/E
    pe_str = f"{float(pe):.1f}x" if pe else "N/A"
    pe_pill = "good" if pe and float(pe) < 25 else ("caution" if pe and float(pe) < 45 else "danger")
    pe_exp = f"Trading at {pe_str} earnings. {'Attractive multiple' if pe_pill == 'good' else ('Loss-making company' if not pe else 'Growth premium priced in')}."

    # P/B Ratio (Handle Negative P/B for eroded net worth)
    if pb is not None:
        try:
            pb_num = float(pb)
            pb_str = f"{pb_num:.2f}x"
            if pb_num < 0:
                pb_pill = "danger"
                pb_exp = f"Negative P/B ratio ({pb_str}) indicates complete net worth erosion (accumulated losses exceed equity capital)."
            elif pb_num < 3.0:
                pb_pill = "good"
                pb_exp = f"Price to book of {pb_str}. Reasonable asset valuation."
            elif pb_num < 8.0:
                pb_pill = "caution"
                pb_exp = f"Price to book of {pb_str}. Valuation premium."
            else:
                pb_pill = "danger"
                pb_exp = f"Price to book of {pb_str}. Extremely elevated multiple."
        except Exception:
            pb_str = "N/A"
            pb_pill = "caution"
            pb_exp = "Price to book ratio not available."
    else:
        pb_str = "N/A"
        pb_pill = "caution"
        pb_exp = "Price to book ratio not available."

    # EV / EBITDA
    ev_str = f"{float(ev_ebitda):.1f}x" if ev_ebitda else "N/A"
    ev_pill = "good" if ev_ebitda and 0 < float(ev_ebitda) < 15 else ("caution" if ev_ebitda and float(ev_ebitda) < 30 else "danger")
    ev_exp = f"Enterprise multiple of {ev_str}."

    # Dividend Yield
    # yfinance reports dividendYield already as a percentage value (e.g. 0.32 == 0.32%),
    # not a fraction — multiplying by 100 here previously inflated every yield 100x.
    div_str = f"{float(div_yield):.2f}%" if div_yield else "0.0%"
    div_pill = "good" if div_yield and float(div_yield) > 1.0 else "caution"
    div_exp = f"Annual dividend yield of {div_str}."

    # Net Worth & Solvency evaluation
    has_negative_equity = (stockholders_equity is not None and stockholders_equity <= 0) or (pb is not None and float(pb) < 0)

    if has_negative_equity:
        de_str = "Capital Eroded"
        de_pill = "danger"
        debt_num = total_debt_bs or info.get("totalDebt", 0.0)
        debt_disp = f"{curr_sym}{debt_num / (1e7 if is_inr else 1e6):,.1f} {('Cr' if is_inr else 'M')}"
        eq_disp = f"{curr_sym}{stockholders_equity / (1e7 if is_inr else 1e6):,.1f} {('Cr' if is_inr else 'M')}" if stockholders_equity else "Negative"
        de_exp = f"Extremely distressed: company has total debt of {debt_disp} against eroded negative net worth ({eq_disp})."

        roe_str = "N/A"
        roe_pill = "danger"
        roe_exp = "Return on equity is not meaningful due to negative shareholder net worth."

        opm_str = f"{(float(opm) * 100):.1f}%" if opm and float(opm) > 0 else "N/A"
        opm_pill = "caution" if opm and float(opm) > 0 else "danger"
        opm_exp = "Operating margin on residual non-core activity."

        npm_str = f"{(float(npm) * 100):.1f}%" if npm and float(npm) != 0 else "Negative"
        npm_pill = "danger"
        npm_exp = "Recurring bottom-line net deficit."
    else:
        # Solvent / positive net worth.
        # yfinance's debtToEquity is always a percentage value (e.g. 1.408 == 1.408%),
        # never a raw ratio — dividing only "when it looked too big" left small-debt
        # companies (ratio < 0.05) showing a leverage figure 100x too high.
        if de is not None:
            de_val = float(de) / 100
        elif total_debt_bs is not None and stockholders_equity is not None and stockholders_equity > 0:
            de_val = total_debt_bs / stockholders_equity
        else:
            de_val = None

        if de_val is not None:
            de_str = f"{de_val:.2f}"
            de_pill = "good" if de_val < 0.8 else ("caution" if de_val < 1.5 else "danger")
            de_exp = f"Debt-to-equity ratio of {de_str}. {'Low financial leverage' if de_pill == 'good' else 'Elevated borrowing'}."
        else:
            de_str = "N/A"
            de_pill = "caution"
            de_exp = "Debt-to-equity ratio not reported."

        if roe is not None:
            roe_val = float(roe) * 100
            roe_str = f"{roe_val:.1f}%"
            roe_pill = "good" if roe_val > 15 else ("caution" if roe_val > 8 else "danger")
            roe_exp = f"Return on equity is {roe_str}."
        else:
            roe_str = "N/A"
            roe_pill = "caution"
            roe_exp = "Return on equity data not reported."

        opm_str = f"{(float(opm) * 100):.1f}%" if opm else "N/A"
        opm_pill = "good" if opm and float(opm) > 0.15 else "caution"
        opm_exp = f"Operating profit margin of {opm_str}."

        npm_str = f"{(float(npm) * 100):.1f}%" if npm else "N/A"
        npm_pill = "good" if npm and float(npm) > 0.08 else "caution"
        npm_exp = f"Net profit margin of {npm_str}."

    # Current Ratio (Liquidity & Distorted Working Capital Safeguard)
    cr_val = info.get("currentRatio")
    cr_num = None
    if cr_val is not None:
        try:
            cr_num = float(cr_val)
        except Exception:
            pass
    if cr_num is None and bs is not None and "Current Assets" in bs.index and "Current Liabilities" in bs.index:
        try:
            ca = float(bs.loc["Current Assets"].dropna().iloc[0])
            cl = float(bs.loc["Current Liabilities"].dropna().iloc[0])
            if cl > 0:
                cr_num = ca / cl
        except Exception:
            pass

    if cr_num is not None:
        cr_str = f"{cr_num:.2f}"
        if has_negative_equity and cr_num > 3.0:
            cr_pill = "caution"
            cr_exp = f"Ratio is distorted ({cr_str}x) due to negligible current trade liabilities rather than liquidity strength. Long-term debt overhang persists."
        elif cr_num > 6.0:
            cr_pill = "caution"
            cr_exp = f"Unusually high ratio ({cr_str}x) indicates either inefficient cash management or minimal short-term trade operations."
        elif 1.3 <= cr_num <= 3.0:
            cr_pill = "good"
            cr_exp = f"Healthy current liquidity ratio of {cr_str}."
        elif 1.0 <= cr_num < 1.3:
            cr_pill = "caution"
            cr_exp = f"Tight working capital buffer of {cr_str}."
        else:
            cr_pill = "danger"
            cr_exp = f"Weak liquidity ratio of {cr_str}. Potential difficulty meeting short-term obligations."
    else:
        cr_str = "N/A"
        cr_pill = "caution"
        cr_exp = "Current liquidity ratio not reported."

    # Free Cash Flow
    if fcf is not None and float(fcf) != 0:
        fcf_num = float(fcf)
        fcf_str = f"{curr_sym}{fcf_num / (1e7 if is_inr else 1e6):,.1f} {('Cr' if is_inr else 'M')}"
        fcf_pill = "good" if fcf_num > 0 else "danger"
        fcf_exp = f"{'Positive' if fcf_num > 0 else 'Negative'} recurring free cash flow from operations."
    else:
        fcf_str = "N/A"
        fcf_pill = "caution"
        fcf_exp = "Free cash flow data not available or zero."

    # Revenue Growth
    if rev_growth is not None:
        sales_val = float(rev_growth) * 100
        sales_str = f"{sales_val:+.1f}%"
        sales_pill = "good" if sales_val > 15 else ("caution" if sales_val > 0 else "danger")
        sales_exp = f"Top-line revenue trend is {sales_str} year-over-year."
    else:
        if fin is not None and ("Total Revenue" in fin.index or "Operating Revenue" in fin.index):
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else fin.loc["Operating Revenue"]
            rev_vals = rev_row.dropna()
            if len(rev_vals) > 0 and rev_vals.iloc[0] == 0:
                sales_str = "0.0% (No Ops)"
                sales_pill = "danger"
                sales_exp = "Company has zero active operational revenue reported."
            else:
                sales_str = "N/A"
                sales_pill = "caution"
                sales_exp = "Revenue growth CAGR data not reported."
        else:
            sales_str = "N/A"
            sales_pill = "caution"
            sales_exp = "Revenue growth CAGR data not reported."

    # Earnings Growth
    if earn_growth is not None:
        profit_val = float(earn_growth) * 100
        profit_str = f"{profit_val:+.1f}%"
        profit_pill = "good" if profit_val > 15 else ("caution" if profit_val > 0 else "danger")
        profit_exp = f"Earnings trajectory of {profit_str}."
    else:
        if has_negative_equity:
            profit_str = "Loss-Making"
            profit_pill = "danger"
            profit_exp = "Company has recurring net losses and negative earnings."
        else:
            profit_str = "N/A"
            profit_pill = "caution"
            profit_exp = "Profit growth CAGR data not reported."

    # Cash Conversion Cycle (CCC) was already computed from real statement data above;
    # only override it for companies confirmed to have no active operations.
    if has_negative_equity or sales_str.startswith("0.0%"):
        ccc_str = "N/A (No Ops)"
        ccc_pill = "caution"
        ccc_exp = "No operational inventory or receivable turnover due to inactive operations."

    # Data confidence: investment-researcher rule — "disclose your confidence level".
    # A verdict built on 6 of 16 available metrics deserves a different level of trust
    # than one built on 15 of 16, and the reader should see that at a glance.
    metric_values = [pe_str, pb_str, ev_str, div_str, roe_str, roce_str, opm_str, npm_str,
                      de_str, icr_str, cr_str, altman_str, fcf_str, sales_str, profit_str, ccc_str]
    available = sum(1 for v in metric_values if v not in ("N/A",) and not str(v).startswith("N/A"))
    confidence_pct = round(available / len(metric_values) * 100, 0)
    confidence_label = "High" if confidence_pct >= 75 else ("Medium" if confidence_pct >= 50 else "Low")

    return {
        "symbol": resolved_sym,
        "title": f"{name} ({curr_sym}{cmp_price:,.2f})",
        "subtitle": f"Sector: {sector} • Currency: {curr_code} ({curr_sym})",
        "pe": pe_str, "pePill": pe_pill, "peExplain": pe_exp,
        "pb": pb_str, "pbPill": pb_pill, "pbExplain": pb_exp,
        "ev": ev_str, "evPill": ev_pill, "evExplain": ev_exp,
        "div": div_str, "divPill": div_pill, "divExplain": div_exp,
        "roe": roe_str, "roePill": roe_pill, "roeExplain": roe_exp,
        "roce": roce_str, "rocePill": roce_pill, "roceExplain": roce_exp,
        "opm": opm_str, "opmPill": opm_pill, "opmExplain": opm_exp,
        "npm": npm_str, "npmPill": npm_pill, "npmExplain": npm_exp,
        "de": de_str, "dePill": de_pill, "deExplain": de_exp,
        "icr": icr_str, "icrPill": icr_pill, "icrExplain": icr_exp,
        "cr": cr_str, "crPill": cr_pill, "crExplain": cr_exp,
        "altman": altman_str, "altmanPill": altman_pill, "altmanExplain": altman_exp,
        "fcf": fcf_str, "fcfPill": fcf_pill, "fcfExplain": fcf_exp,
        "sales": sales_str, "salesPill": sales_pill, "salesExplain": sales_exp,
        "profit": profit_str, "profitPill": profit_pill, "profitExplain": profit_exp,
        "ccc": ccc_str, "cccPill": ccc_pill, "cccExplain": ccc_exp,
        "dataConfidence": {
            "score_pct": confidence_pct,
            "label": confidence_label,
            "note": f"{available} of {len(metric_values)} ratios available from reported financials.",
        },
    }
