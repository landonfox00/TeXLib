# TeXLib Sublime Plugin — Design

Status: **draft / pre-development.** No code written yet. This documents the
intended shape so we can react to it before committing effort.

Worktree: `C:\Users\Landon\texlib-sublime-wt`, branch `feat/sublime-plugin`
(off `main`), isolated from the in-progress `fix/pset-solution-tab-gotcha` tree.

---

## 1. Intent

Convert the TeXLib **build layer** from a LaTeXTools-hosted custom builder into a
self-contained **native Sublime Text package** that *complements* LaTeXTools:

- **Own** the build entry point (our own command, panel, keymap, deploy story).
- **Add** TeXLib-domain commands LaTeXTools has no concept of.
- **Delegate** editor intelligence (completions, log parsing, SyncTeX) to
  LaTeXTools via its **stable `run_command` names**, not fragile internal imports.

We become the *driver*; LaTeXTools becomes a *library we call*. Coupling moves
from brittle Python imports to documented command names — a net ownership win.

## 2. Goals / non-goals

**Goals**
- Ownership: no dependence on LaTeXTools' internal `PdfBuilder` API or its
  private `Popen`; coupling only through public command names.
- Deploy/distribution: top-level plugin hot-reloads on save (no restart); ship
  as one installable package to coworkers.
- Elevation: first-class TeXLib commands (scaffolding, coursemeta, bank).

**Non-goals**
- Replacing LaTeXTools. It stays installed for editor smarts.
- Rebuilding completions, the TeX log parser, or SyncTeX viewer wiring from
  scratch.
- Any change to the Lua/TeX engine layer (`problem_engine.lua`, the `.cls`
  files, the Python build scripts' core logic).

## 3. Why this is cheap — the measured coupling

`texlib_builder.py` (77 KB) was measured against the live source:

- **Zero `import sublime` / `import sublime_plugin`.** The file is already
  Sublime-agnostic.
- It **never assigns** its own root/name/engine — those are inherited from
  `PdfBuilder`. The *entire* contract it consumes is:

  | Symbol | Uses | Role |
  |---|---|---|
  | `self.display(text)` | 23 | Append to the build panel |
  | `self.tex_root` / `tex_name` | few | Root path (read once) |
  | `self.engine` | 2 | Resolved `%!TeX program` |
  | `self.options` | 3 | The `--texlib-mode=` variant args |
  | `self.base_name` | 16 | Base filename |
  | `yield (argv, msg)` protocol | ~10 | LaTeXTools runs argv, pumps output, resumes |

  Every `self._*` name (dozens) is our own method.

**Implication:** ~95 % of the builder is portable **verbatim**. Cutting
LaTeXTools loose means re-providing ~6 symbols + a coroutine host — a bounded,
~150–250-line surface — not a rewrite.

## 4. Architecture

```
┌───────────────────────── TeXLib package (native, ours) ──────────────────────┐
│                                                                               │
│  Build:      texlib_build (WindowCommand)  ── mode picker, output panel       │
│  Runner:     async driver — Popen each yielded argv, stream, cancel/kill,     │
│              resume the ported commands() coroutine                           │
│  Logic:      ported build brain (engine force, mode inject, biber cache,      │
│              rerun loop, .vmap slice, aux routing, publish)  ← verbatim        │
│  Domain:     new-doc scaffold, coursemeta, bank insert/goto, versions, LMS    │
│  Editor:     LaTeX.sublime-settings, snippets, TeXLib-macro completions       │
│  Delegation: thin run_command shims → LaTeXTools editor commands              │
│                                                                               │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │ run_command("latextools_*")   (stable)
                                     ▼
┌───────────────────── LaTeXTools (installed, unchanged) ──────────────────────┐
│  Passive: \ref/\cite/\includegraphics completions, env-closing (event         │
│           listeners — fire on their own; we keep them by keeping LT installed) │
│  Callable: jumpto_pdf, view_pdf, texcount, toc_quickpanel, ...                 │
│  Optional: parseTeXlog (log→clickable errors) — see Risk #1                    │
└───────────────────────────────────────────────────────────────────────────────┘
```

## 5. The conversion seam — three tiers

**Tier A — transfers verbatim (the 95 %).** All decision logic: engine forcing,
mode extraction, biber change-detection cache, rerun loop, `.vmap` version
slicing, `.spl` split, aux routing, the publish step, and the
`texlib_pdfpost.py` external-pypdf shell-out (Sublime's embedded Python still
has no pypdf — constraint unchanged, already handled out-of-process). Touches
nothing but `self.display` and the argv it yields.

**Tier B — must be rebuilt (~150–250 lines, the "host").** What `PdfBuilder`
provides free today:
- Resolve `root` / `base_name` / `engine` from the active view + a `%!TeX
  program` regex (trivial; single-file docs → root *is* the file).
- An output view + `result_file_regex` for clickable errors.
- The **async driver**: consume `commands()`, spawn each yielded argv via
  `Popen`, stream stdout to the panel, handle cancel→kill, resume the generator,
  and thread results back (the existing `inner.send((yield item))` pattern is
  preserved — the host just needs to feed it).
- A `display()` equivalent.

**Tier C — delegate, never rebuild.** Editor intelligence stays LaTeXTools':
call its commands from our keymap; keep passive completions by keeping LT
installed.

## 6. Package layout (deployable)

A proper package folder (becomes `Packages/TeXLib/`), deployed by **directory
junction** (`mklink /J`) instead of copy — live edits, hot-reload on save, no
more redeploy+restart dance:

```
Sublime/texlib/                     ← dev source; junction → Packages/TeXLib
  texlib.py                         ← top-level: commands, event listeners, async runner
  texlib_build.py                   ← ported build brain (was texlib_builder.py − PdfBuilder)
  texlib_pdfpost.py                 ← unchanged external pypdf helper
  Default (Windows).sublime-keymap  ← build + delegation bindings
  Default.sublime-commands          ← palette entries
  Main.sublime-menu                 ← menu
  LaTeX.sublime-settings            ← syntax settings (moved out of Sublime/)
  snippets/ , completions           ← TeXLib-macro editing aids
```

Naming follows repo convention: package/command **identifiers** dashed where
user-facing; Python **modules** underscored (backend, not referenced from
`.tex`). Personal `Preferences.sublime-settings` / spell-check words stay
*out* of the shippable bundle (see §12).

## 7. Commands

**Build**
- `texlib_build` (WindowCommand, arg `mode`) — replaces the
  `latextools_make_pdf` build target. Same modes as today
  (default/key/solutions/student/rubric/draft/quick) via a **quick-panel picker**
  with descriptions (richer than the current `.sublime-build` variant list).

**Domain (the elevation — new capability)**
- `texlib_new_document` — pick a class → scaffold the template with coursemeta
  wired.
- `texlib_show_metadata` / `texlib_open_coursemeta` — resolve & display the
  governing `coursemeta.tex`, jump to `\GetCourseMetaDir`.
- `texlib_insert_problem` / `texlib_goto_problem` — bank-aware: list/insert
  `\begin{problem}{id}` from the resolved bank.
- `texlib_build_versions`, `texlib_publish`, `texlib_package_lms` — first-class
  wrappers over the existing `build_versions.py` / publish / `package_for_lms.py`.

**Delegation (thin `run_command` shims or direct keymap)**
- forward sync → `latextools_jumpto_pdf`
- open/refresh viewer → `latextools_view_pdf`
- word count → `latextools_texcount`
- TOC nav → `latextools_toc_quickpanel`

## 8. Delegation table (verified command names)

Pulled from the installed `LaTeXTools.sublime-package`:

| Command | Class | Purpose |
|---|---|---|
| `latextools_jumpto_pdf` | `LatextoolsJumptoPdfCommand` | Forward SyncTeX: source → PDF |
| `latextools_view_pdf` | `LatextoolsViewPdfCommand` | Open PDF in viewer |
| `latextools_jumpto_anywhere` | `LatextoolsJumptoAnywhereCommand` | Jump to ref/cite/file/env under cursor |
| `latextools_texcount` | `LatextoolsTexcountCommand` | Word count |
| `latextools_toc_quickpanel` | `LatextoolsTocQuickpanelCommand` | TOC navigation |
| `latextools_reveal_aux_directory` | `LatextoolsRevealAuxDirectoryCommand` | Open aux dir |

`run_command` is **fire-and-forget / async** — no return value. We can *trigger*
these but not compose on their results; anything needing a return uses our own
code, not a delegated call.

## 9. Risks / open questions (ranked)

1. **Log → clickable errors.** **DECIDED (2026-07-10): regex + `-file-line-error`.**
   Add `-file-line-error` to the base engine flags so errors emit
   `./file.tex:42: message`, linked by a `result_file_regex` (identical to the
   current `.sublime-build`) — zero LaTeXTools coupling. Rationale: the value of
   a full parser (`parseTeXlog`) is mostly robust *multi-file* handling, and the
   tree is single-file (no `%!TeX root`). Rejected: importing `parseTeXlog`
   (reintroduces the fragile coupling we're removing). The seam is isolated —
   **escalate to a vendored parser** only if the regex misses too much in real
   use (errors without file:line, warnings-as-nav). Phase 1 must confirm
   `-file-line-error` doesn't perturb the ported rerun/biber detection regexes
   (it shouldn't — those match "Rerun to get…"/biber strings, orthogonal to it).
2. **Async driver correctness.** New, currently-untested surface (threading,
   `sublime.set_timeout`, panel writes, kill-on-cancel). Easy to ship bugs:
   zombie engine processes on cancel, interleaved output. Needs dedicated tests
   the current suite doesn't have.
3. **Forward SyncTeX handoff.** `latextools_jumpto_pdf` may assume LT knows the
   output dir. Our aux-routing copies PDF/synctex back next to source, so it
   *should* line up — **verify it lands**; re-point `test_synctex_integration.py`
   at the new command.
4. **Settings split.** Some settings are LaTeXTools' (engine path, comma-safe
   `TEXINPUTS`, `builder: texlib`) and go dead/irrelevant; some are ours
   (`LaTeX.sublime-settings`, `Preferences`). One-time untangle so coworkers get
   a clean bundle.
5. **Test-harness seam.** `test_texlib_builder.py` fakes the `PdfBuilder` host to
   drive `commands()`. Logic assertions survive; the fake host shim gets
   rewritten to match the new driver's contract.
6. **Hot-reload of helper modules.** Sublime reloads the top-level plugin on
   save, but `texlib_build` imported by `texlib.py` can go stale. Mitigate: keep
   the reloadable surface flat, or use explicit module-reload on plugin load.
7. **Embedded Python has no pypdf** — unchanged; keep the external shell-out.

## 10. Migration phases

- **Phase 0 — scaffold + coexist.** Native `texlib_build` runs *alongside* the
  existing LaTeXTools builder; both work. No cutover. Junction deploy in place.
- **Phase 1 — build parity.** Port the brain behind the new host; match current
  outputs byte-for-byte on the smoke fixtures; pass ported logic tests + new
  driver tests.
  - **In progress (2026-07-10).** `texlib/texlib_build.py` = the brain, ported by
    deterministic copy + seam edits (drop `PdfBuilder`/monkeypatch, add
    `__init__`, add `-file-line-error`); compiles with zero `sublime`/LaTeXTools
    deps. `texlib/texlib.py` = the async runner (Popen-per-argv, streamed panel,
    cancel, overlap guard, feeds `self.out` back). `test_texlib_build.py` drives
    the coroutine with a fake engine — 12/12 parity checks pass (force, macro
    inject, rerun loop, quick, `-file-line-error`). `test_texlib_runner.py` covers
    the async driver itself (fake Popen): cancel→kill mid-stream, rerun feedback
    through the runner, overlap guard — 9/9.
  - **Validated live (2026-07-10):** deployed via junction; a real pdflatex build
    of the `syllabus` fixture succeeded end-to-end — streamed output, TEXINPUTS
    resolved the shared `.sty` (recursive `//` even found `Syllabi/syllabus.cls`),
    coursemeta via cwd, aux routing to `%TEMP%\texlib-aux`, the **rerun loop fired
    for real** (2 passes), copy-back, the publish step (shareable PDF + desktop
    shortcut), and the build summary. Closes gaps (a) live build + (c) TEXINPUTS.
    **Remaining live smoke:** a lua doc (quiz/exam — force + `-shell-escape` + bank
    engine) and a live Cancel.
  - **All live smoke passed (2026-07-10):** quiz (lua force + `-shell-escape` +
    bank), exam-01 (autoexam versions A/B/C + per-version pypdf slicing via the
    external-Python shell-out — the hardest postprocess path) + a live Cancel
    (kill mid-pass-1). **Phase 1 complete, committed as `23378b0`.** (Publish
    toggles wired: the runner feeds `publish_shareable_copies` /
    `copy_published_path_to_clipboard` from `TeXLib.sublime-settings`.)
  - **Drift note (RESOLVED 2026-07-10):** consolidated in Phase 2 — one core
    (`TexlibBuildCore`), two thin hosts (native `TexlibBuild`, LaTeXTools
    `TexlibBuilder` adapter). See the Phase 2 entry below.
- **Delegation layer / Tier C (2026-07-10).** Built the "complement" half: a
  successful build delegates to LaTeXTools' `jumpto_pdf` — open/refresh + forward
  sync per LaTeXTools' own `forward_sync`/`keep_focus` settings, gated by the
  TeXLib `open_pdf_on_build` setting; `jumpto_pdf` falls back to the PDF next to
  the source (where copy-back puts it), so it always resolves. `TeXLib: View PDF`
  and `TeXLib: Forward Sync` expose those on demand. Coupling is by stable command
  name, never import. `test_texlib_runner.py` covers the on_success trigger (fires
  only on completed build + PDF present + not cancelled). **Needs a live check:**
  confirm the viewer pops/syncs after a build.
- **Phase 2 done (2026-07-10) — native-canonical + cutover.** Build logic is now
  ONE source: `TexlibBuildCore` in `texlib_build.py`. The native `TexlibBuild`
  subclasses it (adds the constructor); the LaTeXTools builder is a 113-line
  adapter — `class TexlibBuilder(TexlibBuildCore, PdfBuilder)`, core first in the
  bases so `commands()`/`_*` resolve to the core, PdfBuilder supplies `__init__` +
  host attrs. 1690 → 113 lines; nothing left to drift. `Ctrl+B` / `Ctrl+Shift+B`
  now run the native build for TeX files (LaTeXTools' build system still reachable
  via Build With: TeXLib). Native side proven by the six suites; the LaTeXTools
  adapter path needs a **live re-test** (redeploy `texlib_builder.py` to
  Packages/User + restart). **Log-parser (Risk #1) RESOLVED (2026-07-11):** a live
  typo build confirmed `-file-line-error` emits accurate `./file.tex:14: message`
  errors. Landed with two follow-ups: set `result_base_dir` so relative `./` paths
  resolve on click, and a LaTeXTools-style `show_panel_on_build` ("errors" default) —
  the panel stays hidden with a status-bar "building…" and pops open only on failure,
  appending a clickable error summary (source errors; `.aux` consequences excluded).
  No vendored parser needed.
- **Phase 3 — domain features.** Scaffolding, coursemeta, bank commands.
  - **Bank navigation done (2026-07-10), `texlib/texlib_bank.py`** (own top-level
    file → hot-reloads independently). `TeXLib: Go to Bank Problem` and `TeXLib:
    Insert Bank Problem` scan the doc + its `\loadbank`/`\importproblem` targets +
    a sibling `bank.tex` for `\begin{problem}{id}[attrs]`, quick-panel to jump to
    a definition or insert `\getproblem{id}`. `test_texlib_bank.py` covers the
    pure scan (sources + ids + attrs + line, both inline and external patterns).
    **Live check pending.**
  - **TEXMF install done (2026-07-10), `texlib/texlib_texmf.py`.** `TeXLib: Install
    Classes to TEXMF` copies the payload (8 `.cls` + 17 root `.sty` + 7 Lua engines;
    unique basenames → flat copy) into `TEXMFHOME/tex/latex/texlib/` so *every* TeX
    tool finds them, not just this plugin. This is the piece of the installer's job
    worth pulling in — the **installer balance**: the repo stays the single source;
    the installer and the plugin are *peer distribution channels* (editor-agnostic
    turnkey vs. Sublime-integrated); this command lets the plugin subsume the
    installer's function *for Sublime users* without making the classes editor-
    captive. Source auto-detected (bundled `latex/` else repo root) or `class_source`
    setting. `test_texlib_texmf.py` covers the gather. **Live check pending.**
  - **Scaffolding done (2026-07-10), `texlib/texlib_scaffold.py`.** `TeXLib: New
    Document` lists the `<class>-template.tex` files (class from filename; test
    fixtures ignored), drops the chosen one into the active folder under a name you
    pick, opens it, and warns if no `coursemeta.tex` is in scope. `test_texlib_
    scaffold.py` covers discovery. **Live check pending.**
  - **Coursemeta locators done (2026-07-10), `texlib/texlib_locate.py`.** `TeXLib:
    Open coursemeta.tex` (upward walk) and `TeXLib: Reveal Aux Directory` (the
    `%TEMP%\texlib-aux\<md5(tex_root)[:12]>` the build routes to — hash + tex_root
    resolution mirror the runner so it points at the same folder). `test_texlib_
    locate.py` covers both. **Live check pending.**
  - **Completions + snippets done (2026-07-10).** `texlib/texlib_complete.py` —
    macro completions after `\` (\getproblem/\setvar/\picklist/…) and problem-**id**
    completions inside `\getproblem{…}` (reuses the bank scanner). `snippets/` —
    `problem`/`solution`/`parts`/`questions`/`getproblem`/`versions`.
    `test_texlib_complete.py` covers the context classifier.
  - **Utility commands done (2026-07-10).** `texlib/texlib_utils.py` — `Clean Aux
    Directory` (rmtree the build's aux dir, reuses `aux_dir_for`) and `Package for
    LMS` (shell out to `package_for_lms.py`). **Deferred:** `Show Resolved Metadata`
    — an honest version needs the engine to dump resolved values (a build-time
    `.metadump` sidecar), so skipped rather than showing half-resolved coursemeta.
  - Domain set complete (bank / TEXMF / scaffold / locators / completions /
    snippets / utils). Phase 2 (consolidation + cutover) is done above.
- **Phase 4 — distribution.** Package via the installer repo / a Package Control
  custom repo; finish the settings split; document LaTeXTools as a companion.

Phases 0–1 are reversible and low-risk (nothing removed). The commitment point
is Phase 2.

## 11. Testing

- **Reuse** `test_texlib_builder.py` logic assertions; swap the fake host.
- **New** async-driver unit tests: cancel actually kills the process; output
  ordering; rerun/biber branch sequencing.
- **Reuse** `test_biber_integration.py` / `test_synctex_integration.py`; re-point
  at the native command.
- `smoke_test.py` is unaffected (never touches Sublime).

## 12. Distribution

Ship the package via the **TeXLib-Installer** repo (existing channel) or a
Package Control **custom repository** for auto-update. LaTeXTools listed as a
companion/prereq. The shippable bundle excludes personal `Preferences` and
spell-check words — those stay machine-local.

## 13. Open decisions (for Landon)

- [x] Log-parser strategy (Risk #1): **regex + `-file-line-error`** (2026-07-10).
- [ ] Package folder name / where domain commands live.
- [ ] Keep the LaTeXTools builder as a fallback through Phases 0–2? (recommended:
      yes.)
- [ ] Distribution channel: installer bundle vs. Package Control custom repo.
