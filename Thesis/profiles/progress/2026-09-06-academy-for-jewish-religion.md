# 2026-09-06 — academy-for-jewish-religion

**blocked** — alphabetical fallback. Round of ten, institution 5 of 10.

AJR *does* have a terminal written degree work — the **Master's Project**,
typically 50–100 pages — but it publishes **no manuscript format** for it. The
catalog prescribes the project by content and process, never by layout.

Read on the access date: the **Academic Catalog 5786 / 2025–2026**, 141 pages.

Things a later pass should not have to rediscover:

- **`https://ajr.edu/academic-catalog` is a 301 to a PDF**, not an HTML page:
  `https://ajr.edu/wp-content/uploads/ACADEMIC-CATALOG-5786-2025-2026.pdf`.
  A naive fetch saves the PDF bytes under the original name and every text search
  on it silently returns zero — which is what happened here on the first pass.
  Run `pdftotext` on it, don't grep the download.
- **The browser pane cannot reach `ajr.edu`** — `navigate` returned "denied or
  failed". curl with a browser User-Agent works fine, so use that.
- **THIS IS THE NEW YORK INSTITUTION.** IPEDS UNITID 497718, `ajr.edu`, Yonkers
  NY. There is a separate, unaffiliated **Academy for Jewish Religion
  (California)** — the very next slug in this round's queue,
  `academy-for-jewish-religion-california`. Do not let sources cross between the
  two files.
- **Counts in the catalog: margin 0, title page 0, accessib 0.** The two
  "signature" hits are a complaint form ("Signature ___ Date ___"), not an
  approval page.
- **The one formatting rule in the catalog is deliberately NOT reused here.**
  Under "Guide for Submitting Papers": "Written papers submitted as course work
  should be double-spaced in a standard, easily readable, 12-point font." That is
  scoped to **course work**. The Master's Project is a separate degree
  requirement, not a course paper — the catalog even exempts students who wrote
  an M.A. thesis elsewhere from it. Applying a coursework rule to the filed
  project would be exactly the inference RESEARCHING.md forbids, and it would not
  be enough for a profile anyway (no margins, no pages).
- What the catalog *does* say about the project is all substance: "heavily
  footnoted from source materials, both primary and secondary", "An extensive
  bibliography should accompany the work", "typically vary in length from 50 to
  100 pages", citation style free ("Chicago Style, the SBL Style, or the MLA
  Style"), plus a dated submission timeline and a half-hour oral presentation.
  None of it is layout.
- **Worth revisiting** if AJR ever publishes a Master's Project style guide — the
  document exists, so unlike the acupuncture schools in this round there is a real
  manuscript that a profile could serve.
