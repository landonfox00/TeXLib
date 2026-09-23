# 2026-09-12 — university-of-kentucky

**profile** — HERD rank 67. PR #196.

Complete except accessibility: geometry (1.5in left for binding, 1in elsewhere),
double spacing chosen out of UK's three permitted values, and both pages built
from the Graduate School's own specimens. Accessibility is recorded as
**Not published** — no Graduate School page, form or FAQ read on the access date
mentions it.

Things a later pass must not rediscover:

- **The dissertation specimens are dead links on the Graduate School's own
  page.** Everything under
  `gradschool.uky.edu/sites/gradschool.uky.edu/files/Documents/ThesisDissertationPrep/`
  (`Dissertation_Title_Page.pdf`, `DissertationExample05-06.pdf`, …)
  301-redirects to HTML. The **thesis** specimens under
  `/sites/default/files/2025-05/` are live, and the dissertation prose is the
  thesis prose with the noun swapped, so the pages were built from those.
- The specimens print `(Director of Thesis Signature)` above each label; the
  prose overrides that — "NO signatures are to be reproduced in electronic
  theses ... TYPE the names". The profile follows the prose. Do not "restore"
  the signature rules from the specimen.
- A UK Libraries research guide (`libguides.uky.edu`) states an **April 20,
  2026** ADA Title II date for ETD submissions. That is a library guide, not a
  source under RESEARCHING.md, and no Graduate School page repeats it. It is
  recorded in the profile header as a lead. If it ever lands on a Graduate
  School page, that date is UK's own — do not reconcile it with anyone else's.
- Layout trap, likely to recur: a `\vfill` on the main vertical list inside
  `titlepage` makes the page builder ship out early and spills the last block
  onto a second page. The fix used here is to wrap the whole page in
  `\vbox to \textheight{...}`, which works because `\prevdepth` is -1000pt at
  the top of a fresh page so no interline glue is added above the box.
- The profile defines `\ukcollege{}` (the specimen names the COLLEGE, not the
  program) and `\ukdgs{}` (the Director of Graduate Studies, named on the
  approval page), and wants `\graddate{2027}` — a bare year, since the title
  page's last lines are a year and a copyright line using it.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
