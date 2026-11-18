# 2026-09-10 — university-of-virginia-main-campus

**profile** — HERD rank 33. PR #174. An honest partial, in the `stanford-university`
mould but for a different reason.

Set: the institution name, the title page (from the Graduate School of Arts &
Sciences' own *Example Title Page* template), and two accessibility findings.
**Left at the neutral fallback: geometry and spacing** — and also, as a third
state the class cannot express, the approval page.

**Do not go looking for UVA's margin rule. There isn't one.** UVA runs no single
university-wide graduate school. The Library's ETD checklist — the one
university-wide document — heads its step 2 "Know your school's instructions"
and lists nine schools with nine separate procedures. The Graduate School of
Arts & Sciences, the largest, publishes a title-page template and nothing else:
no margin, no spacing, no typeface, no page numbering. Four URLs were read and
none carried a figure. Third-party sites state margins for UVA confidently; none
of them is a `uva.edu` page. Finishing this profile means picking a *school*, and
a school-level figure belongs in a school-specific profile, not in this one — the
IPEDS slug covers the whole university.

**The approval page is left at the neutral fallback on purpose, and that is not
"unchecked".** UVA prescribes no approval page in the manuscript: approval is
the "Final Exam Form must be submitted to the Graduate School", and the only
committee element in the filed document is the *optional* title-page block the
template annotates "(no signatures)". `\thesisnoapprovalpage` was still not
called, because UVA never says the document may not contain one, and that
macro's contract is a quote to that effect. "Not prescribed" and "forbidden" are
different findings. The file says so at length; the PR asks the reviewer whether
to promote it.

Two smaller things. **PDF/A is preferred, not required** — "If the approved
version is a document, it MUST be in PDF format (PDF/a preferred)"; the MUST
governs "PDF", so `\thesisrequirepdfstandard` is not called. And the profile
adds two local macros, `\thesisuvahometown` and `\thesisuvapriordegrees`, for
title-page fields no other institution asks for; both default to empty and their
lines vanish when unset.
