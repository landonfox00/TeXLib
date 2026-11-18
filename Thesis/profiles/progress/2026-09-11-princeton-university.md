# 2026-09-11 — princeton-university

**profile** — HERD rank 45. PR #191.

Complete: geometry (1in all sides), double spacing, the title page from the
Archives' own specimen, `\thesisnoapprovalpage`, and three quoted accessibility
notes — all of them recording that accessibility is **optional** at Princeton.
Nothing left to the neutral fallback.

Things a later pass must not rediscover:

- **Format is the University Archives' to set, not the Graduate School's.**
  "The Princeton University Archives (Mudd Library) oversees the format and
  physical form"; the Graduate School sets "general requirements" and the
  Archives "does not oversee the contents, order of elements (aside from the
  first three pages), citation style". The submission guide says outright that
  where another source conflicts, "the Princeton University Archives
  requirements should be followed". That is why a LibGuide-hosted PDF is the
  citation here.
- **Accessibility is explicitly NOT required** — "Should you wish to make your
  dissertation or Master's thesis meet accessibility standards…" and "While it
  is not required at this time, adding alt text for any illustrations makes
  your content accessible." So no `\thesisrequire…` is set, deliberately. This
  is the Duke-style case RESEARCHING.md warns not to paraphrase toward other
  schools' requirements.
- **Princeton's own warning against precedent**, worth heeding before anyone
  "improves" this file: "Do not rely on the form or format of bound
  dissertations or theses that may be found in the Princeton University Library
  or your department, or on LaTeX templates shared by fellow students or staff.
  … older practices should not be used as precedents."
- **A second, wider margin rule exists for bound copies** — the "Dual
  Submission" subset only (students who redacted the PDF for copyright). The
  profile encodes the PDF rule, which is what every candidate files.
- **The date takes no comma** and is the Board of Trustees conferral month/year:
  "No other date should appear on the title page." Class default `May, 20XX` is
  out of spec.
- **`\thesisnoapprovalpage` here is an inference, not a quote**, and is flagged
  as such in the file: the first three pages are prescribed and closed, the
  8-page spec never mentions a signature page, and approval is collected on
  signed reader reports and the PhD Dissertation Report Form outside the
  manuscript.
- Build note: the title page originally overflowed and pushed the date onto a
  second page. The vertical budget is tight — Princeton's specimen has eleven
  centred blocks. If this page is edited, re-render page 1 and check the date
  is on it.
