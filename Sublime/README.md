# TeXLib — Sublime Text setup

This folder holds the canonical Sublime Text configuration for working with
the TeXLib library: a custom LaTeXTools builder, the build system that drives
it, and the editor settings. It replaces the old split `Sublime/` +
`SublimeUser/` folders (which had drifted into duplicates, stale `landonf`
machine paths, two overlapping build scripts, and `__pycache__` junk).

## What's here

| File | Deploy to | Purpose |
|------|-----------|---------|
| `texlib_builder.py` | `Packages/User/` | The custom LaTeXTools builder (`builder: "texlib"`). |
| `TeXLib.sublime-build` | `Packages/User/` | Build system + the mode-picker variants. |
| `LaTeXTools.sublime-settings` | `Packages/User/` | LaTeXTools config: engine path, `texlib` builder, comma-safe `TEXINPUTS`. |
| `Preferences.sublime-settings` | `Packages/User/` | Editor prefs: `font_size` 10, full `added_words` / `ignored_words` lists. |
| `Default (Windows).sublime-keymap` | `Packages/User/` | Personal Windows keybindings (currently all commented). |
| `Default.sublime-commands` | `Packages/User/` | Command-palette entries for the build modes. |
| `Package Control.sublime-settings` | `Packages/User/` | Installed-packages list (LaTeXTools, Package Control, PowerShell, UnitTesting). |
| `test_texlib_builder.py` | — (not deployed) | Standalone logic test for the builder. Run with `python test_texlib_builder.py`. |
| `README.md` | — | This file. Not deployed. |

**Important about the LaTeXTools settings filename.** If Sublime ever closes
with unsaved edits to `LaTeXTools.sublime-settings`, it leaves a recovery copy
named `LaTeXTools-<hash>.sublime-settings`. Always deploy as the bare name
`LaTeXTools.sublime-settings` — anything with a hash suffix is auto-recovery
junk, not the canonical file. If you find one in your `Packages/User/`, the
real config is whichever name Sublime is actually reading; check by editing
one and seeing whether the build behavior changes.

## Deploy

1. In Sublime Text: **Preferences → Browse Packages…** — this opens the
   `Packages/` folder.
2. Copy every file above (except this README) into `Packages/User/`.
3. **Tools → Build System → TeXLib**.
4. Restart Sublime (so the builder plugin loads).

That's it on each machine. The files live here in the (OneDrive-synced) TeXLib
folder so they travel with the library; deploying is just the copy step above.
If you'd rather not copy by hand, ask and we'll add a small deploy script.

## Using it

Open any TeXLib document (`autoexam`, `quiz`, `didactic`, `pset`, `schedule`,
`syllabus`, `report-card`, `bingo`) and:

- **`Ctrl+B`** — build in the default mode.
- **`Ctrl+Shift+B`** — pick a build mode:
  - **Answer Key** — injects `\def\ShowKey{}`
  - **Solutions** — injects `\def\ShowSolutions{}`
  - **Student Copy** — injects `\def\StudentMode{}`
  - **Rubric** — injects `\def\ShowRubric{}`
  - **Draft** — injects `\def\ShowDraft{}`
  - **Quick** — a single engine pass, no biber, no rerun loop; for fast preview
    while writing. Cross-references / citations may be stale — run a normal
    build to settle them before sharing.
- The same modes are in the **command palette** (`Ctrl+Shift+P` → type "TeXLib").
- For `autoexam` documents with `\versions{A,B,C,...}`, a normal default build
  already produces `<base>_A.pdf`, `<base>_B.pdf`, … (and `_solutions` copies
  under dual/only `\solutions` mode) alongside the combined `<base>.pdf` — see
  **Per-version/solutions PDF slicing** below. No separate mode needed.

You never edit the `.tex` to switch modes — the builder injects the flag on the
command line, exactly the way `smoke_test.py` does.

## What the builder does

- **Engine selection.** Honors the `%!TeX program = …` magic comment (LaTeXTools
  resolves that for us). On top of that, it forces `lualatex` for
  `\documentclass{autoexam|quiz|schedule}`, which require it — so a document
  that forgot the magic comment still builds correctly. Plain `pdflatex`
  documents are untouched.
- **Cross-reference reruns.** Re-runs the engine (up to 3×) while the log still
  says "Rerun to get cross-references right."
- **biber change-detection.** For biblatex documents, biber (and its forced
  re-pass) only runs when the `.bcf` changed since the `.bbl` was last built —
  the hash is cached in the aux dir. Editing prose no longer pays for a biber
  run plus an extra engine pass on every build; touch a `\cite` or the
  bibliography and it re-runs automatically.
- **PDF splitting.** If the engine drops a `<base>.spl` file containing
  `split_page=N`, the builder splits `<base>.pdf` into `<base>_Exam.pdf` and
  `<base>_Solutions.pdf` (the autoexam key-build workflow). Needs `pypdf`.
- **Per-version/solutions PDF slicing.** For `autoexam` documents with
  `\versions{A,B,C,...}` (or dual/only `\solutions` mode), a normal build
  compiles every version/copy into ONE combined PDF, then slices
  `<base>_A.pdf`, `<base>_B.pdf`, `<base>_A_solutions.pdf`, … out of it
  afterward, keyed off a `<base>.vmap` sidecar autoexam writes per copy — no
  separate recompile per version. Needs `pypdf`.
- **Tidy.** Hides the `<base>.synctex.gz` artifact on Windows.

It folds in the useful logic from the three retired scripts: `onetex_build.py`
(engine detection, rerun loop), `OneTeXBuilder.py` (synctex hiding), and
`autoexam.py` (version loop, PDF split).

## Testing

The builder has three layers of automated tests (none deployed to Sublime):

| Script | Needs TeX? | Covers |
|--------|-----------|--------|
| `test_texlib_builder.py` | No | Decision logic + **full multi-pass orchestration** (biber-skip cache, rerun detection, `MAX_RERUNS` cap, per-version biber, aux routing, hidden-file recovery, schedmap rewrite, per-version/solutions `.vmap` PDF slicing). Drives `commands()` with a scripted side-effect timeline so the biber/rerun branches actually execute. |
| `test_biber_integration.py` | Yes (`pdflatex`/`lualatex` + `biber`) | Real end-to-end: drives the actual builder coroutine against the real toolchain on a biblatex fixture. Proves a fresh build settles with no undefined refs, an unchanged rebuild **skips biber** in one pass, and editing the `.bib` re-runs biber. Soft-skips if the tools are absent. |
| `test_synctex_integration.py` | Yes (`lualatex` + poppler's `pdftotext` + `synctex`) | Real end-to-end **inverse search**: drives the real builder against a real build, then uses TeX Live's own `synctex edit -o page:x:y:pdf` CLI to simulate a Sumatra double-click and check where it actually lands — the fabricated-data unit tests above can't catch a real engine/table-package quirk (e.g. xltabular deferring shipout) that only shows up against genuine output. Soft-skips if the tools (or a poppler-flavored `pdftotext` specifically — an xpdf build earlier on `PATH` silently lacks `-bbox`) are absent. |
| `smoke_test.py` (repo root) | Yes (`lualatex`) | Builds every module template; content/visual regression for shared `.sty`/`.cls` refactors. |

Run them directly:

```sh
python Sublime/test_texlib_builder.py        # fast, no TeX
python Sublime/test_biber_integration.py     # real pdflatex + biber
python Sublime/test_synctex_integration.py   # real lualatex + synctex CLI
python smoke_test.py                          # full template builds
```

`.github/workflows/tests.yml` runs the no-TeX logic suite on every push, plus
an integration job that installs TeX Live + biber.

## Notes

- **LaTeXTools version.** `texlib_builder.py` imports `PdfBuilder` from the
  modern LaTeXTools layout (`plugins/builder/`), falling back to the legacy
  layout (`builders/`). If neither import works you'll get a clear error at
  load time — update LaTeXTools and restart.
- **The `TEXINPUTS` comma trap.** kpathsea cannot resolve a `TEXINPUTS` entry
  containing a comma, and the real OneDrive folder name has one. The
  `LaTeXTools.sublime-settings` here points `TEXINPUTS` at the **`OneDriveUNR`**
  junction (comma-free) instead. Keep that junction in place, or builds won't
  find the consolidated shared `.sty`/`.lua` files at the TeXLib root.
- **Build system conflicts.** If "Automatic" build keeps picking LaTeXTools'
  own `LaTeX` build system instead of this one, explicitly select
  **Tools → Build System → TeXLib**.
