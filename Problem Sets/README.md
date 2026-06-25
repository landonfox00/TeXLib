# `pset` — Problem-Set / Homework Assignments

A LaTeX class for assignment sheets. Sits between `autoexam` (heavy:
randomized, versioned, problem-bank-driven) and `didactic` (lecture
notes with theorem boxes). Use it for a single-version homework with
inline math, optional definitions/theorems alongside the problems,
and three build modes for the three things you actually do with a
problem set: hand it out, blank-it-out for handwriting, or print the
answer key.

## What it gives you

- A `problem` environment with auto-numbered "Problem N." headings
	and an optional points argument.
- A `parts` environment for sub-parts labeled `(a)`, `(b)`, `(c)`.
- Boxed `theorem`, `definition`, `corollary`, `proposition`, `lemma`,
	`example`, `remark`, `note`, `recall` — same look as `didactic`.
- A `solution` environment with three behaviours:
	- **Default** — body discarded entirely (clean assignment sheet).
	- **`\StudentMode`** — blank watermarked box of configurable height
	for handwriting.
	- **`\ShowKey` or `\ShowSolutions`** — body visible, blue-tinted.
- A `hint` environment that's always visible (yellow-tinted, lighter).
- The unified TeXLib build-flag CLI and metadata-driven title block.

---

## Tutorial: a five-minute problem set

```latex
\documentclass{pset}

\meta{
	pset-number = 3,
	pset-due    = {Friday, May 15, 2026},
}

\begin{document}
\maketitle

\begin{definition}[Continuity]
	A function $f$ is continuous at $a$ if
	$\lim_{x \to a} f(x) = f(a)$.
\end{definition}

\begin{problem}[10]
	Determine whether each function is continuous at the given point.
	\begin{parts}
		\part $f(x) = x^2$ at $a = 1$.
		\part $g(x) = 1/x$ at $a = 0$.
	\end{parts}
\end{problem}

\begin{solution}[3in]
	(a) Continuous: $\lim_{x \to 1} x^2 = 1 = f(1)$.
	\newline
	(b) Not continuous: $g$ is undefined at $0$.
\end{solution}

\begin{problem}[15]
	Use the definition of derivative to compute $f'(x)$ for $f(x) = x^3$.
\end{problem}

\begin{hint}
	Recall the binomial expansion of $(x+h)^3$.
\end{hint}

\begin{solution}[4in]
	$f'(x) = \lim_{h \to 0} \frac{(x+h)^3 - x^3}{h} = 3x^2$.
\end{solution}

\end{document}
```

Build the three artifacts:

```sh
# Hand-out copy (clean, no solutions, no blank space)
lualatex pset3.tex

# Student worksheet (blank space inside each solution box)
lualatex \def\StudentMode{}\input{pset3.tex}

# Answer key (solutions visible)
lualatex \def\ShowKey{}\input{pset3.tex}
```

---

## Reference

### Document class

`\documentclass[options]{pset}`
Options pass through to `article`. Default base size is 11pt.

### Class-local metadata keys

| Key                  | Effect                                                    |
|----------------------|-----------------------------------------------------------|
| `pset-number`        | Used in the title (e.g. "Problem Set 3")                  |
| `pset-title`         | Override the title (defaults to `Problem Set <number>`)   |
| `pset-due`           | Due-date string shown under the title                     |
| `pset-instructions`  | Inline instructions text (boxed); overrides the default file |
| `pset-instructions-file` | Filename (no `.tex`) for instructions, `\input` unboxed and overriding inline; default file `pset-instructions`. Settable course-wide in `coursemeta.tex`. |

Instructions resolve **file > inline > default** (the default wording lives in
`pset-instructions.tex` so it is a SyncTeX inverse-search target), shared with
the other assessment classes via `texlib-instructions`.

The bare alias `due` is also accepted for `pset-due`. (`number` and
`title` are already taken by `didactic`'s legacy aliases, so they are
*not* aliased here — use the `pset-` namespace.)

Plus all `course-metadata` keys — usually set in `coursemeta.tex`.

### Build flags (TeXLib unified CLI)

`\ifsolutions`, `\ifkey`, `\ifrubric`, `\ifdraft`, `\ifstudent`,
`\ifinstructor` and the matching compile-time defines
(`\ShowSolutions`, `\ShowKey`, `\StudentMode`, …). Source toggles
(in the preamble): `\solutions`, `\keys`, `\drafts`, `\studentmode`,
`\instructormode`. All inherited from `texlib-build`.

### Commands

`\maketitle` — emits the title block: title, course/term, optional
"Answer Key" annotation, optional due date, optional Name field
(student mode), boxed instructions paragraph.

`\GetPsetNumber`, `\GetPsetTitle`, `\GetPsetDue`,
`\GetPsetInstructions` — direct getters.

### Environments

#### `problem` — top-level numbered problem

```latex
\begin{problem}[10]                 % optional points argument
	Show that ...
\end{problem}
```

The body opens with `\textbf{Problem N.}` (auto-counted). With
`[points]`, italicized `(N points)` is appended after the heading.

The counter is `problem`; reference it with `\theproblem` and
`\label`/`\ref`.

#### `parts` — sub-parts list

```latex
\begin{parts}
	\part First part.
	\part Second part.
\end{parts}
```

Labels are bold `(a)`, `(b)`, `(c)`, .... Inside the env, `\part` is
locally rebound to `\item` so it doesn't collide with `article.cls`'s
sectioning command.

#### `solution` — gated answer block

```latex
\begin{solution}[<student-blank-height>]
	Answer body, written in the source regardless of mode.
\end{solution>
```

Optional argument is the height of the blank box used in student
mode (default 3cm). Visibility:

| Mode                      | Rendering                                  |
|---------------------------|--------------------------------------------|
| Default (no flag)         | Body discarded entirely (no box)           |
| `\StudentMode`            | Blank box of `<height>`, "Show your work here" watermark |
| `\ShowKey` / `\ShowSolutions` | Body visible, blue-tinted box           |

Implementation note: in default mode the env is overridden by
`\excludecomment{solution}` (from the `comment` package) so the body
is never typeset — no spacing artefacts on the page.

#### `hint` — always-visible nudge

```latex
\begin{hint}
	A small hint, visible to everyone.
\end{hint}
```

Yellow-tinted box, always rendered regardless of build mode. Useful
for problems that need a nudge without giving away the solution.

#### Theorem-likes (boxed via tcolorbox)

`theorem`, `definition`, `corollary`, `proposition`, `lemma` (sharp
black frames); `example`, `remark`, `note`, `recall` (no frame, left
rule only). All share a single counter, numbered `Theorem 1`,
`Definition 2`, etc.

#### `\solution` inside an `example`

Within an `example` (also `example*`) you can mark a worked solution inline
with `\solution`:

```latex
\begin{example}
	Evaluate $\lim_{x \to 3}(2x + 1)$.
	\solution Direct substitution gives $7$.
\end{example}
```

Everything after `\solution` renders with an italic **"Solution."** lead-in
(matching the `\answer` command) and is **always visible** in every build mode —
a worked example's solution is part of the exposition, not a gated answer
(unlike the standalone `solution` box, which
is discarded outside answer-key/student mode). The hook is shared — it lives in
`texlib-thmenv.sty`, so every class with an `example` environment gets it — and
is scoped to the example environment, so the standalone `\begin{solution}` box
keeps `\solution` everywhere else; just don't nest a `\begin{solution}` box
*inside* an example.

### Math utilities

`\mbb`, `\mrm`, `\mcal`, `\msf`, `\mf`, `\mscr`, `\dd`, `\abs`,
`\lrp`, `\lrb`, `\lrcb`, `\deriv[<n>]{<f>}{<x>}`,
`\inte[<lo>][<hi>]{<integrand>}{<x>}`, `\todo`. All
`\providecommand`-defined.

### Page header / footer

| Position           | Content                          |
|--------------------|----------------------------------|
| Header L           | `\GetPsetTitle` (bold)           |
| Header R           | `\GetCourse`                     |
| Footer L           | `\GetTerm`                       |
| Footer C           | `<page> of <total>`              |
| Footer R           | `\GetInstructor`, or "Answer Key" if `\ifkey` |

---

## Tips

- **Three-PDF workflow:** I keep one source `.tex` per problem set and
	build three PDFs from it (hand-out, student worksheet, instructor
	key). The `\StudentMode` and `\ShowKey` flags pick the variant.
- **Heights for blank boxes:** The optional `[<height>]` argument on
	`solution` only matters in student mode. Tune it per-problem so the
	blank box is roomy enough for handwriting but doesn't waste paper
	in the hand-out version (where it's invisible anyway).
- **Embedding a definition before a problem:** the `definition` /
	`theorem` envs share their counter, so a definition before Problem 5
	might be numbered "Definition 3", which is fine — they're a separate
	numbering stream from problems.
- **Long problems with parts:** start `\begin{parts}` on the next
	line after the problem statement; the alphabetical labels render
	cleanly under the bold `Problem N.` heading.
- **Hint vs solution:** hints are for things that should always be
	visible; solutions are gated. If you want a "see hint" reveal,
	use a `solution` instead of a `hint` and rely on `\ShowKey`.

## Related

- `course-metadata.md` — course metadata loaded by every TeXLib class.
- `Notes/README.md` (didactic) — same theorem look, different
	mode-toggling story (student vs instructor based).
- `Exams/README.md` (autoexam) — when you need versions, randomization,
	or a problem bank, reach for autoexam instead.
