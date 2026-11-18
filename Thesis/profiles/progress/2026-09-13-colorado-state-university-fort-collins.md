# 2026-09-13 — colorado-state-university-fort-collins

**profile** — PR #204.

Complete but for two fields deliberately left neutral. Geometry (1in all four
sides), spacing (double body), the full title page and `\thesisnoapprovalpage`
are all set from the Graduate School's own formatting page and the annotated
title-page specimen it links. No chapter-opening margin is set because CSU
states none — 1in applies to every page. The typeface is left to the class
default because CSU names Times New Roman and Arial as *examples*, not as the
requirement.

Things a later pass should not have to rediscover:

- **CSU publishes no accessibility rule for a filed thesis.** Three Graduate
  School URLs were read and none mentions accessible/tagged/alt text/WCAG/PDF/A
  outside the site footer. CSU *Libraries* does publish encouragement language
  ("encouraged to submit... meet accessibility requirements"), and search
  engines surface it as if it were the Graduate School's. It is not, and under
  RESEARCHING.md a library page is not a source. Recorded as `Not published`.
- **The absence of an approval page is an inference, flagged as such in the
  file.** CSU never writes "must not contain one". What it publishes is an
  exhaustive ordered contents list marking every preliminary page required or
  optional, in which no approval/committee/signature page appears, plus the
  committee printed on the title page. The word "signature" does not occur on
  the formatting page at all. Left for the reviewer to downgrade if they want
  the stricter standard.
- The linked title-page specimen prints "Spring 2014" as its example term. That
  is the specimen's sample value, not a stale-document signal — it was
  re-uploaded in April 2025 and agrees with the current prose on every item.
- The title page takes the department from `\gradprogram`, since the class has
  no separate department field and CSU wants the department on that line.
