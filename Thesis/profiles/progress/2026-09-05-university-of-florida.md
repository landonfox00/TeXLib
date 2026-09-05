# 2026-09-05 — university-of-florida

**profile** — HERD rank 26. PR #125. Round of ten, institution 4 of 10.

The most complete profile of this round: geometry, spacing, title page,
`\thesisnoapprovalpage`, and **all three accessibility check-flags** raised —
the first institution in this set where the evidence supports
`\thesisrequirepdfstandard`. Only `\thesissetchapteropening` is unset, and there
it is a *verified absence* ("one inch all around on all pages"), not an unknown.

Things a later pass should not have to rediscover:

- **UF mandates its own class file, and no profile can satisfy that.** "…
  templates for MS Word and LaTeX which you **must** use", and for LaTeX, "you
  must use the provided template and run your compiler with LuaLaTeX and TeXlive
  2025." The profile makes texlib-thesis *match* UF's rules; it does not make it
  UF's template. This is stated at the top of the profile, not buried. First
  institution in the set to do this.
- **The accessibility values come from the template's `\DocumentMetadata`, not
  from prose.** UF's `exampleMasterFile.tex` opens with `lang=en-US,
  pdfstandard=ua-2, pdfversion=2.0, tagging=on`. The prose supplies the *mandate*
  ("your document must meet accessibility standards", "you must use LuaLaTex and
  Texlive 2025"); the template supplies the *values*. That split is flagged in
  the profile so a reviewer can weigh it — it is the one requirement here read
  off a template rather than a sentence.
- **The Graduate School delegates to UFIT, and that is why UFIT pages count.**
  `it.ufl.edu` is not an independent authority; it qualifies only because
  grad.ufl.edu's own formatting page names those templates and says students must
  use them. Do not generalise this to other institutions' IT help desks.
- **The UF site was reorganised and several obvious URLs are dead.** 404 or
  redirect-to-homepage: `grad.ufl.edu/academics/editorial/etd-specs/` (which is
  what UFIT's own "GRADUATE SCHOOL FORMATTING GUIDE" link still points at),
  `grad.ufl.edu/academics/tdp/`, `graduateschool.ufl.edu/academics/tdp/`,
  `success.grad.ufl.edu/td/formatting`. **The live path is
  `/current/academics/tdp/formatting/`.**
- **Double spacing is a real requirement here**, not a menu — unlike Vanderbilt
  and Penn State earlier in this round, where all three spacings were permitted.
- **`\graddate` should be the YEAR ALONE at UF** (`\graddate{2027}`). UF's title
  page prints `\degreeYear` and never `\degreeMonth`; the class has one free-text
  date field, so this is resolved by instruction rather than string-parsing.
- **UF's class opens with `\vspace*{-0.4in}` to lift the title above the top
  margin. Not reproduced,** deliberately: the stated rule is "one inch all around
  on **all pages**", and a profile should follow the rule over a template's
  convenience. Not an oversight.
- **No signatures anywhere.** The page order is exhaustive and contains no
  approval, committee or signature page; UF's own class emits none; the chair is
  template metadata (`\chair{...}`), not a page.
- UF's official template uses `math/setup=mathml-SE`, which is the setting this
  library withholds because of the luamml nth-root bug (see ACCESSIBILITY.md).
  Not a profile matter, but worth knowing if anyone compares outputs.
