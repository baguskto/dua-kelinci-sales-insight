"use strict";
// All server data is inserted with textContent, never innerHTML, so file values cannot become markup.
// Charts: Apache ECharts (vendored). Tooltips use richText mode so the strict CSP (no inline styles) holds.
(function () {
  document.documentElement.classList.add("js");
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const FONT = '"Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  // Brand colors. Red = brand, decline and alerts; increases are ink (#161616), never red.
  const C = { ink: "#161616", red: "#DC2B2D", redInk: "#A51D20", muted: "#5B5652", grey: "#BDB4AC", ribbon: "#EBE2DC", line: "#EEE8E3", node: "#C9C2BB", bar: "#8A8580" };

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function filterUrl(params) {
    const u = new URL(window.location.href);
    Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
    u.hash = "";
    return u.pathname + u.search;
  }

  // Indonesian short rupiah, same rules as dk_sales.fmt.rupiah_short.
  function dec(v, digits) {
    let s = v.toFixed(digits);
    if (digits) s = s.replace(/0+$/, "").replace(/\.$/, "");
    return s.replace(".", ",");
  }
  function rp(v) {
    const a = Math.abs(v), sign = v < 0 ? "-" : "";
    if (a >= 1e9) return `${sign}Rp${dec(a / 1e9, 2)} miliar`;
    if (a >= 1e6) return `${sign}Rp${dec(a / 1e6, 1)} juta`;
    if (a >= 1e3) return `${sign}Rp${dec(a / 1e3, 0)} ribu`;
    return `${sign}Rp${Math.round(a)}`;
  }
  function axisJt(v) { return v >= 1e9 ? dec(v / 1e9, 1) + " M" : dec(v / 1e6, 0) + " jt"; }
  function arrow(m) { return (m ?? 0) >= 0 ? "▲" : "▼"; }

  // -- charts ---------------------------------------------------------------
  const dataEl = document.getElementById("chart-data");
  const charts = [];
  const narrow = () => window.innerWidth < 560;

  function initCharts() {
    if (!dataEl || !window.echarts) return;
    const D = JSON.parse(dataEl.textContent);
    const base = { textStyle: { fontFamily: FONT, color: C.ink }, animation: false };
    const tooltip = { renderMode: "richText", backgroundColor: C.ink, borderWidth: 0, padding: [8, 10], textStyle: { color: "#fff", fontSize: 12, fontFamily: FONT } };

    function mount(id) {
      const node = document.getElementById(id);
      if (!node) return null;
      node.classList.remove("skeleton");
      const c = window.echarts.init(node, null, { renderer: "svg" });
      charts.push(c);
      return c;
    }

    // Hero: running net sales by day of month, previous month grey, last month red, end labels.
    const cumChart = mount("chart-cum");
    if (cumChart && D.cumulative.length) {
      const S = D.cumulative;
      const n = Math.max(...S.map((s) => s.values.length));
      const days = Array.from({ length: n }, (_, i) => String(i + 1));
      const last = S[S.length - 1];
      const prev = S.length > 1 ? S[S.length - 2] : null;
      const lastHigher = !prev || last.values[last.values.length - 1] >= prev.values[prev.values.length - 1];
      const series = [];
      if (prev) {
        series.push({ type: "line", name: prev.month, data: prev.values, symbol: "none", lineStyle: { color: C.grey, width: 2.5 }, z: 2,
          endLabel: { show: true, offset: [0, lastHigher ? 10 : -10], formatter: () => `${prev.month}  ${prev.total_label}`, color: C.muted, fontFamily: FONT, fontWeight: 600, fontSize: 12 } });
      }
      series.push({ type: "line", name: last.month, data: last.values, symbol: "none", lineStyle: { color: C.red, width: 3.5 }, z: 3,
        areaStyle: { color: "rgba(220,43,45,0.07)" },
        endLabel: { show: true, offset: [0, prev ? (lastHigher ? -10 : 10) : 0], formatter: () => `${last.month}  ${last.total_label}`, color: C.redInk, fontFamily: FONT, fontWeight: 800, fontSize: 13 } });
      cumChart.setOption(Object.assign({}, base, {
        grid: { left: 56, right: narrow() ? 112 : 150, top: 16, bottom: 28 },
        tooltip: Object.assign({ trigger: "axis", axisPointer: { type: "line", lineStyle: { color: C.grey } },
          formatter: (ps) => [`Tanggal ${ps[0].axisValue}`].concat(ps.map((p) => `${p.seriesName}: ${rp(p.value)}`)).join("\n") }, tooltip),
        xAxis: { type: "category", data: days, boundaryGap: false, axisTick: { show: false }, axisLine: { lineStyle: { color: C.line } },
          axisLabel: { color: C.muted, interval: (i) => i === 0 || (i + 1) % 5 === 0, formatter: (v) => "tgl " + v } },
        yAxis: { type: "value", splitNumber: 4, axisLabel: { color: C.muted, formatter: axisJt }, splitLine: { lineStyle: { color: C.line } } },
        series,
      }));
    }

    // Region: dumbbell September -> Oktober (board B), sorted by change, label at the right end.
    const regionChart = mount("chart-region");
    if (regionChart) {
      const hasMom = D.region.length && D.region[0].prev !== null;
      if (hasMom) {
        const rows = D.region.slice().sort((a, b) => (a.mom ?? 0) - (b.mom ?? 0));
        regionChart.setOption(Object.assign({}, base, {
          grid: { left: narrow() ? 84 : 100, right: 78, top: 8, bottom: 24 },
          tooltip: Object.assign({ trigger: "item", formatter: (p) => { const r = rows[p.dataIndex]; return `${r.key}\n${D.months[0]}: ${r.prev_label}\n${D.months[1]}: ${r.curr_label}\n${arrow(r.mom)} ${r.mom_label}`; } }, tooltip),
          xAxis: { type: "value", min: 0, splitNumber: 3, axisLabel: { color: C.muted, formatter: axisJt }, splitLine: { lineStyle: { color: C.line } } },
          yAxis: { type: "category", data: rows.map((r) => r.key), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: C.ink, fontWeight: 600, fontSize: narrow() ? 11 : 12 } },
          series: [{ type: "custom", data: rows.map((r, i) => [r.prev, r.curr, i]), encode: { x: [0, 1], y: 2 }, z: 3,
            renderItem: (params, api) => {
              const r = rows[params.dataIndex];
              const s = api.coord([api.value(0), api.value(2)]);
              const o = api.coord([api.value(1), api.value(2)]);
              const up = (r.mom ?? 0) >= 0;
              const col = up ? C.ink : C.red;
              return { type: "group", children: [
                { type: "line", shape: { x1: s[0], y1: s[1], x2: o[0], y2: o[1] }, style: { stroke: col, lineWidth: 3 } },
                { type: "circle", shape: { cx: s[0], cy: s[1], r: 5.5 }, style: { fill: "#fff", stroke: "#8A8580", lineWidth: 2 } },
                { type: "circle", shape: { cx: o[0], cy: o[1], r: 6.5 }, style: { fill: col } },
                { type: "text", x: Math.max(s[0], o[0]) + 12, y: o[1], style: { text: `${arrow(r.mom)} ${r.mom_label}`, fill: up ? C.ink : C.redInk, font: `700 12px ${FONT}`, verticalAlign: "middle" } },
              ] };
            } }],
        }));
        regionChart.on("click", (p) => { const r = rows[p.dataIndex]; if (r) window.location.href = filterUrl({ region: r.key }); });
      } else {
        const rows = D.region.slice().reverse();
        regionChart.setOption(barOption(rows, false));
        regionChart.on("click", (p) => { const r = rows[p.dataIndex]; if (r) window.location.href = filterUrl({ region: r.key }); });
      }
    }

    // Brand: sorted bars with share and month-on-month change (decline in red, increase in ink).
    function barOption(rows, withMom) {
      const showMom = withMom && !narrow();
      return Object.assign({}, base, {
        grid: { left: narrow() ? 100 : 136, right: showMom ? 196 : 124, top: 4, bottom: 4 },
        tooltip: Object.assign({ trigger: "item", formatter: (p) => { const r = rows[p.dataIndex]; return `${r.key}\n${r.label}${r.mom_label ? `\n${arrow(r.mom)} ${r.mom_label} vs bulan sebelumnya` : ""}`; } }, tooltip),
        xAxis: { type: "value", show: false },
        yAxis: { type: "category", data: rows.map((r) => r.key), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: C.ink, fontWeight: 600, width: narrow() ? 94 : 128, overflow: "truncate", fontSize: narrow() ? 11 : 12 } },
        series: [{ type: "bar", data: rows.map((r, i) => ({ value: r.value, itemStyle: { color: i === rows.length - 1 ? C.ink : C.bar } })), barWidth: 14, itemStyle: { borderRadius: [0, 7, 7, 0] },
          label: { show: true, position: "right", distance: 8, fontSize: 12, fontFamily: FONT,
            formatter: (p) => { const r = rows[p.dataIndex]; const m = showMom && r.mom_label ? ((r.mom ?? 0) >= 0 ? `  {up|▲ ${r.mom_label}}` : `  {dn|▼ ${r.mom_label}}`) : ""; return `{v|${r.label}}${m}`; },
            rich: { v: { color: C.ink, fontWeight: 600, fontFamily: FONT }, up: { color: C.ink, fontWeight: 700, fontFamily: FONT }, dn: { color: C.redInk, fontWeight: 700, fontFamily: FONT } } } }],
      });
    }
    const brandChart = mount("chart-brand");
    if (brandChart) {
      const rows = D.brand.slice().reverse();
      brandChart.setOption(barOption(rows, true));
      brandChart.on("click", (p) => { const r = rows[p.dataIndex]; if (r) window.location.href = filterUrl({ brand: r.key }); });
    }

    // Region x brand flow (board A): light ribbons, the focused region highlighted.
    const flowChart = mount("chart-flow");
    const pick = document.getElementById("flow-focus");
    const badge = document.getElementById("flow-badge");
    if (flowChart && D.heat.cells.length) {
      const H = D.heat;
      const regionRow = Object.fromEntries(D.region.map((r) => [r.key, r]));
      const draw = (focus) => {
        const fr = regionRow[focus];
        const hi = fr && (fr.mom ?? 0) < 0 ? C.red : C.ink;
        const nodes = H.regions.map((r) => ({ name: r, itemStyle: { color: r === focus ? hi : C.ink } }))
          .concat(H.brands.map((b) => ({ name: b, itemStyle: { color: C.node } })));
        const links = H.cells.map((c) => ({ source: c.region, target: c.brand, value: c.value,
          lineStyle: { color: c.region === focus ? hi : C.ribbon, opacity: c.region === focus ? 0.5 : 0.75 } }));
        flowChart.setOption(Object.assign({}, base, {
          tooltip: Object.assign({ trigger: "item", formatter: (p) => p.dataType === "edge" ? `${p.data.source} ke ${p.data.target}\n${rp(p.data.value)}` : `${p.name}\n${D.region_totals[p.name] || D.brand_totals[p.name] || ""}` }, tooltip),
          series: [{ type: "sankey", left: 4, right: narrow() ? 112 : 190, top: 8, bottom: 8, nodeWidth: 10, nodeGap: narrow() ? 8 : 12, layoutIterations: 0,
            data: nodes, links, lineStyle: { curveness: 0.5 }, emphasis: { focus: "adjacency" },
            label: { fontFamily: FONT, fontSize: narrow() ? 11 : 12, color: C.ink,
              formatter: (p) => { const v = D.region_totals[p.name] || D.brand_totals[p.name]; const b = p.name === focus ? "f" : "n"; return narrow() ? `{${b}|${p.name}}` : `{${b}|${p.name}}  {v|${v}}`; },
              rich: { n: { fontWeight: 600, fontFamily: FONT }, f: { fontWeight: 800, fontFamily: FONT }, v: { color: C.muted, fontSize: 11, fontFamily: FONT } } } }],
        }), true);
        if (badge && fr) {
          badge.textContent = fr.mom === null ? fr.key : `${fr.key} ${arrow(fr.mom)} ${fr.mom_label} ${D.months.join(" ke ")}`;
          badge.classList.toggle("is-down", (fr.mom ?? 0) < 0);
        }
        if (pick && pick.value !== focus) pick.value = focus;
        document.querySelectorAll(".rl-row").forEach((a) => a.classList.toggle("is-focus", a.querySelector(".rl-name")?.textContent === focus));
      };
      let focus = D.focus;
      draw(focus);
      flowChart.on("click", (p) => { if (p.dataType === "node" && regionRow[p.name]) { focus = p.name; draw(focus); } });
      if (pick) pick.addEventListener("change", () => { focus = pick.value; draw(focus); });
    }
    let t;
    window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => charts.forEach((c) => c.resize()), 120); });
  }
  // Charts measure label text, so wait for the vendored font.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(initCharts, initCharts); else initCharts();

  // -- filters and rail ------------------------------------------------------
  document.querySelectorAll(".filt select").forEach((s) => s.addEventListener("change", () => s.form.submit()));
  document.querySelectorAll(".rail-btn[data-spy]").forEach((a) => a.addEventListener("click", () => {
    document.querySelectorAll(".rail-btn").forEach((b) => b.classList.toggle("is-on", b === a));
  }));

  // -- drawers --------------------------------------------------------------
  document.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", (ev) => {
    ev.preventDefault();
    const d = document.getElementById(b.dataset.open);
    if (d && d.showModal) { d.showModal(); const f = d.querySelector("input, button.close"); if (f) f.focus(); }
  }));
  document.querySelectorAll("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  document.querySelectorAll("dialog").forEach((d) => d.addEventListener("click", (ev) => { if (ev.target === d) d.close(); }));
  // Shortcut buttons in the Telegram preview scroll within the app; move focus to the target too.
  document.querySelectorAll('.kb[href^="#"]').forEach((a) => a.addEventListener("click", () => {
    const target = document.querySelector(a.getAttribute("href"));
    if (target) { target.setAttribute("tabindex", "-1"); setTimeout(() => target.focus({ preventScroll: true }), 300); }
  }));

  // -- copy and send ----------------------------------------------------------
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

  async function copyText(text, statusEl, okMsg, sourceEl) {
    try {
      await navigator.clipboard.writeText(text);
      if (statusEl) statusEl.textContent = okMsg;
    } catch (_) {
      if (sourceEl) {
        const range = document.createRange();
        range.selectNodeContents(sourceEl);
        const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
        if (statusEl) statusEl.textContent = "Teks sudah dipilih, tekan Ctrl+C atau Cmd+C.";
      } else if (statusEl) {
        statusEl.textContent = "Browser menolak akses clipboard. Teks tugas: " + text;
      }
    }
  }
  document.querySelectorAll("[data-copy-target]").forEach((b) => b.addEventListener("click", () => {
    const src = document.getElementById(b.dataset.copyTarget);
    if (src) copyText(src.textContent, document.getElementById(b.dataset.status || "tg-status"), "Ringkasan tersalin. Tempel di grup Telegram.", src);
  }));
  document.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", () => {
    copyText(b.dataset.copy, document.getElementById(b.dataset.status), "Tugas tersalin. Tempel di chat salesman.", null);
  }));
  document.querySelectorAll(".js-tg-send").forEach((sendBtn) => sendBtn.addEventListener("click", async () => {
    const status = document.getElementById("tg-status");
    sendBtn.disabled = true;
    status.textContent = "Mengirim...";
    const r = await postJSON("/api/telegram/send", { period: sendBtn.dataset.period });
    status.textContent = r.data.message || r.data.error || "Selesai.";
    sendBtn.disabled = false;
  }));

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
