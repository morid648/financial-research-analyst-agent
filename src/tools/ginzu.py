"""FCFF valuation engine replicating Damodaran's fcffsimpleginzu.xlsx ("Valuation output").

Source: https://pages.stern.nyu.edu/~adamodar/pc/fcffsimpleginzu.xlsx (Apr 2026 version).
Each row below mirrors that sheet's formula; tests/test_ginzu.py pins the workbook's
own Almarai example plus Excel-recalculated variants.

Rates are decimals (0.05 = 5%). Money is in any consistent unit (e.g. millions).

ponytail: no R&D/lease/option converters and a fixed 1-year reinvestment lag (the
workbook defaults) — add them when a caller has those inputs.
"""

from typing import Any, Dict, List, Optional


def capitalize_rd(current: float, past: List[float], life: int) -> Dict[str, float]:
    """Mirror of the workbook's 'R& D converter': treat R&D as a capital asset.

    past: prior years' R&D, most recent first (year -1, -2, ...). Returns the research
    asset (added to invested capital), this year's amortization, and the adjustment to
    operating income (current R&D added back, amortization deducted).
    """
    past = past[:life]
    asset = current + sum(rd * (life - k) / life for k, rd in enumerate(past, start=1))
    amortization = sum(rd / life for rd in past)
    return dict(
        research_asset=asset, amortization=amortization, ebit_adjustment=current - amortization
    )


def cost_of_capital(
    *,
    riskfree: float,
    beta: float,
    erp: float,
    pretax_cost_of_debt: float,
    marginal_tax: float,
    market_equity: float,
    book_debt: float,
    interest_expense: float,
    debt_maturity: float = 3.0,  # the workbook's default average maturity
) -> Dict[str, float]:
    """Mirror of the workbook's 'Cost of capital worksheet' (detailed approach, no
    preferred stock or convertibles): debt valued at market as a bond, market weights."""
    kd = pretax_cost_of_debt
    n = debt_maturity
    mv_debt = (
        interest_expense * (1 - (1 + kd) ** -n) / kd + book_debt / (1 + kd) ** n
        if kd > 0
        else book_debt
    )
    ke = riskfree + beta * erp
    kd_after = kd * (1 - marginal_tax)
    total = market_equity + mv_debt
    we = market_equity / total if total > 0 else 1.0
    wacc = we * ke + (1 - we) * kd_after
    return dict(
        cost_of_equity=ke,
        after_tax_cost_of_debt=kd_after,
        market_value_of_debt=mv_debt,
        equity_weight=we,
        debt_weight=1 - we,
        cost_of_capital=wacc,
    )


def value_fcff(
    *,
    revenue: float,
    ebit: float,
    effective_tax: float,
    marginal_tax: float,
    growth_next_year: float,
    growth_years_2_5: float,
    margin_next_year: float,
    target_margin: float,
    margin_convergence_year: int,
    sales_to_capital_1_5: float,
    sales_to_capital_6_10: float,
    riskfree: float,
    initial_cost_of_capital: float,
    mature_erp: float,
    debt: float,
    cash: float,
    shares: float,
    minority: float = 0.0,
    non_operating_assets: float = 0.0,
    book_equity: float = 0.0,
    nol: float = 0.0,
    failure_probability: float = 0.0,
    failure_proceeds_tie: str = "V",  # "V" = fair value, "B" = book capital
    failure_proceeds_pct: float = 0.5,
    stable_cost_of_capital: Optional[float] = None,  # default: riskfree + mature ERP
    terminal_roic: Optional[float] = None,  # default: cost of capital (advantages fade)
    riskfree_after_10: Optional[float] = None,  # default: today's riskfree persists
    perpetual_growth: Optional[float] = None,  # default: = riskfree
) -> Dict[str, Any]:
    years = range(1, 11)
    rf_term = riskfree if riskfree_after_10 is None else riskfree_after_10
    g_term = rf_term if perpetual_growth is None else perpetual_growth
    r_term = rf_term + mature_erp if stable_cost_of_capital is None else stable_cost_of_capital

    # Growth: next-year rate, years 2-5 rate, then linear to g_term over years 6-10.
    growth = [growth_next_year] + [growth_years_2_5] * 4
    growth += [growth_years_2_5 - (growth_years_2_5 - g_term) / 5 * k for k in range(1, 6)]
    rev = [revenue]
    for g in growth:
        rev.append(rev[-1] * (1 + g))
    rev_term = rev[10] * (1 + g_term)

    # Margin: year 1 given, converging linearly to target by the convergence year.
    conv = margin_convergence_year
    margin = [
        (
            margin_next_year
            if t == 1
            else (
                target_margin
                if t > conv
                else target_margin - (target_margin - margin_next_year) / conv * (conv - t)
            )
        )
        for t in years
    ]

    # Tax: effective through year 5, stepping to marginal (terminal) over years 6-10.
    tax = [effective_tax] * 5 + [
        effective_tax + (marginal_tax - effective_tax) / 5 * k for k in range(1, 6)
    ]

    # Cost of capital: initial through year 5, stepping to the stable rate over 6-10.
    wacc = [initial_cost_of_capital] * 5 + [
        initial_cost_of_capital - (initial_cost_of_capital - r_term) / 5 * k for k in range(1, 6)
    ]

    s2c = [sales_to_capital_1_5] * 5 + [sales_to_capital_6_10] * 5
    rev_next = rev[2:] + [rev_term]  # 1-year lag: reinvest this year for next year's growth

    rows: List[Dict[str, float]] = []
    nol_prev, df, pv_sum = nol, 1.0, 0.0
    for i, t in enumerate(years):
        ebit_t = margin[i] * rev[t]
        if ebit_t > 0:
            nopat = ebit_t if ebit_t < nol_prev else ebit_t - (ebit_t - nol_prev) * tax[i]
        else:
            nopat = ebit_t
        nol_prev = nol_prev - ebit_t if (ebit_t < 0 or nol_prev > ebit_t) else 0.0
        reinvest = (rev_next[i] - rev[t]) / s2c[i]
        fcff = nopat - reinvest
        df /= 1 + wacc[i]
        pv = fcff * df
        pv_sum += pv
        rows.append(
            dict(
                year=t,
                growth=growth[i],
                revenue=rev[t],
                margin=margin[i],
                ebit=ebit_t,
                tax_rate=tax[i],
                nopat=nopat,
                reinvestment=reinvest,
                fcff=fcff,
                cost_of_capital=wacc[i],
                discount_factor=df,
                pv=pv,
            )
        )

    # Terminal year: marginal tax, reinvestment = g / ROIC so growth is paid for.
    ebit_term = margin[-1] * rev_term
    nopat_term = ebit_term * (1 - marginal_tax)
    roic_term = wacc[-1] if terminal_roic is None else terminal_roic
    reinvest_term = g_term / roic_term * nopat_term if g_term > 0 else 0.0
    fcff_term = nopat_term - reinvest_term
    tv = fcff_term / (r_term - g_term)
    pv_tv = tv * df

    sum_pv = pv_sum + pv_tv
    if failure_proceeds_tie == "B":
        proceeds = (book_equity + debt) * failure_proceeds_pct
    else:
        proceeds = sum_pv * failure_proceeds_pct
    operating_assets = sum_pv * (1 - failure_probability) + proceeds * failure_probability
    equity = operating_assets - debt - minority + cash + non_operating_assets

    return {
        "forecast": rows,
        "terminal": dict(
            growth=g_term,
            revenue=rev_term,
            ebit=ebit_term,
            nopat=nopat_term,
            reinvestment=reinvest_term,
            fcff=fcff_term,
            cost_of_capital=r_term,
            roic=roic_term,
        ),
        "terminal_value": tv,
        "pv_terminal_value": pv_tv,
        "pv_fcff_10y": pv_sum,
        "operating_assets": operating_assets,
        "equity_value": equity,
        "value_per_share": equity / shares,
    }
