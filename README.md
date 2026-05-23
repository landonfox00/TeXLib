# TeXLib

A personal LaTeX library for math teaching at the University of Nevada, Reno: shared `.sty` packages, a LuaLaTeX engine for randomized exams, a Sublime Text build system, and a smoke-test harness that builds every module after refactors.

This repository tracks only the reusable library. Course-specific materials (exams, quizzes, notes, schedules, syllabi) live alongside it locally but are intentionally gitignored.

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
├── Sublime/               # editor build system + settings
├── LICENSE
└── README.md
```

Course-material directories (`Bingo/`, `Exams/`, `Notes/`, `Problem Sets/`, `Quizzes/`, `Report Cards/`, `Schedule/`, `Syllabi/`) live alongside this tree locally but are gitignored.

## License

MIT — see [LICENSE](LICENSE). `quiver.sty` retains its original authorship.
