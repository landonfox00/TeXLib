# How inverse search actually works — and what else could

Research notes, 2026-08-20. Written alongside the solution-box inverse-search
fix (PR #81) because that fix was found by measurement and its mechanism was
not understood at the time. It is now. Everything below is either verified
against this repo's own builds, read directly from the named sources, or
explicitly flagged as inference.

Instruments: `sol_probe.py` and `dissect_synctex.py` (session scratchpad;
recreate from this document if lost — each is ~80 lines against
`test_synctex_integration`'s fixtures).

## 1. The three layers

Inverse search is three separate systems that only agree by convention:

1. **Engine emission.** The engine stamps every node (glyph, kern, glue, box,
   rule, math) with a *tag* (input-file number) and *line* at node-creation
   time. At shipout it serializes the page's box tree into `.synctex`:
   `Input:` records map tags to filenames; per-sheet records `(`/`)` (hbox),
   `[`/`]` (vbox), `x` (current position), `k`, `g`, `r`, `$` carry
   `tag,line:x,y[:W,H,D]` in TeX sp.
2. **The file.** A *verbose sketch of the box tree*, not a click map. Box
   records carry TeX's box dimensions, which routinely lie about ink
   (`\smash`, `\rlap`, overhanging rules), and child records carry baseline
   positions only.
3. **The viewer's parser.** `synctex_parser.c` (Jérôme Laurens). SumatraPDF
   vendors it verbatim (`ext/synctex/` in its repo — verified), so the
   `synctex edit` CLI used by our test suite exercises the same lineage of
   code as Landon's actual viewer. It does **not** trust the recorded
   geometry; it reconstructs its own. That reconstruction is where our bug
   lived.

## 2. What the parser really does with a click

From `synctex_parser.c` (fetched from jlaurens/synctex master and read):

- **Visible boxes.** Each hbox gets a second geometry, the `_V` ("visible")
  box: initialized from the recorded dimensions
  (`_synctex_setup_visible_hbox`), then *grown — never shrunk — to contain
  every child* (`_synctex_make_hbox_contain_point/box`). The stated rationale
  in the source: "some box have 0 width but do contain text material." This
  exists to compensate for `\smash`-style lies, and it is exactly what our
  decoration exploited in reverse: a 0-size smashed wrapper containing a
  page-wide, box-tall rule acquires a visible box the size of the rule.
- **Edit query** (`synctex_iterator_new_edit`): walk all hboxes of the sheet;
  among those whose visible box contains the click, take the *smallest*
  (`_synctex_smallest_container_v2`, by area); descend to the *deepest*
  contained box (`_synctex_eq_deepest_container_v2`); answer with the closest
  *children* of that box. If no hbox contains the click at all, fall back to
  nearest-box by a 9-region distance metric (`_synctex_distance_to_box_v2`).
- The LuaTeX manual says it plainly: "the synctex interpreter used in editors
  is rather peculiar and has some assumptions (heuristics)."

Consequences worth internalizing:

- A click's answer is decided by **which box wins the container contest**,
  not by what ink is under the cursor.
- Decoration that enlarges a wrapper's visible box makes that wrapper the
  deepest container for clicks over the *content*, and the answer then comes
  from the decoration's nodes, not the text's.
- A point *outside* every visible hbox can resolve *better* than a point
  inside the wrong one, via the nearest-box fallback. That is precisely the
  "click below the line works, click on the text doesn't" behaviour users
  called flaky.

## 3. The measured mechanism of our bug

Dissection of the real Scenario-2 build (solutions mode), baseline vs fixed:

- The solution's glyph records (`x<tag>,5`) sit on the line baseline
  (y = 151.4pt) inside a line hbox whose *recorded* box (143.9–153.5pt)
  covers the glyphs. The records were never displaced — my PR #81 framing
  ("the rule displaces the records") was behaviorally right and mechanically
  wrong. What moves is the *resolvable region*, on the parser side.
- Baseline: the dead band ended at **159.1pt = the fill rule's overhanging
  bottom** (baseline 151.4 + depth 2.1 + 6pt overhang). Fixed: it ended at
  **153.1 ≈ the box bottom** (151.4 + 2.1). The live-band edge tracks the
  decoration's extent exactly, in both geometries. That is the smoking gun
  for the visible-box mechanism.
- The page is full of **tag-0 records** — including the paragraph's own
  line-hboxes (`(0,7:…`) — and `Input:` tags start at 1, so tag 0 maps to
  *no file*. A query that lands on a tag-0 node has nothing to print, and the
  CLI answers with its banner alone: the observed "resolves to nothing".
  Tag 0 here is a signature of this pipeline's Lua-emitted material (the
  engine serves body content through `tex.print`/redirects; the *glyphs* get
  correct tags via `texlib_synctex.lua`'s input redirect, but the *boxes
  built around them* do not). Flagged as inference: the precise LuaTeX rule
  for when tag 0 is assigned was not chased to the engine source.
- Residual anomaly, recorded not explained: with the fill flush, the accent
  rule must *keep* its 6pt overhang — making the accent flush as well
  regressed the offset to +6.2pt. The two rules interact through the
  container contest in a way that was measured (three configurations) but not
  derived. The comment in `texlib-solutions.sty` says: re-measure, don't
  reason.

The durable lesson for this codebase: **inside a text line, decoration must
never have a larger visible extent than the box that carries the content** —
where "visible extent" means the parser's grown box, not TeX's dimensions,
so `\smash`/`\raisebox{0pt}[0pt][0pt]` do not help (both measured: no
effect). Zero-declared size is invisible to TeX and fully visible to SyncTeX.

## 4. Alternative architectures

### 4a. Direct node control in LuaTeX (the unused superpower)

LuaTeX exposes the whole attribution layer (manual §10.3.19, §"node
functions"; present in the TL2025 LuaTeX shipped here):

- `node.set_synctex_fields(n, tag, line)` / `get_synctex_fields` — per-node,
  on glue, kern, hlist, vlist, rule, math (and glyph, engine-mode dependent);
- `tex.set_synctex_mode(0–4)` — 0 native; 1 use the values set below; 2–4
  extend coverage to glyphs/glue;
- `tex.set_synctex_tag/line` (save-stack aware),
  `tex.force_synctex_tag/line` (overriding; 0 resets);
- `tex.set_synctex_no_files` + the `finish_synctex` callback — for replacing
  the native file writer outright.

TeXLib already manipulates attribution *indirectly* (`texlib_synctex.lua`
serves generated content through a real temp file so the engine's native
stamping lands on the user's source — 221 lines of machinery to arrange what
`force_synctex_tag/line` states in two calls). The indirect route works and
is well-tested; the direct route is strictly more expressive: it can also fix
the *containers*, which the redirect cannot reach.

### 4b. The ConTeXt replacement (proof the full rewrite works)

ConTeXt abandoned native emission entirely (Hans Hagen; local:
`doc/context/.../workflows-synctex.tex`, read in full). Design points, all
quoted or paraphrased from that chapter:

- sets/overloads the node fields from Lua and writes its **own** `.synctex`
  (uncompressed, ConTeXt-constructed);
- restricts sync to **text in the text flow** — headers, footers, and
  macro-generated furniture are deliberately unreachable, and files from the
  TeX tree are blocked (`\blocksynctexfile`) so a click can never open a
  read-only style file;
- ships two granularities: `method=min` (per word, ~10% overhead) and
  `method=max` (ranges, ~5%);
- ships a viewer cheat (`state=repeat`) whose stated purpose is "to fool the
  areas resolver in the library that the viewer uses" — independent
  confirmation that the parser heuristics, not emission, are the fragile
  layer;
- ships `mtx-synctex`, its **own resolver script**, used by TeXShop instead
  of the library — with the pointed remark that "very few editors are able to
  delegate resolving the file and line from position on the page to a script
  which would be a generic solution".

### 4c. Editor-side reimplementations

The parser heuristics exist in at least three independent codebases:
Laurens' C library (SumatraPDF, Skim, Okular, the TeX Live CLI), VS Code
LaTeX-Workshop's TypeScript reimplementation (`synctexjs`, toggleable against
an external `synctex` binary), and ConTeXt's `mtx-synctex`. Any TeXLib change
that leans on parser behaviour should be tested against the CLI (done — our
suite) and ideally spot-checked in Sumatra, but Sumatra vendoring the C
library means the CLI is a faithful proxy.

### 4d. Non-SyncTeX fallbacks (for completeness)

Text-search-based inverse search (find the clicked words in the source) is
what Skim does when SyncTeX fails; it needs no build support but breaks on
math, generated text, and duplicated phrases — for a problem-bank pipeline,
where the same stem can appear in multiple copies, it is structurally wrong.
`\pdfsavepos`-style custom position maps could drive a bespoke sync but would
re-derive ConTeXt's solution with none of its maturity. Neither is worth
pursuing here given 4a exists.

## 5. Recommendations for TeXLib, ranked

1. **Keep the geometric discipline and gate it.** PR #81's rule — decoration
   flush to the content box — plus the probe's numeric check (click at glyph
   centre must resolve; band offset ≈ 0) is cheap and now understood. The
   probe deserves promotion from scratchpad to the test suite as a scenario
   check so a future box redesign fails a gate instead of a user.
2. **Stamp the containers, not just the glyphs.** The two `KNOWN`
   mc-key-inverse-search failures and the tag-0 container problem are the
   same disease. One `node.set_synctex_fields` pass over the solution
   wrapper's boxes and rules — stamping them with the *solution's own*
   tag/line, reachable from the existing Lua layer — would turn the whole
   green box into a correct click target instead of a hazard. This composes
   with, rather than replaces, `texlib_synctex.lua`. Prototype before
   trusting: the container contest means results must be measured (§3's
   anomaly).
3. **Do not rewrite emission.** ConTeXt proves a full replacement is
   possible and also what it costs (its own resolver, per-viewer cheats,
   maintained forever). TeXLib's native+redirect emission works; the failures
   have all been parser-interaction bugs, which recommendations 1–2 address
   at a fraction of the surface.

## Sources

- `synctex_parser.c`, jlaurens/synctex (master; fetched and read —
  `synctex_iterator_new_edit`, `_synctex_setup_visible_hbox`,
  `_synctex_make_hbox_contain_*`, `_synctex_point_in_box_v2`,
  `synctex_node_hbox_{v,width,height,depth}`).
- SumatraPDF source tree, `ext/synctex/` (GitHub API listing; vendored copy
  of the same parser).
- LuaTeX Reference Manual, TL2025 (`doc/luatex/base/luatex.pdf`):
  §10.3.19 "Functions related to synctex", node functions
  `get/set_synctex_fields`, callback `finish_synctex`.
- ConTeXt workflows manual, SyncTeX chapter
  (`doc/context/sources/general/manuals/workflows/workflows-synctex.tex`).
- This repo: `texlib_synctex.lua`, `texlib-solutions.sty`,
  `Sublime/test_texlib_synctex_integration` fixtures; measurements from
  `sol_probe.py` / `dissect_synctex.py` runs of 2026-08-19/20.
