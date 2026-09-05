# 2026-09-05 — vanderbilt-university

**profile** — HERD rank 24. PR #123. Round of ten, institution 2 of 10.

Geometry, spacing and the ETD title page set; `\thesisnoapprovalpage` declared.
Governed by the Graduate School's live Thesis & Dissertation Guidelines page,
with the exact title-page layout taken from the "Title Page Format" specimen in
the complete Format Guidelines PDF and from the ETD title-page sample the live
page links. `\thesissetchapteropening` left unset — no such rule is published.

Things a later pass should not have to rediscover:

- **The 08_2021 PDF is NOT a superseded edition.** Its filename makes it look
  stale beside an undated live page, but the two state the margin and spacing
  rules in identical words and the live page links the PDF as its own complete
  text. They were compared clause by clause. The live page is newer only in
  linking three sample pages marked "NEW"; where the samples and the PDF's own
  older specimens differ, the samples win.
- **The margin rule is a RANGE with a MAXIMUM**, which is the reverse of the
  usual "at least" rule: "a minimum of one-half inch … and a maximum of one inch
  from top, bottom, left and right". A *wider* margin can be out of spec here.
  Do not "correct" this against a neighbouring profile's minimum-only rule.
- **Spacing is the student's choice** — single, one-and-a-half or double are all
  permitted. `double` is a default in this profile, not Vanderbilt's rule.
- **There are two title pages and only one of them is filed.** The ETD version
  (typed committee names under "Approved:", no rules) is the manuscript's first
  page; the signature version is circulated to the committee and uploaded to
  VIREO as an administrative file. `\thesistitlepage` produces the ETD one.
- **Physical signatures are still collected** — "Committee member signatures on
  the title page must be originals" — but on that separate sheet, not in the
  manuscript. The required arrangement contains no approval page at all, hence
  `\thesisnoapprovalpage`.
- **Specimen check found a real layout error.** A first draft used `\vfill` to
  push the "Approved:" block to the page foot; rendering the school's own ETD
  sample showed it flows continuously and ends about three quarters down. Fixed
  before commit. The gaps themselves are not prescribed ("Spacing on the title
  page will vary according to the length of the title"), so they approximate the
  specimen.
- **No accessibility rule is published.** The 1,183-line Format Guidelines PDF
  has exactly one occurrence of "accessib" and it is "the SED survey accessible
  at https://sed-ncses.org". Recorded as `{Not published}`; no flag raised.
- `https://gradschool.vanderbilt.edu/academics/theses/submission.php` returns
  **HTTP 500**. Don't waste a fetch on it; the live guidelines page covers
  submission.
