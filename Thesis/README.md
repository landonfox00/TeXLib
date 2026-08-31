# Thesis — accessible thesis / dissertation class

`texlib-thesis.cls` is a report-based LaTeX class for M.S. theses and Ph.D.
dissertations that produces a **tagged, PDF/UA-conformant** document. It was
built at the University of Nevada, Reno on Paul Hurtado's accessible thesis
template (v0.5, <https://www.pauljhurtado.com/latex/>), but the conformance
machinery is not UNR's, so it is not confined to UNR.

The parts a graduate school actually dictates — the title page, the
committee-approval page, and the margin/spacing figures — live in an
[institution profile](#institution-profiles). `unr` is the reference profile;
an institution with no profile yet still gets a conformant document from the
neutral defaults.

**`\documentclass{thesis}` still works and is unchanged.** It is now a
two-line wrapper that loads this class with `profile=unr`, and the rendered
output is pixel-identical to the pre-split class across all ten pages of the
shipped template.

## Institution profiles

```latex
\documentclass[profile=unr]{texlib-thesis}   % or just \documentclass{thesis}
\documentclass{texlib-thesis}                % neutral defaults
```

A profile is one file, `Thesis/profiles/<name>.tex`, loaded last so it can use
anything the class loaded. It owns exactly three things:

| What | How |
|---|---|
| The institution name | `\thesisinstitution{...}` |
| The two pages | `\renewcommand{\thesistitlepage}{...}`, `\renewcommand{\thesisapprovalpage}{...}` |
| The filing figures | `\thesissetgeometry{left=1in, ...}`, `\thesissetspacing{double\|onehalf\|single}` |

Everything else — the tagged-PDF stack, the trivlist-free theorem
environments, `\ThesisMathIntent`, the front-matter machinery, the
degree/committee metadata model, biblatex — is shared and needs no profile.

**Writing one.** Copy [`profiles/unr.tex`](profiles/unr.tex), which is
commented as the reference, and replace the two page bodies. The committee list
(`\committeemember`) and its per-member signature rule are provided by the
class, so a minimal profile is a name plus two layouts. Profiles for other
institutions are welcome — see the caveat in
[Status](#status) about checking current wording before filing.

Asking for a profile that does not exist warns and falls back to the neutral
pages rather than failing the build; asking for `generic` explicitly is the
same as asking for nothing, and does not warn.

#### The institution worklist

`thesis_institutions.py` maintains the list of US institutions that could use a
profile, and scaffolds one.

```
python thesis_institutions.py fetch                  # refresh from IPEDS
python thesis_institutions.py next                   # next one with no profile
python thesis_institutions.py scaffold <slug>        # write a skeleton
python thesis_institutions.py list --state NV
```

The list is **derived, not curated**: it comes from the federal IPEDS
institutional-characteristics survey, filtered to institutions whose highest
offering is a master's or above — 2,135 of them, 1,283 doctorate-granting.
A hand-assembled list of two thousand university names would be wrong on day one
in ways nobody could see, since a plausible name for an institution that does
not exist reads exactly like a correct one. `institutions.source` records where
the committed copy came from and when.

Work proceeds **alphabetically**, and `next` reads the answer off the profiles
directory, so there is no cursor to lose or disagree with.

`scaffold` writes a skeleton, not a profile. Every institution-specific value in
it is a placeholder, it renders the neutral pages until someone replaces them,
and it carries a provenance header — source URL, access date, who read it — that
must be filled in. IPEDS supplies an institution'''s name and nothing else; it
cannot tell you a margin. **Nobody should file a thesis against a scaffolded
profile until a person has read that graduate school'''s own requirements.**

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
| Body restarts at Arabic `1`, bottom-center, no running header | conforms |
| Table of Contents, **List of Tables**, List of Figures, in that order | conforms |
| Fonts embedded, 10-12pt | conforms (12pt; all faces embedded) |
| Committee page wording and layout | **needs the Graduate School's answer -- see below** |

`twoside` no longer widens the inner margin. UNR requires 1.0in on all four
sides with no binding exception, and the manuscript is filed electronically
("no hard copies will be produced"), so a 1.25in inner margin was 0.25in out of
spec on every odd page. `twoside` remains available for headers and blank-page
behavior; add a binding offset at print time for a personal copy, not in the
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

## The accessibility report

UNR requires an accessibility report to be filed alongside the manuscript. An
accessible build writes one automatically — `<base>_accessible-report.html`,
veraPDF's PDF/UA-2 conformance report, beside the tagged PDF. Building through
`--texlib-mode=accessible` (or Sublime's Accessible variant) produces the pair;
by hand it is:

```
verapdf --flavour ua2 --format html --success thesis-template.pdf > thesis-report.html
```

`--success` itemizes every passed check (~1 MB) rather than only the failures
(~20 KB); for a filing artifact, itemized is the safer choice. Needs veraPDF
and a JRE — the build says so and carries on if it is missing.

**What format the Graduate School actually accepts is unconfirmed.** Their
guidance points at Adobe Acrobat Pro, whose checker emits its own artifact also
called an "Accessibility Report"; veraPDF validates PDF/UA-2 far more strictly
(to the ISO clause) but it is a *different* document. Ask before filing. See
the note in the Not-yet-done section below.

## Authoring

```latex
\DocumentMetadata{lang=en, tagging=on,
  tagging-setup={math/setup={mathml-AF}, table/header-rows=1},
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
single ambiguous symbol (for example, `\sin^{-1}`).

## Not yet done (contributions welcome)

- **The committee page needs a ruling from the Graduate School.** Their page is
  internally inconsistent: section 4 says to use the handout template and *"type
  the words as they appear"*, while the committee-page section says to use their
  **PDF** template and *"combine the PDF into your manuscript"*. This class
  typesets its own, which matches section 4 and Hurtado's template but not a
  literal reading of the merge instruction. Ask before filing; the class can do
  either.
- **The accessibility report's required format is unresolved.** Hurtado's
  2026-08-25 department email states that accessibility reports must now be
  submitted with thesis documents, but his guidelines doc does not yet define
  one — no contents, no producing tool, no submission process; he has said that
  doc needs updating. The class emits a veraPDF report (above) on the assumption
  that ISO-clause-level PDF/UA-2 conformance is at least sufficient evidence.
  Confirm with the Graduate School, or at his forthcoming workshop, before
  filing on that assumption.
- Optional semantic `<Title>` / `<H1>` tagging of the title and committee pages
  (currently auto-tagged as paragraphs — valid, but less precise for a screen
  reader; see Hurtado's manual-tagging approach).
- Per-chapter bibliographies and appendix bookmark labels.

`UNRlogoN.pdf` is the University of Nevada, Reno "N" mark used on the committee
approval page, as distributed with Hurtado's template.
