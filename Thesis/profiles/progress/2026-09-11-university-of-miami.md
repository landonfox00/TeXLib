# 2026-09-11 — university-of-miami

**profile** — HERD rank 44. PR #190.

Set from the Graduate School's own 9/9/26 formatting guidelines and its 8-13-26
Ph.D. front-matter template: geometry (1.5in left, 1in elsewhere), double
spacing, the title page, and the **signature page** — which Miami requires *in*
the filed PDF, with the rules drawn and blank. Left neutral: the font (see
below) and `\thesissetchapteropening` (Miami states one top margin).

Things a later pass must not rediscover:

- **Two generations of front-matter templates are linked from the same page.**
  The current set is `../../_assets/pdf/<degree>-template-8-13-26.docx`; an
  older 4-1-24 / 7-5-23 / 1-29-25 set still sits at `/_assets/pdf/`. Follow the
  8-13-26 files.
- **The signature page keeps blank rules** — "must be included in the final PDF
  of your ETD, but without the actual ink signature ... For legal reasons, ink
  signatures are not displayed on this page." That is the opposite of UCI and
  CWRU in this same round; do not generalize between them.
- **The second argument of `\committeemember` is an ACADEMIC TITLE here, not a
  committee role.** Miami: "Signature lines should include only the signees'
  name, degree earned, and title. Do NOT add 'Chairperson,' 'Committee Member,'
  or 'Outside Member' ... Do not add 'Dr.' or 'Professor' in front of a
  signee's name."
- **The Dean's line is mandatory** and its name will rot (`Soyeon Ahn, Ph.D.,
  Interim Dean of the Graduate School` on the 8-13-26 template); exposed as
  `\thesisgraduatedean`. The template puts the Dean's cell in the second row,
  right column; the profile appends it as the final cell, which only matches
  when there are exactly four other members. Flagged in the file.
- **The date takes no comma** and is the degree-award date, not the defence
  date: "Fall: December 2026 / Spring: May 2027 / Summer: July 2027". The class
  default `May, 20XX` is out of spec on both counts.
- **Typeface is an open question.** "Acceptable fonts include Arial, Times New
  Roman, and Courier New" — the class's Latin Modern is not on that list, but
  "include" is not "limited to". No face is set; a filer may want
  `\setmainfont{TeX Gyre Termes}`.
- **Accessibility is not published**: zero hits across the 9/9/26 guidelines,
  the 10/21/25 ETD Process document, the 9/9/26 preparation checklist and both
  ETD web pages.
