# Visual-regression reference images

PNG renders of smoke-test builds, one per page, pixel-diffed by `smoke_test.py`
to catch **layout** regressions that the text/content checks can't see — the
motivating case was a stray vertical-rule stub under the schedule's last row.
Two naming schemes share this directory:

- `<module>-<page>.png` (e.g. `Schedule-1.png`) — the canonical per-module
  templates, compared by `--visual`.
- `<area>__<scenario>-<page>.png` (e.g. `schedule__month-pages-1.png`) — the
  visual scenario packs, compared by `--scenarios`. See
  [../../examples/scenarios/README.md](../../examples/scenarios/README.md).

## Scope

Only deterministic modules are covered at the **bare-template** level
(`VISUAL_MODULES`, derived in `smoke_test.py` from `examples/manifest.py`:
Schedule, Report Cards, Syllabi, Notes). `autoexam`/`quiz` shuffle versions and
pull random bank problems, so their bare templates differ build-to-build.
They're instead covered by **seed-pinned scenario packs**
(`examples/scenarios/exam`, `examples/scenarios/quiz`), where a fixed
`\setexamseed` + a single version makes the render reproducible and comparable.

## Regenerating

These images are **environment-specific** — font rendering differs across TeX
Live versions and platforms. Regenerate (and commit the result) whenever you:

- intentionally change a covered module's layout, or
- bump your TeX Live / toolchain.

```
python smoke_test.py --update-refs            # all covered modules
python smoke_test.py Schedule --update-refs   # just one
```

`--visual` is also a quick **local** dev aid (run it before a layout-touching
refactor). Comparison needs `pdftoppm` (poppler) and `magick` (ImageMagick);
when either is missing the check soft-skips.

## CI gate

`.github/workflows/visual.yml` diffs against these refs inside a **pinned** TeX
Live container on PRs + nightly, non-required (it reports regressions without
blocking merges). The real pin is the `docker_image` tag
(`ghcr.io/xu-cheng/texlive-full:20260701`, TeX Live 2026) plus the apk version
pins in the workflow — the action SHA alone pins only the action, not the
toolchain. The pin keeps rendering stable so the committed refs stay valid —
they match that container byte-for-byte. If the refs ever drift, regenerate
them **in the container**: run
the `visual` workflow manually with `update_refs=true` (Actions ▸ visual ▸ Run
workflow), download the `visual-refs` artifact, and commit `tests/visual_refs/`.
A plain local `--update-refs` only stays green in CI if your toolchain renders
identically to the pinned container.
