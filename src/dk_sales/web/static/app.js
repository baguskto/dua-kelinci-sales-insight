"use strict";
// All server data is inserted with textContent, never innerHTML, so file values cannot become markup.
(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

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
        await navigator.clipboard.writeText(t.value);
        status.textContent = "Tersalin. Tempel di Telegram.";
      } catch (_) {
        t.select();
        status.textContent = "Teks sudah dipilih, tekan Ctrl+C / Cmd+C.";
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
      const t = el("table", "tbl compact");
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
    const meta = [];
    meta.push(d.mode_label);
    if (d.sources && d.sources.length) meta.push("Sumber: " + d.sources.map((s) => s.label).join("; "));
    if (d.guard) meta.push(d.guard.ok ? "Cek angka: lolos" : "Cek angka: ada angka tak tercocokkan");
    if (d.fallback_reason) meta.push("Alasan fallback: " + d.fallback_reason);
    aEl.append(el("div", "meta", meta.join(" | ")));
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

  const up = document.getElementById("upload-form");
  if (up) {
    up.addEventListener("submit", () => {
      const b = up.querySelector("button[type=submit]");
      b.disabled = true;
      b.textContent = "Memeriksa file...";
    });
  }
})();
