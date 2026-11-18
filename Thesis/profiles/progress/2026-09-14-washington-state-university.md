# 2026-09-14 — washington-state-university

**profile** — round of ten, institution 1. PR #215.

Complete rather than partial: geometry (1in minimum, all four sides), spacing
(double, taken from WSU's own recommendation on top of a stated 1.5 floor),
title page and committee page are all set from the Graduate School's own
documents. Nothing is left to the neutral fallback except
`\thesissetchapteropening`, which WSU does not ask for — chapters must start on
a new page and that is all.

Things a later pass should not have to rediscover:

- **The committee-page sentence is not in the guidelines PDF.** The prose guide
  only states the constraints on it (capital C in "Committee", "the thesis of"
  vs "the dissertation of", the author's name matching the title page). The
  sentence itself is printed only in the Graduate School's Word template,
  `thesis-dissertation-template.docx`, which is where this profile takes it
  from.
- **WSU's committee page carries no signatures.** No rules, no date line, no
  seal anywhere in the guide, the checklist or the template. The class default
  draws a signature rule, so the profile overrides `\thesis@memberline` for that
  page. Do not "restore" the rules.
- **The committee page sets its own page numbering** (roman, counter forced to
  2, visible folio), because WSU requires it to be numbered "ii" and the title
  page to be the only unnumbered page. That is unusual for a profile hook and is
  deliberate; it assumes WSU's prescribed prefatory order.
- **The formatting guidelines PDF contains no accessibility rule at all** — the
  word does not occur in it. The only WSU accessibility text is on the
  submission page and is encouragement ("please be sure to follow best
  practices"), naming no standard, level or checkable property. So
  `\thesisrequiretagging` and friends are deliberately unset. A later pass
  should not read WSU Libraries' `libguides` accessibility guide as a
  requirement: RESEARCHING.md excludes library guides as sources, and the
  Graduate School links it as a resource, not a rule.
- **Left for the reviewer:** WSU says page numbers "should be centered at the
  bottom of the page, 0.5 inches from the edge". The class centres the folio in
  the foot but does not pin it to 0.5in. The build stays clear of WSU's hard
  0.5in "absolute margin", so it satisfies the rule stated as a rule.
- A CAHNRS-hosted copy of an older submission guide (`Updated 8/18/2023`) is
  still on the server at `wpcdn.web.wsu.edu`, and an even older
  `Thesis_Guidelines05.pdf`. Neither is the Graduate School's current document;
  the live v1.3 guidelines dated 1/15/2026 govern.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`,
two lualatex passes, no errors and no class warnings; veraPDF `--flavour ua2`
reports compliant, 1727 rules passed, 0 failed.
