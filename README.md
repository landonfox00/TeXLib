# TeXLib

[![smoke](https://github.com/landonfox00/TeXLib/actions/workflows/smoke.yml/badge.svg)](https://github.com/landonfox00/TeXLib/actions/workflows/smoke.yml)
[![tests](https://github.com/landonfox00/TeXLib/actions/workflows/tests.yml/badge.svg)](https://github.com/landonfox00/TeXLib/actions/workflows/tests.yml)

A LaTeX library for teaching mathematics: shared `.sty` packages, a set of document-class modules (exams, quizzes, lecture notes, problem sets, schedules, syllabi, report cards, bingo cards, problem-bank catalogs, and a thesis class), a LuaLaTeX engine for randomized exams, and a build tool that turns one source file into every copy the course needs — student, solutions, instructor — each with a tagged PDF/UA-2 twin and a veraPDF conformance report to prove it.

It is developed at the University of Nevada, Reno and used there every semester. The one place an institution's own rules have to appear — the required policy language in a syllabus — is [chosen by profile](Syllabi/README.md#policy-statements), with an institution-neutral set shipped as the default and UNR as one profile among however many people contribute. Only [`Thesis/`](Thesis/), which encodes one Graduate School's filing requirements, is still UNR-specific.

## Quickstart

Set up TeXLib on a new machine or for a new course.

### One-time setup (per machine)

1. **Install a recent TeX Live** (2023 or later — needs `lualatex`, `expl3`, `tcolorbox`, `pgfplots`, `siunitx`, `mathrsfs`, `tikz-cd`, `spath3`). On Windows, install TeX Live full; on macOS, use MacTeX; on Linux, install `texlive-full` from your package manager.
2. **Clone this repo:**
   ```
   git clone https://github.com/landonfox00/TeXLib.git
   cd TeXLib
   ```
3. **Install the classes** so `\documentclass{didactic}` resolves in any editor:
   ```
   python texlib_cli.py install
   ```
   This copies the `.cls`/`.sty`/`.lua` files into your `TEXMFHOME` (`kpsewhich -var-value=TEXMFHOME` will tell you where that is). Re-run it after pulling library updates. `python texlib_cli.py uninstall` reverses it.

   *Developing the library itself?* Skip this — an installed copy **shadows** your working tree, so you would keep building against the last copy you installed. Put the TeXLib root on `TEXINPUTS` instead (the `texlib_cli.py` build command derives it for you, and so does the Sublime plugin). **Warning:** `kpathsea` cannot resolve `TEXINPUTS` entries containing commas, so watch for commas in any path component — on Windows that means OneDrive paths like `OneDrive - University of Nevada, Reno` need a junction; see [Sublime/README.md](Sublime/README.md).
4. **(Optional) Check the setup:**
   ```
   python texlib_cli.py doctor
   ```
   It reports the toolchain, whether veraPDF and pypdf are available, and how a build will actually resolve the classes. `python smoke_test.py` goes further and builds every module's template; exit code 0 means they all built cleanly.

### Per-course setup

1. **Make a course directory** anywhere on disk (it doesn't need to be inside TeXLib). For example:
   ```
   ~/Courses/Math181-Fall2026/
   ```
2. **Drop in a `coursemeta.tex`** with the institution / instructor / course / term values. Copy [`coursemeta.example.tex`](coursemeta.example.tex) and edit, or look at [`examples/Math181-Fall2026/`](examples/Math181-Fall2026/) for a working end-to-end course folder. `course-metadata.sty` auto-discovers this file from the document directory or any of five ancestors, so a single `coursemeta.tex` at the course root applies to every document underneath it.
3. **Pick a document class** from the [Modules](#modules) table below and start a new `.tex`:
   ```latex
   \documentclass{texlib-didactic}     % lecture notes
   % or texlib-{pset, quiz, autoexam, schedule, syllabus, report-card,
   %            bingo, bank, thesis}
   %
   % The bare names ({didactic}, {quiz}, ...) still work -- each is a
   % compatibility wrapper -- but they are too generic for a library to
   % claim, so prefer the texlib- form in new documents.
   \begin{document}
     ...
   \end{document}
   ```
4. **Build.**
   ```
   python texlib_cli.py build yourfile.tex
   ```
   That is the whole command, for every class. It picks the engine, runs the rerun-until-settled loop, runs biber when the bibliography actually changed, and produces every variant the document supports plus their tagged PDF/UA twins. `--mode solutions` (or `student`, `instructor`, `base`, `draft`, `quick`, `accessible`) builds just one; `python texlib_cli.py modes` lists them. See [Build modes and variants](#build-modes-and-variants) below, and [Using TeXLib from your editor](#using-texlib-from-your-editor) for wiring that command to a keystroke.

   From Sublime Text (with the build system from `Sublime/` installed) the same build is `Ctrl+B`.

   Calling the engine by hand works too, but then the engine choice is yours to get right:
   ```
   lualatex yourfile.tex          # autoexam / quiz / schedule / bingo / report-card / bank / thesis
   pdflatex yourfile.tex          # didactic / pset / syllabus
   ```
   The split is defined in one place, `LUALATEX_CLASSES` in [`Sublime/texlib/texlib_buildspec.py`](Sublime/texlib/texlib_buildspec.py). Getting it wrong is not a soft failure: `bingo.cls` and `schedule.cls` call `\directlua` at class load, so under `pdflatex` they fatal immediately.

## Using TeXLib from your editor

The build lives in `texlib_cli.py`, not in any editor, so wiring it up is a one-liner wherever you write.

| Editor | Wiring |
|---|---|
| **Any editor, any OS** | `python /path/to/TeXLib/texlib_cli.py build %f` |
| **Sublime Text** | Install `Sublime/` (see [Sublime/README.md](Sublime/README.md)) — `Ctrl+B`, plus completions, a bank browser, and a Doctor. |
| **VS Code** | A task in `.vscode/tasks.json` whose `command` is the line above, bound to `Ctrl+Shift+B`. |
| **Makefile / latexmk** | `%.pdf: %.tex` → the same line. Exit code is 0 on success, 1 on a build error. |
| **Overleaf** | You cannot install anything or set `TEXINPUTS` there. `python texlib_cli.py overleaf` writes a zip to upload into the project instead; the classes then work, with one PDF per compile and the source-level switches (`\solutions`, `\keys`, …) standing in for build modes. The bundle's own `README-TEXLIB.md` covers the compiler setting and the limits. |
| **CI** | Same again; `--quiet` suppresses the engine log and prints only the condensed error report. |

The Sublime plugin and the CLI are two front-ends over one build core (`TexlibBuildCore`), so a fix in the build reaches both. If they ever disagree, the core is right and one of the hosts has a bug.

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
| [`quiver.sty`](quiver.sty) | Third-party. Vendored from https://q.uiver.app for commutative-diagram support. Not covered by this repo's license — see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). |

### Lua engine

- [`problem_engine.lua`](problem_engine.lua) — LuaLaTeX engine driving the shared problem-bank workflow. Handles problem-bank loading, version randomization (autoexam), per-problem SyncTeX redirection (so inverse-search lands in the bank file, not generated temp files), and the per-version page-shuffle. Loaded automatically by both the `autoexam` and `quiz` document classes.

### Tooling

- [`texlib_cli.py`](texlib_cli.py) — the editor-independent command line. `build` (any class, any mode), `install` / `uninstall` (classes into `TEXMFHOME`), `overleaf` (a zip for a machine you cannot install on), `doctor` (what a build would use), `modes`. A host over the shared build core, not a second build implementation.

  ```
  python texlib_cli.py build exam.tex                    # every applicable variant
  python texlib_cli.py build notes.tex --mode accessible # tagged twin + veraPDF report
  python texlib_cli.py build *.tex --quiet               # errors only; exit 1 if any failed
  python texlib_cli.py overleaf                          # texlib-overleaf.zip
  ```

- [`smoke_test.py`](smoke_test.py) — builds every per-module template and reports pass/fail. Safety net for refactors that touch shared `.sty`/`.cls` files. Usage:

  ```
  python smoke_test.py                 # all modules, default mode
  python smoke_test.py Notes Exams     # subset
  python smoke_test.py --modes all     # default + student + solutions + instructor + rubric
  ```

  Exit code is the number of failed builds.

- [`Sublime/`](Sublime/) — Sublime Text build system + LaTeXTools settings + custom builder (`texlib_builder.py`) that handles engine selection, rerun loops, the biber-skip cache, and PDF splitting (including per-version/solutions PDFs sliced out of a single combined `\versions{A,B,C}` autoexam build). See [Sublime/README.md](Sublime/README.md) for deploy instructions.

### Modules

**Class and package names carry a `texlib-` prefix.** `didactic`, `quiz`,
`thesis`, `schedule`, `bank` and the rest are names no library should claim:
they collide with a file of the same name sitting next to your document, and
CTAN will not allocate them. Every old name remains as a compatibility wrapper,
so `\documentclass{didactic}` and `\RequirePackage{course-metadata}` keep
working with identical output; the wrappers are two lines each and there is
nothing in them to drift. `basic-utilities` is now `texlib-utilities` and
`course-metadata` is `texlib-coursemeta`. `quiver.sty` keeps its upstream name,
since renaming vendored third-party code would break its own documentation.


Each module is a document class plus a README; the canonical `<module>-template.tex` files live under [`examples/templates/`](examples/templates/). `smoke_test.py` builds every module's template to catch regressions in the shared `.sty` files.

| Module | Class | Purpose |
|---|---|---|
| [`Bank/`](Bank/) | `texlib-bank.cls` | Problem-bank catalog / preview class. A thin wrapper that `\loadbank`s a bare-fragment problem bank and renders a browsable `\printbankcatalog` (number, id, attrs, stem, solution) for instructor perusal. |
| [`Bingo/`](Bingo/) | `texlib-bingo.cls` | 5×5 math-symbol bingo cards. Supports a standard layout (math expression per cell) and a labeled layout with separate `\bingolegend{...}` table, used for exam-review bingo. |
| [`Exams/`](Exams/) | `texlib-autoexam.cls` | Randomized-exam class. Paired with [`problem_engine.lua`](problem_engine.lua) and a problem `bank.tex`; emits multiple shuffled versions per build. |
| [`Notes/`](Notes/) | `texlib-didactic.cls` | Lecture-notes class with section-numbered theorems and a large theorem taxonomy (theorem, lemma, corollary, proposition, definition, procedure, example, question, note, ...). |
| [`Problem Sets/`](Problem%20Sets/) | `texlib-pset.cls` | Problem-set class with flat theorem numbering and a smaller taxonomy. |
| [`Quizzes/`](Quizzes/) | `texlib-quiz.cls` | Short-form quiz class. |
| [`Report Cards/`](Report%20Cards/) | `texlib-report-card.cls` | Per-section report-card class for end-of-term grade summaries. |
| [`Schedule/`](Schedule/) | `texlib-schedule.cls` | Course-schedule / calendar class. Uses `calendar.lua`, `date.lua`, and `schedule.lua` for date math. |
| [`Syllabi/`](Syllabi/) | `texlib-syllabus.cls` | Course-syllabus class. `syllabus-template.tex` is a complete example syllabus — course info, learning outcomes, grading, and policy statements. Required policy language (`\policystatement{disability}`) resolves from your own file, then your `institution-profile`, then an institution-neutral set; see [Policy statements](Syllabi/README.md#policy-statements). |
| [`Thesis/`](Thesis/) | `texlib-thesis.cls` | **Prototype.** Accessible UNR thesis/dissertation class: tagged, PDF/UA-2 + PDF/A-4f conformant, following the Graduate School filing guidelines. CI-gated, but see [`Thesis/README.md`](Thesis/README.md) for what's not yet done before treating it as final. |

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

`default_variants` in `builder_settings` (or `TEXLIB_VARIANTS`) pins the set — e.g. `["student"]` to keep `Ctrl+B` to one extra PDF, or `["base"]` for the pre-0.8.0 single-PDF behaviour. A single document overrides everything with `\metasetup{build-variants = {student, instructor}}`, or `none` for the base PDF alone.

For a versioned exam each variant is sliced per version, so `\versions{A,B}` gives `exam_A.pdf` / `exam_B.pdf` (student), `exam_A_solutions.pdf` (the key) and `exam_A_instructor.pdf` (key plus rubric).

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
├── texlib_cli.py          # the editor-independent command line (build / install / doctor)
├── CHANGELOG.md
├── TODO.md
├── LICENSE                # plain MIT, nothing appended (detectors stop reading otherwise)
├── THIRD-PARTY-NOTICES.md # vendored code + build-time dependency licenses
└── README.md
```

Build artifacts (`*.pdf`, `*.aux`, `*.log`, `*.out`, `*.toc`, `*.synctex.gz`, ...) and per-machine state (`*.sublime-workspace`, `*.sublime-project`) are gitignored, including those inside the module directories.

## License

MIT — see [LICENSE](LICENSE). Vendored code and the build-time dependencies keep their own terms; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). `quiver.sty` in particular retains its original authorship and is not covered by this repo's license.
