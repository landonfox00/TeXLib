# 2026-09-13 — university-of-delaware

**profile** — PR #205.

Complete. Geometry (left 1.5in bound-in side, bottom 1.5in, top and right 1in),
`\thesissetchapteropening{2in}`, double spacing, the full title page and
`\thesisnoapprovalpage` are all set from the Graduate College's own manual. Only
the typeface is left neutral: UD asks for "any standard font such as Courier,
Times Roman, Times, or Helvetica" at 12 point, which is a choice.

Things a later pass should not have to rediscover:

- **Three editions of the manual are on UD's servers and the filename of the
  current one is misleading.** The live Steps to Graduation page links
  `UD-Thesis-Manual-1-21.pdf`, whose name suggests January 2021 but whose cover
  reads "LAST UPDATED Jan 2026". Also reachable and NOT to be used:
  `UD-Thesis-Manual-7-19.pdf` on the same host and `UD-Thesis-Manual-19-1.pdf`
  on `grad.udel.edu` (cover: January 2019). Do not "correct" the source URL to
  a newer-looking one.
- **UD removed the signature page, effective Fall 2026**, and says so outright:
  "with the implementation of an electronic approval process, the signature
  pages have been removed from the final paper submission". Approval is
  collected on a form outside the document; the title page carries an
  "Electronic Version Approved:" block instead. The 2019 editions still
  prescribe the page, which is the trap the bullet above guards.
- **No accessibility rule is published.** The manual's only hit for
  "accessible" is about where to download the Word macros. Its "All fonts used
  should be embedded" sentence sits in the ProQuest section and is ProQuest's
  requirement, not UD's — deliberately not encoded.
- The dean's name is a field (`\udgraddean`), not a constant: UD's specimen
  prints the sitting dean but the facing explanation generalises it to "Correct
  Name of Dean". Unset, the page prints a loud placeholder.
- **The 2in title placement needed four measured fixes**, all commented in the
  file: `\centering` not `{center}` (trivlist `\topsep`), `\setstretch` not
  `{spacing}` (leading before the first line), a `\vbox` after
  `\nointerlineskip` (the stretched `\baselineskip` above line one), and
  `\topskip=0pt` (10pt before the page's first box). Each omission costs
  0.14–0.6in. Verified at 1.99in on the rendered page.
- **Observation for the class, not this profile:** with
  `\thesissetchapteropening{2in}` the first inked row of a chapter page
  measures 2.30in, because `\@makechapterhead` adds its own leading on top of
  the class's computed offset. That is shared behaviour affecting every profile
  using the hook (Michigan, UNC, Georgia Tech), so it was left alone here.
