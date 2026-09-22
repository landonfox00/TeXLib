# 2026-09-22 — american-international-college

**blocked** — alphabetical fallback (the HERD priority list is exhausted).

Unlike most blocks in this directory, AIC genuinely files dissertations: the
2025-26 Graduate Course Catalog carries an 18-credit four-course dissertation
block in the EdD (EDU9529/9539/9549/9559) plus a two-course dissertation
research sequence, and a PsyD dissertation sequence in Mental Health Counseling
(PSY9951/9952). What is missing is the *format* rule. The catalog was
downloaded and read in full (11,881 lines of extracted text) and contains no
occurrence of a margin, a spacing rule, a title-page or approval-page
prescription, or a named style manual for the filed document — the only
style mention is a course description saying one course "leads to the
completion of an APA formatted" paper, which is coursework, not a filing rule.

For a later pass, so this is not re-searched from scratch:

- The catalog index is at `https://www.aic.edu/academics/course-catalog/`, and
  the PDFs are served from `aic.cdn.neptuneweb.com`, **not** from `aic.edu`.
  The old `aic.edu/html/wp-content/uploads/pdf/...?x95878=` URLs that search
  engines still return answer 200 with an HTML page, not a PDF — a `curl -o`
  against one produces a file that `pdftotext` rejects as damaged. Use the
  catalog index page to get the current CDN link.
- `https://www.aic.edu/school-of-education/doctoral-programs-of-study/`
  301-redirects to `https://online.aic.edu/programs/online-edd`, which is
  marketing copy and links no handbook.
- Neither the School of Education landing page nor the online-EdD pages link a
  dissertation manual. If one exists it is behind the student portal, which is
  what this block records.

To retry: delete `blocked/american-international-college.csv` once a public
dissertation handbook appears, or after asking the School of Education for the
document it enforces.
