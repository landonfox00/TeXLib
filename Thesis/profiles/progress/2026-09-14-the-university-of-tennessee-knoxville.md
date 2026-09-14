# 2026-09-14 — the-university-of-tennessee-knoxville

**profile** — round of ten, institution 4. PR #218.

Complete: geometry, spacing, title page, `\thesisnoapprovalpage`,
`\thesisrequiretagging` and eight quoted accessibility records. Only
`\thesissetchapteropening` is left neutral, correctly — UTK says "Text must
begin at the top of the page" and states no deeper opening margin.

Things a later pass should not have to rediscover:

- **The guide's URL says 2023 and the guide is not from 2023.** It is served
  from `/documents/2023/07/preparation-guide-for-theses-and-dissertations.pdf/`
  and its cover reads "2026 / 2027". The Graduate School republishes in place.
  Do not go looking for a newer-looking path; there isn't one, and do not
  down-rate the citation for the stale directory.
- **UTK fixes the margin rather than flooring it**: "These margins define the
  minimum *and maximum* white space to be maintained on all sides of the page
  and apply to page number placement." A wider margin is as wrong as a narrower
  one, and the rule explicitly covers the folio — which is why the class's
  `normal` layout (includefoot) is right here and no page-number exception is
  taken. Unlike Washington State and Wichita, there is nothing left unimplemented
  on this point.
- **Spacing is a choice with a CEILING, not a floor**: "Students may use single,
  1.5, or double-spacing … you cannot exceed double-spacing." The profile takes
  double, the top of the range.
- **No approval page**, stated twice as a closed set: in prose ("The three
  preliminary pages that are required … are the title page, abstract, and table
  of contents … All other pages are optional") and in Table A-2, "Required Page
  Sequence — Preliminary Pages", which enumerates eight pages and no approval
  leaf. Approval runs through the review and Vireo process in Section 5.
- **The title page spec is an annotated specimen, Figure A-1 on guide p. 52
  (PDF page 59).** It was rendered at 120 dpi and read as an image; the
  annotations are prescriptive and are quoted in the profile header. Two of them
  are easy to get backwards: the degree line carries no major or department, and
  the date is month-and-year of *graduation* with "no date or a comma after the
  month". Note also that the degree name and the bare word "Degree" are separate
  lines — that is the wording, not a typesetting accident.
- **UTK requires a SCORE and proof of it, which no build can produce.**
  "Electronic theses and dissertations must be at least 70% compliant as
  determined by the YuJa Panorama accessibility report. A copy of the report
  showing you've met the minimum compliance threshold must be submitted to
  thesis@utk.edu before the document can be accepted." A clean PDF/UA build is
  the means, not the evidence. Flagged at the top of the profile.
- **The guide's own formatting exemplars are not accessibility models** — "At
  this time, the exemplars do not reflect accessibility compliance." Recorded,
  because copying one is the obvious wrong move.
- `\thesisrequiredocumentlanguage` is deliberately **not** set: UTK requires
  language tagging for foreign-language passages only, never the document
  language as such. `\thesisrequirepdfstandard` likewise — WCAG is not a PDF
  standard and UTK names no PDF/A or PDF/UA level.
- **A `%` inside a `\thesisaccessibilityrequirement` argument kills the build**
  ("File ended while scanning use of \thesisaccessibilityrequirement"). Two
  literal "70%" quotes did it here. Escape them.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors; the only class warning is the intended one from
`\thesisnoapprovalpage`. veraPDF `--flavour ua2` reports compliant, 1727 rules
passed, 0 failed. Title page rendered and compared against Figure A-1.
