"use strict";
// All server data is inserted with textContent, never innerHTML, so file values cannot become markup.
// Charts are SVG rendered on the server, so the page reads the same without this script.
(function () {
  document.documentElement.classList.add("js");
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  // -- filters ---------------------------------------------------------------
  // Each option carries the URL of its view, so the same code works on the server and on the static export.
  document.querySelectorAll(".filt select").forEach((s) => s.addEventListener("change", () => {
    const href = s.selectedOptions[0] && s.selectedOptions[0].dataset.href;
    if (href) window.location.href = href; else s.form.submit();
  }));

  // -- drawers --------------------------------------------------------------
  document.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", (ev) => {
    ev.preventDefault();
    const d = document.getElementById(b.dataset.open);
    if (d && d.showModal) { d.showModal(); const f = d.querySelector("input, button.close"); if (f) f.focus(); }
  }));
  document.querySelectorAll("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  document.querySelectorAll("dialog").forEach((d) => d.addEventListener("click", (ev) => { if (ev.target === d) d.close(); }));

  // -- copy and send ----------------------------------------------------------
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Accept": "application/json" },
      body: JSON.stringify(body || {}),
      credentials: "same-origin",
    });
    let data = {};
    try { data = await r.json(); } catch (_) { data = { error: "Could not read the server response." }; }
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
        if (statusEl) statusEl.textContent = "Text selected: press Ctrl+C or Cmd+C.";
      } else if (statusEl) {
        statusEl.textContent = "The browser blocked the clipboard. Task text: " + text;
      }
    }
  }
  document.querySelectorAll("[data-copy-target]").forEach((b) => b.addEventListener("click", () => {
    const src = document.getElementById(b.dataset.copyTarget);
    if (src) copyText(src.textContent, document.getElementById(b.dataset.status || "tg-status"), "Summary copied. Paste it into the Telegram group.", src);
  }));
  document.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", () => {
    copyText(b.dataset.copy, document.getElementById(b.dataset.status), "Task copied.", null);
  }));
  document.querySelectorAll(".js-tg-send").forEach((sendBtn) => sendBtn.addEventListener("click", async () => {
    const status = document.getElementById("tg-status");
    sendBtn.disabled = true;
    status.textContent = "Sending...";
    const r = await postJSON("/api/telegram/send", { period: sendBtn.dataset.period });
    status.textContent = r.data.message || r.data.error || "Done.";
    sendBtn.disabled = false;
  }));

  // -- chat -------------------------------------------------------------------
  const form = document.getElementById("chat-form");
  const log = document.getElementById("chat-log");
  // Static export: no server, so the example questions read answers the real engine gave at build time.
  const savedUrl = document.getElementById("chat-drawer")?.dataset.answers;
  let saved = null;
  async function savedAnswer(q) {
    try {
      if (!saved) {
        const r = await fetch(savedUrl);
        if (!r.ok) throw new Error(String(r.status));
        saved = await r.json();
      }
    } catch (_) {
      return { ok: false, status: 0, data: { error: "Could not load the saved answers. Reload the page and try again." } };
    }
    const d = saved[q];
    return d ? { ok: true, status: 200, data: d } : { ok: false, status: 404, data: { error: "No saved answer for this question. Free questions need the local app." } };
  }
  async function ask(q) {
    if (!q.trim()) return;
    const qEl = el("div", "msg q", q);
    log.prepend(qEl);
    const aEl = el("div", "msg a", "Working...");
    qEl.after(aEl);
    const r = savedUrl ? await savedAnswer(q) : await postJSON("/api/chat", { question: q });
    aEl.textContent = "";
    if (!r.ok) {
      aEl.classList.add("refusal");
      aEl.append(el("div", "", r.data.error || "The question could not be processed (" + r.status + ")."));
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
      det.append(el("summary", "", "Numbers used"));
      det.append(t);
      aEl.append(det);
    }
    const meta = el("div", "meta");
    meta.append(el("span", "srcchip", d.mode_label));
    (d.sources || []).forEach((s) => meta.append(el("span", "srcchip", "Source: " + s.label)));
    if (d.guard) meta.append(el("span", "srcchip", d.guard.ok ? "Number check: passed" : "Number check: failed"));
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
        btn.textContent = "Upload";
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch (_) { d = { ok: false, message: "Could not read the server response (" + xhr.status + ")." }; }
        if (xhr.status === 413) d = { ok: false, message: "File too large." };
        status.textContent = (d.ok ? "" : "File rejected. ") + (d.message || d.error || "");
        status.classList.toggle("alert-text", !d.ok);
        if (d.ok) setTimeout(() => { window.location.href = "/"; }, 900);
      });
      xhr.addEventListener("error", () => { btn.disabled = false; status.textContent = "Connection lost while uploading."; });
      btn.disabled = true;
      btn.textContent = "Checking file...";
      xhr.send(new FormData(up));
    });
  }
})();

// -- net sales line chart: tooltip at the highlight point, follows hover and arrow keys, Escape hides it
(function () {
  const svg = document.querySelector('svg[data-chart="net"]');
  const tip = document.getElementById("net-tip");
  const data = document.getElementById("net-points");
  if (!svg || !tip || !data) return;
  const pts = JSON.parse(data.textContent);
  const hl = svg.querySelector(".lc-hl");
  const ring = hl.querySelector("circle");
  const drop = hl.querySelector("line");
  const vb = svg.viewBox.baseVal;
  const bottom = Number(drop.getAttribute("y2"));
  const months = tip.querySelector("b").textContent.split(" ")[0];
  const prevMonth = tip.querySelector("span").textContent.split(" ")[0];
  let idx = pts.findIndex((p) => String(p.x) === hl.dataset.x && String(p.y) === hl.dataset.y);
  if (idx < 0) idx = pts.length - 1;

  function place(i) {
    idx = Math.max(0, Math.min(pts.length - 1, i));
    const p = pts[idx];
    ring.setAttribute("cx", p.x); ring.setAttribute("cy", p.y);
    drop.setAttribute("x1", p.x); drop.setAttribute("x2", p.x); drop.setAttribute("y1", p.y); drop.setAttribute("y2", bottom);
    tip.textContent = "";
    const b = document.createElement("b"); b.textContent = months + " " + p.day;
    const s = document.createElement("span"); s.textContent = prevMonth + " " + p.prev;
    tip.append(b, " " + p.curr, document.createElement("br"), s);
    const box = svg.getBoundingClientRect();
    const host = svg.parentElement.getBoundingClientRect();
    const x = box.left - host.left + (p.x / vb.width) * box.width;
    const y = box.top - host.top + (p.y / vb.height) * box.height;
    const w = tip.offsetWidth;
    tip.style.left = Math.max(0, Math.min(host.width - w, x - w - 8)) + "px";
    tip.style.top = Math.max(0, y - tip.offsetHeight - 6) + "px";
    tip.hidden = false;
  }
  svg.addEventListener("mousemove", (ev) => {
    const box = svg.getBoundingClientRect();
    const vx = ((ev.clientX - box.left) / box.width) * vb.width;
    let best = 0;
    pts.forEach((p, i) => { if (Math.abs(p.x - vx) < Math.abs(pts[best].x - vx)) best = i; });
    place(best);
  });
  svg.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowLeft") { ev.preventDefault(); place(idx - 1); }
    else if (ev.key === "ArrowRight") { ev.preventDefault(); place(idx + 1); }
    else if (ev.key === "Home") { ev.preventDefault(); place(0); }
    else if (ev.key === "End") { ev.preventDefault(); place(pts.length - 1); }
    else if (ev.key === "Escape") { tip.hidden = true; }
  });
  svg.addEventListener("focus", () => place(idx));
  window.addEventListener("resize", () => { if (!tip.hidden) place(idx); });
  place(idx);
})();
