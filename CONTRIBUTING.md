# Contributing to TeXLib

TeXLib is a personal LaTeX teaching library (`.sty`/`.cls`/`.lua`) plus course
materials, shared publicly so colleagues can use and improve it. Contributions
are welcome — bug reports, new bank problems, class fixes, and tooling.

## Ground rules

- **Branch off `main`.** Use a descriptive branch name (`fix/scorepage-empty`,
  `feat/quiz-instructions`). Don't commit straight to `main`.
- **One logical change per commit.** Write present-tense, scoped messages
  (`fix(engine): …`, `docs: …`). Reference the area you touched.
- **Update the CHANGELOG.** Add a bullet under `## [Unreleased]` in
  `CHANGELOG.md` (Keep a Changelog format). Versions correspond to git tags.

## Naming convention

- **Frontend files** — anything an author types in a `.tex` (package/class
  names, public macros) use **dashes**: `texlib-problembank.sty`,
  `course-metadata.sty`.
- **Backend files** — engine/tooling not referenced from `.tex`
  (`.lua`, `.py`, internal helpers) use **underscores**: `problem_engine.lua`,
  `texlib_synctex.lua`, `build_versions.py`.

## Testing (please run before opening a PR)

You need TeX Live (lualatex/pdflatex, + biber for bibliographies) on `PATH`.

```bash
python smoke_test.py                 # build every module template (all classes)
python smoke_test.py --modes all     # also key/solutions/student/rubric modes
python Sublime/test_texlib_builder.py  # builder logic (no toolchain needed)
python test_build_versions.py        # parallel multi-version driver
python Sublime/test_biber_integration.py   # real biber cache (needs biber)
```

Visual regression (optional; needs `pdftoppm` + ImageMagick) compares rendered
pages to local references — these are environment-specific and not committed:

```bash
python smoke_test.py --visual            # compare to tests/visual_refs/
python smoke_test.py --scenarios         # scenario packs (tests/scenarios/)
python smoke_test.py --update-refs       # regenerate refs after an intended change
```

CI (`.github/workflows/`) runs the smoke build and the no-toolchain logic tests
on push/PR. A green PR should pass `smoke_test.py` locally first.

## Adding bank problems

Bank problems are region-delimited
`\begin{problem}{id}[meta] <stem> [\begin{choices}…\end{choices}]
[\begin{solution}…\end{solution}] \end{problem}` blocks (the optional choices
block marks a multiple-choice problem; `\cchoice` flags the answer). Define them
in a bank file and pull with `\getproblem{id}` (anywhere) or `\problem{filter}`
(inside `\begin{problems}` / `\begin{mcproblems}`). Keep `id`s unique. See
`texlib-problembank.sty` and the `Exams/` templates for the full API.

## Releasing (maintainer)

Bump the relevant version, finalize the `CHANGELOG.md` section, then
`git tag vX.Y.Z && git push --tags`. The installer bundles a TeXLib snapshot
at its own release time (see the [TeXLib-Installer](https://github.com/landonfox00/TeXLib-Installer) repo).
