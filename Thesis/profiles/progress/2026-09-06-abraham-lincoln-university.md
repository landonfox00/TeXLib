# 2026-09-06 — abraham-lincoln-university

**blocked** — alphabetical fallback. Round of ten, institution 3 of 10.

Not "could not find the requirements". **Abraham Lincoln University does not
require a filed thesis or dissertation at all**, so there is nothing for a
profile to encode.

What was read, both current and both downloaded in full:

- `ALU_Catalog_Univ.pdf` — the University Catalog (Associate, Bachelor's,
  Master's), 143 pages, PDF creation date 2026-01-09.
- `ALU_Catalog_JD.pdf` — the School of Law Catalog, 96 pages.

Occurrences across both: **thesis 0, dissertation 0, margin 0, title page 0,
signature page 0.** The terminal graduate requirement is a three-credit
*Graduate Capstone course* (BUS699, CJS699) — a course, not a filed manuscript.
ALU is a fully online university whose graduate offerings are professional
master's degrees and the JD.

Things a later pass should not have to rediscover:

- **The obvious web search is poisoned by a different institution.** Searching
  "Abraham Lincoln University thesis" returns **Lincoln University (CA)** —
  `lincolnuca.edu`, a separate school with an MBA Thesis Manual and a
  thesis/dissertation LibGuide. That is NOT this institution (ALU is
  `alu.edu`, IPEDS UNITID 488031). Do not write a profile from those pages.
- The catalogs are the right sources and they are linked from
  https://alu.edu/catalog/ (which also lists an Addendum to the School of Law
  Catalog).
- The five "accessib" hits in the University Catalog are all about affordability
  and access to education — "provide accessible, career-focused and lifelong
  learning opportunities" — not document accessibility. There is no accessibility
  rule to record because there is no document to apply it to.
- **This branch creates `Thesis/profiles/institutions.blocked.csv` from
  scratch**, because the only other row for it lives on the still-open PR #114
  (`a-t-still-university-of-health-sciences`). Whichever of the two merges second
  will hit a trivial add/add conflict on that file; the fix is to keep both rows.
- If ALU ever adds a research doctorate, this block should be revisited —
  `alu.edu/academics/doctorate-degrees/` exists as a page, but the University
  Catalog covers only Associate, Bachelor's and Master's.
