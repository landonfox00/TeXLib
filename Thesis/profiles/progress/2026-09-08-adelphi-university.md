# 2026-09-08 — adelphi-university

**blocked** — alphabetical fallback. Round of ten, institution 2 of 10.

Adelphi grants doctorates but has no central graduate school and publishes no
university-wide manuscript format. Graduate Admissions, the University Bulletin
and the Bulletin's own search were all read; none states a margin, spacing,
title-page or approval-page rule for a filed thesis.

Things a later pass should not have to rediscover:

- **The catalog search works and is worth reusing.** `catalog.adelphi.edu` is
  Acalog; the current bulletin is `cur_cat_oid=44` (2026-27, updated February
  2026). A keyword search runs from
  `search_advanced.php?cur_cat_oid=44&search_database=Search&filter[keyword]=…`.
  WebFetch returns an EMPTY body for every `catalog.adelphi.edu` URL — use the
  Browser pane. Plain curl with a browser UA also returns zero bytes.
- **The one "margins" hit in the whole bulletin is a false positive.** It is in
  Social Work: Doctoral, and it governs the *admission application*: "The
  personal statement should be no longer than 4 [four] double-spaced pages, with
  once inch margins and a 12-pt font". Nothing to do with the dissertation. Do
  not mine it for a profile. `"signature page"` returns no matches at all.
- **Format rules exist, but only per school.** The Gordon F. Derner School of
  Psychology PhD Handbook, the School of Social Work PhD Handbook (updated July
  2025) and the School Psychology Doctoral Handbook each carry their own. They
  are department documents, which RESEARCHING.md excludes. Three schools with
  three handbooks is also positive evidence that no single university rule
  exists to find.
- **The Honors College Thesis guide is undergraduate** and turns up high in
  search. Not a graduate filing requirement.
- Adelphi files through ProQuest ETD Administrator (`siteId=844`). That page
  states ProQuest's requirements, not Adelphi's, and RESEARCHING.md excludes it.
- No accessibility rule for a filed manuscript was found anywhere.
