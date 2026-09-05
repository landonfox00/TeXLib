# 2026-09-05 — the-university-of-texas-at-austin

**profile** — HERD rank 31. PR #131. Round of ten, institution 9 of 10.

Spacing, title page and committee membership page set. **`\thesissetgeometry` is
deliberately UNSET** — the important part of this file. No accessibility
check-flag raised.

Things a later pass should not have to rediscover:

- **UT Austin publishes NO margin figure.** The entire margin section of the
  18-page Format Guidelines reads: "Margins should be consistent throughout the
  document, including the appendix." That is a *consistency* rule, not a
  measurement. Checked exhaustively: across all 18 pages the word "inch" occurs
  **once**, about oversized plates ("more than 11x14 inches"). So the geometry
  stays unset (the Stanford pattern) and the class's neutral 1in renders, which
  satisfies UT's only stated rule. **Do not fill this in from a sibling
  profile.**
- **But UT's own LaTeX package uses 1.25in on all four sides**, and that is
  recorded in the profile header for a filer who wants to match it:
  `\oddsidemargin 0.25in`, `\textwidth 6in` (its own comment: "8.5 inches, with
  1.25 inch margins"), `\topmargin 0.25in`, `\textheight 8.5in`. The profile does
  **not** set it — doing so would state as UT's requirement a figure UT declined
  to state, and 1in is equally in spec. Evidence laid out, choice left to the
  filer.
- **Spacing is recommended, not required**: "1.5 or double spacing is recommended
  for ease of reading." Same shape as the margin finding, one step less severe.
- **No signatures on the committee membership page, stated outright**: "The
  committee membership page in the pdf file that is uploaded for archiving and
  publication must not contain committee signatures." The strongest such
  statement in this round. Signatures go on a separate form, and UT is unusually
  specific: no proxy signatures, all on a single page, scanned/electronic
  accepted if legible, "Typed names as a signature are not allowed", and
  "Extensions will not be granted because a committee member was not available to
  sign."
- **No post-nominals on committee members** — "Educational or professional titles
  (Ph.D. or Dr.) are not included" — but "Supervisor"/"Co-supervisor" *must*
  follow the name. Same trap as WashU (#130), opposite of most profiles here.
- **The bold in Sample D marks fill-in fields, not typography.** The specimen
  bolds exactly the four placeholders a student replaces (title, name, document
  type, degree) and nothing else; the prose asks for bold nowhere. Everything is
  set plain. Flagged because a later pass could "correct" this from the picture.
- **The committee membership page comes BEFORE the title page** in UT's required
  order (item 2 vs item 3 — copyright page is item 1).
- **Numbering ambiguity left for the reviewer**: UT says numbering starts "with 1
  on the first page of the document (the Copyright Page or Committee Listing
  Page)" and numbers are "centered at the bottom of the page throughout", yet
  Samples C and D show no page number on either. The profile follows the samples
  and leaves both unnumbered, reading the prose as fixing where the *count*
  starts.
- **Conferral months are May, August or December only.**
- **Box access recipe applies here too** (same as WashU #130): the `/s/<hash>`
  pages are JS viewers; open in a browser, take the `f_<digits>` id from the DOM,
  fetch
  `https://utexas.app.box.com/index.php?rm=box_download_shared_file&shared_name=<hash>&file_id=f_<digits>`.
- **No accessibility rule is published, and this one deserves a re-check.** Zero
  hits across the Format Guidelines, the Digital Submission Requirement page and
  the LaTeX & Overleaf page. UT Austin *does* have a university-wide Digital
  Accessibility Policy (footer link on every page) and as a large public entity
  falls under the **April 2026** ADA Title II date — but the Graduate School has
  not applied either to a filed ETD in its published requirements, and the class
  must not invent the bridge. Contrast Florida (#125), where the graduate school
  made that link explicitly and all three flags are raised.
