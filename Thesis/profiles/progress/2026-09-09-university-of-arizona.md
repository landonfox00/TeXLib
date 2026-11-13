# 2026-09-09 — university-of-arizona

**profile** — HERD rank 35. PR #163.

Set: geometry (as a documented choice, not a requirement — see below), the
title page and the committee approval page, both reproduced from the Graduate
College's own specimens. Left to the neutral fallback: spacing, chapter
openings, and every accessibility declaration.

Things a later pass should not have to rediscover:

- **Arizona publishes no margin requirement.** Both formatting guides say, in
  III.C, that documents "archived and retrieved electronically in .PDF format do
  not need to abide by specific margins", and give 1in only as advice to
  students ordering bound copies from ProQuest. The profile pins 1in and says in
  its header that this is the bound-copy figure, not a requirement. Do not
  "correct" the header to read as though Arizona mandates 1 inch.
- **No spacing rule either.** Neither guide contains the word "spacing". This is
  an absence, not a gap in the research.
- **Page numbering is one arabic sequence from the title page**, which the class
  cannot produce and no profile field can set. Recorded in the profile header.
- **The approval page is never typeset by the filer.** The Graduate College
  collects signatures on its own specimen — Adobe Sign, or a colour print signed
  at the defence and scanned back — and that artifact goes in as page 2. The
  specimen carries a large UA wordmark watermark, deliberately not reproduced.
  What the profile typesets is the prescribed wording and signature layout, as a
  drafting aid.
- **Everything lives on Box, and Box is awkward.** The guides and specimens are
  `arizona.box.com/...` short links redirecting to `arizona.app.box.com/v/...`.
  To get the bytes: fetch the `/v/` page, pull `"sharedName"` and `"typedID"`
  out of the HTML, then GET
  `…/index.php?rm=box_download_shared_file&shared_name=<sn>&file_id=<f_id>`
  **with a cookie jar seeded by the `/v/` page first** — without the session
  cookie Box returns an HTML "link has been removed" stub that `file` reports as
  HTML and `pdftotext` chokes on. The `.doc`/`.docx` specimens cannot be
  downloaded this way at all; read them in the Browser pane's Box preview with a
  tall viewport (900x1500), and re-apply the resize after every navigation.
