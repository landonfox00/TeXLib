# 2026-09-11 — case-western-reserve-university

**profile** — HERD rank 42. PR #188.

Complete, and the first in this round with a real approval page. Set from the
School of Graduate Studies' own ETD Guidelines page and the two specimen PDFs it
links: geometry (1.5in left, 1in elsewhere, all minima), double spacing, the
title page, the **Committee Approval Sheet**, `\thesisrequiretagging`,
`\thesisrequiredocumentlanguage` and seven quoted MDAS rules. Only
`\thesissetchapteropening` is left neutral, because no such rule exists.

Things a later pass must not rediscover:

- **The approval sheet's position is fixed**: "A Committee Approval Sheet must
  be included as the second page of your PDF document." A document filing here
  must call `\thesisapprovalpage` immediately after `\thesistitlepage`.
- **Typed names only, no signatures** — stated, not inferred. The class's
  default signature rule is overridden, and the specimen puts the ROLE above
  the NAME, the reverse of the class default.
- **Two different dates.** The title page takes the graduation month and year
  ("either January, May or August ... NOT the date of your defense"); the
  approval sheet takes the defence date. The profile mints
  `\thesisdefensedate`, defaulting to `\thesis@date` — a document that files
  here should set it.
- `\thesisrequiretagging` is the one judgement call: CWRU never writes
  "tagged", but two MDAS items (headings for major sections, alt text on
  figures) are PDF structure that cannot exist untagged. A reviewer reading
  that narrowly can drop the single line.
- CWRU's accessibility date is **Spring 2023**, its own MDAS start — unrelated
  to the ADA Title II dates in neighbouring profiles. Do not reconcile them.
- The guidelines page carries no revision date; its linked assets are dated in
  their paths (title page 2023-04, committee sheet 2018-04). There is no second
  edition on the server.
