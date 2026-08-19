# Examples

Every TeXLib example lives under this directory, and every one of them is declared exactly once in [`manifest.py`](manifest.py).

## Layout

| Path | What it is | Written to be |
|---|---|---|
| [`templates/`](templates/) | the canonical document you copy to start work, one per class | canonical |
| `<Course>/` | end-to-end course folders sharing one `coursemeta.tex` | realistic |
| [`fixtures/`](fixtures/) | regression traps, one specific bug each | deliberately weird |
| [`scenarios/`](scenarios/) | one-configuration-each feature matrix | deliberately minimal |

Each `templates/<Module>/` folder carries the template **and the data that document needs** — its problem bank, gradebook, `coursemeta.tex`, `.bib`. What stays behind in `../<Module>/` is the class itself, its engine `.lua`, and the library defaults it resolves by name (the `*-instructions.tex` files, Syllabi's policy statements). Those are library assets, not example data.

A template builds from outside its module directory exactly the way a course folder does — `CLASS_HOME_MODULE` stages the class's assets into the build directory. That machinery already existed for `<Course>/`, which is why this needed no new plumbing.

These four are not merged into a single corpus on purpose. A good teaching example makes a poor regression fixture — too much going on to localise a failure — and a good fixture makes a terrible showcase. They are unified by *declaration*, not by file.

## The manifest

`manifest.py` is the single source. Each entry carries its path, what it is for (`smoke` / `accessible` / `visual` / `showcase`), the substrings its rendered PDF must and must not contain, and a note saying why the example exists at all.

`smoke_test.py` derives its registries from it, and the class gallery renders from it — so what you can browse and what CI actually builds cannot drift apart. Adding an example is one edit in one file. Previously it meant remembering which of four registries to touch, and touching the wrong subset failed silently: the example simply never ran, and a green suite said nothing was wrong.

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
