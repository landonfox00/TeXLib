# 2026-09-12 — university-at-albany

**blocked** — HERD rank 75. PR #203.

The Graduate School's own requirements page,
`www.albany.edu/graduate/resources-current-students/dissertation-thesis-information`,
sits behind a **Cloudflare Turnstile** bot-detection challenge. Everything the
Graduate School publishes on formatting — including the "Dissertation Guidelines
& Forms" and "Thesis Guidelines & Forms" accordions — is on that page, and every
other UAlbany source found links back to it.

What was tried, so nobody repeats it:

- `curl` with a browser User-Agent → HTTP 403, Cloudflare interstitial.
- `curl` with a full browser header set (Accept, Accept-Language,
  Sec-Fetch-\*, Referer) on two different paths, including the older
  `/graduatebulletin/` tree → 403 on both. The whole `www.albany.edu` host is
  protected, not one page.
- `WebFetch` → HTTP 403.
- The in-app Browser pane → redirected to `https://albany.edu` showing
  "Performing security verification" with a Turnstile widget, still there after
  ~25s across three attempts. **Completing bot-detection is out of bounds for
  this routine**, so that is where it stops.

Sources that DO respond, and why none of them substitutes:

- `admissions.albany.edu/portal/etdhelp` (a different host, no Cloudflare) —
  real, and confirms the Graduate School and the Libraries run joint office
  hours covering "formatting questions, **accessibility requirements**,
  publishing options…". It states no requirement of its own. Worth knowing that
  UAlbany *has* accessibility requirements to find, once the page is readable.
- `scholarsarchive.library.albany.edu/etd/` — the repository. Its "Dissertation
  Guidelines & Forms" and "Thesis Guidelines & Forms" links point straight back
  at the blocked page.
- `libguides.library.albany.edu` — a library guide, excluded by RESEARCHING.md.
- `etdadmin.com/main/resources?siteId=185` — ProQuest boilerplate, excluded.
- An Overleaf "Albany LaTeX Dissertation Template" exists but is user-uploaded,
  not published by the Graduate School.

**Retry from a machine with an ordinary interactive browser session**, where the
challenge clears by itself; the content is public, not behind a login. Delete
`blocked/university-at-albany.csv` to re-queue.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
