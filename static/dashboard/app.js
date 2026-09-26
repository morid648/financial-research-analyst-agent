/**
 * Dashboard — live technicals, risk, valuation and news for one ticker.
 * Theme is handled by /static/js/theme.js; colours are read from CSS tokens at draw time.
 */

(function () {
  "use strict";

  const state = {
    currentSymbol: "AAPL",
    currentRange: "3M",
    isAnalyzing: false,
    chartData: [],
  };

  const elements = {
    commandModal: document.getElementById("command-palette-modal"),
    commandInput: document.getElementById("command-input"),
    commandResults: document.getElementById("command-results"),
    tickerInput: document.getElementById("ticker-search-input"),
    searchSubmitBtn: document.getElementById("search-submit-btn"),
    toastContainer: document.getElementById("toast-container"),
    canvas: document.getElementById("main-price-chart"),
    chartEmpty: document.getElementById("chart-empty"),
    chartTitle: document.getElementById("chart-symbol-title"),
    valPrice: document.getElementById("val-price"),
    valPriceChange: document.getElementById("val-price-change"),
    valConsensus: document.getElementById("val-consensus"),
    valConsensusScore: document.getElementById("val-consensus-score"),
    valRsi: document.getElementById("val-rsi"),
    valRsiSignal: document.getElementById("val-rsi-signal"),
    valPe: document.getElementById("val-pe"),
    valPeSignal: document.getElementById("val-pe-signal"),
    valVar: document.getElementById("val-var"),
    valRiskTier: document.getElementById("val-risk-tier"),
    consensusVerdict: document.getElementById("consensus-verdict-display"),
    consensusProgressBar: document.getElementById("consensus-progress-bar"),
    dcfTargetVal: document.getElementById("dcf-target-val"),
    sharpeRatioVal: document.getElementById("sharpe-ratio-val"),
    newsSentimentVal: document.getElementById("news-sentiment-val"),
    agentReasoningFeed: document.getElementById("agent-reasoning-feed"),
    executionTimeLabel: document.getElementById("execution-time-label"),
  };

  function init() {
    bindEvents();
    initCanvasChart();
    const params = new URLSearchParams(window.location.search);
    let startSymbol = params.get("symbol");
    if (!startSymbol) {
      try { startSymbol = localStorage.getItem("finresearch_active_ticker"); } catch (_) {}
    }
    startSymbol = (startSymbol || "AAPL").toUpperCase();
    if (elements.tickerInput) elements.tickerInput.value = startSymbol;
    runAnalysis(startSymbol);
  }

  function submitSymbol(raw) {
    const symbol = (raw || "").trim().toUpperCase();
    if (!symbol) return;
    if (elements.tickerInput) elements.tickerInput.value = symbol;
    runAnalysis(symbol);
  }

  function bindEvents() {
    const kbd = document.getElementById("kbd-hint");
    if (kbd && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) kbd.textContent = "⌘K";

    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openCommandPalette();
      } else if (e.key === "Escape") {
        closeCommandPalette();
      }
    });

    if (elements.commandModal) {
      elements.commandModal.addEventListener("click", (e) => {
        if (e.target === elements.commandModal) closeCommandPalette();
      });
    }
    if (elements.commandInput) {
      elements.commandInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          closeCommandPalette();
          submitSymbol(elements.commandInput.value);
        }
      });
    }
    document.querySelectorAll(".command-item").forEach((item) => {
      item.addEventListener("click", () => {
        closeCommandPalette();
        submitSymbol(item.dataset.ticker);
      });
    });

    if (elements.searchSubmitBtn) {
      elements.searchSubmitBtn.addEventListener("click", () => submitSymbol(elements.tickerInput.value));
    }
    if (elements.tickerInput) {
      elements.tickerInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") submitSymbol(elements.tickerInput.value);
      });
    }

    document.querySelectorAll(".chip-btn").forEach((chip) => {
      chip.addEventListener("click", () => submitSymbol(chip.dataset.ticker));
    });

    document.querySelectorAll(".timeframe-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".timeframe-btn").forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        const range = btn.dataset.range || "3M";
        state.currentRange = range;
        fetchHistory(state.currentSymbol, periodFor(range)).then((points) => {
          state.chartData = points;
          drawChart();
        });
      });
    });

    document.querySelectorAll(".reasoning-step-header").forEach((btn) => {
      btn.addEventListener("click", () => {
        const item = btn.closest(".reasoning-step-item");
        const open = item.classList.toggle("active");
        btn.setAttribute("aria-expanded", String(open));
      });
    });

    window.addEventListener("themechange", drawChart);
  }

  function periodFor(range) {
    return range === "1M" ? "1mo" : range === "3M" ? "3mo" : range === "6M" ? "6mo" : range === "1Y" ? "1y" : "5y";
  }

  let lastFocus = null;
  function openCommandPalette() {
    if (!elements.commandModal) return;
    lastFocus = document.activeElement;
    elements.commandModal.classList.add("open");
    if (elements.commandInput) {
      elements.commandInput.value = "";
      elements.commandInput.focus();
    }
  }

  function closeCommandPalette() {
    if (!elements.commandModal || !elements.commandModal.classList.contains("open")) return;
    elements.commandModal.classList.remove("open");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function showToast(message) {
    if (!elements.toastContainer) return;
    const toast = document.createElement("div");
    toast.className = "toast-item";
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 200);
    }, 2400);
  }

  // Run Analysis Logic — fetches real data from /analyze (technical/risk/sentiment),
  // /quote (price + P/E), /dcf (fair value target) and /history (chart) in parallel.
  // Every field is either a real computed number or an explicit "N/A" — never a
  // randomly-generated placeholder (see docs/ROOT_CAUSE_ANALYSIS.md, finding #6).
  async function runAnalysis(symbol) {
    if (state.isAnalyzing) return;
    state.isAnalyzing = true;
    state.currentSymbol = symbol;

    if (elements.searchSubmitBtn) { elements.searchSubmitBtn.disabled = true; elements.searchSubmitBtn.setAttribute("aria-busy", "true"); }
    document.body.classList.add("is-loading");

    const period = state.currentRange === "1M" ? "1mo" : state.currentRange === "3M" ? "3mo" : state.currentRange === "6M" ? "6mo" : state.currentRange === "1Y" ? "1y" : "5y";

    try {
      const [analyzeRes, quoteRes, dcfRes, historyPoints] = await Promise.all([
        fetch(`/api/v1/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol }),
        }).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`/api/v1/quote/${encodeURIComponent(symbol)}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`/api/v1/dcf/${encodeURIComponent(symbol)}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetchHistory(symbol, period),
      ]);

      if (!analyzeRes && !quoteRes) {
        showToast(`Unable to identify company or ticker '${symbol}'. Please use a specific ticker symbol (e.g., AAPL, NVDA, RELIANCE.NS, TCS.NS).`);
        renderUnavailable(symbol);
        return;
      }

      renderRealData(symbol, { analyze: analyzeRes, quote: quoteRes, dcf: dcfRes, history: historyPoints });
      const resolved = (quoteRes && quoteRes.symbol) || symbol;
      try { localStorage.setItem("finresearch_active_ticker", resolved); } catch (_) {}
      const u = new URL(window.location);
      u.searchParams.set("symbol", resolved);
      window.history.replaceState({}, "", u);
    } catch (e) {
      console.error("Analysis error:", e);
      renderUnavailable(symbol);
    } finally {
      state.isAnalyzing = false;
      if (elements.searchSubmitBtn) { elements.searchSubmitBtn.disabled = false; elements.searchSubmitBtn.removeAttribute("aria-busy"); }
      document.body.classList.remove("is-loading");
    }
  }

  async function fetchHistory(symbol, period) {
    try {
      const res = await fetch(`/api/v1/history/${encodeURIComponent(symbol)}?period=${encodeURIComponent(period)}`);
      if (!res.ok) return [];
      const data = await res.json();
      if (!data || !Array.isArray(data.dates) || !Array.isArray(data.closes)) return [];
      return data.dates.map((d, i) => ({
        date: new Date(d),
        price: data.closes[i],
        volume: (data.volumes && data.volumes[i]) || 0,
      })).filter((p) => typeof p.price === "number" && !isNaN(p.price));
    } catch (e) {
      return [];
    }
  }

  function setBadge(el, text, cls) {
    if (!el) return;
    el.textContent = text;
    if (cls) el.className = el.className.replace(/\b(gain|loss|neutral)\b/g, "").trim() + ` ${cls}`;
  }

  function renderRealData(symbol, { analyze, quote, dcf, history }) {
    const displaySymbol = (analyze && analyze.symbol) || (quote && quote.symbol) || symbol;
    if (elements.chartTitle) elements.chartTitle.textContent = `${displaySymbol} · closing price`;

    const currSym = (quote && (quote.currency_symbol || quote.currency)) || "$";
    const price = (quote && typeof quote.raw_price === "number") ? quote.raw_price : (analyze ? analyze.current_price : null);
    const changePct = quote && typeof quote.change_pct === "number" ? quote.change_pct : null;

    if (elements.valPrice) elements.valPrice.textContent = (price !== null && price !== undefined) ? `${currSym}${price.toFixed(2)}` : "N/A";
    if (elements.valPriceChange) {
      if (changePct !== null) {
        const isUp = changePct >= 0;
        elements.valPriceChange.textContent = `${isUp ? "+" : ""}${changePct.toFixed(2)}%`;
        setBadge(elements.valPriceChange, elements.valPriceChange.textContent, isUp ? "gain" : "loss");
      } else {
        setBadge(elements.valPriceChange, "N/A", "neutral");
      }
    }

    // Agent consensus — from the real recommendation + confidence /analyze computes
    // (a rule-based heuristic on RSI/MACD, not literally a multi-agent vote — see
    // docs/ROOT_CAUSE_ANALYSIS.md recommendation #5 — but real inputs, not random).
    const rec = analyze ? analyze.recommendation : null;
    const confidence = analyze && typeof analyze.confidence === "number" ? analyze.confidence : null;
    const recClass = rec === "BUY" ? "gain" : rec === "SELL" ? "loss" : "neutral";
    if (elements.valConsensus) {
      elements.valConsensus.textContent = rec || "N/A";
      elements.valConsensus.style.color = rec === "BUY" ? "var(--gain)" : rec === "SELL" ? "var(--loss)" : "var(--text-2)";
    }
    setBadge(elements.valConsensusScore, confidence !== null ? `${confidence.toFixed(2)} / 1.0` : "N/A", recClass);
    if (elements.consensusVerdict) {
      elements.consensusVerdict.textContent = rec || "N/A";
      elements.consensusVerdict.className = `consensus-verdict ${rec === "BUY" ? "buy" : rec === "SELL" ? "sell" : "hold"}`;
    }
    if (elements.consensusProgressBar) elements.consensusProgressBar.style.width = confidence !== null ? `${Math.round(confidence * 100)}%` : "0%";

    // Technical RSI — real, computed from actual price history (src/tools/technical_indicators.py)
    const rsi = analyze && analyze.technical && analyze.technical.rsi;
    if (elements.valRsi) elements.valRsi.textContent = rsi && typeof rsi.value === "number" ? rsi.value.toFixed(1) : "N/A";
    if (elements.valRsiSignal) {
      const sig = rsi ? rsi.signal : null;
      setBadge(elements.valRsiSignal, sig ? sig.charAt(0) + sig.slice(1).toLowerCase() : "N/A", sig === "OVERSOLD" ? "gain" : sig === "OVERBOUGHT" ? "loss" : "neutral");
    }

    // Trailing P/E — real, from yfinance trailingPE
    const peRaw = quote && quote.pe;
    const peNum = peRaw && peRaw !== "N/A" ? parseFloat(peRaw) : null;
    if (elements.valPe) elements.valPe.textContent = peNum !== null && !isNaN(peNum) ? `${peNum.toFixed(1)}x` : "N/A";
    if (elements.valPeSignal) setBadge(elements.valPeSignal, peNum === null ? "N/A" : peNum < 25 ? "Attractive" : peNum < 40 ? "Fair Value" : "Premium", peNum === null ? "neutral" : peNum < 25 ? "gain" : peNum < 40 ? "neutral" : "loss");

    // Risk — real historical volatility / VaR(95%) / Sharpe (src/api/routes.py::_compute_risk_metrics)
    const risk = analyze ? analyze.risk : null;
    const varPct = risk && typeof risk.var_95_daily_pct === "number" ? risk.var_95_daily_pct : null;
    if (elements.valVar) {
      elements.valVar.textContent = varPct !== null ? `${varPct.toFixed(2)}%` : "N/A";
      elements.valVar.style.color = varPct !== null ? "var(--loss)" : "var(--text-2)";
    }
    if (elements.valRiskTier) {
      const tier = risk ? risk.volatility : null;
      setBadge(elements.valRiskTier, tier || "N/A", tier === "Low" ? "gain" : tier === "High" ? "loss" : "neutral");
    }
    if (elements.sharpeRatioVal) elements.sharpeRatioVal.textContent = risk && typeof risk.sharpe_ratio === "number" ? risk.sharpe_ratio.toFixed(2) : "N/A";

    // DCF target — real, from the fixed get_company_dcf_profile()
    if (elements.dcfTargetVal) {
      if (dcf && typeof dcf.fair_value_per_share === "number") {
        const upside = typeof dcf.upside_pct === "number" ? dcf.upside_pct : 0;
        elements.dcfTargetVal.textContent = `${dcf.currency || currSym}${dcf.fair_value_per_share.toFixed(2)} (${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%)`;
        elements.dcfTargetVal.style.color = upside >= 0 ? "var(--gain)" : "var(--loss)";
      } else {
        elements.dcfTargetVal.textContent = "N/A";
        elements.dcfTargetVal.style.color = "var(--text-2)";
      }
    }

    // News sentiment — real FinBERT/VADER score (src/tools/sentiment_engine.py), or
    // an honest "Unavailable" if the news pipeline couldn't run for this request.
    const sentiment = analyze ? analyze.sentiment : null;
    if (elements.newsSentimentVal) {
      if (sentiment && sentiment.status === "analyzed" && typeof sentiment.score === "number") {
        const s = sentiment.score;
        elements.newsSentimentVal.textContent = `${s >= 0 ? "+" : ""}${s.toFixed(2)} (${sentiment.label || "Neutral"})`;
        elements.newsSentimentVal.style.color = s > 0.1 ? "var(--gain)" : s < -0.1 ? "var(--loss)" : "var(--text-2)";
      } else {
        elements.newsSentimentVal.textContent = "Unavailable";
        elements.newsSentimentVal.style.color = "var(--text-2)";
      }
    }

    renderReasoningStream(displaySymbol, { analyze, dcf, sentiment, history });
    renderNewsFeed(sentiment);
    if (elements.executionTimeLabel) {
      elements.executionTimeLabel.textContent = (analyze && typeof analyze.execution_time_seconds === "number")
        ? `Completed in ${analyze.execution_time_seconds.toFixed(2)}s`
        : "Completed";
    }

    state.chartData = history || [];
    drawChart();
  }

  // Agent "execution stream" — previously static HTML with fabricated specifics
  // (a fake RSI, a fake DCF target) that silently contradicted the real numbers
  // shown in the metric pills above. Now built from the same real API responses.
  function renderReasoningStream(symbol, { analyze, dcf, sentiment, history }) {
    const el = (id) => document.getElementById(id);
    const setStep = (n, badgeText, badgeClass, contentText) => {
      const badge = el(`step${n}-badge`);
      const content = el(`step${n}-content`);
      if (badge) { badge.textContent = badgeText; badge.className = `delta-badge ${badgeClass}`; }
      if (content) content.textContent = contentText;
    };

    const days = (history && history.length) || 0;
    const articlesN = sentiment && sentiment.articles_analyzed ? sentiment.articles_analyzed : 0;
    setStep(1, "Success", "gain", `Fetched ${days} days of price history and ${articlesN} recent news article${articlesN === 1 ? "" : "s"} for ${symbol}.`);

    const tech = analyze && analyze.technical;
    const rsi = tech && tech.rsi;
    const macd = tech && tech.macd;
    const ma = tech && tech.moving_averages;
    if (rsi && rsi.value !== undefined) {
      const macdTxt = macd && macd.trend ? `MACD histogram is ${macd.trend} (${macd.crossover !== "none" ? macd.crossover + " crossover" : "no crossover"}).` : "MACD unavailable.";
      const smaTxt = (ma && ma.sma_50 && ma.sma_200 && ma.current_price)
        ? `Price is ${(((ma.current_price - ma.sma_50) / ma.sma_50) * 100).toFixed(1)}% vs SMA-50 and ${(((ma.current_price - ma.sma_200) / ma.sma_200) * 100).toFixed(1)}% vs SMA-200 (${ma.trend || "n/a"} trend).`
        : "";
      setStep(2, rsi.signal === "OVERBOUGHT" ? "Bearish" : rsi.signal === "OVERSOLD" ? "Bullish" : "Neutral", rsi.signal === "OVERSOLD" ? "gain" : rsi.signal === "OVERBOUGHT" ? "loss" : "neutral",
        `Calculated 14-period RSI at ${rsi.value.toFixed(1)} (${rsi.signal}). ${macdTxt} ${smaTxt}`);
    } else {
      setStep(2, "N/A", "neutral", "Insufficient price history for technical indicators.");
    }

    if (dcf && typeof dcf.fair_value_per_share === "number") {
      const upside = dcf.upside_pct || 0;
      setStep(3, upside >= 10 ? "Undervalued" : upside <= -10 ? "Overvalued" : "Fair Value", upside >= 10 ? "gain" : upside <= -10 ? "loss" : "neutral",
        `5-year DCF model (WACC ${dcf.wacc}%, terminal growth ${dcf.terminal_g}%) projects an intrinsic value of ${dcf.currency || "$"}${dcf.fair_value_per_share.toFixed(2)}, a ${upside >= 0 ? "+" : ""}${upside.toFixed(1)}% ${upside >= 0 ? "premium" : "discount"} to the current price.`);
    } else {
      setStep(3, "N/A", "neutral", "DCF valuation unavailable for this ticker.");
    }

    const risk = analyze && analyze.risk;
    if (risk && risk.status === "analyzed") {
      const dcfBeta = dcf && typeof dcf.beta === "number" ? ` Beta of ${dcf.beta.toFixed(2)} vs. the broader market.` : "";
      setStep(4, risk.volatility || "N/A", risk.volatility === "Low" ? "gain" : risk.volatility === "High" ? "loss" : "neutral",
        `Calculated annualized historical volatility at ${risk.annual_volatility_pct}%.${dcfBeta} Daily 95% historical Value at Risk (VaR) at ${risk.var_95_daily_pct}%.`);
    } else {
      setStep(4, "N/A", "neutral", "Insufficient return history for a risk calculation.");
    }
  }

  // Real headlines with per-article FinBERT/VADER scores (src/tools/news_impact.py).
  function renderNewsFeed(sentiment) {
    const container = document.getElementById("news-stream-container");
    if (!container) return;
    container.textContent = "";

    const articles = sentiment && Array.isArray(sentiment.top_articles) ? sentiment.top_articles : [];
    if (articles.length === 0) {
      const p = document.createElement("p");
      p.className = "subtle";
      p.textContent = "No recent news sentiment for this ticker.";
      container.appendChild(p);
      return;
    }

    articles.forEach((a) => {
      const score = Number(a.score) || 0;
      const item = document.createElement("div");
      item.className = "news-item";

      const meta = document.createElement("div");
      meta.className = "news-meta";
      const src = document.createElement("span");
      const when = a.published_at ? new Date(a.published_at).toLocaleDateString() : "";
      src.textContent = [a.source || "Unknown source", when].filter(Boolean).join(" · ");
      const badge = document.createElement("span");
      badge.className = "delta-badge " + (score > 0.1 ? "gain" : score < -0.1 ? "loss" : "neutral");
      badge.textContent = `${score >= 0 ? "+" : "−"}${Math.abs(score).toFixed(2)} ${a.label || "Neutral"}`;
      meta.append(src, badge);

      const title = document.createElement("div");
      title.className = "news-title";
      title.textContent = a.title || "";

      item.append(meta, title);
      container.appendChild(item);
    });
  }

  // True failure state — no fabricated numbers, every field shown as N/A.
  function renderUnavailable(symbol) {
    if (elements.chartTitle) elements.chartTitle.textContent = `${symbol} · data unavailable`;
    [elements.valPrice, elements.valRsi, elements.valPe, elements.valVar, elements.sharpeRatioVal].forEach((el) => {
      if (el) el.textContent = "N/A";
    });
    setBadge(elements.valPriceChange, "N/A", "neutral");
    setBadge(elements.valConsensusScore, "N/A", "neutral");
    setBadge(elements.valRsiSignal, "N/A", "neutral");
    setBadge(elements.valPeSignal, "N/A", "neutral");
    setBadge(elements.valRiskTier, "N/A", "neutral");
    if (elements.valConsensus) { elements.valConsensus.textContent = "N/A"; elements.valConsensus.style.color = "var(--text-2)"; }
    if (elements.consensusVerdict) { elements.consensusVerdict.textContent = "N/A"; elements.consensusVerdict.className = "consensus-verdict hold"; }
    if (elements.consensusProgressBar) elements.consensusProgressBar.style.width = "0%";
    if (elements.dcfTargetVal) { elements.dcfTargetVal.textContent = "N/A"; elements.dcfTargetVal.style.color = "var(--text-2)"; }
    if (elements.newsSentimentVal) { elements.newsSentimentVal.textContent = "Unavailable"; elements.newsSentimentVal.style.color = "var(--text-2)"; }
    ["1", "2", "3", "4"].forEach((n) => {
      const badge = document.getElementById(`step${n}-badge`);
      const content = document.getElementById(`step${n}-content`);
      if (badge) { badge.textContent = "N/A"; badge.className = "delta-badge neutral"; }
      if (content) content.textContent = "Unable to fetch data for this ticker.";
    });
    renderNewsFeed(null);
    state.chartData = [];
    drawChart();
  }

  // Canvas line chart with a right-hand price scale and first/last date labels.
  function initCanvasChart() {
    if (!elements.canvas) return;
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(drawChart, 100);
    });
    drawChart();
  }

  function drawChart() {
    const canvas = elements.canvas;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const w = rect.width;
    const h = rect.height;
    ctx.clearRect(0, 0, w, h);

    const data = state.chartData;
    const hasData = data && data.length >= 2;
    if (elements.chartEmpty) elements.chartEmpty.hidden = hasData;
    if (!hasData) return;

    const css = window.cssVar || (() => "");
    const lineColor = css("--text") || "#ecebe8";
    const gridColor = css("--border") || "#2a2c31";
    const labelColor = css("--text-3") || "#8f8d88";
    const monoFont = "11px 'IBM Plex Mono', ui-monospace, monospace";

    const axisW = 64;
    const axisH = 22;
    const topPad = 8;
    const plotW = w - axisW;
    const plotH = h - axisH - topPad;

    const prices = data.map((d) => d.price);
    let minP = Math.min(...prices);
    let maxP = Math.max(...prices);
    const pad = (maxP - minP) * 0.08 || maxP * 0.01 || 1;
    minP -= pad;
    maxP += pad;
    const range = maxP - minP;
    const yFor = (p) => topPad + plotH - ((p - minP) / range) * plotH;

    // Horizontal gridlines + price labels
    ctx.font = monoFont;
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    ctx.lineWidth = 1;
    const steps = 4;
    for (let i = 0; i <= steps; i++) {
      const p = minP + (range / steps) * i;
      const y = Math.round(yFor(p)) + 0.5;
      ctx.strokeStyle = gridColor;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(plotW, y);
      ctx.stroke();
      ctx.fillStyle = labelColor;
      ctx.fillText(p.toLocaleString("en-US", { maximumFractionDigits: p < 100 ? 2 : 0 }), plotW + 8, y);
    }

    // Price line — monotone cubic (Fritsch–Carlson): smooth, but never overshoots a real close
    const pts = data.map((d, i) => ({ x: (plotW / (data.length - 1)) * i, y: yFor(d.price) }));
    const n = pts.length;
    const slopes = [];
    for (let i = 0; i < n - 1; i++) slopes.push((pts[i + 1].y - pts[i].y) / (pts[i + 1].x - pts[i].x));
    const tangents = [slopes[0]];
    for (let i = 1; i < n - 1; i++) tangents.push(slopes[i - 1] * slopes[i] <= 0 ? 0 : (slopes[i - 1] + slopes[i]) / 2);
    tangents.push(slopes[n - 2]);
    for (let i = 0; i < n - 1; i++) {
      if (slopes[i] === 0) { tangents[i] = 0; tangents[i + 1] = 0; continue; }
      const a = tangents[i] / slopes[i];
      const b = tangents[i + 1] / slopes[i];
      const h = a * a + b * b;
      if (h > 9) {
        const t = 3 / Math.sqrt(h);
        tangents[i] = t * a * slopes[i];
        tangents[i + 1] = t * b * slopes[i];
      }
    }
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 0; i < n - 1; i++) {
      const dx = (pts[i + 1].x - pts[i].x) / 3;
      ctx.bezierCurveTo(
        pts[i].x + dx, pts[i].y + tangents[i] * dx,
        pts[i + 1].x - dx, pts[i + 1].y - tangents[i + 1] * dx,
        pts[i + 1].x, pts[i + 1].y
      );
    }
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 1.75;
    ctx.lineJoin = "round";
    ctx.stroke();

    // First / last date labels
    const fmtDate = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "2-digit" });
    ctx.fillStyle = labelColor;
    ctx.textBaseline = "bottom";
    ctx.textAlign = "left";
    ctx.fillText(fmtDate(data[0].date), 0, h);
    ctx.textAlign = "right";
    ctx.fillText(fmtDate(data[data.length - 1].date), plotW, h);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
