# 2026-09-13 — university-of-connecticut

**profile** — PR #210.

Complete. Geometry (1in minimum all four sides), double spacing, the title
page, the advisory committee page, `\thesisrequiretagging`,
`\thesisrequiredocumentlanguage` and six quoted accessibility requirements are
all set. Left neutral: chapter-opening margin (UConn states none) and typeface.

Things a later pass should not have to rediscover:

- **UConn's filing requirements live at the Office of the Registrar**, not at
  `grad.uconn.edu`, which carries no competing specifications page. The
  Registrar administers degree completion there and the submission portal
  enforces its numbered rules #1–#14. Department pages (Social Work, Neag,
  Psychology, Math) and the library guide all publish their own versions and
  are **not** sources.
- **The accessibility requirement is dated into the near future**: "EFFECTIVE
  for SPRING 2027 GRADUATES ... your dissertation must meet the Web Content
  Accessibility Guidelines (WCAG) 2.1." Spring 2027 is the next graduating
  class for anyone filing now, so it is recorded as a requirement. UConn is the
  first school in this set to name WCAG by version.
- **`\thesisrequiredocumentlanguage` is the one inference in the file**, made
  deliberately and flagged there. UConn's enumerated list does not name the
  document language; it requires WCAG 2.1 as a whole, of which Language of Page
  (SC 3.1.1) is Level A, and introduces the list with the non-exhaustive "This
  includes". Set because the asymmetry favours it — a false positive costs a
  build warning, a false negative costs a document that fails the named
  standard. One line to delete if a reviewer disagrees.
- **The title-page layout needed the docx *styles*, not its paragraphs.** The
  title paragraph carries no justification of its own and looks left-aligned;
  it is styled Heading 1, and Heading 1 in `styles.xml` sets `w:jc="center"`.
  That also confirms UConn wants the dissertation title itself tagged as H1,
  which is consistent with its headings rule.
- **The advisory committee page carries no signature rules** — the sample shows
  typed names on the same line as the role. UConn does collect real signatures,
  but on the approval *forms*: "Original, scanned, or electronic signatures are
  accepted", and they "may be on different pages or come from multiple faculty
  emails". The page records who approved; the forms carry the signing. It is
  also a numbered preliminary page, so it must not set `\thispagestyle{empty}`.
- **Vertical placement of the title block is not prescribed** by either source —
  the sample's spacing is empty Word paragraphs, not a stated measurement — so
  the profile centres it and says so rather than inventing a figure.
- Font note: UConn "recommends" Arial/Times/Helvetica twice, so nothing to
  require, but adds a **must** this class cannot meet literally — "The font
  selected must be an embedded, True Type (not scalable) font", where lualatex
  embeds OpenType as Type0/CID. Same shape as the Caltech note in this round.
  Recorded, not encoded.
- Do **not** reconcile UConn's ADA Title II framing against other profiles'
  compliance dates; the deadlines differ legitimately by entity size.
