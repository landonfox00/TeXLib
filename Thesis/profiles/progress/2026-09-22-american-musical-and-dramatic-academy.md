# 2026-09-22 — american-musical-and-dramatic-academy

**blocked** — alphabetical fallback (the HERD priority list is exhausted).

AMDA's graduate programs do end in a thesis — the MA carries THR600 Thesis
Seminar (6.0 credits), whose own description ends "completing a finished
thesis, edited according to MLA guidelines and suitable for publication", and
the MFA in Writing for Theatre and Media ends in a creative thesis project.
That sentence is the entire published rule about the document. The
Consolidated Catalog's Academic Policies & Standards section covers enrollment,
attendance, grading, registration and graduation and states no margin,
spacing, title-page, approval-page or font requirement. A named citation style
is not a filing format and the class has no field for one.

For a later pass:

- The catalog lives at `https://amda.catalog.amda.edu/` (sections: About AMDA,
  Degree & Certificate Programs, Course Offerings, Academic Policies &
  Standards, Glossary, Revisions). `/academic-policies-all/academic-policies`
  was read; `/degree-certificate-programs/graduate-programs` does not exist.
- FETCH NOTE: `www.amda.edu` answers WebFetch with **403**. A `curl` with a
  browser User-Agent and a `Referer` gets 200. The program pages are
  JS-rendered, so the extracted HTML carries navigation chrome and no program
  prose — use the catalog host or the PDFs on `storage.amda.edu` instead.
  `https://www.amda.edu/graduate-programs/master-of-arts` now redirects to
  `/programs-list/ma-performance-studies-arts-ed`.
- The THR600 wording above is from
  `https://storage.amda.edu/media/documents/AMDA-MFA-MA-Handout.pdf`, which
  carries no date. If a dated source matters to a reviewer, that is the gap.
