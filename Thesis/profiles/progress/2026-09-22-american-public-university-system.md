# 2026-09-22 — american-public-university-system

**blocked** — alphabetical fallback (the HERD priority list is exhausted).

This is the clean "behind a login" case, and the most frustrating institution
of the round: APUS has a thesis option, has a written format standard for it,
and publishes everything *except* that standard. The public graduate catalog
says master's programs end with "a comprehensive exam, a thesis or an
integrative practicum"; the public Student Handbook names the thesis, creative
project, practicum and portfolio options and then says "please refer to the End
of Program Assessment Manual for Graduate Studies". The EOP Manual is the
document that carries the margins, the title page and the rest, and its only
link — on that same public handbook page — is
`http://ebooks.apus.edu.ezproxy1.apus.edu/Capstone/CapstoneManual.pdf`. That is
the ecampus proxy. The bare host `ebooks.apus.edu` does not resolve publicly at
all (NXDOMAIN), so there is no unproxied copy to reach.

Things a later pass should not rediscover:

- **Do not confuse APU (Azusa Pacific) with APUS.** Searching "APU thesis
  format handbook" surfaces `www.apu.edu`'s and `webspace.apu.edu`'s "APU Style
  and Format Handbook for Dissertation and Thesis Publications", which is Azusa
  Pacific University's and has nothing to do with this institution. APUS's own
  domains are `apus.edu`, `apu.apus.edu`, `amu.apus.edu` and `catalog.apus.edu`.
- `https://www.apu.apus.edu/docs/shared/success-center-pdfs/mastersthesis.pdf`
  is public and fetches cleanly, but is a one-page handout about writing a
  thesis *statement*; it states no format figure and itself points at the EOP
  Manual.
- `https://myclassroom.apus.edu/shared/commonfolder/science-and-technology-common/ITCC/ITCC500/APA%20Resources/APUS%20APA%20Style%20Guide.pdf`
  is also public, but it is a course-level APA 6th-edition writing guide, not
  the filing rule.
- An `academia.edu` copy of the EOP Manual exists. It is a third-party re-host
  of unknown version and is not a source under RESEARCHING.md.
- `researchandacademicexcellence@apus.edu` is the address the library's own FAQ
  gives for EOP Manual questions and for earlier versions. Asking them for the
  current manual is the realistic way to unblock this one.
