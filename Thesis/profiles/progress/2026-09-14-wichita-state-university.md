# 2026-09-14 — wichita-state-university

**profile** — round of ten, institution 3. PR #217.

Complete: geometry, spacing, title page, Committee Identification Page (Wichita's
name for the approval page), and the accessibility finding. Only
`\thesissetchapteropening` is left neutral, correctly — Wichita's major headings
sit *on* the one-inch top margin, not below a deeper one.

Things a later pass should not have to rediscover:

- **The manual is dated Fall 2023 and that is not staleness to "fix".** Its PDF
  metadata says 2023-09-15. It is nevertheless current: the Graduate School's
  live ETD page links exactly this file under "Format", and no newer edition
  exists on wichita.edu. There is no superseded copy sitting beside it.
- **The layout spec is the full-sized sample pages, not prose.** §3.2.1 says
  "Center all other information on this page, as shown below and in the
  full-sized samples on pages 41-42" and gives no blank-line counts. The title
  page's vertical positions were therefore measured off the sample rendered at
  110 dpi (PDF pages 47 and 51 of the manual, which are the manual's own pp. 41
  and 45) and are listed in the profile header in inches from the paper top. Do
  not replace them with guessed blank-line counts.
- **Wichita publishes no accessibility requirement at all.** The 96-page manual
  contains no occurrence of "accessibility", "alt text", "tagged", "WCAG",
  "PDF/A", "screen reader", "508" or "Title II"; its four hits for "accessible"
  are about supplemental files being reachable. Recorded as
  `\thesisaccessibilityrequirement{Not published}` — an absence, not an unread
  section — with the note that the manual predates the federal deadlines.
- **No signatures.** "Keep in mind that signatures are not required on this
  page", and the sample annotates the same block "NOTE THAT SIGNATURES ARE NO
  LONGER REQUIRED ON THIS PAGE".
- **Three profile-local setters were added**, because Wichita requires
  information the class has no field for: `\wichitapriordegrees`,
  `\wichitamajor`, and `\wichitadeans`. The first and third warn at build time
  when a document needs them and has not set them, rather than printing a
  plausible placeholder — an omitted required line is a filing error and a
  silent one. `\wichitadeans` prints only for a dissertation, which is what the
  manual says ("For doctoral dissertations only").
- **`\gradprogram` takes the BARE department name for this profile** — the page
  supplies "Submitted to the Department of" itself. Wichita also warns that a
  programme name may differ from its department, and that four programmes
  submit to an area named in the manual's Appendix B instead.
- **The `\ifx` guarding the dean block compares against a `\newcommand`'d twin,
  not a `\def`'d one**, because `\newcommand` builds a `\long` macro and `\def`
  does not, so a `\def`'d comparison never matches `\thesis@docnoun`. The first
  draft had that bug. Do not "simplify" it back.
- **Left for the reviewer:** as at Washington State, the page-number placement
  ("one-half inch from the bottom edge of the paper") is not implemented; the
  class centres the folio in the foot. Wichita's hard rule — text must not
  intrude into the one-inch bottom margin — is satisfied. The title page's date
  line also sits nearer 7.9in than the sample's 8.57in; noted in the header.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors and no class warnings (the test document sets all
three profile-local fields). veraPDF `--flavour ua2` reports compliant, 1727
rules passed, 0 failed. Title page and Committee Identification Page rendered
and compared side by side against the manual's own sample pages.
