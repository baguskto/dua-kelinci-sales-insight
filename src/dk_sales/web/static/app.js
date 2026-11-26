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
  document.querySelectorAll(".filt select").forEach((s) => s.addEventListener("change", () => s.form.submit()));

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
    copyText(b.dataset.copy, document.getElementById(b.dataset.status), "Tugas tersalin.", null);
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
