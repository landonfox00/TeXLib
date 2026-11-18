# 2026-09-13 — utah-state-university

**profile** — PR #208.

Complete. Geometry (left 1.5in binding side, other three 1in), double spacing,
and the full title page — including its two-column **signature grid** — are set
from the School of Graduate Studies' 2025 Publication Guide and the annotated
samples in its Appendix A. Left neutral: chapter-opening margin (USU states
none) and typeface (USU permits 10/11/12 pt and names no face, so there is
nothing to encode).

Things a later pass should not have to rediscover:

- **USU still collects physical signatures, and they go on the TITLE PAGE.**
  This is the first school in this series where the signature rules are real
  rather than decorative. `\thesisnoapprovalpage` here means "the approvals are
  already on the title page", **not** "nobody signs" — USU's ordered contents
  list has no separate approval leaf.
- **The grid is two per row, and an odd signatory count centres the last one**
  ("If you have an odd number of signatories, center the odd-numbered one").
  Implemented with a counter: odd count ⇒ the row still has room, even count ⇒
  the Vice Provost starts a row alone and is centred. Confirmed against both
  the three-member sample (4 signatories, 2×2) and the four-member sample (5
  signatories, Vice Provost centred).
- **`\centerline` is not usable under tagging.** Centring that lone box with
  `\centerline` cost **17 veraPDF failures** — "P shall not contain P",
  "P shall not contain Part", "StructTreeRoot shall not contain Div" — because
  it is `\hb@xt@\hsize` around the box and nests structure elements illegally.
  `{\centering …\par}` is ordinary paragraph material and stays conformant.
  Worth remembering for every future profile. The other near-miss:
  `\hspace*{\fill}` either side puts the box flush **right**, because a
  trailing `\fill` merges with `\parfillskip`.
- **`\parindent=0pt`, not a leading `\noindent`.** The grid breaks rows with
  `\par`, so a single `\noindent` straightens only the first row and every
  later left-hand signature line sits indented.
- **Two USU rules a profile cannot express**, recorded in the file header so
  they are not lost: page numbers go in the **upper right**, 0.75in down and
  1in from the right edge (a page style, and a profile owns no page-style
  hook — the class's default foot folio is wrong at USU); and "A ragged right
  margin is strongly recommended" (recommended, so not imposed).
- **The Vice Provost's name is a field, not a constant** (`\usuviceprovost`).
  The 2025 guide's samples print "David F. Feldon, Ph.D." — recorded in the
  file comment so it is one copy-paste away for anyone who confirms it is
  current. USU makes the post-nominal letters mandatory on that line
  specifically.
- **No accessibility rule is published.** The whole guide contains "accessib"
  once, in "remains accessible to the public ... even if ... embargoed" — public
  availability, not assistive technology — and no alt text / WCAG / tagged /
  PDF/A at all.
