# 2026-09-13 — louisiana-state-university-and-agricultural-and-mechanical-college

**profile** — PR #211.

Complete. Geometry (1in all four sides, no exceptions), double spacing, the
three-block title page and `\thesisnoapprovalpage` are all set from the
Graduate School's February 2026 handbook and its page-25 sample. Left neutral:
chapter-opening margin and typeface.

Things a later pass should not have to rediscover:

- **Three editions of the handbook are live on lsu.edu and two are linked from
  the same page.** `thesisanddissertationhandbook_feb2026.pdf` is current — it
  is what the page's own prose points at ("review the Thesis & Dissertation
  Handbook. It contains the complete formatting guidelines") and what Quick
  Links label "With Formatting Guidelines". Also live:
  `..._2025.pdf` (a sidebar card on the same page) and `..._fall2022.pdf` (an
  older path, prominent in search results).
- **No chapter-opening margin, and that is a positive finding, not a gap.** LSU
  says the margin admits no exceptions at all — "Margins must be the same on
  every page with no exceptions for wide tables and figures in landscape
  format" — so a deeper opening would be *out of spec*, not merely unasked-for.
- **Spacing is an unusually wide choice**: "Your document's narrative text may
  be either single- or double-spaced throughout." A single-spaced LSU thesis is
  in spec. The profile takes double and says so. "Throughout" is load-bearing —
  mixing is forbidden, as is anything between ("no spaces larger than a double
  space, except on the title page. Do not use half-spaces").
- **The accessibility rule is real but best-effort, and that is why no
  declaration is set.** "Make your document accessible to visually impaired
  readers to the best of your ability", and it is item 4 of the five conditions
  before upload. LSU names no tagging, no document language, no WCAG level and
  no PDF standard, so `\thesisrequiretagging` and friends stay off. Contrast
  UConn in the same round, which names WCAG 2.1 and does get them. Two quoted
  `\thesisaccessibilityrequirement` entries instead.
- **The committee does sign at LSU — a form, not a page.** "a copy of the
  committee-signed Thesis/Dissertation Approval Form, which your department
  prepares and emails to gradsvcs@lsu.edu." That is stronger evidence for
  `\thesisnoapprovalpage` than the closed front-matter list alone, and the list
  agrees.
- Title is **16pt bold solid capitals on the first line below the top margin**,
  with 12pt for everything else on the page; the prose gives the size but not
  the weight, so the sample governs the bold. `\topskip=0pt` again, as in
  Delaware, to stop 10pt creeping in above the page's first box.
- Set `\graddate` to a bare "Month Year" for LSU (e.g. `May 2022`) — the class
  default "May, 20XX" carries a comma LSU's example does not.
