# 2026-09-06 — academy-of-art-university

**blocked** — alphabetical fallback. Round of ten, institution 7 of 10.

AAU has a thesis, but it is a **per-department creative Final Thesis Project**,
not a filed manuscript, and AAU publishes no university-wide format for it.

What was read on the access date:

- https://www.academyart.edu/catalog/ — the Course Catalog Listing.
- https://www.academyart.edu/courses/thesis/ and
  https://www.academyart.edu/courses/final-thesis-completion/ — the thesis
  courses themselves.
- https://my.academyart.edu/my-academy/academic-resources/graduate-student-academic-resources/
- https://elmo.academyart.edu/find-resources/mfa.html — the library's Master's
  Thesis Projects collection.

Things a later pass should not have to rediscover:

- **The catalog PDF URL that search engines return is dead.**
  `https://www.academyart.edu/wp-content/uploads/academy-art-u-catalog-web.pdf`
  returns an HTML **"Page not found"** page with a 200-ish body — so a naive
  download saves 330 KB of HTML under a `.pdf` name and `pdftotext` fails on it.
  The live catalog is at `https://www.academyart.edu/catalog/` and is a
  JS-driven course listing with no PDF behind it.
- **The graduate-resources URL redirects.** `my.academyart.edu/.../graduate-student-academic-resources/`
  lands on a generic "Current Students" page — zero occurrences of "thesis",
  "margin" or "handbook".
- **What AAU's thesis actually is.** The course descriptions make it plain: GR 810
  "Graphic Design Thesis" is about "conceptualization, research, and prototyping";
  IXD 830 "Final Thesis Completion" is about "mood boards, experimenting with
  typography, composition, color, balance, layout, legibility". These are studio
  projects, reviewed by a committee and presented — not a manuscript filed to a
  central format standard. Each department runs its own.
- **The one formatting page on an `academyart.edu` domain is off-limits.**
  `libguides.academyart.edu/research-process/mla-formatting` gives MLA advice
  (12pt Times New Roman and so on). It is a **library research guide** —
  explicitly excluded by RESEARCHING.md — and it is about course papers, not a
  filed thesis. **Do not build a profile from it.**
- **Worth revisiting** only if AAU publishes a graduate thesis manual. Any real
  format rules likely live in per-department handbooks behind the
  `my.academyart.edu` student login, which is not a public source either.
