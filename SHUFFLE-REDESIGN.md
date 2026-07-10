# Autoexam/quiz shuffle redesign

Branch: `feat/shuffle-collect-emit`. Goal: replace the source-text shuffle
pre-pass with a typeset-time list permutation, preserving the authoring syntax
exactly and keeping every generated file out of the user's course folders.

## Why

Today `\shuffle` shuffles **source text**. `autoexam_run_versions` re-reads the
document off disk, a hand-rolled partial TeX parser in Lua
(`find_problems_marker`, `split_section_into_items`, `shuffle_section_body`, …)
finds `\begin{problems}` blocks, Fisher-Yates permutes the string fragments,
writes a per-version temp `.tex`, and `\input`s it. Consequences:

- A partial TeX tokenizer in Lua string-land — fragile to any `%`, brace, or
  `\newpage` it didn't anticipate.
- `\newpage` does double duty as the shuffle-group delimiter (layout tangled
  with structure).
- The temp-file round-trip is the root of the `<jobname>.tex` coupling and the
  scratch-litter class of bugs.
- Split brain: question **order** shuffled in the source pre-pass, MC **option**
  order shuffled at typeset time.

## Design

Shuffle a **collected list**, not text. Inside `{problems}`/`{mcproblems}`,
`\problem` (currently `\let` to `\@problem@item`, which typesets immediately)
becomes a **collect** macro that records each item's args into an ordered Lua
list. At `\end{...}` the engine permutes the list and **emits** in shuffled
order through the *same* `pbank_problem_item` path. The string-parsing pre-pass
is deleted.

The permutation core is `problem_shuffle.lua` — pure, tex-independent,
unit-tested under plain `texlua` (`test_shuffle.lua`). It uses a private
Park-Miller MINSTD stream seeded by the per-version seed, so it needs no
`math.randomseed` warm-up (the old correlated-seed workaround goes away).

Pins for problem **order**: `\extracredit` → last (authored order kept);
`\section` → hard boundary (permute within a section). Per-page counts (from
`\newpage`) are preserved by the emit loop chunking the permuted order.
(`[fixed]` is a **choices** feature — MC option order — handled separately at
typeset time in `resolve_mc_order`; unaffected.)

## Authoring contract — unchanged (P1)

Zero migration. `\problem[pts]{id}`, `\newpage` between problems,
`\extracredit`, `\section`, `\shuffle`, `\versions{…}`, `\setversionseed` all
behave exactly as written. `exam1.tex` needs no edits. Optional future nicety:
`\begin{problems}[perpage=N]` auto-paginates so manual `\newpage`s can be
dropped — purely additive.

## Generated files → LaTeXTools' temp dir only

Every intermediate the redesign writes (the single body temp, `.sco`,
`.srcmap`, SyncTeX scratch) goes through `texlib_scratch_path()`. Next to the
source the user sees **only** the deliverables: `<base>.pdf`, the version
slices, and `.synctex` — nothing else.

`texlib_scratch_path` gains a 3-tier fallback so no build ever litters a course
folder:

1. `TEXLIB_AUX_DIR` (Sublime builder) — the normal path.
2. `TEXMF_OUTPUT_DIRECTORY` (set by TeX Live under any `-output-directory`).
3. **new:** `<system-temp>/texlib-scratch/<hash(cwd|jobname)>/` — so even a bare
   `lualatex file.tex` with no routing flags writes to temp, not the source.

The redesign also collapses the per-version body temps (`_body_A/B/C.tex`) to a
single unshuffled body — strictly fewer generated files than today.

## What changes

**Deleted** (`problem_engine.lua`, ~300 lines): `shuffle_problems_body`,
`shuffle_one_section`, `shuffle_section_body`, `find_problems_marker`,
`find_section_end`, `split_problems_on_newpage`, `split_section_into_items`, and
the `scan_depth0_commands` usage feeding them.

**Added**: `problem_shuffle.lua` (pure permute — DONE); `pbank_collect_item` +
`pbank_emit_section` in `problem_engine.lua`; a collecting `\problem` and the
emit call in `texlib-problembank.sty`.

**Version loop**: drop the `shuffle_problems_body` call; write one unshuffled
body temp, `\input` it per version with the version seed set first — each
version's `{problems}` self-shuffles.

## Behavioral note

Draws now happen at emit time in shuffled order, so a given seed yields a
**different** A/B/C ordering than today — a one-time reshuffle (accepted; no
exam administered yet). Regression tests therefore assert **properties**
(bijection, extra-credit last, sections unmixed, per-page counts held, versions
differ, rebuild byte-identical), not a byte match to the old order.

## Phases

1. **Pure permute core + contract tests** — `problem_shuffle.lua`,
   `test_shuffle.lua` (10 checks, passing). **DONE.**
2. **Collect→permute→emit wiring.** `pbank_collect_item` / `pbank_collect_break`
   / `pbank_emit_section` in `problem_engine.lua`; `{problems}`/`{mcproblems}`
   rewired (`\@problem@collect`, `\@xc@collect` for deferred extra-credit,
   `\PbankPageBreak`/`\PbankEmitItem`); `\question` numbering threaded through
   the emit. The source-text pre-pass is bypassed (`ensure_ver` inputs the body
   verbatim). Verified: single-version authored order preserved; multi-version
   shuffle correct + uniform; student/solutions of a version share one order;
   `\newpage` per-page grouping held; the real Math 182 `exam1.tex`
   (MC + FR + `\solutions` × 3 versions) builds clean. Two RNG fixes en route:
   high-bit extraction (LCG low bits correlated → an item stuck in one slot) and
   a SplitMix32 seed avalanche (adjacent version seeds collapsed onto the same
   permutation for small item counts). `\extracredit` (deferred, pinned last)
   and `\section` boundaries (a `{problems}` block splits into independently
   permuted runs, headings emitted between them) build correctly. **DONE.**
   Deferred edge case: the `.sco`/`\scorepage` instructor grid still reflects
   authored (not shuffled) order — only wrong when `\shuffle` + `\scorepage` +
   *per-problem-varying* points coincide (uniform-point sections, the common
   case, are already correct). The clean fix is emit-side `.sco` writing (the
   emit is the only place that knows the permuted order + page structure); the
   prescan text-parse would otherwise have to re-derive `\section` boundaries,
   which is exactly the parsing this redesign removes.
3. **Cleanup + hardening.** Deleted the dead string-parsing shuffle layer
   (`scan_depth0_commands`, `split_problems_on_newpage`, `split_section_into_items`,
   `shuffle_section_body`, `shuffle_one_section`, `shuffle_problems_body` — ~170
   lines; `find_problems_marker`/`find_section_end`/`scan_problem_pts` stay for
   the `.sco` prescan). Version loop now writes ONE shared body temp (was one per
   version). `texlib_scratch_path` (both copies) gained the tier-3 system-temp
   fallback, so a bare `lualatex doc.tex` leaves zero engine scratch beside the
   source. **DONE.**
4. Verify: smoke-build every exam/quiz template + the real Math 182 exams;
   assert the properties + the "only PDFs/.synctex beside the source" check;
   regen visual refs.
5. Docs + CHANGELOG.

## Risks to watch

Question numbering across shuffled emit + section boundaries; `choose=m` MC
selection and per-problem `\setrng` values drawing correctly at emit time;
SyncTeX redirection per emitted problem; the first-on-page separator-rule flag
(`pbank_first_on_page`); multi-part (`\ppart`) problems staying atomic; any
inline (non-bank) `\problem`.

## Out of scope (stretch)

Capturing the document body as a token list to eliminate the body temp file
entirely — the current code avoids `tex.sprint` for list-environment reasons, so
this needs its own spike. The one-temp-file baseline is already a large win.
