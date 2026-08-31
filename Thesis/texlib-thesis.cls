% texlib-thesis.cls — accessible thesis / dissertation class (TeXLib)
% ============================================================================
% A report-based class for M.S. theses and Ph.D. dissertations that produces a
% TAGGED, PDF/UA-conformant document by default. Built at the University of
% Nevada, Reno on Paul Hurtado's accessible LaTeX thesis template (v0.5,
% pauljhurtado.com/latex), but the conformance machinery is not UNR's and there
% is no reason it should only serve UNR.
%
% ACCESSIBLE BY DESIGN. Tagging is intrinsic here, not an opt-in mode: the
% document MUST begin with
%     \DocumentMetadata{ lang=en, tagging=on,
%         tagging-setup={ math/setup={mathml-AF}, table/header-rows=1 },
%         pdfstandard={ua-2,a-4f} }
%     \documentclass{texlib-thesis}
% (\DocumentMetadata can only enable tagging BEFORE \documentclass.) The class
% warns if it was not tagged. Compile with lualatex.
%
% WHAT IS AND IS NOT INSTITUTION-SPECIFIC
%
% Everything here — the tagged-PDF stack, the trivlist-free theorem
% environments, the MathML intent helper, the front-matter machinery, the
% degree/committee metadata model — applies to any graduate school. What does
% NOT is the part every graduate school writes its own rules for: the title
% page, the committee-approval page, and the margin/spacing figures. Those live
% in a PROFILE:
%
%     Thesis/profiles/<name>.tex     loaded by \documentclass[profile=<name>]
%
% A profile binds \thesistitlepage and \thesisapprovalpage and may call
% \thesissetgeometry / \thesissetspacing. `unr' is the reference profile and
% reproduces exactly what this class emitted before the split; `generic' is a
% plain, conformant fallback for an institution with no profile yet. Writing a
% new one means overriding two page macros — see Thesis/README.md.
%
% `thesis.cls' remains as a thin wrapper loading this class with profile=unr,
% so every existing \documentclass{thesis} document is unaffected.
%
% This is a PROTOTYPE: the pages are functional and tag cleanly, but exact
% spacing and any current wording should be checked against your own graduate
% school's filing guidelines before a real submission.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{texlib-thesis}[2026/08/25 v0.7.4 Accessible thesis/dissertation (TeXLib)]

% ---------------------------------------------------------------------------
% 0. Options: oneside (default, per grad-school submission) / twoside (binding)
% ---------------------------------------------------------------------------
% profile=<name> selects the institution profile (see the header). Declared
% before the catch-all so it is consumed here rather than passed to report,
% which would reject it. Default `generic': a class loaded with no profile must
% still produce a conformant document, not an error -- the wrapper thesis.cls
% passes profile=unr.
\newcommand{\thesis@profile}{generic}
\DeclareOption*{%
	\@expandtwoargs\in@{=}{\CurrentOption}%
	\ifin@
		\expandafter\thesis@setprofile\CurrentOption\@nil
	\else
		\PassOptionsToClass{\CurrentOption}{report}%
	\fi
}
\def\thesis@setprofile#1=#2\@nil{%
	\def\@tempa{#1}\def\@tempb{profile}%
	\ifx\@tempa\@tempb
		\renewcommand{\thesis@profile}{#2}%
	\else
		\PassOptionsToClass{#1=#2}{report}%
	\fi
}
\ProcessOptions\relax
\LoadClass[letterpaper,12pt,oneside]{report}

% The institution name a profile can set, used in warnings and by the pages.
% Empty by default: a generic build must not claim an affiliation it has no
% basis for, and "your graduate school" is the honest phrasing when unset.
\newcommand{\thesis@institution}{}
\newcommand{\thesisinstitution}[1]{\renewcommand{\thesis@institution}{#1}}
\newcommand{\thesis@whose}{%
	\ifx\thesis@institution\@empty your~graduate~school\else\thesis@institution\fi}

% Warn (do not fail) if the document was not started with \DocumentMetadata's
% tagging engine. An untagged thesis meets no accessibility rule anywhere, and
% a growing number of graduate schools now require a tagged filing.
\AtBeginDocument{%
	\@ifundefined{tag_struct_begin:n}{%
		\ClassWarningNoLine{texlib-thesis}{This thesis was built WITHOUT PDF tagging.^^J%
			An accessible (tagged) PDF is required by \thesis@whose. Put^^J%
			\string\DocumentMetadata{lang=en,tagging=on,...,pdfstandard={ua-2,a-4f}}^^J%
			as the FIRST line, before \string\documentclass, and compile with lualatex}%
	}{}%
}

% ---------------------------------------------------------------------------
% 1. Page geometry + spacing  (UNR: 1in margins; double-spaced body)
% ---------------------------------------------------------------------------
\RequirePackage{geometry}
\RequirePackage{setspace}
% (@ is already a letter inside a .cls -- no \makeatletter needed here, and a
%  \makeatother would wrongly disable it for the rest of the class.)
% UNR requires 1.0in on ALL FOUR sides, with no exception for binding -- tables
% and appendices included. The manuscript is filed electronically ("no hard
% copies will be produced"), so the wider inner margin a bound copy would want
% is not something the filed document may have: an inner=1.25in twoside build
% is 0.25in out of spec on every odd page and would be caught by the Graduate
% School's margin check.
%
% twoside is therefore a LAYOUT option only -- it still governs where headers
% and the \cleardoublepage blanks fall -- and no longer changes the margins.
% Anyone who wants a binding offset for a personal printed copy should add it at
% print time, not in the filed PDF.
% The figures are a PROFILE's to set -- 1in all round and double spacing is the
% common case and the default, not a universal rule. \thesissetgeometry re-runs
% both saved snapshots together, because a profile that changed only `normal'
% would leave the front-matter pages on the old margins: the two must never
% disagree, and making that impossible is cheaper than documenting it.
\newcommand{\thesis@margins}{left=1in, right=1in, top=1in, bottom=1in}
\newcommand{\thesissetgeometry}[1]{%
	\renewcommand{\thesis@margins}{#1}%
	\thesis@applygeometry
}
% \geometry's argument is parsed by keyval, which does NOT expand macros first:
% passing \thesis@margins straight in makes keyval read the whole list as one
% undefined key ("left=1in, right=1in, top=1in, bottom=1in undefined"). \edef
% the list, then hand over the expansion. Safe because the value is plain text.
\newcommand{\thesis@applygeometry}{%
	\edef\thesis@geo@tmp{letterpaper, \thesis@margins, includefoot}%
	\expandafter\geometry\expandafter{\thesis@geo@tmp}%
	\savegeometry{normal}%
	% A no-footer geometry for the unnumbered front-matter pages, so the frame/
	% content can use the full text height.
	\edef\thesis@geo@tmp{letterpaper, \thesis@margins}%
	\expandafter\geometry\expandafter{\thesis@geo@tmp}%
	\savegeometry{nopagenumber}%
	\loadgeometry{normal}%
}
\thesis@applygeometry
\raggedbottom
% Spacing is likewise a filing rule, not a typographic one: \thesissetspacing
% takes `double' (default), `onehalf' or `single'.
\newcommand{\thesissetspacing}[1]{%
	\def\@tempa{#1}%
	\def\@tempb{single}\ifx\@tempa\@tempb\singlespacing\fi
	\def\@tempb{onehalf}\ifx\@tempa\@tempb\onehalfspacing\fi
	\def\@tempb{double}\ifx\@tempa\@tempb\doublespacing\fi
}
\doublespacing

% ---------------------------------------------------------------------------
% 2. Fonts + math  (accessible math needs the Unicode-engine stack)
% ---------------------------------------------------------------------------
% The main face is Latin Modern -- fontspec's default, since nothing overrides
% it. (An earlier version of this comment claimed New Computer Modern "via
% fontsetup"; fontsetup is not loaded and never was. Verified with pdffonts on a
% real build: LMRoman throughout, TeX Gyre Termes only on the committee page.)
%
% Latin Modern satisfies UNR's "Times New Roman, Arial, or a similarly clear
% font" and every face is embedded, which the Graduate School requires. If you
% would rather file in a literally Times-like face, the class already loads TeX
% Gyre Termes for the committee page -- add \setmainfont{TeX Gyre Termes} after
% \documentclass. That is a typographic choice, not a conformance one, so the
% class does not make it for you.
%
% unicode-math (loaded AFTER the other math packages) drives MathML math
% tagging. TeX Gyre Termes gives the committee page its required Times-like face.
\RequirePackage{amsmath}
\RequirePackage{amsthm}
\RequirePackage[no-math]{fontspec}
\RequirePackage{unicode-math}
% \termesfont is NOT declared here: a Times-like face is a requirement of one
% graduate school's committee page, not of a tagged thesis. profiles/unr.tex
% declares it, which is also why profiles load after fontspec.

% ---------------------------------------------------------------------------
% 3. Graphics, tables, references
% ---------------------------------------------------------------------------
\RequirePackage{graphicx}
\RequirePackage{tikz}
\RequirePackage{tikzpagenodes}   % current page text area — committee-page frame
\RequirePackage{xcolor}
\RequirePackage{caption}
% booktabs: this section is called "tables" and shipped none. A thesis has
% tables, UNR requires a List of Tables when it does, and \hline rules are the
% classic giveaway of an unstyled LaTeX table. Also tags cleanly -- the rules are
% spacing, not content, so they add nothing to the structure tree.
\RequirePackage{booktabs}
\RequirePackage[title]{appendix}
\RequirePackage[hidelinks, linktoc=page, pdfusetitle]{hyperref}
% cleveref direct, NOT texlib-crossref: that package exists because
% cleveref's amsthm patch leaves a block-level list open under tagging and
% kills the first definition-style environment. This class never uses
% amsthm's theorem environments -- section 9 defines trivlist-free ones of
% its own -- so \@begintheorem is never patched and the fault cannot fire.
% Keeping cleveref also keeps the per-environment \crefname naming set up
% there, which the zref-clever shim does not reproduce.
\RequirePackage[capitalise, nameinlink]{cleveref}
% Bibliography (biber backend). The document adds its .bib with \addbibresource
% and prints the list with \makereferences, which titles it and adds it to the
% ToC as an unnumbered chapter (matching the front-matter pages).
\RequirePackage[backend=biber, style=numeric, sorting=nyt, maxbibnames=10, giveninits=true]{biblatex}
\newcommand{\makereferences}{%
	\clearpage
	\printbibliography[heading=bibintoc, title={References}]%
}

% ---------------------------------------------------------------------------
% 4. Degree / committee metadata
% ---------------------------------------------------------------------------
% \title and \author come from the kernel (pdfusetitle feeds them to the PDF
% title/author). The rest are thesis-specific.
\newcommand{\thesis@degree}{Master of Science}
\newcommand{\thesis@docnoun}{thesis}      % lowercase: "a thesis submitted..."
\newcommand{\thesis@DocNoun}{Thesis}      % Title case: "Thesis Advisor"
\newcommand{\thesis@program}{Mathematics}
\newcommand{\thesis@advisor}{Advisor Name, Ph.D.}
\newcommand{\thesis@date}{May, 20XX}
\newcommand{\graddegree}[1]{\renewcommand{\thesis@degree}{#1}}
\newcommand{\gradprogram}[1]{\renewcommand{\thesis@program}{#1}}
\newcommand{\gradadvisor}[1]{\renewcommand{\thesis@advisor}{#1}}
\newcommand{\graddate}[1]{\renewcommand{\thesis@date}{#1}}
% \doctype{thesis|dissertation}: sets both the lowercase and Title-case nouns
% and the default degree, so M.S. vs Ph.D. is one edit.
\newcommand{\doctype}[1]{%
	\def\@tempa{#1}\def\@tempb{dissertation}%
	\ifx\@tempa\@tempb
		\renewcommand{\thesis@docnoun}{dissertation}%
		\renewcommand{\thesis@DocNoun}{Dissertation}%
		\renewcommand{\thesis@degree}{Doctor of Philosophy}%
	\else
		\renewcommand{\thesis@docnoun}{thesis}%
		\renewcommand{\thesis@DocNoun}{Thesis}%
		\renewcommand{\thesis@degree}{Master of Science}%
	\fi
}
% Committee: \committeemember{Name, Degree}{Role}; \committee stores the list.
\newcommand{\thesis@committee}{}
\newcommand{\committeemember}[2]{%
	\g@addto@macro\thesis@committee{\thesis@memberline{#1}{#2}}%
}

% ---------------------------------------------------------------------------
% 5. Title page  (UNR: unnumbered, centered; title manually tagged)
% ---------------------------------------------------------------------------
% Emit the title/heading content #2. (A future refinement can wrap it in an
% explicit \tagstructbegin{tag=#1} so a screen reader announces it as a Title/
% H1 -- see Hurtado's template -- but that manual tagging must be perfectly
% balanced against the auto-tagger; the auto-tagged paragraph is already valid.)
\newcommand{\thesis@tagtitle}[2]{#2}

% \thesistitlepage and \thesisapprovalpage are the two PROFILE HOOKS. The
% definitions here are the institution-neutral fallbacks; a profile file
% \renewcommand's them. They are separate from the rest of the class because
% they are the only parts whose CONTENT a graduate school dictates -- everything
% else is conformance machinery that is the same everywhere.
%
% The generic title page carries the same information in the same order as a
% typical filing, with the institution line omitted when none is set rather than
% invented. It is deliberately plain: a fallback that looked official would
% invite someone to file it unmodified.
\newcommand{\thesistitlepage}{%
	\loadgeometry{nopagenumber}%
	\begin{titlepage}%
		\thispagestyle{empty}\singlespacing\centering
		\vspace*{\fill}
		\ifx\thesis@institution\@empty\else
			\textsc{\thesis@institution}\par
		\fi
		\vfill\vfill\vfill
		\thesis@tagtitle{Title}{{\large\bfseries\@title}}\par
		\vfill\vfill
		A \thesis@docnoun{} submitted in partial fulfillment of the\\
		requirements for the degree of \thesis@degree{} in\\
		\thesis@program\par
		\vfill\vfill
		by\\[1em]{\bfseries\@author}\par
		\vfill\vfill
		\thesis@advisor~/ \thesis@DocNoun{} Advisor\par
		\vfill
		\thesis@date\par
		\vspace*{\fill}
	\end{titlepage}%
	\loadgeometry{normal}%
}

% ---------------------------------------------------------------------------
% 6. Copyright page  (optional)
% ---------------------------------------------------------------------------
\newcommand{\makecopyrightpage}{%
	\clearpage\thispagestyle{empty}%
	\vspace*{\fill}
	{\centering\large Copyright by \@author\par All Rights Reserved.\par}%
	\vspace*{\fill}\clearpage
}

% ---------------------------------------------------------------------------
% 7. Committee approval page  (profile hook)
% ---------------------------------------------------------------------------
% Every graduate school has one and no two look alike -- signature rules vs.
% typed names, a seal or none, its own heading wording. So the layout is a
% profile's, and only the pieces every version needs live here: the committee
% list and the per-member line.
%
% A hidden, tagged "Committee Approval Page" H1 gives a screen reader a heading
% for a page that is otherwise a wall of centred text; any decorative frame a
% profile draws should be tagged as an artifact so it is skipped.
\newcommand{\thesis@memberline}[2]{%
	\vskip 2.2em
	\rule{3in}{0.4pt}\par
	{#1\ifx\relax#2\relax\else, #2\fi}\par
}
% Institution-neutral fallback: the substance (who approved what, for which
% degree) with no borrowed insignia. Deliberately plain -- see \thesistitlepage.
\newcommand{\thesisapprovalpage}{%
	\clearpage\thispagestyle{empty}%
	\loadgeometry{nopagenumber}\singlespacing
	\begin{center}
		\thesis@tagtitle{H1}{{\color{white}\tiny Committee Approval Page}}\par
		\ifx\thesis@institution\@empty\else
			{\large\textsc{\thesis@institution}}\par\vspace{1em}
		\fi
		{\large THE GRADUATE SCHOOL}\par
		\vfill
		We recommend that the \thesis@docnoun\\prepared under our supervision by\par
		\vfill
		\MakeUppercase{\bfseries\@author}\par
		\vfill
		entitled\par
		\begin{minipage}{0.7\textwidth}
			\centering\bfseries
			\hyphenpenalty=10000 \exhyphenpenalty=10000 \emergencystretch=2em
			\@title\par
		\end{minipage}\par
		\vfill
		be accepted in partial fulfillment of the\\requirements for the degree of\par
		\vfill
		{\bfseries\MakeUppercase{\thesis@degree}}\par
		\thesis@committee
		\vfill
		\thesis@date\par
	\end{center}%
	\loadgeometry{normal}\doublespacing\clearpage
}

% ---------------------------------------------------------------------------
% 8. Front-matter pages (Abstract, Dedication, Acknowledgements, ...)
% ---------------------------------------------------------------------------
% \begin{frontmatterpage}{Abstract} ... \end{frontmatterpage}
% Unnumbered chapter-level heading, added to the ToC, centered title.
\NewDocumentEnvironment{frontmatterpage}{m}{%
	\clearpage
	\chapter*{#1}%
	\addcontentsline{toc}{chapter}{#1}%
}{\clearpage}

% \frontmatter / \mainmatter: roman page numbers for the front matter, arabic
% (restarted) for the body -- the standard thesis pagination.
\newcommand{\frontmatter}{\clearpage\pagenumbering{roman}}
\newcommand{\mainmatter}{\clearpage\pagenumbering{arabic}}

% ---------------------------------------------------------------------------
% 9. Accessible theorem environments (trivlist-free)
% ---------------------------------------------------------------------------
% amsthm builds theorems on \trivlist, tagged as a list <L>, so the body nests
% as <P>/<Sect> inside <L> -- a PDF/UA structure violation. Define the theorem
% environments as plain headed paragraphs instead, chapter-numbered.
%
% \thesis@mkthm{env}{Label}{bodyfont}: each environment gets its OWN counter,
% chapter-reset and displayed as <chapter>.<n>. A per-environment counter (rather
% than one shared "thm" counter) is what lets \cref/\Cref name the reference
% correctly ("Theorem 1.2", "Definition 1.1") -- cleveref keys a reference on its
% counter, so a shared counter would print "??" for every type but one.
\newcommand{\thesis@mkthm}[3]{% #1 = env, #2 = Label, #3 = body font
	\newcounter{#1}[chapter]%
	\@namedef{the#1}{\thechapter.\arabic{#1}}%
	\@ifundefined{crefname}{}{\crefname{#1}{#2}{#2s}\Crefname{#1}{#2}{#2s}}%
	\NewDocumentEnvironment{#1}{o}{%
		\par\addvspace\medskipamount\noindent
		\refstepcounter{#1}%
		{\bfseries #2~\csname the#1\endcsname}%
		\IfNoValueF{##1}{\space{\normalfont(##1)}}%
		{\bfseries .}\hskip.5em\relax #3\ignorespaces
	}{\par\addvspace\medskipamount}%
}
% plain style: italic body (theorem family)
\thesis@mkthm{theorem}{Theorem}{\itshape}
\thesis@mkthm{lemma}{Lemma}{\itshape}
\thesis@mkthm{corollary}{Corollary}{\itshape}
\thesis@mkthm{proposition}{Proposition}{\itshape}
% definition style: upright body
\thesis@mkthm{definition}{Definition}{}
\thesis@mkthm{example}{Example}{}
\thesis@mkthm{remark}{Remark}{}

% ---------------------------------------------------------------------------
% 10. MathML intent helpers (screen-reader alt-text for ambiguous notation)
% ---------------------------------------------------------------------------
% Single math node only (luamml drops the intent on multi-node expressions).
% \ThesisMathIntent{intent}{math}; e.g. inverse trig / a single custom symbol.
\newcommand{\ThesisMathIntent}[2]{%
	\@ifundefined{MathMLintent}{#2}{\MathMLintent{#1}{#2}}%
}

% ---------------------------------------------------------------------------
% 11. Institution profile
% ---------------------------------------------------------------------------
% Loaded LAST, on purpose: a profile redefines the two page macros and may call
% \thesissetgeometry / \thesissetspacing / \thesisinstitution, all of which must
% land on top of the defaults above rather than under them. Loading it late also
% means a profile can use anything the class loaded -- fontspec faces, tikz,
% graphicx -- without ordering rules of its own.
%
% Resolution is by \InputIfFileExists on a relative subpath, the same mechanism
% syllabus.cls uses for policy statements, so it works identically from a
% TEXINPUTS checkout (Thesis/ is a search segment) and from an installed TEXMF
% tree (kpathsea resolves the subpath).
%
% `generic' is the built-in default and has no file: the definitions above ARE
% the generic profile. Asking for it explicitly is therefore not an error and
% must not warn.
\def\thesis@generic{generic}
\ifx\thesis@profile\thesis@generic
\else
	\InputIfFileExists{profiles/\thesis@profile.tex}{}{%
		\ClassWarningNoLine{texlib-thesis}{No profile `\thesis@profile' found^^J%
			(looked for profiles/\thesis@profile.tex). Falling back to the^^J%
			institution-neutral pages -- check the name, or add the file}%
	}%
\fi

\endinput
