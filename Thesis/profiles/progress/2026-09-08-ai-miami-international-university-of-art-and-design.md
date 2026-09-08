# 2026-09-08 — ai-miami-international-university-of-art-and-design

**blocked** — alphabetical fallback. Round of ten, institution 9 of 10.

The institution is closed. It shut with the whole Art Institutes system on
2023-09-30, three years before this round and after the IPEDS HD2023 snapshot
the worklist is derived from. There is nobody to file a thesis with.

Things a later pass should not have to rediscover:

- **Two independent confirmations, both opened directly.** `ainextstep.com` —
  which is where `artinstitutes.edu` now redirects — says "Effective September
  30, 2023, The Art Institutes system of schools permanently closed" and names
  *Miami International University of Art & Design* first in its list of eight
  2023 closures. The Florida Department of Education's **Commission for
  Independent Education** closed-school transcript register lists "Miami
  International University of Art and Design, Miami" and gives its records
  location as the Art Institutes closed-school information page.
- **The domain probes are unambiguous**: `artinstitutes.edu/miami/` → **404** at
  `ainextstep.com/miami/`; `artinstitutes.edu` → **200** at `ainextstep.com`;
  `aimiami.edu` does not resolve at all (curl code 000). The IPEDS `web` column
  for this row (`www.artinstitutes.edu/miami/`) is dead.
- **`https://studentaid.gov/sites/default/files/ai.pdf` — the Department of
  Education's Art Institutes Closure Fact Sheet — TIMES OUT.** WebFetch (60s)
  and curl (45s) both failed on it. It is the obvious source to reach for and it
  is not reachable; use the two above instead.
- **`web02.fldoe.org/CIE/Transcript/TranscriptRequest.aspx` is a useful tool for
  any FLORIDA institution in this queue.** It is the state's register of closed
  independent postsecondary institutions and where their student records went.
  It already carries "Acupuncture and Massage College, Miami" (the subject of
  PR #144) and "Academy For Five Element Acupuncture, Inc., Hallandale" (#138).
  Read it with the Browser pane and search the rendered text — the table is long
  and alphabetical.
- **The worklist will keep serving closed institutions.** This is the second in
  the current alphabetical run. IPEDS HD2023 predates a wave of for-profit
  closures, so expect more; the closure check is cheap (probe the `web` column
  first) and should come before any format research.
