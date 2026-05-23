# TeXLib

A personal LaTeX library for math teaching at the University of Nevada, Reno: shared `.sty` packages, a set of document-class modules (exams, quizzes, lecture notes, problem sets, schedules, syllabi, report cards, bingo cards), a LuaLaTeX engine for randomized exams, a Sublime Text build system, and a smoke-test harness that builds every module after refactors.

## What's in here

### Core packages (`.sty`)

| File | Purpose |
|---|---|
| [`basic-utilities.sty`](basic-utilities.sty) | Kitchen-sink utility: pulls in math/tikz/enumitem, sets up `tasks` defaults, defines a `parts` enumerate list, an `\AutoLabel` helper, and a `\fig` wrapper. |
| [`course-metadata.sty`](course-metadata.sty) | Layered metadata engine. Define `\metasetup{ institution=..., instructor=..., course-subject=..., ... }` and downstream `\Get…` commands appear. Auto-loads `coursemeta.tex` if found one to three directories up. |
| [`texlib-build.sty`](texlib-build.sty) | Unified build flags. Exposes `\ifsolutions`, `\ifkey`, `\ifrubric`, `\ifdraft`, `\ifstudent`, `\ifinstructor`. Toggled either compile-time (`-jobname=… "\def\ShowSolutions{}\input{file}"`) or source-level (`\solutions`, `\keys`, `\rubrics`, `\drafts`, `\studentmode`, `\instructormode`). |
| [`texlib-footer.sty`](texlib-footer.sty) | Shared `fancyhdr` footer: `[Course] [page X of Y] [Institution]`. Headers stay class-specific. |
| [`texlib-mathutils.sty`](texlib-mathutils.sty) | Math macros: `\mbb`/`\mrm`/`\mcal`/`\msf`/`\mf`/`\mscr`, auto-sizing `\abs`/`\lrp`/`\lrb`/`\lrcb`, `\dd`/`\deriv`/`\inte`, bold-red `\todo`. |
| [`texlib-theorems.sty`](texlib-theorems.sty) | `tcolorbox` styles for theorem environments: colored thin left-rule + ~2% background tint. Styles: `texlibtheorem` (red), `texlibproposition` (violet), `texlibdefinition` (blue), `texlibprocedure` (teal), `texlibexample` (black), `texlibquestion` (orange), `texlibnote` (gray). |
| [`quiver.sty`](quiver.sty) | Third-party. Vendored from https://q.uiver.app for commutative-diagram support. Not covered by this repo's license — see [LICENSE](LICENSE). |

### Lua engine

- [`autoexam_engine.lua`](autoexam_engine.lua) — LuaLaTeX engine extracted from `autoexam.cls`. Handles problem-bank loading, version randomization, per-problem SyncTeX redirection (so inverse-search lands in the bank file, not generated temp files), and the per-version page-shuffle. Loaded automatically by the `autoexam` document class.

### Tooling

- [`smoke_test.py`](smoke_test.py) — builds every per-module `template.tex` and reports pass/fail. Safety net for refactors that touch shared `.sty`/`.cls` files. Usage:

  ```
  python smoke_test.py                 # all modules, default mode
  python smoke_test.py Notes Exams     # subset
  python smoke_test.py --modes all     # default + student + key + solutions
  ```

  Exit code is the number of failed builds.

- [`Sublime/`](Sublime/) — Sublime Text build system + LaTeXTools settings + custom builder (`texlib_builder.py`) that handles engine selection, rerun loops, and PDF splitting. See [Sublime/README.md](Sublime/README.md) for deploy instructions.

### Modules

Each module is a document class plus a canonical `template.tex` and a README. `smoke_test.py` builds every module's `template.tex` to catch regressions in the shared `.sty` files.

| Module | Class | Purpose |
|---|---|---|
| [`Bingo/`](Bingo/) | `bingo.cls` | 5×5 math-symbol bingo cards. Supports a standard layout (math expression per cell) and a labeled layout with separate `\bingolegend{...}` table, used for exam-review bingo. |
| [`Exams/`](Exams/) | `autoexam.cls` | Randomized-exam class. Paired with [`autoexam_engine.lua`](autoexam_engine.lua) and a problem `bank.tex`; emits multiple shuffled versions per build. |
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
├── autoexam_engine.lua    # LuaLaTeX engine for randomized exams
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
├── TODO.md
├── LICENSE
└── README.md
```

Build artifacts (`*.pdf`, `*.aux`, `*.log`, `*.out`, `*.toc`, `*.synctex.gz`, ...) and per-machine state (`*.sublime-workspace`, `*.sublime-project`) are gitignored, including those inside the module directories.

## License

MIT — see [LICENSE](LICENSE). `quiver.sty` retains its original authorship.
