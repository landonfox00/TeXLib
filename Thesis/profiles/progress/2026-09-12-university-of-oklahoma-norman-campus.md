# 2026-09-12 — university-of-oklahoma-norman-campus

**profile** — HERD rank 74. PR #202.

Set: geometry (1in, the low end of OU's permitted 1–1.5in range), the title page
and the Committee Page, both built from the Graduate College's samples.
Accessibility recorded as **Not published**. `\thesissetspacing` deliberately
**left unset**.

Things a later pass must not rediscover:

- **OU publishes no line-spacing rule at all.** The instruction packet and the
  web checklist between them cover font size, margins, page order, page
  numbering, front matter, blank pages, file name — and never mention spacing.
  The class's neutral default applies. Do not import a figure from a
  neighbouring profile.
- The **margin is a range**: "minimum 1" and maximum 1.5"", with consistency
  across the document as the only other constraint. The profile takes 1in and
  says so; anything up to 1.5in is equally in spec.
- **Font size 12pt is a requirement**, not a range — "Standard, professional
  12-point font must be used throughout. (headings may be larger)" — but the
  class has no hook, so it is header-only.
- "**The document should not contain any blank pages**" (on the web checklist,
  not in the packet). A `twoside` build inserts `\cleardoublepage` blanks, so OU
  documents must stay `oneside`. Noted in the profile header.
- The latitude the profile leans on: "The text of the Title Page, Committee
  Page, and Copyright Page must include all text on the sample pages of the
  instruction packet (**format may vary**)". Wording is mandatory; arrangement
  is not.
- OU calls the approval page the **Committee Page**; it is required, is the
  document's second page, and carries **no signatures**.
- The sample writes each member as "Dr. John Doe, Chair". The profile does not
  add "Dr." — put the wanted form into `\committeemember`.
- `\ouacademicunit{}` is defined because the checklist requires "the exact name
  of the academic unit" and the class has no such field.
- Section 3 of the packet is titled "Accessibility" and contains **one sentence
  referring students to the ADRC** — a section that exists but asks for nothing.
  No ADA date anywhere.

Round of 2026-09-12 (ten institutions). Skipped as already in flight: the 29
`profile/...` branches open at the start of the round.
