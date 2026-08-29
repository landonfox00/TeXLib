# TeXLib

[![smoke](https://github.com/landonfox00/TeXLib/actions/workflows/smoke.yml/badge.svg)](https://github.com/landonfox00/TeXLib/actions/workflows/smoke.yml)
[![tests](https://github.com/landonfox00/TeXLib/actions/workflows/tests.yml/badge.svg)](https://github.com/landonfox00/TeXLib/actions/workflows/tests.yml)

A personal LaTeX library for math teaching at the University of Nevada, Reno: shared `.sty` packages, a set of document-class modules (exams, quizzes, lecture notes, problem sets, schedules, syllabi, report cards, bingo cards, problem-bank catalogs, and a thesis class), a LuaLaTeX engine for randomized exams, a Sublime Text build system, and a smoke-test harness that builds every module after refactors.

## Quickstart

Set up TeXLib on a new machine or for a new course.

### One-time setup (per machine)

1. **Install a recent TeX Live** (2023 or later — needs `lualatex`, `expl3`, `tcolorbox`, `pgfplots`, `siunitx`, `mathrsfs`, `tikz-cd`, `spath3`). On Windows, install TeX Live full; on macOS, use MacTeX; on Linux, install `texlive-full` from your package manager.
2. **Clone this repo:**
   ```
   git clone https://github.com/landonfox00/TeXLib.git
   cd TeXLib
   ```
3. **Tell `kpathsea` where to find the shared `.sty` files.** Add the absolute path to the TeXLib root to your `TEXINPUTS`:
   ```
   # bash/zsh
   export TEXINPUTS=".:/abs/path/to/TeXLib:$TEXINPUTS"
   # PowerShell
   $env:TEXINPUTS = ".;C:\path\to\TeXLib;$env:TEXINPUTS"
   ```
   Make the change permanent in your shell rc / Windows environment variables. **Warning:** `kpathsea` cannot resolve `TEXINPUTS` entries that contain commas, so watch for commas in any path component. On Windows that means OneDrive paths like `OneDrive - University of Nevada, Reno` need a junction (for example, `OneDriveUNR`); see [Sublime/README.md](Sublime/README.md) for the workaround used in the Sublime build system.
4. **(Optional) Run the smoke test** to confirm everything builds:
   ```
   python smoke_test.py
   ```
   Exit code 0 means every module's template built cleanly.

### Per-course setup

1. **Make a course directory** anywhere on disk (it doesn't need to be inside TeXLib). For example:
   ```
   ~/Courses/Math181-Fall2026/
   ```
2. **Drop in a `coursemeta.tex`** with the institution / instructor / course / term values. Copy [`coursemeta.example.tex`](coursemeta.example.tex) and edit, or look at [`examples/Math181-Fall2026/`](examples/Math181-Fall2026/) for a working end-to-end course folder. `course-metadata.sty` auto-discovers this file from the document directory or any of five ancestors, so a single `coursemeta.tex` at the course root applies to every document underneath it.
3. **Pick a document class** from the [Modules](#modules) table below and start a new `.tex`:
   ```latex
   \documentclass{didactic}        % lecture notes
   % or {pset}, {quiz}, {autoexam}, {schedule}, {syllabus}, {report-card},
   %    {bingo}, {bank}, {thesis}
   \begin{document}
     ...
   \end{document}
   ```
4. **Build.** From Sublime Text (with the build system from `Sublime/` installed) it's `Ctrl+B` — the builder picks the right engine per class. From the command line the engine matters:
   ```
   lualatex yourfile.tex          # autoexam / quiz / schedule / bingo / report-card / bank / thesis
   pdflatex yourfile.tex          # didactic / pset / syllabus
   ```
   The split is defined in one place, `LUALATEX_CLASSES` in [`Sublime/texlib/texlib_buildspec.py`](Sublime/texlib/texlib_buildspec.py). Getting it wrong is not a soft failure: `bingo.cls` and `schedule.cls` call `\directlua` at class load, so under `pdflatex` they fatal immediately.
   `Ctrl+B` builds every variant the document supports; to build just one (student copy, solutions, instructor copy, draft) see [Build modes and variants](#build-modes-and-variants) below.

## What's in here

### Core packages (`.sty`)

| File | Purpose |
|---|---|
| [`basic-utilities.sty`](basic-utilities.sty) | Kitchen-sink utility: pulls in math/tikz/enumitem, sets up `tasks` defaults, defines a `parts` enumerate list, an `\AutoLabel` helper, and a `\fig` wrapper. |
| [`course-metadata.sty`](course-metadata.sty) | Layered metadata engine. Define `\metasetup{ institution=..., instructor=..., course-subject=..., ... }` and downstream `\Get…` commands appear. Auto-loads `coursemeta.tex` from the document directory or up to five directories up. |
| [`texlib-build.sty`](texlib-build.sty) | Unified build flags. Exposes `\ifsolutions`, `\ifkey`, `\ifsolinline`, `\ifrubric`, `\ifdraft`, `\ifstudent`, `\ifinstructor`. Toggled either compile-time (`-jobname=… "\def\ShowSolutions{}\input{file}"`) or source-level (`\solutions`, `\keys`, `\keysinline`, `\rubrics`, `\drafts`, `\studentmode`, `\instructormode`). Also the `\ifdraft` watermark and the `<base>.buildmeta` variant sidecar (`\TeXLibDeclareVariants`, `\TeXLibNoteSolution`) the build planner reads. Loaded by every class except `thesis`. |
| [`texlib-footer.sty`](texlib-footer.sty) | Shared `fancyhdr` footer: `[Course] [page X of Y] [Institution]`. Headers stay class-specific. |
| [`texlib-mathutils.sty`](texlib-mathutils.sty) | Math macros: `\mbb`/`\mrm`/`\mcal`/`\msf`/`\mf`/`\mscr`, auto-sizing `\abs`/`\lrp`/`\lrb`/`\lrcb`, `\dd`/`\deriv`/`\inte`, bold-red `\todo`. |
| [`texlib-theorems.sty`](texlib-theorems.sty) | `tcolorbox` styles for theorem environments: colored thin left-rule + ~2% background tint. Styles: `texlibtheorem` (red), `texlibproposition` (violet), `texlibdefinition` (blue), `texlibprocedure` (teal), `texlibexample` (black), `texlibquestion` (orange), `texlibnote` (gray). Customize with `\texlibtheoremsetup{rule=false, tint=false, theorem-color=…}` — toggle the left rule or tint globally, or recolor any family. |
| [`quiver.sty`](quiver.sty) | Third-party. Vendored from https://q.uiver.app for commutative-diagram support. Not covered by this repo's license — see [LICENSE](LICENSE). |

### Lua engine

- [`problem_engine.lua`](problem_engine.lua) — LuaLaTeX engine driving the shared problem-bank workflow. Handles problem-bank loading, version randomization (autoexam), per-problem SyncTeX redirection (so inverse-search lands in the bank file, not generated temp files), and the per-version page-shuffle. Loaded automatically by both the `autoexam` and `quiz` document classes.

### Tooling

- [`smoke_test.py`](smoke_test.py) — builds every per-module template and reports pass/fail. Safety net for refactors that touch shared `.sty`/`.cls` files. Usage:

  ```
  python smoke_test.py                 # all modules, default mode
  python smoke_test.py Notes Exams     # subset
  python smoke_test.py --modes all     # default + student + solutions + instructor + rubric
  ```

  Exit code is the number of failed builds.

- [`Sublime/`](Sublime/) — Sublime Text build system + LaTeXTools settings + custom builder (`texlib_builder.py`) that handles engine selection, rerun loops, the biber-skip cache, and PDF splitting (including per-version/solutions PDFs sliced out of a single combined `\versions{A,B,C}` autoexam build). See [Sublime/README.md](Sublime/README.md) for deploy instructions.

### Modules

Each module is a document class plus a README; the canonical `<module>-template.tex` files live under [`examples/templates/`](examples/templates/). `smoke_test.py` builds every module's template to catch regressions in the shared `.sty` files.

| Module | Class | Purpose |
|---|---|---|
| [`Bank/`](Bank/) | `bank.cls` | Problem-bank catalog / preview class. A thin wrapper that `\loadbank`s a bare-fragment problem bank and renders a browsable `\printbankcatalog` (number, id, attrs, stem, solution) for instructor perusal. |
| [`Bingo/`](Bingo/) | `bingo.cls` | 5×5 math-symbol bingo cards. Supports a standard layout (math expression per cell) and a labeled layout with separate `\bingolegend{...}` table, used for exam-review bingo. |
| [`Exams/`](Exams/) | `autoexam.cls` | Randomized-exam class. Paired with [`problem_engine.lua`](problem_engine.lua) and a problem `bank.tex`; emits multiple shuffled versions per build. |
| [`Notes/`](Notes/) | `didactic.cls` | Lecture-notes class with section-numbered theorems and a large theorem taxonomy (theorem, lemma, corollary, proposition, definition, procedure, example, question, note, ...). |
| [`Problem Sets/`](Problem%20Sets/) | `pset.cls` | Problem-set class with flat theorem numbering and a smaller taxonomy. |
| [`Quizzes/`](Quizzes/) | `quiz.cls` | Short-form quiz class. |
| [`Report Cards/`](Report%20Cards/) | `report-card.cls` | Per-section report-card class for end-of-term grade summaries. |
| [`Schedule/`](Schedule/) | `schedule.cls` | Course-schedule / calendar class. Uses `calendar.lua`, `date.lua`, and `schedule.lua` for date math. |
| [`Syllabi/`](Syllabi/) | `syllabus.cls` | Course-syllabus class. `syllabus-template.tex` is a complete example syllabus — course info, learning outcomes, grading, and policy statements. |
| [`Thesis/`](Thesis/) | `thesis.cls` | **Prototype.** Accessible UNR thesis/dissertation class: tagged, PDF/UA-2 + PDF/A-4f conformant, following the Graduate School filing guidelines. CI-gated, but see [`Thesis/README.md`](Thesis/README.md) for what's not yet done before treating it as final. |

Autoexam retains a set of **deprecated aliases** (`\theExamNumber`, `\theExamDate`, `\thePS`, `\examsetup`, `\examversions`, `\overview`) with no removal date: each still has dozens of live uses across existing course material, and they stay until a cross-course migration retires them (see `texlib-problembank.sty` for the removal precedent). Don't use them in new documents.

## Build modes and variants

A **variant** is one rendering of the document: the same source, a different audience. The names say who the PDF is for, not which macro produces it.

| Variant | Who it is for | Compile-time |
|---|---|---|
| *(base)* | The plain build — `<base>.pdf` | *(none)* |
| `student` | Blank answer space, name rule | `\def\StudentMode{}` |
| `solutions` | The **student's** key: answers, no grading apparatus | `\def\ShowKey{}` |
| `solutions-inline` | The same answers drawn *into* the student's blank, so the page geometry matches. Needs `{partsolution}` | `\def\ShowKeyInline{}` |
| `instructor` | Answers **plus** the rubric and common-error notes | `\def\ShowSolutions{}\def\ShowRubric{}\def\InstructorMode{}` |

`Ctrl+B` (mode `default`) builds the base PDF, then every variant the document actually supports, each with a tagged PDF/UA twin — `<base>_solutions.pdf`, `<base>_solutions_accessible.pdf`, and so on. Which variants those are is decided per document, not guessed: each class declares what it distinguishes (`\TeXLibDeclareVariants`) and each build writes a `<base>.buildmeta` sidecar recording whether the document actually contains solutions, rubrics or common-error blocks. A lecture note with no solutions in it builds one PDF and its tagged twin, and says why it built nothing else.

Other modes: `base` (the plain build alone, fully settled), `full` (every variant, skipping the content check), `quick` (one pass, references may be stale), `accessible` (normal + tagged pair), `draft` (adds a `DRAFT` watermark), and each variant name as a single-shot build.

Each tagged PDF is accompanied by `<base>_accessible-report.html` — veraPDF's PDF/UA-2 conformance report, written whether the file passes or fails, since a report naming the clauses it broke is the one worth reading. That is the artifact to hand over when someone asks for proof of accessibility (UNR requires one with a filed thesis). It needs veraPDF and a JRE; without them the build is unaffected and says the report was skipped. See `accessible_report` / `accessible_report_full` in the plugin settings.

`default_variants` in `builder_settings` (or `TEXLIB_VARIANTS`) pins the set — e.g. `["student"]` to keep `Ctrl+B` to one extra PDF, or `["base"]` for the pre-0.8.0 single-PDF behaviour.

Every class **except `thesis`** loads `texlib-build.sty` and responds to these; `thesis` loads no TeXLib package at all, so the flags do not exist in it. Source-level equivalents (`\solutions`, `\keys`, `\rubrics`, `\drafts`, `\studentmode`, `\instructormode`) can go in a document preamble instead. The Sublime build system surfaces the modes as palette entries; `smoke_test.py` injects the single-variant ones via the same compile-time mechanism.

> **Renamed in 0.8.0.** `key` → `solutions`, and what used to be `solutions` is now `instructor`. The old tokens still work and report the rename rather than silently building the wrong thing — which matters here, because `solutions` survived the rename with a *different* meaning. The underlying TeX flags (`\ifkey`, `\ifsolutions`, `\ifrubric`) are unchanged, so no document or class needed to move.

## Repo layout

```
.
├── *.sty                  # shared packages
├── problem_engine.lua     # LuaLaTeX engine shared by autoexam + quiz
├── smoke_test.py          # build-everything safety net
├── Bank/                  # bank.cls (problem-bank catalog)
├── Bingo/                 # bingo.cls
├── Exams/                 # autoexam.cls + bank
├── Notes/                 # didactic.cls
├── Problem Sets/          # pset.cls
├── Quizzes/               # quiz.cls
├── Report Cards/          # report-card.cls
├── Schedule/              # schedule.cls + lua helpers
├── Syllabi/               # syllabus.cls
├── Thesis/                # thesis.cls (prototype)
├── Sublime/               # editor build system + settings
├── examples/              # templates/ + fixtures/ + scenarios/ + end-to-end course examples, smoke-built
├── tests/                 # visual_refs/ — committed reference renders the visual CI gate diffs against
├── coursemeta.example.tex # copy-paste starter for per-course metadata
├── CHANGELOG.md
├── TODO.md
├── LICENSE
└── README.md
```

Build artifacts (`*.pdf`, `*.aux`, `*.log`, `*.out`, `*.toc`, `*.synctex.gz`, ...) and per-machine state (`*.sublime-workspace`, `*.sublime-project`) are gitignored, including those inside the module directories.

## License

MIT — see [LICENSE](LICENSE). `quiver.sty` retains its original authorship.
