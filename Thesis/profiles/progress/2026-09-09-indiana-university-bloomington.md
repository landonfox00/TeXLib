# 2026-09-09 — indiana-university-bloomington

**profile** — HERD rank 41. PR #169.

Set: geometry (1in all sides), spacing (double), the title page and the
acceptance page, both from the Graduate School's own `.docx` specimens and
covering both degree levels. Left to the neutral fallback: chapter openings and
every accessibility declaration.

Things a later pass should not have to rediscover:

- **The acceptance page is required and is filed UNSIGNED, with the signature
  rules drawn.** "Your Research Committee members' names and signature lines
  follow and are fully right-justified" and "The page remains unsigned for
  inclusion in your dissertation." So the blank rules are correct — do not
  replace this page with a scan, and do not delete the rules.
- **Two different dates on the two front pages.** The title page carries "the
  date when all requirements have been satisfied — this is not necessarily the
  month in which you defend"; the acceptance page carries the defence date in
  full. The profile adds `\iudefensedate{...}` for the second.
- **Prose and specimen disagree on where the defence date goes**, and the profile
  follows the prose. The master's acceptance specimen puts the date immediately
  after the "Master's Committee" heading, *before* the signature lines; the prose
  at both degree levels says it comes after the names, and the doctoral specimen
  agrees with the prose.
- **"for the degree" on the title page, "for the degree of" on the acceptance
  page.** They really do differ; both are reproduced as written.
- **The typeface list is a recommendation** ("recommended for the ease with which
  they convert to a PDF"), so the class passes as shipped — unlike ASU (#165) and
  Purdue (#167). Size is 11 or 12 point, up to 16 on the title page.
- **The IU seal and branding are forbidden** on any part of the dissertation
  without written permission. No insignia is drawn.
- **Pagination**: the title page counts as i but bears no number, numbering
  *begins* on the acceptance page as ii, and the vita at the end carries no page
  number at all. Running heads are banned. Unexpressible.
- **Accessibility: nothing published.** Both guides at both degree levels plus
  the Thesis & Dissertation index were read in full and contain no accessibility
  language whatsoever. IU Libraries' accessible-PDF guide is a library research
  guide, not the Graduate School's filing requirements, so nothing from it is
  encoded. Beware: a web search for IU thesis accessibility surfaces **UC
  Davis's** April-2026 WCAG sentence as though it were IU's. It is not.
- **The pages carry no revision date**, so nothing here can be dated.
