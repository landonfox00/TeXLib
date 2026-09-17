# 2026-09-17 — alcorn-state-university

**profile** — alphabetical fallback. Round of ten, institution 8 of 10.

Set from the Office of Graduate Studies' "Thesis and Non-Thesis Manual (APA 7th
Edition Formatting and Style Guide)", revised June 2022, linked from the live
Thesis and Research Project page: geometry (1.5in left, 1in elsewhere), double
spacing, the Appendix B title page and the Appendix C approval (signature) page,
plus a "Not published" accessibility finding. Left neutral: typeface
(Times New Roman is "preferred"/"standard" with APA alternatives listed), page
number position (top right, 1in — the class uses the footer), and no chapter
opening (only the bound cover has a 2in top).

A later pass should not have to rediscover:

- **Signatures are wet ink, outside the PDF**: four original signature pages
  on 20 lb cotton bond, black ink, submitted to the Graduate Office for the
  Provost's signature.
- The profile adds four `\providecommand` fields the class lacks —
  `\thesisschool`, `\thesisdepartment`, `\thesisdefensedate`, `\thesisdean` —
  plus `\thesispriordegrees`, because the title page wants "JANE DOE, B.S." while
  the approval page wants the legal name without degrees.
- Emptiness is tested by expansion: `\ifx\X\@empty` never matches a
  `\providecommand`'d macro (it is `\long`), so the obvious test silently
  always reads "set".
- The approval page is tight: a Chair plus three members fits at the current
  gaps; at 1.6 baselineskip the Provost's line spilled onto a second page.
- Three quoted ambiguities are in the header (approval page "Optional" in one
  table but required everywhere else; checklist's "centered vertically" title vs
  the specimen; block quotes double vs single). The separate 2019 Capstone
  Project Manual is for capstones and was not used.
- alcorn.edu serves curl with a browser User-Agent; the old
  `graduation-information/thesis-and-project` URL now 404s.
