# `bingo` — Math Bingo Cards

A LuaLaTeX class for printing math bingo cards. You write one 5×5 grid of cell
contents; the class draws the grid, scales each cell to fit, and (optionally)
shuffles the entries into a reproducible set of randomized cards.

## What it gives you

- A `\bingobank` command: list the answer pool once, then stamp out cards with
  `\bingocards[...]` — no per-card body.
- A `bingocard` environment for one-off cards whose body *is* the grid — cells
  separated by `&`, rows by `\\`, exactly like a `matrix`.
- Built-in randomization: `[copies=N, randomize]` emits `N` cards, each a
  different shuffle of the pool.
- Auto-scaling cells: short symbols print large and uniform; long expressions
  shrink to fit. No separate legend.
- A footer that numbers each card; the number is also the card's random seed, so
  the set is reproducible and any sheet can be regenerated.

---

## Tutorial: a five-minute card

```latex
\documentclass{bingo}

\begin{document}

\begin{bingocard}
  \beta   & \pm     & \Omega & \mu          & \mathbb{R} \\
  \to     & \int    & \neq   & \notin       & \psi       \\
  \exists & \forall & \free  & \frac{d}{dx} & \sqrt{x}   \\
  \theta  & \circ   & \pi    & \prod        & \gamma     \\
  \alpha  & \infty  & \sigma & \sum         & \Delta     \\
\end{bingocard}

\end{document}
```

Each cell is typeset in math mode automatically — write `\frac{d}{dx}`, not
`$\frac{d}{dx}$` (a `$...$` wrapper is allowed and stripped, e.g. to keep a
linter quiet). `\free` is the free space — an ordinary entry, shuffled and
placed like any other (there is no reserved center cell). A blank cell renders
empty. Cards are centered vertically on the page.

### Randomized exam-review cards (declare a pool, stamp out cards)

The original use case: take the answers to an exam review and turn them into
bingo cards, a different shuffle per student. List the pool once with
`\bingobank` (in the preamble or before the cards), then emit with `\bingocards`:

```latex
\bingobank{
  \frac{\ln(e^x+x)}{x},
  xe^{-x},
  \pi,
  \free,
  % ... one entry per line; a comma-separated list, may exceed 25 entries
}

\begin{document}
\bingocards[copies=30, randomize]
\end{document}
```

With `randomize`, the pool is shuffled and the first 25 entries are placed, once
per copy. A pool of exactly 25 is a pure permutation (every card has the same
entries in different spots); a larger pool samples 25 of them per card. With
`keepfree` (on by default), `\free` is always among the placed 25, so every card
has a free space.

The randomization is **fixed across builds** — recompiling the same source
always produces the same cards (seeded by each card's number). To deal a fresh
set from the same pool, set `seed=` to any number; it stays fixed until you
change it again. This mirrors `autoexam`, whose versioned shuffles are likewise
deterministic per version.

You can also pass the pool inline to `bingocard` instead of declaring a bank —
useful for a single quick card:

```latex
\begin{bingocard}[randomize]
  ... 5x5 of entries ...
\end{bingocard}
```

---

## Reference

### Document class

`\documentclass[options]{bingo}`
Options pass through to `article` (base size 11pt). Requires **LuaLaTeX** (the
randomizer runs in Lua). Page geometry uses 1in margins, matching the other
TeXLib classes.

### Pools and cards

`\bingobank[<name>]{ <comma-separated entries> }`
Declare an answer pool (default `name` is `default`). Usable in the preamble.
The argument is a plain comma-separated list (any length, one entry per line is
tidy); brace an entry that itself contains a top-level comma. `\free` renders the
free symbol. For multi-word or wide answers, stack them with
`\substack{line one\\ line two}` so they fit the cell.

`\bingocards[<options>]`
Emit cards from a declared pool — no body. Set `bank=<name>` in the options to
pick a non-default pool.

`\begin{bingocard}[<options>] <grid body> \end{bingocard}`
A self-contained card whose body is the grid (for one-offs); takes the same
options as `\bingocards`.

| Option      | Default   | Effect                                                       |
|-------------|-----------|--------------------------------------------------------------|
| `copies=N`  | `1`       | Emit `N` cards, each on its own page.                        |
| `randomize` | off       | Shuffle the pool (and sample to 25 if longer) for each copy. |
| `keepfree`  | on        | Always place `\free` (if in the pool) so every card has a free space. |
| `seed=K`    | `0`       | Reshuffle salt. Randomization is fixed across builds; change `seed` to deal a new (still build-stable) set from the same pool. |
| `bank=name` | `default` | (`\bingocards` only) which declared pool to use.             |

> **Free-space note.** With `keepfree` (the default), `\free` is always among the
> placed 25, at a random cell. Set `keepfree=false` to treat `\free` as an
> ordinary pool entry, in which case a pool larger than 25 may by chance place
> zero or two free spaces on a card.

### Cell scaling

Each cell is typeset at a large base size and shrunk only if it overflows, so
single symbols stay big and uniform while wide expressions scale down. If a cell
would shrink below ~40% it raises an error naming the cell — shorten it, split
the bank, or raise `cell-size`.

### Class options (`\documentclass[...]{bingo}`)

Set as comma-separated key-values in the class option list, e.g.
`\documentclass[bingo-title={Exam 3 Bingo}, show-instructions=true]{bingo}`.

| Key            | Default | Effect                                      |
|----------------|---------|---------------------------------------------|
| `cell-size`    | 3.1cm   | Side length of each grid cell.              |
| `free-symbol`  | `\star` | Symbol `\free` renders.                     |
| `show-headers` | `true`  | Show the B-I-N-G-O letters above the grid.  |
| `show-title`   | `false` | Render `\bingotitle` above each card.       |
| `show-instructions` | `false` | Print the instructions block on every card. |
| `bingo-title`  | `Bingo` | Running-header title (e.g. `Exam 3 Bingo`). |
| `bingo-instructions` | — | Inline how-to-play text (boxed).            |
| `bingo-instructions-file` | — | A file `\input` (unboxed) for the instructions instead. |

All standard `course-metadata` keys also work and populate the header/footer.

### Instructions

A how-to-play block, mirroring the quiz class: a boxed, small-font paragraph.
Two ways to place it:

- **On every card** — set `show-instructions=true` (the block prints above each
  grid).
- **As a cover page** — call `\bingoinstructions` once (with a centered title)
  before `\bingocards`, then `\newpage`.

Content resolves file > inline > default:

- `bingo-instructions-file = my-notes` — `\input` the file verbatim (it controls
  its own layout, no box);
- `bingo-instructions = {short text}` — boxed inline text;
- otherwise the default wording in `bingo-instructions.tex` (a real file, so
  SyncTeX inverse-search jumps to it; edit there to change the default for every
  card set).

### Footer number

Every card carries the unified TeXLib footer (course left, institution right);
the center field is the card's sequential number — `1`, `2`, `3`, … — one per
page. That number is also the random seed for the card, so the printed sheets
are reproducible: recompiling the same pool regenerates the same cards, and the
number on a sheet identifies exactly which card it is.

---

## Migrating from the old API

Earlier versions used coordinate placement (`\bcell{col}{row}{}`), `\labelcells`,
and a separate `\bingolegend{...}`. Those still compile (a `bingocard` body that
calls `\labelcells`/`\bcell` is routed to the legacy renderer), but new cards
should use the grid body above — it removes the legend entirely by scaling long
expressions into the cells.

## Related

- `course-metadata.md` — course/title metadata for the header, footer, and
  `\bingotitle`.
