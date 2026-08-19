# Thesis — accessible UNR thesis / dissertation class

`thesis.cls` is a report-based LaTeX class for University of Nevada, Reno M.S.
theses and Ph.D. dissertations that produces a **tagged, PDF/UA-conformant**
document — meeting UNR's accessibility requirement — following the Graduate
School filing guidelines and building on Paul Hurtado's accessible thesis
template (v0.5, <https://www.pauljhurtado.com/latex/>).

## Status

The example (`thesis-template.tex`) builds with **0 errors** and passes veraPDF
for both **PDF/UA-2** (accessibility) and **PDF/A-4f** (archival). It is gated in
CI by `smoke.yml` and `accessible.yml` like every other class, so conformance is
checked on every push rather than by hand.

Checked against the [Graduate School filing guidelines](https://www.unr.edu/grad/current-students/filing-guidelines):

| Requirement | Status |
|---|---|
| 1.0in margins on all four sides | conforms (the `twoside` binding offset was removed -- see below) |
| Page order: title, copyright, committee, abstract, ... | conforms |
| No page number on the first three pages | conforms |
| Abstract begins lowercase Roman at `i` | conforms |
| Body restarts at Arabic `1`, bottom-centre, no running header | conforms |
| Table of Contents, **List of Tables**, List of Figures, in that order | conforms |
| Fonts embedded, 10-12pt | conforms (12pt; all faces embedded) |
| Committee page wording and layout | **needs the Graduate School's answer -- see below** |

`twoside` no longer widens the inner margin. UNR requires 1.0in on all four
sides with no binding exception, and the manuscript is filed electronically
("no hard copies will be produced"), so a 1.25in inner margin was 0.25in out of
spec on every odd page. `twoside` remains available for headers and blank-page
behaviour; add a binding offset at print time for a personal copy, not in the
filed PDF.

## Compiling

Requires **LuaLaTeX** (accessible MathML math tagging is a Unicode-engine
feature) and **Biber** for the bibliography:

```
lualatex thesis-template
biber    thesis-template
lualatex thesis-template
lualatex thesis-template
```

Tagging is intrinsic, not optional: the document **must** begin with
`\DocumentMetadata{...}` *before* `\documentclass{thesis}` (that is the only
place PDF tagging can be switched on). The template already includes it; the
class warns if it is missing.

## Authoring

```latex
\DocumentMetadata{lang=en, tagging=on,
  tagging-setup={math/setup={mathml-SE}, table/header-rows=1},
  pdfstandard={ua-2, a-4f}}
\documentclass{thesis}          % add [twoside] to shift margins for binding

\title{...}\author{...}
\doctype{thesis}                % or dissertation (sets degree + nouns)
\gradprogram{Mathematics}
\gradadvisor{Pat D. Advisor, Ph.D.}
\graddate{May, 2027}
\committeemember{Pat D. Advisor, Ph.D.}{Advisor}
\committeemember{...}{Committee Member}
\committeemember{...}{Graduate School Representative}
\addbibresource{thesis-refs.bib}

\begin{document}
\makeUNRtitlepage
\makecopyrightpage
\committeeapprovalpage
\frontmatter
\begin{frontmatterpage}{Abstract} ... \end{frontmatterpage}
\tableofcontents \listoffigures
\mainmatter
\chapter{Introduction} ...
\begin{theorem}[Name]\label{t} ... \end{theorem}   % accessible, chapter-numbered
\makereferences
\end{document}
```

Accessible theorem environments (`theorem`, `lemma`, `corollary`, `proposition`,
`definition`, `example`, `remark`) render as plain headed paragraphs rather than
amsthm's `\trivlist`, which tags as a list and breaks PDF/UA. `\cref` names them
correctly. `\ThesisMathIntent{intent}{math}` attaches screen-reader alt-text to a
single ambiguous symbol (e.g. `\sin^{-1}`).

## Not yet done (contributions welcome)

- **The committee page needs a ruling from the Graduate School.** Their page is
  internally inconsistent: section 4 says to use the handout template and *"type
  the words as they appear"*, while the committee-page section says to use their
  **PDF** template and *"combine the PDF into your manuscript"*. This class
  typesets its own, which matches section 4 and Hurtado's template but not a
  literal reading of the merge instruction. Ask before filing; the class can do
  either.
- Optional semantic `<Title>` / `<H1>` tagging of the title and committee pages
  (currently auto-tagged as paragraphs — valid, but less precise for a screen
  reader; see Hurtado's manual-tagging approach).
- Per-chapter bibliographies and appendix bookmark labels.

`UNRlogoN.pdf` is the University of Nevada, Reno "N" mark used on the committee
approval page, as distributed with Hurtado's template.
