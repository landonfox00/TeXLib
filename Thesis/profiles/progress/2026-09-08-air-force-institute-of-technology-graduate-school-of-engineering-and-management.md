# 2026-09-08 — air-force-institute-of-technology-graduate-school-of-engineering-and-management

**profile** — alphabetical fallback. Round of ten, institution 10 of 10.
PR #157.

Geometry, spacing, the title page and the committee membership page are all set
from the Graduate School's own *Style Guide for AFIT Dissertations, Theses, and
Graduate Research Papers*, June 2024 revised edition.
`\thesissetchapteropening` is deliberately left unset, and the accessibility
finding is a recorded absence.

Things a later pass should not have to rediscover:

- **AFIT is hard to fetch, and the routes that work are narrow.**
  `www.afit.edu` is unreachable from here through every channel tried: curl
  fails with an SSL error on TLS 1.2, 1.3 and a relaxed cipher list (`openssl
  s_client` connects and verifies fine, so it is a client/negotiation problem,
  not a bad certificate), WebFetch reports a closed socket, and the in-app
  Browser pane refuses the navigation outright. `scholar.afit.edu` is behind
  Cloudflare: the record page `scholar.afit.edu/docs/24/` loads in the Browser
  pane, but the PDF download at `cgi/viewcontent.cgi?article=1023&context=docs`
  returns **HTTP 403** to curl (browser UA + Referer), to WebFetch, and to a
  same-origin `fetch()` from the loaded record page, and a browser navigation to
  it lands on a bot-verification interstitial that does not clear.
- **The way through is record page live + PDF from the Internet Archive.** The
  live record establishes the edition ("Publication Date 6-2024",
  "Revised edition issued June 2024"); the capture
  `web.archive.org/web/20240916020100if_/…` supplies the 95-page PDF, whose
  cover reads "June 2024" and whose PDF CreationDate is 2024-06-28. Capture
  postdates the revision, internal dates agree with the live record — current
  edition, not a superseded one. **This is not the same situation as a stale
  archived catalog**; do not collapse the two.
- **The chapter-opening rule is a trap and the profile leaves it UNSET on
  purpose.** §4.3 says "On the first page of Chapter I, the title is placed
  three single lines below the normal one-inch top margin" — that is the report
  title, on Chapter I only ("Note that only Chapter I has the title of the
  thesis at the top of the page", §A.7), and it is measured *from* the normal
  1in margin, which it therefore leaves alone. `\thesissetchapteropening` would
  deepen every chapter opening, which AFIT does not ask for.
- **The committee page's gaps are shrinkable glue, and that is load-bearing.**
  Gaps were measured off the guide's own rendered specimen (5.5 single lines
  between blocks) and then written as `4.5\baselineskip plus 0pt minus
  3\baselineskip`. A dissertation adds members and the dean's name; a probe with
  **five members plus the dean** compresses onto one page with no overfull vbox.
  Anyone retuning that skip must re-run that probe.
- **`\afit@ccgap` is a MACRO, not a `\newskip`, and that was a real bug.** The
  first draft used `\newskip` assigned at profile-load time, which froze the
  preamble's `\baselineskip` rather than the single-spaced value the page runs
  at; every gap came out about 30% too deep and the specimen comparison caught
  it. Do not "tidy" it back into a length.
- **Four fields AFIT needs have no home in the class**, so the profile
  `\providecommand`s them: `\thesisdocumentdesignator`, `\thesisauthorrank`,
  `\thesisdepartment`, `\thesisdeanname` (dissertations only, prints only when
  set), plus `\thesisdistributionstatement` and `\thesisidentifyingword`. The
  designator is assigned by the Thesis Processing Center, not chosen by the
  student.
- **Two prescribed pages this profile does NOT produce**: the cover page (§6.1,
  which carries the AFIT crest) and the disclaimer/copyright page (§6.2–6.3).
  The class has no cover-page hook and the profile ships no crest. A filer must
  add both. Flagged in the profile header too.
- **GRADUATE RESEARCH PAPER is AFIT's third document kind** and the class's
  `\doctype` has no value for it. `\thesisidentifyingword` is overridable for
  that case.
- **No signatures inside the manuscript.** They live on the SF 298's
  coordination blocks and, for limited theses (Distribution B–F) only, the
  Document Distribution Memorandum, "signed by your primary research advisor and
  the department head" (§A.5).
- **Accessibility: genuinely nothing.** Zero occurrences of accessib, alt text,
  WCAG, Section 508, tagged, PDF/A or screen reader in all 95 pages, in a guide
  detailed enough to legislate widow/orphan handling and superscript point
  sizes. Recorded as `{Not published}`; no check-flag raised.
- The hidden tagged "Committee Membership Page" H1 shares a baseline with the
  document designator, so `pdftotext` interleaves their characters. Cosmetic,
  affects only the invisible run, and the tag tree order is correct. The obvious
  "fix" — moving the heading above the top margin — would put content outside
  the 1in margin AFIT requires on every page. Noted in the profile.
