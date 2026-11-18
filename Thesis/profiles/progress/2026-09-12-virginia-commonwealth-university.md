# 2026-09-12 — virginia-commonwealth-university

**profile** — HERD rank 68. PR #197.

Complete: geometry (1in), double spacing, title page from the Graduate School's
sample template, `\thesisnoapprovalpage`, `\thesisrequiretagging` and nine quoted
accessibility rules. Nothing left to the neutral fallback.

Things a later pass must not rediscover:

- **The Manual is now a Google Doc, and the April 2023 PDF still on the server
  is superseded.** `graduate.vcu.edu/media/graduate-school-2021/docs/ETDManualApril2023-FINAL.pdf`
  is the first search hit and is no longer linked from the hub page. The two
  agree on everything encoded here but are not identical (the PDF calls a
  copyright notice "not required"; the Doc drops the clause). Quote the Doc.
  Google Docs export cleanly with `/export?format=txt`.
- **VCU states that it issues no format requirements** — "The Graduate School
  does not issue specific format requirements for Electronic Theses and
  Dissertations (ETD)" — and defers to schools, departments and the committee.
  The 1in / double figures come from a NOTE inside the *ETD sample templates*
  doc, which is the only place VCU writes a number. A school or college with its
  own ETD manual overrides them (the School of Medicine publishes one).
- `\thesisrequirepdfstandard` is deliberately unset: PDF/A appears only in a
  list of "recommended" preservation formats *alongside plain PDF*, and PDF/UA
  only as a property of a checker VCU suggests. Neither is required. Do not
  promote either.
- VCU cites ADA Title II with **no date** and names WCAG with **no version or
  level**. Nothing to reconcile against a neighbouring profile.
- The accessibility document is a published Google Doc whose closing paragraphs
  are in VCU Libraries' voice; the Graduate School links it from its own ETD
  page as the accessibility reference, which is the standing it is cited with.
- The profile defines `\vcupriordegrees{}` for the template's "Student's degrees
  with Institutions and dates", which shares the author's line.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
