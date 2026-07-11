# Feature-test fixtures

Self-contained documents that exercise one feature the canonical module
templates don't. Unlike the visual packs in [`../scenarios/`](../scenarios/)
(local-only, pixel-diffed), these are **registered in `smoke_test.py`'s `MODULES`
list**, so they build on every push alongside the real modules and assert their
expected text via `EXPECT_TEXT`.

## Layout

```
tests/fixtures/
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

## Adding a fixture

Drop `tests/fixtures/<Module>/<entry>.tex` (self-contained, with any siblings it
needs), then add an entry to `MODULES` in `smoke_test.py` — and, if it should
assert rendered text, a matching `EXPECT_TEXT["tests/fixtures/<Module>"]` list
of single-token markers. Run `python smoke_test.py tests/fixtures/<Module>` to
check it.
