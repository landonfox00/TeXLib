# TeXLib

[![smoke](https://github.com/landonfox00/TeXLib/actions/workflows/smoke.yml/badge.svg)](https://github.com/landonfox00/TeXLib/actions/workflows/smoke.yml)
[![tests](https://github.com/landonfox00/TeXLib/actions/workflows/tests.yml/badge.svg)](https://github.com/landonfox00/TeXLib/actions/workflows/tests.yml)

A personal LaTeX library for math teaching at the University of Nevada, Reno: shared `.sty` packages, a set of document-class modules (exams, quizzes, lecture notes, problem sets, schedules, syllabi, report cards, bingo cards), a LuaLaTeX engine for randomized exams, a Sublime Text build system, and a smoke-test harness that builds every module after refactors.

## Quickstart

Setting up TeXLib on a new machine or for a new course.

### One-time setup (per machine)

1. **Install a recent TeX Live** (2023 or later — needs `lualatex`, `expl3`, `tcolorbox`, `pgfplots`, `siunitx`, `mathrsfs`, `tikz-cd`, `spath3`). On Windows the easiest path is TeX Live full; on macOS use MacTeX; on Linux `texlive-full` from your package manager.
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
   Make the change permanent in your shell rc / Windows environment variables. **Watch out for commas** in any path component — `kpathsea` cannot resolve `TEXINPUTS` entries containing commas. On Windows that means OneDrive paths like `OneDrive - University of Nevada, Reno` need a junction (e.g. `OneDriveUNR`); see [Sublime/README.md](Sublime/README.md) for the workaround used in the Sublime build system.
4. **(Optional) Run the smoke test** to confirm everything builds:
   ```
   python smoke_test.py
   ```
   Exit code 0 means every module's `template.tex` built cleanly.

### Per-course setup

1. **Make a course directory** anywhere on disk (it doesn't need to be inside TeXLib). E.g.:
   ```
   ~/Courses/Math181-Fall2026/
   ```
2. **Drop in a `coursemeta.tex`** with the institution / instructor / course / term values. Copy [`coursemeta.example.tex`](coursemeta.example.tex) and edit, or look at [`examples/Math181-Fall2026/`](examples/Math181-Fall2026/) for a working end-to-end course folder. `course-metadata.sty` auto-discovers this file from the document directory or any of three ancestors, so a single `coursemeta.tex` at the course root applies to every document underneath it.
3. **Pick a document class** from the [Modules](#modules) table below and start a new `.tex`:
   ```latex
   \documentclass{didactic}        % lecture notes
   % or {pset}, {quiz}, {autoexam}, {schedule}, {syllabus}, {report-card}, {bingo}
   \begin{document}
     ...
   \end{document}
   ```
4. **Build.** From Sublime Text (with the build system from `Sublime/` installed) it's `Ctrl+B`. From the command line:
   ```
   lualatex yourfile.tex          # for autoexam / quiz / schedule
   pdflatex yourfile.tex          # for everything else
   ```
   To switch build modes (solutions, answer key, rubric, draft, student-vs-instructor copy) see [Build modes](#build-modes) below.

## What's in here

### Core packages (`.sty`)

| File | Purpose |
|---|---|
| [`basic-utilities.sty`](basic-utilities.sty) | Kitchen-sink utility: pulls in math/tikz/enumitem, sets up `tasks` defaults, defines a `parts` enumerate list, an `\AutoLabel` helper, and a `\fig` wrapper. |
| [`course-metadata.sty`](course-metadata.sty) | Layered metadata engine. Define `\metasetup{ institution=..., instructor=..., course-subject=..., ... }` and downstream `\Get…` commands appear. Auto-loads `coursemeta.tex` if found one to three directories up. |
| [`texlib-build.sty`](texlib-build.sty) | Unified build flags. Exposes `\ifsolutions`, `\ifkey`, `\ifrubric`, `\ifdraft`, `\ifstudent`, `\ifinstructor`. Toggled either compile-time (`-jobname=… "\def\ShowSolutions{}\input{file}"`) or source-level (`\solutions`, `\keys`, `\rubrics`, `\drafts`, `\studentmode`, `\instructormode`). |
| [`texlib-footer.sty`](texlib-footer.sty) | Shared `fancyhdr` footer: `[Course] [page X of Y] [Institution]`. Headers stay class-specific. |
| [`texlib-mathutils.sty`](texlib-mathutils.sty) | Math macros: `\mbb`/`\mrm`/`\mcal`/`\msf`/`\mf`/`\mscr`, auto-sizing `\abs`/`\lrp`/`\lrb`/`\lrcb`, `\dd`/`\deriv`/`\inte`, bold-red `\todo`. |
| [`texlib-theorems.sty`](texlib-theorems.sty) | `tcolorbox` styles for theorem environments: colored thin left-rule + ~2% background tint. Styles: `texlibtheorem` (red), `texlibproposition` (violet), `texlibdefinition` (blue), `texlibprocedure` (teal), `texlibexample` (black), `texlibquestion` (orange), `texlibnote` (gray). Customize with `\texlibtheoremsetup{rule=false, tint=false, theorem-color=…}` — toggle the left rule or tint globally, or recolor any family. |
| [`quiver.sty`](quiver.sty) | Third-party. Vendored from https://q.uiver.app for commutative-diagram support. Not covered by this repo's license — see [LICENSE](LICENSE). |

### Lua engine

- [`problem_engine.lua`](problem_engine.lua) — LuaLaTeX engine driving the shared problem-bank workflow. Handles problem-bank loading, version randomization (autoexam), per-problem SyncTeX redirection (so inverse-search lands in the bank file, not generated temp files), and the per-version page-shuffle. Loaded automatically by both the `autoexam` and `quiz` document classes.

### Tooling

- [`smoke_test.py`](smoke_test.py) — builds every per-module `template.tex` and reports pass/fail. Safety net for refactors that touch shared `.sty`/`.cls` files. Usage:

  ```
  python smoke_test.py                 # all modules, default mode
  python smoke_test.py Notes Exams     # subset
  python smoke_test.py --modes all     # default + student + key + solutions
  ```

  Exit code is the number of failed builds.

- [`build_versions.py`](build_versions.py) — standalone parallel builder for multi-version (`\versions{A,B,C}`) autoexam documents. Builds every version concurrently (one process each, reusing the Sublime builder's per-version pipeline so there's no logic drift), then merges them into one PDF or keeps them separate. Needs `lualatex`/`pdflatex` (+ `biber` if the exam cites) on PATH and `pypdf` for merging; no Sublime/LaTeXTools install required. Usage:

  ```
  python build_versions.py exam.tex            # combined exam.pdf
  python build_versions.py exam.tex --separate # exam_A.pdf, exam_B.pdf, ...
  python build_versions.py exam.tex --both -j 4 -v
  ```

- [`Sublime/`](Sublime/) — Sublime Text build system + LaTeXTools settings + custom builder (`texlib_builder.py`) that handles engine selection, rerun loops, the biber-skip cache, and PDF splitting. See [Sublime/README.md](Sublime/README.md) for deploy instructions.

### Modules

Each module is a document class plus a canonical `template.tex` and a README. `smoke_test.py` builds every module's `template.tex` to catch regressions in the shared `.sty` files.

| Module | Class | Purpose |
|---|---|---|
| [`Bingo/`](Bingo/) | `bingo.cls` | 5×5 math-symbol bingo cards. Supports a standard layout (math expression per cell) and a labeled layout with separate `\bingolegend{...}` table, used for exam-review bingo. |
| [`Exams/`](Exams/) | `autoexam.cls` | Randomized-exam class. Paired with [`problem_engine.lua`](problem_engine.lua) and a problem `bank.tex`; emits multiple shuffled versions per build. |
| [`Notes/`](Notes/) | `didactic.cls` | Lecture-notes class with section-numbered theorems and a large theorem taxonomy (theorem, lemma, corollary, proposition, definition, procedure, example, question, note, ...). |
| [`Problem Sets/`](Problem%20Sets/) | `pset.cls` | Problem-set class with flat theorem numbering and a smaller taxonomy. |
| [`Quizzes/`](Quizzes/) | `quiz.cls` | Short-form quiz class. |
| [`Report Cards/`](Report%20Cards/) | `report-card.cls` | Per-section report-card class for end-of-term grade summaries. |
| [`Schedule/`](Schedule/) | `schedule.cls` | Course-schedule / calendar class. Uses `calendar.lua`, `date.lua`, and `schedule.lua` for date math. |
| [`Syllabi/`](Syllabi/) | `syllabus.cls` | Course-syllabus class. `Syllabus_Template.tex` is the canonical filled-in example; `template.tex` is the minimal smoke-test variant. |

## Build modes

Every TeXLib document class loads `texlib-build.sty`, so they all respond to the same flags:

| Flag | Source-level | Compile-time |
|---|---|---|
| Show solutions | `\solutions` | `\def\ShowSolutions{}` |
| Show answer key | `\keys` | `\def\ShowKey{}` |
| Show rubric | `\rubrics` | `\def\ShowRubric{}` |
| Draft watermark | `\drafts` | `\def\ShowDraft{}` |
| Student copy | `\studentmode` | `\def\StudentMode{}` |
| Instructor copy | `\instructormode` | `\def\InstructorMode{}` |

The Sublime build system surfaces these as palette entries; `smoke_test.py` injects them via the same compile-time mechanism.

## Repo layout

```
.
├── *.sty                  # shared packages
├── problem_engine.lua     # LuaLaTeX engine shared by autoexam + quiz
├── smoke_test.py          # build-everything safety net
├── Bingo/                 # bingo.cls + template
├── Exams/                 # autoexam.cls + bank + template
├── Notes/                 # didactic.cls + template
├── Problem Sets/          # pset.cls + template
├── Quizzes/               # quiz.cls + preamble + template
├── Report Cards/          # report-card.cls + template
├── Schedule/              # schedule.cls + lua helpers + template
├── Syllabi/               # syllabus.cls + Syllabus_Template + template
├── Sublime/               # editor build system + settings
├── examples/              # end-to-end course examples (Math181-Fall2026, ...)
├── coursemeta.example.tex # copy-paste starter for per-course metadata
├── CHANGELOG.md
├── TODO.md
├── LICENSE
└── README.md
```

Build artifacts (`*.pdf`, `*.aux`, `*.log`, `*.out`, `*.toc`, `*.synctex.gz`, ...) and per-machine state (`*.sublime-workspace`, `*.sublime-project`) are gitignored, including those inside the module directories.

## License

MIT — see [LICENSE](LICENSE). `quiver.sty` retains its original authorship.
