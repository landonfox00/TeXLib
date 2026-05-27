# `autoexam` — UNR Free-Response Exams

The largest TeXLib class. Builds randomized, multi-version exams from
a problem bank, with synchronized answer keys, optional rubrics, and
per-problem inline-Lua randomization. Handles single-version edits
("just typeset version A") and full multi-version builds (A, B, C,
…) collated into one PDF, depending on whether the Python builder is
calling it.

## What it gives you

- A `\versions{A, B, C}` declaration (or `\examversions{...}`) that
	drives everything else.
- A problem-bank workflow: `\loadbank{...}`, `\newproblem{...}`,
	`\getproblem{key=val}`, plus a `problem` environment for inline
	definition of multi-line problems.
- Per-version randomization built on a Lua engine: `\setrng`,
	`\calcvar`, `\picklist`, `\pickrange`, `\foreachpick`, with
	`\get`/`\geti`/`\getlist` for retrieval.
- A `solution`/`partsolution` environment pair that gates visibility
	on `\ifsolutions`/`\ifkey` and renders only when building the key.
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

# Or let Python builder cycle through versions and collate
python3 build_exam.py exam5.tex
```

For the answer key, redefine `\ShowKey` (or call `\keys` in source)
and recompile to get a key version that interleaves problem statements
with their solutions and rubrics.

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
| `exam-instructions-file` | `instructions-file`   | Filename for boxed instructions (default `autoexam-instructions`) |

Plus all `course-metadata` keys (`course-title`, `course-section`,
`institution`, `term`, …) — set them in `coursemeta.tex` once and
never again.

### Build flags (TeXLib unified CLI)

`\ifsolutions`, `\ifkey`, `\if@autoexam@rubric`, `\if@autoexam@versioned`.

Compile-time toggles: `\ShowSolutions`, `\ShowKey`, `\ShowRubric`,
`\Version{A}`. Source toggles: `\solutions`, `\keys`, `\rubrics`.

### Problem bank workflow

`\loadbank{bank.tex}`
Load a problem bank from a file. Equivalent to `\input{bank.tex}` but
tracks load order for diagnostics.

`\newproblem{id}{key=val,...}{content}[solution]`
Define a problem. Square-bracket solution is optional. Calls may sit
in the bank file, in the document preamble, or in the body.

`\dupproblem{id}{key=val,...}{content}{solution}` (deprecated)
Same as `\newproblem` but with mandatory solution argument.

`\begin{problem}{id}[key=val,...] ... \solution ... \end{problem}`
Multi-line / environment-style problem definition. Body text before
`\solution` is the problem; text after is the solution.

`\getproblem{query}` (aliases: `\useproblem`, `\reqproblem`)
Retrieve a problem. `query` is either an id (`linear_eq`) or a
`key=val, key=val` list (`topic=algebra, diff=hard`); the latter
randomly picks one matching problem (per version, deterministically).

`\importproblem{file}{id}` — load a single problem from a file.

`\shufflepages` / `\byversion{A}{B}{C}` — control per-version page
shuffling and version-specific content.

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
exam number/date, version letter (if versioned), instructions box
(loaded from `\@autoexam@instructions@file`), and the postscript
(if set).

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
- **Builder mode vs. standalone mode:** the Python builder watches for
	the `examversions` declaration via regex, then invokes lualatex
	per-version with `\def\Version{X}`. Standalone mode (no builder)
	loops over all versions in one compile.
- **Filenames the builder produces:** `<jobname>_A.sco`,
	`<jobname>_autoexam_body_A.tex`, `<jobname>.srcmap`, etc. — these
	are intermediate artifacts you can ignore between rebuilds.

## Related

- `course-metadata.md` — the metadata layer.
- The Lua engine: `problem_engine.lua` (heavily commented in-source).
- The `exam.cls` documentation (CTAN) for the `questions`/`parts`/
	`points` machinery the class builds on.
