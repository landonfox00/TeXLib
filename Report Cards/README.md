# `report-card` — Per-Student Report Cards

A LaTeX class for generating end-of-term grade reports — one
per-student section per page, all collated into a single PDF you can
split and email out (or print and hand back).

## What it gives you

- **`\gradebook{file.csv}` — the recommended path.** Point it at a
	report-view CSV (one row per student) and the class renders a full,
	auto-computed card for every student: one cover each, the breakdown
	table, the standing bar, and the final-exam scenarios. All the
	arithmetic lives in your gradebook spreadsheet; the class only
	typesets. See [Gradebook-driven workflow](#gradebook-driven-workflow-recommended).
- A `reportcard` environment that wraps each student's section with a
	title page, a disclaimer, and a trailing page break (the manual path,
	when you want to hand-write one card).
- A `\gradebreakdown{...}` table for the per-category point breakdown.
- A `\standingbar{...}` TikZ visualization showing earned vs. possible
	points with grade-threshold markers.
- A `\scenarios{...}` table showing what the student needs on the
	final to reach each letter grade.
- A `\signoff{...}` macro for a personalized closing.

The header and footer are driven by `coursemeta.tex`; the brand color
defaults to UNR navy but is overridable.

---

## Gradebook-driven workflow (recommended)

Keep **one `gradebook.xlsx` per course-semester** (e.g. inside a
`Math 181 Spring 2026/` directory) as your single source of truth.
Build it in Google Sheets, do all the grade math there with formulas,
and let the build turn it into report cards.

### The two tabs

1. **`Roster`** — your workspace: one column per assignment (HW1, HW2,
	…, Quiz1, …, Exam 1–5, EC…), plus whatever formulas you like
	(drop-lowest, averages, weighted totals).
2. **`Report View`** — formula columns that reference `Roster` and
	produce exactly the values a card prints. **This is the only tab the
	class reads.** Editing `Roster` updates it automatically.

`make_starter_gradebook.py` generates a working two-tab starter
(`gradebook.xlsx`) you can import into Google Sheets
(`File → Import → Upload`) and adapt — the Report View formulas are
already wired to the Roster.

### Report View column convention

Columns are matched **by name** (order defines the breakdown row order):

| Column header            | Meaning                                            |
|--------------------------|----------------------------------------------------|
| `Name`                   | Student name (the cover + section)                  |
| `<Category> Weight`      | Category weight, e.g. `Homework Avg. Weight` → 15  |
| `<Category> Score`       | The student's % in that category                   |
| `<Category> Points`      | Points earned (weight × score / 100)               |
| `---`                    | A column literally named `---` inserts a `\midrule` |
| `Current Total`          | Running percentage (boxed in the total row)        |
| `Current Points`         | Running points earned                              |
| `Weight Summary`         | Left cell of the total row, e.g. `75% (+15% E.C.)` |
| `Need <letter>`          | Scenario cell: `22.0%`, `Already secured`, …        |

Each `<Category>` contributes one breakdown row from its
`Weight`/`Score`/`Points` triplet. A blank `Score`/`Points` cell prints
an em dash (not-yet-graded). The standing-bar thresholds use the class
cutoffs (`\rc@cut@a..d`, default A90/B80/C70/D60).

### How the file reaches the build

The class reads **CSV**; `gradebook.csv` is the Report View tab exported
from `gradebook.xlsx`. You get that CSV one of two ways:

- **Automatically (Sublime / TeXLib builder).** Building a
	`report-card` document converts every `*.xlsx` in the document's
	directory to a sibling `.csv` (its Report View tab) first — so you
	only ever maintain the one `.xlsx`. (Dependency-free; no openpyxl.)
- **Manually / plain `lualatex`.** Run the standalone converter:

	```
	python gradebook_to_csv.py gradebook.xlsx        # -> gradebook.csv
	python gradebook_to_csv.py gb.xlsx out.csv --sheet "Report View"
	```

### Pointing at the gradebook

Set the path **once in `coursemeta.tex`** (or the class options) with the
`gradebook-path` key, then call **bare `\gradebook`** — it resolves the
path for you, falling back to a sibling `gradebook.csv`:

```latex
\documentclass[
	report-date = {May 7, 2026}, institution = {University of Nevada, Reno},
	instructor  = {Your Name}, season = Spring, year = 2026,
	course-subject = Math, course-number = 181, course-title = {Calculus I},
	gradebook-path = {gradebook.xlsx},   % or set this in coursemeta.tex
]{report-card}
\begin{document}
\gradebook            % uses gradebook-path (falls back to sibling gradebook.csv)
\end{document}
```

Resolution order, mirroring the problem bank's `\loadbank`:

1. `\gradebook[explicit.csv]` — an explicit argument always wins.
2. else `gradebook-path` from coursemeta/class options. A `.xlsx` value is
	mapped to its `.csv` sibling (the file the builder exports), tried
	literally first, then relative to the coursemeta directory.
3. else a sibling `gradebook.csv`.

> Requires LuaLaTeX (the engine reads the CSV via `\directlua`). The
> TeXLib builder forces lualatex for `report-card` automatically, but put
> **`% !TeX program = lualatex`** as the first line of every report-card
> document so any editor (or a non-redeployed builder) picks the right
> engine — otherwise a pdflatex build dies with
> "`\gradebook` requires LuaLaTeX". The template ships with this line.

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
| `report-card-title` | `\GetCourseShort \GetCourseTitle` | Title shown on covers + header |
| `brand-color`  | `003366` (UNR navy)  | HTML hex for tables, bars, rules      |
| `accent-color` | `808080` (silver)    | Reserved for future styling            |
| `rc-disclaimer`| UNR-style boilerplate| Renders below the per-student title. Legacy alias: `disclaimer`. |
| `rc-signature` | `\GetInstructor`     | Used in `\signoff`. Legacy alias: `signature`. |

Plus all `course-metadata` keys — including **`gradebook-path`**, the
report-view CSV (or `.xlsx`, mapped to its `.csv`) that bare `\gradebook`
loads. Set it in `coursemeta.tex` to share one gradebook course-wide.

### Build flags (TeXLib unified CLI)

`\ifdraft`, `\ifkey` and the matching `\ShowDraft` / `\ShowKey`
toggles. Source: `\drafts`.

### Commands and environments

`\gradebook[file.csv]`
Render one report card per row of a report-view CSV (see
[Gradebook-driven workflow](#gradebook-driven-workflow-recommended)).
Each student gets one cover plus an auto-filled breakdown, standing bar,
and scenarios table. The argument is **optional**: with no argument the
path comes from the `gradebook-path` metadata key (then a sibling
`gradebook.csv`). LuaLaTeX only.

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

- Header L: `\GetReportCardTitle` (bold)
- Header R: `\GetTermSection`
- Footer L: `\GetCourseTitle`
- Footer R: `\GetInstitution`
- Footer C: `<page> of <total>`

The first page of each card uses the `firstpage` style (header rule
suppressed, footer kept) so the cover sits cleanly at the top.

### Color setup

The brand and accent colors are defined at `\AtBeginDocument` time
from the metadata (so users can override them via `\meta{brand-color
= ...}` after `\documentclass`). Internal name: `rc@brand` and
`rc@accent`. Use `rc@brand!10` for a 10% tint, etc.

---

## Tips

- **One gradebook per term:** keep a single `gradebook.xlsx` per
	course-semester directory and drive the cards with `\gradebook`
	(see above). Change a grade in the sheet, rebuild — no LaTeX edits.
	The manual `reportcard` environment below is for one-offs.
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
