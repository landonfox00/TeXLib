# `bingo` — Math Bingo Cards

A LaTeX class for printing math-symbol bingo cards. Two layouts are
supported:

1. **Standard cards.** Each cell contains a math symbol or expression
	(e.g. $\beta$, $\int$, $\mathbb{R}$). Different students get
	different cards.
2. **Labeled cards + legend.** Each cell shows its grid label (B1, B2,
	…, O5); a separate `\bingolegend{...}` table maps labels to math
	expressions. This is the layout I use for exam-review bingo, where
	the student picks the answer matching the question I read aloud.

## What it gives you

- A `bingocard` environment that draws the 5×5 grid, optional
	B-I-N-G-O headers, and the free-space symbol at center.
- `\bcell{col}{row}{math}` and `\bcelltext{col}{row}{text}` for
	placing content in cells.
- `\labelcells` and `\bingolegend{...}` for the labeled layout.
- An optional metadata-driven title block above each card.

---

## Tutorial: a five-minute card

```latex
\documentclass{bingo}

\begin{document}

\begin{bingocard}
	\bcell{B}{1}{\beta}     \bcell{I}{1}{\pm}      \bcell{N}{1}{\Omega}        \bcell{G}{1}{\mu}     \bcell{O}{1}{\mathbb{R}}
	\bcell{B}{2}{\to}       \bcell{I}{2}{\int}     \bcell{N}{2}{\neq}          \bcell{G}{2}{\notin}  \bcell{O}{2}{\psi}
	\bcell{B}{3}{\exists}   \bcell{I}{3}{\forall}                              \bcell{G}{3}{\frac{d}{dx}} \bcell{O}{3}{\sqrt{x}}
	\bcell{B}{4}{\theta}    \bcell{I}{4}{\circ}    \bcell{N}{4}{\pi}           \bcell{G}{4}{\prod}   \bcell{O}{4}{\gamma}
	\bcell{B}{5}{\alpha}    \bcell{I}{5}{\infty}   \bcell{N}{5}{\sigma}        \bcell{G}{5}{\sum}    \bcell{O}{5}{\Delta}
\end{bingocard}

\newpage

% Another card with different symbols ...

\end{document}
```

(The center cell `(N, 3)` is auto-filled with the free-space symbol —
`\star` by default — so you skip it in your `\bcell` calls.)

For the labeled-card layout used in exam-review bingo:

```latex
\begin{bingocard}
	\labelcells          % auto-fills B1..O5 in every cell
\end{bingocard}

\bingolegend{
	$\text{B}1$ : $\beta$ & $\text{I}1$ : $\pm$ & $\text{N}1$ : $\Omega$ & $\text{G}1$ : $\mu$ & $\text{O}1$ : $\mathbb{R}$ \\
	$\text{B}2$ : $\to$   & $\text{I}2$ : $\int$ & $\text{N}2$ : $\neq$  & $\text{G}2$ : $\notin$ & $\text{O}2$ : $\psi$ \\
	...
}
```

---

## Reference

### Document class

`\documentclass[options]{bingo}`
Options pass through to `article`. Default base size is 12pt. The
class sets `\pagestyle{empty}` so cards print without page numbers.

### Metadata keys (set via `\meta{...}`)

| Key            | Default | Effect                                       |
|----------------|---------|----------------------------------------------|
| `cell-size`    | 2.8cm   | Side length of each grid cell.               |
| `free-symbol`  | `\star` | Symbol placed at center cell (N, 3).         |
| `show-headers` | `true`  | Show the B-I-N-G-O letters above the grid.   |
| `show-title`   | `false` | Render `\bingotitle` above each card.        |

All standard `course-metadata` keys also work — useful when
`show-title=true`.

### Build flags (TeXLib unified CLI)

`\ifsolutions`, `\ifkey`, `\ifdraft`, `\ifstudent`, `\ifinstructor`
and the matching compile-time toggles. The `\ifkey` flag adds an
"Answer Key" annotation to the title block when `show-title=true`.

### Commands and environments

`\begin{bingocard}[<options>] ... \end{bingocard}`
Draw a 5×5 grid with B-I-N-G-O headers (if enabled) and the free-space
symbol at center. The optional argument is forwarded to `\metasetup` —
useful for per-card overrides like `[show-title=true]`.

`\bcell{col}{row}{math}`
Place math-mode content in cell `(col, row)`. `col` is one of `B`,
`I`, `N`, `G`, `O`; `row` is `1` (top) through `5` (bottom).

`\bcelltext{col}{row}{text}`
Same but text-mode content (no `$...$` wrapping).

`\labelcells`
Inside a `bingocard`, fill all 24 non-free cells with their grid
labels (B1, B2, …, O5).

`\bingolegend{rows}`
Render a 5-column legend tabular outside (typically below) the card.
Cells are separated by `&`, rows by `\\`. Used with `\labelcells` to
build the answer-bingo style.

`\bingotitle` / `\maketitle`
Auto title block (course + term, plus "Answer Key" if `\ifkey`).
`\maketitle` is an alias for `\bingotitle` so the unified TeXLib
title pattern works here too. Inside each `\bingocard` the title is
emitted only if `show-title=true`.

### Coordinate convention

Internally, the grid is drawn with `tikzpicture[x=cell-size, y=cell-size]`:

- Columns: B → x = 0.5, I → 1.5, N → 2.5, G → 3.5, O → 4.5
- Rows:    row 1 → y = 4.5 (top), row 5 → y = 0.5 (bottom)
- Free space at (N, 3) → (2.5, 2.5)

If you want to drop in a custom node, use those coordinates inside the
environment.

---

## Tips

- **Per-student randomization:** the class deliberately doesn't shuffle
	cells — you typically want each student's card to differ in known
	ways. Generate a sequence of `bingocard` environments with shuffled
	`\bcell` orderings (a small Lua script outside LaTeX is the easiest
	approach), or copy/paste with manual permutations.
- **Free-space override:** set `free-symbol = \cdot` (or any math token)
	to change the centerpiece per card.
- **Larger or smaller cards:** adjust `cell-size`. The page geometry
	uses `margin=1in`; a `cell-size` larger than ~3.4cm may overflow.
- **Two cards per page:** call `\begin{bingocard}...\end{bingocard}`
	twice with `\newpage` between them — the standard pattern.

## Related

- `course-metadata.md` — for any course/title metadata you want
	rendered in `\bingotitle`.
