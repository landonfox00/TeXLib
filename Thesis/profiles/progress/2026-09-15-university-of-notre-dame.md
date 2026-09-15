# 2026-09-15 — university-of-notre-dame

**profile** — HERD rank 100, the last entry in `priority.csv`. PR #229.

Complete but for the typeface: geometry (left 1.5in, others 1in), double
spacing, a 2in chapter opening, the title page from the Graduate School's own
Formatted Example File, and `\thesisnoapprovalpage`. Notre Dame ships its Word
template in three faces, so no face is required and none is set.

For a later pass, so it is not rediscovered:

- **Do not read the guide's one use of "accessible" as an accessibility rule.**
  It says flattening vectors to PNG/JPG "makes the PDF more accessible in terms
  of the resources needed to read the file" — file size, not disability access.
  Following it would also destroy the tagged content this class emits.
- The title page carries a **director's signature line that is never signed**:
  "Although we retain the classic signature line, do not include a scanned or
  digital signature on the official submission." The rule is drawn blank on
  purpose.
- The guide's literal spacing counts (four lines here, eight there) come to ~53
  lines and do not fit a letter page; the profile uses proportional `\vfill`
  and reproduces exactly the three blocks the guide names as double-spaced. The
  guide itself treats the counts as adjustable. An earlier draft double-spaced
  the whole page and pushed the date onto a second leaf.
- The sample title pages the guide refers to are **not in the guide** — they are
  in `gs_dt_template_example.pdf` on the Author Resources page.
- `dt_formatting_guide_updated_6_23_2026.pdf` is dated 2026-06-23 in both its
  filename and its PDF ModDate: the most current source in this round.
- Not encodable, recorded in the header: page numbers centred ¾in from the
  bottom, the abstract neither numbered nor counted, all-capital division
  headings, and a 30MB submission cap.

With this institution the ranked queue is exhausted; `next` falls back to
alphabetical from here.
