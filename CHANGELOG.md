# Changelog

All notable changes to TeXLib are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions correspond to git tags.

## [Unreleased]

A consolidation pass: a new user-facing feature on `\problem`, four new shared `.sty` files that retire duplicated machinery between `autoexam` and `quiz`, a Lua engine rename, and the test harness extended to cover the new feature.

### Added

- **Per-call variable overrides on `\problem`.** Inside `\begin{problems}…\end{problems}`, `\problem{id}` accepts a trailing optional argument that pins random variables to specific values for that one instance: `\problem{quadratic}[a=1, b=2, c=3]` solves `x²+2x+3` instead of a freshly-sampled quadratic. Partial fixes work too — `\problem{quadratic}[a=1]` leaves `b` and `c` random. The engine adds a `fixed[]` table that `set_var`/`set_rng`/`calc_var`/`pick_*` consult before writing, so a bank entry's own randomisation calls become no-ops on locked names. `push_scope`/`pop_scope` save and restore the table around each problem, so the override is local. `\importproblem` was upgraded to use the same lock semantics.
- **`texlib-problembank.sty`** — single source of truth for the shared problem-bank LaTeX glue: engine loader, `\setvar`/`\setrng`/`\calcvar`/`\get`, the four `\pick*` commands, `\getlist`/`\geti`/`\foreachpick`, `\newproblem`/`\dupproblem`, `\begin{problem}`, `\getproblem` (+ `\useproblem`/`\reqproblem`), `\ppart`, `\@problem@item`, `\loadbank`, `\importproblem`, and `\providecommand` defaults for `\workbox`/`\autoexam@problem@sep`. Required by `autoexam.cls` and `quiz.cls`; collapses ~120 lines of duplicated code per class to a single `\RequirePackage`.
- **`texlib-corepkg.sty`** — universal package bundle: fontenc/lmodern/geometry, expl3/xparse/ifthen/etoolbox, xcolor, the amsmath family, `texlib-mathutils`, graphicx, tikz/pgfplots + standard libraries, and hyperref with the canonical `\hypersetup` used across every TeXLib class. `basic-utilities.sty` now `\RequirePackage`s this and adds its own extras (siunitx, caption, tasks). `autoexam.cls`/`quiz.cls` load it directly; `didactic.cls`/`pset.cls`/`report-card.cls` inherit it transitively via basic-utilities. Each of the heavier classes shrank by 8–11 lines.
- **`texlib-itemfmt.sty`** — `\encircle` (the circled-token decoration) and `\extracredit` (extra-credit `\question` variant), previously duplicated across `autoexam.cls` and `quiz.cls`. `\extracredit` is now available to autoexam too.
- **`texlib-pagestyle.sty`** — `\SetTeXLibExamRules` bundles `\pagestyle{headandfoot}` + `\firstpagefootrule` + `\runningheadrule` + `\runningfootrule`. Sibling to `texlib-footer.sty` (which serves the fancyhdr-based classes the same way).
- **`texlib-thmenv.sty`** — the union of `\newtheorem*` declarations from `autoexam.cls` (3) and `quiz.cls` (14): `thm*`, `defn*`, `cor*`, `prop*`, `lem*`, `conj*`, `ques*`, `prob*`, `exam*`, `ex*` (legacy short alias), `notn*`, plus the remark-style `rmk*`/`recall*`/`case*`/`desiderata*`. Both classes inherit the full set.
- **Shared `\the*` aliases in `course-metadata.sty`.** `\theCourseSubject`, `\theCourseNumber`, `\theCourseTitle`, `\theCourseSection`, `\theCourseRoom`, `\theCourse`, `\theInstructor`, `\theInstitution`, `\theSchool`, `\theSeason`, `\theYear`, `\theTerm` are all `\providecommand`s here now, so no class needs to declare them and there's no risk of a `\newcommand` clash if a future metadata key reuses one of those names. Class-specific aliases (`\theExamNumber`, `\theQuizNumber`, …) stay in their respective classes.
- **`Test/Exams/fix-test.tex` + `fix-bank.tex`** — exercises the new `\problem[fix]` syntax. Registered as a smoke-test entry so the feature is covered on every CI run.
- **`smoke_test.py` now collects `.cls` files from module subdirectories** when assembling each build's temp dir, so test entries under `Test/<Module>/` can use a sibling module's class.

### Changed

- **`autoexam_engine.lua` → `problem_engine.lua`.** The file is shared between `autoexam` and `quiz`; the old name implied otherwise.
- **Lua engine function names: the shared ones gained a `pbank_*` prefix.** `pbank_problem_item`, `pbank_apply_fix`, `pbank_set_bankfile`, `pbank_inject_part`, `pbank_first_on_page`, `pbank_part_*`, `pbank_stretch_list`, `pbank_pending_*`, and the new `pbank_suppress_redirect` flag. Autoexam-specific functions kept their `autoexam_*` prefix (`autoexam_run_versions`, `autoexam_versions`, `autoexam_shuffle_pages`, `autoexam_write_srcmap`, `autoexam_read_body`, `autoexam_scorepage`, `autoexam_gradingrow`) — they would only ever be called by autoexam.cls.
- **`\loadbank` is now defined once in `texlib-problembank.sty`.** It activates the SyncTeX bank-file redirect via `pbank_set_bankfile()` so inverse search from the PDF lands in the bank source file (previously: only quizzes called this; autoexam ran with the redirect dormant to avoid a multi-version input-stack overflow). `autoexam_run_versions` now sets `pbank_suppress_redirect=true` before iterating versions, so the redirect is automatically suppressed for the multi-version case and active for single-version builds.

### Fixed

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
