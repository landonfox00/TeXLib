# 2026-09-15 — university-of-new-mexico-main-campus

**profile** — HERD rank 97. PR #226.

Complete: geometry, spacing, the title page (which carries the committee), no
approval page, and five accessibility rules including two checkable
declarations. Nothing left to the neutral fallback except the chapter-opening
margin, which UNM does not require.

For a later pass, so it is not rediscovered:

- **UNM's two own documents disagree about the left margin.** `guidelines.html`
  says "Left: 1.25–1.5 in" (twice); `sample-dissertation.pdf` says "Margins need
  to be one inch; however, the left-hand margin may be up to 1.25". The profile
  sets `left=1.25in`, the only figure in spec under both. Do not "fix" it to 1in
  or 1.5in against one document alone.
- **`titlepage` resets the page counter**, and UNM is the first profile whose
  title page is numbered ("page number is i"). Without a carry, the page after
  the title page repeated "i". The profile carries the counter across
  `\end{titlepage}` and advances it. A UNM document must call `\frontmatter`
  *before* `\thesistitlepage`; both orders build, but only that one numbers i.
- The two checkable accessibility declarations (`\thesisrequiretagging`,
  `\thesisrequiredocumentlanguage`) are **entailments** of "must pass
  accessibility requirements in Adobe Acrobat", not items UNM names. Flagged in
  the PR as the file's one judgement call.
- UNM's accessibility instructions tell candidates to *uncheck* Acrobat's
  reading-order and colour-contrast rules because staff check those by hand.
  That is recorded as a requirement, not as an exemption.
- The class has no field for previously earned degrees, which UNM requires under
  the author's name; the profile defines `\priordegrees{}` for it.
