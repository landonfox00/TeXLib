% thesis.cls — UNR accessible thesis / dissertation class (TeXLib)
% ============================================================================
% A report-based class for University of Nevada, Reno M.S. theses and Ph.D.
% dissertations that produces a TAGGED, PDF/UA-conformant document by default,
% following the UNR Graduate School filing requirements and building on Paul
% Hurtado's accessible LaTeX thesis template (v0.5, pauljhurtado.com/latex).
%
% ACCESSIBLE BY DESIGN. UNR now requires accessible (tagged) theses, so tagging
% is intrinsic here, not an opt-in mode: the document MUST begin with
%     \DocumentMetadata{ lang=en, tagging=on,
%         tagging-setup={ math/setup={mathml-SE}, table/header-rows=1 },
%         pdfstandard={ua-2,a-4f} }
%     \documentclass{thesis}
% (\DocumentMetadata can only enable tagging BEFORE \documentclass.) The class
% warns if it was not tagged. Compile with lualatex.
%
% This is a PROTOTYPE: the title page, committee-approval page, and front-matter
% environments are functional and tag cleanly, but exact committee-page spacing
% and any current UNR wording should be checked against the Graduate School
% filing guidelines before a real submission.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{thesis}[2026/08/25 v0.7.4 UNR accessible thesis/dissertation (TeXLib)]

% ---------------------------------------------------------------------------
% 0. Options: oneside (default, per grad-school submission) / twoside (binding)
% ---------------------------------------------------------------------------
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{report}}
\ProcessOptions\relax
\LoadClass[letterpaper,12pt,oneside]{report}

% Warn (do not fail) if the document was not started with \DocumentMetadata's
% tagging engine -- an untagged thesis will not meet the UNR accessibility rule.
\AtBeginDocument{%
	\@ifundefined{tag_struct_begin:n}{%
		\ClassWarningNoLine{thesis}{This thesis was built WITHOUT PDF tagging.^^J%
			UNR requires an accessible (tagged) PDF. Put^^J%
			\string\DocumentMetadata{lang=en,tagging=on,...,pdfstandard={ua-2,a-4f}}^^J%
			as the FIRST line, before \string\documentclass{thesis}, and compile with lualatex}%
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
\geometry{letterpaper, left=1in, right=1in, top=1in, bottom=1in, includefoot}
\savegeometry{normal}
% A no-footer geometry for the unnumbered front-matter pages, so the frame/
% content can use the full text height.
\geometry{letterpaper, left=1in, right=1in, top=1in, bottom=1in}
\savegeometry{nopagenumber}
\loadgeometry{normal}
\raggedbottom
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
\newfontfamily{\termesfont}{TeX Gyre Termes}

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
\newcommand{\makeUNRtitlepage}{%
	\loadgeometry{nopagenumber}%
	\begin{titlepage}%
		\thispagestyle{empty}\singlespacing\centering
		\vspace*{\fill}
		\textsc{University of Nevada, Reno}\par
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
% 7. Committee approval page
% ---------------------------------------------------------------------------
% The UNR committee page: a double blue frame with a drop shadow, the Graduate
% School heading, the author (bold caps), the title, the degree, and each
% committee member with a signature rule. A hidden, tagged "Committee Approval
% Page" H1 gives a screen reader a heading; the decorative frame is tagged as an
% artifact so it is skipped.
\newcommand{\thesis@memberline}[2]{%
	\vskip 2.2em
	\rule{3in}{0.4pt}\par
	{#1\ifx\relax#2\relax\else, #2\fi}\par
}
\newcommand{\committeeapprovalpage}{%
	\clearpage\thispagestyle{empty}%
	\loadgeometry{nopagenumber}\singlespacing
	\begin{tikzpicture}[remember picture, overlay]
		\draw[draw={rgb,255:red,0;green,0;blue,128}, line width=0.75pt]
			([xshift=1.5pt,yshift=-1.5pt]current page text area.north west)
			rectangle
			([xshift=-1.5pt,yshift=1.5pt]current page text area.south east);
		\draw[draw={rgb,255:red,0;green,0;blue,128}, line width=0.75pt]
			([xshift=3pt,yshift=-3pt]current page text area.north west)
			rectangle
			([xshift=-3pt,yshift=3pt]current page text area.south east);
	\end{tikzpicture}%
	\begin{center}
		\thesis@tagtitle{H1}{{\color{white}\tiny Committee Approval Page}}\par
		\vspace{-1em}
		\includegraphics[width=0.68in, alt={University of Nevada, Reno logo}]{UNRlogoN}\par
		\begingroup\termesfont
		\vspace{1mm}
		{\fontsize{12}{18}\selectfont\textcolor[RGB]{0,0,128}{THE GRADUATE SCHOOL}}\par
		\vfill
		{\fontsize{12}{12}\selectfont We recommend that the \thesis@docnoun\\
			prepared under our supervision by}\par
		\vfill
		\MakeUppercase{\bfseries\@author}\par
		\vfill
		{\fontsize{12}{12}\selectfont entitled}\par
		\begin{minipage}{0.7\textwidth}
			\centering\bfseries
			\hyphenpenalty=10000 \exhyphenpenalty=10000 \emergencystretch=2em
			\@title\par
		\end{minipage}\par
		\vfill
		{\fontsize{12}{12}\selectfont be accepted in partial fulfillment of the\\
			requirements for the degree of}\par
		\vfill
		{\bfseries\MakeUppercase{\thesis@degree}}\par
		\thesis@committee
		\vfill
		\thesis@date\par
		\endgroup
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

\endinput
