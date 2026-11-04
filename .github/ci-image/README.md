# CI image

`ghcr.io/landonfox00/texlib-ci` is the toolchain for every container job in
CI: `tests.yml` (biber-integration), `smoke.yml`, `visual.yml` and
`accessible.yml`. It is `ghcr.io/xu-cheng/texlive-full:20260701` (TeX Live
2026, by digest) with the tools those jobs used to install at job time:

| Tool | Version | Used by |
| --- | --- | --- |
| ImageMagick | `7.1.2.35-r0` (apk, exact) | visual |
| poppler-utils | `25.12.0-r1` (apk, exact) | all four |
| veraPDF | 1.30.2 (SHA-256 checked) | accessible |
| pypdf | 6.16.2 (pip) | biber-integration, accessible |
| python3, py3-pip, openjdk17-jre, curl, unzip | whatever Alpine had at build time | |

`/etc/texlib-ci/manifest` records what a build resolved, and each gate prints it
at the top of its log. `/etc/texlib-ci/apk-packages.txt` lists every package.

## Why an image

Alpine keeps only the newest build of a package. With the exact pins installed
at job time, every Alpine update to a pinned package failed `apk add` on every
PR at once: ImageMagick 7.1.2.27 → .30 (2026-08-30), → .34 (2026-10-24), → .35
(2026-11-03). The exact pins stay, because they are what keeps renders and
verdicts fixed (an unpinned roll to the 7.1.2.27 Beta once cost `visual` its
fuzz tolerance). They are resolved once, here, and the workflows run the
result by digest, so nothing outside this repository can change what a gate
runs.

## Bumping a tool

1. On a branch, edit the `ARG` in `Dockerfile` (or the `FROM` line for a new
   TeX Live snapshot: tag and digest).
2. Push. `ci-image.yml` runs on any push that touches this directory (not on
   `main`), builds the image, checks each gate's tools, pushes
   `texlib-ci:<date>-<sha>`, and prints the full `CI_IMAGE` value in the run
   summary. Off a branch with no Dockerfile change, dispatch it instead
   (Actions ▸ ci-image ▸ Run workflow), once the workflow is on `main`.
3. Put that value in the `CI_IMAGE` line of all four workflows, in the same PR.
4. If the bump can move renders (ImageMagick, poppler, TeX Live), dispatch
   `visual` on the branch with `update_refs=true`, read the artifact's
   `.regen-manifest`, and commit the refs if they changed.

A pinned apk version that Alpine has dropped fails at step 2, at build time,
which is when you want to hear about it. Images already pushed stay pullable,
so the gates on `main` keep running while a bump is in progress.

## Visibility

The package must stay **public**: the gates pull it with no login (the
TeX Live action runs a bare `docker run`). If it were private, every container
job would fail at `docker pull` with `denied`.

veraPDF is installed at `/opt/verapdf-1.30.2`, not `/opt/verapdf`, because the
latter is one of `find_verapdf()`'s fallback roots: installing there would turn
on veraPDF verdicts in every job that builds a tagged PDF. `accessible.yml`
puts `$TEXLIB_VERAPDF_HOME` on `PATH`, and is the only job that does.
