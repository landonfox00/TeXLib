# 2026-09-13 — dartmouth-college

**profile** — PR #214.

Complete. Geometry (left 1.5in binding side; top/bottom/right 1in), 1.5 line
spacing, and the full title page — including its **examining-committee
signature block and the Dean's signature block** — are set from the Guarini
School's May 2025 thesis guidelines. Left neutral: chapter-opening margin
(Guarini states none) and typeface (Guarini names no face, only an 11pt floor).

Things a later pass should not have to rediscover:

- **The HTML page every search engine points at is gone.** Both Google and
  Dartmouth's own search still return
  `/academics/graduate-registrar/information-submission-thesis-dissertation-or-course-track-fulfillments`,
  which now serves Dartmouth's "Page Not Found". The PDFs it used to link are
  still live under `.../graduate_studies/wysiwyg/`, so the profile cites the
  PDF directly.
- **Four editions of the guidelines are live and the filenames do not sort by
  date** — one misspells the school. All four return HTTP 200:
  `thesis_guidelines_4.pdf` (Updated **05/01/2025** — used),
  `guairni_school_thesis_guidelines_-_updated_2022.pdf` (Updated 05/27/2022),
  `guairni_school_thesis_guidelines.pdf` (the "guairni" typo), and
  `guarini_school_thesis_guidelines.pdf` (Updated 7/30/2018). They agree on
  margins and spacing but **not** on the list of approved majors, and the 2018
  edition names majors Dartmouth no longer offers. **Take the date from the
  page foot, never from the filename.**
- **Signatures go on the title page** — all of them, in one place, committee
  plus the Dean. Electronic signatures are allowed, ideally a high-resolution
  image of an actual one. `\thesisnoapprovalpage` therefore means "the
  approvals are already on the title page", not "nobody signs" — same shape as
  Utah State in this round.
- **Spacing is a floor and the profile sits on it**: "at least 18 points (1.5
  lines)". `onehalf` is the figure Guarini names; `double` also satisfies it.
- **Top/bottom/right margins are a range** — "between 0.5" to 1" wide". The
  profile takes the wide end. Only the 1.5in left margin is exact.
- **The page overflowed on the first try** and pushed the Dean's block to page
  two — which would have put a signature line on the leaf Guarini's pagination
  rules reserve as the blank page after the title page. The skips are now
  deliberately tight; with five committee signatures it will start to crowd,
  and the fix is to tighten further rather than let it spill.
- **Two other title-page formats exist in the same PDF and are not encoded**:
  Engineering Sciences (one extra line, "Thayer School of Engineering", above
  the Guarini line) and MALS. A filer in either should override
  `\thesistitlepage`.
- Two rules a profile cannot express, recorded in the file: a **blank page
  follows the title page**, neither counted nor numbered, which a filer must
  emit themselves; and text must be **at least 11-point**.
- **No accessibility rule is published** in the guidelines. Noted as an absence
  *in the guidelines* rather than across the whole site, because the second
  place to look was the page that now 404s.
