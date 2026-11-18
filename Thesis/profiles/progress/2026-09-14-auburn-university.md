# 2026-09-14 — auburn-university

**profile** — round of ten, institution 2. PR #216.

Complete: geometry, spacing, title page (which carries the committee under
"Approved by"), `\thesisnoapprovalpage`, and nine accessibility records
including `\thesisrequiretagging` and `\thesisrequiredocumentlanguage`. Only
`\thesissetchapteropening` is left alone, correctly — Auburn's one top-margin
exception is the title page's 2in, applied inside the title page, and every
other major heading takes the body's 1in.

Things a later pass should not have to rediscover:

- **Auburn is the accessibility-heaviest school profiled so far.** It requires a
  "Digital Accessibility Disclosure Statement" as a preliminary page, publishes
  a combined "Accessibility & Formatting Checklist", and tells students to run
  PAC or Acrobat and fix every error. `\thesisrequiretagging` and
  `\thesisrequiredocumentlanguage` are both set on that evidence.
- **The modal verbs are genuinely mixed and that is flagged, not smoothed
  over.** The guide page hedges ("should", "we encourage") where the checklist
  commands. The profile header sets out both and quotes the checklist lines the
  two declarations rest on, so a reviewer who reads the modal differently can
  drop them without re-researching. `\thesisrequirepdfstandard` is deliberately
  NOT set: Auburn names tools (PAC, Acrobat), never a standard.
- **No approval page, on three independent statements** — the enumerated
  preliminary-page list omits one, approval is collected on the separate
  "Electronic Thesis/Dissertation Final Approval Form", and "Replace any
  signatures — digital or physical — in the electronic document with typed
  names." So no physical signatures anywhere in the filed file.
- **Auburn paginates the preliminary pages in ARABIC**, not roman: title page is
  an unnumbered page 1, the abstract is page "2", and the count runs unbroken
  into the body. An Auburn document must therefore not call
  `\frontmatter`/`\mainmatter`. Recorded in the profile header.
- **Two required preliminary pages the class cannot supply** — the Digital
  Accessibility Disclosure Statement and the AI Use Disclosure Statement. Both
  are written out in the profile header with their layout, because an author
  reading only the profile would otherwise file without them.
  `\thesisaccessibilityreport` does not substitute for the first: the report
  says what Auburn asks for, the disclosure says what the author did.
- Two typos in Auburn's own text ("accessibilty", "esnure") are quoted as found
  and marked as theirs. Do not silently correct them in a later pass.
- Auburn recommends **sans serif** for accessibility, which cuts against this
  class's Latin Modern default. Recorded as an accessibility item rather than
  acted on, since Auburn states it as a recommendation.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`,
two lualatex passes, no errors; the only class warning is the intended one from
`\thesisnoapprovalpage`. veraPDF `--flavour ua2` reports compliant, 1727 rules
passed, 0 failed. Title page rendered and compared against the guide's numbered
element list.
