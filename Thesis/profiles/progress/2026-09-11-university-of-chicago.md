# 2026-09-11 — university-of-chicago

**blocked** — HERD rank 38.

UChicago's authoritative filing requirements are the *University-Wide
Requirements for the Ph.D. Dissertation*, published by the Dissertation Office
(Center for Digital Scholarship) at `lib.uchicago.edu`. That entire host —
including `phd.lib.uchicago.edu` and the `documents/447/booklet2011.pdf` copy —
answers every request with a Cloudflare Turnstile "Verification Required" page:
plain `curl`, `curl` with a browser User-Agent plus a `Referer`, WebFetch, and
the in-app Browser pane all got the wall, and the non-interactive Turnstile did
not clear on its own.

What a later pass must not rediscover: `registrar.uchicago.edu/graduation/
doctoral-dissertation/` and `studentmanual.uchicago.edu/academic-policies/
dissertation-requirements/` are both reachable and both carry *zero* format
figures — they only say "All dissertations must follow the instructions provided
in the University-Wide Requirements for the Ph.D. Dissertation, available from
the Dissertation Office". So the blocked host is the only source, and search
snippets quoting margins for UChicago are quoting that blocked page.

A person with a browser can read it in one click; delete
`blocked/university-of-chicago.csv` to requeue it.
