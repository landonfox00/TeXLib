# Examples

End-to-end illustrations of using TeXLib for a real course. Copy a directory and edit, or just use it as a reference for the per-course workflow described in the [root Quickstart](../README.md#quickstart).

## What's here

- [`Math181-Fall2026/`](Math181-Fall2026/) — A Calculus I course folder built around one shared `coursemeta.tex`. The documents an instructor produces for a real semester:
  - `coursemeta.tex` — institution/instructor/term/course/date metadata, picked up automatically by every document in the directory (and demonstrating the single-source-of-truth pattern).
  - `syllabus.tex` — a `syllabus` with title block, `\syllabussection`s, and the two-column `\gradetables`. Shows course-wide values coming from `coursemeta.tex` while instructor-contact keys (`email`, `office`, `office-hours`, `class-time`) are set as class options.
  - `schedule.tex` — a landscape `schedule` grid: Fall 2026 holidays, MWF sections, Friday quizzes, exam/review weeks, and finals. Reads the term dates and `lecture-days` from `coursemeta.tex`.
  - `lecture-01-limits.tex` — a short `didactic` lecture demonstrating `definition` / `theorem` / `example` / `exercise` / `solution` environments.
  - `quiz-01.tex` — a short `quiz` mixing inline problems and bank-backed `\getproblem` retrieval.
  - `exam-01.tex` + `bank.tex` — a randomized **multi-version** `autoexam` (`\versions{A,B,C}` + `\shuffle`) that retrieves problems from a small course bank by topic. Build it as a collated PDF, a single version, or an answer key (see the header of `exam-01.tex`).

The folder deliberately covers the *everyday* course documents. The remaining classes — `pset` (problem sets), `report-card`, and `bingo` — aren't shown here; for those, copy the canonical template from the module directory ([`Problem Sets/pset-template.tex`](../Problem%20Sets/pset-template.tex), [`Report Cards/report-card-template.tex`](../Report%20Cards/report-card-template.tex), [`Bingo/bingo-template.tex`](../Bingo/bingo-template.tex)). Each module's `README.md` documents its options.

## Building an example

From the example directory, with `TEXINPUTS` configured per the root Quickstart:

```
cd examples/Math181-Fall2026
lualatex syllabus.tex
lualatex schedule.tex
lualatex lecture-01-limits.tex
lualatex quiz-01.tex
lualatex exam-01.tex                                   # collated A/B/C
lualatex "\def\ShowKey{}\input{exam-01.tex}"           # answer key
```

These examples **are** built by the CI smoke test — `smoke_test.py` registers every document above as a build fixture, so a class change that breaks the documented workflow fails CI instead of leaving the docs to silently rot. The check is build-only (no text assertion): the documents share one `coursemeta.tex`, so there's no single per-document token to assert. Their illustrative role is unchanged — they're still the place to point someone at a real end-to-end course folder.
