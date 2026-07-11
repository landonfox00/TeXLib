# TeXLib native Sublime package — Phase 0

The native "complement, not replace" plugin from
[`../PLUGIN-DESIGN.md`](../PLUGIN-DESIGN.md). **Phase 0 = scaffold + coexist.**
It stands up the package and an invokable `texlib_build` command that *resolves*
the target (root + engine + mode) and reports it; it does **not** yet spawn the
engine (that's the Phase 1 async runner). It touches neither Ctrl+B nor
`Packages/User`, so the existing LaTeXTools `texlib` builder keeps working
unchanged.

## Files

| File | Role |
|------|------|
| `texlib.py` | Top-level plugin: `texlib_build`, `texlib_build_pick`, target resolution, output panel. |
| `Default.sublime-commands` | Command-palette entries ("TeXLib: Build …"). |
| `Default (Windows).sublime-keymap` | Bindings — commented in Phase 0 to avoid conflicts. |
| `.python-version` | Opt into Sublime's 3.8 plugin host. |
| `deploy-plugin.ps1` | Junction this folder to `Packages/TeXLib` (hot-reload; no copy). |

## Deploy / test

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy-plugin.ps1
```

Restart Sublime once. Then open any TeXLib `.tex` and run **Command Palette →
"TeXLib: Build (pick mode)"**. You should get a `texlib` output panel reporting
the resolved root, `\documentclass`, engine (with lua-force noted), and mode.

Undo: `cmd /c rmdir "%APPDATA%\Sublime Text\Packages\TeXLib"`.

## Not done here (later phases)

- **Phase 1** — the async runner (`_run_build`) that Popens the engine, streams
  to the panel, and ports the build brain from `../texlib_builder.py`.
- **Phase 2** — cut over from the LaTeXTools builder; settle the log-parser
  decision (PLUGIN-DESIGN Risk #1).
- **Phase 3+** — domain commands (scaffold / coursemeta / bank), distribution.
