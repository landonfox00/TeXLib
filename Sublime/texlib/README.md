# TeXLib — native Sublime Text package

The native "complement, not replace" plugin from
[`../PLUGIN-DESIGN.md`](../PLUGIN-DESIGN.md). It **owns the build** and adds
TeXLib-domain commands, while **delegating editor smarts** (PDF viewer, forward
sync, word count, TOC, jump-to-ref) to LaTeXTools by stable command name — never
by importing its internals. Nothing here needs LaTeXTools to *build*; it's a
companion we call.

## Commands

All are in the Command Palette (`Ctrl+Shift+P` → "TeXLib: …") and under
**Tools → TeXLib**. Build/pick are also bound to `Ctrl+B` / `Ctrl+Shift+B` for
`.tex` files.

| Command | What it does |
|---------|--------------|
| **Build** / **Build — Pick Mode** | Native build (default, or key/solutions/student/rubric/draft/quick). A status-bar spinner shows the current step; the panel pops only on failure. On success, opens/forward-syncs the PDF via LaTeXTools. |
| **Cancel Build** / **Cancel All Builds** / **Build Status** | Cancel this document's build, cancel every running build, or list running builds (documents build in parallel). |
| **View PDF** / **Forward Sync** / **Show Build Output** | Delegate to LaTeXTools' `view_pdf` / `jumpto_pdf`; or re-open this document's build panel. |
| **Word Count** / **Table of Contents** / **Jump to \ref / \cite** | Delegate to LaTeXTools' `texcount` / `toc_quickpanel` / `jumpto_anywhere`. |
| **New Document** | Scaffold from a `<class>-template.tex`. |
| **Go to / Insert Bank Problem** / **Insert Problem by Topic** | Scan the doc + its banks for `\begin{problem}{id}`; jump to a definition, insert `\getproblem{id}`, or filter by a topic first. |
| **Bank Report** / **Bank Preview** | Coverage report (unused / duplicate / dangling ids, topic & difficulty distribution); or build a `\printbankcatalog` PDF via `\documentclass{bank}`. |
| **Open coursemeta.tex** / **Show Resolved Metadata** | Open the governing metadata file; or show every resolved field (reads the `.metadump` sidecar the build writes). |
| **Reveal / Clean Aux Directory** | Open or delete the build's `%TEMP%\texlib-aux\<hash>`. |
| **Package for LMS** | Run `package_for_lms.py` on the active course. |
| **Uninstall Classes from TEXMF** | Remove a stale TeXLib copy from `TEXMFHOME` so builds resolve from your live checkout (via `texinputs`) instead of a shadowing install. System-wide install is the standalone **TeXLib-Installer**'s job. |
| **Doctor** | Check the toolchain (lualatex / biber / synctex / pypdf), the `texinputs` setting, coursemeta resolution, and whether a TEXMF install shadows your checkout. |
| **Toggle Build on Save** / **Edit Settings** | Enable opt-in build-on-save; open the split default \| user settings. |

Plus **completions** (`\getproblem`/`\setvar`/… after `\`; problem ids inside
`\getproblem{…}`; coursemeta keys inside `\metasetup{…}`) and **snippets**
(`problem`, `solution`, `parts`, `questions`, `getproblem`, `versions`).

## Files

Each `texlib_*.py` is a top-level plugin, so it hot-reloads on save
independently.

| File | Role |
|------|------|
| `texlib.py` | Build runner + async driver + status-bar spinner + LaTeXTools delegation. |
| `texlib_build.py` | `TexlibBuildCore` (the one build brain) + native `TexlibBuild`. |
| `texlib_editor.py` | Word count / TOC / jump-to-ref delegations + Edit Settings. |
| `texlib_bank.py` | Bank navigation (go-to / insert). |
| `texlib_topic.py` | Insert a bank problem by topic. |
| `texlib_bankreport.py` | Bank coverage report + bank preview. |
| `texlib_meta.py` | Show resolved metadata (reads the `.metadump`). |
| `texlib_complete.py` | Macro + problem-id + coursemeta-key completions. |
| `texlib_scaffold.py` | New-document scaffolding. |
| `texlib_locate.py` | Open coursemeta / reveal aux dir. |
| `texlib_utils.py` | Clean aux dir, package for LMS. |
| `texlib_onsave.py` | Opt-in build-on-save. |
| `texlib_texmf.py` | Uninstall a stale class copy from TEXMF (un-shadow the checkout). |
| `texlib_doctor.py` | Build-environment check. |
| `texlib_pdfpost.py` | External-Python pypdf helper (PDF split/slice). |
| `snippets/` | `.sublime-snippet` files. |
| `messages.json`, `messages/` | Package Control install/upgrade messages. |
| `Default.sublime-commands`, `Default (Windows).sublime-keymap`, `Main.sublime-menu`, `TeXLib.sublime-settings` | Palette, keys, menu, settings. |

## Settings (`TeXLib.sublime-settings`)

Machine-local values belong in `Packages/User/TeXLib.sublime-settings` (open the
split view with **Edit Settings**).

- `texinputs` — the child engine's `TEXINPUTS`; how builds resolve the classes.
  Point it at the comma-free repo checkout. No TEXMF install is needed.
- `open_pdf_on_build` — open/refresh + forward-sync the PDF after a build (default true).
- `show_panel_on_build` — `"errors"` (default), `"always"`, or `"never"`.
- `build_on_save` — rebuild on every save (default false; use Toggle Build on Save).
- `class_source` — path to the TeXLib repo (for LMS packaging / coursemeta key
  completions), if auto-detection can't find it.

## Deploy / test

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy-plugin.ps1   # junction into Packages/TeXLib
```

Restart Sublime once after adding **new** plugin files; edits to existing
top-level `texlib_*.py` hot-reload. Every domain command has a headless test
suite in `../` (`test_texlib_*.py`) — no TeX toolchain needed.

## Distribution

The package ships via a **Package Control custom repository** (auto-update) — see
`../PLUGIN-DESIGN.md §12`. LaTeXTools is listed as a companion. The
**TeXLib-Installer** remains the editor-agnostic, system-wide channel; this
plugin resolves classes from your checkout via `texinputs` and never copies them
into TEXMF.

## Relationship to the LaTeXTools builder

`../texlib_builder.py` is a thin LaTeXTools **adapter** over the same
`TexlibBuildCore` — one source of build logic, nothing to drift. `Ctrl+B` runs
the native path; `Tools → Build With → TeXLib` runs the adapter.
