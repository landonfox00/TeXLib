# Visual scenario packs

Each scenario is a **self-contained document** exercising *one* configuration of
a module, built and pixel-diffed against a committed reference by
`smoke_test.py --scenarios`. This is the tier-2/3 visual testing layer: where
the per-push module suite builds one canonical `template.tex` per module, the
scenario packs cover the configuration space (orientation, `month-pages`, edge
dates, …) without bloating the fast path.

## Layout

```
tests/scenarios/
  <area>/                     # maps to a module (see SCENARIO_AREA_MODULE)
    <name>/
      template.tex            # required — metadata inline via \metasetup
      coursemeta.tex          # optional — ship one to exercise coursemeta keys
      expect-text             # optional — PDF substrings to assert (text scenario)
      tags                    # optional — whitespace-separated tier tags
```

- **`<area>`** maps to the module whose `.cls`/`.lua` the scenario builds on
  (`schedule` → `Schedule/`). Add new areas in `smoke_test.py`'s
  `SCENARIO_AREA_MODULE`.
- **`template.tex`** is fully self-contained: it sets its own metadata with
  `\metasetup{...}` inline, so no `coursemeta.tex` is needed (the harness builds
  each scenario in an isolated temp dir).
- **`tags`** (optional) marks the tier. Absent ⇒ `core`. Put `full` in the file
  to make a scenario run only under `--full` (use for edge cases you don't need
  on every focused run).
- **`expect-text`** (optional) turns a scenario into a **text-assertion** check:
  list substrings (one per line; blank lines and `#` comments ignored) that must
  appear in the rendered PDF. A scenario that ships `expect-text` and has *no*
  reference PNGs skips the pixel diff — ideal when what's under test is *which
  text renders* (e.g. that a `coursemeta.tex` key resolved to the right file),
  not layout. If it also has refs, both the text check and the diff run. Use
  single-token markers (no spaces/hyphens) so `pdftotext` can't split them.
- A scenario may ship its own **`coursemeta.tex`** — the harness auto-loads it
  (it does *not* drop the smoke-test stub for scenarios), so you can exercise
  course-metadata keys like `quiz-instructions-file` or `bank-path`.

References land in `../visual_refs/<area>__<name>-<page>.png`.

## Running

```
python smoke_test.py --scenarios                 # core scenarios, all areas (focused)
python smoke_test.py --scenarios schedule        # core scenarios in one area
python smoke_test.py --scenarios --full          # ALL scenarios, all areas (ultimate)
python smoke_test.py --scenarios --update-refs   # regenerate references
python smoke_test.py --scenarios schedule --full --update-refs   # combine freely
```

Each scenario runs the area's content checks (grid non-empty + text tokens) plus
a per-page visual diff. References are **rendering-environment-specific**, so
they must be regenerated after an intentional layout change or a TeX Live bump.
The `visual.yml` workflow runs `--scenarios` inside a **pinned** TeX Live
container, so these are gated in CI (non-required); locally, comparison needs
`pdftoppm` (poppler) and `magick` (ImageMagick) — missing tools soft-skip. The
randomized `autoexam`/`quiz` classes are made deterministic here with a fixed
`\setexamseed` + single version, bringing them into visual scope.

## Current packs

| Area | Scenario | Tier | Exercises |
|------|----------|------|-----------|
| schedule | `landscape-mwf`     | core | the common case: Fall MWF, landscape (4 cols incl. quiz) |
| schedule | `portrait`          | core | portrait geometry branch |
| schedule | `month-pages`       | core | per-month tables + boundary-week repeat (multi-page) |
| schedule | `summer-intensive`  | core | MTWRF daily, 5 day-columns, sub-month term |
| schedule | `mid-week-start`    | full | term starting mid-week → partial first week |
| schedule | `recitations`       | full | a recitation column alongside lectures |
| schedule | `no-quiz`           | full | MWF only, no quiz column (3 cols) |
| report-cards | `standard`      | core | one student: full card (breakdown, standing bar, scenarios) |
| report-cards | `multi-student` | full | two students in one file → multi-page / per-card reset |
| syllabi | `standard`           | core | title block, sections, two-column grade tables |
| syllabi | `long`               | full | content-heavy syllabus that spills onto page 2 |
| notes | `theorem-custom`       | core | `\texlibtheoremsetup` — tint off + recoloured theorem/definition rules |
| quiz | `coursemeta-instructions` | core | `quiz-instructions-file` set in `coursemeta.tex` resolves to a course-local instructions file (text-assertion scenario, no PNG ref) |
| exam | `standard`               | core | deterministic seed-pinned exam: cover + MC answer-key frame + free-response (instructor copy) |
| quiz | `standard`               | core | deterministic seed-pinned quiz: title + free-response + multiple-choice (student copy) |

## Adding a scenario

Drop a new `tests/scenarios/<area>/<name>/template.tex` (self-contained), add a
`tags` file if it's `full`-only, then `python smoke_test.py --scenarios <area>
--full --update-refs` to mint its reference and commit the PNG(s).

For a **text-focused** feature (where the assertion is "the right text rendered",
not pixels), skip the PNG ref: ship an `expect-text` file with a unique marker
instead. The `quiz/coursemeta-instructions` pack is the model — its `template.tex`
+ `coursemeta.tex` + `course-quiz-instructions.tex` prove a coursemeta key
resolved to a course-local file, asserted by the `CMQUIZINSTRMARKER` marker.
