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

Both PDFs are kept because tagging costs visual fidelity: `tcolorbox` theorem
wraps are dropped, since their inner list breaks under tagging. The normal PDF
is the one to print and project; the tagged twin is the one a screen reader can
navigate.

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

## Getting the evidence

`<base>_accessible-report.html` is written beside the tagged PDF on every
accessible build, **whether it passes or fails** — a report naming the clauses a
file broke is the one worth reading. It is the artifact to hand over when
someone asks for proof; some graduate schools now require one filed with a
thesis.

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
