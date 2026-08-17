/* logic.js -- pure, DOM-free helpers shared by the browser app (app.js) and the
   Node test suite (test/logic.test.js).

   Loaded as a classic <script> BEFORE app.js in the browser (so these become
   globals app.js can call); require()-d in Node for testing. Keep every function
   here PURE -- no DOM, no shared mutable app state -- so it is unit-testable in
   isolation. State-dependent wrappers stay in app.js. */
"use strict";

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// pdftocairo reuses internal ids (glyph0-1, clip1, ...) across files; namespace
// each injected SVG's ids + references so inlined problems can't collide.
let _svgSeq = 0;
function uniquifySVG(svg) {
  const n = ++_svgSeq;
  return svg
    .replace(/\bid="([^"]+)"/g, (m, x) => `id="${x}__${n}"`)
    .replace(/\b(xlink:href|href)="#([^"]+)"/g, (m, a, x) => `${a}="#${x}__${n}"`)
    .replace(/url\(#([^)]+)\)/g, (m, x) => `url(#${x}__${n})`);
}

function cssId(id) { return id.replace(/[^A-Za-z0-9_-]/g, "_"); }

// how an added/pasted problem is written: a topic filter, or the bare id
function argForMode(p, mode) { return (mode === "filter" && p.topic) ? "topic=" + p.topic : p.id; }

// does a problem pass the desk/library filter set?
function matchWith(p, f) {
  if (f.topic !== "all" && p.topic !== f.topic) return false;
  if (f.type !== "all" && p.type !== f.type) return false;
  if (f.fresh && (p.used_in || []).length) return false;
  if (f.q) {
    const hay = `${p.id} ${p.topic} ${p.section} ${p.preview}`.toLowerCase();
    if (!hay.includes(f.q.toLowerCase())) return false;
  }
  return true;
}

// a representative scored problem for a "topic=..." filter (points estimate)
function filterRep(arg, problems) {
  const m = /topic=([^,]+)/.exec(arg);
  if (!m) return null;
  const t = m[1].trim();
  return (problems || []).find((p) => p.topic === t && p.points != null) || null;
}

// total points on the exam: concrete ids sum directly, filters estimate via a rep
function sumPoints(entries, byId, problems) {
  let n = 0;
  (entries || []).forEach((e) => {
    if (e.is_filter) { const c = filterRep(e.arg, problems); if (c) n += c.points; }
    else { const p = byId[e.arg]; if (p && p.points != null) n += p.points; }
  });
  return n;
}

// Theme preference: "auto" (follow the OS), "light", "dark". Auto is expressed as
// the ABSENCE of a data-theme attribute -- that is what lets the prefers-color-
// scheme rules keep tracking the OS live -- so themeAttr returns null for it.
const THEMES = ["auto", "light", "dark"];
function normalizeTheme(v) { return THEMES.includes(v) ? v : "auto"; }
function themeAttr(pref) { const t = normalizeTheme(pref); return t === "auto" ? null : t; }

// the \begin{problems}/\begin{mcproblems} body from the current entries
function examBody(entries) {
  const fr = (entries || []).filter((e) => e.env === "fr");
  const mc = (entries || []).filter((e) => e.env === "mc");
  const blk = (name, arr) =>
    `\\begin{${name}}\n${arr.map((e) => "\t\\problem{" + e.arg + "}").join("\n")}\n\\end{${name}}`;
  const out = [];
  if (fr.length) out.push(blk("problems", fr));
  if (mc.length) out.push(blk("mcproblems", mc));
  return out.join("\n\n") || "% add problems to build the exam body";
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { esc, uniquifySVG, cssId, matchWith, argForMode, filterRep, sumPoints, examBody,
                     THEMES, normalizeTheme, themeAttr };
}
