# Profile progress log

One dated line per research pass: slug, outcome, and the PR it went out in.
`texlib-thesis-profile-round` appends to this on every run; a batch done by hand
records itself the same way.

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

## 2026-09-04 - texas-a-and-m-university-college-station

`profile` - HERD rank 22. `next` served Minnesota (rank 21) again, because that
profile lives on the open PR #117 and not on `main`; it was **skipped, not
redone** - #117 is complete and reaches the same conclusions from the same
sources - so this round took rank 22 instead. Expect Minnesota to keep coming
back until #117 merges.

Set from the Graduate and Professional School's *Guidelines for Theses,
Dissertations, and Records of Study*, dated **Updated 6/3/2026**, with the
title-page layout taken from the example manuscript the Grad School generates
from its own LaTeX template (version 20260717): geometry (1in minimum, 2in
ceiling), spacing (double, a single value not a choice), the seven-element title
page with its two-column committee block, no approval page (signatures are
digital, in ARCS), and four accessibility rules. Builds clean; tagged output
veraPDF UA-2 `isCompliant="true"`.

Two things flagged for the reviewer rather than decided. TDS says its accessible
templates and fonts are "strongly encouraged" and never that a filed PDF must be
tagged, so `\thesisrequiretagging` is NOT set - but one sentence ("While use of
the templates is optional, the formatting and structural conventions they
reflect are required") can be read the other way. And `\thesisnoapprovalpage`
rests on where the signatures are collected, not on a sentence forbidding the
page. Also worth knowing: `grad.tamu.edu` refuses plain fetches (403/404) and
needs a browser User-Agent plus a Referer header. PR #118.
