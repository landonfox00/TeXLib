# Accessibility

TeXLib produces **tagged, PDF/UA-2 conformant** PDFs. Every accessible build is
validated with veraPDF and writes the conformance report next to the PDF.

## What you get

Every build can emit two PDFs:

| File | What it is |
|---|---|
| `<base>.pdf` | The normal document. Unchanged by any of this. |
| `<base>_accessible.pdf` | A tagged twin: PDF/UA-2 + PDF/A-4f, with a real structure tree and MathML for the mathematics. |
| `<base>_accessible-report.html` | veraPDF's conformance report for that twin — the verdict plus every ISO 32005 clause it broke, if any. |

```bash
python texlib_cli.py build notes.tex --mode accessible
```

or `Ctrl+Shift+B` → "Accessible" in Sublime, or `python smoke_test.py
--accessible` across every shipped template at once.

Both PDFs are kept because the tagged twin is typeset in a separate
run and can differ from the normal PDF in spacing and page breaks.
That run always uses lualatex, while lecture notes, problem sets and
syllabi are otherwise built with pdflatex. The normal PDF
is the one to print and project; the tagged twin is the one a screen reader can
navigate.

The MathML travels as one associated file per distinct formula, in the `/AF`
entry of the formula's structure element, which is where Firefox and Foxit read
it. LaTeX's default also lists every one of those files in the document's
`EmbeddedFiles` name tree, the list viewers show as the document's attachments:
4,035 `mathml-N.xml` entries in a 241-page document, which SumatraPDF appends to its
bookmarks pane after the outline. The accessible build sets
`viewer/pane/mathml=false`, so that list holds only the document's real
attachments. A document with none carries LaTeX's PDF/A-4f placeholder,
`pdf-A4f.txt`, as the one entry, as a document without mathematics already did.

## How conformance is verified

- **A required check.** `.github/workflows/accessible.yml` runs
  `smoke_test.py --accessible` on every PR to `main` and nightly, inside a
  pinned TeX Live container. It is a required check under branch protection: a
  regression is a red build, not a discovery months later.
- **Every class.** The gate covers all ten document classes — lecture notes,
  problem sets, quizzes, randomized exams, schedules, syllabi, report cards,
  bingo cards, problem-bank catalogs and the thesis class — plus the metadata
  and exam fixtures. `CLASS_HOME_MODULE` in `smoke_test.py` is the authoritative
  list.
- **Rule-level validation, not a smoke test.** Conformance is checked with
  [veraPDF](https://verapdf.org/) against the `ua2` profile, which is the
  flavour the documents actually declare. veraPDF's autodetect would silently
  fall back to a weaker profile on a file whose XMP claim is missing — which is
  the very defect the check exists to catch.
- **A missing validator fails the gate.** If veraPDF is absent the job fails
  instead of skipping, because a skipped check reports the same green as a
  passing one.
- **Answer keys.** `smoke_test.py --accessible` builds each document's default
  copy, in which a solution is typeset into a discarded box. The same job runs
  `test_solution_tagged_conformance.py`, which builds one exam's tagged student
  copy and four tagged keys (`solutions`, `solutions-inline`, `instructor`, and
  a `solutions` key whose part solutions have no header line) and requires that
  none has a failed check and that every list item is a label and a body. It
  also reads each key's structure tree for the order, which veraPDF does not
  check: every solution is one `<Div>` that reads "Solution." and then the
  answer.
- **The characters themselves.** Tags and conformance say how a document is
  structured, not whether the letters in it are the right letters. `smoke.yml`
  runs `test_text_layer.py`, which sets 35 non-ASCII characters through
  `texlib-corepkg` and `texlib-didactic` under both engines and asserts that
  `pdftotext` gives each one back unchanged; and every build in the suite fails
  if its log carries a `Missing character` line, meaning a glyph was dropped
  from the page. Both exist because neither failure is visible any other way:
  until 2026-09 a literal `§` in a lualatex build typeset `ğ`, most of Latin
  Extended-A and every curly quote vanished from the page, and a fully
  conformant, fully tagged PDF/UA file carried the wrong text to the screen
  reader. Structure was never the thing that was broken.
- **The layout of `{cols}`.** veraPDF validates the structure tree and does not
  read where the text sits, so an exam whose columns had collapsed into one
  would still conform. The accessible job also runs
  `test_cols_tagged_layout.py`, which builds one exam's `{cols}` problem as a
  normal copy and as a tagged copy and requires its parts in two columns in
  each.

## Getting the evidence

`<base>_accessible-report.html` is written beside the tagged PDF on every
accessible build, **whether it passes or fails** — a report naming the clauses a
file broke is the one worth reading. It is the artifact to hand over when
someone asks for proof; some graduate schools now require one filed with a
thesis.

A build that produces several tagged PDFs checks each one. A document with
solutions also builds `<base>_solutions_accessible.pdf`, and one with rubrics
builds `<base>_instructor_accessible.pdf`. Each is run through veraPDF and gets
a report of its own beside it, named after its PDF
(`<base>_solutions_accessible-report.html`). The build ends with one line per
tagged PDF, giving the verdict and the number of failed checks:

```
TeXLib: PDF/UA-2 conformance (veraPDF; set accessible_report_full for the itemized form):
    exam1_accessible.pdf  PASSED, 0 failed checks  -> exam1_accessible-report.html
    exam1_solutions_accessible.pdf  FAILED, 17 failed checks  -> exam1_solutions_accessible-report.html
```

A key is checked on its own because it has structure the base copy does not
have: the solutions. Until 2026-10 a build checked the base copy alone, and
every `{partsolution}` in a tagged key failed five checks beside a base report
that passed. A report is deleted when a build stops producing its PDF.

A report is kept only beside the PDF it was written for. When a build writes a
tagged PDF again, it deletes the earlier report as the new PDF lands, and the
check then writes the new one. If no report is written for the new PDF, the
build ends with none beside it, and it names an earlier report it removed:

```
TeXLib: removed a stale accessibility report (its PDF was rebuilt without a new report): exam1_accessible-report.html
```

That happens when `accessible_report` is off (the line says so), when veraPDF
is not installed, and when veraPDF ends in a tool error. Until 2026-10 the
earlier report stayed in all three, beside a PDF it did not describe. A build
that is cancelled after replacing a tagged PDF leaves no report for it either,
and prints no line.

veraPDF exits 0 for a conforming file and 1 for a non-conforming one, and writes
a valid report either way. Only an exit above 1 is a tool error. Lean by default
(~20 KB); `accessible_report_full` adds `--success`, which evidences all ~840
passed checks against the profile's 1727 rules, for when someone wants proof
rather than a verdict.

Without veraPDF installed, the build is unaffected and says the report was
skipped. Note that veraPDF's installer does **not** put itself on `PATH`;
TeXLib looks in the known install roots as well, so a complete veraPDF in
`~/verapdf` is found rather than reported missing.

## Known limitations

**Mathematics tagging is split across two methods, and readers disagree.**
MathML can be attached as associated files (AF), which Firefox's viewer and
Foxit read — the in-browser path from an LMS link — or as structure elements
(SE), which Adobe Acrobat reads. Emitting both is what covers a class of
readers; emitting one silently flattens the mathematics for the other half.

Which methods are emitted is declared once, in `ACCESSIBLE_DOCMETA` in
[`Sublime/texlib/texlib_buildspec.py`](Sublime/texlib/texlib_buildspec.py).
Check the current value there — it has changed to work around a toolchain bug
and may change again.

Builds ask for both and fall back per document. A `luamml` defect aborts the run
outright — no PDF — when one formula contains two or more `\sqrt[n]{...}`, and
only the SE path reaches the code responsible. A build that hits it re-runs the
tagged half with AF alone and says so. So a document with two nth-roots in one
formula reads as flattened text in Acrobat, while every other document is
covered in both readers. The trigger is narrow: of 26 math constructs tested as
sibling pairs under SE, only those involving `\sqrt[n]` abort, and two nth-roots
in separate formulas — or in separate cells of one matrix — are fine.

If you need SE on a document that falls back, the workaround is editorial rather
than technical: split the formula so no two nth-roots share it. The defect is
upstream, not in TeXLib, and it reproduces on a bare `article`.

**A failed check does not fail the build.** A tagged PDF that fails is reported
`FAILED` with its count, in the last lines of the build and in its report. The
build's exit status and the editor's build status are what they would have been
without the check. The same holds for a PDF veraPDF could not read, which is
reported `NOT CHECKED` with the reason. A script that needs conformance enforced
has to run veraPDF and test its exit status, as `smoke_test.py --accessible`
does in CI.

**`\tagpdfsetup{math/alt/use}` is deliberately not set.** It raises the score an
Ally- or UDOIT-style checker reports by replacing the MathML with flat alt text,
which hides the real markup from screen readers. Set it in your own preamble if
you need the higher score.

**Tagging changes what LaTeX accepts.** Under `tagging=on`:

- Inline list keys are fatal. `\begin{itemize}[leftmargin=*]` fails with
  "Some keys specified on the enumerate environment are unknown". Declare list
  formatting with `\setlist` in the preamble instead, which is honoured.
- `cleveref` is fatal — its `amsthm` patch leaves a block-level list open and
  the first definition-style environment dies. TeXLib routes `\cref` through
  `texlib-crossref.sty`, which uses cleveref normally and `zref-clever` in an
  accessible build. If you load cleveref yourself, you will hit this.
- The `tasks` package is not tagging-aware. It builds, and the tagged PDF
  fails: a `{tasks}` grid is recorded as paragraphs nested in a paragraph
  (ISO 32005 Table 5, `P-P` and `P-Part`). In an accessible build TeXLib loads
  `texlib-tasks.sty` whenever `tasks` is loaded, by a class or by your own
  preamble, and the grid is tagged as a list with one item per task. The log
  says so if that package could not install itself, which happens when `tasks`
  or the LaTeX tagging code is not a version it knows. The defect is upstream
  and is tracked as
  [latex3/tagging-project#370](https://github.com/latex3/tagging-project/issues/370).

**Conformance covers structure only.** PDF/UA-2 means the document's structure
is machine-checkable and correct. It says nothing about the quality of your alt
text, your colour contrast, or whether your tables are comprehensible.

## Why this exists

An untagged LaTeX handout reaches a screen-reader user as an unnavigable wall of
text, with the mathematics read as gibberish or skipped. The LaTeX kernel can now
produce the tagging that fixes this; most of the remaining work is knowing which
packages break under it, which is what this library encodes.

Separately, the US Department of Justice's Title II rule sets compliance
deadlines for public entities' web content, falling in 2026 and 2027 depending
on the entity's size. Course materials distributed through an LMS are in scope.
Consult the rule and your institution's guidance for the date that applies to
you; this file is not legal advice.

## Checking your own document

```bash
python texlib_cli.py build yourfile.tex --mode accessible
python texlib_cli.py doctor          # is veraPDF even installed?
```

Then open `<base>_accessible-report.html`. A `PASS` line against `ua2` is the
claim; the clause list is what to fix if it says otherwise. If no report
appears, veraPDF was not found — that is a skip, not a pass, and the build says
so.

To validate something TeXLib did not build, veraPDF's CLI takes any PDF:

```bash
verapdf --flavour ua2 --format html yourfile.pdf > report.html
```
