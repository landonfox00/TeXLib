# 2026-09-10 — university-of-colorado-boulder

**profile** — HERD rank 38. PR #179.

Set: 1in margins, the title page from the Graduate School's own sample,
`\thesisnoapprovalpage`, and six accessibility requirements. Specifications
headed "Revised 2018, 2023, 2026", so current.

**`\thesissetspacing` is deliberately unset, and that is a finding.** Boulder
states no line-spacing rule for the body. The Specifications cover pagination,
type, margins, headings, style, title page, abstract, tables and figures,
footnotes, citations and bibliography, and never give a figure; the only mention
is hedged and about the bibliography ("Often the entries in the bibliography are
single-spaced with a double space between entries"), and the checklist asks for
"Correct spacing of text, bibliography, quotes" without saying what correct is.
Do not fill this in from a neighbouring profile.

**Boulder's typeface rule contradicts itself, in both documents, identically:**
"Use a sans serif font accessible to screen readers (Times New Roman, Calibri,
Aptos, etc.)". Times New Roman is not sans serif. The profile sets no face and
says why. Do not "resolve" it by imposing a sans face — Boulder has not said
which half of its own sentence governs.

**The sample title page says "of the requirement for the degree of" — singular.**
The Specifications delegate the statement's wording to the sample ("statement
shown on sample page"), so the sample is the authority and the profile
reproduces it as written. The CU Denver | Anschutz template a few files away
reads "requirements". Do not reconcile them; they are different schools.

**Accessibility is mandatory here and named**: "The Digital Accessibility Office
has created Thesis Accessibility Guidance, to which each student must adhere."
Six items recorded verbatim (adherence, headings, document title metadata, alt
text, tables, 4.5:1 contrast). `\thesisrequiretagging` and
`\thesisrequiredocumentlanguage` are still **not** set — neither document names
a tagged PDF, PDF/UA, PDF/A or a document language, and the conversion advice is
just "Save as … PDF". Setting them would infer the mechanism from the goal.

Approval is a **separate single-page supplemental file** (the Thesis Approval
Form), signed electronically by the chair and one other member and uploaded
alongside the PDF — never a leaf of the manuscript. The eight-entry Thesis
Organization list confirms it.

Also: `\gradprogram` must carry "Department of X" here, since the sample prints
"Department of English". `\cubpriordegrees` is the only added macro.
