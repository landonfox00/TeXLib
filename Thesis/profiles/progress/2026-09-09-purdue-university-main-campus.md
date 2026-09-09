# 2026-09-09 — purdue-university-main-campus

**profile** — HERD rank 39. PR #167.

Set: geometry (1in body, 1.5in top on the two front pages), spacing (1.5 — not
a choice at Purdue), the title page and the Statement of Committee Approval
page, `\thesisrequiretagging`, `\thesisrequiredocumentlanguage`, and eight
quoted accessibility entries. Left to the neutral fallback: chapter openings and
`\thesisrequirepdfstandard`.

Things a later pass should not have to rediscover:

- **Purdue forbids filing from a non-official template**, and publishes its own
  LaTeX/Overleaf one. "Please do not use a non-official template or attempt to
  recreate a template. You must use and work directly within the official
  template." So this profile is a **record**, not a filing route, and its header
  says so at the top. Do not soften that. Anyone who actually needs a Purdue
  thesis should start from Purdue's Overleaf template.
- **Purdue's Templates page has a dropped "NOT"**: it renders the prohibition as
  "Please DO override template formatting, mix formatting methods, use a
  non-official template, or attempt to recreate a template." The handbook's
  wording settles the intent. Quoted as printed in the profile, with the reading
  noted — do not silently mend it, and do not read it as permission.
- **The Standard handbook has a copy-paste error**: its section 1.1 refers to
  "the official Purdue APA Thesis Template". Every other reference says Standard.
- **Times New Roman 12pt is required**, so the class's Latin Modern is out of
  spec independently of the template rule — same situation as Arizona State.
- **Page numbering is one arabic sequence beginning at page 2** (the Statement
  page), with no roman front matter at all. Unexpressible.
- **Accessibility is binding and dated Spring 2027**, with an explicit
  tagged-PDF sentence ("If your final submission is a PDF, it must be a tagged
  PDF") and a stated consequence — non-compliant submissions are returned.
  `\thesisrequiredocumentlanguage` is a WCAG-derivation, as at UC Davis.
  The Spring 2027 date and UC Davis's April 2026 date are both correct.
- **Fetching**: `purdue.edu` pages are JS-rendered — read them in the Browser
  pane and pull document links from the DOM. The handbook `.docx` (8.3 MB)
  needs a cookie jar seeded from the Templates page plus a matching `Referer`,
  or the WAF returns HTML. Read it with `zipfile` on `word/document.xml`; the
  `w:pgMar` values there independently confirm the 1in/1.5in margins.
