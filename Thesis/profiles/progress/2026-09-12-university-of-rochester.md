# 2026-09-12 — university-of-rochester

**profile** — HERD rank 73. PR #201.

Complete: geometry (1.25in minimum, all four sides), double spacing including
the front matter, the title page from the manual's annotated specimen,
`\thesisnoapprovalpage`, and three accessibility entries recorded **as
recommendations**. Nothing left to the neutral fallback.

Things a later pass must not rediscover:

- **Three editions of the manual are reachable; only one is current.** The
  June 2026 PDF (`…/wp-content/uploads/2026/08/Manual-for-PhD-Students_7.26.V2.pdf`,
  produced 2026-07-28) is the one to quote, and it is *fuller* than the web page
  it is linked from — the accessibility section and the "Format of Title Page"
  specimen appear only in the PDF. Superseded: the 2022 `Thesis-Manual-March-2022.pdf`
  (still linked on the same page as "Get the PDF") and the older College manual
  at `rochester.edu/college/gradstudies/assets/pdf/theses-manual.pdf`, which
  search engines rank highly.
- **Accessibility at Rochester is RECOMMENDED, not required** — "The University
  of Rochester recommends creating digital content that conforms to … WCAG 2.1
  Level AA". So no `\thesisrequiretagging`, no document language, no PDF
  standard. Same call as Texas A&M. Do not promote these to requirements
  without a new source.
- The ADA is cited with **no compliance date**.
- Margins are a **minimum** ("at least 1.25 inches"), not a fixed figure, and
  page numbers are the one thing allowed outside them.
- Rochester doubles the **front matter** as well as the body; the bibliography
  is the stated exception.
- The title must be printed **as given** — the specimen's placeholder says "Not
  all Caps or all Lower-Case Letters" — so no `\MakeUppercase` here, unlike
  Kentucky and Missouri in this same round.
- The profile adds the word "Professor" before `\gradadvisor` because the manual
  requires it; put a bare name in `\gradadvisor`. It also defines `\urunit{}`
  for the department/program-and-school block, which runs to two or three lines.
  `\graddate` must be a bare conferral **year**.
- The committee is named on the *Contributors and Funding Sources* page, not on
  the title page and not on an approval leaf. The word "signature" does not
  appear in the manual at all.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
