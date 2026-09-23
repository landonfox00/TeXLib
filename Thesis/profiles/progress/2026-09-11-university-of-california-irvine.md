# 2026-09-11 — university-of-california-irvine

**profile** — HERD rank 41. PR #187.

Complete: geometry (1in minimum, all four sides), double spacing, the title page
reproduced from the manual's own specimen image, `\thesisnoapprovalpage`,
`\thesisrequiretagging`, `\thesisrequiredocumentlanguage`, and nine quoted
accessibility rules. Nothing is left to the neutral fallback except
`\thesissetchapteropening` (none is required) and `\thesisrequirepdfstandard`
(UCI names no PDF standard — WCAG is not one).

Things a later pass must not rediscover:

- **Why a LibGuide is cited:** the Graduate Division's own submission page
  (`grad.uci.edu/current-students/thesisdissertationelectronicsubmission/`)
  names `guides.lib.uci.edu/gradmanual` as *the* formatting manual, and the
  manual describes itself as established by the Graduate Division, the Graduate
  Council and the Libraries jointly.
- **The title-page layout is an IMAGE**, not prose:
  `d2jv02qf7xgjwx.cloudfront.net/customers/926/images/Dissertation_Template_Title_Page.jpg`,
  embedded on the Title Page page. Reading it required rendering the JPEG. The
  right-aligned committee block, the unbroken-then-broken "UNIVERSITY OF
  CALIFORNIA," / "IRVINE" line and the sentence-case title all come from there.
- **The date line is a bare YEAR** ("the year in which your degree will be
  conferred"), not a month and year. The class default `May, 20XX` is out of
  spec at UCI; a document must set `\graddate{2027}`.
- The ADA date UCI publishes is **April 2026**. That is UCI's own figure — do
  not reconcile it against a different date in a neighbouring profile.
- Every manual page carried "Last Updated: Sep 10, 2026", one day before access.
- Signatures still collected, on the Ph.D. Form II / Master's Thesis Signature
  Page filed with the Graduate Division — never in the manuscript.
