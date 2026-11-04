# 2026-09-09 — michigan-state-university

**profile** — HERD rank 38. PR #166.

Set: geometry (1in, the bottom of a stated range), spacing (double, one of two
permitted), the title page from the annotated specimen, and
`\thesisnoapprovalpage`. Left to the neutral fallback: chapter openings and
every accessibility declaration.

Things a later pass should not have to rediscover:

- **Two superseded editions are still served, and search engines prefer them.**
  The governing guide is dated **August 2026** and lives on MSU's Sitecore CDN
  (`edge.sitecorecloud.io/.../manuals/etd-formatting-guide-august-2026.pdf`),
  linked from *Formatting Your Document* as the "Printable Formatting Guide".
  A web search for the MSU ETD formatting guide returns
  `grad.msu.edu/sites/default/files/content/etd/ETD Formatting Guide August
  2025.pdf` and `... FINAL Jan 2023.pdf` first; neither is linked from the
  current page. Take nothing from those.
- **The page itself is JS-rendered and `get_page_text` returns empty.** Pull the
  document links out of the DOM instead.
- **Margins are a range** — "between 1 and 1 1/2 inches and consistent on all
  sides" — and spacing is a choice (1.5 or double). The profile takes 1in and
  double and says so. Note the consistency clause: a binding allowance on the
  left alone is *out* of spec at MSU.
- **The approval is an electronic Form, never a page**, and the guide explicitly
  forbids attaching it to the ProQuest submission. Preliminary pages are Title,
  Abstract, Copyright, Dedication, Acknowledgements, Preface, TOC and the lists —
  no signature leaf.
- **The typeface rule is a ban, not a list**, so the class satisfies it: "Script,
  small caps, and ornamental fonts will not be accepted", with five faces
  "strongly suggested". Contrast Arizona State (PR #165), whose closed list of
  eight the class fails.
- **One ambiguity left for the reviewer**: line 5 of the title-page block is
  written `<unit/program> - <degree>` in the prose and rendered with an em dash
  in the specimen. The profile emits the prose's spaced hyphen, per
  RESEARCHING.md's prose-over-template rule.
- **Accessibility: nothing published.** The string "accessib" occurs once in the
  whole guide, about transcribing QR codes and linked video. Recorded as its own
  entry alongside "Not published". MSU's university-wide accessibility programme
  and its library's accessible-LaTeX guide are not the Graduate School's filing
  requirements and are not encoded.
