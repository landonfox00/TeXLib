# 2026-09-14 — albert-einstein-college-of-medicine

**blocked** — round of ten, institution 10. PR #224.

The Sue Golding Graduate Division's thesis guidelines exist as URLs and could
not be opened by any route available here. Recorded in
`blocked/albert-einstein-college-of-medicine.csv` so the queue moves on.

What was tried, so the next pass does not repeat it:

- **`einsteinmed.edu` returns 403 to every automated client, including its own
  homepage.** Not a per-file restriction — bot protection across the domain.
  Tried: plain `curl`; `curl` with a Chrome User-Agent; the same plus a
  `Referer`, `Accept: application/pdf`, `Accept-Language`, the three
  `Sec-Fetch-*` headers and `Upgrade-Insecure-Requests`; and a cookie jar
  primed from the homepage first (which itself 403s, so there was nothing to
  prime with). WebFetch gets the same 403. This is a harder block than the
  `grad.tamu.edu` case recorded in the routine's instructions — the
  User-Agent-plus-Referer trick does not work here.
- **The in-app browser pane reaches the site but not the documents.**
  `einsteinmed.edu/uploadedFiles/education/phd/thesis_guidelines_r.pdf` responds
  with a file download rather than a page, so the pane cannot render or read it.
- **`thesis-defense-guidelines.pdf` (GRAD-POL-007) redirects to a PowerDMS
  login** — `accounts.powerdms.com`. Einstein keeps its policy documents in
  PowerDMS, so that one is genuinely behind authentication, not merely awkward.
- **Two candidate PhD pages 404.** `einsteinmed.edu/education/phd/current-students/`
  and `.../academics/_content/overview.html` both resolve to the site root or a
  404 page; the site has been reorganised under the Montefiore Einstein brand
  and the old `einstein.yu.edu` paths are gone too.
- **The two sources that *are* readable are both excluded by RESEARCHING.md.**
  The D. Samuel Gottesman Library's "Author's Toolkit" LibGuide
  (`library.einsteinmed.edu/thesis/`) is a library guide, and the departmental
  first-year handbooks are department pages. Neither is a source for a profile,
  and a later pass should not be tempted by them — the LibGuide in particular
  looks authoritative and says outright that you should go to the Graduate
  School for the official guidelines.

The one substantive thing learned in passing, from search snippets rather than
from a page actually opened, and therefore **not** usable as a citation: Einstein
directs students to Turabian where its own guidelines are silent, and paginates
the front matter in small roman numerals beginning with the title page. If a
later pass gets into the guidelines, expect those two to be confirmed there.

**To retry:** delete `Thesis/profiles/blocked/albert-einstein-college-of-medicine.csv`.
The realistic routes are a browser session that can save the PDF to disk, or an
email to the Graduate Division for a copy that is not behind PowerDMS.
