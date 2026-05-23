# `syllabus` — UNR Course Syllabus

A LaTeX class for typesetting course syllabi. The title block, page
header, and contact-info table are all driven by `coursemeta.tex` and
class-local metadata keys, with backward-compat shims for older
syllabi that used command-style metadata (`\instructor{}`, `\email{}`,
…).

## What it gives you

- A clean two-column contact-info block above the body, with rows that
	appear or disappear based on which fields are set.
- A `\syllabussection{Title}` command for policy/info blocks.
- Grade-table helpers: `\gradecategories`, `\gradescale`, `\gradetables`.
- The unified TeXLib build-flag CLI.

---

## Tutorial: a five-minute syllabus

```latex
\documentclass{syllabus}

\meta{
	course-title   = Math 126EE Precalculus I,
	course-section = 1008,
	short-title    = Math 126EE Precalc,        % used in running header
	instructor     = Landon Fox,
	email          = landonf@unr.edu,
	office         = 146F NLLC,
	office-hours   = MWF 10:00--10:50am,
	class-time     = MWF 9:00--9:50am,
	course-room    = AB 206,
}

\begin{document}
\maketitle

\syllabussection{Course Description}
The course covers fundamentals of algebra, polynomial and rational
functions, and complex numbers.

\syllabussection{Grade Scale}
\gradetables{
	Homework & 15\% \\ \hline
	Quizzes  & 10\% \\ \hline
	Exams    & 50\% \\ \hline
	Final    & 25\% \\ \hline
}{
	$A$ & $90 \leq x$       \\ \hline
	$B$ & $80 \leq x < 90$  \\ \hline
	$C$ & $70 \leq x < 80$  \\ \hline
	$D$ & $60 \leq x < 70$  \\ \hline
	$F$ & $x < 60$
}

\end{document}
```

---

## Reference

### Document class

`\documentclass[options]{syllabus}`
Options pass through to `article`. The class pre-declares the
`dvipsnames` option for `xcolor`, so it's safe to load even when other
packages pull `xcolor` in first.

### Class-local metadata keys

| Key               | Notes                                        |
|-------------------|----------------------------------------------|
| `instructor-email`| Instructor email (rendered as a `mailto:`). Legacy alias: `email`. |
| `office`          | Office location                              |
| `office-hours`    | Office hours string                          |
| `organizer`       | Organizer name (for multi-section courses)   |
| `class-time`      | Lecture time                                 |
| `class-time-alt`  | Optional second-line time                    |
| `short-title`     | Used in the page header (defaults to `\GetCourse`) |

Plus all standard `course-metadata` keys: `course-title`, `course-section`,
`institution`, `course-room`, `term`, …

### Backward-compat command-style metadata

For documents that pre-date the metadata refactor, the following
commands still work and forward to `\metasetup`:

```
\coursetitle{...}     \courseshort{...}    \coursesection{...}
\semester{...}        \instructor{...}     \email{...}
\office{...}          \officehours{...}    \classroom{...}
\organizer{...}       \classtime[alt]{main}
```

### Build flags (TeXLib unified CLI)

`\ifsolutions`, `\ifkey`, `\ifrubric`, `\ifdraft`, `\ifstudent`,
`\ifinstructor` and the matching `\ShowSolutions`/`\StudentMode`/
etc. compile-time toggles are defined for consistency. Source toggles:
`\drafts`.

### Commands

`\maketitle`
Renders the title block: course title, section, term, then the
contact-info table inside two horizontal rules.

`\syllabussection{Title}`
Bold-titled paragraph break for a policy or info block. Title is
followed by a period.

`\gradecategories{rows}`
Render a `Category | Total Grade` table. Pass tabular rows separated
by `\\` and `&`.

`\gradescale{rows}`
Render a `Grade Letter | Grade Range (%)` table.

`\gradetables{cats}{scale}`
Render both side by side, centered.

### Predicates

`\IfMetaSet{key}{true}{false}` — from `course-metadata`. Useful in
custom title blocks.
`\IfSyllSet{name}{true}{false}` — class-local; `name` is the
underscored variable name (`class_time`, `office_hours`, …).

### Page layout

- Headers use `fancyplain`: left = `\GetShortTitle`, right =
	`\GetTerm`.
- Center footer: `<page> of <total>`.
- Footnotes use the `\fnsymbol` series.

---

## Tips

- **Title-block fields auto-hide:** if you don't set `email`, the email
	row disappears from the title block. Same for `office`, `office-hours`,
	`class-time`, `organizer`, `course-room`. The branching is implemented
	with `\IfMetaSet` and `\IfSyllSet`.
- **Two-line class times:** use `class-time-alt` for the continuation,
	e.g. `class-time = MWF 9:00am`, `class-time-alt = TTh 9:00--10:15am`.
- **Hyperref colors:** the class loads hyperref with `urlcolor=darkblue`,
	`linkcolor=darkred`. Override in your preamble after `\documentclass`
	if you need different colors.
- **Override `\maketitle`:** if your department has a non-standard
	format, you can `\renewcommand{\maketitle}{...}` after the class
	loads — all metadata getters remain available.

## Related

- `course-metadata.md` — for `course-title`, `course-section`, `term`.
- The class is style-independent of `didactic` and `quiz`, so a
	syllabus does not pull in tcolorbox, exam.cls, etc.
