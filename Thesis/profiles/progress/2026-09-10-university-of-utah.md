# 2026-09-10 — university-of-utah

**profile** — HERD rank 34. PR #175.

Complete: geometry (1.25in left/right, 1in top/bottom), a 2in main-heading
opening, double spacing, the title page from the Thesis Office's four sample
title pages, the mandatory Statement of Thesis/Dissertation Approval, and four
accessibility requirements. Nothing is left to the neutral fallback. The
templates index carries "Last Updated: 4/10/26", so the handbook is current.

Things a later pass should not have to rediscover.

**The 2in figure is the third line of Utah's margin rule, not an option** —
"main headings pages (title in ALL CAPS) top margin: 2 inches" — and the
handbook repeats it per page ("The word ABSTRACT is placed 2 inches from the top
of the page"). Continuation pages revert to 1in, which is what the class already
does.

**`\thesisrequiretagging` is deliberately unset.** Utah has a whole
accessibility chapter, and *alt text* is a hard requirement ("It is required
that you add alternate text for each figure, table, or any object that is not
text"), but the screen-reader sentence is a SHOULD and Utah never names a tagged
PDF, PDF/UA or PDF/A anywhere.

**The approval-statement layout came from the Word template, not the handbook.**
The handbook's Figures 2.4 and 2.5 are *not* reproduced on the web pages — the
HTML carries no images at all — so `word_template_version_13.docx` is the only
published full layout. Do not go hunting the web pages for it.

**The profile adds author-facing macros, which is unusual and was necessary.**
Utah's approval statement needs a per-member approval date, a departmental
approver and the Dean's name; the class models none. `\utahcommitteemember`
(name, role, date) replaces `\committeemember` for Utah filings;
`\utahdepartment`, `\utahdepartmentapproval` and `\utahgraduatedean` supply the
rest. A plain `\committeemember` still renders, with the date column blank —
visibly incomplete rather than silently wrong.

**`\utahgraduatedean` defaults to a real person's name** (the one in Word
template v13 on the access date). That will rot. It is a default, not a fact
about the filing, and the header says so.

Two things the profile cannot enforce and documents instead: `\graddate` must be
month-then-year with no comma and the month must be December, May or August; and
where the degree name differs from the department name Utah splits the degree
over three lines, which the author writes into `\graddegree`.
