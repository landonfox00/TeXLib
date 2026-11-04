# 2026-09-13 — iowa-state-university

**profile** — PR #206.

Complete, and the strongest accessibility case in the profile set so far.
Geometry (1in throughout), double spacing, the full title page,
`\thesisnoapprovalpage`, `\thesisrequiretagging` and seven quoted accessibility
requirements are all set. Left neutral: chapter-opening margin (ISU states
none) and typeface.

Things a later pass should not have to rediscover:

- **The layout is not on the requirements page; it is in a Box folder.** The
  requirements page prescribes title-page *content* item by item but never its
  order. The order came from the Graduate College's own annotated specimen,
  `PhD_Title_Page.pdf`, in the "Thesis_Dissertation Annotated Samples" Box
  folder (owner: Graduate College, file updated 17 Nov 2025) linked off the
  Toolkits and Resources page.
- **Box shared files download over plain curl** with
  `https://iastate.app.box.com/index.php?rm=box_download_shared_file&shared_name=<SHARE>&file_id=f_<FILEID>`.
  The file id comes from the anchor href in the folder listing, which needs the
  Browser pane (the listing is JS-rendered). That trick is worth keeping — several
  schools park their specimens on Box.
- **The two sources disagree on the committee's name and the profile follows the
  newer one.** The requirements page's Responsibility of Content statement says
  "program of study committee"; the Nov 2025 specimen says "academic plan
  committee" and heads the list "Academic Plan Committee:". ISU renamed the
  body. This is a deliberate departure from `RESEARCHING.md`'s prefer-the-prose
  default, argued in the file header. Do not "correct" either against the other
  without reading both.
- **The accessibility items are live rules, not aspirations.** ISU's grace
  period ran Jan–Dec 2024; "Starting in January 2025, the New Format
  Requirements will be treated as requirements", and ISU enforces them — "The
  thesis/dissertation will not be accepted until all requirements are met, even
  if this results in a delay to the student's graduation." That is what
  licenses `\thesisrequiretagging`. Document language and PDF standard are
  still NOT set: ISU names neither.
- **The title page has to fit one text block, and the block is 8.58in, not
  9in** (geometry's `\textheight` = 620.43pt). A spill puts a page number on
  the title page, against ISU's "No page number appears on the title page".
  Both `\vspace*{\fill}` centring and a `\vfill` before the copyright notice
  spilled — the latter because infinitely stretchable glue is a legal page
  break and TeX takes it on a full page. Fixed skips throughout; about 0.7in of
  slack remains for a longer title or an extra committee member.
