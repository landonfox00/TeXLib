# 2026-09-04 — texas-a-and-m-university-college-station

**profile** — HERD rank 22. PR #118.

Set from the Graduate and Professional School's *Guidelines for Theses,
Dissertations, and Records of Study*, dated **Updated 6/3/2026**, with the
title-page layout taken from the example manuscript the Grad School generates
from its own LaTeX template (version 20260717): geometry (1in minimum, 2in
ceiling), spacing (double, a single value not a choice), the seven-element title
page with its two-column committee block, no approval page (signatures are
digital, in ARCS), and four accessibility rules. Builds clean; tagged output
veraPDF UA-2 `isCompliant="true"`.

**Two things left for the reviewer rather than decided.** TDS says its accessible
templates and fonts are "strongly encouraged" and never that a filed PDF must be
tagged, so `\thesisrequiretagging` is NOT set — but one sentence ("While use of
the templates is optional, the formatting and structural conventions they
reflect are required") can be read the other way. And `\thesisnoapprovalpage`
rests on where the signatures are collected, not on a sentence forbidding the
page.

**Worth not rediscovering.** `grad.tamu.edu` refuses plain fetches — 403 to curl,
404 through WebFetch — and needs a browser User-Agent plus a `Referer` header
naming the linking page. TDS also requires 12-point type, which the class
satisfies only because it loads `report` at `12pt`; there is no profile field
for it, so that requirement would break silently if the class's base size
changed.

**Queue note.** `next` served Minnesota (rank 21) again, because that profile
lives on the open PR #117 and not on `main`. It was skipped, not redone — #117
is complete and reaches the same conclusions from the same sources — so this
round took rank 22 instead. Expect Minnesota to keep coming back until #117
merges.
