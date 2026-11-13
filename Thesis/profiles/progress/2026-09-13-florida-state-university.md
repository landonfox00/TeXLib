# 2026-09-13 — florida-state-university

**profile** — PR #207.

Complete, and the first in this round with a real **committee page** rather than
no approval page at all. Geometry (exactly 1in all four sides), double spacing,
the title page and the committee page are all set from the Graduate School's
2024 Guidelines and Requirements plus its annotated Ph.D. Title-and-Committee
specimen. Left neutral: chapter-opening margin (FSU wants main section headings
AT 1in, not below a deeper opening) and the typeface.

Things a later pass should not have to rediscover:

- **"Exactly 1 inch" is stronger than the usual floor.** At FSU a wider margin
  is as wrong as a narrower one — no binding allowance.
- **Spacing is a genuine choice**: "must be all double-spaced OR all
  1.5-spaced". The profile takes double and says so; `onehalf` is equally
  compliant. Mixing is what FSU forbids.
- **The typeface is left unset on purpose.** FSU says the manuscript "should be
  in either Times New Roman or Arial" — "should", not the "must" it uses for
  margins and spacing. Encoding `TeX Gyre Termes` here would be this file
  deciding that a metric-compatible clone counts as Times New Roman, which is
  Manuscript Clearance's call. Flagged in the header for filers.
- **The committee page is NUMBERED** ("The Committee page is the first numbered
  page", i.e. ii), so unlike the class's neutral approval page it must not set
  `\thispagestyle{empty}`. The document still owns `\pagenumbering{roman}`.
- **No signature lines anywhere.** FSU collects approval through Manuscript
  Clearance and the Graduate Student Tracking database, and separately requires
  signatures to be stripped from the filed PDF: "Redact, delete, or obscure ...
  any signatures."
- **One ordering rule this file cannot enforce**: "The University Rep is always
  listed immediately after the chair (or co-chairs)." The chair comes from
  `\gradadvisor` and everyone else from `\committeemember` in call order, so a
  filer must put the University Representative first among the
  `\committeemember` calls. Said in the file.
- **No accessibility rule is published** — the 2024 PDF and the Formatting
  Guidelines page contain none of accessible / alt text / WCAG / tagged /
  PDF/A. FSU's "Redact ... any signatures" rule reads adjacent but is privacy,
  not accessibility, and is deliberately not recorded through that field.
- The specimen is dated May 2016 but is the file the **current** page links, and
  the 2024 guide defers to it by name. Not a superseded edition.
- Small trap worth remembering: a placeholder default that is printed through
  `\MakeUppercase` must not contain a `\string`'d control sequence — it came
  out as `\FSUCOLLEGE` and would have sent a filer after a command that does
  not exist.
