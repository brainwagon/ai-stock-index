/* Frontend controller for AI & Adjacent Markets Index Dashboard. */

(function () {
  "use strict";

  const RANGE_TO_FIELD = {
    "1D": "ret_1d",
    "1W": "ret_1w",
    "1M": "ret_1m",
    "3M": "ret_3m",
    "YTD": "ret_ytd",
    "1Y": "ret_1y",
  };

  const state = {
    range: "YTD",
    sectorWeight: "equal",
    sectorFilter: "all",
    search: "",
    unusualOnly: false,
    sortBy: "ret_1d",
    sortDir: "desc",
    hiddenSeries: new Set(["bench_spy", "bench_qqq", "bench_smh"]),
    autoRefresh: true,
    countdown: 60,
    staticMode: false,
    tickerCache: new Map(),
    data: null,
    detailSymbol: null,
    detailRange: "3M",
  };

  const el = {
    timestamp: document.getElementById("market-timestamp"),
    errorBanner: document.getElementById("error-banner"),
    rangeSelector: document.getElementById("range-selector"),
    autoRefreshBtn: document.getElementById("auto-refresh-btn"),
    autoRefreshState: document.getElementById("auto-refresh-state"),
    refreshBtn: document.getElementById("refresh-btn"),
    kpiEq1d: document.getElementById("kpi-eq-1d"),
    kpiEqSub: document.getElementById("kpi-eq-sub"),
    kpiCap1d: document.getElementById("kpi-cap-1d"),
    kpiCapSub: document.getElementById("kpi-cap-sub"),
    kpiBreadthMain: document.getElementById("kpi-breadth-main"),
    kpiBreadthSub: document.getElementById("kpi-breadth-sub"),
    kpiBenchmarks: document.getElementById("kpi-benchmarks"),
    regimeSection: document.getElementById("regime-section"),
    regimeHeadline: document.getElementById("regime-headline"),
    regimeSummary: document.getElementById("regime-summary"),
    frothLabel: document.getElementById("froth-label"),
    frothBar: document.getElementById("froth-bar"),
    unwindLabel: document.getElementById("unwind-label"),
    unwindBar: document.getElementById("unwind-bar"),
    frothSignals: document.getElementById("froth-signals"),
    unwindSignals: document.getElementById("unwind-signals"),
    regimeCaveat: document.getElementById("regime-caveat"),
    mainChartTitle: document.getElementById("main-chart-title"),
    mainChartSubtitle: document.getElementById("main-chart-subtitle"),
    chartLegend: document.getElementById("chart-legend"),
    mainChart: document.getElementById("main-chart"),
    mainTooltip: document.getElementById("main-tooltip"),
    unusualList: document.getElementById("unusual-list"),
    sectorWeightToggle: document.getElementById("sector-weight-toggle"),
    sectorGrid: document.getElementById("sector-grid"),
    corrWindowLabel: document.getElementById("corr-window-label"),
    corrMatrix: document.getElementById("corr-matrix"),
    barChartTitle: document.getElementById("bar-chart-title"),
    sectorBars: document.getElementById("sector-bars"),
    searchInput: document.getElementById("search-input"),
    unusualOnlyToggle: document.getElementById("unusual-only-toggle"),
    sectorFilterPills: document.getElementById("sector-filter-pills"),
    watchlistTbody: document.getElementById("watchlist-tbody"),
    detailModal: document.getElementById("detail-modal"),
    detailTitle: document.getElementById("detail-title"),
    detailSubtitle: document.getElementById("detail-subtitle"),
    detailRangeSelector: document.getElementById("detail-range-selector"),
    detailStats: document.getElementById("detail-stats"),
    detailChart: document.getElementById("detail-chart"),
    detailTooltip: document.getElementById("detail-tooltip"),
    closeDetailBtn: document.getElementById("close-detail-btn"),
    addModal: document.getElementById("add-modal"),
    openAddModalBtn: document.getElementById("open-add-modal-btn"),
    closeAddBtn: document.getElementById("close-add-btn"),
    addTickerForm: document.getElementById("add-ticker-form"),
    newSymbolInput: document.getElementById("new-symbol-input"),
    newSectorSelect: document.getElementById("new-sector-select"),
    addFormError: document.getElementById("add-form-error"),
    resetWatchlistBtn: document.getElementById("reset-watchlist-btn"),
  };

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtPct(val, showSign = true) {
    if (val === null || val === undefined || !Number.isFinite(val)) {
      return '<span class="muted-val">--</span>';
    }
    const cls = val >= 0 ? "pos" : "neg";
    const sign = showSign && val > 0 ? "+" : "";
    return `<span class="${cls}">${sign}${val.toFixed(2)}%</span>`;
  }

  function fmtPctText(val) {
    if (val === null || val === undefined || !Number.isFinite(val)) return "--";
    const sign = val > 0 ? "+" : "";
    return `${sign}${val.toFixed(2)}%`;
  }

  function fmtPrice(val, symbol = "") {
    if (val === null || val === undefined || !Number.isFinite(val)) return "--";
    const formatted = Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return String(symbol).startsWith("^") ? formatted : `$${formatted}`;
  }

  function fmtCap(val) {
    if (val === null || val === undefined || !Number.isFinite(val) || val <= 0) return "--";
    if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
    if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`;
    if (val >= 1e6) return `$${(val / 1e6).toFixed(0)}M`;
    return `$${val.toFixed(0)}`;
  }

  function showError(msg) {
    if (!msg) {
      el.errorBanner.classList.add("hidden");
      el.errorBanner.textContent = "";
    } else {
      el.errorBanner.textContent = msg;
      el.errorBanner.classList.remove("hidden");
    }
  }

  function safeSymbolFilename(symbol) {
    const clean = String(symbol || "").trim().toUpperCase();
    if (clean.startsWith("^")) {
      return `IDX_${clean.slice(1)}`;
    }
    return clean.replace(/\//g, "_");
  }

  async function detectBackendMode() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "static") {
      applyStaticModeUI(true);
      return;
    }
    try {
      const res = await fetch("api/health", { cache: "no-store" });
      if (res.ok) {
        const body = await res.json();
        if (body && body.status === "ok") {
          applyStaticModeUI(false);
          return;
        }
      }
    } catch (_) {
      // Fall through to static snapshot mode
    }
    applyStaticModeUI(true);
  }

  function applyStaticModeUI(isStatic) {
    state.staticMode = isStatic;
    if (isStatic) {
      state.autoRefresh = false;
      el.autoRefreshBtn.classList.add("hidden");
      el.openAddModalBtn.classList.add("hidden");
    } else {
      el.autoRefreshBtn.classList.remove("hidden");
      el.openAddModalBtn.classList.remove("hidden");
    }
  }

  async function loadOverview(force = false) {
    const apiRange = state.range === "1D" ? "YTD" : state.range;
    try {
      el.refreshBtn.disabled = true;
      el.refreshBtn.textContent = "Loading...";
      const url = state.staticMode
        ? `data/overview-${encodeURIComponent(apiRange)}.json`
        : `/api/market/overview?range=${encodeURIComponent(apiRange)}&refresh=${force ? "true" : "false"}`;
      const res = await fetch(url, state.staticMode ? { cache: "no-store" } : undefined);
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      state.data = await res.json();
      if (state.staticMode && force) {
        state.tickerCache.clear();
      }
      showError(null);
      renderAll();
    } catch (err) {
      showError(`Failed to load market data: ${err.message}`);
    } finally {
      el.refreshBtn.disabled = false;
      el.refreshBtn.textContent = "Refresh";
    }
  }

  function renderAll() {
    if (!state.data) return;
    renderHeaderTimestamp();
    renderKpis();
    renderRegimeMonitor();
    renderPrimaryChart();
    renderUnusualMoves();
    renderSectorCards();
    renderCorrelationMatrix();
    renderSectorBars();
    renderSectorFilterPills();
    renderWatchlistTable();
  }

  function scoreColor(score) {
    if (score >= 75) return "#f43f5e";
    if (score >= 50) return "#f59e0b";
    if (score >= 25) return "#38bdf8";
    return "#10b981";
  }

  function renderSignalList(signals) {
    if (!Array.isArray(signals) || !signals.length) {
      return '<div class="empty-state">No signals available</div>';
    }
    return signals
      .map((sig) => {
        const status = sig.status || "normal";
        let badgeCls = "badge-pos";
        let statusText = "Normal";
        if (status === "watch") {
          badgeCls = "badge-warn";
          statusText = "Watch";
        } else if (status === "alert") {
          badgeCls = "badge-neg";
          statusText = "Alert";
        }
        const tipHtml =
          sig.description || sig.significance
            ? `<span class="tip-wrap">
                <button type="button" class="tip-btn" aria-label="Explain ${escapeHtml(sig.label)}">?</button>
                <span class="tip-popover">
                  <strong>${escapeHtml(sig.label)}</strong>
                  <span>${escapeHtml(sig.description || "")}</span>
                  ${sig.significance ? `<span class="tip-sig"><strong>Significance:</strong> ${escapeHtml(sig.significance)}</span>` : ""}
                </span>
              </span>`
            : "";
        return `<div class="signal-row">
          <div>
            <span class="signal-name">${escapeHtml(sig.label)}${tipHtml}</span>
            ${sig.description ? `<span class="signal-desc">${escapeHtml(sig.description)}</span>` : ""}
            <span class="signal-thresh">${escapeHtml(sig.threshold)}</span>
          </div>
          <div class="signal-val">${escapeHtml(sig.value_text)}</div>
          <span class="badge ${badgeCls}">${statusText}</span>
        </div>`;
      })
      .join("");
  }

  function renderRegimeMonitor() {
    const reg = state.data.regime;
    if (!reg) {
      el.regimeSection.classList.add("hidden");
      return;
    }
    el.regimeSection.classList.remove("hidden");
    el.regimeHeadline.textContent = reg.summary_headline || "";
    el.regimeSummary.textContent = reg.summary_note || "";
    el.regimeCaveat.textContent = reg.caveat || "";

    const fScore = reg.froth_score ?? 0;
    const fColor = scoreColor(fScore);
    el.frothLabel.textContent = `${reg.froth_label} (${fScore}/100)`;
    el.frothLabel.style.color = fColor;
    el.frothBar.style.width = `${Math.max(4, fScore)}%`;
    el.frothBar.style.background = fColor;

    const uScore = reg.unwind_score ?? 0;
    const uColor = scoreColor(uScore);
    el.unwindLabel.textContent = `${reg.unwind_label} (${uScore}/100)`;
    el.unwindLabel.style.color = uColor;
    el.unwindBar.style.width = `${Math.max(4, uScore)}%`;
    el.unwindBar.style.background = uColor;

    el.frothSignals.innerHTML = renderSignalList(reg.froth_signals);
    el.unwindSignals.innerHTML = renderSignalList(reg.unwind_signals);
  }

  function renderHeaderTimestamp() {
    const ts = state.data.market_timestamp || "Latest daily close";
    const count = state.data.composite?.constituent_count || 0;
    const modeTag = state.staticMode ? " · Static snapshot" : " · Live API";
    el.timestamp.textContent = `Last market bar: ${ts} · ${count} AI & adjacent equities${modeTag}`;
  }

  function renderKpis() {
    const comp = state.data.composite;
    const field = RANGE_TO_FIELD[state.range] || "ret_ytd";
    const rangeLabel = state.range;

    const eq1d = comp.equal?.ret_1d;
    const eqRange = comp.equal?.[field];
    const spxBench = comp.benchmarks?.["^GSPC"] || comp.benchmarks?.SPY;
    const spxLabel = comp.benchmarks?.["^GSPC"] ? "S&P 500" : "SPY";
    const spxRange = spxBench?.[field];
    const alphaSpx =
      eqRange !== null && eqRange !== undefined && spxRange !== null && spxRange !== undefined
        ? eqRange - spxRange
        : null;

    el.kpiEq1d.innerHTML = fmtPct(eq1d);
    el.kpiEqSub.innerHTML =
      `${rangeLabel}: ${fmtPct(eqRange)}` +
      (alphaSpx !== null ? ` · vs ${spxLabel}: ${fmtPct(alphaSpx)}` : "");

    const cap1d = comp.cap?.ret_1d;
    const capRange = comp.cap?.[field];
    const ndxBench = comp.benchmarks?.["^NDX"] || comp.benchmarks?.QQQ;
    const ndxLabel = comp.benchmarks?.["^NDX"] ? "NDX" : "QQQ";
    const ndxRange = ndxBench?.[field];
    const alphaNdx =
      capRange !== null && capRange !== undefined && ndxRange !== null && ndxRange !== undefined
        ? capRange - ndxRange
        : null;

    el.kpiCap1d.innerHTML = fmtPct(cap1d);
    el.kpiCapSub.innerHTML =
      `${rangeLabel}: ${fmtPct(capRange)}` +
      (alphaNdx !== null ? ` · vs ${ndxLabel}: ${fmtPct(alphaNdx)}` : "");

    const stocks = (state.data.tickers || []).filter((t) => !t.is_benchmark && t.ret_1d !== null);
    const sorted = [...stocks].sort((a, b) => b.ret_1d - a.ret_1d);
    const leader = sorted[0];
    const laggard = sorted[sorted.length - 1];
    el.kpiBreadthMain.textContent = `${comp.up_count} / ${comp.constituent_count} Up (${comp.breadth_pct ?? "--"}%)`;
    el.kpiBreadthSub.innerHTML =
      leader && laggard
        ? `Top: <strong>${escapeHtml(leader.symbol)}</strong> ${fmtPct(leader.ret_1d)} · Lag: <strong>${escapeHtml(laggard.symbol)}</strong> ${fmtPct(laggard.ret_1d)}`
        : "No intraday movers yet";

    const benchMeta = [
      { sym: "^GSPC", label: "S&P 500" },
      { sym: "^NDX", label: "NDX 100" },
      { sym: "SMH", label: "SMH" },
    ];
    const benchRows = benchMeta
      .map(({ sym, label }) => {
        const b = comp.benchmarks?.[sym];
        if (!b) return "";
        return `<div class="bench-row">
          <span><strong>${label}</strong> ${fmtPrice(b.price, sym)}</span>
          <span>1D ${fmtPct(b.ret_1d)} · ${rangeLabel} ${fmtPct(b[field])}</span>
        </div>`;
      })
      .join("");
    el.kpiBenchmarks.innerHTML = benchRows || '<span class="muted-val">Unavailable</span>';
  }

  function renderPrimaryChart() {
    const isIntraday = state.range === "1D";
    const chartData = isIntraday ? state.data.intraday_chart : state.data.chart;
    const labels = isIntraday ? chartData?.timestamps || [] : chartData?.dates || [];
    const series = chartData?.series || [];

    el.mainChartTitle.textContent = isIntraday
      ? "Intraday Performance (5m Bars)"
      : `Cumulative Performance (${state.range})`;
    el.mainChartSubtitle.textContent = isIntraday
      ? "Percentage change vs prior session close"
      : "Daily-rebalanced composite & sector indices vs benchmarks";

    el.chartLegend.innerHTML = series
      .map((s) => {
        const muted = state.hiddenSeries.has(s.id) ? "muted" : "";
        const latestStr = s.latest !== null && s.latest !== undefined ? ` (${fmtPctText(s.latest)})` : "";
        return `<button type="button" class="legend-chip ${muted}" data-series-id="${escapeHtml(s.id)}">
          <span class="legend-swatch" style="background:${escapeHtml(s.color)}"></span>
          <span>${escapeHtml(s.name)}${escapeHtml(latestStr)}</span>
        </button>`;
      })
      .join("");

    el.chartLegend.querySelectorAll(".legend-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-series-id");
        if (state.hiddenSeries.has(id)) state.hiddenSeries.delete(id);
        else state.hiddenSeries.add(id);
        renderPrimaryChart();
      });
    });

    window.AICharts.drawMultiLineChart(el.mainChart, el.mainTooltip, {
      labels,
      series,
      hiddenIds: state.hiddenSeries,
    });
  }

  function renderUnusualMoves() {
    const items = state.data.unusual_moves || [];
    if (!items.length) {
      el.unusualList.innerHTML = '<div class="empty-state">No unusual price or volume spikes detected right now.</div>';
      return;
    }
    el.unusualList.innerHTML = items
      .map((item) => {
        const badges = (item.unusual_reasons || [])
          .map((reason) => {
            let cls = "badge-warn";
            if (reason.startsWith("Move +") || reason.startsWith("Z-Score +")) cls = "badge-pos";
            else if (reason.startsWith("Move -") || reason.startsWith("Z-Score -")) cls = "badge-neg";
            return `<span class="badge ${cls}">${escapeHtml(reason)}</span>`;
          })
          .join("");
        return `<div class="unusual-item" data-symbol="${escapeHtml(item.symbol)}">
          <div class="unusual-left">
            <div class="unusual-sym">${escapeHtml(item.symbol)} <span class="muted-val" style="font-weight:400">${fmtPrice(item.price)}</span></div>
            <div class="unusual-name">${escapeHtml(item.name)} · ${escapeHtml(item.sector_name)}</div>
            <div class="reason-badges">${badges}</div>
          </div>
          <div class="num" style="font-size:13px;font-weight:700">${fmtPct(item.ret_1d)}</div>
        </div>`;
      })
      .join("");

    el.unusualList.querySelectorAll(".unusual-item").forEach((node) => {
      node.addEventListener("click", () => openTickerModal(node.getAttribute("data-symbol")));
    });
  }

  function renderSectorCards() {
    const sectors = state.data.sectors || [];
    const wKey = state.sectorWeight;
    const activeField = RANGE_TO_FIELD[state.range] || "ret_ytd";

    el.sectorGrid.innerHTML = sectors
      .map((sec) => {
        const stats = sec[wKey] || sec.equal;
        const isActive = state.sectorFilter === sec.id ? "active" : "";
        const breadth = sec.breadth_pct ?? 0;
        const gainer = sec.top_gainer
          ? `${escapeHtml(sec.top_gainer.symbol)} ${fmtPct(sec.top_gainer.ret_1d)}`
          : "--";
        return `<article class="sector-card ${isActive}" data-sector-id="${escapeHtml(sec.id)}" style="border-top-color:${escapeHtml(sec.color)}">
          <div class="sector-name">${escapeHtml(sec.short_name)}</div>
          <div class="sector-metrics">
            <div><div class="sector-metric-label">1D</div>${fmtPct(stats.ret_1d)}</div>
            <div><div class="sector-metric-label">1M</div>${fmtPct(stats.ret_1m)}</div>
            <div><div class="sector-metric-label">${escapeHtml(state.range === "1D" ? "YTD" : state.range)}</div>${fmtPct(stats[state.range === "1D" ? "ret_ytd" : activeField])}</div>
          </div>
          <div class="breadth-bar"><div class="breadth-fill" style="width:${breadth}%"></div></div>
          <div class="sector-foot">
            <span>${sec.up_count}/${sec.count} up</span>
            <span>Lead: ${gainer}</span>
          </div>
        </article>`;
      })
      .join("");

    el.sectorGrid.querySelectorAll(".sector-card").forEach((card) => {
      card.addEventListener("click", () => {
        const sid = card.getAttribute("data-sector-id");
        state.sectorFilter = state.sectorFilter === sid ? "all" : sid;
        renderSectorCards();
        renderSectorFilterPills();
        renderWatchlistTable();
      });
    });
  }

  function correlationCellStyle(val) {
    if (val === null || val === undefined || !Number.isFinite(val)) return "";
    if (val >= 0) {
      const alpha = Math.min(0.65, Math.max(0.08, val * 0.6)).toFixed(2);
      return `background: rgba(16, 185, 129, ${alpha});`;
    }
    const alpha = Math.min(0.65, Math.max(0.08, Math.abs(val) * 0.6)).toFixed(2);
    return `background: rgba(244, 63, 94, ${alpha});`;
  }

  function renderCorrelationMatrix() {
    const corr = state.data.correlations;
    if (!corr || !corr.labels || !corr.labels.length) {
      el.corrMatrix.innerHTML = '<div class="empty-state">Insufficient return history for correlation.</div>';
      return;
    }
    el.corrWindowLabel.textContent = `Daily return correlation (${corr.window} window)`;

    const headers = corr.labels.map((lbl) => `<th>${escapeHtml(lbl)}</th>`).join("");
    const rows = corr.labels
      .map((rowLbl, rIdx) => {
        const cells = corr.matrix[rIdx]
          .map((val) => {
            const txt = val !== null && val !== undefined ? val.toFixed(2) : "--";
            return `<td style="${correlationCellStyle(val)}">${txt}</td>`;
          })
          .join("");
        return `<tr><th>${escapeHtml(rowLbl)}</th>${cells}</tr>`;
      })
      .join("");

    el.corrMatrix.innerHTML = `<table class="corr-table">
      <thead><tr><th></th>${headers}</tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  function renderSectorBars() {
    const field = RANGE_TO_FIELD[state.range] || "ret_ytd";
    const wKey = state.sectorWeight;
    el.barChartTitle.textContent = `Sector & Benchmark Comparison (${state.range}, ${wKey === "cap" ? "Cap-Wt" : "Equal-Wt"})`;

    const entries = [];
    for (const sec of state.data.sectors || []) {
      if (sec.is_benchmark) continue;
      const val = sec[wKey]?.[field];
      entries.push({ label: sec.short_name, color: sec.color, value: val });
    }
    for (const [sym, label] of [
      ["^NDX", "NASDAQ 100"],
      ["^GSPC", "S&P 500"],
      ["SMH", "SMH (ETF)"],
      ["QQQ", "QQQ (ETF)"],
      ["SPY", "SPY (ETF)"],
    ]) {
      const b = state.data.composite?.benchmarks?.[sym];
      if (b) {
        entries.push({ label, color: "#64748b", value: b[field] });
      }
    }

    entries.sort((a, b) => (b.value ?? -999) - (a.value ?? -999));
    const maxAbs = Math.max(1, ...entries.map((e) => Math.abs(e.value || 0)));

    el.sectorBars.innerHTML = entries
      .map((entry) => {
        const val = entry.value;
        const pctWidth = val !== null && val !== undefined ? Math.min(100, (Math.abs(val) / maxAbs) * 100) : 0;
        const barColor = val !== null && val < 0 ? "#f43f5e" : entry.color;
        return `<div class="bar-row">
          <div class="bar-label">${escapeHtml(entry.label)}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${pctWidth.toFixed(1)}%;background:${escapeHtml(barColor)}"></div>
          </div>
          <div class="bar-val">${fmtPct(val)}</div>
        </div>`;
      })
      .join("");
  }

  function renderSectorFilterPills() {
    const sectors = state.data.sector_meta || [];
    const pills = [{ id: "all", short_name: "All Sectors" }, ...sectors];
    el.sectorFilterPills.innerHTML = pills
      .map((p) => {
        const active = state.sectorFilter === p.id ? "active" : "";
        return `<button type="button" class="filter-pill ${active}" data-filter-sector="${escapeHtml(p.id)}">${escapeHtml(p.short_name)}</button>`;
      })
      .join("");

    el.sectorFilterPills.querySelectorAll(".filter-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.sectorFilter = btn.getAttribute("data-filter-sector");
        renderSectorCards();
        renderSectorFilterPills();
        renderWatchlistTable();
      });
    });
  }

  function renderWatchlistTable() {
    const query = state.search.trim().toLowerCase();
    let rows = [...(state.data.tickers || [])];

    if (state.sectorFilter !== "all") {
      rows = rows.filter((r) => r.sector === state.sectorFilter);
    }
    if (state.unusualOnly) {
      rows = rows.filter((r) => r.is_unusual);
    }
    if (query) {
      rows = rows.filter(
        (r) =>
          r.symbol.toLowerCase().includes(query) ||
          (r.name && r.name.toLowerCase().includes(query))
      );
    }

    const key = state.sortBy;
    const dir = state.sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      const av = a[key];
      const bv = b[key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "string") return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });

    if (!rows.length) {
      el.watchlistTbody.innerHTML = '<tr><td colspan="14" class="empty-state">No tickers match your filter.</td></tr>';
      return;
    }

    el.watchlistTbody.innerHTML = rows
      .map((r) => {
        const volStr = r.vol_ratio !== null && r.vol_ratio !== undefined ? `${r.vol_ratio.toFixed(2)}x` : "--";
        const volCls = r.vol_ratio >= 1.5 ? "badge badge-warn" : "";
        const rangePct = r.range_52w_pct !== null && r.range_52w_pct !== undefined ? r.range_52w_pct : null;
        const rangeHtml =
          rangePct !== null
            ? `<div title="52W: ${fmtPrice(r.low_52w, r.symbol)} - ${fmtPrice(r.high_52w, r.symbol)}">
                 <span class="range-track"><span class="range-marker" style="left:${rangePct}%"></span></span>
               </div>`
            : '<span class="muted-val">--</span>';
        const sparkHtml = window.AICharts.renderSparklineSvg(r.sparkline);
        const flagHtml = r.is_unusual
          ? `<span class="badge badge-warn" title="${escapeHtml((r.unusual_reasons || []).join(", "))}">Alert</span>`
          : "";

        return `<tr data-symbol="${escapeHtml(r.symbol)}">
          <td>
            <div class="ticker-cell">
              <span class="ticker-sym">${escapeHtml(r.symbol)}</span>
              <span class="ticker-name">${escapeHtml(r.name)}</span>
            </div>
          </td>
          <td>
            <span class="sector-tag">
              <span class="sector-dot" style="background:${escapeHtml(r.sector_color)}"></span>
              ${escapeHtml(r.sector_name)}
            </span>
          </td>
          <td class="num">${fmtPrice(r.price, r.symbol)}</td>
          <td class="num">${fmtPct(r.ret_1d)}</td>
          <td class="num">${fmtPct(r.ret_1w)}</td>
          <td class="num">${fmtPct(r.ret_1m)}</td>
          <td class="num">${fmtPct(r.ret_3m)}</td>
          <td class="num">${fmtPct(r.ret_ytd)}</td>
          <td class="num">${fmtPct(r.ret_1y)}</td>
          <td class="num"><span class="${volCls}">${volStr}</span></td>
          <td>${rangeHtml}</td>
          <td>${sparkHtml}</td>
          <td class="num">${fmtCap(r.market_cap)}</td>
          <td class="num">
            ${flagHtml}
            ${state.staticMode ? "" : `<button type="button" class="remove-btn" data-remove="${escapeHtml(r.symbol)}" title="Remove ${escapeHtml(r.symbol)}">&times;</button>`}
          </td>
        </tr>`;
      })
      .join("");

    el.watchlistTbody.querySelectorAll("tr[data-symbol]").forEach((tr) => {
      tr.addEventListener("click", (evt) => {
        if (evt.target.closest("[data-remove]")) return;
        openTickerModal(tr.getAttribute("data-symbol"));
      });
    });

    el.watchlistTbody.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", async (evt) => {
        evt.stopPropagation();
        const sym = btn.getAttribute("data-remove");
        try {
          const res = await fetch(`/api/watchlist/${encodeURIComponent(sym)}`, { method: "DELETE" });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to remove ticker");
          }
          await loadOverview(false);
        } catch (err) {
          showError(err.message);
        }
      });
    });
  }

  async function openTickerModal(symbol) {
    if (!symbol) return;
    state.detailSymbol = symbol;
    el.detailModal.classList.remove("hidden");
    await loadTickerDetail();
  }

  async function loadTickerDetail() {
    if (!state.detailSymbol) return;
    el.detailTitle.textContent = `${state.detailSymbol} — Loading...`;
    try {
      let s;
      let series;
      if (state.staticMode) {
        let doc = state.tickerCache.get(state.detailSymbol);
        if (!doc) {
          const fname = safeSymbolFilename(state.detailSymbol);
          const res = await fetch(`data/tickers/${encodeURIComponent(fname)}.json`, { cache: "no-store" });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          doc = await res.json();
          state.tickerCache.set(state.detailSymbol, doc);
        }
        s = doc.snapshot;
        series = doc.ranges?.[state.detailRange] || { labels: [], prices: [], volumes: [] };
      } else {
        const res = await fetch(
          `/api/market/ticker/${encodeURIComponent(state.detailSymbol)}?range=${encodeURIComponent(state.detailRange)}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        s = payload.snapshot;
        series = payload.series || { labels: [], prices: [], volumes: [] };
      }

      el.detailTitle.textContent = `${s.symbol} · ${s.name}`;
      el.detailSubtitle.textContent = `${s.sector_name} · 52W Range: ${fmtPrice(s.low_52w, s.symbol)} – ${fmtPrice(s.high_52w, s.symbol)}`;

      el.detailStats.innerHTML = `
        <div class="detail-stat-box">
          <div class="detail-stat-label">Last Price (1D)</div>
          <div class="detail-stat-val">${fmtPrice(s.price, s.symbol)} ${fmtPct(s.ret_1d)}</div>
        </div>
        <div class="detail-stat-box">
          <div class="detail-stat-label">YTD / 1Y Return</div>
          <div class="detail-stat-val">${fmtPct(s.ret_ytd)} / ${fmtPct(s.ret_1y)}</div>
        </div>
        <div class="detail-stat-box">
          <div class="detail-stat-label">Vol Ratio / 30D Ann Vol</div>
          <div class="detail-stat-val">${s.vol_ratio ? s.vol_ratio.toFixed(2) + "x" : "--"} · ${s.vol_30d_ann ? s.vol_30d_ann.toFixed(1) + "%" : "--"}</div>
        </div>
        <div class="detail-stat-box">
          <div class="detail-stat-label">Market Cap / Fwd P/E · Z</div>
          <div class="detail-stat-val">${fmtCap(s.market_cap)} · ${s.forward_pe ? s.forward_pe.toFixed(1) + "x" : "--"} · ${s.z_score_1d !== null && s.z_score_1d !== undefined ? s.z_score_1d.toFixed(2) + "σ" : "--"}</div>
        </div>
      `;

      window.AICharts.drawDetailPriceChart(el.detailChart, el.detailTooltip, {
        labels: series.labels || [],
        prices: series.prices || [],
        volumes: series.volumes || [],
        isIndex: String(s.symbol).startsWith("^"),
      });
    } catch (err) {
      el.detailTitle.textContent = state.detailSymbol;
      el.detailSubtitle.textContent = `Error loading detail: ${err.message}`;
    }
  }

  function bindEvents() {
    el.rangeSelector.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        el.rangeSelector.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.range = btn.getAttribute("data-range");
        if (state.range === "1D") {
          renderAll();
        } else {
          loadOverview(false);
        }
      });
    });

    el.sectorWeightToggle.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        el.sectorWeightToggle.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.sectorWeight = btn.getAttribute("data-weight");
        renderSectorCards();
        renderSectorBars();
      });
    });

    el.refreshBtn.addEventListener("click", () => {
      state.countdown = 60;
      loadOverview(true);
    });

    el.autoRefreshBtn.addEventListener("click", () => {
      state.autoRefresh = !state.autoRefresh;
      state.countdown = 60;
      el.autoRefreshState.textContent = state.autoRefresh ? "ON (60s)" : "OFF";
    });

    el.searchInput.addEventListener("input", () => {
      state.search = el.searchInput.value;
      renderWatchlistTable();
    });

    el.unusualOnlyToggle.addEventListener("change", () => {
      state.unusualOnly = el.unusualOnlyToggle.checked;
      renderWatchlistTable();
    });

    document.querySelectorAll("#watchlist-table thead th[data-sort]").forEach((th) => {
      th.addEventListener("click", () => {
        const col = th.getAttribute("data-sort");
        if (state.sortBy === col) {
          state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
        } else {
          state.sortBy = col;
          state.sortDir = col === "symbol" || col === "sector_name" ? "asc" : "desc";
        }
        renderWatchlistTable();
      });
    });

    // Detail modal
    el.closeDetailBtn.addEventListener("click", () => el.detailModal.classList.add("hidden"));
    el.detailModal.addEventListener("click", (evt) => {
      if (evt.target === el.detailModal) el.detailModal.classList.add("hidden");
    });
    el.detailRangeSelector.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        el.detailRangeSelector.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.detailRange = btn.getAttribute("data-range");
        loadTickerDetail();
      });
    });

    // Add ticker modal
    el.openAddModalBtn.addEventListener("click", () => {
      el.addFormError.classList.add("hidden");
      el.newSymbolInput.value = "";
      el.addModal.classList.remove("hidden");
      el.newSymbolInput.focus();
    });
    el.closeAddBtn.addEventListener("click", () => el.addModal.classList.add("hidden"));
    el.addModal.addEventListener("click", (evt) => {
      if (evt.target === el.addModal) el.addModal.classList.add("hidden");
    });

    el.addTickerForm.addEventListener("submit", async (evt) => {
      evt.preventDefault();
      el.addFormError.classList.add("hidden");
      const symbol = el.newSymbolInput.value.trim().toUpperCase();
      const sector = el.newSectorSelect.value;
      try {
        const res = await fetch("/api/watchlist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol, sector }),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail || "Unable to add ticker");
        el.addModal.classList.add("hidden");
        await loadOverview(false);
      } catch (err) {
        el.addFormError.textContent = err.message;
        el.addFormError.classList.remove("hidden");
      }
    });

    el.resetWatchlistBtn.addEventListener("click", async () => {
      await fetch("/api/watchlist/reset", { method: "POST" });
      el.addModal.classList.add("hidden");
      await loadOverview(false);
    });

    window.addEventListener("resize", () => {
      if (state.data) renderPrimaryChart();
    });
  }

  function startAutoRefreshTimer() {
    setInterval(() => {
      if (!state.autoRefresh) return;
      state.countdown -= 1;
      if (state.countdown <= 0) {
        state.countdown = 60;
        loadOverview(true);
      }
      el.autoRefreshState.textContent = `ON (${state.countdown}s)`;
    }, 1000);
  }

  async function init() {
    bindEvents();
    await detectBackendMode();
    startAutoRefreshTimer();
    await loadOverview(false);
  }

  init();
})();
