/* Bank Studio client -- three views (Library Desk, Composer, Card Wall) over one
   shared exam state and one renderer.  Talks to the stdlib server: browse the
   parsed bank, render problems with the real engine (SVG), and add/remove/
   reorder problems, which the server writes into the exam .tex. */
"use strict";

const S = {
  problems: [], byId: {}, exam: { entries: [] }, sources: [], renderAvailable: false,
  tab: "desk", insertMode: "id",
  // desk
  selected: null, pvMode: "rendered", showSol: true, target: 100,
  filters: { q: "", topic: "all", type: "all", fresh: false },
  // composer
  compMode: "rendered", caret: "end", flashArg: null,
  // wall
  wallF: { q: "", topic: "all", type: "all" },
  // palette
  pal: { q: "", sel: 0, list: [] },
  renderCache: {},
};

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

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

/* ---------- shared rendering ---------- */
function fetchSVG(id, sol) {
  const key = `${id}|${sol ? 1 : 0}`;
  if (S.renderCache[key]) return Promise.resolve(S.renderCache[key]);
  return fetch(`/api/render/${encodeURIComponent(id)}?sol=${sol ? 1 : 0}`)
    .then(async (res) => {
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.error || res.statusText); }
      return res.text();
    })
    .then((svg) => {
      svg = svg.replace(/<\?xml[^>]*\?>/, "").replace(/<!DOCTYPE[^>]*>/i, "");
      S.renderCache[key] = svg;
      return svg;
    });
}
function injectSVG(el, id, sol) {
  if (!el) return;
  if (!S.renderAvailable) { el.className = "render-box center"; el.textContent = "No engine on PATH."; return; }
  const cached = S.renderCache[`${id}|${sol ? 1 : 0}`];
  if (cached) { el.className = "render-box"; el.innerHTML = cached; return; }
  el.className = "render-box center"; el.innerHTML = `<span class="spinner"></span>rendering&hellip;`;
  fetchSVG(id, sol).then((svg) => { el.className = "render-box"; el.innerHTML = svg; })
    .catch((e) => { el.className = "render-box center"; el.textContent = "render failed: " + e.message; });
}
function typeChip(p) { return p.type === "mc" ? `<span class="chip mc">MC</span>` : `<span class="chip fr">FR</span>`; }
function tintTeX(src) {
  let s = esc(src);
  s = s.replace(/(%[^\n]*)/g, '<span class="cmt">$1</span>');
  s = s.replace(/(\\[a-zA-Z@]+)/g, '<span class="kw">$1</span>');
  s = s.replace(/(\[[^\]\n]*\])/g, '<span class="opt">$1</span>');
  s = s.replace(/(\{[^{}\n]*\})/g, '<span class="arg">$1</span>');
  return s;
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
    renderDeskFilters(); renderRows(); renderPreview(); renderTray();
  } catch (e) {
    $("#preview").innerHTML = `<div class="empty">Failed to load bank:<br>${esc(e.message)}</div>`;
  }
}

/* ---------- filters shared ---------- */
function topics() { const t = []; S.problems.forEach((p) => { if (p.topic && !t.includes(p.topic)) t.push(p.topic); }); return t; }
function matchWith(p, f) {
  if (f.topic !== "all" && p.topic !== f.topic) return false;
  if (f.type !== "all" && p.type !== f.type) return false;
  if (f.fresh && (p.used_in || []).length) return false;
  if (f.q) { const hay = `${p.id} ${p.topic} ${p.section} ${p.preview}`.toLowerCase(); if (!hay.includes(f.q.toLowerCase())) return false; }
  return true;
}
function usedFiles(p) { return [...new Set((p.used_in || []).map((u) => u.file))]; }
function inExam(id) { const p = S.byId[id] || {}; return S.exam.entries.some((e) => e.arg === id || e.arg === "topic=" + p.topic); }
function argFor(p) { return (S.insertMode === "filter" && p.topic) ? "topic=" + p.topic : p.id; }

/* =======================================================================
   LIBRARY DESK
======================================================================= */
function renderDeskFilters() {
  const f = S.filters;
  let h = `<button class="fchip" data-topic="all" aria-pressed="${f.topic === "all"}">All topics</button>`;
  topics().forEach((t) => { h += `<button class="fchip" data-topic="${esc(t)}" aria-pressed="${f.topic === t}">${esc(t)}</button>`; });
  h += `<button class="fchip" data-type="fr" aria-pressed="${f.type === "fr"}">FR</button>`;
  h += `<button class="fchip" data-type="mc" aria-pressed="${f.type === "mc"}">MC</button>`;
  h += `<button class="fchip" data-fresh="1" aria-pressed="${!!f.fresh}" title="Only problems not used in your other assessments">&#10022; Fresh only</button>`;
  $("#filters").innerHTML = h;
}
function renderRows() {
  const rows = S.problems.filter((p) => matchWith(p, S.filters));
  $("#count").textContent = `${rows.length} of ${S.problems.length} problems`;
  $("#rows").innerHTML = rows.map((p) => {
    const uf = usedFiles(p);
    return `
    <div class="prow" data-pid="${esc(p.id)}" aria-current="${S.selected === p.id}" tabindex="0" role="button">
      <div class="r1"><span class="pid">${esc(p.id)}</span></div>
      <div class="r2">${typeChip(p)}
        ${p.section ? `<span class="chip sec">&sect;${esc(p.section)}</span>` : ""}
        ${p.points != null ? `<span class="chip pts">${p.points} pts</span>` : ""}
        ${p.duplicate ? `<span class="chip dup">dup id</span>` : ""}
        ${uf.length ? `<span class="chip used" title="Used in: ${esc(uf.join(", "))}">used &times;${uf.length}</span>` : ""}
        ${inExam(p.id) ? `<span class="in-exam-dot">&#10003; in exam</span>` : ""}</div>
    </div>`; }).join("") || `<div class="empty">No problems match.</div>`;
}
function renderPreview() {
  const p = S.byId[S.selected]; const box = $("#preview");
  if (!p) { box.innerHTML = `<div class="empty">Select a problem.</div>`; return; }
  const here = inExam(p.id);
  box.innerHTML = `
    <div class="pv-head">${typeChip(p)}<span class="pid" style="font-size:15px">${esc(p.id)}</span>
      ${p.duplicate ? `<span class="chip dup">duplicate id in bank</span>` : ""}</div>
    <div class="pv-meta">
      ${p.section ? `<span class="chip sec">&sect;${esc(p.section)}</span>` : ""}
      ${p.topic ? `<span>topic: <b>${esc(p.topic)}</b></span>` : ""}
      ${p.source ? `<span>source: ${esc(p.source)}</span>` : ""}
      ${p.points != null ? `<span class="chip pts">${p.points} pts</span>` : ""}</div>
    <div class="pv-used">${usedText(p)}</div>
    <div class="pv-toolbar">
      <div class="seg" role="group" aria-label="View">
        <button data-pv="rendered" aria-pressed="${S.pvMode === "rendered"}">Rendered</button>
        <button data-pv="source" aria-pressed="${S.pvMode === "source"}">LaTeX source</button></div>
      <label class="btn sm ghost" style="cursor:pointer"><input type="checkbox" id="sol-toggle" ${S.showSol ? "checked" : ""}> show solution</label>
    </div>
    <div id="render-slot"></div>
    <div class="pv-actions">
      ${here ? `<button class="btn" data-act="remove-sel"><span>&#10003;</span> In exam &mdash; remove</button>`
        : `<button class="btn primary" data-act="add-sel"><span>&#43;</span> Add to exam</button>`}
      <button class="btn ghost" data-act="copy-line">Copy <code>\\problem{${esc(argFor(p))}}</code></button>
    </div>`;
  renderDeskSlot();
}
function renderDeskSlot() {
  const p = S.byId[S.selected]; const slot = $("#render-slot"); if (!slot) return;
  if (S.pvMode === "source") { slot.className = "src"; slot.innerHTML = `<pre>${tintTeX(p.raw)}</pre>`; return; }
  slot.className = ""; slot.innerHTML = `<div class="render-box center"></div>`;
  injectSVG(slot.firstElementChild, p.id, S.showSol);
}
function renderTray() {
  const el = $("#examlist"); const entries = S.exam.entries;
  if (!entries.length) { el.innerHTML = `<div class="empty">Empty.<br>Add problems from the middle pane.</div>`; }
  else {
    const group = (label, kind) => {
      const arr = entries.filter((e) => e.env === kind); if (!arr.length) return "";
      return `<div class="egroup-lbl">${label}</div>` + arr.map((e) => `
        <div class="eitem"><span class="earg">\\problem{${esc(e.arg)}}</span>
          ${e.is_filter ? `<span class="filter-tag">filter</span>` : ""}
          <span class="mv"><button data-act="move" data-idx="${e.index}" data-dir="-1" title="Up">&#9650;</button>
            <button data-act="move" data-idx="${e.index}" data-dir="1" title="Down">&#9660;</button></span>
          <button class="del" data-act="remove" data-idx="${e.index}" title="Remove">&times;</button></div>`).join("");
    };
    el.innerHTML = group("Part I &middot; Free response \\begin{problems}", "fr")
      + group("Part II &middot; Multiple choice \\begin{mcproblems}", "mc");
  }
  $("#tray-n").textContent = `${entries.length} q`;
  $("#tray-total").innerHTML = `${entries.length} &middot; ${knownPoints()}`;
  renderCoverage();
}
function filterRep(arg) { const m = /topic=([^,]+)/.exec(arg); if (!m) return null; const t = m[1].trim(); return S.problems.find((p) => p.topic === t && p.points != null) || null; }
function knownPoints() {
  let n = 0;
  S.exam.entries.forEach((e) => {
    if (e.is_filter) { const c = filterRep(e.arg); if (c) n += c.points; }
    else { const p = S.byId[e.arg]; if (p && p.points != null) n += p.points; }
  });
  return n;
}
function pointsApprox() { return S.exam.entries.some((e) => e.is_filter && filterRep(e.arg)); }
function usedText(p) {
  const u = p.used_in || [];
  if (!u.length) return `<span class="fresh-tag">&#10022; Fresh &mdash; not used in your other assessments</span>`;
  return `Used in: ` + u.map((h) => `<span class="used-file">${esc(h.file)}<em>${h.by}</em></span>`).join(" ");
}

/* coverage / points-budget meter (desk tray) */
function renderCoverage() {
  const el = $("#coverage"); if (!el) return;
  const pts = knownPoints(), target = S.target;
  const pct = target > 0 ? Math.min(100, Math.round((pts / target) * 100)) : 0;
  const tps = topics();
  const examCount = (t) => S.exam.entries.filter((e) => e.arg === "topic=" + t || (S.byId[e.arg] && S.byId[e.arg].topic === t)).length;
  const availCount = (t) => S.problems.filter((p) => p.topic === t).length;
  const covered = tps.filter((t) => examCount(t) > 0).length;
  el.innerHTML = `
    <div class="cov-row"><span>Points budget${pointsApprox() ? ` <em class="approx" title="includes topic-filter estimates">approx</em>` : ""}</span>
      <span><b>${pts}</b> / <input class="cov-target" id="cov-target" type="number" min="0" step="5" value="${target}"></span></div>
    <div class="cov-bar"><i style="width:${pct}%" class="${pts > target ? "over" : ""}"></i></div>
    <div class="cov-row"><span>Topic coverage</span><span>${covered}/${tps.length} topics</span></div>
    <div class="cov-topics">${tps.map((t) => {
      const c = examCount(t), a = availCount(t);
      return `<span class="cov-chip ${c ? "" : "zero"}" title="${c} on exam of ${a} available">${esc(t)} <b>${c}</b>/${a}</span>`;
    }).join("")}</div>`;
}

/* =======================================================================
   COMPOSER
======================================================================= */
function renderComposer() {
  const body = $("#comp-body");
  if (S.compMode === "source") {
    body.className = "comp-body comp-source";
    body.innerHTML = `<pre>${tintTeX(composerSource())}</pre>`;
    return;
  }
  body.className = "comp-body";
  const entries = S.exam.entries;
  let h = `<div class="doc"><div class="doc-cover"><div class="t">${esc(S.exam.name)}</div>
    <div class="s">${S.problems.length} problems in bank &middot; ${entries.length} on exam</div></div>`;
  const fr = entries.filter((e) => e.env === "fr");
  const mc = entries.filter((e) => e.env === "mc");
  const section = (name, arr) => {
    if (!arr.length) return "";
    let s = `<div class="env-line">\\begin{${name}}</div>`;
    arr.forEach((e) => { s += qblock(e); });
    s += `<div class="env-line">\\end{${name}}</div>`;
    return s;
  };
  if (!entries.length) h += caretGap("end") + `<div class="empty">Empty document. Press <kbd>&#8984;K</kbd> to insert a problem.</div>`;
  else { h += section("problems", fr) + section("mcproblems", mc) + caretGap("end"); }
  h += `</div>`;
  body.innerHTML = h;
  // fill rendered blocks
  entries.forEach((e) => {
    if (e.is_filter) return;
    const p = S.byId[e.arg]; if (!p) return;
    injectSVG($(`#cb-${e.index} .render-box`), p.id, true);
  });
}
function qblock(e) {
  const flash = S.flashArg === e.arg ? " flash" : "";
  let inner;
  if (e.is_filter) {
    const n = S.problems.filter((p) => "topic=" + p.topic === e.arg).length;
    inner = `<div class="filter-block">filter <b>${esc(e.arg)}</b> &mdash; the engine picks one of ${n} at build time</div>`;
  } else if (!S.byId[e.arg]) {
    inner = `<div class="filter-block">unknown id <b>${esc(e.arg)}</b> &mdash; not in the loaded bank</div>`;
  } else {
    inner = `<div class="render-box center"></div>`;
  }
  return `<div class="qblock${flash}" id="cb-${e.index}">
    <span class="qnum">${e.index + 1}.</span>
    <div class="qtools">
      <button data-act="move" data-idx="${e.index}" data-dir="-1" title="Up">&#9650;</button>
      <button data-act="move" data-idx="${e.index}" data-dir="1" title="Down">&#9660;</button>
      <button data-act="remove" data-idx="${e.index}" title="Remove">&times;</button></div>
    ${inner}
    <div class="qsrc">\\problem{${esc(e.arg)}}</div></div>${caretGap(e.index)}`;
}
function caretGap(pos) {
  const here = String(S.caret) === String(pos);
  return `<div class="caret-gap${here ? " here" : ""}" data-caret="${pos}"></div>`;
}
function composerSource() {
  return `\\documentclass[exam-number = 1]{autoexam}\n\\versions{A, B, C}\n\\shuffle\n\\loadbank{bank.tex}\n\n`
    + `\\begin{document}\n\\maketitle\n\n${generateTeX()}\n\n\\end{document}`;
}

/* palette */
function openPalette() { S.pal.q = ""; S.pal.sel = 0; $("#pal-input").value = ""; renderPalette(); $("#palette-overlay").classList.add("open"); setTimeout(() => $("#pal-input").focus(), 30); }
function closePalette() { $("#palette-overlay").classList.remove("open"); }
function paletteMatches() {
  const q = S.pal.q.toLowerCase().trim();
  return S.problems.filter((p) => !q || `${p.id} ${p.topic} ${p.section} ${p.preview}`.toLowerCase().includes(q));
}
function renderPalette() {
  const list = paletteMatches(); S.pal.list = list;
  if (S.pal.sel >= list.length) S.pal.sel = Math.max(0, list.length - 1);
  const res = $("#pal-results");
  res.innerHTML = list.length ? list.map((p, i) => `
    <div class="pres" data-pal="${i}" aria-selected="${i === S.pal.sel}">
      ${typeChip(p)}
      <div class="pv"><div class="l1"><span class="pid">${esc(p.id)}</span>
        ${p.section ? `<span class="chip sec">&sect;${esc(p.section)}</span>` : ""}</div>
        <div class="l2">${esc(p.preview)}</div></div>
      <span class="ins">\\problem{${esc(argFor(p))}}</span></div>`).join("")
    : `<div class="empty">No problems match &ldquo;${esc(S.pal.q)}&rdquo;.</div>`;
  const sel = res.querySelector('[aria-selected="true"]'); if (sel) sel.scrollIntoView({ block: "nearest" });
}
async function paletteInsert() {
  const p = S.pal.list[S.pal.sel]; if (!p) return;
  const after = S.caret === "end" ? null : Number(S.caret);
  S.flashArg = argFor(p);
  await addToExam(p.id, after);
  if (S.caret !== "end") S.caret = Number(S.caret) + 1;
  closePalette();
}

/* =======================================================================
   CARD WALL
======================================================================= */
function renderWallFilters() {
  const f = S.wallF;
  let h = `<button class="fchip" data-wtopic="all" aria-pressed="${f.topic === "all"}">All</button>`;
  topics().forEach((t) => { h += `<button class="fchip" data-wtopic="${esc(t)}" aria-pressed="${f.topic === t}">${esc(t)}</button>`; });
  h += `<button class="fchip" data-wtype="fr" aria-pressed="${f.type === "fr"}">FR</button>`;
  h += `<button class="fchip" data-wtype="mc" aria-pressed="${f.type === "mc"}">MC</button>`;
  $("#wall-filters").innerHTML = h;
}
function renderWall() {
  renderWallFilters();
  const cards = S.problems.filter((p) => matchWith(p, S.wallF));
  $("#wall-tag").textContent = `${cards.length} cards`;
  $("#wall-grid").innerHTML = cards.map((p) => `
    <div class="card ${p.type === "mc" ? "is-mc" : ""} ${inExam(p.id) ? "in-exam" : ""}" data-card="${esc(p.id)}" role="button" tabindex="0">
      <div class="ribbon"></div>
      <div class="card-render center" id="wc-${cssId(p.id)}"></div>
      <div class="card-foot">${typeChip(p)}<span class="pid" style="font-size:11.5px">${esc(p.id)}</span>
        ${p.points != null ? `<span class="chip pts">${p.points}</span>` : ""}
        <span class="card-add ${inExam(p.id) ? "added" : ""}" data-wadd="${esc(p.id)}" title="Add" role="button" tabindex="0">${inExam(p.id) ? "&#10003;" : "&#43;"}</span></div>
    </div>`).join("") || `<div class="empty" style="grid-column:1/-1">No cards match.</div>`;
  cards.forEach((p) => injectSVG($(`#wc-${cssId(p.id)}`), p.id, false));
  renderWallDock();
}
function cssId(id) { return id.replace(/[^A-Za-z0-9_-]/g, "_"); }
function renderWallDock() {
  const film = $("#wall-film"); const entries = S.exam.entries;
  film.innerHTML = entries.length ? entries.map((e) => `
    <div class="film-chip"><span class="idx">${e.index + 1}</span>${e.env === "mc" ? `<span class="chip mc">MC</span>` : `<span class="chip fr">FR</span>`}
      <span class="pid" style="font-size:11.5px">${esc(e.arg)}</span>
      <button class="x" data-act="remove" data-idx="${e.index}" title="Remove">&times;</button></div>`).join("")
    : `<div class="film-empty">Add problems with &#43; to build the exam.</div>`;
  $("#dock-count").textContent = entries.length ? `${entries.length} &middot; ${knownPoints()} pts`.replace("&middot;", "·") : "empty";
}
function openModal(id) {
  const p = S.byId[id]; if (!p) return;
  const here = inExam(id);
  $("#modal-inner").innerHTML = `
    <div class="modal-head">${typeChip(p)}<span class="pid" style="font-size:15px">${esc(p.id)}</span>
      ${p.section ? `<span class="chip sec">&sect;${esc(p.section)}</span>` : ""}
      ${p.points != null ? `<span class="chip pts">${p.points} pts</span>` : ""}
      <button class="close-x" data-act="close-modal" aria-label="Close">&times;</button></div>
    <div class="modal-body"><div class="render-box center" id="modal-render"></div>
      <div class="src" style="margin-top:14px"><div class="egroup-lbl" style="font-family:var(--mono)">bank source</div>
        <pre>${tintTeX(p.raw)}</pre></div></div>
    <div class="modal-foot">
      ${here ? `<button class="btn" data-act="modal-remove" data-pid="${esc(p.id)}"><span>&#10003;</span> In exam &mdash; remove</button>`
        : `<button class="btn primary" data-act="modal-add" data-pid="${esc(p.id)}"><span>&#43;</span> Add to exam</button>`}
      <button class="btn ghost" data-act="copy-line-id" data-pid="${esc(p.id)}">Copy <code>\\problem{${esc(argFor(p))}}</code></button></div>`;
  injectSVG($("#modal-render"), p.id, true);
  $("#modal-overlay").classList.add("open");
}
function closeModal() { $("#modal-overlay").classList.remove("open"); }

/* =======================================================================
   exam mutations + tabs + misc
======================================================================= */
function generateTeX() {
  const fr = S.exam.entries.filter((e) => e.env === "fr");
  const mc = S.exam.entries.filter((e) => e.env === "mc");
  const blk = (name, arr) => `\\begin{${name}}\n${arr.map((e) => "\t\\problem{" + e.arg + "}").join("\n")}\n\\end{${name}}`;
  const out = [];
  if (fr.length) out.push(blk("problems", fr));
  if (mc.length) out.push(blk("mcproblems", mc));
  return out.join("\n\n") || "% add problems to build the exam body";
}
function refreshExam(data) {
  S.exam = data;
  renderTray(); renderRows();
  if (S.tab === "desk") renderPreview();
  else if (S.tab === "composer") renderComposer();
  else if (S.tab === "wall") renderWall();
}
async function addToExam(id, after) {
  const p = S.byId[id]; if (!p) { toast("unknown problem", true); return; }
  const bodyObj = { id, mode: S.insertMode };
  if (after != null) bodyObj.after = after;
  try { refreshExam(await api("/api/exam/add", post(bodyObj))); toast(`Added ${id}`); }
  catch (e) { toast(e.message, true); }
}
async function removeIdx(idx) { try { refreshExam(await api("/api/exam/remove", post({ index: idx }))); } catch (e) { toast(e.message, true); } }
async function moveIdx(idx, dir) { try { refreshExam(await api("/api/exam/reorder", post({ index: idx, dir }))); } catch (e) { toast(e.message, true); } }
async function removeByPid(id) {
  const p = S.byId[id];
  const e = S.exam.entries.find((x) => x.arg === id || x.arg === "topic=" + p.topic);
  if (e) await removeIdx(e.index);
}
function post(obj) { return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) }; }

function switchTab(tab) {
  S.tab = tab;
  $$(".tab").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === tab));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + tab));
  if (tab === "composer") renderComposer();
  else if (tab === "wall") renderWall();
}

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
  const el = ev.target.closest("[data-tab],[data-pid],[data-topic],[data-type],[data-fresh],[data-pv],[data-mode],[data-comp-view],[data-caret],[data-pal],[data-card],[data-wadd],[data-wtopic],[data-wtype],[data-act]");
  if (!el) return;
  const d = el.dataset;
  if (d.tab) switchTab(d.tab);
  else if (d.pid != null && d.act == null) { S.selected = d.pid; renderRows(); renderPreview(); }
  else if (d.topic != null) { S.filters.topic = d.topic; renderDeskFilters(); renderRows(); }
  else if (d.type != null) { S.filters.type = S.filters.type === d.type ? "all" : d.type; renderDeskFilters(); renderRows(); }
  else if (d.fresh != null) { S.filters.fresh = !S.filters.fresh; renderDeskFilters(); renderRows(); }
  else if (d.pv != null) { S.pvMode = d.pv; renderPreview(); }
  else if (d.mode != null) { S.insertMode = d.mode; $$('[data-mode]').forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === S.insertMode)); if (S.tab === "desk") renderPreview(); }
  else if (d.compView != null) { S.compMode = d.compView; $$('[data-comp-view]').forEach((b) => b.setAttribute("aria-pressed", b.dataset.compView === S.compMode)); renderComposer(); }
  else if (d.caret != null) { S.caret = d.caret; renderComposer(); }
  else if (d.pal != null) { S.pal.sel = +d.pal; paletteInsert(); }
  else if (d.wadd != null) { ev.stopPropagation(); addToExam(d.wadd, null); }
  else if (d.card != null) { openModal(d.card); }
  else if (d.wtopic != null) { S.wallF.topic = d.wtopic; renderWall(); }
  else if (d.wtype != null) { S.wallF.type = S.wallF.type === d.wtype ? "all" : d.wtype; renderWall(); }
  else if (d.act) handleAct(d.act, d);
});
function handleAct(a, d) {
  if (a === "add-sel") addToExam(S.selected, null);
  else if (a === "remove-sel") removeByPid(S.selected);
  else if (a === "remove") removeIdx(+d.idx);
  else if (a === "move") moveIdx(+d.idx, +d.dir);
  else if (a === "copy-line") copyText(`\\problem{${argFor(S.byId[S.selected])}}`, "Copied \\problem line");
  else if (a === "copy-line-id") copyText(`\\problem{${argFor(S.byId[d.pid])}}`, "Copied \\problem line");
  else if (a === "modal-add") { addToExam(d.pid, null); openModal(d.pid); }
  else if (a === "modal-remove") { removeByPid(d.pid).then(() => openModal(d.pid)); }
  else if (a === "close-modal") closeModal();
}
document.addEventListener("change", (ev) => {
  if (ev.target.id === "sol-toggle") { S.showSol = ev.target.checked; renderDeskSlot(); }
  else if (ev.target.id === "cov-target") { S.target = Math.max(0, +ev.target.value || 0); renderCoverage(); }
});
document.addEventListener("keydown", (ev) => {
  if ($("#palette-overlay").classList.contains("open")) {
    if (ev.key === "Escape") { closePalette(); ev.preventDefault(); }
    else if (ev.key === "ArrowDown") { S.pal.sel = Math.min(S.pal.list.length - 1, S.pal.sel + 1); renderPalette(); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { S.pal.sel = Math.max(0, S.pal.sel - 1); renderPalette(); ev.preventDefault(); }
    else if (ev.key === "Enter") { paletteInsert(); ev.preventDefault(); }
    return;
  }
  if ($("#modal-overlay").classList.contains("open") && ev.key === "Escape") { closeModal(); return; }
  if ((ev.metaKey || ev.ctrlKey) && (ev.key === "k" || ev.key === "K")) { ev.preventDefault(); if (S.tab !== "composer") switchTab("composer"); openPalette(); return; }
  if ((ev.key === "Enter" || ev.key === " ")) {
    const row = ev.target.closest?.("[data-pid]"); if (row && row.dataset.act == null) { S.selected = row.dataset.pid; renderRows(); renderPreview(); ev.preventDefault(); return; }
    const card = ev.target.closest?.("[data-card]"); if (card) { openModal(card.dataset.card); ev.preventDefault(); }
  }
});
$("#search").addEventListener("input", (e) => { S.filters.q = e.target.value; renderRows(); });
$("#wall-search").addEventListener("input", (e) => { S.wallF.q = e.target.value; renderWall(); });
$("#pal-input").addEventListener("input", (e) => { S.pal.q = e.target.value; S.pal.sel = 0; renderPalette(); });
$("#copy-btn").addEventListener("click", () => copyText(generateTeX(), "Copied exam body"));
$("#wall-copy").addEventListener("click", () => copyText(generateTeX(), "Copied exam body"));
$("#comp-copy").addEventListener("click", () => copyText(composerSource(), "Copied document"));
$("#palette-open").addEventListener("click", openPalette);
$("#palette-overlay").addEventListener("click", (e) => { if (e.target.id === "palette-overlay") closePalette(); });
$("#modal-overlay").addEventListener("click", (e) => { if (e.target.id === "modal-overlay") closeModal(); });
$("#theme-btn").addEventListener("click", () => {
  const root = document.documentElement;
  const cur = root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light");
  root.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
});

boot();
