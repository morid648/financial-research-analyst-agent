"""src/tools/ginzu.value_fcff must reproduce Damodaran's fcffsimpleginzu.xlsx exactly.

Expected values: the workbook's own Almarai example (Apr 2026 version, value/share
7.18784) and ten variants recalculated by Excel itself, one per model branch.
"""

import pytest

from src.tools.ginzu import value_fcff

ALMARAI = dict(
    revenue=21765.4,
    ebit=3060.9,
    effective_tax=0.175,
    marginal_tax=0.25,
    growth_next_year=0.05,
    growth_years_2_5=0.05,
    margin_next_year=0.14063146094259696,
    target_margin=0.14063146094259696,
    margin_convergence_year=5,
    sales_to_capital_1_5=1.708537671031893,
    sales_to_capital_6_10=1.708537671031893,
    riskfree=0.0458,
    initial_cost_of_capital=0.0705501574064654,
    mature_erp=0.0423,
    debt=45063,
    cash=19000,
    shares=4315,
    minority=1558,
    non_operating_assets=21119,
    book_equity=10667.8,
)

CASES = [
    ("almarai_as_published", {}, 7.187840270062114),
    (
        "high_growth_margin_convergence",
        dict(
            growth_next_year=0.25,
            growth_years_2_5=0.15,
            margin_next_year=0.08,
            target_margin=0.20,
            margin_convergence_year=7,
        ),
        18.2986769158382,
    ),
    (
        "losses_with_nol",
        dict(
            growth_next_year=0.30,
            growth_years_2_5=0.20,
            margin_next_year=-0.05,
            target_margin=0.12,
            margin_convergence_year=4,
            nol=500,
        ),
        10.485745468411,
    ),
    (
        "failure_proceeds_at_value",
        dict(failure_probability=0.2, failure_proceeds_tie="V", failure_proceeds_pct=0.5),
        6.31837258141048,
    ),
    (
        "failure_proceeds_at_book",
        dict(failure_probability=0.3, failure_proceeds_tie="B", failure_proceeds_pct=0.4),
        6.1293088147677,
    ),
    (
        "stable_wacc_and_terminal_roic",
        dict(stable_cost_of_capital=0.09, terminal_roic=0.15),
        9.03107751101553,
    ),
    ("riskfree_after_year_10", dict(riskfree_after_10=0.03), 8.31136571006475),
    ("negative_perpetual_growth", dict(perpetual_growth=-0.02), 5.81962273440291),
    ("keep_effective_tax", dict(effective_tax=0.12, marginal_tax=0.12), 8.51305757012457),
    (
        "sales_to_capital_split_conv_year_1",
        dict(
            sales_to_capital_1_5=2.5,
            sales_to_capital_6_10=1.2,
            margin_convergence_year=1,
            margin_next_year=0.10,
            target_margin=0.18,
        ),
        9.62664353588808,
    ),
    (
        "india_like_direct_wacc",
        dict(
            riskfree=0.05,
            growth_next_year=0.12,
            growth_years_2_5=0.10,
            initial_cost_of_capital=0.125,
        ),
        6.11664730235683,
    ),
]


@pytest.mark.parametrize("name,overrides,expected", CASES, ids=[c[0] for c in CASES])
def test_matches_damodaran_workbook(name, overrides, expected):
    assert value_fcff(**{**ALMARAI, **overrides})["value_per_share"] == pytest.approx(
        expected, rel=1e-9
    )


def test_cost_of_capital_matches_workbook():
    """Almarai's 'Cost of capital worksheet' (detailed approach): E62 = 7.0550%."""
    from src.tools.ginzu import cost_of_capital

    r = cost_of_capital(
        riskfree=0.0458,
        beta=0.5145245310221007,  # workbook's levered beta (C57)
        erp=0.05580814643676354,  # operating-regions ERP (B27)
        pretax_cost_of_debt=0.052803,
        marginal_tax=0.25,
        market_equity=4315 * 72.28,
        book_debt=45063,
        interest_expense=493.4,
        debt_maturity=3,
    )
    assert r["market_value_of_debt"] == pytest.approx(39953.64461186393, rel=1e-12)
    assert r["cost_of_equity"] == pytest.approx(0.07451466037258848, rel=1e-12)
    assert r["cost_of_capital"] == pytest.approx(0.0705501574064654, rel=1e-12)


def test_rd_converter_matches_workbook():
    """The workbook's 'R& D converter' example: 3-year life."""
    from src.tools.ginzu import capitalize_rd

    r = capitalize_rd(85622, [73213, 56052, 42740], life=3)
    assert r["research_asset"] == pytest.approx(153114.6666666667, rel=1e-12)
    assert r["amortization"] == pytest.approx(57335.0, rel=1e-12)
    assert r["ebit_adjustment"] == pytest.approx(28287.0, rel=1e-12)
