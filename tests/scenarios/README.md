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
a per-page visual diff. Like all visual checks, references are
**rendering-environment-specific**, so this stays a local aid (not wired into
CI) and must be regenerated after an intentional layout change or a TeX Live
bump. Comparison needs `pdftoppm` (poppler) and `magick` (ImageMagick); missing
tools soft-skip.

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

## Adding a scenario

Drop a new `tests/scenarios/<area>/<name>/template.tex` (self-contained), add a
`tags` file if it's `full`-only, then `python smoke_test.py --scenarios <area>
--full --update-refs` to mint its reference and commit the PNG(s).
