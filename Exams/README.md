# `autoexam` — UNR Free-Response Exams

The largest TeXLib class. Builds randomized, multi-version exams from
a problem bank, with synchronized answer keys, optional rubrics, and
per-problem inline-Lua randomization. Handles single-version edits
("just typeset version A", via `\def\Version{A}`) and full
multi-version builds (A, B, C, …) collated into one PDF — which the
Sublime builder then automatically slices into one PDF per version
(and per solutions-state).

## What it gives you

- A `\versions{A, B, C}` declaration (or `\examversions{...}`) that
	drives everything else.
- A problem-bank workflow: `\loadbank{...}`, the `problem` environment
	(`\begin{problem}{id} ... \end{problem}`) for defining problems, and
	`\getproblem{key=val}` / `\problem{id}` for retrieving them.
- Per-version randomization built on a Lua engine: `\setrng`,
	`\calcvar`, `\picklist`, `\pickrange`, `\foreachpick`, with
	`\get`/`\geti`/`\getlist` for retrieval.
- A `solution`/`partsolution` environment pair that renders only when
	building the key — it gates on `\ifsolutions`, which `\ifkey`
	(`\ShowKey`/`\keys`) now implies for this class.
- Smart-columns environment (`problems`) that groups problems into
	TWO-column or FULL-width layouts based on per-problem hints.
- Rubric overlays, common-errors lists, and a scorepage option for
	the final.
- A printable title page assembled from `coursemeta.tex` plus a
	`\examsetup{number=…, date=…, ps=…}` preamble call.

This README is a quick orientation; the class is heavily commented
inline (1,089 lines) and that commentary is the authoritative reference
for edge cases.

---

## Tutorial: a five-minute exam

Using a bank file `bank.tex` and a coursemeta.tex one level up:

```latex
\documentclass{autoexam}

\examversions{A, B, C}

\examsetup{
	number = 5,
	date   = May 2, 2026,
	ps     = {Good luck!},
}

\loadbank{bank.tex}

\begin{document}

\begin{problems}
	\problem{topic=quad, diff=easy}
	\problem{topic=ratineq}
	\problem{topic=graph}
\end{problems}

\end{document}
```

Then build:

```sh
# Single-version edit pass
lualatex \def\Version{A}\input{exam5.tex}

# Full multi-version build (the Sublime builder also slices exam5_A.pdf,
# exam5_B.pdf, ... out of the combined PDF automatically)
lualatex exam5.tex
```

For the answer key, redefine `\ShowKey` (or call `\keys` in source)
and recompile. This builds the instructor **key copies only** (no blank
student copy) — each problem interleaved with its solution, and one key
per version in a multi-version exam. Add `\def\ShowRubric{}` to also
overlay the grading rubrics. To build the blank student copies **and**
the keys together (the fuller production build the Sublime builder then
slices apart), use `\def\ShowSolutions{}` instead.

---

## Reference (high-level)

Refer to the inline comments in `autoexam.cls` for argument-level
details; the class has well-documented comments and is the source of
truth for behavior.

### Document class

`\documentclass[options]{autoexam}`
Options pass through to `exam.cls`. Default base size is 11pt.

### Versions

`\examversions{A, B, C, ...}` (or short alias `\versions{...}`)
Declare the versions. In standalone mode (no `\Version` defined), the
class loops over all versions in one compilation. In builder mode
(`\def\Version{A}` passed externally), only the named version is built.

### Per-exam metadata via `\meta`

Use `\meta{exam-number=…, exam-date=…, exam-postscript=…}` in the
preamble. The legacy `\examsetup{...}` command still works as a
backward-compat alias (it forwards to `\meta` internally).

| Canonical key            | Legacy bare key       | Effect                                       |
|--------------------------|-----------------------|----------------------------------------------|
| `exam-number`            | `number`              | Stored as `\theExamNumber`                   |
| `exam-date`              | `date`                | Stored as `\theExamDate`                     |
| `exam-postscript`        | `ps`                  | Postscript shown on the title page           |
| `points`                 | —                     | Declared point total (default 100); the point-total check warns on mismatch |
| `exam-instructions`      | —                     | Inline instructions text (boxed); overrides the default file |
| `exam-instructions-file` | `instructions-file`   | Filename (no `.tex`) for instructions, `\input` unboxed and overriding inline; default file `autoexam-instructions`. Settable course-wide in `coursemeta.tex`. |

**Exam date from coursemeta.** If `exam-date` is not set on the document,
`autoexam` falls back to the coursemeta `exam<N>-date` key whose number matches
`exam-number` (e.g. `exam-number=3` → `exam3-date`). An explicit local
`exam-date` always wins; with neither, the date shows the `\todo` placeholder.
Set `exam1-date`..`exam5-date` (and `final-date`) once in `coursemeta.tex` to
share them with the syllabus `\examdatetable` — a reschedule is then one edit.

**Point-total check.** At `\begin{document}`, `autoexam` sums the
explicitly-annotated `\problem[pts]` points and warns if they don't match
`points` (default `100`; set `\meta{points=…}` to change). Extra credit
(`\extracredit`) is excluded. Bank problems whose points resolve from the bank
at typeset time (no `[pts]` in the source) can't be seen by the source scan, so
an all-bank exam (source sum 0) is skipped — annotate `\problem[pts]{…}` to
bring a problem into the tally.

Plus all `course-metadata` keys (`course-title`, `course-section`,
`institution`, `term`, …) — set them in `coursemeta.tex` once and
never again.

### Build flags (TeXLib unified CLI)

`\ifsolutions`, `\ifkey`, `\if@autoexam@rubric`, `\if@autoexam@versioned`.

Compile-time toggles: `\ShowSolutions`, `\ShowKey`, `\ShowRubric`,
`\Version{A}`. Source toggles: `\solutions`, `\keys`, `\rubrics`.

Two answer-revealing builds, distinguished by *which* copies they emit:

- `\ShowKey` / `\keys` → **key copies only** (`AutoExamSolMode=only`): the
	instructor copy of each version, with `\ifsolutions` on. An exam's answer
	key IS its instructor copy, so `\ifkey` implies `\ifsolutions`. The cover
	reads "Answer Key".
- `\ShowSolutions` / `\solutions` → **dual** (`AutoExamSolMode=dual`): the
	blank student copies *and* the key copies, collated for the builder to
	slice. The cover reads "Solutions".

`\ShowRubric` / `\rubrics` overlays the grading rubrics on top of either
(rubrics live inside a shown solution, so they need one of the above too).

### Problem bank workflow

`\loadbank{bank.tex}`
Load a problem bank from a file. Equivalent to `\input{bank.tex}` but
tracks load order for diagnostics.

`\begin{problem}{id}[key=val,...] ... \end{problem}`
Define a problem. The body is region-delimited: an optional
`\begin{choices}...\end{choices}` (its presence marks the problem multiple
choice) and an optional `\begin{solution}...\end{solution}`; everything else is
the stem. In a choices block, `\cchoice` marks the correct option, `\fchoice[i]`
forces an always-present option into slot `i` (negative = from the end), and
`[choose=m]` presents only `m` of the options (per version). May sit in the bank
file, the preamble, or the body. Inverse search (double-click in the PDF) jumps
back to the `\begin{problem}` block in its source file.

`\getproblem{query}` (aliases: `\useproblem`, `\reqproblem`)
Retrieve a problem. `query` is either an id (`linear_eq`) or a
`key=val, key=val` list (`topic=algebra, diff=hard`); the latter
randomly picks one matching problem (per version, deterministically).

`\importproblem{file}{id}` — load a single problem from a file.

`\shuffle` (alias `\shufflepages`) / `\byversion{A}{B}{C}` — control
per-version shuffling (problem order + each MC problem's options) and
version-specific content.

### Lua engine: randomization & math

| Command                                  | Purpose                                       |
|------------------------------------------|-----------------------------------------------|
| `\setvar{name}{value}`                   | Store a named value                           |
| `\setrng{name}{min}{max}`                | Random integer in [min, max]                  |
| `\calcvar{name}{lua-expr}`               | Compute from stored vars                      |
| `\get{name}`                             | Typeset a stored value                        |
| `\picklist{name}{n}{a, b, c, ...}`       | Pick `n` items without replacement            |
| `\picklistr{name}{n}{a, b, c, ...}`      | Pick `n` items with replacement               |
| `\pickrange{name}{n}{min}{max}`          | Pick `n` distinct integers from [min, max]    |
| `\pickranger{name}{n}{min}{max}`         | Pick `n` integers from [min, max] (replace)   |
| `\getlist{name}`                         | Typeset all picked values, comma-separated   |
| `\geti{name}{i}`                         | Typeset the i-th picked value                 |
| `\foreachpick[sep]{name}{code}`          | Iterate over picked values (sets `\currentpick`) |

### Solutions, parts, rubrics

`\begin{solution} ... \end{solution}`
Solution body. Visible only in key/solutions builds.

`\begin{partsolution} ... \end{partsolution}`
Per-part solution paired with `\part`.

`\rubric{points}{description}`
Add a rubric line. Rendered as an overlay in rubric builds.

`\begin{commonerrors} ... \end{commonerrors}`
List common student errors; renders only in solutions/key build.

`\ppart`
Insert a part marker compatible with the autoexam shuffler.

### Smart columns

`\begin{problems} ... \end{problems}`
Group problems with smart two-column / full-width layout based on
per-problem `width=` metadata.

`\splitpage{left content}{right content}`
Two-column layout for a single page.

`\qsep`
Insert a problem separator between problems (auto-emitted; rarely
called directly).

### Page layout & title page

`\maketitle` (overridden by the class)
Renders the standardized title page: course/term/instructor block,
exam number/date, version letter (if versioned), the instructions
(file > inline > the default `autoexam-instructions.tex`, via
`texlib-instructions`), and the postscript (if set).

`\blankpage`
Force a blank page between sections.

`\scorepage[questions]`
Add a final scoring page (defaults to 20 questions).

### Tools / inline figures

`\graph[opts]{x-min}{x-max}{y-min}{y-max}{tikz body}`
Inline coordinate plane with axes and a tikz body.

`\workbox{height}`
Reserved blank space for student work.

`\encircle{x}` — circle around a single token (multiple-choice helper).

### Backward-compat aliases

`\theExamNumber`, `\theExamDate`, `\thePS`, `\theCourseNumber`,
`\theCourseTitle`, `\theCourseSection`, `\theSeason`, `\theYear`,
`\theSchool` — all aliased to the modern metadata getters.

---

## Notes & gotchas

- **`enumitem` is intentionally not loaded** — it patches `\list` and
	conflicts with `exam.cls`'s `questions`/`parts` environments.
- **AUX label warnings:** the class redefines `\@newl@bel` and
	`\@testdef` to suppress "multiply defined label" and
	"labels may have changed" oscillations that arise from each version
	rewriting the same `question@N` / `part@N@M` labels.
- **Problem engine:** `problem_engine.lua` lives at the TeXLib root
	(shared with `quiz.cls`). The class locates it via a small kpse +
	relative-path search inside its `\directlua{dofile(...)}` loader, so
	the file can also sit next to the class or alongside the .tex being
	built.
- **Normal build vs. forced single version:** a normal compile (no
	`\Version` defined) loops over every declared version in one compile,
	producing a combined PDF that the Sublime builder then slices into
	`<jobname>_A.pdf`, `<jobname>_B.pdf`, ... afterward. Passing
	`\def\Version{X}` externally (or on a raw command line) forces only
	that one version to build.
- **Filenames the builder produces:** `<jobname>_A.sco`,
	`<jobname>_autoexam_body_A.tex`, `<jobname>.srcmap`,
	`<jobname>.vmap`, etc. — these are intermediate artifacts you can
	ignore between rebuilds.

## Related

- `course-metadata.md` — the metadata layer.
- The Lua engine: `problem_engine.lua` (heavily commented in-source).
- The `exam.cls` documentation (CTAN) for the `questions`/`parts`/
	`points` machinery the class builds on.
