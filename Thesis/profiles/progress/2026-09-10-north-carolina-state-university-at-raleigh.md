# 2026-09-10 — north-carolina-state-university-at-raleigh

**profile** — HERD rank 39. PR #180. Complete; nothing left to the neutral
fallback.

**This is the first profile in the directory to set both
`\thesisrequiretagging` and `\thesisrequiredocumentlanguage`, and NC State's own
words reach them.** "ADA Title II mandates that all digital content provided by
state institutions, including Electronic Theses and Dissertations (ETDs), must
meet WCAG 2.1 Level AA accessibility standards." The checklist then names the
mechanism, not just the goal: the "No Print-to-PDF" rule requires "'Document
structure tags for accessibility' is selected", and the PDF properties must show
"The text language of the PDF is specified". No PDF standard is named, so
`\thesisrequirepdfstandard` stays unset. NC State also addresses LaTeX authors
directly ("Use accessibility packages to create document structure, tags, and
alt text"). Six requirements recorded verbatim.

**Two published choices, both recorded rather than presented as rules.** The
left margin "can either be 1 inch or 1.25 inches" (profile takes 1in; take
1.25in if the copy will be bound), and body text "must be 1.5- or double-spaced"
(profile takes double). Do not later "correct" either to a single value.

**There is no approval page and no signature anywhere in the document.** The
committee lives on the *title page* under "APPROVED BY:", as blank rules. Twice
stated: the title page "Should not be signed by your committee", and "Do not
include actual signatures from your committee. Approval is now entered
electronically, via MyPack portal."

**The title is title case, not capitals** — "Capitalize the first letter of all
important words in your title" — and long titles take an inverted-pyramid shape
the author must break by hand with `\\`. The profile does not uppercase.

Layout notes for whoever maintains this. The signature block is a genuine
two-column grid (`\ncsu@memberline` alternates on a counter). An odd member
count is closed with an *empty box of the right column's width*, not a bare
`\par`: the title page is centred, so a lone box on its own line would centre
itself, and the annotated sample says "Left-sided lines should be left-aligned".
The `\strut` in `\ncsu@sigbox` is the same 0pt-wide-empty-`\parbox` trap
recorded in the Boston University log.

NC State also excludes two roles from the page outright — "Do not include
signature lines or names of Graduate School Representatives or Technical
Consultants" — which the class cannot enforce; don't pass them to
`\committeemember`.
