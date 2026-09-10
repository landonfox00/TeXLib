# 2026-09-10 — rutgers-university-new-brunswick

**profile** — HERD rank 32. PR #173.

All set from the School of Graduate Studies' *Electronic Thesis and Dissertation
Style Guide* and its two linked title-page samples: 1in margins on all four
sides, double spacing, and the title page reproduced from the specimen. Nothing
is left to the neutral fallback. `\thesissetchapteropening` is deliberately not
called — SGS states one margin figure and no deeper chapter opening.

Three things a later pass should not have to rediscover.

**The doctorate and master's samples differ only in words the class already
varies by `\doctype`** — "A dissertation submitted to the" against "A thesis
submitted to the", plus the degree line. One title page covers both; do not add
a second.

**The accessibility date here is 26 April 2027 and is NOT a typo for 2026.** SGS
writes "Starting on April 26, 2027, all electronic dissertations and theses will
be required to comply with Title II ADA accessibility standards." The Title II
deadline differs by the size of the public entity, so a neighbouring profile
carrying 2026 is also right. Do not reconcile them.

**`\thesisrequiretagging` is deliberately unset.** SGS names Title II and points
at its own PDF guide but never says "tagged PDF", "PDF/UA" or "PDF/A". Setting
the flag would infer the mechanism from the standard. It is a judgement call and
is flagged as one in the PR; the reviewer may reasonably flip it, especially
after April 2027.

Also: Rutgers-Camden's Graduate School publishes a *separate* dissertation style
guide (`graduateschool.camden.rutgers.edu`). It was not read for this file and
must not be used for it — this profile prints "New Brunswick, New Jersey" on the
title page, which is campus-specific.
