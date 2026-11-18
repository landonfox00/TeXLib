# 2026-09-12 — university-of-south-florida

**profile** — HERD rank 69. PR #198.

Complete: geometry (1in), double spacing, a title page built from USF's
blank-line-by-blank-line specification, `\thesisnoapprovalpage`,
`\thesisrequiretagging` and seven quoted accessibility rules. Nothing left to
the neutral fallback.

Things a later pass must not rediscover:

- **USF actively discourages LaTeX**, in writing: "Due to the difficulty
  creating Accessible PDFs through LaTex, we are currently discouraging the use
  of LaTex ... For this reason, we encourage the use of Word instead." It also
  says "In LaTex there are packages that allow for the document structure to be
  read and converted into a tagged PDF when compiled", and names **veraPDF** as
  an acceptable checker — the same tool this repo's gate runs. Quoted in the
  profile header; not argued with.
- The title-page page is prescriptive down to the number of blank lines between
  blocks, and the gap after the degree block is **3 lines, or 2 when the
  optional concentration line is present**. The profile switches that
  automatically off `\usfconcentration`.
- **Two different dates** on one page: the Date of Approval is the defence date
  (`\graddate`), the copyright year is "the year matching the year of the final
  submission" (`\usfcopyrightyear`, which defaults to `\thesis@date` so an unset
  value shows as a full date rather than a plausible wrong year).
- Five profile-local setters exist because USF names more title-page fields than
  the class holds: `\usfdepartment`, `\usfcollege`, `\usfconcentration`,
  `\usfkeywords`, `\usfcopyrightyear`.
- The Major Professor comes from `\gradadvisor` and the rest from
  `\committeemember`; listing the advisor in both prints them twice.
- USF names WCAG 2.1 AA **only for colour contrast**, and gives **no ADA
  compliance date**. Nothing to reconcile against a neighbouring profile.
- The requirements are spread over ~25 small `.aspx` pages under
  `etd-formatting-requirements/{general,section-specific}/`; plain curl serves
  them fine. The ADA rules live on `section-specific/index.aspx`, not on a page
  of their own.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
