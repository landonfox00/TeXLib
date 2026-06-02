# Visual-regression reference images

PNG renders of smoke-test builds, one per page, pixel-diffed by `smoke_test.py`
to catch **layout** regressions that the text/content checks can't see — the
motivating case was a stray vertical-rule stub under the schedule's last row.
Two naming schemes share this directory:

- `<module>-<page>.png` (e.g. `Schedule-1.png`) — the canonical per-module
  templates, compared by `--visual`.
- `<area>__<scenario>-<page>.png` (e.g. `schedule__month-pages-1.png`) — the
  visual scenario packs, compared by `--scenarios`. See
  [../scenarios/README.md](../scenarios/README.md).

## Scope

Only deterministic modules are covered (`VISUAL_MODULES` in `smoke_test.py`:
Schedule, Report Cards, Syllabi, Notes). `autoexam`/`quiz` shuffle versions and
pull random bank problems, so their pages differ build-to-build and can't be
pixel-compared.

## Regenerating

These images are **environment-specific** — font rendering differs across TeX
Live versions and platforms. Regenerate (and commit the result) whenever you:

- intentionally change a covered module's layout, or
- bump your TeX Live / toolchain.

```
python smoke_test.py --update-refs            # all covered modules
python smoke_test.py Schedule --update-refs   # just one
```

Because of that environment-sensitivity, `--visual` is a **local** developer
aid (run it before a layout-touching refactor); CI runs build + content checks
only, which are portable. Comparison needs `pdftoppm` (poppler) and `magick`
(ImageMagick); when either is missing the check soft-skips.
