# 2026-09-05 — emory-university

**profile** — HERD rank 29. PR #129. Round of ten, institution 7 of 10.

Geometry, spacing, cover page and approval page all set. Only
`\thesissetchapteropening` is unset. No accessibility check-flag raised.

Things a later pass should not have to rediscover:

- **TWO EDITIONS ARE ON THE SERVER AND THEY DIFFER. Do not correct this file back
  to the older one.** The 2019 PDF is still served and still ranks first in
  search; it names **Lisa A. Tedesco** as Dean. The 2023-10-03 `.docx` is what
  Laney's own doctoral-completion page links, its filename literally says
  `new-dean`, and it names **Kimberly Jacob Arriola, Ph.D, MPH**. The margin,
  spacing, font and page-number rules are *identical* in both, checked clause by
  clause; the Dean's name is the substantive difference. The 2019 PDF was still
  used — but only to **render** the two specimen pages as images, since a `.docx`
  cannot be rendered here and the layouts are unchanged.
- **The Dean's name is the one line in this profile guaranteed to rot.** It has
  already changed once. Re-check before any real filing.
- **The signature rules are blank on purpose.** "Do NOT include real signatures
  in the electronic copy … that you upload into the ETD." Blank rules are
  correct for the ETD copy — not an oversight.
- **Signatures are collected separately and electronically**, via a DocuSign
  Power Form that goes to LGS with the completion packet. Emory also lets a
  student place the signed DocuSign pages in front of the manuscript, at their
  option. The Dean's rule stays blank too: "You Do Not need to get the Dean's
  signature on this form before you submit your graduation forms."
- **Emory says a margin violation is grounds for rejection** — "A
  dissertation/thesis cannot be accepted if any of the text falls outside the
  margins" — and reasserts it for the special pages. This is not decorative.
- **That made the approval page's vertical spacing load-bearing, and the first
  draft failed it.** With roomier gaps the Date rule fell off the bottom with a
  committee of only *three*. Spacing was retuned and re-verified so a committee
  of **five** fits inside the 1in bottom margin — the size Emory says the single
  column should "likely accommodate". Verified by building a five-member probe
  and confirming both "Dean of the" and "Date" land on the approval page and
  nothing spills to the next. **Anyone editing those gaps must re-run that
  check.**
- **Not reproduced, and flagged rather than guessed**: "with committees of 5 or 6
  members, you may use a two-column layout for the committee members." It is
  permissive, and five fits the single column, so single column is used. A filer
  with six must build the two-column variant by hand.
- **`\author` needs two lines at Emory** — the previous academic degree sits on
  its own line under the name ("B.A., Yale University, 2004"), so
  `\author{Ada N. Student\\B.A., Yale University, 2020}`. The class has one
  author field and Emory wants two lines.
- **The degree carries no subject matter**: "your degree is not 'Doctor of
  Philosophy, Sociology'". The field is separate and excludes the word "program"
  and any sub-field.
- **`\graddate` is the calendar YEAR alone** — "the calendar year you receive
  your degree (not the academic year)".
- **No accessibility rule is published.** Across both editions and the ETD page,
  "accessib" occurs exactly twice and neither is a document rule (the
  Distribution Agreement's licence grant, and a note about prior publication).
  No "alt text", "WCAG", "tagged" or "PDF/A" anywhere. Emory is private, so the
  April 2026 ADA Title II date does not reach it as it does the public
  universities in this set. Recorded as `{Not published}`.
