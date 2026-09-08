# 2026-09-08 — adventhealth-university

**blocked** — alphabetical fallback. Round of ten, institution 6 of 10.

AdventHealth University is a health-sciences institution (Orlando FL) whose
graduate work culminates in a capstone, and it publishes no manuscript format:
the catalog delegates to program handbooks in as many words.

Things a later pass should not have to rediscover:

- **The delegation is in the current catalog, not an old one.** 2026-2027
  Academic Catalog, *Degree Requirements: Graduate Programs*: "Successfully
  complete the graduate capstone requirement (refer to Program Handbook for more
  information)." The capstone itself is defined only by content — "a scholarly
  report on a study, grant, or project which synthesizes and/or applies current
  evidence and knowledge" — never by layout.
- **The whole-catalog search is decisive and was run on both current volumes.**
  2026-2027 Academic Catalog (`catoid=82`) and 2026-2027 Student Handbook
  (`catoid=84`): zero matches for `margins`, zero for `dissertation`, zero for
  the phrase `"signature page"`, zero for the word `"double-spaced"`. `thesis`
  matches only two course codes in the whole catalog — ROBO 690 Capstone/Thesis
  and HTCA 699 Thesis — plus the Robotic Surgery M.S. program that requires them.
- **Fetch note.** `catalog.ahu.edu` (Acalog / Modern Campus) returns an EMPTY
  body to WebFetch. The Browser pane renders it. Its `search_advanced.php`
  endpoint also returns an empty page when navigated to directly, but works
  perfectly when `fetch()`ed from a page already on the origin — that is how
  these counts were taken.
- **Catalog ids drift, so look them up rather than reusing these.** As of
  2026-09-08: `82` = 2026-2027 Academic Catalog, `84` = 2026-2027 Student
  Handbook, `74` = 2025-2026 Academic Catalog. The option list on
  `catalog.ahu.edu/index.php` carries the mapping. A stale id silently serves an
  ARCHIVED edition that still looks live.
- No accessibility rule for a filed manuscript exists in either volume.
