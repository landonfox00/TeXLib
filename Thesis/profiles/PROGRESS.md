# Profile progress log

**This file is the archive, not the current log.** From 2026-09-04 each research
pass writes its own file in [`progress/`](progress/) instead of appending here —
one file per institution per round, named `<YYYY-MM-DD>-<slug>.md`. See
[`progress/README.md`](progress/README.md) for why.

The short version: the routine now researches ten institutions a round and opens
one PR per institution, so ten branches were all appending to the end of this
one file. Every sibling conflicted the moment the first merged. A per-institution
file cannot conflict, and it travels with the profile it describes — if a PR is
rejected, its log entry goes with it instead of claiming work that never landed.

What follows is the record up to that change, kept as written. Nothing new is
appended below.

## 2026-09-02 — NSF HERD top-20 batch

Twenty institutions researched in one pass, chosen as the top 20 US research
universities by FY2024 R&D expenditure (NSF NCSES HERD, report NSF 26-304,
Table 4 — see `priority.source`). Every figure below came from a URL opened on
2026-09-02; each profile header carries its own source and access date.

| # | slug | outcome |
|---|---|---|
| 1 | johns-hopkins-university | profile — geometry, spacing, title page, no approval page, PDF/A |
| 2 | university-of-pennsylvania | profile — geometry, spacing; pages left neutral |
| 3 | university-of-california-san-francisco | profile — geometry, spacing; pages left neutral |
| 4 | university-of-michigan-ann-arbor | profile — complete: geometry, 2in openings, spacing, title page, no approval page, 6 accessibility rules |
| 5 | university-of-wisconsin-madison | profile — accessibility only; Wisconsin publishes no margin or spacing rule |
| 6 | university-of-california-los-angeles | profile — geometry, spacing; pages left neutral |
| 7 | university-of-california-san-diego | profile — geometry, spacing; approval page required, layout not encoded |
| 8 | university-of-washington-seattle-campus | profile — records that UW prescribes no formatting, and forbids an approval page |
| 9 | stanford-university | profile — PARTIAL; no format-requirements page found, geometry unset |
| 10 | cornell-university | profile — geometry, spacing; pages left neutral |
| 11 | university-of-north-carolina-at-chapel-hill | profile — geometry, 2in openings, spacing, 7 accessibility rules (WCAG 2.2 AA) |
| 12 | ohio-state-university-main-campus | profile — accessibility only; only one margin figure published |
| 13 | duke-university | profile — geometry (1.5in left), spacing |
| 14 | university-of-maryland-college-park | profile — geometry, spacing |
| 15 | georgia-institute-of-technology-main-campus | profile — geometry (1.5in left), spacing, ADA Title II |
| 16 | yale-university | profile — geometry, spacing |
| 17 | university-of-pittsburgh-pittsburgh-campus | profile — geometry, spacing, accessibility |
| 18 | new-york-university | profile — geometry, spacing |
| 19 | harvard-university | profile — geometry, spacing |
| 20 | columbia-university-in-the-city-of-new-york | profile — geometry, spacing |

All 20 build clean and the tagged output is PDF/UA-2 conformant (spot-checked
with veraPDF on Michigan, UNC, Johns Hopkins and the pre-existing UNR profile,
all `isCompliant="true"`).

**Two that are deliberately incomplete.** Stanford's format requirements were
not findable at a stanford.edu URL on the access date, so its geometry is unset
rather than filled in from the figures third-party sites state confidently.
Wisconsin and Ohio State publish accessibility rules but not a full margin rule,
so those profiles set what exists and nothing more.

**One correction worth keeping.** Search results and several third-party guides
give UCLA a 1.5in left margin for binding. UCLA's own filing requirements say
`LEFT, RIGHT, TOP: 1"`. The profile follows the source.

**What this batch changed in the class** (see the PR): a chapter-opening margin
hook, a way for a profile to state that no approval page is permitted, and the
accessibility declarations — all three were things a profile previously had to
note in a comment and then file out of spec anyway.
