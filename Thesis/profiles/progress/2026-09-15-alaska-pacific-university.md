# 2026-09-15 — alaska-pacific-university

**blocked** — PR #233.

APU does award thesis-bearing degrees — the low-residency M.F.A. in Creative
Writing requires `CRWR 69900 Thesis` (8 credits) — but publishes no filing
format anywhere reachable.

What was read, so a later pass starts further along:

- `https://www.alaskapacific.edu/graduate-studies/` — no occurrence of "thesis".
- The 2024–2025 Student Handbook (56 pp) — **zero** occurrences of "thesis" and
  zero of "margin".
- The 2026–2027 catalog's Academic Regulations — GPA, credit and probation
  policy only. Its one thesis sentence is about `NC` grades on
  "thesis/dissertation/professional project classes", not about format.
- The M.F.A. program page — degree requirements and outcomes, no format.

Fetching notes:

- `www.alaskapacific.edu` 403s WebFetch but serves curl with a browser
  User-Agent plus `Sec-Fetch-Dest: document` / `Sec-Fetch-Mode: navigate`.
- The Acalog catalog (`catalog.alaskapacific.edu`) returns an **empty body** to
  both WebFetch and curl — its `search_advanced.php` answers `202` with zero
  bytes. It reads fine in the Browser pane, which is the way to search it.
- Current catalog is `catoid=18` (2026–2027); Academic Regulations is
  `content.php?catoid=18&navoid=550`.

Likely the format is set per program and lives in program materials that are not
public. Delete the block file to retry if APU publishes a graduate handbook.
