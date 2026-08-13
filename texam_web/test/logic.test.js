/* logic.test.js -- unit tests for the pure client logic (texam_web/logic.js),
   run under Node's built-in test runner (no dependencies):

       node --test texam_web/test/

   These cover the browser-side logic that has no server equivalent: HTML
   escaping, SVG id-namespacing, filter matching, points math, and the exam-body
   serializer. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const L = require("../logic.js");

test("esc escapes the HTML metacharacters", () => {
  assert.strictEqual(L.esc("a<b>&c"), "a&lt;b&gt;&amp;c");
  assert.strictEqual(L.esc(42), "42");
});

test("uniquifySVG namespaces ids + refs, disjoint per call", () => {
  const svg = '<svg><path id="glyph0-1"/><use xlink:href="#glyph0-1"/><rect fill="url(#p)"/></svg>';
  const a = L.uniquifySVG(svg);
  assert.match(a, /id="glyph0-1__\d+"/);
  assert.match(a, /xlink:href="#glyph0-1__\d+"/);
  assert.match(a, /url\(#p__\d+\)/);
  const b = L.uniquifySVG(svg);
  const idA = a.match(/id="([^"]+)"/)[1];
  const idB = b.match(/id="([^"]+)"/)[1];
  assert.notStrictEqual(idA, idB);            // different calls -> different namespace
});

test("cssId sanitizes to an attribute-safe token", () => {
  assert.strictEqual(L.cssId("a/b c:d.e"), "a_b_c_d_e");
  assert.strictEqual(L.cssId("keep-_ok"), "keep-_ok");
});

test("argForMode: filter uses topic, id otherwise", () => {
  const p = { id: "p1", topic: "alg" };
  assert.strictEqual(L.argForMode(p, "filter"), "topic=alg");
  assert.strictEqual(L.argForMode(p, "id"), "p1");
  assert.strictEqual(L.argForMode({ id: "q", topic: "" }, "filter"), "q");   // no topic -> id
});

test("matchWith honors topic / type / fresh / query", () => {
  const p = { id: "lim1", topic: "limit", type: "fr", section: "2.3",
              preview: "evaluate the limit", used_in: [] };
  const F = (o) => Object.assign({ topic: "all", type: "all", fresh: false, q: "" }, o);
  assert.ok(L.matchWith(p, F({})));
  assert.ok(!L.matchWith(p, F({ topic: "algebra" })));
  assert.ok(!L.matchWith(p, F({ type: "mc" })));
  assert.ok(L.matchWith(p, F({ q: "EVAL" })));            // case-insensitive, hits preview
  assert.ok(!L.matchWith(p, F({ q: "zzz" })));
  const used = Object.assign({}, p, { used_in: [{ file: "quiz.tex" }] });
  assert.ok(!L.matchWith(used, F({ fresh: true })));      // fresh-only hides a used problem
  assert.ok(L.matchWith(p, F({ fresh: true })));          // ...but keeps an unused one
});

test("filterRep finds a scored representative for a topic filter", () => {
  const problems = [{ id: "a", topic: "limit", points: null },
                    { id: "b", topic: "limit", points: 5 }];
  assert.strictEqual(L.filterRep("topic=limit", problems).id, "b");
  assert.strictEqual(L.filterRep("plain-id", problems), null);
  assert.strictEqual(L.filterRep("topic=none", problems), null);
});

test("sumPoints adds concrete ids and estimates filters", () => {
  const byId = { a: { points: 6 }, b: { points: 4 }, c: {} };
  const problems = [{ topic: "x", points: 3 }];
  const entries = [
    { arg: "a", is_filter: false },
    { arg: "b", is_filter: false },
    { arg: "c", is_filter: false },          // no points -> contributes 0
    { arg: "topic=x", is_filter: true },     // estimated via rep (3)
    { arg: "topic=none", is_filter: true },  // no rep -> 0
  ];
  assert.strictEqual(L.sumPoints(entries, byId, problems), 13);   // 6 + 4 + 0 + 3 + 0
  assert.strictEqual(L.sumPoints([], byId, problems), 0);
});

test("theme preference normalizes to auto and maps auto to no attribute", () => {
  assert.deepStrictEqual(L.THEMES, ["auto", "light", "dark"]);
  assert.strictEqual(L.normalizeTheme("dark"), "dark");
  assert.strictEqual(L.normalizeTheme("light"), "light");
  assert.strictEqual(L.normalizeTheme("auto"), "auto");
  assert.strictEqual(L.normalizeTheme("system"), "auto");   // unknown -> the default
  assert.strictEqual(L.normalizeTheme(null), "auto");       // nothing stored -> the default
  assert.strictEqual(L.themeAttr("auto"), null);            // auto == no data-theme
  assert.strictEqual(L.themeAttr("junk"), null);
  assert.strictEqual(L.themeAttr("dark"), "dark");
});

test("examBody emits FR + MC blocks (or a placeholder when empty)", () => {
  const body = L.examBody([
    { arg: "a", env: "fr" }, { arg: "topic=t", env: "fr" }, { arg: "m", env: "mc" },
  ]);
  assert.match(body, /\\begin\{problems\}/);
  assert.match(body, /\\problem\{a\}/);
  assert.match(body, /\\problem\{topic=t\}/);
  assert.match(body, /\\begin\{mcproblems\}/);
  assert.match(body, /\\problem\{m\}/);
  assert.strictEqual(L.examBody([]), "% add problems to build the exam body");
});
