# 2026-09-06 — academy-for-jewish-religion-california

**profile (honest partial)** — alphabetical fallback. Round of ten, institution
6 of 10.

Only the institution name and the accessibility finding are set. **No geometry,
no spacing, no title page** — not because the catalog could not be found, but
because AJRCA publishes no figures. Modelled on `stanford-university.tex`.

Things a later pass should not have to rediscover:

- **AJRCA STATES ITS MANUSCRIPT FORMAT BY DELEGATION, AND THAT IS ALL IT SAYS.**
  "The completed thesis, in appropriate format and style (based on Chicago
  Manual of Style), must be submitted to the advisor by April 1 of the year of
  ordination." The sentence recurs near-verbatim for all four thesis programs —
  Rabbinic (p. 20), Cantorial (p. 28), Chaplaincy, M.A. — with trivial wording
  changes and no substantive difference. Chicago is a third-party style guide,
  not an AJRCA specification, so nothing is set from it. **Do not "finish" this
  profile by transcribing Chicago's margins.**
- Counts in the 101-page 2026-2027 catalog: **thesis 67, margin 0, title page 0,
  double-spac 0, font 0.** It was read in full; re-grepping it will not help.
- **THE APPROVAL PAGE IS REQUIRED AND IS STILL LEFT NEUTRAL ON PURPOSE**, which
  is the opposite call from MIT (#135) and Abilene Christian (#136) in this same
  round. AJRCA's thesis genuinely carries one — "the advisor, reader, and Dean of
  the Rabbinical School will certify on a signature page that the thesis is
  satisfactory" — so `\thesisnoapprovalpage` would be *wrong*. But no layout,
  wording or field order is published, so writing a page would invent one.
  Leaving the macro alone is the documented "not yet checked" state and renders
  the neutral page, which is the conservative outcome. **Do not harmonise the
  three files.**
- **The signatories differ by program**: Rabbinic names three (advisor, reader,
  Dean of the Rabbinical School); Cantorial, Chaplaincy and the M.A. name two
  (advisor and reader). One fixed page could not serve all four — a further
  reason not to write one from the prose.
- **The filed thesis is a BOUND PHYSICAL OBJECT**: "the student will submit two
  bound copies to the Academy." AJRCA has not moved to electronic filing. That
  makes a binding margin a real concern, and AJRCA publishes none — which is why
  the geometry is left unset rather than defaulted to a symmetric 1in.
- **Signatures are physical.**
- **Current catalog is 2026-2027**, linked from
  https://ajrca.edu/students/academic-catalog/. Older editions (2019-20, 2020-21,
  2022-23) rank highly in search and are still on the server — take the one the
  catalog page links.
- **THIS IS THE CALIFORNIA INSTITUTION.** IPEDS UNITID 457271, `ajrca.edu`, Los
  Angeles. The separate, unaffiliated **Academy for Jewish Religion (New York)**
  — `ajr.edu`, blocked in this same round (#139) — is a different school with a
  different terminal document (a Master's *Project*, not a thesis). Sources must
  not cross between the two files.
- **To finish this profile**: ask the AJRCA office whether the Academy enforces
  any figures beyond Chicago, and whether it publishes a signature-page template.
  If the answer is "Chicago and nothing else", the file is already complete and
  should say so.
- Built clean (0 errors); veraPDF `--flavour ua2`: 4812 passed, 0 failed. The
  neutral approval page renders, which is the intended behaviour here.
