# 2026-09-13 — the-university-of-texas-health-science-center-at-houston

**profile** (deliberate partial) — PR #212.

Set: institution name, geometry, spacing, accessibility (an absence). Left to
the neutral fallback on purpose: the title page and the approval page.

The finding that shapes the whole file:

- **UTHealth Houston has no single filing standard.** Its doctoral degrees are
  filed under at least two incompatible rule sets:
  - **GSBS** (jointly run with MD Anderson): margins stated as *minima* — left
    ≥1.25in, top/bottom/right ≥0.8in — with the Approval Page placed **first**,
    ahead of the title page. **Already encoded** under
    `the-university-of-texas-md-anderson-cancer-center.tex`, which IPEDS
    records as that school's degree grantor.
  - **School of Public Health**: margins stated *exactly* — top 1.25, left
    1.25, bottom 1.1, right 1 — with a required Signature Page laid out quite
    differently.
  - **McWilliams School of Biomedical Informatics** awards a PhD and publishes
    no findable formatting requirements.
- **The geometry that is set is SPH's exact figures, chosen because they also
  clear GSBS's minima** (1.25 meets the 1.25 left floor; 1.25/1.1/1.0 all
  exceed 0.8). So a document built with it is in spec at **both** schools.
  Do not "simplify" those four values toward the GSBS minima — that breaks SPH,
  whose numbers are exact.
- **Leaving geometry unset would have been strictly worse**, which is why this
  file departs from the Stanford honest-partial pattern on that one field: the
  class's neutral 1in-all-round is *out of spec at both schools*, since both
  require more than 1in on the left.
- **`\thesisnoapprovalpage` would be flatly wrong** — both schools require an
  approval/signature page. The neutral page renders, which at least puts a page
  where both expect one. Both schools' layouts are transcribed in the file for
  whoever finishes it.
- **Neither school publishes an accessibility rule.** SPH's checklist contains
  no *accessible / accessibility / alt text / WCAG / tagged / PDF/A*; the same
  was established for GSBS on 2026-09-05 and is recorded in the MD Anderson
  profile.
- To finish this properly someone has to decide what one UTHealth profile
  should print when its two schools disagree — most likely by splitting it in
  two once the class can express that, rather than picking a winner.
