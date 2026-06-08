# Examples

End-to-end illustrations of using TeXLib for a real course. Copy a directory and edit, or just use it as a reference for the per-course workflow described in the [root Quickstart](../README.md#quickstart).

## What's here

- [`Math181-Fall2026/`](Math181-Fall2026/) — A minimal Calculus I course folder. Contains:
  - `coursemeta.tex` — institution/instructor/term/course metadata, picked up automatically by every document in the directory.
  - `lecture-01-limits.tex` — a short `didactic` lecture demonstrating `definition` / `theorem` / `example` / `exercise` / `solution` environments.
  - `quiz-01.tex` — a short `quiz` document mixing inline problems and bank-backed `\getproblem` retrieval.

## Building an example

From the example directory, with `TEXINPUTS` configured per the root Quickstart:

```
cd examples/Math181-Fall2026
lualatex lecture-01-limits.tex
lualatex quiz-01.tex
```

These examples **are** built by the CI smoke test — `smoke_test.py` registers `lecture-01-limits.tex` and `quiz-01.tex` as build fixtures, so a class change that breaks the documented workflow fails CI instead of leaving the docs to silently rot. The check is build-only (no text assertion): the two documents share one `coursemeta.tex`, so there's no single per-module token to assert. Their illustrative role is unchanged — they're still the place to point someone at a real end-to-end course folder.
