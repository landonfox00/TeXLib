# 2026-09-14 — oregon-state-university

**profile** — round of ten, institution 9. PR #223.

Set: geometry, spacing, title page, approval page, `\thesisrequiretagging` and
five quoted accessibility records. `\thesissetchapteropening` left neutral —
"Each level 1 heading begins a new page" and no deeper top margin is stated.

Things a later pass should not have to rediscover:

- **OSU puts the page number at the TOP RIGHT and leaves the pretext pages
  unnumbered, and this profile cannot do it.** "Page numbers must appear at the
  top right corner of pages, approximately 1 inch from the top edge … No headers
  or footers may be used." The class puts the folio in the foot and builds its
  `normal` geometry with `includefoot`; a profile owns page layouts, not the
  document's page style, and there is no hook to move the number to a head. A
  document built against this profile is **out of spec on pagination** until the
  class grows a hook or the author sets a page style. Stated at the top of the
  profile. This is the one substantive gap.
- **The 1.5in left margin is for a PRINTED copy only** — "The left margin must
  be 1 inch unless printing and binding a personal or departmental copy then
  change to 1.5 inch" — so the filed electronic copy takes 1in, the opposite of
  Brown. Do not carry Brown's figure over.
- **The top margin takes OSU's stated preference of 1.2in**: "All other margins
  must be at least 1 inch, preferably 1.2 for top margin." Both 1in and 1.2in
  satisfy the rule, so nothing rests on the choice.
- **Three dates and two names that the class keeps as one or none.** The
  *defence* date appears on the title page after "Presented" and again in the
  approval page's first sentence; the *commencement* date is the title page's
  last line and is "the June following the defense date … Only month & year, no
  date or it will be rejected"; and the *department* is not the major — "Some
  majors and departments have the same name while others differ."
  `\oregonstatedefense` and `\oregonstatedepartment` were added, both warning if
  unset; `\graddate` carries the commencement date and `\gradprogram` the major.
- **The approval page has NO committee on it.** OSU names four signatories —
  major professor, department head, Dean of Graduate Education, and the author,
  who signs to authorise release — and the rest of the committee appears
  nowhere. `\committeemember` is deliberately unused by this profile; adding
  those lines would be inventing them.
- **Filed without signatures**, like Brown: "the signatures on this page have
  been replaced with the ETD Submission Approval form", and "Submit one copy of
  your thesis/dissertation, **without signatures**, electronically to
  ScholarsArchive." So drawing empty rules is correct.
- **Four alternate wordings exist for the signature lines** — co-major
  professors, dual majors, and MAIS — all listed in the profile header. An
  author in one of those cases must override the page.
- **`\thesisrequiretagging` is set on an inference OSU never spells out.** It
  requires the filed document to be accessible, flatly ("Your thesis or
  dissertation must meet OSU's Electronic Documents Accessibility
  requirements"), recommends Word, and allows PDF for complex documents with
  "Work closely with your major professor to ensure the digital accessibility of
  your PDF". A LaTeX thesis is on the PDF path and an untagged PDF cannot be an
  accessible one. OSU never uses the word "tagged"; the reasoning is written out
  in the profile so a reviewer can drop the line.
- OSU is one of the few schools to name **LaTeX** in its accessibility text:
  "Utilize Microsoft Word or LaTex Heading styles for effective and accessible
  heading structures."
- `\noindent` is load-bearing on each signature caption; without it the caption
  picks up `\parindent` and sits a quad right of the rule it belongs to.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors, zero missing characters, no class warnings (the test
sets both profile-local fields). veraPDF `--flavour ua2` reports compliant, 0
failed rules. Title page and approval page rendered and compared against Figures
6 and 7 of the Thesis Guide.
