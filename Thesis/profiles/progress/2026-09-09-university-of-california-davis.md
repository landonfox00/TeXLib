# 2026-09-09 — university-of-california-davis

**profile** — HERD rank 36. PR #164.

Set: geometry (1in flat), spacing (double), the title page reproduced from the
Graduate Studies specimen, `\thesisnoapprovalpage`, and four accessibility
entries plus `\thesisrequiretagging` and `\thesisrequiredocumentlanguage`. Left
to the neutral fallback: chapter openings and `\thesisrequirepdfstandard` (Davis
names no PDF standard).

Things a later pass should not have to rediscover:

- **The committee approval lives on the title page**, which is why the profile
  sets `\thesisnoapprovalpage`. Davis is also the first institution here where
  the *unsigned* page is the one that belongs in the filed PDF: the signed copy
  goes to GradSphere separately, and the ProQuest upload "will be unsigned, and
  include blank signature lines". Arizona and Mount Sinai are the other way
  round. Do not "fix" the blank rules.
- **This profile deliberately prints the folio on the title page** — the only
  one in the directory that does. Davis requires it ("The title page is always
  page i", "no unnumbered pages"). A Davis document must call `\frontmatter`
  before `\thesistitlepage` for that folio to read `i`.
- **`\thesisrequiredocumentlanguage` is a derivation, not a quote.** Davis
  requires WCAG 2.1 Level AA, which includes SC 3.1.1 Language of Page; Davis
  never names the document language itself. Flagged in the profile header and in
  the PR as a line a reviewer may strike.
- **The April 2026 ADA Title II date here is correct** and is the large-public-
  entity date. Other profiles in this directory say April 2027 for smaller
  entities. Both are right.
- **`grad.ucdavis.edu` returns 403 to WebFetch and to curl with any User-Agent.**
  Read it in the Browser pane. The formatting requirements are inside a
  JavaScript accordion (`ul.list--accordion`) whose bodies are `<li
  id="accordion-N">` siblings hidden with `display:none`; "Expand All" did not
  make them visible to the accessibility tree. Pull them straight out of the DOM
  by walking that list and reading each `aria-controls` target.
- **The title-page specimen is on Box** at `ucdavis.box.com/v/TitlePageSample-TD`
  — page 1 annotated in red, page 2 clean. Same Box download recipe as Arizona:
  seed a cookie jar with the `/v/` page, then GET
  `index.php?rm=box_download_shared_file&shared_name=…&file_id=f_…`.
