# 2026-09-12 — university-of-illinois-chicago

**profile** — HERD rank 66. PR #195.

Title page reproduced from the Graduate College's own Sample D `.docx`, plus
`\thesisnoapprovalpage`, `\thesisrequiretagging`,
`\thesisrequiredocumentlanguage` and seven quoted accessibility rules. Geometry
(1in) and double spacing are set from the two official templates only.

Things a later pass must not rediscover:

- **UIC publishes no prose margin, spacing or body-font rule, and that is a
  finding rather than a failed search.** The Manual says the Graduate College
  "has delegated ... most aspects of format" to the student's program, and its
  review is a closed list that covers the title page, the preliminary pages,
  "consistency of formatting in the body" and accessibility — never a margin.
  The 1in/double figures come from the LaTeX template's `\geometry{margin=1in}`
  and `\doublespacing` and from the Word sample's page setup. Do not "upgrade"
  them to a quoted requirement; there isn't one.
- The **sample title pages are on Box** and are reachable: take the `file_id`
  out of the share page's JSON and fetch
  `uofi.app.box.com/index.php?rm=box_download_shared_file&shared_name=…&file_id=…`
  with a browser User-Agent. `DoctoralTitlePageSampleD.docx` is the specimen the
  profile is measured from (2in top margin, TNR 12pt, bold double-spaced title,
  committee indented 1in).
- `\thesisrequiredocumentlanguage` is an **inference**, flagged in the file: UIC
  never says "set the language", but requires passing "31 of 32 possible options"
  of Acrobat's checker with only the table summary exempt, and Primary Language
  is one of the 32. A reviewer who dislikes that chain can drop the line.
- UIC cites ADA Title II with **no compliance date**. Nothing to reconcile
  against the dated figures in neighbouring profiles.
- The profile defines `\uicpriordegrees{}` because UIC requires previously
  earned degrees under the author's name and the class has no field for it, and
  it needs `\graddate{2027}` — a year, not "May, 2027".

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
