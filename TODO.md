# TeXLib TODO / Notes

Free-form running list. Was previously `more_convience_more_pretty.tex` (typo: "convience"); renamed to Markdown so it actually renders on GitHub.

## Random

- `schedule` environment should not make the title.

## General conventions and documentation

- Make list of conventions for all LaTeX:
  - whitespace conventions
  - comment conventions
  - margin conventions
- Make documentation.

## Generalized templates

### Title

Update instructions:
- Emphasize "please box or circle your answer."
- Guessing and checking is not permitted; some method or process must be utilized.
- If you are unsure what to do, write down what you think you should do and/or any information you think might be relevant for partial credit.

### Schedule

- New page per month; repeat days to complete weeks.
- Fix the week column length.

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
