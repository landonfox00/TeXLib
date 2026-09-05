# 2026-09-05 — university-of-california-berkeley

**profile** — HERD rank 32. PR #132. Round of ten, institution 10 of 10 — the
round completed.

Geometry, spacing, title page, `\thesisnoapprovalpage`, and **two accessibility
check-flags plus eight recorded requirements** — the richest accessibility
record in the directory. Only `\thesissetchapteropening` is unset.

Things a later pass should not have to rediscover:

- **BERKELEY REQUIRES SINGLE SPACING.** "Your manuscript must be single-spaced
  throughout, including the abstract, dedication, acknowledgments, and
  introduction." Every other institution in this directory either requires or
  permits double. A well-meaning pass that "fixes" `{single}` to `{double}` for
  consistency with its neighbours would put a filer out of spec on every page.
  The warning sits at the **top** of the profile, not beside the setting, for
  that reason.
- **The ADA Title II date here is April 2026**, the large-public-entity deadline.
  Other profiles legitimately carry April 2027 (smaller public entities). Both
  are right — do not reconcile them.
- **The accessibility mandate is in the graduate school's own prose**, not read
  off a template — unlike Florida (#125), where the values came from the
  template's `\DocumentMetadata`. Berkeley states WCAG 2.1 Level AA outright, and
  lists key components: tags, table headers, reading order, alt text, colour
  contrast, and metadata including **language**. That last one is what
  `\thesisrequiredocumentlanguage` is raised on.
- **`\thesisrequirepdfstandard` is NOT raised, deliberately.** WCAG 2.1 AA is a
  *web content* standard, not a PDF standard; it is not what
  `\GetDocumentProperties{document/pdfstandard}` reports, and declaring it there
  would make the class compare two incomparable strings and emit an advisory
  nobody could act on. Recorded verbatim instead.
- **`\author` is the bare registered name.** "Do not list previous degrees on
  your title page", and the name must match the Registrar's record. That is the
  opposite of Emory (#129) and MD Anderson (#122) in this same round, which both
  want prior degrees on the page.
- **`\graddate` is a SEMESTER, not a month** — "Degrees are conferred in Fall,
  Spring, and Summer." `\graddate{Spring 2027}`. Berkeley is the only institution
  this round that wants a semester there.
- **The title page's line breaks are mandatory**: "Line breaks must match this
  example." Note that "in", "in the" and "of the" each occupy a line of their
  own — it looks like an accident and is not. Nothing on the page is bold, and
  the title stays in mixed capitalisation.
- **"University of California, Berkeley" must be written out in full** — "do not
  abbreviate to UC Berkeley or just University of California" — so it is
  hard-coded rather than derived.
- **Committee prefixes are "Professor"** and Co-Chair "must be hyphenated and
  capitalized exactly as 'Co-Chair'".
- **No signatures anywhere.** Approval rides on the **Final Signature eForm** in
  CalCentral, outside the manuscript. Berkeley cross-checks it: "the committee
  listed on your title page (and on the final signature eForm you will submit)
  must match your currently approved committee" — so the title-page committee
  list is load-bearing and a mismatch stops a filing.
- The Sample Title Page is a Google Doc; `…/export?format=txt` and
  `…/export?format=pdf` both work without a login, and its **page 2** is the
  specimen (page 1 is a stub reading "Tab 1").
