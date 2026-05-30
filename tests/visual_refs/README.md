# Visual-regression reference images

PNG renders of each deterministic module's smoke-test build, one per page,
named `<module>-<page>.png` (e.g. `Schedule-1.png`). `smoke_test.py --visual`
renders the current build and pixel-diffs it against these, catching **layout**
regressions that the text/content checks can't see — the motivating case was a
stray vertical-rule stub under the schedule's last row.

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
