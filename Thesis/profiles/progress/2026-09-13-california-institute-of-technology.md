# 2026-09-13 — california-institute-of-technology

**profile** — PR #209.

Complete. Geometry (left 1.5in, other three 1in), double spacing, the title
page and `\thesisnoapprovalpage` are all set from the Graduate Studies Office's
April 2024 Regulations. Left neutral: chapter-opening margin (Caltech states
none) and typeface.

Things a later pass should not have to rediscover:

- **The margin table is a `pdftotext` trap, and the garbled reading is the
  exact inversion of the rule.** Extraction produces "Margins - 1½ inches /
  Left margin - 1 inch / Right margin / Top and bottom - 1 inch", which reads
  as a 1in left margin. The page rendered at 110dpi says: **left 1½in, right
  1in, top and bottom 1in**. Read this one off the image.
- **A superseded edition is still on the server** and search engines surface
  it: `phd-thesis_guidelines_rev_1-11-16.pdf` under
  `gradoffice.caltech.edu/documents/6332/`. The current one is
  `.../documents/28130/phd-thesis_guidelines_rev_04-2024.pdf`.
- **The specimen also mis-extracts**: "California Institute of Technology /
  Pasadena, California" comes out flush left in `-layout` text and is centred
  on the page.
- **"Thesis by", not "Dissertation by"** — Caltech calls the document a thesis
  throughout, PhD included, so that string is fixed in the profile rather than
  taken from `\thesis@DocNoun` (which `\doctype{dissertation}` would turn into
  "Dissertation").
- **Two dates, deliberately different**: the year is the year the degree is
  conferred at Commencement, which "may be the following calendar year"; the
  parenthesised date below it is the thesis examination. Separate setters,
  neither reusing `\graddate`.
- **Two rules a profile cannot express**, in the file header: page numbers go
  at the **top**, ≥0.75in down and within the margins (the class's foot folio
  is wrong here); and "Embedded fonts, which should be either TrueType of Type
  1, are required for the PDF" — this class embeds OpenType as Type0/CID, which
  satisfies the substance but not the letter. Flagged for a reviewer rather
  than silently ignored.
- **No accessibility rule for a filed thesis.** Caltech *does* run an
  institute-wide digital accessibility standard (WCAG 2.1 AA for digital
  content and platforms), which the Grad Office regulations do not invoke —
  recorded in the header as a thing to re-check, not encoded as a filing rule.
- Layout note: the specimen is **not** vertically centred. Centring put the
  title 2.62in down, about an inch low; it now starts at 1.74in with the slack
  taken by a `\vfill` between the degree and the institute block.
