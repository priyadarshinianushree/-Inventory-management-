/* UI helpers: escaping, formatting, toast, modal, forms, pagination. */
const $ = (sel, root = document) => root.querySelector(sel);

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const fmt = {
  money: (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 }),
  num: (n) => Number(n || 0).toLocaleString("en-IN"),
  // the database stores UTC "YYYY-MM-DD HH:MM:SS"
  parse: (s) => new Date(String(s).replace(" ", "T") + "Z"),
  date: (s) => (s ? fmt.parse(s).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "-"),
  datetime: (s) => (s ? fmt.parse(s).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "-"),
};

function badge(text, tone = "gray") {
  return `<span class="badge b-${tone}">${esc(text)}</span>`;
}

const debounce = (fn, ms = 300) => {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};

/* ---------------------------------------------------------------- toast */
function toast(message, type = "success") {
  const el = document.createElement("div");
  el.className = "toast " + (type === "error" ? "error" : "");
  el.textContent = message;
  $("#toast-root").appendChild(el);
  setTimeout(() => el.remove(), type === "error" ? 6000 : 3500);
}

/* ---------------------------------------------------------------- modal */
function openModal({ title, html, size = "md" }) {
  const wrap = document.createElement("div");
  wrap.className = "modal-backdrop";
  wrap.innerHTML = `<div class="modal ${size}" role="dialog" aria-modal="true">
      <div class="modal-head"><h3>${esc(title)}</h3><button class="icon-btn" data-close aria-label="Close">&times;</button></div>
      <div class="modal-body">${html}</div></div>`;
  $("#modal-root").appendChild(wrap);
  const onKey = (e) => { if (e.key === "Escape") close(); };
  function close() { wrap.remove(); document.removeEventListener("keydown", onKey); }
  document.addEventListener("keydown", onKey);
  wrap.addEventListener("mousedown", (e) => { if (e.target === wrap) close(); });
  wrap.querySelectorAll("[data-close]").forEach((b) => (b.onclick = close));
  return { close, body: $(".modal-body", wrap), el: wrap };
}

function confirmDialog({ title = "Are you sure?", message, confirmText = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const m = openModal({
      title, size: "sm",
      html: `<p style="margin:0 0 4px">${message}</p>
        <div class="modal-actions"><button class="btn" data-close>Cancel</button>
        <button class="btn ${danger ? "danger" : "primary"}" id="cd-ok">${esc(confirmText)}</button></div>`,
    });
    let answered = false;
    $("#cd-ok", m.body).onclick = () => { answered = true; m.close(); resolve(true); };
    new MutationObserver((_r, obs) => { if (!document.body.contains(m.el)) { obs.disconnect(); if (!answered) resolve(false); } })
      .observe($("#modal-root"), { childList: true });
  });
}

/* ---------------------------------------------------------------- forms */
function fieldHtml(f, val) {
  const id = "f_" + f.name;
  const attrs = [f.required ? "required" : "", f.readonly ? "readonly" : "", f.min !== undefined ? `min="${f.min}"` : "", f.max !== undefined ? `max="${f.max}"` : "",
    f.step !== undefined ? `step="${f.step}"` : "", f.maxlength ? `maxlength="${f.maxlength}"` : "",
    f.minlength ? `minlength="${f.minlength}"` : "", f.pattern ? `pattern="${f.pattern}"` : "",
    f.placeholder ? `placeholder="${esc(f.placeholder)}"` : "", f.autocomplete ? `autocomplete="${f.autocomplete}"` : ""].join(" ");
  let input;
  if (f.type === "select") {
    input = `<select id="${id}" name="${f.name}" ${f.required ? "required" : ""}>${(f.options || []).map((o) =>
      `<option value="${esc(o.value)}" ${String(o.value) === String(val ?? "") ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
  } else if (f.type === "textarea") {
    input = `<textarea id="${id}" name="${f.name}" rows="${f.rows || 3}" ${attrs}>${esc(val ?? "")}</textarea>`;
  } else if (f.type === "checkbox") {
    input = `<label class="check"><input type="checkbox" id="${id}" name="${f.name}" ${val ? "checked" : ""}> ${esc(f.label)}</label>`;
  } else {
    input = `<input id="${id}" name="${f.name}" type="${f.type || "text"}" value="${esc(val ?? "")}" ${attrs}>`;
  }
  const label = f.type === "checkbox" ? "" : `<label for="${id}">${esc(f.label)}${f.required ? ' <span class="req">*</span>' : ""}</label>`;
  return `<div class="field ${f.full ? "full" : ""}" data-field="${f.name}">${label}${input}${f.help ? `<small>${esc(f.help)}</small>` : ""}<div class="err"></div></div>`;
}

function readForm(form, fields, includeHidden = false) {
  const out = {};
  fields.forEach((f) => {
    const wrap = form.querySelector(`[data-field="${f.name}"]`);
    if (!includeHidden && wrap && wrap.hidden) return;
    const el = form.elements[f.name];
    if (!el) return;
    out[f.name] = f.type === "checkbox" ? el.checked : el.value;
  });
  return out;
}

function setFieldError(form, name, msg) {
  const wrap = form.querySelector(`[data-field="${name}"]`);
  if (!wrap) return false;
  wrap.classList.toggle("invalid", !!msg);
  $(".err", wrap).textContent = msg || "";
  return true;
}
function clearErrors(form) {
  form.querySelectorAll(".field").forEach((w) => { w.classList.remove("invalid"); $(".err", w).textContent = ""; });
  const fe = $(".form-error", form);
  if (fe) fe.hidden = true;
}
/** Browser-side validation; shows messages under each field. */
function validateForm(form) {
  let first = null;
  form.querySelectorAll("input, select, textarea").forEach((el) => {
    if (el.disabled || el.type === "checkbox") return;
    if (!el.checkValidity()) {
      let msg = el.validationMessage;
      if (el.validity.valueMissing) msg = "This field is required";
      else if (el.validity.patternMismatch) msg = el.title || "Invalid format";
      setFieldError(form, el.name, msg);
      first = first || el;
    }
  });
  if (first) first.focus();
  return !first;
}
/** Show server-side field errors; returns true if at least one landed on a field. */
function showErrors(form, details) {
  let any = false;
  Object.entries(details || {}).forEach(([k, v]) => { if (setFieldError(form, k, v)) any = true; });
  return any;
}

async function openFormModal({ title, fields, values = {}, submitLabel = "Save", onSubmit, size }) {
  const resolved = await Promise.all(fields.map(async (f) => ({ ...f, options: typeof f.options === "function" ? await f.options() : f.options })));
  const html = `<form novalidate><div class="form-grid">${resolved.map((f) => fieldHtml(f, values[f.name])).join("")}</div>
    <div class="form-error" hidden></div>
    <div class="modal-actions"><button type="button" class="btn" data-close>Cancel</button>
    <button type="submit" class="btn primary">${esc(submitLabel)}</button></div></form>`;
  const m = openModal({ title, html, size });
  const form = $("form", m.body);

  const refresh = () => {
    const cur = readForm(form, resolved, true);
    resolved.forEach((f) => {
      if (f.showIf) {
        const wrap = form.querySelector(`[data-field="${f.name}"]`);
        const show = !!f.showIf(cur);
        wrap.hidden = !show;
        wrap.querySelectorAll("input,select,textarea").forEach((i) => (i.disabled = !show));
      }
      if (f.labelFn) {
        const lab = form.querySelector(`[data-field="${f.name}"] label`);
        if (lab) lab.innerHTML = esc(f.labelFn(cur)) + (f.required ? ' <span class="req">*</span>' : "");
      }
    });
  };
  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
  refresh();

  const first = form.querySelector("input:not([type=checkbox]):not(:disabled), select:not(:disabled)");
  if (first) first.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors(form);
    if (!validateForm(form)) return;
    const btn = $("button[type=submit]", form);
    btn.disabled = true;
    try {
      await onSubmit(readForm(form, resolved));
      m.close();
    } catch (err) {
      showErrors(form, err.details);   // highlight the fields the server complained about
      const fe = $(".form-error", form);
      fe.textContent = err.message;
      fe.hidden = false;
    } finally {
      btn.disabled = false;
    }
  });
  return m;
}

/** Ask for a short text (e.g. rejection reason). Resolves to the text, or null if cancelled. */
function promptDialog({ title, label, required = true, submitLabel = "Submit" }) {
  return new Promise((resolve) => {
    let done = false;
    openFormModal({
      title, size: "sm", submitLabel,
      fields: [{ name: "text", label, type: "textarea", required, full: true, maxlength: 300 }],
      onSubmit: async (v) => { done = true; resolve(v.text.trim()); },
    }).then((m) => {
      new MutationObserver((_r, obs) => { if (!document.body.contains(m.el)) { obs.disconnect(); if (!done) resolve(null); } })
        .observe($("#modal-root"), { childList: true });
    });
  });
}

/* ---------------------------------------------------------------- pagination */
function renderPager(el, { page, pages, total, per_page }, onPage) {
  if (!total) { el.innerHTML = ""; return; }
  const from = (page - 1) * per_page + 1, to = Math.min(page * per_page, total);
  const nums = [];
  for (let p = Math.max(1, page - 2); p <= Math.min(pages, page + 2); p++) nums.push(p);
  el.innerHTML = `<span>Showing ${fmt.num(from)}-${fmt.num(to)} of ${fmt.num(total)}</span>
    <div class="pages"><button data-p="${page - 1}" ${page <= 1 ? "disabled" : ""}>&lsaquo;</button>
    ${nums.map((p) => `<button data-p="${p}" class="${p === page ? "cur" : ""}">${p}</button>`).join("")}
    <button data-p="${page + 1}" ${page >= pages ? "disabled" : ""}>&rsaquo;</button></div>`;
  el.querySelectorAll("button[data-p]").forEach((b) => (b.onclick = () => onPage(Number(b.dataset.p))));
}

function downloadCsv(filename, header, rows) {
  const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
