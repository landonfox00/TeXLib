# 2026-09-06 — academy-of-chinese-culture-and-health-sciences

**blocked** — alphabetical fallback. Round of ten, institution 8 of 10.

This is the round's only **access** block: `acchs.edu` is unreachable, not
merely unhelpful.

Things a later pass should not have to rediscover:

- **THE WHOLE SITE IS BEHIND IMPERVA/INCAPSULA AND EVERY DOCUMENTED WORKAROUND
  FAILED.** What was tried, all on the access date:
  - plain `curl` → a 212-byte `_Incapsula_Resource` challenge stub;
  - `curl` with a Chrome User-Agent → same;
  - `curl` with full browser headers (Accept, Accept-Language, cookie jar) **and
    a `Referer`** — the trick that works for `grad.tamu.edu` → an 855-byte
    Incapsula iframe challenge;
  - `WebFetch` → empty content;
  - the in-app **Browser pane** → "navigation to https://acchs.edu was denied or
    failed";
  - **a static PDF asset directly** (`/wp-content/uploads/.../*.pdf`) → also the
    212-byte stub. The block is not limited to HTML pages, which is what rules
    out the usual "fetch the PDF instead" escape.
- **Do not spend another round re-trying curl variants.** Finishing this one
  needs a real browser session on a residential connection, or an email to the
  school.
- **The only reachable copy is EXPIRED and was deliberately not used for
  values.** The Wayback Machine has `MAcCHM_Catalog2023-2025.pdf` (44 pages,
  snapshot 2025-01-26). It is out of date by its own title and cannot be checked
  against the current edition, so nothing was encoded from it.
- **What that archived catalog does suggest**, recorded as intelligence rather
  than as a source: **margin 0, title page 0, double-spac 0, dissertation 0,
  capstone 0.** The two "thesis" matches are both inside the word
  **"synthesis"** ("protein synthesis"). So the MAcCHM professional master's
  appears to have no thesis requirement at all.
- **The open question is the DAOM.** ACCHS also awards a Doctorate of Acupuncture
  & Oriental Medicine, and doctoral programs of that kind often do have a
  capstone document. No DAOM catalog is reachable, live or archived, so whether
  a filed manuscript exists here is genuinely unknown.
- Wayback's CDX index lists catalogs back to 1998 if anyone needs the history;
  the newest is the 2023-2025 one above.
