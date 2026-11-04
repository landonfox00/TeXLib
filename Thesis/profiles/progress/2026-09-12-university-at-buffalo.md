# 2026-09-12 — university-at-buffalo

**profile** — HERD rank 65. PR #194.

Complete: geometry (1in all four sides), double spacing, the title page built
from the Graduate School's own ETD Template, `\thesisnoapprovalpage`, and nine
accessibility requirements plus `\thesisrequiretagging`. Nothing left to the
neutral fallback. The typeface rule ("simple fonts ... e.g. Arial, Helvetica,
Tahoma") is recorded in the header only; the class has no font hook and all four
named examples are sans-serif, which leaves the class's Latin Modern in doubt.

Things a later pass should not rediscover:

- The ETD guidelines page and the ETD Template **contradict each other twice**,
  and both are current and linked from the same page: page-number placement
  ("upper right, lower right or bottom center" vs "Only the page number,
  centered in the bottom margin ... is allowed") and PDF conversion ("Use
  Quartz" vs "Avoid ... use of Quartz"). Neither touches a field the profile
  sets. Do not silently pick a side.
- UB's ADA Title II date is **spring 2027**, not April 2026. It is a SUNY
  campus and this is its own published date. Do not "correct" it against a
  neighbouring profile.
- The no-approval-page call rests on an absence, not a sentence: the prescribed
  page order is a closed marked list with no such page, and the M-form is the
  separate approval instrument. Flagged for the reviewer in the PR.
- `www.buffalo.edu` serves plain curl and WebFetch without complaint; the
  `.docx` template needs a browser User-Agent.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round, including
university-of-chicago (a block PR).
