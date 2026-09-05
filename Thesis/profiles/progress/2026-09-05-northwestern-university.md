# 2026-09-05 — northwestern-university

**profile** — HERD rank 28. PR #128. Round of ten, institution 6 of 10.

Geometry, spacing, title page and `\thesisnoapprovalpage` all set from TGS's own
Dissertation Formatting Requirements page and the sample template it links.
`\thesissetchapteropening` unset; no accessibility check-flag raised.

Things a later pass should not have to rediscover:

- **The fractions were verified at the codepoint level, not by eye.** TGS's page
  serves U+00BE (VULGAR FRACTION THREE QUARTERS) and it decodes to a replacement
  character in several extraction paths — the same trap that hides Penn State's
  margin figure (#124). Read the codepoint out of the raw bytes, don't squint at
  extracted text.
- **The ¾" is an allowance to go CLOSER to the edge, not a second margin.** The
  body rule is a flat 1in on all four sides; page numbers, figures,
  headers/footers, footnotes and full-page images "may be ¾" from edge of page".
  Nothing in the class puts those outside the text block, so the allowance is
  unused.
- **TGS's requirements are explicitly a floor**: "The Graduate School sets the
  **minimum** formatting standards … These guidelines do not address all facets
  of formatting and style." Nothing in the profile is extrapolated past it.
- **The title is emitted verbatim — not uppercased, not bolded** — even though
  four surrounding lines on the specimen are uppercase. TGS wants mixed/title
  case with a precise capitalisation rule that only the author can apply.
- **Northwestern is on quarters.** The conferral months are December, March,
  June, September and no others. `\graddate{June 2027}`.
- **"EVANSTON, ILLINOIS" is set literally**, including for Chicago-campus
  programs — TGS prints one place line and that is it.
- **No signatures anywhere.** The arrangement of pages is exhaustive and contains
  no approval, committee or signature page; TGS's own 20-page template emits
  none.
- **No accessibility rule is published** — zero hits across the requirements
  page, the 20-page template, and the linked File Format Recommendations page
  (checked specifically). Northwestern is private, so the April 2026 ADA Title II
  date does not reach it as it does the public universities in this set.
  Recorded as `{Not published}`. Note TGS *does* state a purpose that gestures at
  it — the standards exist partly "to comply with ProQuest and University Library
  requirements for publishing/archiving" — but a purpose is not a requirement,
  and ProQuest's rules are ProQuest's.
- **One visible difference from the specimen, recorded on purpose**: TGS puts
  page numbers in the upper-right corner ≥¾" from the top and right edges, above
  the 1in block; the class puts them in the footer inside it. Not a margin
  violation (TGS's rule only lets numbers come *closer* to the edge), but anyone
  comparing outputs side by side will see it. Moving it would need a page-style
  hook the class does not expose to a profile.
