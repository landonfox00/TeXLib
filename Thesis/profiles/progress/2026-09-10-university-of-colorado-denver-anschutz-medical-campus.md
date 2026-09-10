# 2026-09-10 — university-of-colorado-denver-anschutz-medical-campus

**profile** — HERD rank 36. PR #177.

Complete: 1in margins all round, double spacing, the title page and the required
approval page from the Denver | Anschutz Graduate School's own templates, and an
accessibility finding of **Not published**. Nothing is left to the neutral
fallback. `\thesissetchapteropening` is not called — chapters simply start at the
top of a new page with "only regular double space before and after".

**BEWARE THE ARCHIVE.** Two superseded editions of the format guide are still
served under `.../resources/archive/format-requirements-and-guidelines.pdf` and
`.../resources/archive/format-guide.pdf`, and search engines rank both *above*
the current one. The Resources & Forms index links only
`2024-november-format-guide.pdf` ("Effective November 2024"), which is what this
profile follows. Do not "correct" a figure against an archive copy.

**Two requirements the class cannot express, recorded in the header rather than
dropped.** The Quick Start Guide's setup list includes "Alignment: Left" — the
body is to be **ragged right**, and this class justifies — and "Paragraph
indent: 0.5"". Neither is one of the fields `RESEARCHING.md` allows a profile to
set, so both are documented for the author (`\raggedright`,
`\setlength{\parindent}{0.5in}`) instead of being set here. Worth a conversation
about whether the class should grow a hook; I did not assume it should.

**The guide addresses LaTeX authors directly, once**: "If using TeX or LaTeX
typesetting, avoid Type 3 fonts." Recorded as an accessibility entry, since a
Type 3 PDF cannot be searched or read aloud. Latin Modern is not one.

Two smaller notes. The submission line is **fixed as "A thesis submitted to the"
even for a doctoral dissertation** — the guide uses "thesis" throughout "to
broadly refer to all scholarly works" — so it does not follow `\doctype`. And
`\gradprogram` must include the word "Program" here ("Ecology Program"), because
the same value is printed on both the title page and the approval page.

No committee macro was needed: CU's ordering rules (chair first, then advisor,
then members; advisor last if not on the committee; no degrees or titles) map
straight onto `\committeemember{Name}{Role}` with an empty role for a plain
member. `\cupriordegrees` and `\cuapprovaldate` are the only additions, and the
latter defaults to the template's visible `<last day of the semester>` so an
unset required line is wrong on the page rather than silently missing.
