# Accessibility

TeXLib produces **tagged, PDF/UA-2 conformant** PDFs, and proves it on every
build rather than claiming it.

This document is written to be checkable. Where it makes a claim, it says how
that claim is enforced and where the enforcement lives, because "accessible" is
invisible in a rendered page and an unverifiable assertion about it is worth
nothing.

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

The pair is deliberate rather than a replacement. Turning tagging on costs real
visual fidelity — `tcolorbox` theorem wraps are dropped, because their inner
list breaks under tagging — so the normal PDF stays the one you print and
project, and the tagged twin is the one a screen reader can navigate. A single
"accessible mode" that quietly degraded your lecture notes would get switched
off, and then nothing would be accessible.

## How the claim is enforced

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
- **No vacuous green.** If veraPDF is absent the gate fails rather than
  skipping. A soft skip on a missing validator is indistinguishable from a pass,
  and that failure mode has bitten this repo before.

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

## Limitations, stated plainly

An accessibility document that lists only strengths is marketing. These are the
real gaps.

**Mathematics tagging is split across two methods, and readers disagree.**
MathML can be attached as associated files (AF), which Firefox's viewer and
Foxit read — the in-browser path from an LMS link — or as structure elements
(SE), which Adobe Acrobat reads. Emitting both is what covers a class of
readers; emitting one silently flattens the mathematics for the other half.
Which methods are emitted is declared in exactly one place,
`ACCESSIBLE_DOCMETA` in [`Sublime/texlib/texlib_buildspec.py`](Sublime/texlib/texlib_buildspec.py)
— read it there rather than trusting this paragraph, because the answer has
changed under a toolchain bug and may change back. At the time of writing, SE
emission is constrained by a `luamml` defect that aborts the run outright on two
`\sqrt[n]{...}` in a single formula; the constraint is a workaround for someone
else's bug, not a design choice, and it is documented at the declaration.

**A better checker score is not better accessibility.** TeXLib deliberately does
**not** set `\tagpdfsetup{math/alt/use}`. It raises the number an Ally- or
UDOIT-style checker reports, and it does so by replacing the real MathML with
flat alt text that hides the actual markup from screen readers. That trade is
available to anyone who wants it and TeXLib will not make it for you.

**Tagging changes what LaTeX accepts.** Under `tagging=on`:

- Inline list keys are fatal. `\begin{itemize}[leftmargin=*]` fails with
  "Some keys specified on the enumerate environment are unknown". Declare list
  formatting with `\setlist` in the preamble instead, which is honoured.
- `cleveref` is fatal — its `amsthm` patch leaves a block-level list open and
  the first definition-style environment dies. TeXLib routes `\cref` through
  `texlib-crossref.sty`, which uses cleveref normally and `zref-clever` in an
  accessible build. If you load cleveref yourself, you will hit this.

**Conformance is a floor, not a ceiling.** PDF/UA-2 conformance means the
structure is machine-checkable and correct. It does not mean your alt text is
good, your colour contrast is adequate, or your tables are comprehensible. Those
are yours.

## Why this exists

The US Department of Justice's Title II rule sets compliance deadlines for
public entities' web content and mobile apps, falling in 2026 and 2027 depending
on the entity's size. Course materials distributed through an LMS are in scope,
and a PDF is the format most likely to fail. Consult the rule and your
institution's own guidance for the date that applies to you — this file is not
legal advice and the deadline is not the reason to do it.

The reason to do it is that a student using a screen reader currently gets, from
a typical LaTeX handout, an unnavigable wall of text with the mathematics
rendered as gibberish or omitted entirely. The machinery to fix that exists in
the LaTeX kernel now. Most of the work is in knowing which parts break, which is
what this library encodes.

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
