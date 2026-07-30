# `didactic` — UNR Lecture Notes

A LaTeX class for math lecture notes. Builds either an instructor copy
(solutions visible) or a student copy (solutions blanked out, replaced
with watermarked space) from the same source file.

## What it gives you

- A consistent header/footer driven by your `coursemeta.tex`.
- Boxed theorem/definition/example/etc. environments via tcolorbox.
- A `solution` environment that adapts to student vs. instructor mode.
- The unified TeXLib build-flag CLI (`\ifsolutions`, `\ifstudent`,
	`\ShowSolutions`, …).

---

## Tutorial: a five-minute lecture note

Make a coursemeta file once at your course root (you only do this once
per course):

```latex
% Math 126EE/Spring 26/coursemeta.tex
\metasetup{
	institution    = {University of Nevada, Reno},
	instructor     = Landon Fox,
	season         = Spring, year = 2026,
	course-subject = Math, course-number = 126EE,
	course-title   = Precalculus I,
	course-section = 1008,
}
```

Now write a lecture in any descendant directory:

```latex
% Math 126EE/Spring 26/Lecture Notes/Unit 1/lecture01.tex
\documentclass{didactic}

\meta{
	unit     = Lecture,
	number   = 1,
	title    = Real Numbers and Order of Operations,
	overview = {We classify the number sets and review order of operations.},
}

\begin{document}
\maketitle

\begin{definition}[Rational number]
	A real number that can be written as $p/q$ for integers $p, q$ with $q \neq 0$.
\end{definition}

\begin{example}
	Express $0.\overline{3}$ as a fraction.
\end{example}

\begin{solution}[2in]
	$0.\overline{3} = 1/3$.
\end{solution}

\end{document}
```

Compile twice to render two versions:

```sh
lualatex --jobname=lecture01_Instructor lecture01.tex
lualatex --jobname=lecture01_Student    lecture01.tex
```

The `solution` environment automatically blanks out for the Student
version (using the watermark "Space for Notes") and renders the
solution body for the Instructor version. The class detects the variant
from the jobname.

---

## Reference

### Document class

`\documentclass[options]{didactic}`
Options are passed through to `article`.

### Metadata keys (set via `\meta{...}`)

| Key             | Effect                                           |
|-----------------|--------------------------------------------------|
| `unit`          | Type label, e.g. "Lecture", "Unit", "Section"    |
| `unit-number`   | Unit/lecture number                              |
| `unit-title`    | Title of this document                           |
| `unit-overview` | Optional abstract; rendered after `\maketitle`   |

The bare aliases `number`, `title`, `overview` continue to work for
backward compatibility — they point at the same storage as the
namespaced names above.

| Key (legacy)    | Effect                                           |
|-----------------|--------------------------------------------------|
| `solutions`= true | force solutions visible (same as `\solutions`) |
| `student` = true  | force student mode                       |
| `instructor` = true | force instructor mode                  |
| `draft`   = true  | enable draft markup                      |

All `course-metadata` keys (institution, term, course-*, lecture-*) are
also accepted but are usually set in `coursemeta.tex`.

### Build flags (TeXLib unified CLI)

Compile-time:

```sh
lualatex \def\ShowSolutions{}\input{file.tex}
lualatex \def\ShowDraft{}\input{file.tex}
lualatex \def\StudentMode{}\input{file.tex}
lualatex \def\InstructorMode{}\input{file.tex}
```

The class additionally inspects `\jobname`: a jobname containing
"Student" sets `\studenttrue`; one containing "Instructor" sets
`\instructortrue`. When neither student nor instructor mode is set,
**instructor** is the default (so `solution` bodies are visible).

Source-level toggles (place in preamble): `\solutions`, `\drafts`,
`\studentmode`, `\instructormode`.

### Commands

`\maketitle` — typesets the title block (unit title + course + term).
If `overview` is set, an abstract follows.

`\GetUnitTitle` — expands to "Lecture 1: Real Numbers" or just the
title if `number` is empty.

`\GetUnitType` / `\GetUnitNumber` / `\GetOverview` — direct getters.

### Environments

#### Theorem-style (boxed)

`theorem`, `definition`, `corollary`, `proposition`, `lemma`,
`conjecture`, `procedure`, `challenge` — all share a numbering
counter, all rendered with sharp-corner tcolorbox frames.

#### Remark-style

`example` (left rule only, lighter visual), `remark`, `note`, `question`,
`recall` — share the theorem counter, less visually heavy.

#### `solution`

`\begin{solution}[<height>] ... \end{solution}` (optional argument is
target height for blank student boxes, default 3cm).

Behavior:

| Mode                        | Rendering                                  |
|-----------------------------|--------------------------------------------|
| `\ifsolutions` (forced on)  | Body visible, blue tint                    |
| Instructor (default)        | Body visible, blue tint                    |
| Student                     | Blank box of `<height>`, "Space for Notes" |

#### Inline lead-ins `\solution` / `\answer` / `\ans` / `\pf`

Inside any worked-shaped environment — `example`, `question`, `exercise`,
`challenge` (and their `*` twins / aliases) — you can mark a worked solution,
answer, or proof inline with a one-word lead-in:

```latex
\begin{example}
	Evaluate $\lim_{x \to 3}(2x + 1)$.
	\solution Direct substitution gives $7$.
\end{example}

\begin{challenge}
	Show $\sqrt{2}$ is irrational.
	\solution Suppose $\sqrt{2} = p/q$ in lowest terms; then …
\end{challenge}
```

Each renders an italic **"Solution."** / **"Answer."** / **"Proof."** lead-in,
then the text continues inline. **Visibility depends on the environment:**

| Environment            | Inline lead-in visibility                              |
|------------------------|--------------------------------------------------------|
| `example`, `question`  | **Always visible** — it is exposition / a shown prompt |
| `challenge`, `exercise`| **Gated** — shown in the instructor build, discarded from the student handout (no solution ships) |

So a worked `example` reads the same for everyone, while a `challenge`
statement stays a bare prompt for students but carries its worked solution in
your instructor build. Turn the gating off globally with `\gateworkedfalse`
(then all four envs are always-visible).

The always-visible half of the hook is shared (it lives in `texlib-thmenv.sty`,
so every class with these environments gets it); the challenge/exercise gating
is added by `didactic.cls`. Each lead-in is scoped to its environment, so the
standalone `\begin{solution}` box keeps `\solution` everywhere else — just don't
nest a `\begin{solution}` box *inside* one of these environments.

#### `{answer}` — the solution box, relabelled

`\begin{answer}` is the same gated box as `\begin{solution}` with an "Answer."
header and a shorter default height — use it for a short-answer key that still
wants student write-space. `{ans}` and `{soln}` are aliases. All accept the
force-show star (`\begin{answer}*`) and obey `\gatesolutionfalse` (make every
box always-visible).

### Math utilities

The class predefines: `\mbb`, `\mrm`, `\mcal`, `\msf`, `\mf`, `\mscr`,
`\dd`, `\abs`, `\lrp`, `\lrb`, `\lrcb`, `\deriv[<n>]{<f>}{<x>}`,
`\inte[<lo>][<hi>]{<integrand>}{<x>}`, `\todo`. They are all
`\providecommand`-defined, so your own preamble can override them.

---

## Tips

- **Where to put `\maketitle`:** right after `\begin{document}`. Headers
	rely on `\GetUnitTitle` so the title block must run before any
	`\thispagestyle{fancy}` page breaks.
- **Section TOC width:** the class sets `\cftsecnumwidth=3em` to keep
	long section labels (like "R.10") from colliding with their titles in
	the auto-generated TOC.
- **Loading enumitem:** `enumitem` is loaded with `[shortlabels]` so
	you can write `\begin{enumerate}[(a)]` without extra setup.

## Related

- `course-metadata.md` — the metadata engine.
- The `solution` env relies on tcolorbox; loading additional tcolorbox
	libraries is fine, but don't redefine the `didacticstyle` style.
