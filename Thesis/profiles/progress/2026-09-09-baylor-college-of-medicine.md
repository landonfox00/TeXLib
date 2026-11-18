# 2026-09-09 — baylor-college-of-medicine

**profile** — HERD rank 42. PR #170.

Set: geometry (1.25in all four sides), `\thesissetchapteropening{2in}`, spacing
(double), the title page and the three-block signature page. Left to the neutral
fallback: every accessibility declaration.

Things a later pass should not have to rediscover:

- **NOT Baylor University.** Baylor College of Medicine (bcm.edu, Houston) and
  Baylor University (baylor.edu, Waco) are separate institutions with different
  thesis rules, and a search for "Baylor dissertation guidelines" returns Waco's
  first. Nothing here comes from baylor.edu.
- **The current instructions are behind a login.** The GSBS forms page links the
  Ph.D. and M.S. instructions to `intouch.bcm.edu`, which redirects an anonymous
  request to `login.microsoftonline.com`. This profile rests on the copy GSBS
  still serves publicly at `bcm.edu/sites/default/files/2020-01/`, dated January
  2020. Every figure is verified against a BCM URL; none is verified as current.
  Someone with BCM credentials should diff the intouch copy against it. That is
  the single thing most worth finishing on this file.
- **Two visible signs of age in the 2020 copy**: its title-page specimen dates
  itself "June 17, 1999", and its signature-page specimen prints a named Dean.
  The profile does not reproduce the name — `\bcmdean{}` is empty by default and
  the rule prints bare.
- **The strongest page-layout wording in the directory**: "the format of the
  title page must be followed exactly. Deviation in format will not be accepted
  and will prevent you from graduating."
- **A real `\thesissetchapteropening{2in}`** — the first one this round. "On the
  first page of every major division of the dissertation (e.g. for new
  chapters), leave a 2 inch margin from the top of the page."
- **The class fails the typeface rule**: "Times New Roman (12 point) or Arial
  (11 point)", a closed list of two. Same as ASU (#165) and Purdue (#167).
- **Do not widen the left margin for binding.** 1.25in is stated flatly for all
  four sides even though four hardcover copies are submitted.
- **The program-approval line has no second "THE".** The template reads
  "APPROVED BY THE Department/Program Name GRADUATE PROGRAM" and the examples
  are listed with the article, so the specimen's line break falls after "THE".
  A first pass rendered "APPROVED BY THE / THE CANCER & CELL BIOLOGY GRADUATE
  PROGRAM"; caught by rendering.
- **Pagination is one continuous sequence**, centred at the bottom, with no
  roman front matter — so no `\frontmatter`.
- **Accessibility: nothing in the 2020 edition.** Recorded as an absence in the
  source that was read, explicitly not as a claim about GSBS today.
