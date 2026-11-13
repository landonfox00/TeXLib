# 2026-09-14 — brown-university

**profile (partial)** — round of ten, institution 8. PR #222.

Set: geometry, spacing, chapter openings and the signature page.
`\thesistitlepage` is left unset because **Brown does not publish a title-page
layout** — that is the whole gap, and it is a gap in the source, not in the
research.

Things a later pass should not have to rediscover:

- **Brown's prose states no margin at all.** The figures come from the artwork
  of the three official sample pages, which each carry the same four
  annotations: "1-inch top margin", "1-inch bottom margin", "**1.5-inch left
  margin**", "1-inch right margin". What makes them the *document's* margins
  rather than three pages' margins is the abstract sample's own note — "USES
  SAME PAPER AND FORMATTING AS THE DISSERTATION". Read the samples as images;
  `pdftotext -layout` does render the annotations, but the signature page's
  layout only makes sense rendered.
- **Brown publishes no title-page sample.** It has samples for the abstract, the
  copyright notice and the signature page, and none for the title page. The
  guidelines mention the title page four times — page i, number suppressed,
  dated with the conferral date, "may be sent by email" — and never say what is
  on it. So the hook stays unset and the neutral page renders. What *is*
  published about it (Chicago title case, explicitly changed from the older
  all-caps practice; the conferral date) is quoted in the profile header,
  because it constrains `\title` and `\graddate` whatever layout is used.
- **The filed signature page is deliberately UNSIGNED**: "An unsigned copy of
  the signature page should be uploaded to ETD system", while the signed one
  goes to the Academic Affairs Manager by email. So drawing empty rules is
  correct here, not a fallback. Electronic signatures are acceptable on the
  emailed copy.
- **The signature page carries four parties**, not three: advisor, then
  "Recommended to the Graduate Council" over the readers, then "Approved by the
  Graduate Council" over the **Dean of the Graduate School**. `\browndean` was
  added for the last one and warns if unset, because Brown requires that "The
  typed names of the director and readers must appear under their signature
  lines".
- **`\thesissetchapteropening{2in}` comes from a rule about headers**: "Do not
  place headers on each page. Use them only as appropriate to indicate major
  sections of the thesis (e.g., INTRODUCTION, CHAPTER 1, BIBLIOGRAPHY). They
  should be centered and placed two inches from the top of the paper in
  uppercase type." The 2in is a total from the paper edge, which is exactly what
  the key takes. Two parts of that sentence are **not** implemented and are
  noted in the profile: the uppercase-and-centred styling of the heading itself,
  which a profile cannot reach through its hooks, and the prohibition on running
  heads, which this class does not emit anyway but a page style could reintroduce.
- **Both minipages in the signature block are top-aligned.** With a `[b]`-aligned
  right box the "Date______" rule lines up with the typed name instead of the
  signature rule, which reads as a second signature line. The first draft did
  that; the render caught it.
- **`\gradprogram` carries the unit's noun for this profile** — the sample reads
  "by the Department of Chemistry", so set `\gradprogram{Department of
  Chemistry}`, unlike Georgetown and Wichita where it is bare.
- **Scope is the doctoral dissertation.** Brown publishes separate Master's
  Thesis Guidelines with near-identical type and spacing wording; its sample
  pages were not read and its approval page is not assumed to be this one.
- **Accessibility: none published.** Searched both guidelines pages and all
  three samples; the only occurrences of the word are the sitewide footer link.
  The nearest adjacent statement is about the repository, not the author —
  Brown's ETD system "collects and archives final dissertations as text-based
  PDF files" — and is recorded as such rather than turned into
  `\thesisrequiretagging`.
- **Left for the reviewer:** Brown pins the folio at "three-fourths of an inch
  from the bottom edge"; the class centres it in the foot without pinning it.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors, zero missing characters, no class warnings (the test
sets `\browndean`). veraPDF `--flavour ua2` reports compliant, 1727 rules
passed, 0 failed. Signature page rendered and compared against Brown's sample.
