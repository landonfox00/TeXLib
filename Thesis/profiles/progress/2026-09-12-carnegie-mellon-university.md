# 2026-09-12 — carnegie-mellon-university

**blocked** — HERD rank 71. PR #200.

Not "could not find it". **CMU publishes no university-wide thesis filing
requirements**, and says so from three directions. Recorded in
`blocked/carnegie-mellon-university.csv`; delete that file to retry if CMU ever
centralises.

What was read, and what it says:

- `cmu.edu/graduate/` — the Office of Graduate and Postdoctoral Affairs. No
  thesis, dissertation, format or template page anywhere in its navigation.
- `cmu.edu/graduate/resources/files/university-wide-graduate-student-handbook-ay25-26.pdf`
  — the **current** University-Wide Graduate Student Handbook, eight pages. The
  word "margin" does not appear; neither does any format rule. Its only mention
  of a dissertation is about All But Dissertation status.
- `library.cmu.edu/services/thesis-dissertation-deposit` and
  `guides.library.cmu.edu/etds` (last updated 2026-07-10) — the Libraries run
  the deposit, and refer formatting away: "Your college or department may have
  additional requirements" and "Check with your department's on thesis
  requirements, formatting, and required submission process" [sic]. Elsewhere
  the Libraries state they do not support formatting or template inquiries.

Two things a later pass should not redo:

- **The College of Engineering publishes its own standards**
  (`engineering.cmu.edu/education/academic-policies/graduate-policies/thesis-dissertation.html`),
  with title page, copyright page and committee signature page templates. That
  is a COLLEGE, not the graduate school, so it cannot found a
  university-level profile — but it is the right starting point if TeXLib ever
  grows per-college profiles, and it is where a CMU engineering filer should be
  sent.
- The Libraries' accessibility page is **encouragement, not a requirement**:
  CMU "passed a Digital Accessibility Policy in early 2025", and "the University
  Libraries *encourages* graduate students … to implement accessibility best
  practices". Nothing to declare with `\thesisrequiretagging`. It does link
  LaTeX-specific guidance (Overleaf's tagged-PDF intro, the AMS guide, Lancaster
  University's checklist).

Blocked rather than shipped as a name-only profile on purpose: a profile in the
directory makes `next` treat CMU as done forever, whereas a block file is one
deletion away from re-queueing.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
