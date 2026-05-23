# `schedule` — UNR Course Schedule

Generates a one-page (or landscape multi-row) tentative-schedule grid
for a course. The grid is computed at compile time from your start/end
dates, lecture days, recitation/quiz days, and a sequence of section
declarations — no manual day-by-day data entry.

## What it gives you

- A `schedule` environment that does the date arithmetic and renders
	the calendar grid.
- High-level directives: `\section`, `\topic`, `\holiday`, `\quiz`,
	`\noquiz`, `\examreview`, `\exam`, `\finalreview`, `\finalsweek`,
	`\winterbreak`, `\note`, `\syllabus`, `\debugdate`.
- Auto-fed by `coursemeta.tex`: start/end dates, final dates,
	lecture-days, year are all metadata.

---

## Tutorial: a five-minute schedule

Given a `coursemeta.tex` already at your course root with start/end
dates and lecture-days, drop this into the schedule file:

```latex
% Math 126EE/Spring 26/Schedule/Schedule.tex
\documentclass{schedule}

\meta{
	landscape    = true,
	lecture-caps = {1.0, 1.0},
	quiz-days    = T,
}

\begin{document}
\begin{schedule}
	% Holidays / blackouts
	\holiday{1-19}{MLK Jr. Day}
	\holiday{2-16}{President's Day}
	\holiday{3-23}[3-27]{Spring Break}

	\noquiz{1-20}
	\quiz[date=1-21]

	% Body — sections in order.
	\syllabus
	\section{R.1}
	\section{R.2}
	\section[2]{R.4}      % weight 2 (≈ 2 lecture days)
	\examreview
	\exam[noquiz]

	\section[1.5]{3.3}
	\section{3.4}
	\finalreview
	\finalsweek[5-7][5]   % finals start 5/7, run 5 days
	\winterbreak
\end{schedule}
\end{document}
```

The class consumes the metadata (start-date, end-date, final-date,
final-time, lecture-days, year) plus the sequence of directives, and
lays out the term week-by-week.

---

## Reference

### Document class

`\documentclass[options]{schedule}`
Loads `article` as the base class. Most users pair it with
`landscape = true` (set via `\meta`).

### Metadata keys (set via `\meta{...}`)

Class-local keys (in addition to all standard `course-metadata` keys):

| Key             | Meaning                                                 |
|-----------------|---------------------------------------------------------|
| `landscape`     | `true`/`false`. Switches geometry to landscape, 0.5in margins |
| `portrait`      | `true` to force portrait                                |
| `lecture-caps`  | Per-day weight caps, comma list matching `lecture-days` |
| `quiz-days`     | Days of the week for quizzes (e.g. `T`, `Th`)           |

Required `course-metadata` keys: `course-subject`, `course-number`,
`course-title`, `course-section`, `season`, `year`, `start-date`,
`end-date`, `final-date`, `final-time`, `lecture-days`. (Recitation
days come from the optional `recitation-days` key, defaulting to empty.)

### Build flags (TeXLib unified CLI)

The standard flags (`\ifsolutions`, `\ifkey`, `\ifdraft`, `\ifstudent`,
`\ifinstructor`) are defined and respond to the standard
`\ShowSolutions` / `\ShowKey` / `\ShowDraft` / `\StudentMode` /
`\InstructorMode` compile-time defines. The schedule class doesn't
itself branch on most of these; they are present so a schedule file
behaves identically to other TeXLib documents in your build pipeline.

### Title block

`\maketitle` (or `\scheduletitle`) emits the standard banner
("Math 126EE Precalculus I Tentative Schedule — Spring 2026 / Section
1008"). The `schedule` env calls it automatically, so existing
documents are unchanged.

### `schedule` environment

`\begin{schedule} ... directives ... \end{schedule}`

Initializes the scheduler, draws the title bar, and renders the grid
on `\end{schedule}`. Directives inside the environment add events to
the grid in declaration order; the date cursor is advanced
automatically.

### Directives

| Directive                          | Effect                                           |
|------------------------------------|--------------------------------------------------|
| `\section[w]{label}`               | Adds a course section taking `w` lecture days (default 1.0). |
| `\topic[w]{label}`                 | Free-form topic block, same weighting.           |
| `\holiday{date}{label}`            | Single-day holiday (date is `M-D`).              |
| `\holiday{start}[end]{label}`      | Multi-day holiday range.                         |
| `\noquiz{date}`                    | Suppress the auto-quiz on `date`.                |
| `\quiz[opts]`                      | Force a quiz; opts can be `date=…`.              |
| `\note[date]{text}`                | Annotate a specific date.                        |
| `\syllabus`                        | Alias for `\topic{Syllabus}` (weight 1.0).       |
| `\examreview[w]`                   | Add an exam-review block.                        |
| `\exam[opts]`                      | Add an exam block. Opts: `noquiz`, `length=…`.   |
| `\finalreview[w]`                  | Add a final-review topic.                        |
| `\finalsweek[start][duration]`     | Insert finals week at `start` for `duration` days. |
| `\winterbreak[label]`              | Auto-rendered winter break (default label `Winter Break`). |
| `\debugdate`                       | Dump the cursor's current date (debugging aid).  |

### Lua bridge

The class loads `date.lua`, `calendar.lua`, and `schedule.lua` from the
class file's directory. These do all the date math. They are part of
the package and must accompany `schedule.cls`.

---

## Tips

- **Section weight:** `\section[2]{R.4}` consumes two lecture days.
	Use this when a topic spans multiple meetings.
- **Quiz handling:** `quiz-days` declares the day of week quizzes
	fall on; the scheduler auto-emits one each week. Use `\noquiz{date}`
	to suppress, or `\quiz[date=…]` to override the day.
- **Spring break / multi-day holidays:** `\holiday{3-23}[3-27]` covers
	the inclusive date range.
- **Exam after a unit:** the typical pattern is
	`\section{...} \section{...} \examreview \exam[noquiz]`.

## Related

- `course-metadata.md` — for the start-date/end-date/final-date/
	lecture-days conventions.
- The Lua engine itself lives in `schedule.lua`; date arithmetic in
	`date.lua` and weekly-grid layout in `calendar.lua`.
