# Changelog

All notable changes to TeXLib are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions correspond to git tags.

## [Unreleased]

A consolidation pass: a new user-facing feature on `\problem`, four new shared `.sty` files that retire duplicated machinery between `autoexam` and `quiz`, a Lua engine rename, the test harness extended to cover the new feature, and partial SyncTeX inverse-search support for the `schedule` class.

### Added (this pass)

- **Section-aware page shuffle for multi-version exams (`\shufflepages`).** The autoexam version loop now reorders questions *within each `\section`/`\section*`* instead of Fisher-Yates over every top-level `\newpage` group. Multiple-Choice / Free-Response sections keep their order with headers fixed; questions permute only within their own section; per-page question counts are preserved and `\extracredit` is pinned last. This lets one source replace hand-maintained per-version files (`exam1vA/B/C.tex` → `exam1.tex` + `\versions{A,B,C}` + `\shufflepages`). `set_exam_seed` was hardened too (djb2 hash + Knuth multiplicative mix + seed-dependent RNG warm-up) so adjacent version letters A/B/C no longer yield correlated or identical shuffles.
- **`texlib_synctex.lua` — generic SyncTeX source-file redirect.** Extracted from the bank-specific path in `problem_engine.lua`. API: `texlib_synctex_setup()` / `texlib_synctex_stage{target_file, lines, id}` / `texlib_synctex_is_active()`. Stages a pending redirect; the registered `open_read_file` callback intercepts the next matching `\@@input`, writes a temp file padded to align source lines, and serves it through a real `io.open` handle (required for LuaTeX to emit the SyncTeX `{N`/`}N` file-tracking records). Both bank- and schedule-flavoured consumers now share this helper.
- **Per-directive source-line tagging in `schedule.lua`.** Each `L_*` directive (`L_topic`, `L_holiday`, `L_quiz`, `L_exam`, `L_finals_week`, `L_meta`, `L_skip_quiz`, …) records `tex.inputlineno` on the cells it touches via a new `tag_cell_source` helper. `render_grid` reads the per-cell tags to determine each row's "primary directive" line.
- **`<jobname>_schedule_grid.tex` + `<jobname>.schedmap` — schedule inverse-search infrastructure.** `render_grid` writes each calendar row into the grid file in week order (one line per week), and emits a sidecar `.schedmap` recording each `grid_line → user_source_line` mapping (the first contributing directive's line in `template.tex`).
- **Sublime builder rewrites `.synctex.gz` for the schedule class.** New `_rewrite_synctex_for_schedmap` step in `texlib_builder.py` reads the `.schedmap`, finds the grid-file `Input` records in the SyncTeX stream, repoints them to the user's source file, and remaps every typeset record's line component from `grid_line` to the source line. **Clicking a calendar cell in the PDF now opens `template.tex` at the line of the directive that produced that cell.** Inverse search works end-to-end in Sublime; command-line builds still produce a viable (if less polished) fallback where clicks land in the grid file at the corresponding line.

### Limitations (schedule SyncTeX)

- **Multi-week clustering under one source line.** Weeks without an explicit directive inherit the most recent directive's line via fallback propagation, so several consecutive weeks may share one attribution (e.g. all weeks between two `\holiday` calls map to the earlier one). Acceptable trade-off; finer per-cell attribution can come later.
- **Single-file assumption.** If the schedule body is `\input`-ed from a separate file rather than written inline in the main `.tex`, the source-line recording still works but the schedmap maps to lines in the main job file, not the included one. Multi-file support is a follow-up.

### Fixed (this pass)

- **`\scorepage` now finds bracketless `\problem{…}` calls.** `prescan_problems` matched only the two-optional-arg spelling `\problem[pts][stretch]{…}`, so the score-summary page came up empty for the documented, common usage. Replaced the regex with a forward scanner that tolerates 0/1/2 optional args plus a trailing `[fix]` (unit-tested over every spelling).
- **Biber-skip cache no longer re-runs needlessly.** `texlib_builder.py` records the biber-inputs fingerprint in `_postprocess` (after the final engine pass settles the `.bcf`) instead of mid-build right after biber — recording early captured a `.bcf` the post-biber pass then rewrote, forcing a spurious biber run next build. Verified by the real-toolchain integration test (3-pass build → cache hit on rebuild). The fingerprint also now folds in the biber binary version.
- **`build_versions.py` scratch cleanup** is delimiter-anchored (`<job>.` / `<job>_`) so version A never sweeps version AB's files (or a real `exam_Answers.pdf`); `merge_pdfs` releases reader handles (no Windows sharing-violation on the post-merge delete); a missing engine reports a clear PATH message.
- **Builder hygiene:** `SetFileAttributesW` replaces `os.system('attrib +h')` (no shell-quoting hazard / console flash); explicit aux directories are created; a `.spl` split signal stranded in the aux dir now warns instead of silently skipping the split. `build_versions.py` and the Sublime builder share one engine-command assembly so they can't drift.
- **`smoke_test.py`:** robust ImageMagick metric parsing, `errors="replace"` consistency, and the cwd-copy block deduped onto `_copy_shared_into`.

### Tooling

- **`build_versions.py` is documented in the top-level README** (it previously appeared only in `Sublime/README.md`).

### Added

- **Visual scenario packs (`smoke_test.py --scenarios`).** A tiered visual-test
  layer on top of the per-module suite: each scenario under
  `tests/scenarios/<area>/<name>/` is a self-contained template (metadata inline
  via `\metasetup`) exercising one configuration, built and pixel-diffed against
  `tests/visual_refs/<area>__<name>-*.png`. Tiers via an optional `tags` file
  (`core` runs by default, `full` only with `--full`); `--scenarios [AREA...]`
  filters by area, `--update-refs` regenerates. Ships packs for **Schedule**
  (`landscape-mwf`, `portrait`, `month-pages`, `summer-intensive`,
  `mid-week-start`, `recitations`, `no-quiz`), **Report Cards** (`standard`,
  `multi-student`), and **Syllabi** (`standard`, `long`) — covering orientation,
  month-pages, a 5-day intensive, partial weeks, recitation columns, a quiz-free
  grid, multi-student report cards, and multi-page syllabi. Local-only, like all
  visual checks (references are environment-specific).
- **`smoke_test.py` now verifies rendered content, not just build success.**
  After each successful build it (1) extracts the PDF text with `pdftotext` and
  asserts per-module expected substrings are present (`EXPECT_TEXT`), and (2)
  checks that key generated artifacts are non-empty (`EXPECT_ARTIFACT_NONEMPTY`
  — e.g. the schedule's `*_schedule_grid.tex`). This catches the "compiles green
  but renders blank/garbled" class a build-only check misses — the empty
  schedule grid is now a hard failure. Opt-in `--visual` pixel-diffs each page
  of the deterministic modules (`VISUAL_MODULES`: Schedule, Report Cards,
  Syllabi, Notes) against committed references in `tests/visual_refs/`
  (`--update-refs` to regenerate), catching layout regressions like the
  row-stub that text checks can't see. New flags: `--no-content`, `--visual`,
  `--update-refs`, `--dump-text`. Every external-tool check (poppler /
  ImageMagick) soft-skips when its tool is absent, so a bare TeX install still
  runs build-only. CI (`smoke.yml`) installs `poppler-utils` so content checks
  run on every push; visual regression stays a local aid (its references are
  rendering-environment-specific). Builds now run multiple passes — re-running
  while the `.log` requests it (latexmk-style) — so `\pageref{LastPage}` and
  other cross-references resolve in the rendered output ("1 of 2" rather than
  the one-shot "1 of ??").
- **`recitation-days` meta key on the `schedule` class.** Now registered in the
  `meta` family (mirroring `quiz-days`: a `\clist_gset` store + an expandable
  `\GetRecitationDays`), so `\meta{recitation-days = R}` adds a capacity-0
  recitation column. Previously `\GetRecitationDays` was an empty
  `\providecommand` with no key to set it, despite the README documenting one —
  `\meta{recitation-days=...}` errored with "unknown key".
- **`month-pages` meta key on the `schedule` class.** `\meta{month-pages = true}` typesets each calendar month as its own table on its own page (`\newpage` between months) instead of one continuous term-long table. A week straddling a month boundary is repeated — at the foot of the earlier month and the head of the next — so every month shows complete weeks, wall-calendar style; week numbers stay continuous across the term. Default (`false`/omitted) is unchanged. Implemented as a page-group partition in `render_grid` (one group = whole term by default, one group per month when enabled), with the table header/lastfoot boilerplate re-emitted per group.
- **Per-call variable overrides on `\problem`.** Inside `\begin{problems}…\end{problems}`, `\problem{id}` accepts a trailing optional argument that pins random variables to specific values for that one instance: `\problem{quadratic}[a=1, b=2, c=3]` solves `x²+2x+3` instead of a freshly-sampled quadratic. Partial fixes work too — `\problem{quadratic}[a=1]` leaves `b` and `c` random. The engine adds a `fixed[]` table that `set_var`/`set_rng`/`calc_var`/`pick_*` consult before writing, so a bank entry's own randomisation calls become no-ops on locked names. `push_scope`/`pop_scope` save and restore the table around each problem, so the override is local. `\importproblem` was upgraded to use the same lock semantics.
- **`texlib-problembank.sty`** — single source of truth for the shared problem-bank LaTeX glue: engine loader, `\setvar`/`\setrng`/`\calcvar`/`\get`, the four `\pick*` commands, `\getlist`/`\geti`/`\foreachpick`, the `\begin{problem}` environment, `\getproblem` (+ `\useproblem`/`\reqproblem`), `\ppart`, `\@problem@item`, `\loadbank`, `\importproblem`, and `\providecommand` defaults for `\workbox`/`\autoexam@problem@sep`. Required by `autoexam.cls` and `quiz.cls`; collapses ~120 lines of duplicated code per class to a single `\RequirePackage`.
- **`texlib-corepkg.sty`** — universal package bundle: fontenc/lmodern/geometry, expl3/xparse/ifthen/etoolbox, xcolor, the amsmath family, `texlib-mathutils`, graphicx, tikz/pgfplots + standard libraries, and hyperref with the canonical `\hypersetup` used across every TeXLib class. `basic-utilities.sty` now `\RequirePackage`s this and adds its own extras (siunitx, caption, tasks). `autoexam.cls`/`quiz.cls` load it directly; `didactic.cls`/`pset.cls`/`report-card.cls` inherit it transitively via basic-utilities. Each of the heavier classes shrank by 8–11 lines.
- **`texlib-itemfmt.sty`** — `\encircle` (the circled-token decoration) and `\extracredit` (extra-credit `\question` variant), previously duplicated across `autoexam.cls` and `quiz.cls`. `\extracredit` is now available to autoexam too.
- **`texlib-pagestyle.sty`** — `\SetTeXLibExamRules` bundles `\pagestyle{headandfoot}` + `\firstpagefootrule` + `\runningheadrule` + `\runningfootrule`. Sibling to `texlib-footer.sty` (which serves the fancyhdr-based classes the same way).
- **`texlib-thmenv.sty`** — the union of `\newtheorem*` declarations from `autoexam.cls` (3) and `quiz.cls` (14): `thm*`, `defn*`, `cor*`, `prop*`, `lem*`, `conj*`, `ques*`, `prob*`, `exam*`, `ex*` (legacy short alias), `notn*`, plus the remark-style `rmk*`/`recall*`/`case*`/`desiderata*`. Both classes inherit the full set.
- **Shared `\the*` aliases in `course-metadata.sty`.** `\theCourseSubject`, `\theCourseNumber`, `\theCourseTitle`, `\theCourseSection`, `\theCourseRoom`, `\theCourse`, `\theInstructor`, `\theInstitution`, `\theSchool`, `\theSeason`, `\theYear`, `\theTerm` are all `\providecommand`s here now, so no class needs to declare them and there's no risk of a `\newcommand` clash if a future metadata key reuses one of those names. Class-specific aliases (`\theExamNumber`, `\theQuizNumber`, …) stay in their respective classes.
- **`Test/Exams/fix-test.tex` + `fix-bank.tex`** — exercises the new `\problem[fix]` syntax. Registered as a smoke-test entry so the feature is covered on every CI run.
- **`smoke_test.py` now collects `.cls` files from module subdirectories** when assembling each build's temp dir, so test entries under `Test/<Module>/` can use a sibling module's class.

### Changed

- **The `schedule` environment no longer emits the title banner itself.** `\maketitle`/`\scheduletitle` must now be called explicitly in the document body (canonically right after `\begin{document}`, before `\begin{schedule}`), matching every other TeXLib class. This lets a schedule run title-less (e.g. when the banner lives elsewhere) by simply omitting the call. Existing schedule documents need one added `\maketitle` line; the canonical `Schedule/template.tex` and the README tutorial were updated accordingly.
- **`autoexam_engine.lua` → `problem_engine.lua`.** The file is shared between `autoexam` and `quiz`; the old name implied otherwise.
- **Lua engine function names: the shared ones gained a `pbank_*` prefix.** `pbank_problem_item`, `pbank_apply_fix`, `pbank_set_bankfile`, `pbank_inject_part`, `pbank_first_on_page`, `pbank_part_*`, `pbank_stretch_list`, `pbank_pending_*`, and the new `pbank_suppress_redirect` flag. Autoexam-specific functions kept their `autoexam_*` prefix (`autoexam_run_versions`, `autoexam_versions`, `autoexam_shuffle_pages`, `autoexam_write_srcmap`, `autoexam_read_body`, `autoexam_scorepage`, `autoexam_gradingrow`) — they would only ever be called by autoexam.cls.
- **`\loadbank` is now defined once in `texlib-problembank.sty`.** It activates the SyncTeX bank-file redirect via `pbank_set_bankfile()` so inverse search from the PDF lands in the bank source file (previously: only quizzes called this; autoexam ran with the redirect dormant to avoid a multi-version input-stack overflow).
- **The bank SyncTeX redirect now writes ONE reused scratch file per job** (`<jobname>_synctex.tex`) instead of one `<jobname>_synctex_<id>.tex` per problem. SyncTeX records the bank path, never the scratch file, and redirects are served strictly sequentially (each `\@@input` read to EOF and closed before the next is staged), so a single overwritten file is safe and course folders no longer accumulate one orphan `.tex` per problem.
- **Inline-defined problems now get inverse search into the document.** A `\begin{problem}{id}...\end{problem}` written directly in an exam/quiz with no `\loadbank` is attributed (via `status.filename`) to the file it lives in, so double-clicking it in the PDF jumps to its `\begin{problem}` block in that source — line-accurate, through the same single reused scratch file, no per-problem `_prob_` temp. Works in single- and multi-version builds for problems defined in the preamble or (single-version) body; problems in a multi-version body-replay file still use the per-problem fallback. `\loadbank` now restores the previous bank context after `\input` (stack-based, nesting-safe) so a `\begin{problem}` placed *after* a `\loadbank` is attributed to the document, not the stale bank file.
- **Quiz default instructions now support SyncTeX inverse search.** The boxed default wording moved out of `quiz.cls` into a real `Quizzes/quiz-instructions.tex` that the class `\input`s (boxed) when a quiz sets neither `quiz-instructions-file` nor an inline `quiz-instructions` — so double-clicking the instructions in the PDF jumps to that source, mirroring autoexam's `autoexam-instructions.tex`. Edit `quiz-instructions.tex` to change the default for every quiz. (Per-quiz overrides are unchanged: `quiz-instructions-file=` is unboxed/full-control; `quiz-instructions={…}` is inline.)
- **`quiz-instructions-file` can now be set course-wide in `coursemeta.tex`.** It's now a course-metadata key (defined in `course-metadata.sty` alongside `bank-path`), so `\metasetup{ quiz-instructions-file = my-quiz-instructions }` in `coursemeta.tex` points every quiz in the course at one local instructions file — resolved relative to the coursemeta directory (`\GetCourseMetaDir`), so it's found from any quiz folder regardless of depth. Resolution mirrors `bank-path`: tried as-is first (per-quiz, document-relative), then coursemeta-relative. Still overridable per quiz via `\meta{ quiz-instructions-file = … }`, and unset → the shared default `quiz-instructions.tex`. Defining the key in `course-metadata.sty` rather than `quiz.cls` is deliberate: `coursemeta.tex` is read before the class body, so a quiz-only key would be missed (and would clash with the metadata engine's unknown-key handler). Exams and other classes that load `coursemeta.tex` simply ignore the key. Covered by a new smoke-test scenario (`tests/scenarios/quiz/coursemeta-instructions/`).
- **Smoke-test scenarios can now make text assertions (`expect-text`).** A scenario that ships an `expect-text` file (PDF substrings, one per line) asserts rendered content directly and — when it carries no reference PNGs — skips the pixel diff, so a feature about *which text renders* (not layout) needs no committed image ref. Scenarios may also ship their own `coursemeta.tex` to exercise course-metadata keys. First user: the `quiz/coursemeta-instructions` pack.
- **Builds now leave a single inverse-search file: `<base>.synctex`.** The Sublime builder's post-process (`_finalize_synctex`) decompresses lualatex's `<base>.synctex.gz` to a plain `<base>.synctex` and deletes the `.gz`; because a viewer reads an uncompressed `.synctex` directly, SumatraPDF no longer spawns its `<base>.synctex.gz.sum.synctex` decompression cache. The build-time SyncTeX scratch `<base>_synctex.tex` (and any legacy per-problem `<base>_synctex_<id>.tex`) is removed too. Net: one hidden `.synctex` per document instead of up to three files. The schedule `.schedmap` → SyncTeX rewrite is unaffected — it runs on the `.gz` before decompression. (Raw command-line builds outside the Sublime builder still produce the `.gz` + scratch; only the builder finalizes.)
- **Multi-version exams now use the bank redirect too.** `autoexam_run_versions` no longer sets `pbank_suppress_redirect=true`. The flag existed to dodge a LuaTeX input-stack overflow when the version loop re-inputs every problem, but the `texlib_synctex.lua` helper closes each `\@@input` at EOF so the inputs pop and stack depth never accumulates (verified: a 3-version exam — 36 bank inputs — builds cleanly even with `max_in_open` forced to 20). Result: multi-version inverse search lands in the bank (not per-problem `_prob_` temp files), and these builds also produce just the single reused scratch file. The flag is retained as an explicit per-call override.

### Removed

- **`\newproblem` and `\dupproblem` are gone — define problems with the `\begin{problem}` environment.** The environment does everything the commands did (define in a bank file, the preamble, or the body) plus supports SyncTeX inverse search, so there's now one canonical way to author a problem. No live document used the commands. Migration is mechanical: `\newproblem{id}{meta}{body}[ans]` → `\begin{problem}{id}[meta]` *body* `\solution` *ans* `\end{problem}`. The dead `define_problem()` Lua backend was removed too (`define_problem_from_env()` remains).

### Fixed

- **`texlib-problembank` no longer forces every loading document onto LuaLaTeX.**
  Its load-time engine loader ran `\directlua` unconditionally, so any
  non-LuaTeX (pdflatex) class that `\RequirePackage`s it — e.g. `didactic`,
  which auto-loads it so lecture notes can optionally `\getproblem` — died at
  load with "Undefined control sequence `\directlua`". The loader is now guarded
  by `\ifdefined\directlua`: under LuaLaTeX it loads as before; under any other
  engine the load is skipped and the bank macros route through an internal
  `\pbank@lua` bridge that raises a clear "Problem-bank features require
  LuaLaTeX" error — but only if a bank command is actually used, so notes/handout
  documents that merely load the package still compile under pdflatex. The
  `\directlua` primitive itself is left untouched (not shadowed), so other
  packages' `\ifdefined\directlua` engine probes still work.
- **Schedule grid no longer leaves a vertical-rule stub below the last row.** The table's bottom edge used to show a short fragment of the `WEEK`/day column rules hanging beneath the final week — longtable was synthesising a phantom trailing row from the non-empty `\endlastfoot` (`\noalign{\vskip -12pt}\hline`). `render_grid` now ends every row, including the last, with `\tabularnewline \hline` and uses an empty `\endlastfoot`, so the last row's own rule is the clean bottom edge. (The same fix applies to each month's table in `month-pages` mode.)
- **SyncTeX bank-file redirect no longer fires "missing \item" errors for problems past line ~1000.** The redirect path pads its temp file with blank lines so the served content lines up with the bank's true source lines (for accurate inverse-search attribution). Each blank line was tokenising — under the default `\endlinechar=13` — to a `\par` token; exam.cls's `\trivlist` starts complaining once roughly 1000 `\par`s have stacked inside a `\question` item, breaking single-version exams and quizzes whenever a problem lived past line ~1000 of the bank. `typeset_problem` now brackets the padding region with `\endlinechar=-1\relax` on line 1 and `\endlinechar=13\relax` on `sm.line-1`, so the blank lines emit zero tokens (no `\par`) and only one harmless `\par` fires right before the real content begins. SyncTeX line attribution is preserved — clicks still land on the correct bank line.
- **`\importproblem` overrides are now actually locked.** Previously its overrides were set via direct `set_var` calls, which the imported file's own `\setrng` could clobber. It now routes through `pbank_apply_fix` and gets the same `fixed[]`-table semantics as `\problem[a=1,b=2]`.

### Cleanup

- Stripped duplicate `\RequirePackage` lines (`fontenc`, `lmodern`, `geometry`, `xparse`, `expl3`, `etoolbox`, the amsmath family, `graphicx`, `tikz`/`pgfplots`, `hyperref` + `\hypersetup`) from `didactic.cls`, `pset.cls`, and `report-card.cls` — all now come through `basic-utilities` → `texlib-corepkg`.
- Removed stray build artifacts (`Notes/template.aux`/`.log`/`.out`/`.toc`, `Problem Sets/template.pdf`/`.synctex.gz`) that had escaped `.gitignore`.

## [0.1.1] — 2026-05-23

Patch release: aux-directory routing for the Sublime builder + theorem-environment polish across the document classes.

### Added

- **Starred (unnumbered) theorem environments in `didactic` and `pset`.** Every theorem-family environment gets a `*` twin (`theorem*`, `lemma*`, `definition*`, `proposition*`, `corollary*`, etc.) plus, in didactic, the short-alias starred forms (`defn*`, `conv*`, `ques*`, `exer*`, `exam*`, `notn*`, `chal*`). Same tcolorbox styling as the numbered versions; consume no counter. Use for one-off results you don't want to clutter the numbering with.
- **Context-sensitive top-level `enumerate` labels in `didactic`.** Inside bold-titled theorem/definition environments, top-level enumerate items render as bold roman (`i.`, `ii.`, `iii.`); everywhere else (body text, remark/question/recall boxes), they render as italic roman. Implemented via `\AtBeginEnvironment` raising a boolean that's read at label-typesetting time, so a bare `\begin{enumerate}` adapts to its surroundings with no per-list configuration.
- **Bold roman top-level `enumerate` labels in `pset` and `autoexam`.** Matches didactic's bold-roman-in-theorem-environment look, applied unconditionally since neither class has a mixed-context need. `\ref` to enumerate items prints `i`, `ii`, ... consistent with the visible label.
- **`didactic` auto-sets the section counter to `\GetUnitNumber` in `\maketitle`.** Subsections now render as `N.1`, `N.2`, ...  and section-numbered theorems pick up the unit prefix without the per-file `\setcounter{section}{...}` boilerplate. Guarded against documents that omit the unit-number metadata key.

### Fixed

- **`Sublime/texlib_builder.py` now honors the LaTeXTools `aux_directory` setting** (the template ships with `"<<temp>>"`, which was previously ignored). The builder routes the engine via `-output-directory` to a stable per-document temp dir under `%TEMP%\texlib-aux\<hash>\`, then copies the PDF, `.synctex.gz`, and any `.spl` signal back next to the source. Net effect: `.aux/.log/.out/.toc/.bcf/.bbl/.fls/.fdb_latexmk` stop accumulating in source directories and OneDrive doesn't see them as changes on every Ctrl+B. biber invocations now use `--input-directory` / `--output-directory` so biblatex cross-references still resolve when aux routing is active. Set `aux_directory` to `""` or `"<<root>>"` in `LaTeXTools.sublime-settings` to opt out and restore the old in-source behavior.

## [0.1.0] — 2026-05-22

Initial public-on-GitHub release. Snapshot of TeXLib after the documentation pass and CI wiring.

### Added

- **Core packages.** `basic-utilities.sty`, `course-metadata.sty` (v8.1 layered metadata engine), `texlib-build.sty` (unified build flags), `texlib-footer.sty`, `texlib-mathutils.sty`, `texlib-theorems.sty`. `quiver.sty` vendored from https://q.uiver.app.
- **Document-class modules.** `bingo`, `autoexam` and `quiz` (which share `problem_engine.lua` for problem-bank randomisation), `didactic` (lecture notes), `pset` (problem sets), `report-card`, `schedule` (with `date.lua` / `calendar.lua` / `schedule.lua`), `syllabus`. Each module ships with a `.cls`, a `template.tex`, and a `README.md`.
- **Smoke-test harness.** [`smoke_test.py`](smoke_test.py) builds every module's `template.tex` and reports pass/fail. Supports `--modes all` to also build with `\StudentMode`, `\ShowKey`, `\ShowSolutions`.
- **Sublime Text integration.** Custom builder `texlib_builder.py` plus build system, command-palette entries, and LaTeXTools settings. See [`Sublime/README.md`](Sublime/README.md).
- **GitHub Actions CI.** `.github/workflows/smoke.yml` runs `smoke_test.py` on every push and PR inside a TeX Live full container; uploads `.log` files as artifacts on failure.
- **Quickstart documentation.** New per-machine and per-course setup walkthroughs in the README, plus [`coursemeta.example.tex`](coursemeta.example.tex) as a copy-paste starting point.
- **MIT license** (with a carve-out noting `quiver.sty` is third-party).

### Notes

- `course-metadata_old.sty` (v7) was archived on the `archive/old-metadata` branch before deletion. Recoverable from there if ever needed.
- A handful of pre-class-consolidation prototypes (`Bingo/bingo.tex`, `Bingo/bingo_og.tex`, `Bingo/Math 181 Su25 *.tex`) and dev-test files (`Notes/test_aliases.*`, `Notes/test_conv_fix.*`, `Notes/test_labeledsection.*`) were deleted from disk before the first commit, so they have no history in this repo.

[Unreleased]: https://github.com/landonfox00/TeXLib/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/landonfox00/TeXLib/releases/tag/v0.1.1
[0.1.0]: https://github.com/landonfox00/TeXLib/releases/tag/v0.1.0
