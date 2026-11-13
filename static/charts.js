/* Zero-dependency Canvas 2D & SVG charting helpers for AI & Adjacent Markets Index. */

(function (global) {
  "use strict";

  function setupHiDPICanvas(canvas) {
    const rect = canvas.parentElement.getBoundingClientRect();
    const width = Math.max(200, Math.floor(rect.width));
    const height = Math.max(180, Math.floor(rect.height));
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, width, height };
  }

  function formatAxisPct(val) {
    const sign = val > 0 ? "+" : "";
    return `${sign}${val.toFixed(1)}%`;
  }

  function formatPrice(val, isIndex = false) {
    const formatted = Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return isIndex ? formatted : `$${formatted}`;
  }

  function drawMultiLineChart(canvas, tooltipEl, config) {
    const { labels = [], series = [], hiddenIds = new Set() } = config;
    const { ctx, width, height } = setupHiDPICanvas(canvas);

    ctx.clearRect(0, 0, width, height);

    const activeSeries = series.filter(
      (s) => !hiddenIds.has(s.id) && Array.isArray(s.values) && s.values.length > 0
    );

    if (!labels.length || !activeSeries.length) {
      ctx.fillStyle = "#64748b";
      ctx.font = "13px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No chart data available for this selection", width / 2, height / 2);
      return;
    }

    const pad = { top: 14, right: 62, bottom: 28, left: 12 };
    const plotW = Math.max(40, width - pad.left - pad.right);
    const plotH = Math.max(40, height - pad.top - pad.bottom);

    let minVal = 0;
    let maxVal = 0;
    for (const s of activeSeries) {
      for (const v of s.values) {
        if (v !== null && v !== undefined && Number.isFinite(v)) {
          if (v < minVal) minVal = v;
          if (v > maxVal) maxVal = v;
        }
      }
    }
    const span = Math.max(1.0, maxVal - minVal);
    minVal -= span * 0.08;
    maxVal += span * 0.08;

    const xFor = (idx) => {
      if (labels.length <= 1) return pad.left;
      return pad.left + (idx / (labels.length - 1)) * plotW;
    };
    const yFor = (val) => {
      return pad.top + (1 - (val - minVal) / (maxVal - minVal)) * plotH;
    };

    function renderFrame(hoverIdx) {
      ctx.clearRect(0, 0, width, height);

      // Horizontal grid lines
      const gridCount = 5;
      ctx.font = "11px ui-monospace, monospace";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      for (let i = 0; i <= gridCount; i++) {
        const val = minVal + ((maxVal - minVal) * i) / gridCount;
        const y = yFor(val);
        ctx.strokeStyle = "rgba(148, 163, 184, 0.12)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();

        ctx.fillStyle = "#64748b";
        ctx.fillText(formatAxisPct(val), width - pad.right + 6, y);
      }

      // Zero baseline
      if (minVal <= 0 && maxVal >= 0) {
        const y0 = yFor(0);
        ctx.strokeStyle = "rgba(226, 232, 240, 0.28)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(pad.left, y0);
        ctx.lineTo(width - pad.right, y0);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // X-axis tick labels
      const tickCount = Math.min(6, labels.length);
      ctx.fillStyle = "#64748b";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      for (let t = 0; t < tickCount; t++) {
        const idx = tickCount === 1 ? 0 : Math.round((t / (tickCount - 1)) * (labels.length - 1));
        const x = xFor(idx);
        ctx.fillText(labels[idx], x, height - pad.bottom + 8);
      }

      // Series lines
      for (const s of activeSeries) {
        ctx.save();
        ctx.strokeStyle = s.color || "#22d3ee";
        ctx.lineWidth = s.kind === "composite" ? 2.6 : 1.7;
        if (s.dashed) {
          ctx.setLineDash([5, 4]);
        }
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < labels.length; i++) {
          const val = s.values[i];
          if (val === null || val === undefined || !Number.isFinite(val)) {
            started = false;
            continue;
          }
          const x = xFor(i);
          const y = yFor(val);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
        ctx.restore();
      }

      // Hover crosshair & dots
      if (hoverIdx !== null && hoverIdx >= 0 && hoverIdx < labels.length) {
        const hx = xFor(hoverIdx);
        ctx.strokeStyle = "rgba(226, 232, 240, 0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(hx, pad.top);
        ctx.lineTo(hx, pad.top + plotH);
        ctx.stroke();

        for (const s of activeSeries) {
          const val = s.values[hoverIdx];
          if (val === null || val === undefined || !Number.isFinite(val)) continue;
          const hy = yFor(val);
          ctx.fillStyle = s.color || "#22d3ee";
          ctx.beginPath();
          ctx.arc(hx, hy, 3.8, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    renderFrame(null);

    canvas.onmousemove = (evt) => {
      const rect = canvas.getBoundingClientRect();
      const mx = evt.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, (mx - pad.left) / plotW));
      const idx = Math.round(ratio * (labels.length - 1));
      renderFrame(idx);

      const rows = activeSeries
        .map((s) => ({
          name: s.name,
          color: s.color,
          val: s.values[idx],
        }))
        .filter((r) => r.val !== null && r.val !== undefined && Number.isFinite(r.val))
        .sort((a, b) => b.val - a.val);

      if (!rows.length) {
        tooltipEl.classList.add("hidden");
        return;
      }

      tooltipEl.innerHTML =
        `<div class="tooltip-title">${labels[idx]}</div>` +
        rows
          .map((r) => {
            const sign = r.val > 0 ? "+" : "";
            const cls = r.val >= 0 ? "pos" : "neg";
            return `<div class="tooltip-row">
              <span style="color:${r.color}">${r.name}</span>
              <span class="${cls}">${sign}${r.val.toFixed(2)}%</span>
            </div>`;
          })
          .join("");
      tooltipEl.classList.remove("hidden");

      const hx = xFor(idx);
      const tipW = tooltipEl.offsetWidth || 180;
      const left = hx + 14 + tipW > width ? Math.max(8, hx - tipW - 14) : hx + 14;
      tooltipEl.style.left = `${left}px`;
      tooltipEl.style.top = "14px";
    };

    canvas.onmouseleave = () => {
      renderFrame(null);
      tooltipEl.classList.add("hidden");
    };
  }

  function drawDetailPriceChart(canvas, tooltipEl, config) {
    const { labels = [], prices = [], volumes = [], isIndex = false } = config;
    const { ctx, width, height } = setupHiDPICanvas(canvas);

    ctx.clearRect(0, 0, width, height);

    if (!labels.length || !prices.length) {
      ctx.fillStyle = "#64748b";
      ctx.font = "13px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No price history available", width / 2, height / 2);
      return;
    }

    const pad = { top: 14, right: 68, bottom: 28, left: 12 };
    const plotW = Math.max(40, width - pad.left - pad.right);
    const plotH = Math.max(40, height - pad.top - pad.bottom);

    let minP = Math.min(...prices);
    let maxP = Math.max(...prices);
    const span = Math.max(0.5, maxP - minP);
    minP -= span * 0.08;
    maxP += span * 0.08;

    const maxVol = volumes.length ? Math.max(...volumes, 1) : 0;
    const isUp = prices[prices.length - 1] >= prices[0];
    const lineColor = isUp ? "#10b981" : "#f43f5e";

    const xFor = (idx) => {
      if (labels.length <= 1) return pad.left;
      return pad.left + (idx / (labels.length - 1)) * plotW;
    };
    const yFor = (val) => pad.top + (1 - (val - minP) / (maxP - minP)) * plotH;

    function renderFrame(hoverIdx) {
      ctx.clearRect(0, 0, width, height);

      // Grid lines
      const gridCount = 4;
      ctx.font = "11px ui-monospace, monospace";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      for (let i = 0; i <= gridCount; i++) {
        const val = minP + ((maxP - minP) * i) / gridCount;
        const y = yFor(val);
        ctx.strokeStyle = "rgba(148, 163, 184, 0.12)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();

        ctx.fillStyle = "#64748b";
        ctx.fillText(formatPrice(val, isIndex), width - pad.right + 6, y);
      }

      // Volume bars along bottom 20%
      if (maxVol > 0 && volumes.length === prices.length) {
        const barW = Math.max(1.5, (plotW / labels.length) * 0.65);
        ctx.fillStyle = "rgba(56, 189, 248, 0.20)";
        for (let i = 0; i < volumes.length; i++) {
          const v = volumes[i] || 0;
          const bh = (v / maxVol) * (plotH * 0.22);
          const bx = xFor(i) - barW / 2;
          const by = pad.top + plotH - bh;
          ctx.fillRect(bx, by, barW, bh);
        }
      }

      // Price area gradient
      const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
      grad.addColorStop(0, isUp ? "rgba(16, 185, 129, 0.28)" : "rgba(244, 63, 94, 0.28)");
      grad.addColorStop(1, "rgba(15, 23, 42, 0.0)");

      ctx.beginPath();
      ctx.moveTo(xFor(0), pad.top + plotH);
      for (let i = 0; i < prices.length; i++) {
        ctx.lineTo(xFor(i), yFor(prices[i]));
      }
      ctx.lineTo(xFor(prices.length - 1), pad.top + plotH);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Price line
      ctx.strokeStyle = lineColor;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      for (let i = 0; i < prices.length; i++) {
        const x = xFor(i);
        const y = yFor(prices[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // X-axis ticks
      const tickCount = Math.min(6, labels.length);
      ctx.fillStyle = "#64748b";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      for (let t = 0; t < tickCount; t++) {
        const idx = tickCount === 1 ? 0 : Math.round((t / (tickCount - 1)) * (labels.length - 1));
        ctx.fillText(labels[idx], xFor(idx), height - pad.bottom + 8);
      }

      if (hoverIdx !== null && hoverIdx >= 0 && hoverIdx < labels.length) {
        const hx = xFor(hoverIdx);
        const hy = yFor(prices[hoverIdx]);
        ctx.strokeStyle = "rgba(226, 232, 240, 0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(hx, pad.top);
        ctx.lineTo(hx, pad.top + plotH);
        ctx.stroke();

        ctx.fillStyle = lineColor;
        ctx.beginPath();
        ctx.arc(hx, hy, 4.2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    renderFrame(null);

    canvas.onmousemove = (evt) => {
      const rect = canvas.getBoundingClientRect();
      const mx = evt.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, (mx - pad.left) / plotW));
      const idx = Math.round(ratio * (labels.length - 1));
      renderFrame(idx);

      const px = prices[idx];
      const base = prices[0];
      const chg = base > 0 ? ((px / base - 1) * 100).toFixed(2) : "0.00";
      const sign = Number(chg) > 0 ? "+" : "";
      const vol = volumes[idx] ? Number(volumes[idx]).toLocaleString() : "N/A";

      tooltipEl.innerHTML = `
        <div class="tooltip-title">${labels[idx]}</div>
        <div class="tooltip-row"><span>Price</span><span>${formatPrice(px, isIndex)}</span></div>
        <div class="tooltip-row"><span>Period Chg</span><span>${sign}${chg}%</span></div>
        ${volumes.length ? `<div class="tooltip-row"><span>Volume</span><span>${vol}</span></div>` : ""}
      `;
      tooltipEl.classList.remove("hidden");

      const hx = xFor(idx);
      const tipW = tooltipEl.offsetWidth || 165;
      const left = hx + 14 + tipW > width ? Math.max(8, hx - tipW - 14) : hx + 14;
      tooltipEl.style.left = `${left}px`;
      tooltipEl.style.top = "14px";
    };

    canvas.onmouseleave = () => {
      renderFrame(null);
      tooltipEl.classList.add("hidden");
    };
  }

  function renderSparklineSvg(values) {
    if (!Array.isArray(values) || values.length < 2) {
      return '<span class="muted-val">--</span>';
    }
    const w = 78;
    const h = 22;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const pts = values
      .map((v, i) => {
        const x = ((i / (values.length - 1)) * w).toFixed(1);
        const y = (h - 2 - ((v - min) / span) * (h - 4)).toFixed(1);
        return `${x},${y}`;
      })
      .join(" ");
    const color = values[values.length - 1] >= values[0] ? "#10b981" : "#f43f5e";
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <polyline fill="none" stroke="${color}" stroke-width="1.6" points="${pts}" />
    </svg>`;
  }

  global.AICharts = {
    drawMultiLineChart,
    drawDetailPriceChart,
    renderSparklineSvg,
  };
})(window);
