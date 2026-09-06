# 2026-09-06 — abilene-christian-university

**profile** — alphabetical fallback (the ranked queue ran out at MIT, rank 33).
Round of ten, institution 2 of 10.

Geometry, the 2in chapter opening, spacing and the absence of a student-typeset
approval page are set. **The title page is the neutral fallback** — ACU
prescribes it by template and the template is behind a Google sign-in. No
accessibility check-flag raised; ACU publishes no accessibility rule.

Things a later pass should not have to rediscover:

- **The title-page template is NOT publicly reachable.** The resources page links
  the "ACU Thesis Template" and "Thesis Signature Page Template" as Google Drive
  folders with `usp=sharing` links; both redirect to `accounts.google.com`
  instead of serving a listing. This was tried in the browser pane, not just by
  curl. **This is the one thing that would finish this profile** — get the
  template from the Thesis Coordinator and write `\thesistitlepage` from it.
- What ACU *does* say in prose about the title page is already in the profile:
  title 2in from the top, **sentence case with main words capitalized**, date
  1.5in from the bottom. Note the class's neutral page sets the title bold and
  ACU's case rule is unusual — check both against the template.
- **ACU's left margin is 1.5in — asymmetric**, and it applies to the filed
  electronic copy because that copy "will be printed and bound". Don't normalise
  it to 1in to match its neighbours in this directory.
- **Two sources, no conflict.** The Thesis Guide (Updated August 2024) states
  the four margins but gives the chapter-opening exception *without a number*;
  the Formatting Checklist supplies the 2in. They agree everywhere else, checked
  clause by clause. The checklist is what the final mechanical review runs
  against, so it is not a secondary source here.
- **`\thesissetchapteropening{2in}` covers less than ACU asks.** The same 2in
  applies to every front-matter heading too — ABSTRACT, TABLE OF CONTENTS,
  ACKNOWLEDGMENTS, the dedication, APPENDIX, List of Tables/Figures. The hook
  reaches chapter and major-section openings only.
- **THE APPROVAL PAGE IS A THIRD CASE and the warning text does not quite fit.**
  `\thesisnoapprovalpage` is set, correctly — but ACU is not Washington or Johns
  Hopkins, where approval lives on a separate *form*. At ACU the signature page
  is a separate page that **ACU itself inserts**: "The Thesis Coordinator will
  obtain the Associate Provost's signature and insert the signature page into
  the finished thesis." The guide's own front-matter order contains no signature
  page, so a student who typesets one gets it wrong twice — wrong order, and the
  finished thesis ends up with two. Printing nothing is right; the stock warning
  message just describes a different mechanism.
- **Signatures are still collected and may be "physical or electronic."** ACU has
  not gone electronic-only.
- **ACU forbids full justification** — "The use of double (left & right)
  justification is unacceptable" — and this class justifies by default. It is
  recorded in the profile in prose and deliberately NOT implemented, because
  RESEARCHING.md fixes what a profile may contain and justification is not on
  that list. An ACU filer needs `\raggedright` in their own preamble. Same for
  the 12pt serif font rule, the 1/2in paragraph indent, and the page-numbering
  scheme (counting starts at the TOC; the page after a two-page TOC is "iii").
- **Front matter puts the ABSTRACT BEFORE the title page**, which is the reverse
  of most schools in this directory.
- **No accessibility rule is published.** Zero occurrences of "accessib" in the
  17-page guide; none in the checklist, the resources page or the DC@ACU ETD
  submission instructions. The single hit anywhere is bepress's site-wide
  "Accessibility Statement" footer link on the repository — a website statement,
  not a thesis rule. ACU is private, so the April 2026 ADA Title II date does not
  reach it. Recorded as `{Not published}`.
- Built clean (0 errors); veraPDF `--flavour ua2`: 3169 passed, 0 failed. Margins
  confirmed by rendering a body page and measuring: text starts 1.5in from the
  left, chapter opening at 2in.
