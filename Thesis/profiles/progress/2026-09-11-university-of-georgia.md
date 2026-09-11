# 2026-09-11 — university-of-georgia

**profile** — HERD rank 43. PR #189.

Complete. Set from the Graduate School's 2025 Style Guide (revised August 2025):
geometry, `\thesissetchapteropening{1.75in}`, double spacing, the title page and
the approval page. Nothing left to the neutral fallback.

Things a later pass must not rediscover:

- **A superseded 2022 edition of the same guide is still reachable**, on a
  *department* host (`comm.uga.edu/sites/default/files/
  theses_and_dissertations-STYLE-GUIDE_2022.pdf`), and it ranks well in search.
  The Graduate School's own page links only the 2025 edition. Do not correct a
  figure here against the 2022 copy.
- **Two dead URLs that search engines still serve:**
  `grad.uga.edu/development/academic/theses-dissertations-overview/formatting`
  and `.../current-students/policies-procedures/theses-dissertations-guidelines/
  formatting/` both 404. The live path is `/current-students/fundamentals/`.
- **The 1.5in left margin is a choice, not the rule** — "a left margin of 1.5
  inches may be used for binding purposes", and the filed electronic copy is not
  bound. The profile takes 1in and says so.
- **Accessibility is genuinely NOT PUBLISHED**, not merely unfound: the 45-page
  guide contains no occurrence of accessib/alt text/tagged/WCAG/screen
  reader/PDF/A, and neither do the four ETD sub-pages. UGA's
  `grad.uga.edu/accessibility-policy/` is a *website* policy (Section 508, WCAG
  2.0) and says nothing about a manuscript.
- **The Dean's name is printed on the approval page and will rot.** The sample
  gives "Ron Walcott, Vice Provost for Graduate Education and Dean of the
  Graduate School"; the profile exposes it as `\thesisgraduatedean` so a
  document can correct it without editing the profile.
- **Committee feeding is non-obvious.** UGA splits the block into "Major
  Professor:" and "Committee:", so the profile reads `\gradadvisor` for the
  former and the `\committeemember` list for the latter, dropping roles (UGA
  forbids Dr./PhD/Professor beside a name). Listing the chair in both places
  prints the name twice — the build render shows exactly that.
- Three different date forms: title page takes the graduation **year** alone;
  the approval page takes the graduation **month and year**; neither is the
  submission month.
