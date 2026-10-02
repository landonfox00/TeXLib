# `autoexam` — UNR free-response exams

The largest TeXLib class. Builds randomized, multi-version exams from a problem bank, with synchronized answer keys, optional rubrics, and per-problem inline-Lua randomization. Handles single-version edits (typeset only version A, via `\def\Version{A}`) and full multi-version builds (A, B, C, …) collated into one PDF — which the Sublime builder then automatically slices into one PDF per version (and per solutions-state).

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

Using a bank file `bank.tex` and a `coursemeta.tex` one level up:

```latex
\documentclass{autoexam}

\examversions{A, B, C}

\examsetup{
	number = 5,
	date   = May 2, 2026,
	ps     = {Good luck!},
}

\loadbank{problem-bank.tex}

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

**Exam date from coursemeta.** If `exam-date` is not set on the document, `autoexam` falls back to the coursemeta `exam<N>-date` key whose number matches `exam-number` (for example, `exam-number=3` → `exam3-date`). An explicit local `exam-date` always wins; with neither, the date shows the `\todo` placeholder. Set `exam1-date`..`exam5-date` (and `final-date`) once in `coursemeta.tex` to share them with the syllabus `\examdatetable` — a reschedule is then one edit.

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

- `\ShowKey` / `\keys` (build mode `solutions`) → **key copies only**
	(`AutoExamSolMode=only`): the answer-bearing copy of each version, with
	`\ifsolutions` on. An exam's answer key IS its worked copy, so `\ifkey`
	implies `\ifsolutions`. The cover reads "Solutions".
- `\ShowSolutions` / `\solutions` (build mode `instructor`, which also defines
	`\InstructorMode` and `\ShowRubric`) → **dual** (`AutoExamSolMode=dual`):
	the blank student copies *and* the answer copies, collated for the builder
	to slice. The cover reads "Instructor Version".

The cover word is keyed on `\ifinstructor`, not `\ifkey`: after the 0.8.0
rename the student-facing key is the `solutions` build, so labelling it
"Answer Key" while the instructor copy said "Solutions" had the two backwards.

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
the stem. In a choices block, `\cchoice` marks a correct option, `\fchoice[i]`
forces an always-present option into slot `i` (negative = from the end), and
`[choose=m]` presents only `m` of the options (per version). May sit in the bank
file, the preamble, or the body. Inverse search (double-click in the PDF) jumps
back to the `\begin{problem}` block in its source file.

`\cchoice` is repeatable — mark every option that is right (equivalent forms,
"select all that apply") and the key reports them together as `Answer: B, D`.
`\cchoiceif{lua-expr}` makes an option correct only when the expression holds at
typeset time, so the answer can follow the problem's own random draw:

```latex
\begin{problem}{slope-sign}
    \setrng{a}{-6}{6}
    Let $f(x) = \get{a}x + 1$. On $(-\infty,\infty)$, $f$ is:
    \begin{choices}
        \cchoiceif{a > 0} increasing
        \cchoiceif{a < 0} decreasing
        \cchoiceif{a == 0} constant
    \end{choices}
\end{problem}
```

Conditional options are always presented, so `\shuffle` can never drop the live
answer. The expression sees the same sandbox as `\calcvar` (the `math` library
plus every stored variable); note Lua truthiness, where `0` is true, so compare
explicitly. `\ifvar{lua-expr}{then}{else}` branches ordinary prose on the same
values and works anywhere in a stem, a part, or a `{solution}`.

`\getproblem{query}` (aliases: `\useproblem`, `\reqproblem`)
Retrieve a problem. `query` is either an id (`linear_eq`) or a
`key=val, key=val` list (`topic=algebra, diff=hard`); the latter
randomly picks one matching problem (per version, deterministically).

`\importproblem{file}{id}` — load a single problem from a file.

`\shuffle` / `\byversion{A}{B}{C}` — control
per-version shuffling (problem order + each MC problem's options) and
version-specific content.

### Lua engine: randomization & math

| Command                                  | Purpose                                       |
|------------------------------------------|-----------------------------------------------|
| `\setvar{name}{value}`                   | Store a named value                           |
| `\setrng{name}{min}{max}`                | Random integer in [min, max]                  |
| `\calcvar{name}{lua-expr}`               | Compute from stored vars                      |
| `\get{name}`                             | Typeset a stored value                        |
| `\ifvar{lua-expr}{then}{else}`           | Branch on the current draw                    |
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

`\texlibpartsolheader`
The header a `{partsolution}` prints, `\texlibsolheader` ("Solution.") by
default. `\renewcommand{\texlibpartsolheader}{}` in the preamble removes it from
part solutions and leaves `{solution}`'s in place; use it when a page of short
part answers runs a key onto an extra page.

`\keylayout{inline}` (preamble)
Lay this document's keys out on the student copy's page. The answer space
stays and each solution is drawn into it, so a key page is the student page
with the answers showing: same pagination, every problem where the student
copy prints it. It applies to every answer-bearing copy the builder makes
(`<base>_solutions.pdf`, the per-version `_solutions` slices, `_instructor`).
The plain build is still the student copy.

The tagged twin of a key (`<base>_solutions_accessible.pdf`) keeps the compact
layout. It is read through its structure, where position on the page carries
nothing, and the inline layout costs it conformance: a key of whole-problem
solutions passes PDF/UA-2 compact and fails four Table 5 rules inline.

Where a solution is taller than the blank it is drawn into, the space after it
grows to hold it and the page's other answer spaces give that up in proportion
to their stretch. The page height does not change, and a page on which every
solution fits is left exactly as the student copy. The log records each page
where room was made (`made room for N tall solution(s)`).

A page whose solutions cannot fit at all, however the space is shared, is split:
what fits stays, the rest continues on one added page, and the pages after it
keep their contents. A part is never separated from its own answer. The key is
then a page longer than the student copy, and the build says so:

```
Package texlib-solutions Warning: Page 3 cannot hold its solutions:
(texlib-solutions)                they need 41.5pt more room than it has;
(texlib-solutions)                the key continues on an added page.
```

To get that key back onto the student copy's pages, give the page the room it is
short of: a larger stretch on the `\problem` line, a smaller figure, or one
problem fewer on that page. `TEXLIB_KEYFIT_TRACE=1` in the environment writes
the page as the fit read it to the log, one line per item, in points.

`\keylayout{compact}` is the default: the answer space closes and the solutions
flow, which is what a review sheet with no work space wants.

`\rubric{points}{description}`
Add a rubric line. Rendered as an overlay in rubric builds.

`\begin{commonerrors} ... \end{commonerrors}`
List common student errors; renders only in solutions/key build.

`\ppart`
Insert a part marker compatible with the autoexam shuffler.

`\TeXLibMCKeyStacked` (preamble)
Make multiple-choice answer keys **inverse-searchable**. By default a shown MC
`{solution}` sits in a compact minipage *beside* the choices ("four keys per
page" packing), but that side-by-side box hides the solution from SyncTeX
reverse search — double-clicking it in the PDF won't jump to the bank source.
Put `\TeXLibMCKeyStacked` in the preamble to render the MC solution *stacked*
beneath the choices instead; it stays reachable, so inverse search lands on the
`\begin{solution}` in the bank. The trade-off is vertical space (fewer keys per
page). Affects only shown MC solutions (`\ifsolutions`); the free-response
solution box is inverse-searchable in both layouts.

### Smart columns

`\begin{problems} ... \end{problems}`
Group problems with smart two-column / full-width layout based on
per-problem `width=` metadata.

`\splitpage{left content}{right content}`
Two-column layout for a single page. Part lettering continues across the
split — the left column is (a), (b) and the right carries on as (c), (d).
Question-level: do not nest it inside an existing `{parts}`.

`\begin{cols}[n] ... \end{cols}`
Set a problem's parts in `n` columns (default 2), inside a problem body.
**`{cols}` goes on the OUTSIDE and `{parts}` inside it:**

```latex
\begin{cols}
    \begin{parts}
        \part[2] ...
        \part[2] ...
    \end{parts}
\end{cols}
```

The nesting order matters and the failures are quiet. Inverted — `{parts}`
outside, `{cols}` in — the build dies with "missing `\item`". Used with bare
`\ppart` and no inner `{parts}` at all, every item is silently dropped and
the PDF still builds clean. In an accessible build `{cols}` drops to a single
column (multicol cannot be tagged); the parts and their labels survive, only
the two-up layout is lost.

> **Never use `{cols}` in a problem that lives in a shared bank.** `cols` is
> defined by `autoexam.cls` **only** — `quiz.cls` does not have it. A bank
> fragment is loaded by both classes, so a problem using `{cols}` works in an
> exam and explodes the moment a quiz draws it. Use plain `{parts}` in bank
> problems; every bank problem has to work from both classes. `{cols}` is for
> problems written directly in an exam document.

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

`\begin{sketchaxes}[scale]{x-min}{x-max}{y-min}{y-max} ... \end{sketchaxes}`
The grid a graphing problem is answered on. The body is TikZ, in grid units,
that draws the answer:

```latex
\ppart Graph $f$.
    \begin{sketchaxes}[0.62]{-5}{5}{-5}{5}
        \begin{scope}
            \clip \sketchwindow;
            \draw[blue, very thick, domain=-5:5] plot (\x, {(\x)^2 - 2});
        \end{scope}
        \fill[blue] (0,-2) circle (2.6pt);
    \end{sketchaxes}
    \begin{partsolution}
        Vertex $(0, -2)$, opening upward.
    \end{partsolution}
```

A student copy prints the blank grid. A copy that shows solutions prints the same
grid with the body drawn on it, so the key keeps the student copy's pagination.
`\sketchwindow` is the grid's rectangle. The optional argument is the TikZ scale
(default `0.7`); the starred form drops the y tick labels; an empty body is a
grid that prints blank in every copy. Defined in `texlib-problembank.sty`, so it
works from a quiz and from lecture notes as well.

Do not also draw the answer's grid inside `{partsolution}`: the key then prints
two grids, and the second is what pushes the problem onto another page.

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
- **Filenames the builder produces:** `<jobname>_A.sco`, `<jobname>_autoexam_body_A.tex`, `<jobname>.srcmap`, `<jobname>.vmap`, and similar — these are intermediate artifacts you can ignore between rebuilds.

## Related

- `course-metadata.md` — the metadata layer.
- The Lua engine: `problem_engine.lua` (heavily commented in-source).
- The `exam.cls` documentation (CTAN) for the `questions`/`parts`/
	`points` machinery the class builds on.
