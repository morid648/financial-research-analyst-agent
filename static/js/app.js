/**
 * FinResearch AI - Interactive Stock Studio & Multi-Agent Analyzer
 * Full Multi-Currency Support (₹ INR for Indian Stocks, $ USD for US/Global Stocks)
 * Key Ratio Snippets Under Chart & Deep-Link to Multi-Segment Ratio Page
 */

let stockChartInstance = null;
let lastChartData = null;

// Price line in the text colour; the series direction is already shown by the change badge,
// so the chart itself stays neutral. Colours are read from CSS tokens so it follows the theme.
function renderLiveStockChart(data) {
  const ctx = document.getElementById('stockChart');
  if (!ctx || typeof Chart === 'undefined') return;
  lastChartData = data;

  const curr = data.currency || '$';
  const css = window.cssVar || (() => '');
  const line = css('--text') || '#ecebe8';
  const grid = css('--border') || '#2a2c31';
  const muted = css('--text-3') || '#8f8d88';
  const surface = css('--surface') || '#17181b';
  const fmt = (v) => `${curr}${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (stockChartInstance) stockChartInstance.destroy();

  stockChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        label: `${data.symbol} close (${curr})`,
        data: data.prices,
        borderColor: line,
        borderWidth: 1.75,
        fill: false,
        // Monotone smoothing: rounded, but never overshoots an actual close
        cubicInterpolationMode: 'monotone',
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: line,
        pointHoverBorderColor: surface
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: surface,
          titleColor: muted,
          bodyColor: line,
          borderColor: grid,
          borderWidth: 1,
          padding: 10,
          displayColors: false,
          titleFont: { family: 'IBM Plex Sans', size: 11 },
          bodyFont: { family: 'IBM Plex Mono', size: 12 },
          callbacks: { label: (c) => fmt(c.parsed.y) }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          border: { color: grid },
          ticks: { color: muted, font: { family: 'IBM Plex Mono', size: 11 } }
        },
        y: {
          position: 'right',
          grid: { color: grid, drawTicks: false },
          border: { display: false },
          ticks: {
            color: muted,
            padding: 8,
            maxTicksLimit: 5,
            font: { family: 'IBM Plex Mono', size: 11 },
            callback: (val) => `${curr}${Number(val).toLocaleString('en-IN')}`
          }
        }
      }
    }
  });
}

window.addEventListener('themechange', () => {
  if (lastChartData) renderLiveStockChart(lastChartData);
});

// Update Studio UI with Selected Stock & Proper Currency, Risk Ratings, & Ratio Snippets
async function updateStockStudio(rawInput) {
  const query = (rawInput || '').trim();
  if (!query) return;

  const errBanner = document.getElementById('studioErrorBanner');
  const errText = document.getElementById('studioErrorText');
  const loadingBanner = document.getElementById('studioLoadingBanner');
  const loadingText = document.getElementById('studioLoadingText');
  const searchBtn = document.getElementById('studioSearchBtn');

  // Clear previous errors, show loading state
  if (errBanner) errBanner.style.display = 'none';
  if (loadingBanner) {
    if (loadingText) loadingText.textContent = `Fetching quote for ${query.toUpperCase()}…`;
    loadingBanner.style.display = 'flex';
  }
  if (searchBtn) {
    searchBtn.disabled = true;
    searchBtn.setAttribute('aria-busy', 'true');
    document.querySelector('.studio')?.classList.add('is-loading');
  }

  try {
    const res = await fetch(`/api/v1/quote/${encodeURIComponent(query)}`);
    if (!res.ok) {
      let errorMsg = `Unable to identify company or ticker '${query}'. Please use a specific ticker symbol (e.g., AAPL, MSFT, NVDA for US stocks, or RELIANCE.NS, TCS.NS, CANBK.NS for Indian stocks).`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          errorMsg = errJson.detail;
        } else if (errJson && errJson.error) {
          errorMsg = errJson.error;
        }
      } catch (_) {}

      if (errBanner && errText) {
        errText.textContent = errorMsg;
        errBanner.style.display = 'flex';
      }
      return;
    }

    const apiData = await res.json();

    // Map API response to Studio structure
    const isIndian = apiData.currency === 'INR' || apiData.currency_code === 'INR' || apiData.currency === '₹' || apiData.currency_symbol === '₹' || (apiData.symbol && (apiData.symbol.endsWith('.NS') || apiData.symbol.endsWith('.BO')));
    const currSym = apiData.currency_symbol || apiData.currency || (isIndian ? '₹' : '$');

    // Parse numeric price safely
    let numPrice = null;
    if (apiData.raw_price !== undefined && apiData.raw_price !== null && !isNaN(Number(apiData.raw_price))) {
      numPrice = Number(apiData.raw_price);
    } else if (apiData.price !== undefined && apiData.price !== null) {
      if (typeof apiData.price === 'number') {
        numPrice = apiData.price;
      } else {
        const cleaned = String(apiData.price).replace(/[^0-9.-]+/g, "");
        const parsed = parseFloat(cleaned);
        if (!isNaN(parsed)) numPrice = parsed;
      }
    }

    // Parse numeric change safely
    let numChange = null;
    if (apiData.change_pct !== undefined && apiData.change_pct !== null && !isNaN(Number(apiData.change_pct))) {
      numChange = Number(apiData.change_pct);
    } else if (apiData.raw_change !== undefined && apiData.raw_change !== null && !isNaN(Number(apiData.raw_change))) {
      numChange = Number(apiData.raw_change);
    } else if (apiData.change !== undefined && apiData.change !== null) {
      if (typeof apiData.change === 'number') {
        numChange = apiData.change;
      } else {
        const cleaned = String(apiData.change).replace(/[^0-9.-]+/g, "");
        const parsed = parseFloat(cleaned);
        if (!isNaN(parsed)) numChange = parsed;
      }
    }

    const isUp = (numChange !== null) ? (numChange >= 0) : true;
    const recType = (apiData.recType === 'high-risk' || apiData.recType === 'bearish' || (apiData.recommendation && apiData.recommendation.signal && (apiData.recommendation.signal.includes('RISK') || apiData.recommendation.signal.includes('AVOID') || apiData.recommendation.signal.includes('CAPITAL') || apiData.recommendation.signal.includes('DISTRESSED') || apiData.recommendation.signal.includes('SELL')))) ? 'high-risk' : (isUp ? 'bullish' : 'neutral');

    const heroPrice = document.getElementById('studioHeroPrice');
    const heroChange = document.getElementById('studioHeroChange');
    const heroSymbol = document.getElementById('studioHeroSymbol');
    const heroName = document.getElementById('studioHeroName');
    const recSignal = document.getElementById('studioRecSignal');
    const recConfidence = document.getElementById('studioRecConfidence');
    const recBanner = document.getElementById('studioVerdict');

    if (heroPrice) {
      if (numPrice !== null && !isNaN(numPrice)) {
        heroPrice.textContent = `${currSym}${numPrice.toLocaleString(isIndian ? 'en-IN' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      } else if (typeof apiData.price === 'string' && apiData.price.trim().length > 0) {
        heroPrice.textContent = apiData.price;
      } else {
        heroPrice.textContent = `${currSym}0.00`;
      }
    }
    if (heroSymbol) heroSymbol.textContent = apiData.symbol || query;
    if (heroName) heroName.textContent = apiData.name || apiData.symbol || query;

    if (heroChange) {
      if (numChange !== null && !isNaN(numChange)) {
        heroChange.textContent = `${isUp ? '+' : ''}${numChange.toFixed(2)}%`;
      } else if (typeof apiData.change === 'string' && apiData.change.trim().length > 0) {
        heroChange.textContent = apiData.change;
      } else {
        heroChange.textContent = '+0.00%';
      }
      heroChange.className = `stock-hero-change ${isUp ? 'up' : 'down'}`;
    }

    if (recSignal && apiData.recommendation) {
      recSignal.textContent = apiData.recommendation.signal;
      if (recBanner) recBanner.dataset.tone = recType === 'high-risk' ? 'risk' : (recType === 'bullish' ? 'positive' : 'neutral');
    }

    if (recConfidence && apiData.recommendation) {
      recConfidence.textContent = apiData.recommendation.confidence;
    }

    // Update Sub-Agent Scorecards
    function updateMetricRow(scoreId, descId, metricObj) {
      const scoreEl = document.getElementById(scoreId);
      const descEl = document.getElementById(descId);
      if (scoreEl && metricObj) {
        scoreEl.textContent = metricObj.score;
        scoreEl.className = `score-badge ${metricObj.type || (metricObj.score.toLowerCase().includes('high') ? 'bearish' : 'bullish')}`;
      }
      if (descEl && metricObj) descEl.textContent = metricObj.desc;
    }

    if (apiData.scorecards) {
      updateMetricRow('fundScore', 'fundDesc', apiData.scorecards.fundamental);
      updateMetricRow('techScore', 'techDesc', apiData.scorecards.technical);
      updateMetricRow('sentScore', 'sentDesc', apiData.scorecards.sentiment);
      updateMetricRow('riskScore', 'riskDesc', apiData.scorecards.risk);
    }

    // Update Snippets
    if (apiData.snippets) {
      const snipValEl = document.getElementById('snipValuationVal');
      const snipValDesc = document.getElementById('snipValuationDesc');
      const snipProfEl = document.getElementById('snipProfitVal');
      const snipProfDesc = document.getElementById('snipProfitDesc');
      const snipDebtEl = document.getElementById('snipDebtVal');
      const snipDebtDesc = document.getElementById('snipDebtDesc');
      const snipGrowEl = document.getElementById('snipGrowthVal');
      const snipGrowDesc = document.getElementById('snipGrowthDesc');

      if (snipValEl && apiData.snippets.valuation) {
        snipValEl.textContent = apiData.snippets.valuation.val;
        snipValDesc.textContent = apiData.snippets.valuation.desc;
      }
      if (snipProfEl && apiData.snippets.profit) {
        snipProfEl.textContent = apiData.snippets.profit.val;
        snipProfDesc.textContent = apiData.snippets.profit.desc;
      }
      if (snipDebtEl && apiData.snippets.debt) {
        snipDebtEl.textContent = apiData.snippets.debt.val;
        snipDebtDesc.textContent = apiData.snippets.debt.desc;
      }
      if (snipGrowEl && apiData.snippets.growth) {
        snipGrowEl.textContent = apiData.snippets.growth.val;
        snipGrowDesc.textContent = apiData.snippets.growth.desc;
      }
    }

    // Update Deep-Links & Navbar Links to DCF Model and Ratios
    const activeTicker = apiData.symbol || query;
    try {
      localStorage.setItem('finresearch_active_ticker', activeTicker);
    } catch (_) {}

    // Update all /ratios links on the page (navbar + buttons)
    document.querySelectorAll('a[href^="/ratios"]').forEach(a => {
      a.href = `/ratios?symbol=${encodeURIComponent(activeTicker)}`;
    });

    // Update all /dcf links on the page (navbar + buttons)
    document.querySelectorAll('a[href^="/dcf"]').forEach(a => {
      a.href = `/dcf?symbol=${encodeURIComponent(activeTicker)}`;
    });

    // Keep URL parameter synchronized without full page reload
    if (window.history && window.history.replaceState) {
      const u = new URL(window.location);
      u.searchParams.set('symbol', activeTicker);
      window.history.replaceState({}, '', u);
    }

    // Update Chart with live chart_data
    const chartPrices = (apiData.chart_data && apiData.chart_data.prices && apiData.chart_data.prices.length > 0)
      ? apiData.chart_data.prices
      : (apiData.history && apiData.history.length > 0 ? apiData.history : []);
    const chartLabels = (apiData.chart_data && apiData.chart_data.labels && apiData.chart_data.labels.length > 0)
      ? apiData.chart_data.labels
      : ['10d', '9d', '8d', '7d', '6d', '5d', '4d', '3d', '2d', 'Live'];

    if (chartPrices.length > 0) {
      renderLiveStockChart({
        symbol: apiData.symbol || query,
        currency: currSym,
        recType: recType,
        labels: chartLabels,
        prices: chartPrices
      });
    }

    // Update Quick Ticker active state
    document.querySelectorAll('.ticker-btn').forEach(btn => {
      const btnTick = (btn.dataset.ticker || '').toUpperCase();
      const sym = (apiData.symbol || query).toUpperCase();
      btn.classList.toggle('active', sym.startsWith(btnTick) || btnTick === sym);
    });

  } catch (err) {
    console.error('Error fetching stock quote:', err);
    if (errBanner && errText) {
      errText.textContent = `Unable to connect to market service. Please verify ticker '${query}'.`;
      errBanner.style.display = 'flex';
    }
  } finally {
    if (loadingBanner) loadingBanner.style.display = 'none';
    if (searchBtn) {
      searchBtn.disabled = false;
      searchBtn.removeAttribute('aria-busy');
    }
    document.querySelector('.studio')?.classList.remove('is-loading');
  }
}

// API examples — real endpoints and request fields (see /docs for the full schema)
const CODE_SNIPPETS = {
  curl: `curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE.NS", "analysis_type": "comprehensive"}'

curl "http://localhost:8000/api/v1/dcf/AAPL"
curl "http://localhost:8000/api/v1/ratios/TCS"`,

  python: `import requests

BASE = "http://localhost:8000/api/v1"

analysis = requests.post(f"{BASE}/analyze", json={"symbol": "RELIANCE.NS"}).json()
print(analysis["recommendation"], analysis["risk"]["var_95_daily_pct"])

dcf = requests.get(f"{BASE}/dcf/AAPL").json()
print(dcf["fair_value_per_share"], dcf["scenarios"]["bear"])`,

  javascript: `const BASE = "http://localhost:8000/api/v1";

const ratios = await fetch(\`\${BASE}/ratios/TCS\`).then((r) => r.json());
console.log(ratios.pe, ratios.roce, ratios.dataConfidence);

const dcf = await fetch(\`\${BASE}/dcf/AAPL\`).then((r) => r.json());
console.log(dcf.fair_value_per_share, dcf.upside_pct);`
};

function initCodePlayground() {
  const tabs = document.querySelectorAll('.code-tab-btn');
  const codeDisplay = document.getElementById('codeDisplay');
  const copyBtn = document.getElementById('copyCodeBtn');
  if (codeDisplay) codeDisplay.textContent = CODE_SNIPPETS.curl;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      const lang = tab.dataset.lang;
      if (codeDisplay && CODE_SNIPPETS[lang]) codeDisplay.textContent = CODE_SNIPPETS[lang];
    });
  });

  if (copyBtn && codeDisplay) {
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(codeDisplay.textContent).then(() => showToast('Copied to clipboard'));
    });
  }
}

function showToast(message) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
  const text = document.createElement('span');
  text.textContent = message;
  toast.appendChild(text);
  container.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 200);
  }, 2600);
}

function initFAQ() {
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    question.addEventListener('click', () => {
      const wasOpen = item.classList.contains('active');
      faqItems.forEach(i => {
        i.classList.remove('active');
        i.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
      });
      if (!wasOpen) {
        item.classList.add('active');
        question.setAttribute('aria-expanded', 'true');
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const tickerInput = document.getElementById('studioTickerInput');

  document.querySelectorAll('.ticker-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const ticker = btn.dataset.ticker;
      if (tickerInput) tickerInput.value = ticker;
      updateStockStudio(ticker);
    });
  });

  if (tickerInput) {
    tickerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const val = tickerInput.value.trim();
        if (val) updateStockStudio(val);
      }
    });
  }

  const searchBtn = document.getElementById('studioSearchBtn');
  if (searchBtn && tickerInput) {
    searchBtn.addEventListener('click', () => {
      const val = tickerInput.value.trim();
      if (val) updateStockStudio(val);
    });
  }

  let startupTicker = 'RELIANCE';
  try {
    const urlParams = new URLSearchParams(window.location.search);
    startupTicker = urlParams.get('symbol') || localStorage.getItem('finresearch_active_ticker') || 'RELIANCE';
  } catch (_) {}

  if (tickerInput) tickerInput.value = startupTicker;
  updateStockStudio(startupTicker);

  initCodePlayground();
  initFAQ();
});
