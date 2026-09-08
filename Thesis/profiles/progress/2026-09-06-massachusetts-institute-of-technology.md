# 2026-09-06 — massachusetts-institute-of-technology

**profile** — HERD rank 33, the LAST entry in `priority.csv`. Round of ten,
institution 1 of 10.

Spacing, PDF standard, eight accessibility rules, the title page and the absence
of an approval page are all set. **Geometry is deliberately unset** — see below.

Things a later pass should not have to rediscover:

- **THE RANKED QUEUE IS EXHAUSTED AT MIT.** `priority.csv` ends at rank 33 and
  MIT is it. Every slug `next` served after this one in this round came from the
  alphabetical fallback (`abilene-christian-university` onward). Extending the
  ranked list means transcribing more of HERD Table 4 by hand, which is a
  person's decision, not a round's.
- **MIT PUBLISHES NO MARGIN, AND THIS WAS CHECKED RATHER THAN MISSED.** The
  "Formatting specifications" section lists exactly five items — Pagination,
  Title selection, Embedded links, Font, Spacing — and no margin. The word
  "margin" occurs ONCE in the whole document, in the footnote rule ("included
  within the specified margins"), pointing at a specification that is not there.
  The superseded 2022-2023 PDF has the same single dangling occurrence. So
  `\thesissetgeometry` stays unset and the neutral 1in page renders. **Do not
  "finish" this profile by filling in a margin** unless MIT publishes one; a
  departmental figure is not MIT's, since departments "may dictate more
  stringent requirements".
- **The source is a libraries.mit.edu page, and that is legitimate here.**
  RESEARCHING.md rules out library guides; this is not one. MIT's Office of
  Graduate Education says thesis preparation "is described in the Specifications
  for Thesis Preparation, published annually by the Director of Libraries as
  prescribed by the Committee on Graduate Programs", and links to it as the
  rule. The OGE page was read on the access date specifically to establish that.
- **A SUPERSEDED EDITION IS LINKED FROM THE LIVE PAGE.** The "View this page as
  an accessible PDF" link at the top resolves to the **2022-2023** edition, while
  the HTML page itself carries updates through **April 2026**. The HTML is
  followed. The old PDF was downloaded and compared anyway; it does not conflict
  with anything encoded here.
- **PDF/A-1 is required, tagging is not, and the difference is the point.** "You
  are required to submit a PDF/A-1 formatted thesis document to your department"
  → `\thesisrequirepdfstandard{PDF/A-1}`. But MIT never says "tagged" and accepts
  "PDF/A-1 (either a or b)", and 1b carries no tagging obligation, so
  `\thesisrequiretagging` is **not** set. Everything else on accessibility is
  phrased "You should create accessible files", so it is recorded verbatim
  through `\thesisaccessibilityrequirement` rather than raised as a check-flag.
  The one exception in MIT's own words is captioning for supplemental audio and
  video, which it calls "legally required".
- **`\thesisnoapprovalpage` is set, and the neighbouring profile that looks like
  this one is different.** MIT: "Signature page — Not Required", the department
  receives "A PDF/A-1 of your final thesis document (**with no signatures**)" as
  one file and a signature page as a *separate* file with its own name
  (`...-sig.pdf`). USC (#127) reads almost the same on the surface but then says
  a student whose department requires the page "should ... include the signature
  page in the uploaded PDF version" — inside the manuscript — which is why USC
  keeps the neutral page. **Do not cross-correct these two.** Approval at MIT
  rides on the title page's "Certified by:" and "Accepted by:" lines instead.
- **THE TITLE PAGE MUST BE ONE PAGE AND THE FIRST TWO DRAFTS WERE NOT.** MIT:
  "Title page — Required (all information should be on a single page)." The first
  draft pushed "Accepted by:" onto page 2 with ordinary 2\baselineskip gaps. Every
  gap now goes through `\thesis@mit@gap`, which shrinks to a third, plus a
  `\stretch` pair around the left-aligned block. Verified on a stress case — a
  two-line title AND a two-line degree name AND two prior degrees AND a
  three-line `\thesisacceptedby` — which still lands on one page. **Anyone
  widening those gaps must re-run that check.**
- **A fraction of a macro argument cannot be written inline.** `0.67#1\baselineskip`
  with `#1` = `1.5` pastes into `0.671.5\baselineskip` and threw 18 dimension
  errors. `\thesis@mit@gap` computes through `\@tempdima`/`\@tempdimb` instead.
- **The title is NOT bold**, per MIT's own specimen. As at USC, don't "fix" it.
- **Four local macros were added** because MIT's title page has fields the class
  has none for: `\thesiscopyrightyear` and `\thesisacceptedby` warn at build time
  when unset (every specimen carries them), `\thesissubmissiondate` warns too,
  and `\thesispriordegrees` / `\thesiscopyrightlicense` are silently optional.
  MIT will not say who signs "Accepted by:" — "The name and title of this person
  varies in different degree programs and may vary each term" — so the macro is
  free-form on purpose.
- **The advisor needs two lines**, as at Emory: `\gradadvisor{Beatrice J.
  Jansen\\Professor of Biological Engineering}`, and the profile appends
  ", Thesis Supervisor".
- **PAGINATION IS UNUSUAL AND IS NOT IMPLEMENTED.** MIT wants one consecutive
  arabic sequence over the entire thesis, title page = page 1, with no roman
  front matter. That is a class-level change, not a profile-level one, so it is
  recorded in the profile header and left undone.
- **No physical signatures** in the filed manuscript. Where a department wants a
  signature page it is a separate file.
- Built clean (0 errors, both the normal and the stress case); veraPDF `--flavour
  ua2`: **9135 passed, 0 failed**.
