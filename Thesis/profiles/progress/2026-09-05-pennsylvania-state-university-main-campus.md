# 2026-09-05 — pennsylvania-state-university-main-campus

**profile** — HERD rank 25. PR #124. Round of ten, institution 3 of 10.

Geometry, spacing, title page and committee page all set from the Fox Graduate
School's Thesis and Dissertation Handbook (filename dated 2026-08-27, eight days
before this pass — the freshest source this round). `\thesissetchapteropening`
left unset; no accessibility check-flag raised.

Things a later pass should not have to rediscover:

- **The margin figure is ¾-inch, and `pdftotext` will tell you otherwise.** The
  handbook's vulgar fractions extract as U+FFFD, so p. 9 comes out as "A ?-inch
  or 1-inch margin", which reads naturally and wrongly as one-half. Rendered at
  150 dpi and read as an image: **three-quarters**. Re-check it the same way.
  ¾in and 1in are both acceptable on all sides; the profile sets 1in. The
  "1 ½-inch" left margin is explicitly a *binding* suggestion ("may be more
  appropriate"), not a rule, and is not encoded — Penn State files
  electronically.
- **The handbook's "Doctoral Title Page Example" is a master's title page.** It
  shows "A Thesis in … Master of Science", substantively identical to the
  "Master's Title Page Example" on the next leaf. There is no doctoral specimen
  in the handbook. The doctoral wording in the profile follows the *prose* rule
  ("Master's candidates should use 'Thesis,' and doctoral candidates should use
  'Dissertation'"), not the mislabelled example. Left quoted for the reviewer,
  not silently resolved.
- **Spacing is the student's choice** — "may be single-, double- or
  one-and-a-half-spaced". `double` is a default here, not Penn State's rule.
- **It is a "committee page", not an approval page, and it is numbered ii.**
  Unlike the title page it shows its number, so the profile keeps the normal
  geometry and page style instead of suppressing it. For the number to come out
  as a roman numeral the document must call `\thesisapprovalpage` after
  `\frontmatter` — the profile cannot enforce that.
- **No physical signatures.** Typed names and professorial titles only;
  approval is electronic through eTD. Do not draw signature rules here. Penn
  State also forbids "Ph.D." or "Dr." on that page.
- **Accessibility is the Texas A&M pattern, not the Michigan one.** Penn State's
  templates page says its templates "were created with accessibility in mind"
  and that applying the Styles "keeps your document accessible" — indicative
  mood, no modal verb, no named standard, no checker report. The 37-page
  handbook contains no document-accessibility requirement at all. Recorded
  verbatim under the label `{Templates, not a mandate}`; **no check-flag
  raised**. If the modal verb ever changes to "must", that becomes a real
  `\thesisrequiretagging`.
- The profile defines a local `\thesiscopyrightyear{}` (defaulting to empty, and
  omitting the line when unset) because Penn State puts the copyright notice on
  the title page rather than a page of its own, and the class has no year macro.
  The notice is optional twice over in the sources.
- `https://gradschool.psu.edu/current-students/thesis-and-dissertation-information/`
  is a **404**; the live path is `/academics/theses-and-dissertations`.
