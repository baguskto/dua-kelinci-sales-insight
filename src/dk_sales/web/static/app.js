"use strict";
// All server data is inserted with textContent, never innerHTML, so file values cannot become markup.
// Charts: Apache ECharts (vendored). Tooltips use richText mode so the strict CSP (no inline styles) holds.
(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const css = getComputedStyle(document.documentElement);
  const C = {
    text: css.getPropertyValue("--text").trim() || "#1b1f24",
    muted: css.getPropertyValue("--muted").trim() || "#59616b",
    line: css.getPropertyValue("--line").trim() || "#e3e6ea",
    accent: css.getPropertyValue("--accent").trim() || "#1f4e79",
    seq1: css.getPropertyValue("--seq-1").trim() || "#dbe8f5",
    seq9: css.getPropertyValue("--seq-9").trim() || "#0b3a66",
    up: css.getPropertyValue("--up").trim() || "#1f6fb2",
    down: css.getPropertyValue("--down").trim() || "#b85c00",
  };

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function filterUrl(params) {
    const u = new URL(window.location.href);
    Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
    return u.pathname + u.search;
  }

  // -- charts ---------------------------------------------------------------
  const dataEl = document.getElementById("chart-data");
  const charts = [];
  if (dataEl && window.echarts) {
    const D = JSON.parse(dataEl.textContent);
    const base = { textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", color: C.text }, animation: false };
    const tooltip = { renderMode: "richText", backgroundColor: "#1b1f24", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12 } };

    function mount(id) {
      const node = document.getElementById(id);
      if (!node) return null;
      node.classList.remove("skeleton");
      const c = window.echarts.init(node, null, { renderer: "svg" });
      charts.push(c);
      return c;
    }

    // Region: dumbbell from previous to current month, sorted by current month, MoM label at the end.
    const regionChart = mount("chart-region");
    if (regionChart) {
      const rows = D.region.slice().reverse();
      const hasMom = rows.length && rows[0].prev !== null;
      const names = rows.map((r) => r.key);
      if (hasMom) {
        const max = Math.max(...rows.map((r) => Math.max(r.prev, r.curr)));
        regionChart.setOption(Object.assign({}, base, {
          grid: { left: 96, right: 150, top: 24, bottom: 8 },
          tooltip: Object.assign({ trigger: "item", formatter: (p) => { const r = rows[p.dataIndex]; return `${r.key}\n${D.months[0]}: ${r.prev_label}\n${D.months[1]}: ${r.curr_label}\n${r.mom_label}`; } }, tooltip),
          legend: { data: D.months, top: 0, right: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: C.muted, fontSize: 11 } },
          xAxis: { type: "value", max: max * 1.05, axisLabel: { show: false }, splitLine: { show: false } },
          yAxis: { type: "category", data: names, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: C.text } },
          series: [
            { type: "custom", name: "garis", silent: true, renderItem: (params, api) => {
                const a = api.coord([api.value(1), api.value(0)]);
                const b = api.coord([api.value(2), api.value(0)]);
                const r = rows[params.dataIndex];
                return { type: "line", shape: { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, style: { stroke: r.mom >= 0 ? C.up : C.down, lineWidth: 3 } };
              }, data: rows.map((r, i) => [i, r.prev, r.curr]), z: 1 },
            { type: "scatter", name: D.months[0], symbolSize: 10, itemStyle: { color: C.seq1, borderColor: C.accent, borderWidth: 1.5 }, data: rows.map((r) => r.prev), z: 2 },
            { type: "scatter", name: D.months[1], symbolSize: 12, itemStyle: { color: C.accent }, data: rows.map((r) => r.curr), z: 3 },
            // Invisible anchor at the right end of each dumbbell carries the label, so it never overlaps the line.
            { type: "scatter", name: "label", silent: true, symbolSize: 0, data: rows.map((r) => Math.max(r.prev, r.curr)), z: 4,
              label: { show: true, position: "right", distance: 12, formatter: (p) => { const r = rows[p.dataIndex]; return `${r.curr_label}  ${r.mom >= 0 ? "▲" : "▼"} ${r.mom_label}`; }, color: C.text, fontSize: 11 } },
          ],
        }));
      } else {
        regionChart.setOption(barOption(rows, "Region"));
      }
      regionChart.on("click", (p) => { const r = rows[p.dataIndex]; if (r) window.location.href = filterUrl({ region: r.key }); });
    }

    function barOption(rows, label) {
      return Object.assign({}, base, {
        grid: { left: 128, right: 128, top: 4, bottom: 4 },
        tooltip: Object.assign({ trigger: "item", formatter: (p) => `${rows[p.dataIndex].key}\n${rows[p.dataIndex].label}` }, tooltip),
        xAxis: { type: "value", axisLabel: { show: false }, splitLine: { show: false } },
        yAxis: { type: "category", data: rows.map((r) => r.key), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: C.text, width: 120, overflow: "truncate" } },
        series: [{ type: "bar", name: label, data: rows.map((r) => r.value), itemStyle: { color: C.accent, borderRadius: [0, 3, 3, 0] }, barMaxWidth: 18,
          label: { show: true, position: "right", formatter: (p) => rows[p.dataIndex].label, color: C.muted, fontSize: 11 } }],
      });
    }

    const brandChart = mount("chart-brand");
    if (brandChart) {
      const rows = D.brand.slice().reverse();
      brandChart.setOption(barOption(rows, "Brand"));
      brandChart.on("click", (p) => { const r = rows[p.dataIndex]; if (r) window.location.href = filterUrl({ brand: r.key }); });
    }

    const heatChart = mount("chart-heat");
    if (heatChart && D.heat.cells.length) {
      const H = D.heat;
      const regions = H.regions.slice().reverse();
      const max = Math.max(...H.cells.map((c) => c.value));
      // Dark cells get light text so the printed value stays readable (WCAG AA).
      const cells = H.cells.map((c) => ({
        value: [H.brands.indexOf(c.brand), regions.indexOf(c.region), c.value, c.label, c.full, c.region, c.brand],
        label: { color: c.value > max * 0.55 ? "#ffffff" : "#111111" },
      }));
      heatChart.setOption(Object.assign({}, base, {
        grid: { left: 96, right: 8, top: 8, bottom: 40 },
        tooltip: Object.assign({ trigger: "item", formatter: (p) => `${p.value[5]} x ${p.value[6]}\n${p.value[4]}` }, tooltip),
        xAxis: { type: "category", data: H.brands, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { interval: 0, color: C.text, fontSize: 11, width: 70, overflow: "break" } },
        yAxis: { type: "category", data: regions, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: C.text } },
        visualMap: { show: false, min: 0, max: max, inRange: { color: [C.seq1, C.seq9] }, dimension: 2 },
        series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: "#fff", borderWidth: 2 },
          label: { show: true, formatter: (p) => p.value[3], fontSize: 11 },
          emphasis: { itemStyle: { borderColor: C.text, borderWidth: 2 } } }],
      }));
      heatChart.on("click", (p) => { window.location.href = filterUrl({ region: p.value[5], brand: p.value[6] }); });
    }
    window.addEventListener("resize", () => charts.forEach((c) => c.resize()));
  }

  // -- drawers --------------------------------------------------------------
  document.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", (ev) => {
    ev.preventDefault();
    const d = document.getElementById(b.dataset.open);
    if (d && d.showModal) { d.showModal(); const f = d.querySelector("input, button.close"); if (f) f.focus(); }
  }));
  document.querySelectorAll("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  document.querySelectorAll("dialog").forEach((d) => d.addEventListener("click", (ev) => { if (ev.target === d) d.close(); }));

  // -- Telegram summary -----------------------------------------------------
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Accept": "application/json" },
      body: JSON.stringify(body || {}),
      credentials: "same-origin",
    });
    let data = {};
    try { data = await r.json(); } catch (_) { data = { error: "Respons server tidak terbaca." }; }
    return { ok: r.ok, status: r.status, data };
  }

  const copyBtn = document.getElementById("copy-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const t = document.getElementById(copyBtn.dataset.target);
      const status = document.getElementById("tg-status");
      try {
        await navigator.clipboard.writeText(t.textContent);
        status.textContent = "Tersalin. Tempel di Telegram.";
      } catch (_) {
        const range = document.createRange();
        range.selectNodeContents(t);
        const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
        status.textContent = "Teks sudah dipilih, tekan Ctrl+C atau Cmd+C.";
      }
    });
  }
  const sendBtn = document.getElementById("tg-send");
  if (sendBtn) {
    sendBtn.addEventListener("click", async () => {
      const status = document.getElementById("tg-status");
      sendBtn.disabled = true;
      status.textContent = "Mengirim...";
      const r = await postJSON("/api/telegram/send", { period: sendBtn.dataset.period });
      status.textContent = r.data.message || r.data.error || "Selesai.";
      sendBtn.disabled = false;
    });
  }

  // -- chat -------------------------------------------------------------------
  const form = document.getElementById("chat-form");
  const log = document.getElementById("chat-log");
  async function ask(q) {
    if (!q.trim()) return;
    const qEl = el("div", "msg q", q);
    log.prepend(qEl);
    const aEl = el("div", "msg a", "Menghitung...");
    qEl.after(aEl);
    const r = await postJSON("/api/chat", { question: q });
    aEl.textContent = "";
    if (!r.ok) {
      aEl.classList.add("refusal");
      aEl.append(el("div", "", r.data.error || "Pertanyaan tidak bisa diproses (" + r.status + ")."));
      return;
    }
    const d = r.data;
    if (d.refusal) aEl.classList.add("refusal");
    aEl.append(el("div", "", d.text));
    if (d.table && d.table.length) {
      const t = el("table", "tbl");
      const tb = el("tbody");
      d.table.forEach((row) => {
        const tr = el("tr");
        tr.append(el("th", "", row.label));
        tr.append(el("td", "num", row.value));
        tb.append(tr);
      });
      t.append(tb);
      const det = el("details");
      det.append(el("summary", "", "Angka yang dipakai"));
      det.append(t);
      aEl.append(det);
    }
    const meta = el("div", "meta");
    meta.append(el("span", "srcchip", d.mode_label));
    (d.sources || []).forEach((s) => meta.append(el("span", "srcchip", "Sumber: " + s.label)));
    if (d.guard) meta.append(el("span", "srcchip", d.guard.ok ? "Cek angka: lolos" : "Cek angka: gagal"));
    if (d.fallback_reason) meta.append(el("span", "srcchip", "Fallback: " + d.fallback_reason));
    aEl.append(meta);
  }
  if (form) {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const input = document.getElementById("chat-q");
      const q = input.value;
      input.value = "";
      ask(q);
    });
    document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => ask(c.dataset.q)));
  }

  // -- upload with progress -----------------------------------------------------
  const up = document.getElementById("upload-form");
  if (up && window.XMLHttpRequest && window.FormData) {
    up.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const bar = document.getElementById("upload-progress");
      const status = document.getElementById("upload-status");
      const btn = up.querySelector("button[type=submit]");
      const xhr = new XMLHttpRequest();
      xhr.open("POST", up.action);
      xhr.setRequestHeader("Accept", "application/json");
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) { bar.hidden = false; bar.value = Math.round((e.loaded / e.total) * 100); }
      });
      xhr.addEventListener("load", () => {
        btn.disabled = false;
        btn.textContent = "Unggah dan periksa";
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch (_) { d = { ok: false, message: "Respons server tidak terbaca (" + xhr.status + ")." }; }
        if (xhr.status === 413) d = { ok: false, message: "File terlalu besar." };
        status.textContent = (d.ok ? "" : "File ditolak. ") + (d.message || d.error || "");
        status.classList.toggle("alert-text", !d.ok);
        if (d.ok) setTimeout(() => { window.location.href = "/"; }, 900);
      });
      xhr.addEventListener("error", () => { btn.disabled = false; status.textContent = "Koneksi terputus saat mengunggah."; });
      btn.disabled = true;
      btn.textContent = "Memeriksa file...";
      xhr.send(new FormData(up));
    });
  }
})();
