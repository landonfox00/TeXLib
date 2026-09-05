# Round log, one file per institution

Each research pass by `texlib-thesis-profile-round` writes exactly one file
here:

    <YYYY-MM-DD>-<slug>.md

where the date is the access date and `<slug>` is the IPEDS slug the profile
uses. One file per institution per round — never an append to a shared file.

## Why not one shared log

`PROGRESS.md` used to carry every entry, appended at the end. That worked while
the routine did one institution a night. It stopped working on 2026-09-04, when
the routine changed to **ten institutions per round, one draft PR each**:

- Ten branches all appending to the end of one file means that once the first
  merges, the other nine conflict — every night, nine mechanical resolutions
  whose answer is always "keep both, in date order".
- Worse, the log stopped matching reality. A shared entry claims a profile
  landed; if that PR is later closed unmerged, the claim stays. A file that
  lives in the same PR as the profile it describes is merged or dropped
  **with** it.

Two filenames only collide if two rounds research the same institution on the
same day, which the queue already prevents.

## What goes in one

Short. The profile header carries the sources and the field-by-field reasoning —
do not restate it here. This file answers "what happened in that round, for that
school":

    # 2026-09-04 — texas-a-and-m-university-college-station

    **profile** — HERD rank 22. PR #118.

    One paragraph: what was set, what was left to the neutral fallback, and
    which source governed. Then anything a later pass must not rediscover —
    a superseded edition still on the server, a site that blocks fetches, an
    ambiguity left for the reviewer.

Outcome is one of:

- **profile** — a profile was written and a draft PR opened;
- **blocked** — the graduate school's own filing requirements could not be
  found, recorded in `institutions.blocked.csv` so the queue moves on;
- **dropped** — researched but not shipped, because the profile would not build.

`PROGRESS.md` keeps the record from before this change, including the
2026-09-02 top-20 batch. Nothing new is appended to it.
