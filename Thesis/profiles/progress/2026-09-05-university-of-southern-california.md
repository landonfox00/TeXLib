# 2026-09-05 — university-of-southern-california

**profile** — HERD rank 27. PR #127. Round of ten, institution 5 of 10.

Geometry, spacing and the title page set from the Graduate School's own
guidelines PDF and its Appendix A specimens. The approval page is left as the
class's **neutral fallback on purpose** — the one real judgement in this file.
No accessibility check-flag raised.

Things a later pass should not have to rediscover:

- **Do not read "USC requires no formatting guidelines" as covering margins.**
  USC leaves the *style manual* to the discipline ("MLA, APA, or Chicago") while
  prescribing the general formatting itself: "All margins must be 1"" and
  "Double space text throughout manuscript". Third-party summaries collapse the
  two and get this backwards.
- **The title is NOT bold.** "Do not bold text or add any extraneous
  information." This departs from the class default and from most sibling
  profiles. Don't "fix" it.
- **`\thesisnoapprovalpage` would be wrong here, and so would writing a page.**
  USC's rule is neither: "A signature page is not required by the University …
  Students who are required by their school, department or program to include a
  signature page should … include the signature page in the uploaded PDF
  version". Writing a layout would invent one USC doesn't publish; declaring
  none would silently drop the page for exactly the student the sentence
  addresses. The neutral page renders, and the file says why at length.
- **Where a department does require the page, it goes INSIDE the uploaded PDF** —
  the opposite of Vanderbilt (#123), where the signed page is a separate
  administrative file. Do not cross-correct them.
- **Appendix A holds six specimens and they differ.** The PhD one names "FACULTY
  OF THE USC GRADUATE SCHOOL" and "DOCTOR OF PHILOSOPHY"; other doctorates name
  "FACULTY OF THE USC [SCHOOL NAME]" and "DOCTOR OF [MAJOR …]"; master's read "A
  Thesis Presented to the … MASTER OF ARTS". The profile follows the
  PhD/Graduate School one. A filer in a named school must replace the FACULTY
  line; the profile cannot know which school.
- **The governing PDF is about six years old** — no revision date in its text,
  embedded CreationDate 2020-03-11, served from a `/2020/11/` path. The live page
  links it as current and no newer edition exists on the server, so it is
  followed, but it is worth re-checking before a real filing.
- **One figure the class does not reproduce exactly**: USC puts page numbers
  0.5in from the paper's bottom edge, outside the 1in text block; the class's
  `includefoot` geometry keeps them inside it. That is conservative, not out of
  spec ("all other manuscript material must fit within the margin
  requirements"), and is recorded in the profile in case a reviewer wants it
  chased.
- **No accessibility rule is published** — zero hits for accessib/alt text/WCAG/
  tagged/PDF/A/screen-read across the 13-page PDF and all three submission
  pages. USC is private, so the April 2026 ADA Title II date does not reach it
  the way it reaches the public universities in this set. Recorded as
  `{Not published}`.
- The profile defines a local `\thesiscopyrightyear{}` (as Penn State's does)
  because USC's title page carries a copyright line and the class has no year
  macro. Unlike Penn State's, this one **warns at build time when it is unset**,
  since USC says to "format exactly as shown" and every specimen carries the
  line. Verified both ways: warning fires when unset, two-column foot renders
  when set.
