# 2026-09-14 — georgetown-university

**profile (partial)** — round of ten, institution 6. PR #220.

Set: geometry, spacing and the title page, **all from the Graduate School's own
Word template, not from its prose requirements**. `\thesisapprovalpage` is
deliberately left unset. This is the Stanford shape — an honest partial where
the gap is the point.

Things a later pass should not have to rediscover:

- **Georgetown's formatting requirements are behind a login, but its templates
  are not.** "Dissertation, Doctoral Project and Thesis Formatting Requirements"
  lives at `georgetown.box.com/s/pgffojhhneb119bqef0fkn88e7vgbn9j` and redirects
  to `georgetown.account.box.com/login`. Tried three ways on the access date —
  plain fetch, Box's `rm=box_download_shared_file` endpoint, and a browser — all
  three hit the login. **The templates on the same page are public**, and the PC
  template downloads cleanly from Box's shared-file endpoint once you scrape the
  numeric `file_id` out of the `/s/` page HTML. That is the whole reason this is
  a profile and not a block. Do not spend the next round rediscovering it: go
  straight to the template, or get the requirements from a Georgetown account.
- **The figures come out of the .docx, not out of prose.** Every section of
  `Thesis Dissertation Template-PC-OCT 2025.docx` carries
  `<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>` on
  letter paper — a 1in square frame, no binding offset — and its body paragraphs
  carry `<w:spacing w:line="480" w:lineRule="auto"/>`, which is double.
- **A 1.25in figure circulates for Georgetown and it is not this document's.**
  It comes from `english.georgetown.edu`'s *undergraduate* honors thesis page —
  a department page (not a source) about a different document. Named in the
  profile header only so the next pass does not treat it as a contradiction it
  must resolve. If the Box requirements do say 1.25in, the geometry line is
  wrong and must change.
- **The template's dropdowns are a controlled vocabulary and they are recorded
  in the profile.** School: College of Arts and Sciences / School of Foreign
  Service / School of Health / School of Medicine. Degree: Doctor of Philosophy
  / Master of Arts / Master of Science. Field: a long list in which every entry
  already carries its preposition ("in Applied Mathematics"), so the page prints
  "degree of / *Degree* / in *Field*". Two profile-local setters exist for what
  the class has no field for: `\georgetownschool` (warns if unset) and
  `\georgetownpriordegree`.
- **`\thesisapprovalpage` is unset, not forgotten.** The template has no approval
  page and approval is collected on a separate signed Cover Sheet emailed to
  Graduate Studies — the same shape that justifies `\thesisnoapprovalpage` at
  Michigan, Auburn and Tennessee. It is *not* used here because at those three
  the closed page list came from the school's requirements, and here it comes
  only from a template whose governing prose nobody has read. RESEARCHING.md
  wants a quote for that hook. Whoever reads the Box document should expect to
  turn this into `\thesisnoapprovalpage`.
- **Accessibility is "Not read", not "Not published".** The three readable
  Graduate Studies pages carry nothing beyond the sitewide footer link, but the
  document that would carry a requirement is the one behind the login. None of
  the three checkable declarations is set.
- **Two pages the class does not own are written out in the profile header**
  because an author reading only this file would miss them: the copyright page
  (which needs a year the class's `\makecopyrightpage` does not print) and the
  Georgetown abstract page (title in caps, name with prior-degree abbreviation,
  "Thesis Advisor:", then the heading; 350 words "strictly observed" for
  doctoral abstracts only).

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors and no class warnings. veraPDF `--flavour ua2`
reports compliant, 1727 rules passed, 0 failed. Title page rendered and compared
against the template's own page.
