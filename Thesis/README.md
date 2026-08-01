# Thesis — accessible UNR thesis / dissertation class

`thesis.cls` is a report-based LaTeX class for University of Nevada, Reno M.S.
theses and Ph.D. dissertations that produces a **tagged, PDF/UA-conformant**
document — meeting UNR's accessibility requirement — following the Graduate
School filing guidelines and building on Paul Hurtado's accessible thesis
template (v0.5, <https://www.pauljhurtado.com/latex/>).

## Status

Prototype. The example (`thesis-template.tex`) builds with **0 errors** and
passes veraPDF for both **PDF/UA-2** (accessibility) and **PDF/A-4f** (archival).
See *Not yet done* below for what remains before a real submission.

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

- Verify the committee-page spacing and wording against the current Graduate
  School filing guidelines.
- Optional semantic `<Title>` / `<H1>` tagging of the title and committee pages
  (currently auto-tagged as paragraphs — valid, but less precise for a screen
  reader; see Hurtado's manual-tagging approach).
- List of tables, per-chapter bibliographies, appendix bookmark labels.
- CI: the class needs LuaLaTeX + tagging + Biber, a different build profile from
  the teaching-class smoke suite, so it is verified manually with veraPDF for now.

`UNRlogoN.pdf` is the University of Nevada, Reno "N" mark used on the committee
approval page, as distributed with Hurtado's template.
