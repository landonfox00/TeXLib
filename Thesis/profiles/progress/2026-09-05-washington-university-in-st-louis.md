# 2026-09-05 — washington-university-in-st-louis

**profile** — HERD rank 30. PR #130. Round of ten, institution 8 of 10.

Geometry, spacing, title page and `\thesisnoapprovalpage` set. No accessibility
check-flag raised. `\thesissetchapteropening` is unset **deliberately** — see
below; it is not a gap.

## How to reach these sources again — this cost most of the time here

- **`gradstudies.artsci.washu.edu/guide-doctoral-dissertation` is gated.** It
  returns 403 to curl *and* renders "Access denied … Please click here to log
  in" in a real browser. Don't keep retrying it.
- **`gradstudies.artsci.washu.edu/guides` is NOT gated** and is readable in the
  in-app Browser pane. It carries the links. That is the way in.
- **WashU moved wustl.edu → washu.edu**, and `graduateschool.wustl.edu` no longer
  resolves at all (curl exit 35, TLS failure). Search results still point at
  both.
- **Both documents live on Box**, whose `/s/<hash>` pages are JavaScript viewers
  curl cannot read. Recipe: open the page in the Browser pane, pull the file id
  out of the DOM (it appears as `f_<digits>`), then fetch
  `https://wustl.app.box.com/index.php?rm=box_download_shared_file&shared_name=<hash>&file_id=f_<digits>`,
  which returns the real file.
- **The template is a legacy `.doc` (OLE compound), not `.docx`** — it will not
  unzip. `antiword` is on this machine and reads it.

## Findings

- **The Guide is about process, not formatting.** The 19-page "WashU PhD
  Dissertation Guide" (last updated **May 2026** — the freshest source of the
  round after Penn State's) states no margin or spacing figure at all. The rules
  are in the **template**, which says of itself that it "contains the guidelines
  for the proper formatting of dissertations and theses for PhD students" and "is
  formatted using the same guidelines it describes".
- **WashU refuses the page-number margin exemption** that Northwestern (#128) and
  Emory (#129) grant: "nothing, not even page numbers, should print in the
  margins", with numbers "immediately above the bottom margin". This is the first
  institution this round where the class's `includefoot` footer placement is
  *exactly* right rather than merely tolerable. Do not cross-correct against the
  siblings.
- **The chapter-opening rule is permissive, which is why the hook is unset.** "You
  may start the chapter title below the top margin or you may leave some space
  and start the chapter title up to 3 inches from the top edge of the page."
  Anything from 1in to 3in is in spec; the class default is WashU's *first*
  stated option. Setting `{3in}` would also be in spec but would be a choice, not
  a requirement.
- **No post-nominals on the committee.** The Guide's checklist: "Did you remember
  to remove Ph.D. from your faculty titles?" This is the opposite of most
  profiles here — don't copy a `\committeemember` line from a sibling.
- **`\gradprogram` carries two lines at WashU** — the administrative unit over
  the program ("Division of Biology and Biomedical Sciences" / "Neurosciences"),
  because the checklist asks whether the title page shows "the correct
  administrative unit and school".
- **Ambiguity left for the reviewer:** the template says the title should be in
  "Title Case"; the Guide's checklist asks "Is Your Title in Sentence Case, as in
  This Question?" — a line itself written in Title Case. The two documents name
  different cases and the checklist contradicts its own example. The title is
  emitted **verbatim**, which is correct under either reading.
- **Nothing is bold**: "Use a 12-point regular font."
- **No signatures in the document.** Table 1.1 is exhaustive and lists no
  approval, committee or signature page; the committee is on the title page.
  Approval rides on the Dissertation Defense Approval Form and the Examination
  Approval Form, routed to the school administrator.
- **No accessibility rule is published.** Zero hits in the 24-page template; two
  in the Guide, both meaning "available to your committee" / "to hand". WashU is
  private. Recorded as `{Not published}`.
