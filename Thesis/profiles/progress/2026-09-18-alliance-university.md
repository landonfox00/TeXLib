# 2026-09-18 — alliance-university

**blocked** — alphabetical fallback. PR #250. Round of ten, institution 5 of 10.

**Alliance University (formerly Nyack College, incl. Alliance Theological
Seminary) is closed.** There are no current requirements to read. The Middle
States Commission on Higher Education's notice of 2023-09-01, "Alliance
University Accreditation Ceases August 31, 2023"
(`msche.org/2023/09/01/alliance-university-accreditation-ceases-august-31-2023/`),
says the Commission "acted to note that accreditation for Alliance University,
including all locations, will cease on August 31, 2023", after the
institution notified it of closure.

- `alliance.edu` does not resolve and `www.nyack.edu/` returns 404. A later
  pass need not look for a thesis guide there.
- NYSED keeps an "Alliance University Closure Information" page (records,
  teach-out); it returned no usable text to a scripted fetch and was not
  needed for the finding.
- Same category as `alderson-broaddus-university` (PR #245): the IPEDS
  worklist is built from HD2023 and still lists it. The block is permanent
  unless the worklist is regenerated from a newer IPEDS year.
