# 2026-09-05 — the-university-of-texas-md-anderson-cancer-center

**profile** — HERD rank 23. PR #122. Round of ten, institution 1 of 10.

Geometry, spacing, title page and approval page all set and verified. The
governing source is the graduate school's own graduation page
(`gsbs.uth.edu/academics/graduation`), with the title-page and approval-page
layouts taken from the official Word template it links. Nothing was left to the
neutral fallback except `\thesissetchapteropening`, which is unset because GSBS
publishes no deeper opening margin.

Things a later pass should not have to rediscover:

- **The graduate school is not named like the institution.** IPEDS records the
  degree-granting body as "The University of Texas MD Anderson Cancer Center",
  but the rules belong to the joint *MD Anderson Cancer Center UTHealth Houston
  Graduate School of Biomedical Sciences*. Do not go looking for a separate
  MD Anderson graduate school; there isn't one.
- **The margins are stated as MINIMA**, not exact figures: left ≥ 1.25in,
  top/bottom/right ≥ 0.8in. The profile sets left=1.25in exactly and takes 1in
  for the other three from the school's own template (`w:pgMar` top/right/bottom
  = 1440 twips). 0.8in would be equally in spec — that is a judgement recorded
  in the profile header, not a finding.
- **GSBS orders the Approval Page BEFORE the Title Page**, the reverse of the
  library templates. The profile cannot enforce that; it is flagged in the
  header and in the PR.
- **Physical signatures are still collected.** The committee signs the approval
  page and the Dean signs it afterwards.
- **No accessibility rule is published.** The graduation page's full text has no
  occurrence of "accessible", "accessibility", "alt text", "WCAG", "tagged" or
  "PDF/A"; the forms page has none; a site search returns only
  disability-accommodation contacts. Recorded as `{Not published}`, and no
  check-flag is raised. Other UT-system schools have begun adding such rules, so
  this is worth re-checking rather than treating as settled.
