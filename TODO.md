# TeXLib TODO / Notes

Free-form running list. Was previously `more_convience_more_pretty.tex` (typo: "convience"); renamed to Markdown so it actually renders on GitHub.

## Random

- ~~`schedule` environment should not make the title.~~ **Done** — env no
  longer auto-emits the banner; call `\maketitle` explicitly (added to the
  template + README).

## General conventions and documentation

- Make list of conventions for all LaTeX:
  - whitespace conventions
  - comment conventions
  - margin conventions
- Make documentation.

## Generalized templates

### Title

~~Update instructions:~~ **Already done** — all three live in
`Exams/autoexam-instructions.tex` (box/circle your answer; no guess-and-check;
write down partial-credit info). Quizzes have their own `quiz-instructions-file`.
- Emphasize "please box or circle your answer."
- Guessing and checking is not permitted; some method or process must be utilized.
- If you are unsure what to do, write down what you think you should do and/or any information you think might be relevant for partial credit.

### Schedule

- ~~New page per month; repeat days to complete weeks.~~ **Done** — opt-in via
  `\meta{month-pages = true}`; boundary weeks repeated, wall-calendar style.
- ~~Fix the week column length.~~ **Done** — was the trailing vertical-rule
  stub below the last row (longtable phantom foot-row); cleaned up in
  `render_grid`.
- ~~The shipped `Schedule/template.tex` has Spring directives but the example
  + smoke stub feed it Fall dates, so the grid renders empty.~~ **Done** —
  template is now Fall-coherent (Labor Day / Thanksgiving / `\finalsweek[12-14]`).
- Month-pages polish: gray-out the *repeated* boundary-week days borrowed from
  the adjacent month (currently they render identically in both months).

### Scratch page

- Provide instructions on how to label work for problem.

### Exams

- Horizontal lines between problems.
- Vertical problem formats.
- Add more problems; repeat problem types.

#### End rubric

- Should not be attached; print separate sheet and staple it to back.

## Theme / customization

- Make every visual choice in TeXLib (colors, rule widths, fonts, spacing,
  cell heights, header layout, etc.) customizable rather than hard-coded
  in the class files.
- Provide a dedicated theme file (e.g. `texlib-theme.sty` or a `.tex`
  loaded via `\usetheme{...}`) that ships sensible defaults and can be
  swapped or overridden wholesale.
- Expose per-document override commands so a single `.tex` can tweak any
  theme value inline without editing the shared theme file.

## Exam versioning and randomization

_(open)_

## Tooling / tests

- ~~**Content checks in `smoke_test.py`**~~ **Done** — `pdftotext` substring
  assertions (`EXPECT_TEXT`) + non-empty-artifact checks (`*_schedule_grid.tex`)
  run by default; `--visual` PNG regression for deterministic modules against
  `tests/visual_refs/`. CI installs `poppler-utils`. All checks soft-skip when
  their tool is missing.
- ~~**`didactic.cls` requires LuaTeX but builds with pdflatex**~~ **Done (fix a)** —
  `texlib-problembank`'s load-time engine loader is now guarded by
  `\ifdefined\directlua`; under pdflatex the load is skipped and bank macros
  route through `\pbank@lua`, which raises a clear "requires LuaLaTeX" error
  only if a bank command is actually used. Non-bank `didactic` documents
  compile under pdflatex again. (Surfaced by the smoke build check on branch
  `feat/quiz-auto-load-bank`.)
- ~~Add a second Schedule smoke case (or mode) built with `month-pages = true`~~
  **Done** — the `month-pages` render path is now covered by the
  `schedule/month-pages` visual scenario (`--scenarios`).
- Grow the visual scenario packs beyond Schedule (Report Cards multi-section,
  Notes theorem taxonomy, syllabus variants). Infrastructure is in place — just
  drop `tests/scenarios/<area>/<name>/template.tex` folders.
- ~~**`recitation-days` meta key is documented but unimplemented.**~~ **Done** —
  registered in `schedule.cls`'s `meta` family (mirrors `quiz-days`:
  `\clist_gset` + an expandable `\GetRecitationDays`); the `recitations` scenario
  and the README now use it idiomatically.
- Visual scenarios are local-only (env-specific refs). To make them CI-gateable,
  pin the TeX Live container version and generate/commit refs from that image,
  then add a separate (non-required, or nightly) visual job. Also: parallelize
  builds + seed-pin autoexam/quiz to bring randomized modules into visual scope.
- **Delete orphaned `Quizzes/preamble.tex`** — not `\input`/`\usepackage`d
  anywhere (only named in the top-level README layout); superseded by
  `quiz.cls`. Verify, remove, and fix the README layout line.
