# Third-party notices

TeXLib itself is MIT licensed — see [LICENSE](LICENSE). That file is kept as
the unmodified MIT text and nothing else, because automated license detectors
(GitHub's included, and the policy scanners some institutions run before
approving software) stop recognising a license once anything is appended to it.
Everything that would otherwise have gone at the bottom of `LICENSE` lives here.

## Vendored code

### `quiver.sty`

Third-party code from <https://q.uiver.app>, vendored for commutative-diagram
support. It retains its original authorship — varkor, AndréC, Andrew Stacey —
and its own license terms. TeXLib's MIT license does **not** cover it.

It is vendored rather than depended on because a diagram in a lecture note has
to compile on a machine that has only TeX Live, and `quiver.sty` is not in
`texmf-dist`. `texlib_cli.py install` copies it into `TEXMFHOME` along with the
rest of the payload, so an installed TeXLib carries it too.

## Runtime dependencies (not distributed here)

These are required or optional at build time and are installed separately, each
under its own license:

| Component | License | Role |
|---|---|---|
| [TeX Live](https://tug.org/texlive/LICENSE.TL) | mostly LPPL and similar | the engines (`lualatex`, `pdflatex`), `biber`, `synctex` |
| [veraPDF](https://verapdf.org/) | GPLv3 / MPLv2 dual | PDF/UA-2 conformance reports for accessible builds (optional) |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | per-version exam PDF slicing (optional) |
| [poppler](https://poppler.freedesktop.org/) | GPLv2 | `pdftotext` / `pdftoppm`, used by the test harness only |
| [ImageMagick](https://imagemagick.org/) | ImageMagick License | visual-regression diffs, test harness only |

The editor integration under `Sublime/` targets
[Sublime Text](https://www.sublimetext.com/eula) (commercial) and
[LaTeXTools](https://github.com/SublimeText/LaTeXTools) (MIT). Neither is
required: `texlib_cli.py` builds every class with no editor at all.
