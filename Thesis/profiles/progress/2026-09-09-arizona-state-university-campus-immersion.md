# 2026-09-09 — arizona-state-university-campus-immersion

**profile** — HERD rank 37. PR #165.

Set: geometry (1.25in left/right, 1in top/bottom), spacing (double), the title
page reproduced from the Format Manual's annotated specimen, and
`\thesisnoapprovalpage`. Left to the neutral fallback: chapter openings and
every checkable accessibility declaration.

Things a later pass should not have to rediscover:

- **The class does not satisfy ASU's typeface rule, and no profile field can fix
  it.** ASU requires one of eight named TrueType faces at a named size (Arial
  10, Century 11, Garamond 12, Georgia 11, Sans Serif 10, Tahoma 10, Times New
  Roman 12, Verdana 10). `texlib-thesis` sets Latin Modern. The profile header
  says so at length and gives the filer a `\setmainfont` recipe. This is the
  first institution here where the class is out of spec by default — if the
  library ever grows a typeface field, ASU is the reason.
- **First non-square margins in the directory**: 1.25in left and right, 1in top
  and bottom. Confirmed twice — in prose and on the specimen's own dimension
  annotations.
- **The title page needs TWO dates.** The upper one is the oral-defence month
  and year ("Approved [Month] [Year] by the"); the lower is the conferral month,
  which must be May, August or December. The profile adds `\asuapproved{...}`
  for the first and uses `\thesis@date` for the second.
- **"5 single line spaces" and "ten single line spaces" mean SINGLE.** Taking
  them at the page's ambient double-spaced `\baselineskip` overruns the page and
  silently pushes the last committee member and the university line off it —
  which is exactly what the first build did. Caught by rendering the page, not
  by the log: the build exits clean.
- **Accessibility is published as best practice, not as a filing rule.** ASU's
  guidance (dated 2026-08-27) is titled "Best practice for students and faculty
  advisors" and its feature list is declarative rather than mandatory; the
  February 2022 Format Manual, which is what a format review actually runs
  against, does not contain the string "accessib" at all. So the checkable
  declarations are unset and eight quoted entries are recorded instead — same
  reading as Texas A&M. The one sentence pulling the other way, that "The ASU IT
  Accessibility Standard covers electronic theses and dissertations (ETDs)", is
  quoted as its own entry so a reviewer can weigh it.
- **Pagination is unusual and unexpressible**: the title page is unpaginated,
  roman numbering starts at **i on the abstract**, and an optional copyright page
  "does not change pagination".
