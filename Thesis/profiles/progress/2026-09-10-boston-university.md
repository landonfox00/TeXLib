# 2026-09-10 — boston-university

**profile** — HERD rank 35. PR #176.

Complete: geometry (1.5in top and left, 1in right and bottom), double spacing,
the title page and the readers' approval page from the Libraries' own specimen
pages, and an accessibility finding of **Not published**. Nothing is left to the
neutral fallback. `\thesissetchapteropening` is not called — BU's 1.5in top
margin applies "at all times", not just to chapter openings.

Four things a later pass should not have to rediscover.

**The source is a LibGuide, and that is correct here.** `RESEARCHING.md` rules
out library guides; at BU the Libraries *are* the filing authority — "Submitting
your thesis or dissertation to Boston University Libraries is the last step to
fulfill at the University before you graduate" — and the guide says of itself
"This guide takes precedence should there be any conflict in formatting or
standard requirements." BU has no central graduate school; all thirteen schools
file through this one guide. The full requirements are in a PDF linked from the
guide's Step 2 page. Guide last updated 26 Aug 2026.

**Signatures look self-contradictory and are not.** The guide requires original
signatures (DocuSign for nine schools, wet ink for the rest, "Photocopied,
scanned, faxed, or other methods of reproduced signatures will not be accepted")
*and* says "Be certain to include a copy of this readers' approval page without
signatures in the thesis or dissertation submitted electronically." Both are
quoted in the profile so nobody reconciles them the wrong way. The filed page
carries rules with typed names beneath, per the specimen.

**BU publishes nothing on accessibility.** The full guide PDF has zero hits for
"accessib" as accessibility (only open *access*), "alt text", "tagged", "WCAG",
"PDF/A", "screen reader", "508" or "Title II". Recorded as **Not published**,
plus a second entry for BU's two actual file constraints (fonts embedded, no
security, "Everything allowed"), which are preservation rules rather than
accessibility ones.

**A LaTeX trap worth remembering.** `\parbox[t]{w}{}` with an empty body is
**0pt wide**, not `w` — a vbox takes the width of its widest line and an empty
one has none. The approval page's label column therefore collapsed and shifted
whole rows left for any reader declared without a label. Fixed with a `\strut`,
and the reason is commented in place. Any future profile building a two-column
row this way will hit it.

The profile adds `\buschool` (the official school name, which must come from
BU's fixed list of twelve — the list is quoted in the file, including BU's
warning about Sargent's), `\bupriordegrees`, and `\bureader{Ordinal}{Name}{Title}`.
