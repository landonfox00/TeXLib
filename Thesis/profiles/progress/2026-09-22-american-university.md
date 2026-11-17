# 2026-09-22 — american-university

**profile** — alphabetical fallback (the HERD priority list is exhausted). PR #274.

The one complete profile of this round. Set: geometry (1in flat), spacing
(double), the full title page from AU's own specimen, and
`\thesisnoapprovalpage`. Left to the neutral default: the chapter opening,
because AU's deeper top margin is *permitted* ("up to two inches if desired"),
not required — a flat 1in is in spec and a student who wants the deeper one
adds `\thesissetchapteropening{2in}` themselves. Nothing is declared to
`\thesisrequiretagging` or its siblings: the ETD requirements name no
accessibility rule at all, which is recorded as `{Not published}`.

Things a later pass must not rediscover:

- **`www.american.edu` sits behind a Cloudflare bot challenge.** A `curl` with
  a browser User-Agent gets **403** ("Just a moment…"), and the in-app Browser
  pane stalls on the challenge page indefinitely. WebFetch goes through
  cleanly. Use WebFetch for the HTML pages; PDFs under `/upload/` fetch fine
  and WebFetch saves the bytes, so run `pdftotext` / `pdftoppm` over the saved
  file.
- **The specimen had to be rendered, not just extracted.** The signature rules
  on Appendix A's title page are drawn lines; `pdftotext` shows the names and
  labels but nothing about which line each sits under, and the left/right split
  between the committee block and the Dean block is invisible in the text
  layer. `pdftoppm -png -r 130 -f 2 -l 2` settles it.
- Neither the style guide nor Appendix A carries a revision date in the body.
  The specimen's filename, `etd-appendix-a-11-23.pdf`, is the only date
  evidence either document offers.
- **Signatures are still physical.** The student prints the title page, has the
  committee and the Dean sign it, scans it, and merges the scan back into the
  PDF. That puts an image of text into every filed AU document, which no amount
  of tagging on this side can fix. Stated in the profile header so nobody is
  surprised.
- Two wording discrepancies are left visible in the file rather than resolved:
  the prose writes "American University, Washington D.C. 20016" on one line
  without the comma while the specimen prints two lines with it (the specimen
  is followed), and the specimen insets the label "Chair:" slightly left of the
  signature rules, an offset neither source states in prose (here it is simply
  the first line of the block).
- The profile adds `\thesisschool`, as Texas A&M's adds `\thesiscopyrightyear`
  — AU's title page names the school or college and the class has no slot for
  it. Unset it prints AU's own placeholder, so an unfilled page looks unfilled.
  AU also wants the year alone on the title page, so `\graddate{2027}`, not
  "May, 2027".

Built with `\DocumentMetadata{lang=en,tagging=on,pdfstandard={ua-2,a-4f}}`,
two lualatex passes, no errors; the only warning is the expected
`\thesisnoapprovalpage` one. veraPDF `--flavour ua2`: compliant, 1727 rules
passed, 0 failed.
