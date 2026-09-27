from datetime import timezone

"""
Market data tools for fetching financial data from various sources.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
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
            verified_price or info.get("currentPrice") or info.get("regularMarketPrice") or 0
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


def _beta_vs_index(provider, symbol: str, index: str) -> Optional[float]:
    """Beta of `symbol` against `index` from two years of weekly returns.

    Returns None when there isn't at least a year of overlapping weeks, so callers
    fall back to the provider's own beta rather than trusting a thin regression.
    """
    try:
        import pandas as pd

        stock = provider.get_history(symbol, period="2y", interval="1wk")["Close"]
        market = provider.get_history(index, period="2y", interval="1wk")["Close"]
        rets = pd.concat([stock.pct_change(), market.pct_change()], axis=1, join="inner").dropna()
        if len(rets) < 52:
            return None
        var = rets.iloc[:, 1].var()
        return float(rets.iloc[:, 0].cov(rets.iloc[:, 1]) / var) if var > 0 else None
    except Exception:
        return None


_DAMODARAN = None
_INDUSTRY_INDEX = None
_CONFIG = Path(__file__).resolve().parents[2] / "config"


def _damodaran() -> Dict[str, Any]:
    """Damodaran's country, industry and synthetic-rating data (config/damodaran.json)."""
    global _DAMODARAN
    if _DAMODARAN is None:
        _DAMODARAN = json.loads((_CONFIG / "damodaran.json").read_text(encoding="utf-8"))
    return _DAMODARAN


def _norm_name(name: str) -> str:
    """'Taiwan Semiconductor Manufacturing Company Limited (TWSE:2330)' -> match key."""
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\s*\([^)]*\)\s*$", "", name).lower()).strip()


def _industry_of(symbol: str, name: Optional[str] = None) -> Optional[str]:
    """Damodaran's industry for a Yahoo symbol, from his company classification (indname).

    ADRs (e.g. TSM) are listed under their home ticker (TWSE:2330), so an unmatched
    symbol falls back to the company name against his non-US listings.
    """
    global _INDUSTRY_INDEX
    if _INDUSTRY_INDEX is None:
        import gzip

        with gzip.open(
            _CONFIG / "damodaran_industry_by_ticker.json.gz", "rt", encoding="utf-8"
        ) as fh:
            _INDUSTRY_INDEX = json.load(fh)
    i = _INDUSTRY_INDEX["by_ticker"].get(symbol)
    if i is None and name:
        i = _INDUSTRY_INDEX["by_name"].get(_norm_name(name))
    return None if i is None else _INDUSTRY_INDEX["industries"][i]


US_RISKFREE_FALLBACK = 0.0458  # workbook's Feb 2026 value, used if ^TNX is unavailable
_SUBUNITS = {"GBp": ("GBP", 0.01), "ILA": ("ILS", 0.01), "ZAc": ("ZAR", 0.01)}  # quoted in cents
_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
    "GBp": "GBp ",
    "JPY": "¥",
    "CNY": "¥",
    "HKD": "HK$",
    "TWD": "NT$",
    "KRW": "₩",
    "CAD": "C$",
    "AUD": "A$",
}
# Local market index for regression betas: Yahoo's own beta for non-US listings is not
# measured against the home market (e.g. Reliance 0.15 vs ~1.1 against the Nifty 50).
_LOCAL_INDEX = {
    ".NS": "^NSEI",
    ".BO": "^BSESN",
    ".T": "^N225",
    ".HK": "^HSI",
    ".L": "^FTSE",
    ".DE": "^GDAXI",
    ".PA": "^FCHI",
    ".TO": "^GSPTSE",
    ".AX": "^AXJO",
    ".TW": "^TWII",
    ".KS": "^KS11",
    ".SS": "000001.SS",
    ".SZ": "399001.SZ",
}
_COUNTRY_ALIASES = {"South Korea": "Korea"}


def _usd_per(provider, code: str) -> Optional[float]:
    """USD value of one unit of `code` at the spot rate (handles pence-quoted listings)."""
    base, mult = _SUBUNITS.get(code, (code, 1.0))
    if base == "USD":
        return mult
    rate = (provider.get_info(f"{base}USD=X") or {}).get("regularMarketPrice")
    return float(rate) * mult if rate else None


def _fx_drift(provider, code: str) -> Optional[float]:
    """Annualized change in USD per unit of `code` over ~5 years (0 for USD).

    Used as the inflation differential (purchasing-power parity) that converts local
    nominal growth into USD growth — smoother than any single year's currency swing.
    """
    if _SUBUNITS.get(code, (code,))[0] == "USD":
        return 0.0
    try:
        hist = provider.get_history(f"{code}USD=X", period="5y", interval="1mo")["Close"].dropna()
        years = (hist.index[-1] - hist.index[0]).days / 365.25
        return float((hist.iloc[-1] / hist.iloc[0]) ** (1 / years) - 1) if years >= 1 else None
    except Exception:
        return None


# Same User-Agent as src/rag/ingester.py (SEC requires one). Not imported from there
# because that module loads ChromaDB, which the slim Vercel install doesn't have.
SEC_HEADERS = {"User-Agent": "FinancialResearchAgent/1.0 (research@example.com)"}
_SEC_CIKS: Optional[Dict[str, int]] = None


def _fiscal_year(date) -> int:
    """Fiscal-year label that lines up with SEC XBRL frames (NVDA's Jan-2026 year = 2025)."""
    import pandas as pd

    return (pd.Timestamp(date) - pd.Timedelta(days=182)).year


def _sec_rd_by_year(symbol: str, currency: str) -> Dict[int, float]:
    """Annual R&D by fiscal year from SEC XBRL (10-K and 20-F filers, incl. ADRs like TSM).

    yfinance only carries ~4 years; EDGAR has 10-20, enough for Damodaran's full
    amortizable life. Empty on any failure (non-SEC filer, network, other currency).
    """
    global _SEC_CIKS
    if "." in symbol:  # SEC filers trade on US exchanges; suffixed symbols are local listings
        return {}
    try:
        import httpx

        if _SEC_CIKS is None:
            r = httpx.get(
                "https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=10
            )
            _SEC_CIKS = {v["ticker"].upper(): int(v["cik_str"]) for v in r.json().values()}
        cik = _SEC_CIKS.get(symbol.upper())
        if not cik:
            return {}
        for taxonomy in ("us-gaap", "ifrs-full"):
            r = httpx.get(
                f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{taxonomy}/"
                "ResearchAndDevelopmentExpense.json",
                headers=SEC_HEADERS,
                timeout=10,
            )
            if r.status_code == 200:
                return {
                    int(x["frame"][2:]): float(x["val"])
                    for x in r.json()["units"].get(currency, [])
                    if x.get("fp") == "FY"
                    and x.get("form") in ("10-K", "20-F")
                    and len(x.get("frame", "")) == 6
                }
    except Exception:
        pass
    return {}


# ISO3 codes for IMF data, keyed by statement currency.
_CURRENCY_COUNTRY = {
    "USD": "USA",
    "INR": "IND",
    "JPY": "JPN",
    "CNY": "CHN",
    "HKD": "HKG",
    "TWD": "TWN",
    "EUR": "EURO",
    "GBP": "GBR",
    "KRW": "KOR",
    "CAD": "CAN",
    "AUD": "AUS",
    "CHF": "CHE",
    "SEK": "SWE",
    "NOK": "NOR",
    "DKK": "DNK",
    "SAR": "SAU",
    "ILS": "ISR",
    "ZAR": "ZAF",
    "BRL": "BRA",
    "MXN": "MEX",
    "SGD": "SGP",
    "IDR": "IDN",
    "THB": "THA",
    "TRY": "TUR",
    "PLN": "POL",
    "MYR": "MYS",
}
_IMF_INFLATION: Optional[Dict[str, float]] = None


def _imf_inflation() -> Optional[Dict[str, float]]:
    """IMF WEO CPI inflation forecasts: {ISO3: average % over the next five years}."""
    global _IMF_INFLATION
    if _IMF_INFLATION is None:
        try:
            import httpx

            r = httpx.get("https://www.imf.org/external/datamapper/api/v1/PCPIPCH", timeout=15)
            this_year = datetime.now().year
            _IMF_INFLATION = {
                iso: sum(v[str(y)] for y in range(this_year, this_year + 5)) / 500
                for iso, v in r.json()["values"]["PCPIPCH"].items()
                if all(str(y) in v for y in range(this_year, this_year + 5))
            }
        except Exception:
            return None
    return _IMF_INFLATION


def _inflation_differential(code: str) -> Optional[tuple]:
    """(USD-vs-local adjustment, local inflation, US inflation) from IMF forecasts.

    Damodaran: g_USD = (1 + g_local) × (1 + inflation_US) / (1 + inflation_local) − 1.
    """
    base = _SUBUNITS.get(code, (code,))[0]
    if base == "USD":
        return 0.0, None, None
    infl, iso = _imf_inflation(), _CURRENCY_COUNTRY.get(base)
    if not infl or iso not in infl or "USA" not in infl:
        return None
    return (1 + infl["USA"]) / (1 + infl[iso]) - 1, infl[iso], infl["USA"]


# Listing currency implied by the exchange suffix (fallback when the profile is sparse).
_SUFFIX_CURRENCY = {
    ".NS": "INR",
    ".BO": "INR",
    ".T": "JPY",
    ".HK": "HKD",
    ".L": "GBp",
    ".DE": "EUR",
    ".PA": "EUR",
    ".TO": "CAD",
    ".AX": "AUD",
    ".TW": "TWD",
    ".TWO": "TWD",
    ".KS": "KRW",
    ".KQ": "KRW",
    ".SS": "CNY",
    ".SZ": "CNY",
}


def _fast_info(symbol: str) -> Dict[str, Any]:
    """Currency and share count from yfinance's lightweight quote endpoint.

    Yahoo often returns a sparse company profile (no sharesOutstanding, marketCap or
    currency) to cloud servers such as Vercel and GitHub Actions; fast_info still works
    there — it is what resolve_ticker_symbol already uses for the price.
    """
    out: Dict[str, Any] = {}
    try:
        import yfinance as yf

        fi = yf.Ticker(symbol).fast_info
        for key in ("currency", "shares"):
            try:
                out[key] = fi[key]
            except Exception:
                pass
    except Exception:
        pass
    return out


def dcf_inputs(symbol: str) -> Dict[str, Any]:
    """Gather everything Damodaran's FCFF model needs for a live ticker.

    Valued in US dollars (Damodaran's approach when a local-currency riskfree rate isn't
    available: USD riskfree, the company's country ERP, then convert value per share at
    spot). Returns plain JSON — rates as decimals, money in USD millions, shares in
    millions — so the page can post it to /api/v1/dcf/compute and re-value instantly.
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
    cmp_price = float(
        verified_price or info.get("currentPrice") or info.get("regularMarketPrice") or 0
    )
    fast = (
        {} if info.get("currency") and info.get("sharesOutstanding") else _fast_info(resolved_sym)
    )
    suffix_ccy = next(
        (c for sfx, c in _SUFFIX_CURRENCY.items() if resolved_sym.endswith(sfx)), None
    )
    curr_code = info.get("currency") or fast.get("currency") or suffix_ccy
    if not curr_code and "." not in resolved_sym:
        curr_code = "USD"  # unsuffixed symbols are US listings
    if not curr_code:
        return {
            "error": f"The trading currency of {resolved_sym} is unavailable, so it can't be valued."
        }
    usd_per_listing = _usd_per(provider, curr_code)
    if not usd_per_listing:
        return {
            "error": f"No {curr_code}/USD exchange rate is available for {resolved_sym}, "
            f"so it can't be valued without mixing currencies."
        }

    def _statement(fetch):
        try:
            df = fetch(resolved_sym)
            return df if df is not None and not df.empty else None
        except Exception:
            return None

    income = _statement(provider.get_income_statement)
    balance = _statement(provider.get_balance_sheet)

    def _line(df, keys, idx=0):
        if df is None:
            return None
        for k in keys:
            if k in df.index:
                vals = df.loc[k].dropna()
                if len(vals) > idx:
                    return float(vals.iloc[idx])
        return None

    raw_rev = float(info.get("totalRevenue") or 0) or (
        _line(income, ["Total Revenue", "Operating Revenue"]) or 0.0
    )
    if raw_rev <= 0:
        return {
            "error": f"{resolved_sym} has no reported revenue, so an operating DCF isn't meaningful."
        }
    raw_shares = (
        float(info.get("sharesOutstanding") or 0)
        or float(fast.get("shares") or 0)
        or (_line(balance, ["Ordinary Shares Number", "Share Issued"]) or 0.0)
        or float(info.get("marketCap") or 0) / cmp_price
    )
    if raw_shares <= 0:
        return {
            "error": f"Share count for {resolved_sym} is unavailable, so a per-share DCF can't be computed."
        }

    sources: Dict[str, str] = {}
    fin_code = info.get("financialCurrency")
    if not fin_code:
        # Sparse profile: statements are in the listing currency or in USD (e.g. Infosys,
        # Wipro report in USD). Keep the candidate whose price-to-sales is plausible; a
        # wrong currency is off by ~100x. Refuse if that doesn't settle it.
        mcap_usd = cmp_price * usd_per_listing * raw_shares
        plausible = []
        for code in dict.fromkeys([_SUBUNITS.get(curr_code, (curr_code,))[0], "USD"]):
            rate = _usd_per(provider, code)
            if rate and 0.05 <= mcap_usd / (raw_rev * rate) <= 50:
                plausible.append(code)
        if len(plausible) != 1:
            return {
                "error": f"The currency of {resolved_sym}'s financial statements is unavailable "
                f"and can't be determined reliably, so it can't be valued."
            }
        fin_code = plausible[0]
        sources["financial_currency"] = f"inferred ({fin_code}; profile unavailable)"
    usd_per_fin = _usd_per(provider, fin_code)
    if not usd_per_fin:
        return {
            "error": f"No {fin_code}/USD exchange rate is available for {resolved_sym}'s statements."
        }
    to_usd_m = usd_per_fin / 1e6  # statement currency -> USD millions
    dam = _damodaran()
    industry = _industry_of(resolved_sym, info.get("longName") or info.get("shortName"))
    ind_data = dam["industries"].get(industry) if industry else None

    op_margin = info.get("operatingMargins")
    if op_margin is None:
        ebit_stmt = _line(
            income, ["Operating Income", "EBIT"]
        )  # EBIT line can include other income
        op_margin = ebit_stmt / raw_rev if ebit_stmt is not None else 0.10
        sources["margin"] = "statement" if ebit_stmt is not None else "default"
    else:
        sources["margin"] = "company-reported"
    ebit_reported = float(op_margin) * raw_rev

    # R&D as a capital expense (Damodaran's R&D converter): add back this year's R&D,
    # deduct amortization of past R&D, and add the research asset to invested capital.
    # History: SEC XBRL (10-20 years) merged with yfinance (latest ~4) by fiscal year.
    rd_adjustment = research_asset = 0.0
    rd_by_year = _sec_rd_by_year(resolved_sym, fin_code)
    from_sec = bool(rd_by_year)
    if income is not None and "Research And Development" in income.index:
        for date, val in income.loc["Research And Development"].dropna().items():
            rd_by_year[_fiscal_year(date)] = float(val)
    years = sorted(rd_by_year, reverse=True)
    rd = []  # newest first; stop at the first missing year or non-positive value
    for i, year in enumerate(years):
        if (i and year != years[i - 1] - 1) or rd_by_year[year] <= 0:
            break
        rd.append(rd_by_year[year])
    if len(rd) >= 2:
        from src.tools.ginzu import capitalize_rd

        wanted = int((ind_data or {}).get("rd_life") or 3)
        life = min(wanted, len(rd) - 1)
        cap = capitalize_rd(rd[0], rd[1:], life)
        rd_adjustment, research_asset = cap["ebit_adjustment"], cap["research_asset"]
        sources["rd"] = f"capitalized, {life}-year life" + (
            f" ({'SEC filings' if from_sec else 'Yahoo'}; industry life {wanted})"
            if life < wanted
            else (" (SEC filings)" if from_sec else "")
        )
    ebit = ebit_reported + rd_adjustment

    # Growth: last fiscal year's revenue growth, converted to USD terms with the
    # expected inflation differential (IMF WEO forecasts), so local inflation doesn't
    # leak into a USD valuation. Offline fallback: the currency's 5-year drift vs USD.
    rev_now = _line(income, ["Total Revenue", "Operating Revenue"], 0)
    rev_prev = _line(income, ["Total Revenue", "Operating Revenue"], 1)
    if rev_now and rev_prev and rev_prev > 0:
        growth, sources["growth"] = rev_now / rev_prev - 1, "trailing-annual"
    elif info.get("revenueGrowth") is not None:
        growth, sources["growth"] = float(info["revenueGrowth"]), "latest-quarter-yoy"
    else:
        growth, sources["growth"] = 0.05, "default"
    diff = _inflation_differential(fin_code)
    if diff is not None:
        if diff[0]:
            growth = (1 + growth) * (1 + diff[0]) - 1
            sources[
                "growth"
            ] += f" (USD-adjusted: IMF inflation {fin_code} {diff[1]:.1%} vs USD {diff[2]:.1%})"
    else:
        drift = _fx_drift(provider, fin_code)
        if drift is None:
            sources["growth"] += " (local currency; no inflation or FX data)"
        elif drift:
            growth = (1 + growth) * (1 + drift) - 1
            sources["growth"] += f" (USD-adjusted by {fin_code} 5y drift {drift:+.1%}/yr)"
    growth = max(0.0, min(0.30, growth))

    revenue = raw_rev * to_usd_m
    debt = max(
        0.0, float(info.get("totalDebt") or _line(balance, ["Total Debt"]) or 0) * to_usd_m
    )  # includes lease liabilities (IFRS 16 / ASC 842)
    cash = max(
        0.0,
        float(
            info.get("totalCash")
            or _line(
                balance,
                ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"],
            )
            or 0
        )
        * to_usd_m,
    )
    minority = max(0.0, (_line(balance, ["Minority Interest"]) or 0.0) * to_usd_m)
    book_equity = (_line(balance, ["Stockholders Equity", "Common Stock Equity"]) or 0.0) * to_usd_m
    interest = (
        abs(_line(income, ["Interest Expense", "Interest Expense Non Operating"]) or 0.0) * to_usd_m
    )
    # Cross-holdings and long-term investments: valued separately, added to equity.
    non_operating = max(
        0.0,
        (_line(balance, ["Investments And Advances", "Long Term Equity Investment"]) or 0.0)
        * to_usd_m,
    )

    # Reinvestment lever: Damodaran's default is the industry's sales-to-capital ratio;
    # fall back to the company's own (invested capital incl. the research asset).
    invested = book_equity + debt - cash + research_asset * to_usd_m
    if ind_data:
        s2c, sources["sales_to_capital"] = ind_data["sales_to_capital"], "industry"
    elif invested > 0:
        s2c, sources["sales_to_capital"] = max(0.3, min(5.0, revenue / invested)), "company"
    else:
        s2c, sources["sales_to_capital"] = 1.5, "default"

    country_name = _COUNTRY_ALIASES.get(info.get("country"), info.get("country")) or (
        "India" if resolved_sym.endswith((".NS", ".BO")) else "United States"
    )
    country = dam["countries"].get(country_name) or dam["countries"]["United States"]
    sources["country"] = (
        country_name if country_name in dam["countries"] else "United States (fallback)"
    )

    pretax, tax_paid = _line(income, ["Pretax Income"]), _line(income, ["Tax Provision"])
    marginal_tax = country["marginal_tax"]
    effective_tax = (
        max(0.0, min(marginal_tax, tax_paid / pretax))
        if pretax and pretax > 0 and tax_paid is not None
        else marginal_tax
    )

    tnx = (provider.get_info("^TNX") or {}).get("regularMarketPrice")
    riskfree = float(tnx) / 100 if tnx else US_RISKFREE_FALLBACK
    sources["riskfree"] = "US 10y Treasury" if tnx else "fallback"

    beta, sources["beta"] = (
        (float(info["beta"]), "yfinance") if info.get("beta") else (1.0, "default")
    )
    for suffix, index in _LOCAL_INDEX.items():
        if resolved_sym.endswith(suffix):
            local = _beta_vs_index(provider, resolved_sym, index)
            if local is not None:
                beta, sources["beta"] = local, f"vs {index}"
            break
    beta = max(0.4, min(3.0, beta))
    sources["industry"] = industry or "not classified"

    # Say plainly which inputs are placeholders rather than company data, so a thin-data
    # valuation (new listing, sparse profile) is never presented with full confidence.
    warnings = []
    if not sources["growth"].startswith("trailing-annual"):
        warnings.append(
            "Revenue growth is from a single quarter or a default, not an annual statement."
        )
    if sources["beta"] == "default":
        warnings.append(
            "Beta is unavailable (too little trading history); a beta of 1.0 is assumed."
        )
    if sources["sales_to_capital"] == "default":
        warnings.append(
            "Sales-to-capital is a generic 1.5: the company isn't in Damodaran's industry "
            "classification and its invested capital isn't available."
        )
    if "financial_currency" in sources:
        warnings.append(
            f"Statement currency was inferred as {fin_code} (company profile unavailable)."
        )

    return {
        "symbol": resolved_sym,
        "name": info.get("longName") or info.get("shortName") or resolved_sym,
        "currency": _SYMBOLS.get(curr_code, curr_code + " "),
        "currency_code": curr_code,
        "financial_currency": fin_code,
        "usd_per_listing_unit": usd_per_listing,
        "usd_per_financial_unit": usd_per_fin,
        "cmp": cmp_price,
        "market_cap_usd": cmp_price * usd_per_listing * raw_shares,
        "revenue": revenue,
        "ebit": ebit * to_usd_m,
        "ebit_reported": ebit_reported * to_usd_m,
        "rd_adjustment": rd_adjustment * to_usd_m,
        "research_asset": research_asset * to_usd_m,
        "margin": ebit / raw_rev,
        "growth": growth,
        "sales_to_capital": s2c,
        "industry": industry,
        "effective_tax": effective_tax,
        "marginal_tax": marginal_tax,
        "riskfree": riskfree,
        "beta": beta,
        "erp": country["erp"],
        "mature_erp": dam["mature_market_erp"],
        "country_default_spread": country["default_spread"],
        "interest_expense": interest,
        "debt": debt,
        "cash": cash,
        "minority": minority,
        "non_operating_assets": non_operating,
        "book_equity": book_equity,
        "shares": raw_shares / 1e6,
        "sources": sources,
        "data_warnings": warnings,
    }


def _synthetic_spread(coverage: float, large_firm: bool) -> tuple:
    table = _damodaran()["synthetic_rating"]["large_firm" if large_firm else "small_firm"]
    for upper, rating, spread in table:
        if coverage <= upper:
            return rating, spread
    return table[-1][1], table[-1][2]


def dcf_valuation(
    inputs: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run Damodaran's FCFF model (src/tools/ginzu.py) on dcf_inputs() output.

    overrides (percent units, as the page's sliders): growth, margin, beta, terminal_g,
    rf, erp, tax_rate. Unset → the company-derived defaults.
    """
    from src.tools.ginzu import cost_of_capital, value_fcff

    o = {k: v for k, v in (overrides or {}).items() if v is not None}
    pct = lambda k, default: o[k] / 100 if k in o else default  # noqa: E731
    growth = pct("growth", inputs["growth"])
    margin = pct("margin", inputs["margin"])
    riskfree = pct("rf", inputs["riskfree"])
    erp = pct("erp", inputs["erp"])
    marginal_tax = pct("tax_rate", inputs["marginal_tax"])
    beta = float(o.get("beta", inputs["beta"]))
    perpetual_g = pct("terminal_g", None)  # None → Damodaran default: g = riskfree

    revenue = inputs["revenue"]
    ebit = inputs["ebit"]  # R&D-adjusted
    # Synthetic rating uses reported operating income, as in Damodaran's rating sheet.
    reported = inputs["ebit_reported"]
    coverage = reported / inputs["interest_expense"] if inputs["interest_expense"] > 0 else 1e6
    rating, spread = _synthetic_spread(
        coverage if reported > 0 else -1e5, inputs["market_cap_usd"] > 5e9
    )
    kd = riskfree + spread + inputs["country_default_spread"]

    def run(initial_wacc_delta=0.0, g=perpetual_g, grow=growth, target=margin):
        coc = cost_of_capital(
            riskfree=riskfree,
            beta=beta,
            erp=erp,
            pretax_cost_of_debt=kd,
            marginal_tax=marginal_tax,
            market_equity=inputs["market_cap_usd"] / 1e6,
            book_debt=inputs["debt"],
            interest_expense=inputs["interest_expense"],
        )
        v = value_fcff(
            revenue=revenue,
            ebit=ebit,
            effective_tax=inputs["effective_tax"],
            marginal_tax=marginal_tax,
            growth_next_year=grow,
            growth_years_2_5=grow,
            margin_next_year=inputs["margin"],
            target_margin=target,
            margin_convergence_year=5,
            sales_to_capital_1_5=inputs["sales_to_capital"],
            sales_to_capital_6_10=inputs["sales_to_capital"],
            riskfree=riskfree,
            initial_cost_of_capital=coc["cost_of_capital"] + initial_wacc_delta,
            mature_erp=inputs["mature_erp"],
            stable_cost_of_capital=riskfree + inputs["mature_erp"] + initial_wacc_delta,
            perpetual_growth=g,
            debt=inputs["debt"],
            cash=inputs["cash"],
            shares=inputs["shares"],
            minority=inputs["minority"],
            non_operating_assets=inputs["non_operating_assets"],
            book_equity=inputs["book_equity"],
        )
        return coc, v

    coc, v = run()
    cmp_price = inputs["cmp"]
    # Valued in USD; per-share figures go back to the listing currency at spot.
    to_local = 1.0 / inputs["usd_per_listing_unit"]
    fv = max(0.0, v["value_per_share"]) * to_local
    upside = (fv - cmp_price) / cmp_price * 100 if cmp_price > 0 else 0.0
    if v["equity_value"] <= 0:
        verdict = "Negative equity value (DCF not meaningful at these assumptions)"
    else:
        verdict = "Undervalued (Upside)" if upside >= 0 else "Overvalued (Caution)"

    g_used = v["terminal"]["growth"]
    wacc_steps = [-0.015, -0.0075, 0.0, 0.0075, 0.015]
    g_steps = [g_used + d for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    matrix = [
        [round(max(0.0, run(dw, g)[1]["value_per_share"]) * to_local, 2) for g in g_steps]
        for dw in wacc_steps
    ]

    scen = {
        "bull": (min(0.60, growth * 1.3 + 0.02), min(0.75, margin + 0.03), 0.25),
        "base": (growth, margin, 0.50),
        "bear": (max(0.0, growth * 0.5 - 0.02), max(0.01, margin - 0.03), 0.25),
    }
    scenarios = {}
    for name, (gr, mg, w) in scen.items():
        sv = max(0.0, run(grow=gr, target=mg)[1]["value_per_share"]) * to_local
        scenarios[name] = {
            "growth": round(gr * 100, 8),
            "margin": round(mg * 100, 8),
            "weight": w,
            "fair_value_per_share": round(sv, 2),
            "upside_pct": round((sv - cmp_price) / cmp_price * 100 if cmp_price > 0 else 0.0, 1),
        }

    wacc_pct = coc["cost_of_capital"] * 100
    return {
        "symbol": inputs["symbol"],
        "name": inputs["name"],
        "currency": inputs["currency"],
        "currency_code": inputs["currency_code"],
        "currencyCode": inputs["currency_code"],
        "financial_currency": inputs["financial_currency"],
        "fx_rate": inputs["usd_per_financial_unit"],
        "valuation_currency": "USD",
        "money_symbol": "$",
        "unit": "M",
        "industry": inputs["industry"],
        "cmp": round(cmp_price, 2),
        "model": "Damodaran FCFF (fcffsimpleginzu), 10-year, valued in USD",
        # Slider values, in percent (4dp so a recompute never drifts from the server).
        "growth": round(growth * 100, 8),
        "margin": round(margin * 100, 8),
        "beta": round(beta, 8),
        "terminal_g": round(g_used * 100, 8),
        "rf": round(riskfree * 100, 8),
        "erp": round(erp * 100, 8),
        "tax_rate": round(marginal_tax * 100, 2),
        "effective_tax_rate": round(inputs["effective_tax"] * 100, 2),
        "sales_to_capital": round(inputs["sales_to_capital"], 3),
        "synthetic_rating": rating,
        "wacc": round(wacc_pct, 2),
        "ke": round(coc["cost_of_equity"] * 100, 2),
        "kd_after_tax": round(coc["after_tax_cost_of_debt"] * 100, 2),
        "we": round(coc["equity_weight"], 3),
        "wd": round(coc["debt_weight"], 3),
        "stable_wacc": round(v["terminal"]["cost_of_capital"] * 100, 2),
        "base_revenue": round(revenue, 2),
        "forecast": [{k: round(x, 6) for k, x in row.items()} for row in v["forecast"]],
        "terminal": {k: round(x, 6) for k, x in v["terminal"].items()},
        "total_pv_fcf": round(v["pv_fcff_10y"], 2),
        "terminal_value": round(v["terminal_value"], 2),
        "pv_terminal_value": round(v["pv_terminal_value"], 2),
        "enterprise_value": round(v["operating_assets"], 2),
        "debt": round(inputs["debt"], 2),
        "cash": round(inputs["cash"], 2),
        "minority_interest": round(inputs["minority"], 2),
        "non_operating_assets": round(inputs["non_operating_assets"], 2),
        "rd_adjustment": round(inputs["rd_adjustment"], 2),
        "research_asset": round(inputs["research_asset"], 2),
        "equity_value": round(v["equity_value"], 2),
        "shares": round(inputs["shares"], 4),
        "fair_value_per_share": round(fv, 2),
        "upside_pct": round(upside, 1),
        "verdict": verdict,
        "sensitivity_wacc_steps": [round(wacc_pct + d * 100, 2) for d in wacc_steps],
        "sensitivity_g_steps": [round(g * 100, 2) for g in g_steps],
        "sensitivity_matrix": matrix,
        "scenarios": scenarios,
        "probability_weighted_fair_value": round(
            sum(s["fair_value_per_share"] * s["weight"] for s in scenarios.values()), 2
        ),
        "assumption_sources": inputs["sources"],
        "data_warnings": inputs.get("data_warnings", []),
        "inputs": inputs,
    }


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
    """Live DCF: Damodaran's FCFF model on this company's data (overrides in percent)."""
    inputs = dcf_inputs(symbol)
    if "error" in inputs:
        return inputs
    return dcf_valuation(
        inputs,
        dict(
            growth=growth,
            margin=margin,
            beta=beta,
            terminal_g=terminal_g,
            rf=rf,
            erp=erp,
            tax_rate=tax_rate,
        ),
    )


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

    stockholders_equity = _first_row(
        bs, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]
    )
    total_debt_bs = _first_row(
        bs, ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"]
    )

    # Shared fundamentals for ROCE / Interest Coverage / Altman Z / CCC below
    ebit_val = _first_row(fin, ["EBIT", "Operating Income"])
    total_assets_val = _first_row(bs, ["Total Assets"])
    current_assets_val = _first_row(bs, ["Current Assets"])
    current_liabilities_val = _first_row(bs, ["Current Liabilities"])
    total_liabilities_val = _first_row(
        bs, ["Total Liabilities Net Minority Interest", "Total Liab"]
    )
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
    market_cap_val = info.get("marketCap") or (
        cmp_price * float(info.get("sharesOutstanding") or 0)
    )

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
        total_assets_val
        and total_assets_val > 0
        and current_assets_val is not None
        and current_liabilities_val is not None
        and retained_earnings_val is not None
        and ebit_val is not None
        and total_liabilities_val
        and total_liabilities_val > 0
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
        altman_exp = f"Altman Z-Score of {altman_str}: " + (
            "Safe zone, low near-term bankruptcy risk."
            if altman_z > 2.99
            else (
                "Grey zone, moderate financial distress risk."
                if altman_z > 1.81
                else "Distress zone, elevated bankruptcy risk."
            )
        )
    else:
        altman_str = "N/A"
        altman_pill = "caution"
        altman_exp = "Altman Z-Score not available (insufficient statement data)."

    # Cash Conversion Cycle = DIO + DSO - DPO
    if (
        cogs_val
        and cogs_val > 0
        and revenue_val
        and revenue_val > 0
        and inventory_val is not None
        and receivables_val is not None
        and payables_val is not None
    ):
        dio = (inventory_val / cogs_val) * 365
        dso = (receivables_val / revenue_val) * 365
        dpo = (payables_val / cogs_val) * 365
        ccc_val = dio + dso - dpo
        ccc_str = f"{ccc_val:.0f} Days"
        ccc_pill = "good" if ccc_val < 60 else ("caution" if ccc_val < 120 else "danger")
        ccc_exp = (
            f"Cash conversion cycle of {ccc_str} (DIO {dio:.0f} + DSO {dso:.0f} − DPO {dpo:.0f})."
        )
    else:
        ccc_str = "N/A"
        ccc_pill = "caution"
        ccc_exp = (
            "Cash conversion cycle not available (inventory/receivables/payables not reported)."
        )

    # P/E
    pe_str = f"{float(pe):.1f}x" if pe else "N/A"
    pe_pill = (
        "good" if pe and float(pe) < 25 else ("caution" if pe and float(pe) < 45 else "danger")
    )
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
    ev_pill = (
        "good"
        if ev_ebitda and 0 < float(ev_ebitda) < 15
        else ("caution" if ev_ebitda and float(ev_ebitda) < 30 else "danger")
    )
    ev_exp = f"Enterprise multiple of {ev_str}."

    # Dividend Yield
    # yfinance reports dividendYield already as a percentage value (e.g. 0.32 == 0.32%),
    # not a fraction — multiplying by 100 here previously inflated every yield 100x.
    div_str = f"{float(div_yield):.2f}%" if div_yield else "0.0%"
    div_pill = "good" if div_yield and float(div_yield) > 1.0 else "caution"
    div_exp = f"Annual dividend yield of {div_str}."

    # Net Worth & Solvency evaluation
    has_negative_equity = (stockholders_equity is not None and stockholders_equity <= 0) or (
        pb is not None and float(pb) < 0
    )

    if has_negative_equity:
        de_str = "Capital Eroded"
        de_pill = "danger"
        debt_num = total_debt_bs or info.get("totalDebt", 0.0)
        debt_disp = (
            f"{curr_sym}{debt_num / (1e7 if is_inr else 1e6):,.1f} {('Cr' if is_inr else 'M')}"
        )
        eq_disp = (
            f"{curr_sym}{stockholders_equity / (1e7 if is_inr else 1e6):,.1f} {('Cr' if is_inr else 'M')}"
            if stockholders_equity
            else "Negative"
        )
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
        elif (
            total_debt_bs is not None
            and stockholders_equity is not None
            and stockholders_equity > 0
        ):
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
    if (
        cr_num is None
        and bs is not None
        and "Current Assets" in bs.index
        and "Current Liabilities" in bs.index
    ):
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
        fcf_exp = (
            f"{'Positive' if fcf_num > 0 else 'Negative'} recurring free cash flow from operations."
        )
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
            rev_row = (
                fin.loc["Total Revenue"]
                if "Total Revenue" in fin.index
                else fin.loc["Operating Revenue"]
            )
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
    metric_values = [
        pe_str,
        pb_str,
        ev_str,
        div_str,
        roe_str,
        roce_str,
        opm_str,
        npm_str,
        de_str,
        icr_str,
        cr_str,
        altman_str,
        fcf_str,
        sales_str,
        profit_str,
        ccc_str,
    ]
    available = sum(1 for v in metric_values if v not in ("N/A",) and not str(v).startswith("N/A"))
    confidence_pct = round(available / len(metric_values) * 100, 0)
    confidence_label = (
        "High" if confidence_pct >= 75 else ("Medium" if confidence_pct >= 50 else "Low")
    )

    return {
        "symbol": resolved_sym,
        "title": f"{name} ({curr_sym}{cmp_price:,.2f})",
        "subtitle": f"Sector: {sector} • Currency: {curr_code} ({curr_sym})",
        "pe": pe_str,
        "pePill": pe_pill,
        "peExplain": pe_exp,
        "pb": pb_str,
        "pbPill": pb_pill,
        "pbExplain": pb_exp,
        "ev": ev_str,
        "evPill": ev_pill,
        "evExplain": ev_exp,
        "div": div_str,
        "divPill": div_pill,
        "divExplain": div_exp,
        "roe": roe_str,
        "roePill": roe_pill,
        "roeExplain": roe_exp,
        "roce": roce_str,
        "rocePill": roce_pill,
        "roceExplain": roce_exp,
        "opm": opm_str,
        "opmPill": opm_pill,
        "opmExplain": opm_exp,
        "npm": npm_str,
        "npmPill": npm_pill,
        "npmExplain": npm_exp,
        "de": de_str,
        "dePill": de_pill,
        "deExplain": de_exp,
        "icr": icr_str,
        "icrPill": icr_pill,
        "icrExplain": icr_exp,
        "cr": cr_str,
        "crPill": cr_pill,
        "crExplain": cr_exp,
        "altman": altman_str,
        "altmanPill": altman_pill,
        "altmanExplain": altman_exp,
        "fcf": fcf_str,
        "fcfPill": fcf_pill,
        "fcfExplain": fcf_exp,
        "sales": sales_str,
        "salesPill": sales_pill,
        "salesExplain": sales_exp,
        "profit": profit_str,
        "profitPill": profit_pill,
        "profitExplain": profit_exp,
        "ccc": ccc_str,
        "cccPill": ccc_pill,
        "cccExplain": ccc_exp,
        "dataConfidence": {
            "score_pct": confidence_pct,
            "label": confidence_label,
            "note": f"{available} of {len(metric_values)} ratios available from reported financials.",
        },
    }
