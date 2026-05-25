# Changelog

All notable changes to TeXLib are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions correspond to git tags.

## [Unreleased]

_Nothing yet._

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
- **Document-class modules.** `bingo`, `autoexam` (with `autoexam_engine.lua` for randomized exams), `didactic` (lecture notes), `pset` (problem sets), `quiz`, `report-card`, `schedule` (with `date.lua` / `calendar.lua` / `schedule.lua`), `syllabus`. Each module ships with a `.cls`, a `template.tex`, and a `README.md`.
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
