# 2026-09-11 — oregon-health-and-science-university

**profile** — HERD rank 47. PR #193.

Set from the School of Medicine Graduate Studies formatting guide and the live
Forms, Policies and Resources page: geometry (1.5in left, 1in elsewhere), double
spacing, the title page from the guide's sample, and `\thesisnoapprovalpage`.

Things a later pass must not rediscover:

- **The formatting guide is footed "Revised 9/2010" and is nonetheless the
  current one.** The live Forms page links exactly this PDF, and OHSU publishes
  no other. Its modal is soft — "We recommend that you follow disciplinary
  conventions whenever possible. But for most cases, this formatting guide may
  be helpful." The figures are set because they are the only ones OHSU
  publishes, and the file says so.
- **The approval page has moved out of the document since 2010, and the 2010
  sample is still in the guide.** The old guide says "The second page of the
  document should be the CERTIFICATE OF APPROVAL page" and prints a sample with
  signature lines; the live Forms page now lists the Dissertation/Thesis
  Certificate of Approval as a **Smartsheet form**
  (`app.smartsheet.com/b/form/e5819d89111d40d992f6d71cf1f26527`) and says it
  "replaces the 'signature page' of your thesis". The profile follows the live
  page. Do not "restore" the bound page from the sample.
- **The one deeper-margin rule is deliberately not encoded.** OHSU requires the
  Table of Contents heading "not less than 2 inches from the top of the page" —
  one page only. `\thesissetchapteropening` would apply it to every chapter and
  major-section opening, so it is left unset.
- **`\gradprogram` must carry the whole department phrase** ("Department of
  Mathematics"): the specimen line is "Presented to the Department of Physiology
  & Pharmacology".
- **Escape the ampersand.** `\thesisinstitution{Oregon Health & Science
  University}` is a fatal "Misplaced alignment tab character" — caught by the
  build, fixed to `\&`. First profile in this library whose institution name
  needs it.
- **Accessibility not published** by Graduate Studies (the guide predates the
  question; the Forms page states none). One stone left unturned: the Library's
  deposit page at `digitalcollections.ohsu.edu/pages/?page=submitinfo` answered
  every fetch with a bot-protection interstitial (HTTP 202, empty body). If a
  deposit accessibility rule exists it would be there — and would be the
  Library's, not Graduate Studies'.
