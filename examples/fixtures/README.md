# Feature-test fixtures

Self-contained documents that exercise one feature the canonical module
templates don't. Unlike the visual packs in [`../scenarios/`](../scenarios/)
(local-only, pixel-diffed), these are **registered in `smoke_test.py`'s `MODULES`
list**, so they build on every push alongside the real modules and assert their
expected text via `EXPECT_TEXT`.

## Layout

```
examples/fixtures/
  <Module>/                 # capitalized like the module it builds on
    <entry>.tex             # the file named in MODULES
    coursemeta.tex          # optional — ship one to control metadata
    <siblings>.tex          # optional — banks, includes (copied into the build dir)
```

`build_one` copies every sibling file into the isolated build dir and pulls in
the root `.sty`/`.lua` plus each module's `.cls`, so a fixture can `\loadbank` a
sibling or use any module's class.

## Current fixtures

| Module | Entry | Exercises |
|--------|-------|-----------|
| `Exams` | `fix-test.tex` (+ `fix-bank.tex`) | the `\problem{id}[a=1,b=2]` fix-overrides syntax |
| `Metadata` | `metadata-test.tex` (+ `coursemeta.tex`) | `course-metadata.sty`'s arbitrary-key catch-all + `\Get<Key>` derivation |
| `Notes` | `theorem-numbering.tex` | didactic's shared-counter, section-based theorem numbering (`Theorem 1.1`, `Definition 1.2`, … resetting per `\section`) |
| `MathML` | `nth-root-mathml.tex` | two or more `\sqrt[n]{…}` in ONE formula — the shape that aborts a tagged build under `mathml-SE` |

## Adding a fixture

Drop `examples/fixtures/<Module>/<entry>.tex` (self-contained, with any siblings
it needs), then add an entry to `EXAMPLES` in `examples/manifest.py` — with
`expect=` single-token markers if it should assert rendered text
(`smoke_test.py` derives its module list and `EXPECT_TEXT` from the manifest).
Run `python smoke_test.py examples/fixtures/<Module>` to check it.

A directory may hold **several** fixtures: expectations are keyed by
`(module, template)`, so each one keeps its own `expect`/`absent`/`artifact`
list. Put a fixture in the directory of the module it builds on, and reach for a
new `<Module>` directory only when it genuinely builds on a different class —
not to dodge a name collision. (Until 2026-08-31 those lists were keyed by
module alone and the second fixture in a directory silently erased the first
one's assertions, so the guidance used to be the opposite.)
