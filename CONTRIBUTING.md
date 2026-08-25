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
  `texlib_synctex.lua`, `smoke_test.py`.

## Testing (please run before opening a PR)

You need TeX Live (lualatex/pdflatex, + biber for bibliographies) on `PATH`.

```bash
python smoke_test.py                 # build every module template (all classes)
python smoke_test.py --modes all     # also key/solutions/student/rubric modes
python Sublime/test_texlib_builder.py  # builder logic (no toolchain needed)
python Sublime/test_biber_integration.py   # real biber cache (needs biber)
```

Visual regression (needs `pdftoppm` + ImageMagick) compares rendered pages to
the reference images in `tests/visual_refs/`. The refs **are committed** and
CI-gated; they are canonical for the pinned CI container, so regenerate them
*in that container* (run the `visual` workflow manually with `update_refs=true`,
download the `visual-refs` artifact, commit) rather than locally — a local
`--update-refs` only stays green in CI if your toolchain renders identically
to the pin. See `tests/visual_refs/README.md`.

```bash
python smoke_test.py --visual            # compare to tests/visual_refs/
python smoke_test.py --scenarios         # scenario packs (examples/scenarios/)
python smoke_test.py --update-refs       # local regen (see the caveat above)
```

CI (`.github/workflows/`) runs four workflows: `tests.yml` (logic suites +
real-toolchain integration, every push/PR), `smoke.yml` (full module smoke
build, push/PR to `main`), `visual.yml` (pixel diff against the committed
refs, PR to `main` + nightly), and `accessible.yml` (PDF/UA-2 conformance via
veraPDF, PR to `main` + nightly). A green PR should pass `smoke_test.py`
locally first.

## Adding bank problems

Bank problems are region-delimited
`\begin{problem}{id}[meta] <stem> [\begin{choices}…\end{choices}]
[\begin{solution}…\end{solution}] \end{problem}` blocks (the optional choices
block marks a multiple-choice problem; `\cchoice` flags the answer). Define them
in a bank file and pull with `\getproblem{id}` (anywhere) or `\problem{filter}`
(inside `\begin{problems}` / `\begin{mcproblems}`). Keep `id`s unique. See
`texlib-problembank.sty` and the `Exams/` templates for the full API.

## Releasing (maintainer)

The library releases by git tag: run `python bump_version.py X.Y.Z` (stamps
`texlib-manifest.json` and every `\Provides` line in one pass), close the
`## [Unreleased]` section of `CHANGELOG.md` into a `## [X.Y.Z] — date`
heading, then `git tag vX.Y.Z && git push --tags`. CI's version-contract
check fails the release branch until the manifest, the newest released
heading, and every `\Provides` line agree — `python bump_version.py --check`
runs it locally. The
[TeXLib-Installer](https://github.com/landonfox00/TeXLib-Installer) pins a tag,
downloads its archive at install time, and verifies it against a recorded
SHA-256 — it does not bundle a snapshot — so after tagging, bump the installer's
pin in its own repo.
