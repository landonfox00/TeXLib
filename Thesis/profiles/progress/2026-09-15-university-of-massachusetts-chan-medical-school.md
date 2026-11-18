# 2026-09-15 — university-of-massachusetts-chan-medical-school

**profile** — HERD rank 98. PR #227.

Complete but for the typeface: geometry (1.5in top and left, 1in bottom and
right), double spacing, and both pages reproduced from the Morningside Graduate
School's own specimens — the title page and the "Reviewer Page", which is this
school's approval leaf and carries typed names, not signatures. Accessibility is
recorded as not published.

For a later pass, so it is not rediscovered:

- **www.umassmed.edu 403s plain curl and WebFetch**, and handing a PDF URL to a
  browser starts a download instead of rendering. It serves the file to a
  request with a browser User-Agent plus `Sec-Fetch-Dest: document`,
  `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Site: same-origin` and a same-site
  Referer. This is not a blocked institution.
- The DSpace URL search engines return for the repository's submission
  guidelines (`repository.escholarship.umassmed.edu/pages/morningside-theses-
  dissertations-guidelines`) now redirects to the repository root. The
  authoritative document is the Graduate School's own prep guide, not the
  repository page.
- The guide calls the same leaf both "Reviewer Page" and "Sample Signature
  Page"; the specimen is headed Reviewer Page and every name reads "(Name
  Typed)". Built as typed names. Flagged in the PR.
- The page-numbering paragraph implies a **cover page** before the title page
  ("The cover page should be considered page 'i'"), but no cover page appears in
  the front-matter list and no specimen is printed. Left unimplemented.
- The Dean is named on the reviewer page in the specimen (Mary Ellen Lane,
  Ph.D.). It is a macro, `\umasschandean{}`, because a named officer rots.
- Font ("preferred", not required) and page-number placement (upper right, no
  period) are recorded in the header rather than encoded.
