# TeXLib — native Sublime Text package

The native "complement, not replace" plugin from
[`../PLUGIN-DESIGN.md`](../PLUGIN-DESIGN.md). It **owns the build** and adds
TeXLib-domain commands, while **delegating editor smarts** (PDF viewer, forward
sync) to LaTeXTools by stable command name — never by importing its internals.
Nothing here needs LaTeXTools to *build*; it's a companion we call.

## Commands

All are in the Command Palette (`Ctrl+Shift+P` → "TeXLib: …") and under
**Tools → TeXLib**. Build/pick are also bound to `Ctrl+B` / `Ctrl+Shift+B` for
`.tex` files.

| Command | What it does |
|---------|--------------|
| **Build** / **Build — Pick Mode** | Native build (default, or key/solutions/student/rubric/draft/quick). Streams to its own panel, reruns for cross-refs, biber cache, autoexam version slicing, publish. On success, opens/forward-syncs the PDF via LaTeXTools. |
| **Cancel Build** | Kill the running build. |
| **View PDF** / **Forward Sync** | Delegate to LaTeXTools' `view_pdf` / `jumpto_pdf`. |
| **New Document** | Scaffold from a `<class>-template.tex`. |
| **Go to / Insert Bank Problem** | Scan the doc + its banks for `\begin{problem}{id}`; jump to a definition or insert `\getproblem{id}`. |
| **Open coursemeta.tex** | Open the governing metadata file (walks up to 4 parents). |
| **Reveal / Clean Aux Directory** | Open or delete the build's `%TEMP%\texlib-aux\<hash>`. |
| **Package for LMS** | Run `package_for_lms.py` on the active course. |
| **Install Classes to TEXMF** | Copy the `.cls/.sty/.lua` payload into `TEXMFHOME` so *all* TeX tools (CLI, other editors, CI) find them — the installer's job, for this machine. |

Plus **completions** (`\getproblem`/`\setvar`/… after `\`; problem ids inside
`\getproblem{…}`) and **snippets** (`problem`, `solution`, `parts`, `questions`,
`getproblem`, `versions`).

## Files

Each `texlib_*.py` is a top-level plugin, so it hot-reloads on save
independently.

| File | Role |
|------|------|
| `texlib.py` | Build runner + async driver + LaTeXTools delegation. |
| `texlib_build.py` | `TexlibBuildCore` (the one build brain) + native `TexlibBuild`. |
| `texlib_bank.py` | Bank navigation (go-to / insert). |
| `texlib_complete.py` | Macro + problem-id completions. |
| `texlib_scaffold.py` | New-document scaffolding. |
| `texlib_locate.py` | Open coursemeta / reveal aux dir. |
| `texlib_utils.py` | Clean aux dir, package for LMS. |
| `texlib_texmf.py` | Install classes to TEXMF. |
| `texlib_pdfpost.py` | External-Python pypdf helper (PDF split/slice). |
| `snippets/` | `.sublime-snippet` files. |
| `Default.sublime-commands`, `Default (Windows).sublime-keymap`, `Main.sublime-menu`, `TeXLib.sublime-settings` | Palette, keys, menu, settings. |

## Settings (`TeXLib.sublime-settings`)

Machine-local values belong in `Packages/User/TeXLib.sublime-settings`.

- `texinputs` — value for the child engine's `TEXINPUTS` (point at the comma-free
  repo root so shared `.sty` resolve).
- `open_pdf_on_build` — open/refresh + forward-sync the PDF after a build (default true).
- `publish_shareable_copies` / `copy_published_path_to_clipboard` — publish toggles.
- `class_source` — path to the TeXLib repo (for scaffolding / TEXMF install / LMS),
  if auto-detection can't find it.

## Deploy / test

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy-plugin.ps1   # junction into Packages/TeXLib
```

Restart Sublime once after adding **new** plugin files; edits to existing
top-level `texlib_*.py` hot-reload. The build core and every domain command have
headless test suites in `../` (`test_texlib_*.py`) — no TeX toolchain needed.

## Relationship to the LaTeXTools builder

`../texlib_builder.py` is now a thin LaTeXTools **adapter** over the same
`TexlibBuildCore` — one source of build logic, nothing to drift. `Ctrl+B` runs
the native path; `Tools → Build With → TeXLib` runs the adapter.
