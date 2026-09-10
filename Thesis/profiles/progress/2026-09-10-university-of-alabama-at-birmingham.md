# 2026-09-10 — university-of-alabama-at-birmingham

**profile** — HERD rank 31. PR #172.

Everything is set from the Graduate School's *Format Manual for Theses and
Dissertations* (Updated 03/01/2024): the asymmetric geometry (1.5in left for
binding, 1in on the other three sides), double spacing, a 2in section opening,
the title page from the annotated specimen in Appendix A, and
`\thesisnoapprovalpage`. Nothing is left to the neutral fallback. Accessibility
is recorded as **Not published** — the 31-page manual has zero hits for
"accessib", "alt text", "tagged", "WCAG", "PDF/A", "screen reader" or "508", and
neither the Resources index nor the Editing & Publishing page asks for anything
of the PDF beyond "a single PDF" to ProQuest.

Two things a later pass should not have to rediscover.

**The 2-inch opening is required for front matter and optional for chapters.**
Every preliminary page's title "is centered 2 inches from the top" (indicative),
but the body-chapter rule is twice stated as a *may* — "the first page of each
chapter may have a 2-inch top margin". `\thesissetchapteropening` cannot
distinguish the two, since it drives `\@makechapterhead` and
`\@makeschapterhead` alike, so the profile takes the 2in option for chapters and
says so. Do not "correct" it to 1in on the strength of the *may* alone; that
would also move the front matter, where 2in is required.

**A class defect showed up while checking the title page against the specimen,
and it is NOT this profile's to fix.** UAB puts the year "on the 1-inch bottom
margin"; the built page lands it 0.42in short. Cause: `\thesis@applygeometry`
saves `normal` with `includefoot` and then saves `nopagenumber` without it, but
`geometry` accumulates keys across calls, so `includefoot` leaks into the second
snapshot. Probed on the `unr` profile: both snapshots report
`\textheight = 620.43pt`, and `\footskip = 30pt` is exactly the shortfall. Every
profile's unnumbered front-matter pages are affected equally. The profile
deliberately does not compensate with a negative skip, which would go wrong the
day the class is fixed.

A stale 11/2010 edition of the manual is still served under
`uab.edu/medicine/mstp/`; the current Graduate School resource pages link only
the 03/01/2024 one, which is what this profile follows.
