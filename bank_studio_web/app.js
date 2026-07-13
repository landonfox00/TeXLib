/* Bank Studio -- Library Desk client.  Talks to the stdlib server: browse the
   parsed bank, render the selected problem with the real engine (SVG), and
   add/remove/reorder problems, which the server writes into the exam .tex. */
"use strict";

const S = {
  problems: [], byId: {}, exam: { entries: [] }, sources: [],
  renderAvailable: false,
  selected: null, insertMode: "id", showSol: true, view: "rendered",
  filters: { q: "", topic: "all", type: "all" },
  renderCache: {},
};

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const letter = (i) => String.fromCharCode(65 + i);

async function api(path, opts) {
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }
  if (!res.ok) throw new Error(res.statusText);
  return res.text();
}

/* ---------- boot ---------- */
async function boot() {
  try {
    const data = await api("/api/bank");
    S.problems = data.problems;
    S.byId = Object.fromEntries(data.problems.map((p) => [p.id, p]));
    S.sources = data.sources;
    S.renderAvailable = data.render_available;
    S.exam = data.exam;
    if (S.problems.length) S.selected = S.problems[0].id;
    $("#exam-name").textContent = data.exam.name;
    const badge = $("#render-badge");
    if (S.renderAvailable) { badge.className = "render-badge ok"; badge.textContent = "engine ready"; }
    else { badge.className = "render-badge off"; badge.textContent = "source-only (no lualatex)"; }
    renderFilters(); renderRows(); renderPreview(); renderTray();
  } catch (e) {
    $("#preview").innerHTML = `<div class="empty">Failed to load bank:<br>${esc(e.message)}</div>`;
  }
}

/* ---------- filtering ---------- */
function topics() {
  const t = [];
  S.problems.forEach((p) => { if (p.topic && !t.includes(p.topic)) t.push(p.topic); });
  return t;
}
function match(p) {
  const f = S.filters;
  if (f.topic !== "all" && p.topic !== f.topic) return false;
  if (f.type !== "all" && p.type !== f.type) return false;
  if (f.q) {
    const hay = `${p.id} ${p.topic} ${p.section} ${p.preview}`.toLowerCase();
    if (!hay.includes(f.q.toLowerCase())) return false;
  }
  return true;
}
function inExam(id) {
  return S.exam.entries.some((e) => e.arg === id || e.arg === "topic=" + (S.byId[id] || {}).topic);
}

/* ---------- left rail ---------- */
function renderFilters() {
  const f = S.filters;
  let h = `<button class="fchip" data-topic="all" aria-pressed="${f.topic === "all"}">All topics</button>`;
  topics().forEach((t) => { h += `<button class="fchip" data-topic="${esc(t)}" aria-pressed="${f.topic === t}">${esc(t)}</button>`; });
  h += `<button class="fchip" data-type="fr" aria-pressed="${f.type === "fr"}">FR</button>`;
  h += `<button class="fchip" data-type="mc" aria-pressed="${f.type === "mc"}">MC</button>`;
  $("#filters").innerHTML = h;
}
function renderRows() {
  const rows = S.problems.filter(match);
  $("#count").textContent = `${rows.length} of ${S.problems.length} problems`;
  $("#rows").innerHTML = rows.map((p) => `
    <div class="prow" data-pid="${esc(p.id)}" aria-current="${S.selected === p.id}" tabindex="0" role="button">
      <div class="r1"><span class="pid">${esc(p.id)}</span></div>
      <div class="r2">
        ${typeChip(p)}
        ${p.section ? `<span class="chip sec">&sect;${esc(p.section)}</span>` : ""}
        ${p.points != null ? `<span class="chip pts">${p.points} pts</span>` : ""}
        ${p.duplicate ? `<span class="chip dup">dup id</span>` : ""}
        ${inExam(p.id) ? `<span class="in-exam-dot">&#10003; in exam</span>` : ""}
      </div>
    </div>`).join("") || `<div class="empty">No problems match.</div>`;
}
function typeChip(p) { return p.type === "mc" ? `<span class="chip mc">MC</span>` : `<span class="chip fr">FR</span>`; }

/* ---------- center preview ---------- */
function tintTeX(src) {
  let s = esc(src);
  s = s.replace(/(%[^\n]*)/g, '<span class="cmt">$1</span>');
  s = s.replace(/(\\[a-zA-Z@]+)/g, '<span class="kw">$1</span>');
  s = s.replace(/(\[[^\]\n]*\])/g, '<span class="opt">$1</span>');
  s = s.replace(/(\{[^{}\n]*\})/g, '<span class="arg">$1</span>');
  return s;
}
function renderPreview() {
  const p = S.byId[S.selected];
  const box = $("#preview");
  if (!p) { box.innerHTML = `<div class="empty">Select a problem.</div>`; return; }
  const here = inExam(p.id);
  box.innerHTML = `
    <div class="pv-head">${typeChip(p)}<span class="pid" style="font-size:15px">${esc(p.id)}</span>
      ${p.duplicate ? `<span class="chip dup">duplicate id in bank</span>` : ""}</div>
    <div class="pv-meta">
      ${p.section ? `<span class="chip sec">&sect;${esc(p.section)}</span>` : ""}
      ${p.topic ? `<span>topic: <b>${esc(p.topic)}</b></span>` : ""}
      ${p.source ? `<span>source: ${esc(p.source)}</span>` : ""}
      ${p.points != null ? `<span class="chip pts">${p.points} pts</span>` : ""}
    </div>
    <div class="pv-toolbar">
      <div class="seg" role="group" aria-label="View">
        <button data-view="rendered" aria-pressed="${S.view === "rendered"}">Rendered</button>
        <button data-view="source" aria-pressed="${S.view === "source"}">LaTeX source</button>
      </div>
      <label class="btn sm ghost" style="cursor:pointer">
        <input type="checkbox" id="sol-toggle" ${S.showSol ? "checked" : ""}> show solution</label>
    </div>
    <div id="render-slot"></div>
    <div class="pv-actions">
      ${here
      ? `<button class="btn" data-act="remove-sel"><span>&#10003;</span> In exam &mdash; remove</button>`
      : `<button class="btn primary" data-act="add"><span>&#43;</span> Add to exam</button>`}
      <button class="btn ghost" data-act="copy-line">Copy <code>\\problem{${esc(argFor(p))}}</code></button>
    </div>`;
  renderSlot();
}
function renderSlot() {
  const p = S.byId[S.selected];
  const slot = $("#render-slot");
  if (!slot) return;
  if (S.view === "source") {
    slot.className = "src";
    slot.innerHTML = `<pre>${tintTeX(p.raw)}</pre>`;
    return;
  }
  slot.className = "";
  if (!S.renderAvailable) {
    slot.innerHTML = `<div class="render-box center">No engine on PATH &mdash; switch to LaTeX source.</div>`;
    return;
  }
  const key = `${p.id}|${S.showSol ? 1 : 0}`;
  if (S.renderCache[key]) { slot.innerHTML = `<div class="render-box">${S.renderCache[key]}</div>`; return; }
  slot.innerHTML = `<div class="render-box center"><span class="spinner"></span>rendering with lualatex&hellip;</div>`;
  const want = p.id;
  fetch(`/api/render/${encodeURIComponent(p.id)}?sol=${S.showSol ? 1 : 0}`)
    .then(async (res) => {
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.error || res.statusText); }
      return res.text();
    })
    .then((svg) => {
      svg = svg.replace(/<\?xml[^>]*\?>/, "").replace(/<!DOCTYPE[^>]*>/i, "");
      S.renderCache[key] = svg;
      if (S.selected === want && S.view === "rendered") renderSlot();
    })
    .catch((e) => {
      if (S.selected === want) slot.innerHTML =
        `<div class="render-box center">Render failed: ${esc(e.message)}<br>Try the LaTeX source view.</div>`;
    });
}

/* ---------- right tray ---------- */
function argFor(p) { return (S.insertMode === "filter" && p.topic) ? "topic=" + p.topic : p.id; }
function generateTeX() {
  const fr = S.exam.entries.filter((e) => e.env === "fr");
  const mc = S.exam.entries.filter((e) => e.env === "mc");
  const blk = (name, arr) => `\\begin{${name}}\n${arr.map((e) => "\t\\problem{" + e.arg + "}").join("\n")}\n\\end{${name}}`;
  const out = [];
  if (fr.length) out.push(blk("problems", fr));
  if (mc.length) out.push(blk("mcproblems", mc));
  return out.join("\n\n") || "% add problems to build the exam body";
}
function knownPoints() {
  let n = 0;
  S.exam.entries.forEach((e) => { const p = S.byId[e.arg]; if (p && p.points != null) n += p.points; });
  return n;
}
function renderTray() {
  const el = $("#examlist");
  const entries = S.exam.entries;
  if (!entries.length) {
    el.innerHTML = `<div class="empty">Empty.<br>Add problems from the middle pane.</div>`;
  } else {
    const group = (label, kind) => {
      const arr = entries.filter((e) => e.env === kind);
      if (!arr.length) return "";
      return `<div class="egroup-lbl">${label}</div>` + arr.map((e) => `
        <div class="eitem">
          <span class="earg">\\problem{${esc(e.arg)}}</span>
          ${e.is_filter ? `<span class="filter-tag">filter</span>` : ""}
          <span class="mv">
            <button data-act="move" data-idx="${e.index}" data-dir="-1" title="Up">&#9650;</button>
            <button data-act="move" data-idx="${e.index}" data-dir="1" title="Down">&#9660;</button>
          </span>
          <button class="del" data-act="remove" data-idx="${e.index}" title="Remove">&times;</button>
        </div>`).join("");
    };
    el.innerHTML = group("Part I &middot; Free response \\begin{problems}", "fr")
      + group("Part II &middot; Multiple choice \\begin{mcproblems}", "mc");
  }
  $("#tray-n").textContent = `${entries.length} q`;
  $("#tray-total").innerHTML = `${entries.length} &middot; ${knownPoints()}`;
}

/* ---------- exam mutations (server writes the file) ---------- */
async function refreshExam(data) { S.exam = data; renderTray(); renderRows(); renderPreview(); }
async function addSelected() {
  const p = S.byId[S.selected]; if (!p) return;
  try { await refreshExam(await api("/api/exam/add", post({ id: p.id, mode: S.insertMode }))); toast(`Added ${p.id}`); }
  catch (e) { toast(e.message, true); }
}
async function removeIdx(idx) {
  try { await refreshExam(await api("/api/exam/remove", post({ index: idx }))); }
  catch (e) { toast(e.message, true); }
}
async function moveIdx(idx, dir) {
  try { await refreshExam(await api("/api/exam/reorder", post({ index: idx, dir }))); }
  catch (e) { toast(e.message, true); }
}
async function removeSelected() {
  const p = S.byId[S.selected];
  const e = S.exam.entries.find((x) => x.arg === p.id || x.arg === "topic=" + p.topic);
  if (e) await removeIdx(e.index);
}
function post(obj) { return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) }; }

/* ---------- misc ---------- */
let toastT;
function toast(msg, err) {
  const t = $("#toast");
  t.innerHTML = err ? esc(msg) : `<span class="ok">&#10003;</span> ${esc(msg)}`;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toastT); toastT = setTimeout(() => { t.className = "toast"; }, 2000);
}
function copyText(txt, msg) {
  (navigator.clipboard?.writeText(txt) || Promise.reject()).then(() => toast(msg), () => {
    const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta);
    ta.select(); try { document.execCommand("copy"); } catch (e) {} ta.remove(); toast(msg);
  });
}

/* ---------- events ---------- */
document.addEventListener("click", (ev) => {
  const el = ev.target.closest("[data-pid],[data-topic],[data-type],[data-view],[data-mode],[data-act]");
  if (!el) return;
  if (el.dataset.pid != null) { S.selected = el.dataset.pid; renderRows(); renderPreview(); }
  else if (el.dataset.topic != null) { S.filters.topic = el.dataset.topic; renderFilters(); renderRows(); }
  else if (el.dataset.type != null) { S.filters.type = S.filters.type === el.dataset.type ? "all" : el.dataset.type; renderFilters(); renderRows(); }
  else if (el.dataset.view != null) { S.view = el.dataset.view; renderPreview(); }
  else if (el.dataset.mode != null) {
    S.insertMode = el.dataset.mode;
    $$('[data-mode]').forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === S.insertMode));
    renderPreview();
  } else if (el.dataset.act) {
    const a = el.dataset.act;
    if (a === "add") addSelected();
    else if (a === "remove-sel") removeSelected();
    else if (a === "remove") removeIdx(+el.dataset.idx);
    else if (a === "move") moveIdx(+el.dataset.idx, +el.dataset.dir);
    else if (a === "copy-line") copyText(`\\problem{${argFor(S.byId[S.selected])}}`, "Copied \\problem line");
  }
});
document.addEventListener("change", (ev) => {
  if (ev.target.id === "sol-toggle") { S.showSol = ev.target.checked; renderSlot(); }
});
document.addEventListener("keydown", (ev) => {
  if ((ev.key === "Enter" || ev.key === " ") && ev.target.classList?.contains("prow")) {
    S.selected = ev.target.dataset.pid; renderRows(); renderPreview(); ev.preventDefault();
  }
});
$("#search").addEventListener("input", (e) => { S.filters.q = e.target.value; renderRows(); });
$("#copy-btn").addEventListener("click", () => copyText(generateTeX(), "Copied exam body"));
$("#theme-btn").addEventListener("click", () => {
  const root = document.documentElement;
  let cur = root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light");
  root.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
});

boot();
