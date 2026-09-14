# 2026-09-14 — george-washington-university

**profile** — round of ten, institution 5. PR #219.

Complete: geometry, spacing, title page, certification page, and nine
accessibility records including `\thesisrequiretagging` and
`\thesisrequiredocumentlanguage`. Only `\thesissetchapteropening` is left
neutral, correctly — GW's deeper top margin belongs to the title page alone.

Things a later pass should not have to rediscover:

- **GW's margins are not 1in square.** Portrait: left and right 1.25in, top and
  bottom 1in. The *wider* measure is the horizontal one, which is the opposite
  of the usual binding-driven asymmetry. Landscape pages take the same frame
  rotated (1in sides, 1.25in top and bottom), which one `\thesissetgeometry`
  cannot express; noted in the profile for the author to apply locally.
- **The approval page is conditional in BOTH directions.** "The Certification
  Page is required for dissertations; DO NOT include in a thesis." So
  `\thesisapprovalpage` prints the page for a dissertation and, for a thesis,
  warns and prints nothing — `\thesisnoapprovalpage`'s behaviour applied to half
  the documents. This is the first profile in the set that needed that shape;
  `\doctype` is load-bearing here in a way it is not elsewhere.
- **Two different dates.** The title page carries the *conferral* date, which GW
  fixes by term (August 31 summer, January fall, May Commencement spring); the
  certification paragraph carries the *defence* date. They are not the same
  date and the profile gives them separate fields.
- **Three profile-local setters were added**: `\gwuschool`, `\gwupriordegrees`,
  `\gwudefensedate`. The first and third warn when a document needs them and has
  not set them. `\gwuschool` is used twice — the title page's central paragraph
  and the certification paragraph — which is why it is one field, not two.
- **`\gradadvisor` carries two lines here.** GW prints the director's formal
  name and then their full professorial title on consecutive lines, with no
  separator and no administrative titles. The class has no second field, so the
  profile expects `\gradadvisor{Name\\Professorial Title}`.
- **No signatures.** The certification page certifies in prose that the Final
  Examination was passed; it prescribes no rule, date line or seal.
- **A `\par` after the hidden tagged heading is load-bearing** on the
  certification page. Without it the heading and the opening paragraph are one
  paragraph and GW's "left aligned" first line comes out indented. The first
  draft had that bug.
- **Three document-wide prohibitions the class cannot enforce**, each a
  rejection: no biography/CV/publication lists, **no blank pages anywhere**, no
  running headers anywhere, no rules or page borders. The blank-page rule argues
  against a twoside build, whose `\cleardoublepage` inserts them. Recorded in the
  profile header.
- **School of Law is out of scope** — "The School of Law follows different
  formatting guidelines." Do not extend this profile to cover it.
- **Left for the reviewer:** page-number placement (".75 inch from the bottom of
  the page", with the Word "Footer from Bottom" set to .5 inch) is not pinned;
  the class centres the folio in the foot. Also, GW states the alignment of the
  title on the certification page but not of the author's name below it — the
  profile centres it to match, which is a judgement call.

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`, two
lualatex passes, no errors and no class warnings (the test document sets all
three profile-local fields). veraPDF `--flavour ua2` reports compliant. Title
page and certification page rendered and checked block by block against GW's
counted blank-line specification.
