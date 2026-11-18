# 2026-09-15 — alabama-a-and-m-university

**profile** — first institution of the alphabetical fallback (the ranked queue
ran out at Notre Dame this round). PR #230.

Complete but for the typeface: geometry (left 1.5in, others 1in), double
spacing, a 2in chapter opening, the title page from Appendix D and the
Certificate of Approval from Appendix E. Alabama A&M is the first institution in
a while that requires a **signed** approval page inside the document.

For a later pass, so it is not rediscovered:

- **The source is fourteen years old.** "Thesis and Dissertation Guidelines"
  says "2012 - 2013" on its title page and "June 2012" in its copyright line;
  the PDF was last modified August 2017. It is nonetheless the only formatting
  guide the School of Graduate Studies publishes, and the graduate-admissions
  pages link nothing newer. Some of its rules (25-pound 100% cotton paper, "holes
  or perforations are not permitted in any of the margins") plainly predate
  electronic submission. Every figure should be re-checked before a real filing.
- Its accessibility silence is **age**, not a position; recorded as such.
- `\thesisinstitution{Alabama A&M University}` from `scaffold` does not compile —
  the ampersand must be escaped, because the value is typeset. Worth remembering
  for every future institution with `&` in its name.
- The Appendix E specimen types **no names**: blank rules to be signed, with only
  the advisor's labelled. This profile labels every member's rule with its role,
  which is a deliberate deviation noted in the file.
- Long role labels wrapped back to the left margin under the wrong rule until
  the label was put in its own `\parbox` with a computed width. A profile that
  draws rules beside text needs that.
- Not encodable, recorded in the header: the pagination table (fly pages
  uncounted, title page counted but unnumbered, Certificate of Approval = "ii"),
  the page number "one inch above the bottom edge", and justified-or-left-
  justified as a consistent choice.
