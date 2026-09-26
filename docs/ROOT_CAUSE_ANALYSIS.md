# Root Cause Analysis: Stock Price, Ratio & DCF Accuracy

> **Date**: 2026-09-26 (updated: all findings resolved)
> **Status**: 17 of 17 findings fixed and verified against live data
> **Scope**: `src/tools/market_data.py`, `src/api/routes.py`, `static/dcf.html`, `static/index.html`, `static/js/app.js`, `static/dashboard/*`
> **Trigger**: User-reported accuracy issues in stock prices, financial ratios, and DCF valuation, cross-checked against Screener.in

---

## Executive Summary

A full audit of the ratio, DCF, and quote calculation paths — plus every page that renders them — found **17 distinct defects**, ranging from a silent crash bug that zeroed out DCF valuations, to four ratios that were never calculated at all (hardcoded placeholder strings), to an entire page (`/dashboard`) whose headline numbers, "agent reasoning" narrative, and news feed were all disconnected from any real data source. Every fix below was verified two ways: (1) direct calls to the Python functions against live yfinance data, and (2) the actual rendered page in a browser, re-fetching from the running server.

> **Reading the "Verified" figures**: prices, fair values, and scores quoted below are what the live data feed returned during the audit. Market-dependent numbers (e.g. a share price or DCF target) will differ if re-run today; the *structural* conclusions — a 100x unit error, a hardcoded string, a crash swallowed by `except: pass` — do not depend on market data.

The single root cause underlying most of the ratio/DCF defects: **two independent, undocumented unit-conversion assumptions about yfinance's `info` dict were wrong**, and a **third code path duplicated the same broken logic** instead of reusing the fixed version. Most of the rest were leftover placeholders from an earlier prototype (`/dashboard`), or a client-side JS reimplementation that had drifted from the server-side formula it was supposed to mirror (`dcf.html`).

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | DCF crash on missing `totalRevenue` (undefined variable) | Critical | ✅ Fixed |
| 2 | Altman Z-Score was a hardcoded string, not calculated | Critical | ✅ Fixed |
| 3 | ROCE was `ROE × 1.1`, not a real formula | Critical | ✅ Fixed |
| 4 | Interest Coverage Ratio was a hardcoded string | Critical | ✅ Fixed |
| 5 | Cash Conversion Cycle was hardcoded to `"42 Days"` | Critical | ✅ Fixed |
| 6 | `/dashboard` page metrics disconnected from any real data | Critical | ✅ Fixed |
| 6b | `/dashboard`'s "agent reasoning" text stated numbers that contradicted the real metrics on the same page | Critical | ✅ Fixed |
| 6c | `/dashboard`'s "Real-Time" news feed was 3 fabricated headlines | High | ✅ Fixed |
| 7 | Debt-to-Equity 100x overstated for low-debt companies (2 locations) | High | ✅ Fixed |
| 8 | Dividend yield 100x overstated | High | ✅ Fixed |
| 9 | DCF sensitivity matrix ignored WACC on the client side | High | ✅ Fixed |
| 10 | DCF assumptions silently rounded before re-use, corrupting slider recalculation | Medium | ✅ Fixed |
| 11 | DCF/Ratios bypassed the configured data provider | Medium | ✅ Fixed |
| 12 | D&A/CapEx/NWC used fixed 3%/4%/2% for every company | Medium | ✅ Fixed |
| 13 | Stale ticker alias (Zomato → delisted BSE code) | Medium | ✅ Fixed |
| 14 | `/api/v1/analyze` sentiment/risk are hardcoded stubs | Medium | ✅ Fixed |
| 15 | Dead mock-data table (`STOCK_DATABASE`) in `app.js` | Low | ✅ Fixed |

---

## Root Cause Themes

### Theme A — Two wrong unit-conversion assumptions (findings #7, #8)

`yfinance`'s `info` dict is inconsistent about whether a "ratio-like" field is a fraction (`0.32` = 32%) or already a percentage (`0.32` = 0.32%). The code guessed wrong for two fields:

- `dividendYield`: code assumed a fraction and multiplied by 100. It is already a percentage. Result: Apple showed a 32.00% yield instead of 0.32%.
- `debtToEquity`: code used a heuristic (`divide by 100 only if the value is > 5`) to guess which form it was in. This is unsound — a genuinely low-debt company's *correct* value (e.g. `1.41` meaning 1.41%) is indistinguishable from a *ratio* of `1.41` (141% leverage) by magnitude alone. Utique Enterprises (real D/E 0.01, confirmed against Screener.in) was displayed as `1.41` — a 100x error.

**Fix**: both fields are now always divided by 100, based on empirical verification against multiple tickers (`AAPL`, `RELIANCE`, `UTIQUE`) and cross-checked by hand-computing the ratio from raw balance-sheet line items (`Total Debt / Stockholders Equity`).

### Theme B — Four ratios were never calculated (findings #2–#5)

`get_company_ratios_profile()` in `market_data.py` advertised a "comprehensive 16-point financial ratios profile," but four of the sixteen were never computed from the company's actual financials. Three were placeholder strings — Altman Z-Score and Interest Coverage picked by a coarse if/else on the Debt-to-Equity value, and Cash Conversion Cycle a single constant — and the fourth, ROCE, was a made-up proxy (`ROE × 1.1`) rather than the real formula:

```python
# Before (src/tools/market_data.py, solvent-company branch)
altman_str = "3.60" if de_val < 0.8 else "2.20"
icr_str = "8.5x" if de_val < 1.0 else "2.5x"
roce_str = f"{roe_val * 1.1:.1f}%"
...
# Cash Conversion Cycle, unconditionally:
ccc_str = "42 Days"
```

Every company with D/E < 0.8 received an identical Altman Z-Score of exactly 3.60, and every solvent company was shown a Cash Conversion Cycle of exactly "42 Days" regardless of its actual inventory, receivables, or payables. This violates the analysis principles the audit was run against (the financial-analyst and investment-researcher guidelines used during the review, which are not part of this repository): *"Precision without accuracy is noise"* and *"The best research is falsifiable."*

**Fix**: replaced with the standard formulas, computed from balance sheet / income statement data already being fetched:
- **ROCE** = EBIT ÷ (Total Assets − Current Liabilities)
- **Interest Coverage Ratio** = EBIT ÷ Interest Expense
- **Altman Z-Score** = 1.2·(WC/TA) + 1.4·(RE/TA) + 3.3·(EBIT/TA) + 0.6·(MVE/TL) + 1.0·(Sales/TA)
- **Cash Conversion Cycle** = DIO + DSO − DPO, from Inventory/Receivables/Payables ÷ COGS or Revenue × 365

Where the underlying data genuinely isn't available (e.g. a bank has no meaningful inventory turnover), the ratio now correctly reports `N/A` instead of a fabricated number.

### Theme C — A crash bug that silently zeroed out DCF valuations (finding #1)

```python
# Before (src/tools/market_data.py:435, inside get_company_dcf_profile)
if raw_rev <= 0:
    try:
        fin = t.financials   # <- `t` was never defined anywhere in this function
        ...
    except Exception:
        pass                 # NameError swallowed silently
```

Any company whose `info["totalRevenue"]` field was missing or zero — which happens for a meaningful share of non-US tickers — would hit this branch, immediately raise `NameError: name 't' is not defined`, get silently caught, and fall through to `base_rev = 0.0`. The function then executed its "zero-revenue / shell company" path for what might be a perfectly healthy operating business, producing a valuation based solely on net cash position. This is the most severe kind of bug: it doesn't error out, it returns a *plausible-looking but wrong* answer.

**Fix**: use `provider.get_income_statement(resolved_sym)` (the already-injected data provider) instead of the undefined `t`.

### Theme D — Duplicated logic that only got fixed once (findings #7, #14)

The D/E scaling bug existed in **two places**: `src/tools/market_data.py::get_company_ratios_profile` (feeds `/ratios.html`) and `src/api/routes.py::get_live_quote` (feeds the landing page's hero card and `/dashboard`). These are independent reimplementations of the same calculation rather than one shared function — fixing the first did nothing for the second until it was found separately by testing the landing page directly. `/api/v1/analyze`'s `sentiment`/`risk` stubs are a related symptom: multiple endpoints independently approximate "the same" analysis with different levels of rigor, so a reader can get a different ROCE, D/E, or sentiment score depending on which endpoint or page they hit.

**Recommendation**: consolidate ratio/scoring logic into one shared module that every endpoint calls, rather than maintaining parallel implementations. Not done in this session — the immediate duplicate (`routes.py`) was patched in place to close the accuracy gap without a larger refactor.

### Theme E — Frontend/backend drift in the interactive DCF model (findings #9, #10)

`static/dcf.html` contains a full client-side reimplementation of the DCF math (`calculateDCF()`) so the sliders can recompute instantly without a server round-trip. Two independent bugs were found here:

1. **`renderSensitivityMatrix()`** built each row's parameters as `{...baseParams, terminalG: g}` — it only ever varied terminal growth, never WACC, despite iterating over `waccSteps` and labeling each row with a WACC value. Every row rendered identical numbers. Root cause: `calculateDCF()` always recomputed WACC internally from `rf`/`beta`/`erp`, with no way to override it, so the loop's `w` value was computed but discarded.

2. **Slider value snapping**: `<input type="range">` elements silently round any programmatically-assigned value to the nearest `step`. The sliders were initialized from the live API response (`slider.value = data.margin`), but with `step="0.5"`, an actual margin of `12.331%` silently became `12.5%`. Compounded with the API also rounding `margin`/`growth` to 1 decimal place before sending them, the interactive page's "Base Case" fair value diverged from the server's own answer by ~5% (₹1,382.8 vs. the correct ₹1,317.7 for Reliance) — while displaying itself as the precise, live-recalculated figure.

**Fix**: added a `waccOverride` parameter to `calculateDCF()`; the API now returns growth/margin/beta/terminal-growth/risk-free-rate/ERP at 4-decimal precision instead of 1–2; all six DCF sliders use `step="any"` instead of a discrete step, eliminating snapping entirely. Verified the interactive page now matches the Python backend to the cent.

---

## Detailed Findings

### 1. DCF crash on missing revenue → silent $0 valuation
- **File**: `src/tools/market_data.py`, `get_company_dcf_profile()`
- **Symptom**: Any ticker without `info["totalRevenue"]` populated got a DCF fair value based only on net cash, as if it were a pre-revenue shell company.
- **Root cause**: reference to an undefined variable `t`, caught by a bare `except: pass`.
- **Fix**: use the injected `provider.get_income_statement()` instead.
- **Verified**: AAPL, MSFT, RELIANCE, TSLA, NVDA, TCS, PAYTM all return non-zero, non-crashing forecasts.

### 2–5. Four fabricated ratios (Altman Z, ROCE, Interest Coverage, Cash Conversion Cycle)
- **File**: `src/tools/market_data.py`, `get_company_ratios_profile()`
- **Symptom**: identical, static values shown for large swaths of companies regardless of their actual financials.
- **Fix**: real formulas computed from balance sheet / income statement data (see Theme B above).
- **Verified**: AAPL → Altman 12.73 (Safe), ROCE 68.7%, ICR 33.8x, CCC −71 days; CANBK (a bank) → all four correctly report `N/A` (score dropped from a false 100% to an honest 50%, see finding on data confidence below).

### 6. `/dashboard` page shows numbers unconnected to any real data — **fixed**
- **Files**: `static/dashboard/app.js`, `static/dashboard/index.html`, `src/api/routes.py` (new `/api/v1/history/{symbol}` endpoint)
- **Symptom**: The metric cards (Current Price, Agent Consensus, Technical RSI, Trailing P/E, VaR) showed `$224.23`, `0.78 / 1.0`, `58.4 Neutral`, `32.8x Fair Value` on page load — and **stayed exactly there, for every ticker**, even after a successful `/api/v1/analyze` call.
- **Root cause**: `renderApiResponse(data)` (called on API success) only set the chart title from `data.symbol` and regenerated the chart using `generatePriceHistory()` — a pure `Math.random()` walk. It never wrote to `elements.valPrice`, `valRsi`, `valPe`, or the consensus/VaR fields at all. Those DOM nodes were only ever updated by `renderSymbolData()`, the *failure* fallback path, which independently fabricated a price from a 6-ticker hardcoded table (or `150 + random()*100` for anything else), a random RSI (`45 + random()*25`), a random P/E (`22 + random()*20`), and a DCF target that was *always* `price × 1.12` (a flat, universal "+12.0% upside" for literally every stock).
- **Fix**: rewrote `runAnalysis()` to fetch `/api/v1/analyze`, `/api/v1/quote`, `/api/v1/dcf`, and a new `/api/v1/history/{symbol}` endpoint (thin wrapper around the already-correct `get_historical_data()` tool) in parallel, and wrote every metric pill from those real responses. Added real `risk` (volatility/VaR/Sharpe from historical returns) and `sentiment` (FinBERT via `analyze_news_impact`) to `/api/v1/analyze` — see finding #14. Where a field genuinely can't be computed, it now shows `N/A` rather than a plausible-looking placeholder; there is no more random-number fallback path anywhere on this page.
- **Verified**: AAPL → Price `$341.07 +1.53%` (matches the price verified all session), RSI `65.7 Neutral`, P/E `39.1x` (matches the verified `39.068733`), VaR `-2.01% Medium`, DCF target `$164.70 (-51.7%)` (matches the backend's independently-verified `fair_value_per_share`), Sharpe `1.33`, sentiment `+0.21 (Positive)` — all internally consistent and reproducible from `/api/v1/analyze`+`/quote`+`/dcf` directly.

### 6b. `/dashboard`'s "agent reasoning" narrative stated numbers that contradicted the real metrics next to it — **fixed**
- **File**: `static/dashboard/index.html`
- **Symptom**: below the (now-real) metric pills, an "Orchestrated Agent Execution Stream" section narrated 4 fake "agent steps" with their own, different, hardcoded numbers — e.g. "Calculated 14-period RSI at 58.4 (Neutral)" and "5-year DCF model projects intrinsic target of $248.50" — directly underneath metric pills that (correctly) showed RSI `65.7` and DCF target `$164.70`. Fixing #6 without fixing this would have made the page *more* obviously broken, not less: two different "real-time" numbers for the same metric, ten pixels apart.
- **Root cause**: static HTML text, never wired to any data source at all (not even the old random fallback).
- **Fix**: added element IDs to each of the 4 reasoning steps; `renderReasoningStream()` now builds each sentence from the same `/api/v1/analyze` + `/api/v1/dcf` response objects the metric pills use, so the two can't drift apart.
- **Verified**: AAPL reasoning stream now reads "Calculated 14-period RSI at 65.7 (NEUTRAL)... Beta of 1.08... 5-year DCF model... projects an intrinsic value of $164.70, a -51.7% discount" — matching the metric pills exactly.

### 6c. `/dashboard`'s "Real-Time" news feed was 3 fabricated headlines — **fixed**
- **File**: `static/dashboard/index.html`, `src/api/routes.py`
- **Symptom**: a card labeled "News Sentiment & Market Catalyst — Real-Time" statically showed the same three invented headlines ("Services division revenue growth accelerates...", attributed to "Bloomberg · 2h ago" with a score of "+0.82 Bullish") for every single ticker searched, AAPL or otherwise.
- **Root cause**: static HTML, no backing data.
- **Fix**: extended `_compute_sentiment()` to include the top 3 real, FinBERT-scored articles from `analyze_news_impact()` (`title`, `source`, `published_at`, per-article `score`/`label`); `renderNewsFeed()` renders them, or an honest "No recent news sentiment available" when there genuinely are none.
- **Verified**: AAPL now shows real headlines ("Trump says China's Xi 'seemed to like' renaming AI as super intelligence" — Yahoo Finance, +0.06 Neutral; etc.), matching the 10 articles counted in the real aggregate sentiment score shown in the metric pills.

### 7. Debt-to-Equity overstated 100x for low-debt companies (two locations)
- **Files**: `src/tools/market_data.py::get_company_ratios_profile`, `src/api/routes.py::get_live_quote`
- **Symptom**: Utique Enterprises showed D/E `1.41` (danger) instead of the correct `0.01` (safe); confirmed against Screener.in's published `0.01`.
- **Root cause**: `de_val = float(de) / 100 if float(de) > 5 else float(de)` — yfinance's `debtToEquity` is *always* a percentage value, never a raw ratio; the ">5" heuristic misclassified small-but-correct percentages as already-a-ratio.
- **Fix**: always divide by 100. Applied in both locations independently (they were separate, duplicated implementations — see Theme D).
- **Verified**: UTIQUE → `0.01` (was `1.41`) on both `/ratios.html` and the landing-page hero card; AAPL (`0.78`) and RELIANCE (`0.37`) unchanged, confirming no regression on values that happened to be correct before.

### 8. Dividend yield overstated 100x
- **File**: `src/tools/market_data.py::get_company_ratios_profile`
- **Symptom**: Apple showed a 32.00% dividend yield instead of ~0.32%.
- **Root cause**: same class of bug as #7 — `dividendYield` is already a percentage; code multiplied by 100 anyway.
- **Fix**: display the raw value directly; adjusted the "good/caution" threshold from `> 0.01` (fraction-based) to `> 1.0` (percentage-based) accordingly.
- **Verified**: AAPL → 0.32%, RELIANCE → 0.49% (both match real-world figures).

### 9. Interactive DCF sensitivity matrix ignored WACC (client-side)
- **File**: `static/dcf.html`
- **Symptom**: all 5 WACC rows in "Component 5: 2D Sensitivity Matrix" showed identical values; only the terminal-growth columns varied.
- **Root cause**: `calculateDCF()` always recomputed WACC internally from `rf`/`beta`/`erp`; `renderSensitivityMatrix()` never had a way to force a specific WACC per row.
- **Fix**: added `params.waccOverride`, used by `calculateDCF()` when present; `renderSensitivityMatrix()` now passes each row's WACC step.
- **Verified**: Reliance matrix now correctly ranges from ₹3,626 (WACC 7.04%) to ₹774 (WACC 10.04%) at the same terminal growth, matching the Python backend's independently-computed matrix.

### 10. DCF slider precision loss corrupted the "live" recalculation
- **Files**: `static/dcf.html`, `src/tools/market_data.py`
- **Symptom**: the interactive page's displayed "Base Case" fair value for Reliance (₹1,382.8) didn't match the API's own reported fair value (₹1,317.73) for the same inputs.
- **Root cause**: (a) `<input type="range">` silently snaps any assigned value to the nearest `step`; sliders were initialized from live data with `step="0.5"`, corrupting e.g. `29.7` → `29.5`; (b) the API itself rounded `growth`/`margin`/`beta`/`terminal_g`/`rf`/`erp` to 1–2 decimals before sending them, so even a perfect slider would have recalculated from an already-lossy number (yfinance's real `operatingMargins` for Reliance is `12.331%`, sent to the frontend as `12.3`).
- **Fix**: bumped those six API fields to 4-decimal precision; changed all six DCF sliders to `step="any"` (disables snapping entirely, per the HTML spec).
- **Verified**: frontend `calculateDCF()` output for Reliance now equals `1317.7255...`, matching the backend's `1317.73` to the cent.

### 11. DCF/Ratios bypassed the configured data provider
- **File**: `src/tools/market_data.py`
- **Symptom**: `get_company_dcf_profile` and `get_company_ratios_profile` called `yfinance.Ticker(...)` directly, while every other tool in the codebase goes through `src/data/provider.py`'s `get_provider()` abstraction (which supports FMP, Alpha Vantage, and automatic fallback per `DATA_PROVIDER`/`DATA_FALLBACK_PROVIDER` env vars, per `CLAUDE.md`'s documented architecture).
- **Impact**: if a deployment sets `DATA_PROVIDER=fmp`, every other tool would use FMP, but DCF and Ratios would silently keep using yfinance — an invisible, undocumented inconsistency.
- **Fix**: replaced direct `yfinance.Ticker(...)` calls with `provider.get_balance_sheet()` / `get_income_statement()` / `get_cash_flow()`.
- **Verified**: no behavior change under the default `yfinance` provider (confirmed via full regression across 8 tickers); architecturally now consistent with the rest of the codebase.

### 12. D&A/CapEx/NWC used fixed 3%/4%/2% for every company
- **File**: `src/tools/market_data.py::get_company_dcf_profile`
- **Symptom**: a capital-light software company and a capital-intensive refiner got the identical assumption that CapEx = 4% of revenue.
- **Fix**: derive these from the company's own trailing cash-flow actuals (`Depreciation And Amortization`, `Capital Expenditure`, `Change In Working Capital`, each ÷ revenue) when available, falling back to the generic defaults only when the data is missing.
- **Verified**: Reliance now uses D&A 5.1% / CapEx 10.9% / NWC 1.1% (its real, capital-intensive profile) instead of the generic 3/4/2; Apple uses D&A 2.5% / CapEx 2.7% / NWC 5.4% (its real, capital-light profile).

### 13. Stale ticker alias: Zomato → delisted BSE code
- **File**: `src/tools/market_data.py::COMMON_TICKER_ALIASES`
- **Symptom**: searching "ZOMATO" failed entirely (`Unable to identify company or ticker`).
- **Root cause**: alias pointed to `543320.BO`, a BSE code that stopped returning data after Zomato Ltd. renamed to Eternal Ltd. and changed its primary listing.
- **Fix**: updated alias to `ETERNAL.NS` (confirmed live and trading).
- **Verified**: `ZOMATO` now resolves to `ETERNAL.NS` at ₹335.00, with a full ratios profile.

### 14. `/api/v1/analyze` sentiment/risk are hardcoded stubs — **fixed**
- **File**: `src/api/routes.py::analyze_stock`
- **Symptom**: the endpoint's docstring claims "comprehensive analysis including technical, fundamental, sentiment, and risk analysis," and technical analysis genuinely is computed (real RSI/MACD/moving averages via `src/tools/technical_indicators.py`). But:
  ```python
  sentiment={"status": "analyzed", "score": 0.5},
  risk={"volatility": "medium"},
  ```
  were literal constants — every single ticker got `sentiment.score = 0.5` and `risk.volatility = "medium"`, regardless of any actual news sentiment or volatility calculation.
- **Fix**: added `_compute_risk_metrics()` — real daily/annualized volatility, historical VaR(95%), and Sharpe ratio from the ticker's actual daily returns (the same formulas already used, but never wired up, in `src/agents/risk.py`'s tool functions). Added `_compute_sentiment()` — calls the existing, working `analyze_news_impact()` (FinBERT-based, with an automatic VADER/neutral fallback chain already built into `src/tools/sentiment_engine.py`), returning a genuine aggregate score/label/confidence plus the top 3 scored articles, or an honest `"status": "unavailable"` if the news pipeline can't run for that request — never a fabricated constant.
- **Verified**: live call for AAPL returned real, non-constant values: `risk = {annual_volatility_pct: 24.47, var_95_daily_pct: -2.01, sharpe_ratio: 1.33, volatility: "Medium"}`, `sentiment = {score: 0.207, label: "Positive", confidence: 0.813, engine: "finbert", articles_analyzed: 10}` — computed from 10 real news articles fetched live from Yahoo Finance.
- **Note**: FinBERT (a ~440MB transformer model, already an existing dependency — `transformers`/`torch` were already in the project's `.venv`) takes ~10–90s to load on the *first* request after a server restart while it downloads/loads into memory; subsequent requests reuse the cached in-process model and are fast. This is inherent to the existing sentiment engine design, not something introduced by this fix.
- **Deployment note (added later)**: the Vercel deployment installs a slim dependency set without `transformers`/`torch` to fit the 500 MB function limit, so FinBERT is not available there and the sentiment engine uses its fallback chain instead. Local and Docker installs (full `requirements.txt`) still use FinBERT.

### 15. Dead mock-data table in `app.js` — **fixed**
- **File**: `static/js/app.js`
- **Finding**: a fully-formed table of ~10 hardcoded fake stock profiles (fabricated P/E, ROE, sentiment scores, "STRONG BUY 95.4% Confidence" for Reliance, etc.), plus its two lookup helpers `isIndianStock()` and `normalizeTickerKey()`, existed in the file but were **never referenced anywhere else in the codebase** (confirmed via repo-wide grep). It wasn't the source of any of the bugs in this report — the live page genuinely calls `/api/v1/quote` — but was dead weight that could confuse a future maintainer into thinking it was live-wired, or get accidentally reconnected.
- **Fix**: deleted all ~468 lines (`isIndianStock`, `normalizeTickerKey`, `STOCK_DATABASE`) from `static/js/app.js`.
- **Verified**: `node --check` passes; landing page (`/`) loads and functions identically with no console errors, confirming nothing depended on the removed code.

---

## What Was *Not* Fabricated (verified as legitimate)

Two things surfaced during testing that looked like bugs but checked out as correct once traced to source:

- **TSLA and PAYTM DCF fair value = $0**: both have thin operating margins (2.0% and 2.9%) that, combined with their real (trailing-actual) CapEx intensity, produce negative free cash flow under the model's constant-margin 5-year projection. The equity bridge goes negative and is correctly floored at `$0` rather than shown as a negative share price. Hand-verified the full year-by-year FCF and terminal value arithmetic for both.
- **Reliance's Interest Coverage Ratio (42.0x) and Current Ratio (69.47) vs. Screener.in's different figures (56.0x, 18.48)**: both of our numbers trace exactly to yfinance's own reported EBIT/Interest Expense and Current Assets/Current Liabilities for the company. The discrepancy with Screener.in reflects a different data source/fiscal-period normalization, not a defect in our formula.

---

## Still Open: Placeholder Data Outside This Audit's Scope

*Added 2026-09-26.* The 17 findings above covered the quote, ratio, and DCF paths
and the pages that render them — and all 17 are fixed. A later review of the rest
of `src/api/routes.py` found endpoints that still return **the same hardcoded
values for every request**. They were not part of the original audit, so they are
not counted in the 17 and are **not fixed**:

| Endpoint / function | What it returns today |
|---|---|
| `GET /api/v1/sentiment/{symbol}` | Always `"positive"`, score `0.65`, news `0.7`, social `0.6` — for any ticker. (Real sentiment is available from `POST /api/v1/analyze`, finding #14.) |
| `GET /api/v1/market/summary` | Fixed SPY/QQQ/DIA prices (`470.50`, `395.20`, `375.30`) and `"market_status": "open"` at all hours |
| `POST /api/v1/portfolio` | Real per-stock prices, but a fixed `diversification_score` of `0.7`, `risk_assessment` of `"moderate"`, and one canned recommendation |
| `POST /api/v1/reports` | A stub report whose body is *"Detailed analysis available upon request."* |
| `financial_metrics.compare_to_industry()` | Fixed benchmarks for four industries (Technology, Healthcare, Finance, Consumer), not real peer data |

These are the same class of defect as findings #6 and #14 — plausible-looking
output with no data behind it — and should be fixed (computed from real data) or
removed before being relied on.

---

## Recommendations for Future Work

All 17 findings from the original audit are now fixed (see status table above). Beyond the open placeholders listed in the previous section, what's left is architectural cleanup, not accuracy bugs:

1. **Consolidate duplicated ratio/scoring logic.** `market_data.py::get_company_ratios_profile`, `routes.py::get_live_quote`, and `routes.py::analyze_stock` each independently compute overlapping metrics (D/E, P/E-based recommendations, risk scores) with different levels of rigor. A single shared module would prevent the "fixed in one place, still broken in another" pattern that caused finding #7 to exist twice.
2. **Pre-warm the FinBERT sentiment model at server startup** (rather than lazily on the first `/api/v1/analyze` call) so the first real user of the app after a deploy doesn't see a 10–90s delay. A simple `@app.on_event("startup")` hook calling `src.tools.sentiment_engine._get_analyzer()` once would do it.
3. **Consider disclosing the "AI Agent Team Verdict" methodology.** The landing page's recommendation/confidence badge (`routes.py::get_live_quote`) is a deterministic rule (P/E threshold × price direction → a fixed confidence percentage like "88.5%"), not an ensemble of the specialized agents the marketing copy describes. It isn't fabricated data — the inputs are real — but the framing implies more sophistication than the implementation currently has. The same is true of `/dashboard`'s "Agent Synthesis" recommendation, which is the same `/api/v1/analyze` RSI/MACD rule, not a literal multi-agent vote, even though it's now built from entirely real inputs.
