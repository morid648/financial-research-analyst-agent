"""Regression tests for the live DCF pipeline (dcf_inputs -> dcf_valuation).

The valuation engine is pinned to Damodaran's workbook in tests/test_ginzu.py; these
tests pin how live company data becomes that engine's inputs: valuation in USD with
per-share conversion back to the listing currency, annual growth adjusted for the
currency's drift, beta against the local index, Damodaran's country and industry
data, R&D capitalization, cross-holdings, minority interest, and refusing to invent
numbers.
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.tools.market_data as md


class FakeProvider:
    def __init__(self, info, fx=None, balance_sheet=None, income=None, history=None):
        self._info, self._fx = info, fx or {}
        self._bs, self._income, self._history = balance_sheet, income, history or {}

    def get_info(self, symbol):
        if symbol == "^TNX":
            return {"regularMarketPrice": 4.5}
        if symbol.endswith("=X"):
            return {"regularMarketPrice": self._fx.get(symbol)}
        return self._info

    def get_balance_sheet(self, symbol):
        return self._bs

    def get_income_statement(self, symbol):
        return self._income

    def get_history(self, symbol, period="1y", interval="1d"):
        return pd.DataFrame({"Close": self._history[symbol]})  # KeyError -> "no history"


BASE_INFO = {
    "currency": "USD",
    "financialCurrency": "USD",
    "country": "United States",
    "totalRevenue": 1_000_000_000,  # 1,000 M
    "revenueGrowth": 0.20,
    "operatingMargins": 0.25,
    "beta": 1.0,
    "sharesOutstanding": 100_000_000,  # 100 M
    "totalDebt": 0,
    "totalCash": 0,
}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """No live SEC / IMF calls in tests; individual tests opt in with fixed data."""
    monkeypatch.setattr(md, "_sec_rd_by_year", lambda symbol, currency: {})
    monkeypatch.setattr(md, "_imf_inflation", lambda: None)


def _inputs(monkeypatch, info=None, symbol="TEST", **provider_kwargs):
    provider = FakeProvider({**BASE_INFO, **(info or {})}, **provider_kwargs)
    monkeypatch.setattr(md, "get_provider", lambda: provider)
    monkeypatch.setattr(md, "resolve_ticker_symbol", lambda s: (symbol, 50.0))
    return md.dcf_inputs(symbol)


def _value(monkeypatch, **kw):
    return md.dcf_valuation(_inputs(monkeypatch, **kw))


def test_statements_in_other_currency_are_converted(monkeypatch):
    """ADR-style listing (price USD, statements TWD) must convert, not mix currencies."""
    usd = _value(monkeypatch)
    twd = _value(
        monkeypatch,
        info={"financialCurrency": "TWD", "totalRevenue": BASE_INFO["totalRevenue"] * 32},
        fx={"TWDUSD=X": 1 / 32},
    )
    assert twd["base_revenue"] == pytest.approx(usd["base_revenue"])
    assert twd["fair_value_per_share"] == pytest.approx(usd["fair_value_per_share"], rel=1e-6)


def test_non_usd_listing_is_valued_in_usd_and_converted_back(monkeypatch):
    """Damodaran: USD riskfree + country ERP, then per-share value converted at spot."""
    usd = _value(monkeypatch)
    eur = _value(
        monkeypatch,
        info={"currency": "EUR", "financialCurrency": "EUR", "country": "United States"},
        fx={"EURUSD=X": 1.25},
    )
    # Same business in EUR: every USD figure is 1.25x larger, and value/share is
    # converted back at 1.25, so it equals the USD case exactly (no debt here).
    assert eur["base_revenue"] == pytest.approx(1250.0)
    assert eur["fair_value_per_share"] == pytest.approx(usd["fair_value_per_share"], rel=1e-6)
    assert eur["currency_code"] == "EUR" and eur["money_symbol"] == "$"
    assert eur["rf"] == pytest.approx(4.5)  # USD riskfree, not a local-currency rate


def test_missing_fx_rate_is_an_error_not_a_number(monkeypatch):
    r = _inputs(monkeypatch, info={"financialCurrency": "TWD"}, fx={})
    assert "error" in r and "TWD" in r["error"]


def test_missing_share_count_is_an_error_not_invented(monkeypatch):
    r = _inputs(monkeypatch, info={"sharesOutstanding": None, "marketCap": None})
    assert "error" in r


def test_year_one_growth_uses_annual_statements_not_latest_quarter(monkeypatch):
    """revenueGrowth is one quarter's YoY (here 20%); the annual statement says 5%."""
    income = pd.DataFrame(
        {"2025": {"Total Revenue": 1_050_000_000}, "2024": {"Total Revenue": 1_000_000_000}}
    )
    i = _inputs(monkeypatch, income=income)
    assert i["growth"] == pytest.approx(0.05)
    assert i["sources"]["growth"] == "trailing-annual"


def test_local_growth_is_adjusted_by_the_currencys_drift(monkeypatch):
    """INR losing 5%/yr vs USD turns 10% rupee growth into ~4.5% dollar growth."""
    income = pd.DataFrame(
        {"2025": {"Total Revenue": 1_100_000_000}, "2024": {"Total Revenue": 1_000_000_000}}
    )
    dates = pd.date_range("2021-01-01", periods=5 * 12 + 1, freq="MS")
    years = (dates[-1] - dates[0]).days / 365.25
    fx_path = pd.Series(0.0125 * 0.95 ** (np.arange(len(dates)) / 12), index=dates)
    drift = (fx_path.iloc[-1] / fx_path.iloc[0]) ** (1 / years) - 1
    i = _inputs(
        monkeypatch,
        info={"currency": "INR", "financialCurrency": "INR", "country": "India"},
        fx={"INRUSD=X": 0.0105},
        income=income,
        history={"INRUSD=X": fx_path},
    )
    assert i["growth"] == pytest.approx(1.10 * (1 + drift) - 1)
    assert "USD-adjusted" in i["sources"]["growth"]


def test_minority_interest_is_deducted_from_equity(monkeypatch):
    plain = _value(monkeypatch)
    mi = _value(
        monkeypatch, balance_sheet=pd.DataFrame({"2025": {"Minority Interest": 400_000_000}})
    )
    assert mi["minority_interest"] == pytest.approx(400.0)  # millions
    assert mi["equity_value"] == pytest.approx(plain["equity_value"] - 400.0, abs=0.02)


def test_cross_holdings_are_added_to_equity(monkeypatch):
    plain = _value(monkeypatch)
    xh = _value(
        monkeypatch,
        balance_sheet=pd.DataFrame({"2025": {"Investments And Advances": 300_000_000}}),
    )
    assert xh["non_operating_assets"] == pytest.approx(300.0)
    assert xh["equity_value"] == pytest.approx(plain["equity_value"] + 300.0, abs=0.02)


def test_rd_is_capitalized(monkeypatch):
    """R&D 100/90/80/70 M, 3-year life: EBIT += 100 - (90+80+70)/3 = +20 M."""
    income = pd.DataFrame(
        {
            "2025": {"Research And Development": 100e6},
            "2024": {"Research And Development": 90e6},
            "2023": {"Research And Development": 80e6},
            "2022": {"Research And Development": 70e6},
        }
    )
    i = _inputs(monkeypatch, income=income)
    assert i["rd_adjustment"] == pytest.approx(20.0)
    assert i["research_asset"] == pytest.approx(100 + 90 * 2 / 3 + 80 / 3)
    assert i["ebit"] == pytest.approx(250.0 + 20.0)  # 25% margin on 1,000 M, plus R&D add-back
    assert i["sources"]["rd"] == "capitalized, 3-year life"


def test_industry_sales_to_capital_is_damodarans_default(monkeypatch):
    i = _inputs(monkeypatch, symbol="AAPL")  # in Damodaran's classification
    ind = md._damodaran()["industries"][i["industry"]]
    assert i["industry"] == "Computers/Peripherals"
    assert i["sales_to_capital"] == ind["sales_to_capital"]
    assert i["sources"]["sales_to_capital"] == "industry"


def test_indian_listing_uses_damodaran_country_data_and_nifty_beta(monkeypatch):
    rng = np.random.default_rng(0)
    market = rng.normal(0.002, 0.02, 104)
    history = {
        "^NSEI": 100 * np.cumprod(1 + np.r_[0, market]),
        "TEST.NS": 100 * np.cumprod(1 + np.r_[0, 1.2 * market]),  # beta exactly 1.2
    }
    i = _inputs(
        monkeypatch,
        symbol="TEST.NS",
        info={"currency": "INR", "financialCurrency": "INR", "country": "India", "beta": 0.15},
        fx={"INRUSD=X": 0.0105},
        history=history,
    )
    dam = md._damodaran()["countries"]["India"]
    assert i["beta"] == pytest.approx(1.2, abs=1e-6) and i["sources"]["beta"] == "vs ^NSEI"
    assert i["erp"] == dam["erp"]  # mature ERP + India CRP (Damodaran, Jul 2026)
    assert i["marginal_tax"] == dam["marginal_tax"]
    assert i["riskfree"] == pytest.approx(0.045)  # USD valuation: US 10y Treasury


def test_perpetual_growth_defaults_to_riskfree(monkeypatch):
    r = _value(monkeypatch)
    assert r["terminal_g"] == pytest.approx(r["rf"])  # Damodaran: g = riskfree


def test_compute_endpoint_reproduces_the_get_valuation(monkeypatch):
    """The page recomputes via POST /dcf/compute; it must equal the GET result exactly."""
    from src.api.routes import app

    r = _value(monkeypatch)
    again = TestClient(app).post(
        "/api/v1/dcf/compute", json={"inputs": r["inputs"], "overrides": {"growth": r["growth"]}}
    )
    assert again.status_code == 200
    assert again.json()["fair_value_per_share"] == r["fair_value_per_share"]
    assert again.json()["sensitivity_matrix"] == r["sensitivity_matrix"]


def test_compute_endpoint_rejects_malformed_inputs():
    from src.api.routes import app

    assert TestClient(app).post("/api/v1/dcf/compute", json={"inputs": {}}).status_code == 422


def test_sensitivity_matrix_centre_equals_base_case(monkeypatch):
    r = _value(monkeypatch)
    assert r["sensitivity_matrix"][2][2] == pytest.approx(r["fair_value_per_share"], abs=0.01)


def test_agent_dcf_uses_the_same_model(monkeypatch):
    """dcf_model.get_dcf_summary (the agents' DCF) must report the /dcf model's values."""
    from src.tools import dcf_model

    r = _value(monkeypatch)
    monkeypatch.setattr(dcf_model, "get_company_dcf_profile", lambda s: r)
    summary = dcf_model.get_dcf_summary("TEST")
    assert summary["scenarios"]["base"]["intrinsic_value"] == r["fair_value_per_share"]
    assert summary["wacc"]["wacc_pct"] == r["wacc"]
    assert set(summary["scenarios"]) == {"bull", "base", "bear"}


def test_imf_inflation_differential_converts_local_growth_to_usd(monkeypatch):
    """Damodaran: g_USD = (1 + g_INR) × (1 + π_US) / (1 + π_IN) − 1, IMF forecasts."""
    monkeypatch.setattr(md, "_imf_inflation", lambda: {"USA": 0.024, "IND": 0.041})
    income = pd.DataFrame(
        {"2025": {"Total Revenue": 1_100_000_000}, "2024": {"Total Revenue": 1_000_000_000}}
    )
    i = _inputs(
        monkeypatch,
        info={"currency": "INR", "financialCurrency": "INR", "country": "India"},
        fx={"INRUSD=X": 0.0105},
        income=income,
    )
    assert i["growth"] == pytest.approx(1.10 * 1.024 / 1.041 - 1)
    assert "IMF inflation INR 4.1% vs USD 2.4%" in i["sources"]["growth"]


def test_sec_history_gives_the_full_industry_rd_life(monkeypatch):
    """yfinance has ~4 years; SEC XBRL supplies enough for Semiconductor's 5-year life."""
    sec = {2025: 120.0e6, 2024: 100e6, 2023: 90e6, 2022: 80e6, 2021: 70e6, 2020: 60e6}
    monkeypatch.setattr(md, "_sec_rd_by_year", lambda symbol, currency: dict(sec))
    i = _inputs(monkeypatch, symbol="NVDA")  # Damodaran: Semiconductor, R&D life 5
    past = [100, 90, 80, 70, 60]
    assert i["rd_adjustment"] == pytest.approx(120 - sum(past) / 5)
    assert i["sources"]["rd"] == "capitalized, 5-year life (SEC filings)"


def test_rd_history_stops_at_a_missing_year(monkeypatch):
    sec = {2025: 100e6, 2024: 90e6, 2022: 70e6}  # 2023 missing
    monkeypatch.setattr(md, "_sec_rd_by_year", lambda symbol, currency: dict(sec))
    i = _inputs(monkeypatch)
    assert i["rd_adjustment"] == pytest.approx(100 - 90)  # only 2025 and 2024 are usable


def test_adr_resolves_to_its_home_listing_industry():
    assert md._industry_of("TSM") is None  # Damodaran lists it as TWSE:2330
    name = "Taiwan Semiconductor Manufacturing Company Limited"
    assert md._industry_of("TSM", name) == "Semiconductor"


def test_fiscal_years_line_up_with_sec_frames():
    assert md._fiscal_year("2026-01-25") == 2025  # NVDA's fiscal 2026 = SEC frame CY2025
    assert md._fiscal_year("2025-09-27") == 2025  # Apple
    assert md._fiscal_year("2026-03-31") == 2025  # Indian fiscal year
