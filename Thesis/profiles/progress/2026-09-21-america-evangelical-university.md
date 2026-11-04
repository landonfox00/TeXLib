# 2026-09-21 — america-evangelical-university

**blocked** — alphabetical queue. PR #256.

America Evangelical University (Gardena, CA) does publish a current institutional
catalog — `AEU_Catalog_2025-2026_v10.pdf`, linked from `/academics/catalog` — and
it has a real "Examinations, Candidacy, and Dissertation" section for the Doctor
of Counseling. That section is entirely **process**: committee composition,
advancement to candidacy, draft deadlines, the oral defence. It names no margin,
no line spacing, no title-page or approval-page layout, no style manual, and no
accessibility rule. The catalog's only uses of "accessible" are about database
courses and Korean-language access to a program.

What a later pass must not rediscover: the catalog PDF is reachable by plain
`curl` and `pdftotext -layout` reads it fine (8547 lines), so the block is not a
fetch problem. `/cs/forms` was also read in full — ten downloadable forms,
none of them a thesis format guide, style manual, signature page, or title-page
template. AEU has no separate graduate school site and no ETD page. The
requirements are, as far as the public web goes, **not published**; finishing
this profile means asking the administration office for whatever they enforce.
