# `report-card` — Per-Student Report Cards

A LaTeX class for generating end-of-term grade reports — one
per-student section per page, all collated into a single PDF you can
split and email out (or print and hand back).

## What it gives you

- A `reportcard` environment that wraps each student's section with a
	title page, a disclaimer, and a trailing page break.
- A `\gradebreakdown{...}` table for the per-category point breakdown.
- A `\standingbar{...}` TikZ visualization showing earned vs. possible
	points with grade-threshold markers.
- A `\scenarios{...}` table showing what the student needs on the
	final to reach each letter grade.
- A `\signoff{...}` macro for a personalized closing.

The header and footer are driven by `coursemeta.tex`; the brand color
defaults to UNR navy but is overridable.

---

## Tutorial: a five-minute report card

```latex
\documentclass{report-card}

\meta{
	report-date = {May 7, 2026},
	% brand-color = 003366,   % override (HTML hex), default is UNR navy
}

\begin{document}

\begin{reportcard}{Dawnyelle Allison}

	\section*{Current Grade Calculation}

	Based on the syllabus, here is your grade breakdown prior to the
	Final Exam. Homework and Quiz averages reflect the
	``drop lowest 5'' policy.

	\gradebreakdown{
		Homework Avg. & 15\% & 92.1\% & +13.8 \\
		Quiz Avg.     & 10\% & 67.5\% & +6.8  \\
		\midrule
		Exam 1        & 10\% & 31\%   & +3.1  \\
		Exam 2        & 10\% & 39\%   & +3.9  \\
		Exam 3        & 10\% & 35\%   & +3.5  \\
	}{75\% (+15\% E.C.) & \fbox{\textbf{59.4\%}} & 44.5}

	\section*{Visual Standing}
	\standingbar{5.564}{7.5}{8.75}{10}{11.25}

	\section*{Final Exam Scenarios}
	\scenarios{
		To Pass                       & D 60\% & \textbf{61.9\%} \\
		To Advance to Math 127 or 176 & C 70\% & \textbf{101.9\% (unfeasible)} \\
		To get a B                    & B 80\% & \textbf{141.9\% (unfeasible)} \\
		To get an A                   & A 90\% & \textbf{181.9\% (unfeasible)} \\
	}

	\signoff{Good luck on the final! I wish you a successful career.}

\end{reportcard}

% Subsequent students are wrapped the same way:
% \begin{reportcard}{Adalynn Andresen} ... \end{reportcard}

\end{document}
```

---

## Reference

### Document class

`\documentclass[options]{report-card}`
Options pass through to `article`. Default base size is 11pt.

### Class-local metadata keys

| Key            | Default              | Effect                                |
|----------------|----------------------|---------------------------------------|
| `report-date`  |                      | Date string in title pages and headers |
| `brand-color`  | `003366` (UNR navy)  | HTML hex for tables, bars, rules      |
| `accent-color` | `808080` (silver)    | Reserved for future styling            |
| `rc-disclaimer`| UNR-style boilerplate| Renders below the per-student title. Legacy alias: `disclaimer`. |
| `rc-signature` | `\GetInstructor`     | Used in `\signoff`. Legacy alias: `signature`. |

Plus all `course-metadata` keys.

### Build flags (TeXLib unified CLI)

`\ifdraft`, `\ifkey` and the matching `\ShowDraft` / `\ShowKey`
toggles. Source: `\drafts`.

### Commands and environments

`\maketitle`
Course-level cover page (course title, term, report date) — no
student name. Use this once at the top of the document if you want
a single cover before the per-student sections.

`\studenttitle{Name}`
Emits a centered title block (Name + course + report date) on its own
page, followed by a blank verso and `\newpage`. Most users go through
the `reportcard` environment instead, which calls this for you.

`\begin{reportcard}{Name} ... \end{reportcard}`
Wraps each student section. Opening: `\studenttitle{Name}` then the
disclaimer paragraph. Closing: `\newpage`. Place the per-student
content in between.

`\gradebreakdown{rows}{totals}`
Render the four-column "Category | Weight | Score | Points Earned"
table, with `\toprule`, `\midrule\midrule` separators, a brand-tinted
total row, and `\bottomrule`. Pass tabular rows as `rows` (separate
cells with `&`, rows with `\\`); pass the cells of the totals row
as `totals` (three cells matching the last three columns —
the "Current Total" label is added for you).

`\standingbar{earned}{D}{C}{B}{A}`
Draw the progress bar. Coordinates are 0..12.5 representing
0..100%. `earned` is the user's current points (e.g. 5.564 for 44.5
points out of 75% completed = 44.5 × 12.5 / 100). `D`, `C`, `B`, `A`
are the threshold x-coordinates (typically 7.5, 8.75, 10, 11.25 for
60/70/80/90%).

`\scenarios{rows}`
Render the three-column "Outcome | Required Letter Grade | Required
Final Exam Score" table. Pass tabular rows.

`\signoff{message}`
Bottom-of-card sign-off. Adds a personal message, then "Sincerely,"
on its own line, then `\GetSignature` (defaults to `\GetInstructor`,
overridable via `\meta{signature=...}`).

`\GetReportDate`, `\GetDisclaimer`, `\GetSignature`
Direct getters.

### Page header / footer

- Header L: `\GetCourseShort \GetCourseTitle`
- Header R: `Report Card, \GetReportDate`
- Footer L: `Section <n>`
- Footer R: `\GetInstitution`
- Footer C: `<page> of <total>`

### Color setup

The brand and accent colors are defined at `\AtBeginDocument` time
from the metadata (so users can override them via `\meta{brand-color
= ...}` after `\documentclass`). Internal name: `rc@brand` and
`rc@accent`. Use `rc@brand!10` for a 10% tint, etc.

---

## Tips

- **One file per term:** I keep one `Math <code> <term>.tex` file with
	all students. It's verbose but easy to grep, diff, and re-run when a
	grade changes.
- **Disclaimer override:** if your department has standard wording,
	set `disclaimer = {...}` in the document preamble (or per-student
	via a `\meta{disclaimer=...}` inside the `reportcard` environment).
- **Bar coordinates:** 12.5 = 100%, so multiply percent by 0.125. For
	44.5 points out of a possible 75 (pre-final), that's 44.5 × 12.5 /
	75 = ~7.42.
- **Splitting the PDF:** use `pdftk` or `qpdf` to split the resulting
	multi-student PDF into per-student files keyed by name (the title
	page has the student name in plain text, easy to extract).

## Related

- `course-metadata.md` — for `\GetInstitution`, `\GetCourseShort`,
	`\GetInstructor`.
