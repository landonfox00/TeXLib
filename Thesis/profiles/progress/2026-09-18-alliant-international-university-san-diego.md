# 2026-09-18 — alliant-international-university-san-diego

**profile** — alphabetical fallback. PR #251. Round of ten, institution 6 of 10.

Set from Alliant's systemwide *Dissertation/Doctoral Project Style and Format
Manual* (approved April 2014, revised September 2020): 1in on all four sides,
double spacing, the title page from the manual's annotated specimen (bold
capitals title, school and campus lines, typed "Approved by:" block, no
signatures), and `\thesisnoapprovalpage`, because the manual's prescribed
component sequence has no approval page and approval is signed on a separate
Library Clearance Form. Accessibility recorded as "Not published". The school
and campus lines are two new profile-local fields, `\thesisschool` and
`\thesiscampus`, with visible placeholders.

Things a later pass should not have to rediscover:

- **The manual is served from the library's LibGuides site**
  (`alliant.libguides.com/ld.php?content_id=75637663`) because the Library is
  Alliant's clearing office. The profile header argues why that counts; a
  reviewer who disagrees should block instead. The guide's Word template is
  explicitly "not official or required" and was not used.
- **Two sources disagree on who signs the clearance form.** The 2020 manual
  says the committee and the Program Director; the live clearance page (May
  2026) says "Section 1" is signed by "the dissertation/doctoral project chair
  and the Program Director". Neither puts signatures in the manuscript, so the
  profile is unaffected.
- `\normalbaselineskip` is already stretched under setspace. Counting the
  specimen's "four lines" in it gave gaps ~40pt too deep; the profile counts in
  `\f@baselineskip`. Worth knowing for any other profile that measures a gap
  in "lines" on a double-spaced page.
- Not encoded, and the likeliest review failure for a filer: "Do not justify
  right margins", the APA running head on every page, page numbers top right,
  and a closed font list (Computer Modern is allowed at 10pt only).
