"""DCF for the AI agents — an adapter over the /dcf model.

The FundamentalAnalyst agent calls get_dcf_summary(). It used to run its own
separate DCF; it now uses the same Damodaran FCFF pipeline as the API and page
(src/tools/market_data.py -> src/tools/ginzu.py, verified against Damodaran's
workbook), so the agents and the UI can never disagree about a company's value.

Usage::

    from src.tools.dcf_model import get_dcf_summary
    result = get_dcf_summary("AAPL")
"""

from typing import Any, Dict

from src.tools.market_data import get_company_dcf_profile


def get_dcf_summary(symbol: str) -> Dict[str, Any]:
    """Bull/base/bear intrinsic values, WACC, sensitivity, margin of safety, recommendation."""
    r = get_company_dcf_profile(symbol)
    if "error" in r:
        return {"symbol": symbol, "error": r["error"]}

    scenarios = {
        name: {
            "intrinsic_value": s["fair_value_per_share"],
            "upside_pct": s["upside_pct"],
            "growth_rate": round(s["growth"], 2),
            "terminal_growth": round(r["terminal_g"], 2),
            "target_margin": round(s["margin"], 2),
            "weight": s["weight"],
        }
        for name, s in r["scenarios"].items()
    }
    value = r["fair_value_per_share"]
    margin_of_safety = round((value - r["cmp"]) / value * 100, 1) if value > 0 else 0.0
    recommendation = (
        "Buy" if margin_of_safety >= 20 else "Sell" if margin_of_safety <= -20 else "Hold"
    )
    return {
        "symbol": r["symbol"],
        "model": r["model"],
        "currency": r["currency_code"],
        "current_price": r["cmp"],
        "wacc": {
            "wacc": round(r["wacc"] / 100, 4),
            "wacc_pct": r["wacc"],
            "cost_of_equity_pct": r["ke"],
            "beta": round(r["beta"], 3),
        },
        "scenarios": scenarios,
        "probability_weighted_value": r["probability_weighted_fair_value"],
        "sensitivity": {
            "wacc_pct": r["sensitivity_wacc_steps"],
            "perpetual_growth_pct": r["sensitivity_g_steps"],
            "value_per_share": r["sensitivity_matrix"],
        },
        "margin_of_safety_pct": margin_of_safety,
        "recommendation": recommendation,
        "assumption_sources": r["assumption_sources"],
    }
