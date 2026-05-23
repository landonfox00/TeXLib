# `quiz` — UNR In-Class Quiz

A subclass of `exam.cls` for in-class, pencil-and-paper quizzes.
Header, footer, and title are all driven by `coursemeta.tex` plus a
`quiz-number` you set per quiz.

## What it gives you

- A metadata-driven first-page header (course on the left, "Name"
	blank on the right) and running header on subsequent pages.
- A `\maketitle` that prints a "Quiz N" banner with a boxed
	instructions paragraph (or your own override).
- The full `exam.cls` `questions` / `parts` machinery.
- A starred-style theorem environment library (`thm*`, `defn*`,
	`prop*`, `rmk*`, …) for math content embedded in problems.
- Backward-compat aliases (`\theQuizNumber`, `\theCourseTitle`, …)
	for older quizzes that overrode them with `\renewcommand`.

---

## Tutorial: a five-minute quiz

```latex
\documentclass{quiz}

\meta{ quiz-number = 1 }

\begin{document}
\maketitle

\begin{questions}

\question Evaluate.
	\begin{parts}
		\part[3] $\displaystyle 3 \cdot (-2)^2 + 5 \cdot 4 - 3 \cdot 3^2$
			\vspace{\stretch{1}}
		\part[3] $\displaystyle (4-1)^2 + 2 \cdot 5$
			\vspace{\stretch{1}}
	\end{parts}

\question Solve $2x + 5 = 11$ for $x$.
	\vspace{\stretch{1}}

\end{questions}
\end{document}
```

---

## Reference

### Document class

`\documentclass[options]{quiz}`
Options pass through to `exam.cls`. Default base size is 11pt.

### Class-local metadata keys

| Key                       | Effect                                          |
|---------------------------|-------------------------------------------------|
| `quiz-number`             | Used in the title block (e.g. "Quiz 1")         |
| `quiz-title`              | Override the title (defaults to `Quiz <number>`) |
| `quiz-instructions`       | Override the boxed instructions paragraph (inline) |
| `quiz-instructions-file`  | `\input` the named file instead of the boxed inline string. Filename is given without `.tex`. If both `quiz-instructions` and `quiz-instructions-file` are set, the file wins. |

Plus all `course-metadata` keys (institution, course-*, term, …).

### Problem bank API (shared with autoexam)

`quiz.cls` loads `autoexam_engine.lua` so quizzes can use the same
problem-bank workflow as exams. This means you can author one bank
file that's reusable across quizzes and exams.

`\loadbank{path}` — explicitly load a problem bank file. Inside, you
typically have a sequence of `\newproblem{...}` or `\begin{problem}`
calls.

`\newproblem{id}{key=val,...}{content}[solution]` — define a problem
in the database. The solution argument is optional. Example:

```latex
\newproblem{linear_eq}{topic=algebra, diff=easy}{
	Solve $2x + 5 = 11$ for $x$.
}[$x = 3$]
```

`\begin{problem}{id}[key=val,...] ... \solution ... \end{problem}`
— environment-style definition. Body before `\solution` is the
problem content; body after is the solution. Useful for multi-line
problems with embedded code or display math.

`\getproblem{query}` — retrieve a problem and typeset it. The query
is either a plain id (`linear_eq`) or a key=value filter
(`topic=algebra, diff=hard`); for the latter, one matching problem
is picked at random per build.

```latex
\begin{questions}
	\question \getproblem{linear_eq}
	\question \getproblem{topic=algebra}
\end{questions}
```

Aliases: `\useproblem`, `\reqproblem`.

#### Lua helpers (also available)

The Lua engine exposes randomization helpers — they work without
needing `\versions` (which doesn't exist in `quiz.cls`):

| Command                                   | Purpose                              |
|-------------------------------------------|--------------------------------------|
| `\setvar{name}{value}`                    | Store a value                        |
| `\setrng{name}{min}{max}`                 | Random integer in [min, max]         |
| `\calcvar{name}{lua-expr}`                | Compute from stored vars             |
| `\get{name}`                              | Typeset a stored value               |
| `\picklist{name}{n}{a, b, c, ...}`        | Pick `n` items without replacement   |
| `\pickrange{name}{n}{min}{max}`           | Pick `n` distinct integers from [min, max] |
| `\getlist{name}`                          | Typeset all picked values            |
| `\geti{name}{i}`                          | Typeset the i-th picked value        |

These are useful for quizzes you want to re-use across semesters with
slightly different numbers — set the seed once, regenerate, print.

### Build flags (TeXLib unified CLI)

`\ifsolutions`, `\ifkey`, `\ifrubric`, `\ifdraft`, `\ifstudent`,
`\ifinstructor` and the matching compile-time defines. The `\ifkey`
flag adds an "Answer Key" annotation under the title.

### Commands

`\maketitle`
Emits `Quiz <number>` (or your `quiz-title`) followed by a boxed
instructions paragraph. The default instructions read:

> Notes or other aids are not allowed. Calculators of any kind are
> not permitted. To receive full credit, you must show all of your
> work. Write your answers in the space provided, and box or circle
> all final answers.

Override by setting `quiz-instructions = {...}` in `\meta`.

`\GetQuizNumber`, `\GetQuizTitle`, `\GetQuizInstructions`
Direct getters for the metadata.

`\questionlabel` / `\partlabel`
Renumbered to bold arabic and bold alpha respectively (override of
the exam.cls defaults).

`\encircle{x}`
Tiny utility: places a circled letter, useful for multiple-choice.

`\extracredit[<points>]{<text>}`
Add an extra-credit question. Without a points argument, just labels
"Extra Credit"; with one, includes the points.

`\fig[<options>]{<filename>}`
Wraps `\includegraphics` with sensible defaults (50% width, keep
aspect ratio) under `Figures/<filename>`.

### Theorem environments

The class predefines starred theorem-like envs for embedding small
mathematical statements inside problems:

`thm*`, `defn*`, `cor*`, `prop*`, `lem*`, `conj*`, `ques*`, `prob*`,
`exam*`, `notn*`, `rmk*`, `recall*`, `case*`, `desiderata*`.

These are unnumbered (the `*` form). Use the regular `questions` /
`parts` for the quiz problems themselves.

### Math utilities

The same `\mbb` / `\mrm` / `\mcal` / `\dd` / `\abs` / `\lrp` / `\lrb` /
`\lrcb` / `\deriv` / `\inte` / `\todo` are available as `\providecommand`s.

### Page header / footer

| Position           | Content                          |
|--------------------|----------------------------------|
| First-page header  | left: `\GetCourse` · right: `Name: ___` |
| Running header     | same                             |
| First-page footer  | left: `Section <n>` · right: `\GetInstitution` |
| Running footer     | same                             |

### Backward-compat aliases

For quizzes ported from the older non-class workflow, the following
`\the…` macros still resolve correctly:

```
\theQuizNumber  \theTitle       \theCourseNumber  \theCourseTitle
\theCourse      \theCourseSection \theSeason      \theYear
\theTerm        \theSchool
```

They are `\providecommand`-defined as expandable forwards to the new
metadata getters; `\renewcommand` overrides in legacy files continue
to work.

---

## Tips

- **No enumitem.** `enumitem` is intentionally not loaded — it
	conflicts with `exam.cls`'s redefinition of `\list`. If you need
	fancy lists for a specific quiz, load `enumitem` locally in that
	quiz's preamble (`\usepackage{enumitem}` before `\begin{document}`)
	but be aware you may break `questions`/`parts`.
- **Vertical spacing for handwritten answers:** use
	`\vspace{\stretch{1}}` between parts, then `\newpage` between
	questions if needed. The exam class autospaces nicely; tune as
	needed per quiz.
- **Multi-page quiz:** the running header continues across pages.
- **Override the instructions for special quizzes:** set
	`quiz-instructions = {Open-book quiz; calculators allowed.}`.
	For longer or richly-formatted instructions, put them in their own
	`.tex` file and reference it with
	`quiz-instructions-file = my-instructions` (no `.tex` extension).
- **Sharing a bank with autoexam:** the bank file format is identical.
	The same `bank.tex` can be `\loadbank`'d by both `quiz.cls` and
	`autoexam.cls`; only the *retrieval* differs (quiz uses
	`\question \getproblem{...}` inside `questions`; autoexam uses
	`\begin{problems}` with `\getproblem` directly).

## Related

- `course-metadata.md` — for the course-level metadata.
- The `exam.cls` documentation (CTAN) for the full `questions` /
	`parts` API.
