# 2026-09-22 — american-islamic-college

**blocked** — alphabetical fallback (the HERD priority list is exhausted).

There is a thesis: the MA in Islamic Studies is 36 credits including a 3-credit
thesis course (IS 559 in the Islamic Theology concentration, IS 589 in Islam
and Global Studies). What the college publishes about it is one sentence —
"The MA thesis should be a MLA or an APA-formatted paper summarizing the
research the student has done under the supervision of a full-time faculty
member of the Islamic Studies Program" — plus a committee rule, "a thesis
committee of three persons: the faculty research-mentor, and two additional
faculty readers". Nothing about margins, spacing, a title page, an approval
page, a font or binding. A named citation style is not a filing format, and
the class has no field for one; reading APA's own 1in/double-spaced defaults
into this would be inferring a requirement the college never stated.

For a later pass:

- The 2024 catalog PDF is at
  `https://aicusa.edu/wp-content/uploads/2024/09/2024_student_catalog.pdf` and
  is the current edition (its own header says "August 23, 2024 update; check
  wwww.aicusa.edu for more current editions"). Read in full; the thesis text
  above is all of it.
- `https://aicusa.edu/wp-content/uploads/2019/08/Handbook-2018-updated-2.13.2019.pdf`
  (the Student Handbook) contains no occurrence of "thesis", "margin", "title
  page" or "signature page" at all.
- The graduate-admissions page carries admissions procedure only.
- FETCH NOTE: `aicusa.edu` serves an HTML page, not the PDF, to a bare
  `curl -o`; the download succeeds with a browser User-Agent **and** a
  `Referer` naming a page on the site. WebFetch retrieves the bytes but hands
  back the raw PDF stream, so run `pdftotext` over the file it saved.
