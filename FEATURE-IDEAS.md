# TeXLib — Feature Ideas

Speculative feature brainstorming for **TeXLib** and the **TeXLib-Installer**.
Distinct from [`TODO.md`](TODO.md): that file is the committed, actionable
backlog; this file is a low-stakes idea pool. Promote anything worth doing into
`TODO.md` (or a GitHub issue) and strike it here.

A scheduled agent appends a dated batch of ideas each day at midnight. Entries
are newest-first. Tag each idea with its target repo:

- **[lib]** — TeXLib (classes, `.sty`/`.tex`/`.lua`, course materials)
- **[inst]** — TeXLib-Installer (portable Windows installer)

Format for each daily batch:

```
## YYYY-MM-DD

- **[lib|inst] Short title.** One or two sentences: what it is and why it
  might be worth doing.
```

---

## 2026-06-23

- **[lib] Combined cross-version answer key from `build_versions.py`.** Add a
  `--key` aggregator that, after emitting each `\versions{...}` copy, merges the
  per-version keys into a single grader packet ordered by version letter (A, B,
  C…) instead of one loose key PDF per version. With the syllabus-aligned
  "choose-5" exams now multi-version, a grader juggles N separate keys at the
  table; one ordered packet keyed by the footer version stamp (the 2026-06-21
  seed-footer idea) makes pulling the right key a glance, not a shuffle.
- **[lib] Reusable `\formulasheet{<file>}` final-page include.** A macro in
  `texlib-assessment.sty` that appends a coursemeta-relative reference/series
  sheet as a labeled final page of an exam or quiz, single-sourced so the same
  sheet rides along both without copy-paste. The 182 rebuild ships a series sheet
  and the 181 formula sheets were reconstructed by hand; a shared include means
  one edit propagates to every assessment that opts in, and the sheet can't drift
  between the exam and its make-up quiz.
- **[lib] Per-problem grader score box.** Let a free-response problem render a
  small `[ ___ / pts ]` box in the outer margin (driven by the same
  `\meta{points}` the 2026-06-21 point-total check reads), giving graders one
  consistent place to mark and tally. It complements the end rubric without
  attaching it inline, and pairs naturally with the answer-space guard — a
  problem that reserves writing room should also reserve a place to score it.
- **[inst] "Update available" notifier.** Drop a tiny `check-texlib-update.ps1`
  that queries the GitHub releases API for the latest `TeXLib` tag, compares it
  to the bundled `VERSION.txt` snapshot stamp, and prints "you are N releases
  behind — newest is vX.Y.Z" (silently no-ops offline). It closes the loop on the
  VERSION.txt stamp: coworkers on a stale portable bundle currently have no signal
  that a hash-rot fix or new course material shipped until something breaks.

## 2026-06-22

- **[lib] Dead-bank-problem audit tool.** Add a small Python checker (mirroring
  `smoke_test.py`'s shared-file copy trick) that parses each `bank.tex` for its
  declared `\begin{problem}{id}` IDs, scans the `Exams/`/`Quizzes/` `.tex` for
  `\getproblem`/`\importproblem`/`\picklist*` references, and prints any bank IDs
  never pulled by any document. As banks accrete across semesters, stale problems
  pile up invisibly; a "these N IDs are unreferenced" report makes pruning safe.
- **[lib] coursemeta-driven exam dates, shared by syllabus + schedule.** Register
  `exam1-date`/`final-date`/… keys in `course-metadata.sty` and have both
  `syllabus.cls`'s date table and `schedule.cls`'s calendar grid read them from
  the one `coursemeta.tex`. Today the same exam dates are typed independently in
  two classes, so a mid-semester reschedule silently desyncs the syllabus from the
  wall calendar; single-sourcing them closes that gap.
- **[lib] Free-response answer-space guard.** Let a free-response problem declare
  `\meta{answer-space = <len>}` and, in student/default builds, `\PackageWarning`
  when a problem reserves none (no `\vspace`/answer box/`\fillwithlines`). A
  question shipped with zero room to write is easy to miss in a long exam and only
  surfaces when a student runs out of page — a compile-time nudge beats that.
- **[inst] One-click failure-log collector.** Have the installer drop a small
  `collect-texlib-logs.cmd` (or `.ps1`) on the coworker's desktop that zips the
  most recent `%TEMP%\texlib-aux\<hash>` log plus the bundled `VERSION.txt` and
  opens the folder ready to attach to an email. When a build breaks, the support
  loop ("send me the log / which snapshot?") collapses to one click instead of
  walking a non-technical coworker through hunting down a temp-dir hash.

## 2026-06-21

- **[lib] Exam point-total sanity check.** Have the autoexam Lua engine sum the
  declared per-problem points and compare against the exam's stated total (e.g.
  a `\meta{points = 100}`), emitting a `\PackageWarning` on mismatch. The
  syllabus-aligned "100pt, choose-5" exam format makes an off-by-a-few point
  budget easy to ship unnoticed; catching it at compile time beats a student
  finding it.
- **[lib] Print the version seed in draft/instructor footer.** When `\ifdraft`
  or `\ifinstructor` is set, stamp the resolved `\shufflepages`/version seed into
  the page footer (alongside the existing build badge). A grader holding a single
  randomized copy could then regenerate that exact version for the key, instead
  of guessing which letter the student had.
- **[lib] Bingo call-sheet output.** Add a `\meta{call-sheet = true}` mode to
  `bingo.cls` that, given the same seed, emits the ordered list of cell values as
  a compact instructor sheet — the complement to the printed cards, so the caller
  has a reproducible draw order without hand-transcribing the grid.
- **[inst] Bundle a `VERSION.txt` snapshot stamp.** Have the installer write the
  bundled TeXLib git tag + short SHA into a `VERSION.txt` and surface it in the
  post-install smoke check's pass/fail line. When a coworker reports a broken
  document, the first support question ("which snapshot are you on?") is then
  answerable without guesswork — and it pins down hash-rot vs. content bugs.

## 2026-06-20

- **[lib] Friendly "requires LuaLaTeX" guard.** `autoexam`/`schedule`/`bingo`
  fatal with a cryptic `\directlua` undefined-control-sequence error the moment
  they load under pdflatex. Wrap the class-load Lua entry in `\ifdefined\directlua`
  and `\ClassError` with a one-line "compile with lualatex" message instead, so a
  coworker who hits `Ctrl+B` in the wrong engine gets a readable diagnostic.
- **[lib] Missing-`coursemeta.tex` diagnostic.** When `course-metadata.sty`
  walks `.`/`..`/`../..`/`../../..` and finds no `coursemeta.tex`, it currently
  fails downstream with confusing "undefined `\GetCourse...`" errors. Emit one
  clear `\PackageError` naming the four searched dirs and pointing at
  `examples/Math181-Fall2026/coursemeta.tex` as the model, since bare-template
  builds hit this constantly.
- **[lib] `chktex` lint target + opt-in CI job.** `chktex` is editor-only today
  and easy to forget; add a `make lint` / small Python wrapper that runs it with
  the repo `chktexrc` over the `.tex`/`.sty`/`.cls` tree, then a non-required CI
  job (mirroring the visual-scenario "nightly/optional" pattern) so style
  regressions surface without gating merges.
- **[inst] Auto-create a comma-free build junction.** The installer's target
  coworkers likely share the `University of Nevada, Reno` Documents path whose
  comma breaks kpathsea. Have the installer detect a comma/space in the install
  path and create (or offer to create) a `C:\_texlibjunc`-style junction plus a
  pre-set `TEXINPUTS`, so the documented junction workaround ships instead of
  being rediscovered per machine.

## 2026-06-18

- **[lib] Single-source answer-key flag.** Add a `\meta{answers = true}`
  (or `\AnswersOn`) switch to `autoexam`/`quiz` that compiles an instructor
  key — solutions and rubric points revealed inline — from the *same* `.tex`
  as the student version, so the key can never drift out of sync.
- **[lib] Report-card auto letter grade.** Have the report-card class compute
  the overall percentage and map it to a letter (with an overridable cutoff
  table) instead of the instructor typing the letter by hand, removing a common
  copy/transcription error.
- **[inst] Build-time bundle hash manifest.** Have the installer build script
  verify each pinned third-party binary (Sublime, SumatraPDF) against a
  committed SHA256 manifest *before* packaging, so the silent hash-rot breakage
  is caught at build time rather than on a coworker's machine.
- **[inst] Bundled-package preflight.** Before zipping, scan the bundled TeX
  tree for the specific packages TeXLib classes `\RequirePackage` and fail loudly
  on any missing one, catching an incomplete portable TeX Live subset early.

## 2026-06-18  _(seed — example format, not auto-generated)_

- **[lib] `texlib-theme.sty` proof-of-concept.** Pull a handful of the
  hard-coded rule widths and accent colors out of one class (start with
  `schedule.cls`) into overridable keys, as a vertical slice of the broader
  theming goal already noted in `TODO.md`.
- **[inst] Post-install smoke check.** After install, compile one tiny bundled
  `.tex` and report pass/fail, so a coworker knows the toolchain actually works
  before they hit a real document.
