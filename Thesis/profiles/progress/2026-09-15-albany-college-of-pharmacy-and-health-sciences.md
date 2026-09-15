# 2026-09-15 — albany-college-of-pharmacy-and-health-sciences

**profile** — PR #234. Tenth and last institution of the round.

Set: geometry (left 1.5in, others 1in), double spacing, and the title page —
which at ACPHS is also the approval page, signed in wet ink by the advisor and
committee. Left neutral: the chapter opening (not required) and the typeface.

For a later pass, so it is not rediscovered:

- **Every `/sites/default/files/` URL on acphs.edu now 404s.** ACPHS moved off
  Drupal, and search engines still serve the dead paths (including the 2022–23
  graduate handbook). The live documents sit under `/wp-content/uploads/` on an
  unguessable date path; read the links off
  `https://www.acphs.edu/current-students/`. The governing document is
  `2026/08/Graduate-Student-Handbook-Updated-AUG-2026.pdf`, Appendix C.
- The type rule is **not encodable as written**: "Type sizes of 10 - 12
  characters per inch or point are acceptable" conflates typewriter pitch with
  points. Left unset deliberately, not overlooked.
- Appendix C is titled for the **M.S.** but its prose repeatedly says "thesis or
  dissertation". Flagged in the PR: a doctoral candidate should confirm it
  governs them. Appendix D is the non-thesis capstone track and is untouched.
- Accessibility is recorded twice on purpose: "Not published", plus the colour
  rule ("Colored figures must be of sufficient contrast such that information
  conveyed by different colors can be distinguished in black and white copies")
  quoted with its actual rationale — photocopies, not screen readers — so a
  later pass does not upgrade it into a WCAG claim ACPHS never made.
- The title page's signature grid is built from `\makebox` rules, not a
  `tabular`: it is blank layout, and tagging it as a table would have a screen
  reader announce rows and columns of nothing.
