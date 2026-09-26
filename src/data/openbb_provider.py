"""
OpenBB Platform Market Data Provider.

Implements ``MarketDataProvider`` protocol using the OpenBB Platform (v4+).
Provides unified access to equities, historical OHLCV, financial statements,
macroeconomic data, news, and fundamentals.

Usage::

    from src.data.provider import get_provider
    provider = get_provider("openbb")
    info = provider.get_info("AAPL")
    hist = provider.get_history("AAPL", period="1y")
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from src.data.provider import MarketDataProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenBBProvider(MarketDataProvider):
    """
    Concrete market data provider powered by OpenBB Platform.
    Integrates multiple underlying data sources (yfinance, FMP, SEC, FRED, etc.)
    under the unified OpenBB interface.
    """

    def __init__(self, default_provider: str = "yfinance") -> None:
        self._default_provider = default_provider
        try:
            from openbb import obb

            self._obb = obb
            logger.info("OpenBBProvider initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import OpenBB: {e}")
            raise ImportError("OpenBB is not installed. Install with: pip install openbb") from e

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _empty_df() -> pd.DataFrame:
        return pd.DataFrame()

    @staticmethod
    def _empty_series() -> pd.Series:
        return pd.Series(dtype=float)

    # ── Category 1: Info & Quote ─────────────────────────────────

    def get_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch stock profile, quote, and basic multiples via OpenBB."""
        clean_symbol = symbol.strip().upper()
        info: Dict[str, Any] = {"symbol": clean_symbol}

        try:
            # 1. Fetch current quote
            quote_res = self._obb.equity.price.quote(
                symbol=clean_symbol, provider=self._default_provider
            )
            quote_data = quote_res.to_df()
            if not quote_data.empty:
                row = quote_data.iloc[0].to_dict()
                info["currentPrice"] = (
                    row.get("last_price") or row.get("price") or row.get("close", 0)
                )
                info["regularMarketPrice"] = info["currentPrice"]
                info["previousClose"] = row.get("prev_close") or row.get("previous_close", 0)
                info["open"] = row.get("open", 0)
                info["dayHigh"] = row.get("high", 0)
                info["dayLow"] = row.get("low", 0)
                info["volume"] = row.get("volume", 0)
                info["fiftyTwoWeekHigh"] = row.get("year_high") or row.get("fifty_two_week_high", 0)
                info["fiftyTwoWeekLow"] = row.get("year_low") or row.get("fifty_two_week_low", 0)

            # 2. Fetch company profile / overview
            profile_res = self._obb.equity.profile(
                symbol=clean_symbol, provider=self._default_provider
            )
            profile_df = profile_res.to_df()
            if not profile_df.empty:
                p = profile_df.iloc[0].to_dict()
                info["shortName"] = p.get("name") or p.get("company_name", clean_symbol)
                info["longName"] = p.get("name") or p.get("company_name", clean_symbol)
                info["sector"] = p.get("sector", "N/A")
                info["industry"] = p.get("industry", "N/A")
                info["marketCap"] = p.get("market_cap", 0)
                info["currency"] = p.get("currency", "USD")
                info["beta"] = p.get("beta", 1.0)
                info["description"] = p.get("description", "")

            # 3. Fetch fundamental multiples / key metrics
            try:
                metrics_res = self._obb.equity.fundamental.metrics(
                    symbol=clean_symbol, provider=self._default_provider
                )
                m_df = metrics_res.to_df()
                if not m_df.empty:
                    m = m_df.iloc[0].to_dict()
                    info["trailingPE"] = m.get("pe_ratio") or m.get("pe", None)
                    info["priceToBook"] = m.get("pb_ratio") or m.get("pb", None)
                    info["dividendYield"] = m.get("dividend_yield", 0)
                    info["returnOnEquity"] = m.get("roe", None)
                    info["returnOnAssets"] = m.get("roa", None)
                    info["debtToEquity"] = m.get("debt_to_equity", None)
            except Exception as e:
                logger.debug(f"OpenBB metrics retrieval note for {clean_symbol}: {e}")

            # If price is missing or zero (e.g. ETFs, Indices, or renamed ticker), fallback to YFinanceProvider
            if not info.get("currentPrice"):
                from src.data.provider import YFinanceProvider

                yf_info = YFinanceProvider().get_info(symbol)
                if yf_info and yf_info.get("currentPrice"):
                    return yf_info

            return info

        except Exception as e:
            logger.warning(f"OpenBB get_info error for {clean_symbol}: {e}. Falling back.")
            from src.data.provider import YFinanceProvider

            return YFinanceProvider().get_info(symbol)

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time / latest price quote."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.price.quote(symbol=clean_symbol, provider=self._default_provider)
            df = res.to_df()
            if not df.empty:
                row = df.iloc[0].to_dict()
                return {
                    "symbol": clean_symbol,
                    "price": row.get("last_price") or row.get("price") or row.get("close", 0),
                    "change": row.get("change", 0),
                    "changePercent": row.get("percent_change") or row.get("change_percent", 0),
                    "volume": row.get("volume", 0),
                    "timestamp": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            logger.warning(f"OpenBB get_quote error for {clean_symbol}: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_quote(symbol)

    # ── Category 2: Historical Price Data ────────────────────────

    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV dataframe."""
        clean_symbol = symbol.strip().upper()
        try:
            if not start:
                period_days = {
                    "1d": 1,
                    "5d": 5,
                    "1mo": 30,
                    "3mo": 90,
                    "6mo": 180,
                    "1y": 365,
                    "2y": 730,
                    "5y": 1825,
                    "10y": 3650,
                }
                days = period_days.get(period, 365)
                start_dt = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            else:
                start_dt = start

            res = self._obb.equity.price.historical(
                symbol=clean_symbol,
                start_date=start_dt,
                end_date=end,
                interval=interval if interval != "1d" else "1d",
                provider=self._default_provider,
            )
            df = res.to_df()
            if not df.empty:
                rename_map = {
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                    "date": "Date",
                }
                df = df.rename(columns=rename_map)
                return df
        except Exception as e:
            logger.warning(f"OpenBB get_history error for {clean_symbol}: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_history(
            symbol, period=period, interval=interval, start=start, end=end
        )

    # ── Category 3: Financial Statements ─────────────────────────

    def get_income_statement(self, symbol: str) -> pd.DataFrame:
        """Fetch annual income statement."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.fundamental.income(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                return df
        except Exception as e:
            logger.debug(f"OpenBB income statement retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_income_statement(symbol)

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """Fetch annual balance sheet."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.fundamental.balance(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                return df
        except Exception as e:
            logger.debug(f"OpenBB balance sheet retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_balance_sheet(symbol)

    def get_cash_flow(self, symbol: str) -> pd.DataFrame:
        """Fetch annual cash flow statement."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.fundamental.cash(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                return df
        except Exception as e:
            logger.debug(f"OpenBB cash flow retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_cash_flow(symbol)

    def get_quarterly_income_statement(self, symbol: str) -> pd.DataFrame:
        """Fetch quarterly income statement."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.fundamental.income(
                symbol=clean_symbol, period="quarter", provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                return df
        except Exception as e:
            logger.debug(f"OpenBB quarterly income retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_quarterly_income_statement(symbol)

    def get_financials(
        self,
        symbol: str,
        statement_type: str = "income_statement",
        freq: str = "yearly",
    ) -> pd.DataFrame:
        """Helper to get right statement from provider."""
        if freq == "yearly":
            if statement_type == "income_statement":
                return self.get_income_statement(symbol)
            elif statement_type == "balance_sheet":
                return self.get_balance_sheet(symbol)
            elif statement_type == "cash_flow":
                return self.get_cash_flow(symbol)
        elif freq == "quarterly":
            if statement_type == "income_statement":
                return self.get_quarterly_income_statement(symbol)

        return self._empty_df()

    # ── Category 4: Earnings & Calendar ──────────────────────────

    def get_earnings_history(self, symbol: str) -> pd.DataFrame:
        """Fetch historical earnings vs estimates."""
        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_earnings_history(symbol)

    def get_calendar(self, symbol: str) -> Any:
        """Fetch upcoming dividend/earnings corporate events."""
        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_calendar(symbol)

    # ── Category 5: Dividends ────────────────────────────────────

    def get_dividends(self, symbol: str) -> pd.Series:
        """Fetch dividend payment history series."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.fundamental.dividends(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty and "amount" in df.columns:
                return df["amount"]
        except Exception as e:
            logger.debug(f"OpenBB dividends retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_dividends(symbol)

    # ── Category 6: Options ──────────────────────────────────────

    def get_options_expirations(self, symbol: str) -> List[str]:
        """Fetch options chain expiration dates."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.derivatives.options.chains(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty and "expiration" in df.columns:
                return sorted(list(df["expiration"].astype(str).unique()))
        except Exception as e:
            logger.debug(f"OpenBB options chains retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_options_expirations(symbol)

    def get_options_chain(self, symbol: str, expiration: str) -> Dict[str, pd.DataFrame]:
        """Fetch options calls and puts dataframes."""
        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_options_chain(symbol, expiration=expiration)

    # ── Category 7: Holders & Insider Activity ───────────────────

    def get_insider_transactions(self, symbol: str) -> pd.DataFrame:
        """Fetch insider transactions."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.ownership.insider_trading(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                return df
        except Exception as e:
            logger.debug(f"OpenBB insider transactions: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_insider_transactions(symbol)

    def get_insider_purchases(self, symbol: str) -> pd.DataFrame:
        """Fetch insider purchase summary."""
        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_insider_purchases(symbol)

    def get_institutional_holders(self, symbol: str) -> pd.DataFrame:
        """Fetch institutional shareholder breakdown."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.equity.ownership.institutional(
                symbol=clean_symbol, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                return df
        except Exception as e:
            logger.debug(f"OpenBB institutional holders: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_institutional_holders(symbol)

    def get_mutualfund_holders(self, symbol: str) -> pd.DataFrame:
        """Fetch mutual fund holders breakdown."""
        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_mutualfund_holders(symbol)

    def get_major_holders(self, symbol: str) -> pd.DataFrame:
        """Fetch major holders breakdown."""
        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_major_holders(symbol)

    # ── Category 8: News ─────────────────────────────────────────

    def get_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch recent financial news articles."""
        clean_symbol = symbol.strip().upper()
        try:
            res = self._obb.news.company(
                symbol=clean_symbol, limit=limit, provider=self._default_provider
            )
            df = res.to_df()
            if not df.empty:
                articles = []
                for _, row in df.iterrows():
                    articles.append(
                        {
                            "title": row.get("title", ""),
                            "publisher": row.get("source", "OpenBB News"),
                            "link": row.get("url", ""),
                            "providerPublishTime": row.get("date", datetime.utcnow().isoformat()),
                            "type": "ARTICLE",
                        }
                    )
                return articles
        except Exception as e:
            logger.debug(f"OpenBB news retrieval: {e}")

        from src.data.provider import YFinanceProvider

        return YFinanceProvider().get_news(symbol, limit=limit)
