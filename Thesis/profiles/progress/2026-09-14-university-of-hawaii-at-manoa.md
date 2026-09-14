# 2026-09-14 — university-of-hawaii-at-manoa

**profile** — round of ten, institution 7. PR #221.

Complete: geometry, spacing, title page, `\thesisnoapprovalpage`, and the
accessibility finding (an absence). `\thesissetchapteropening` left neutral —
no deeper opening margin is stated.

Things a later pass should not have to rediscover:

- **Mānoa enforces exactly two things and delegates the rest**, and says so:
  "The margin settings and the title page of the thesis or dissertation MUST
  conform to requirements of the Graduate Division… For the rest of the
  manuscript, it is at the discretion of the graduate programs." Both of those
  two are restated on the **live** Style Policy page, so they do not rest on the
  eight-year-old manual alone.
- **The manual is dated October 2018 and is still current.** It is what the live
  page links. Its old URL `manoa.hawaii.edu/graduate/tdstylepolicy_e/` now 404s;
  the PDF moved to `/graduate/wp-content/uploads/tdstylepolicy_e.pdf`. Do not
  read that 404 as a withdrawal.
- **The ʻokina is missing from Latin Modern and the build does not fail.** This
  is the sharpest finding of the round. A bare U+02BB logs
  `Missing character: There is no ʻ (U+02BB) in font [lmroman12-regular]` and
  then exits 0 with the character **gone from the page** — and it is the rule
  Mānoa names first. Probed on the access date: absent from Latin Modern, TeX
  Gyre Termes, TeX Gyre Pagella and TeX Gyre Heros; **present** in Libertinus
  Serif, DejaVu Serif, DejaVu Sans and FreeSerif. The profile remaps U+02BB
  document-wide (`newunicodechar` plus a `\IfFontExistsTF` chain to Libertinus
  then DejaVu, warning if neither is installed), which keeps the codepoint in
  the text layer and only borrows the glyph. Document-wide rather than
  title-page-only because §2.6 is about Hawaiian words in the body too. U+0101
  (ā) is fine in Latin Modern and needs nothing.
- **Spacing is `onehalf`, not double, and that is deliberate.** §2.7: "Currently
  we recommend 1.5 spacing except where style calls for single spacing." A
  recommendation, and spacing is not one of the two enforced items, so the
  profile follows the school's own recommendation — the same reasoning that
  makes Washington State double.
- **The folio must be INSIDE the margin**: "The entire content on the page,
  including page numbers, must fall WITHIN the margins specified", and "Page
  numbers should remain at the bottom center of the page, above the 1 inch
  margin." So the class's `includefoot` layout is required here, not merely
  harmless — unlike at Washington State and Wichita, nothing is left
  unimplemented on page numbers.
- **No signature page, on a direct quote**: "There no longer is a signature
  page. Use form IV and do not include it in the manuscript." Physical
  signatures still exist — Form IV goes to the Graduate Division **on paper** —
  they just never touch the filed PDF. The committee is named on the title page.
- **Every skip on the title page is shrinkable, and it has to be.** Sample B is
  itself a nearly full page (2.1in to 9.8in) set in a narrow 11pt face with a
  one-line title. Reproduced rigidly at this class's size, an ordinary Mānoa
  title page — two-line title, four or five members, a keyword line — **spills
  onto a second sheet**, silently, carrying a page number. Two drafts did
  exactly that before the `minus` components were added. Do not "tidy" them back
  into rigid skips.
- `\gradprogram` carries any permitted specialization in parentheses, e.g.
  "Zoology (Marine Biology)" — only five specializations may appear at all, and
  only with the programme's permission.
- **Accessibility: none published** by the Graduate Division. Searched, not
  assumed: the 20-page manual has no occurrence of accessibility, alt text,
  tagged, WCAG, PDF/A, screen reader, 508 or Title II, and neither the Style
  Policy, Format nor ProQuest page carries one. A Mānoa **college** publishes an
  ETD template that speaks of federal standards; a college page is not the
  Graduate Division and is not a source.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors, **zero missing characters**, and only the intended
`\thesisnoapprovalpage` warning. veraPDF `--flavour ua2` reports compliant, 1727
rules passed, 0 failed. Title page rendered and compared against Sample B.
