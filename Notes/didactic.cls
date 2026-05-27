% didactic.cls
% UNR Lecture Notes Class -- TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{didactic}[2026/05/09 v3.1 UNR Lecture Notes (TeXLib)]

% ==============================================================================
% 0. OPTIONS PASSED TO ARTICLE
% ==============================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[11pt]{article}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
% basic-utilities transitively loads texlib-corepkg (fontenc/lmodern/geometry,
% expl3/xparse/ifthen/etoolbox, xcolor, amsmath/amssymb/amsthm/mathtools,
% texlib-mathutils, graphicx, tikz/pgfplots + standard libraries,
% hyperref + canonical hypersetup) plus the heavy-class extras (siunitx,
% caption, tasks, extra tikz libraries: datavisualization, fit, calc,
% backgrounds).
\RequirePackage{basic-utilities}
\RequirePackage{xstring}
\RequirePackage{calc, adjustbox, changepage, needspace}
\RequirePackage[shortlabels]{enumitem}
\RequirePackage{fancyhdr, lastpage}
\RequirePackage{tocloft, multirow}
\RequirePackage[many]{tcolorbox}
\RequirePackage{cancel}
\RequirePackage[capitalise,nameinlink]{cleveref}
\RequirePackage{course-metadata}

% Bibliography: biblatex with the biber backend. Loaded last so it can hook
% into hyperref/cleveref/amsmath. The \printreferences command below is a
% \maketitle-style wrapper that prints the cited references with a clean
% section heading; place it near the bottom of the document.
%
% Documents supply their bib file via \addbibresource{...} (typically in
% the course's preamble.tex). Citations use the normal biblatex \cite.
\RequirePackage[backend=biber, style=alphabetic, maxbibnames=10, giveninits=true]{biblatex}
% Postnotes in this library are exercise / section numbers, not pages, so
% suppress the default "p." / "pp." prefix that biblatex prepends.
\DeclareFieldFormat{postnote}{#1}
\DeclareFieldFormat{multipostnote}{#1}
\NewDocumentCommand{\printreferences}{}{%
	\bigskip
	\printbibliography[title={References}]%
}

% ==============================================================================
% 2. BUILD FLAGS -- UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}
\RequirePackage{texlib-footer}

% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS  (incl. TOC switch)
% ==============================================================================
\newif\ifshowtoc \showtoctrue        % default: include TOC in \maketitle

\ExplSyntaxOn
	\tl_new:N \g__didactic_unit_type_tl
	\tl_new:N \g__didactic_unit_number_tl
	\tl_new:N \g__didactic_unit_title_tl
	\tl_new:N \g__didactic_overview_tl

	\keys_define:nn { meta } {
		unit            .tl_gset:N = \g__didactic_unit_type_tl,
		unit-number     .tl_gset:N = \g__didactic_unit_number_tl,
		unit-title      .tl_gset:N = \g__didactic_unit_title_tl,
		unit-overview   .tl_gset:N = \g__didactic_overview_tl,
		% Backward-compat aliases (old names continue to work)
		number          .tl_gset:N = \g__didactic_unit_number_tl,
		title           .tl_gset:N = \g__didactic_unit_title_tl,
		overview        .tl_gset:N = \g__didactic_overview_tl,
		% Build flags addressable from \meta{...}
		solutions  .code:n    = { \str_if_eq:nnT { #1 } { true } { \solutionstrue } },
		student    .code:n    = { \str_if_eq:nnT { #1 } { true } { \studenttrue \instructorfalse } },
		instructor .code:n    = { \str_if_eq:nnT { #1 } { true } { \instructortrue \studentfalse \solutionstrue } },
		draft      .code:n    = { \str_if_eq:nnT { #1 } { true } { \drafttrue } },
		toc        .code:n    = {
			\str_if_eq:nnT { #1 } { false } { \showtocfalse }
			\str_if_eq:nnT { #1 } { true  } { \showtoctrue  }
		},
	}

	\NewExpandableDocumentCommand{\GetUnitType}  {}{ \tl_use:N \g__didactic_unit_type_tl }
	\NewExpandableDocumentCommand{\GetUnitNumber}{}{ \tl_use:N \g__didactic_unit_number_tl }
	\NewExpandableDocumentCommand{\GetUnitTitle} {}{
		\tl_if_empty:NTF \g__didactic_unit_number_tl
			{ \tl_use:N \g__didactic_unit_title_tl }
			{
				\tl_use:N \g__didactic_unit_type_tl   \space
				\tl_use:N \g__didactic_unit_number_tl :~
				\tl_use:N \g__didactic_unit_title_tl
			}
	}
	\NewExpandableDocumentCommand{\GetOverview}{}{ \tl_use:N \g__didactic_overview_tl }
\ExplSyntaxOff

% ==============================================================================
% 4. PAGE LAYOUT -- METADATA-DRIVEN HEADERS
% ==============================================================================
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Headers are class-specific to lecture notes:
%   L: unit title    C: "Instructor Version" if solutions are on    R: section
\fancyhead[L]{\bfseries \GetUnitTitle}
\fancyhead[C]{\ifsolutions\textit{Instructor Version}\fi}
\fancyhead[R]{Section \thesection}
\renewcommand{\headrulewidth}{0.4pt}
% Footer is the shared TeXLib layout (course | page | institution)
\SetTeXLibFooter

% Title page (first page of lecture notes): no header, no header rule.
% Shared footer remains in place.
\fancypagestyle{titlepage}{%
	\fancyhf{}%
	\SetTeXLibFooter
	\renewcommand{\headrulewidth}{0pt}%
}

% ==============================================================================
% 5. TITLE BLOCK (metadata-driven, optional TOC)
% ==============================================================================
\ExplSyntaxOn
\RenewDocumentCommand{\maketitle}{}{
	\begin{center}
		{\LARGE \bfseries \GetUnitTitle} \\[0.5em]
		{\Large \GetCourse \space\textendash\space \GetTerm} \\[0.2em]
		\ifstudent {\small Name:~\underline{\hspace{5cm}}} \fi
	\end{center}
	% \tl_if_blank:V (not \tl_if_empty:N) so an overview that's literally
	% just whitespace -- e.g. overview = { } -- is treated the same as
	% omitting the key entirely. Otherwise that lone space would render an
	% empty Abstract heading with a blank body. The :V expansion variant
	% V-expands the variable to its contents before the blank test, which
	% is what we want; \tl_if_blank itself is an :n-type function so :NF
	% would not be a recognised signature.
	\tl_if_blank:VF \g__didactic_overview_tl {
		\begin{abstract} \GetOverview \end{abstract}
	}
	\ifshowtoc
		\tableofcontents
		\vspace{1em}
	\fi
	\thispagestyle{titlepage}
	% Section number = unit number, so the lecture's \subsection headings render
	% as N.1, N.2, ... and the [section]-numbered theorems as N.1, N.2, ...
	% (lecture notes use \subsection throughout and never call \section). This
	% replaces the per-file "\setcounter{section}{\GetUnitNumber}" that used to
	% sit just after \maketitle. Guarded so a note with no unit-number key (an
	% empty \GetUnitNumber) does not trip "missing number" in \setcounter.
	\tl_if_empty:NF \g__didactic_unit_number_tl {
		\setcounter{section}{\GetUnitNumber}
	}
}
\ExplSyntaxOff

% ==============================================================================
% 6. THEOREM-LIKE ENVIRONMENTS  (colored thin left rule + 2% bg tint)
% ==============================================================================
% The tcolorbox styles (texlibbase + the texlib* family overlays) live in
% texlib-theorems.sty. This class keeps its own \newtheorem taxonomy and
% section-based numbering, and binds each environment to a shared style.
\RequirePackage{texlib-theorems}

% Theorem-family declarations (italic body via theoremstyle plain)
\theoremstyle{plain}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{conjecture}[theorem]{Conjecture}
\newtheorem{proposition}[theorem]{Proposition}

% Definition family (roman body, term being defined italicized inline)
\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}
\newtheorem{convention}[theorem]{Convention}
\newtheorem{procedure}[theorem]{Procedure}
\newtheorem{challenge}[theorem]{Challenge}

% Exercise / Example / Notation (italic label, roman body, decoration via boxes below).
% Note: prior versions of this class used `example` as the env name for
% Exercise content. As of 2026-05-09, `example` prints "Example" and
% `exercise` prints "Exercise" -- migrate any \begin{example} that meant
% Exercise to \begin{exercise}.
\theoremstyle{definition}
\newtheorem{exercise}[theorem]{Exercise}
\newtheorem{example}[theorem]{Example}
\newtheorem{notation}[theorem]{Notation}

\theoremstyle{remark}
\newtheorem{remark}[theorem]{Remark}
\newtheorem{question}[theorem]{Question}
\newtheorem{recall}[theorem]{Recall}

% Apply per-family tcolorbox styles (defined in texlib-theorems.sty)
\tcolorboxenvironment{theorem}    {texlibtheorem}
\tcolorboxenvironment{lemma}      {texlibtheorem}
\tcolorboxenvironment{corollary}  {texlibtheorem}
\tcolorboxenvironment{conjecture} {texlibtheorem}
\tcolorboxenvironment{proposition}{texlibproposition}
\tcolorboxenvironment{definition} {texlibdefinition}
\tcolorboxenvironment{convention} {texlibdefinition}
\tcolorboxenvironment{procedure}  {texlibprocedure}
\tcolorboxenvironment{challenge}  {texlibquestion}
\tcolorboxenvironment{exercise} {texlibexample}
\tcolorboxenvironment{example}  {texlibexample}
\tcolorboxenvironment{notation} {texlibnote}
\tcolorboxenvironment{question}   {texlibquestion}
\tcolorboxenvironment{recall}     {texlibnote}
% (remark deliberately left as plain inline, no rule/tint)

% Unnumbered (starred) twins of every environment above. Same headings, same
% theorem styles, and the same tcolorbox styling (remark* left plain, like
% remark). Use \begin{theorem*} ... \end{theorem*} for a result that consumes
% no number; the starred forms take no shared-counter argument.
\theoremstyle{plain}
\newtheorem*{theorem*}{Theorem}
\newtheorem*{corollary*}{Corollary}
\newtheorem*{lemma*}{Lemma}
\newtheorem*{conjecture*}{Conjecture}
\newtheorem*{proposition*}{Proposition}

\theoremstyle{definition}
\newtheorem*{definition*}{Definition}
\newtheorem*{convention*}{Convention}
\newtheorem*{procedure*}{Procedure}
\newtheorem*{challenge*}{Challenge}
\newtheorem*{exercise*}{Exercise}
\newtheorem*{example*}{Example}
\newtheorem*{notation*}{Notation}

\theoremstyle{remark}
\newtheorem*{remark*}{Remark}
\newtheorem*{question*}{Question}
\newtheorem*{recall*}{Recall}

\tcolorboxenvironment{theorem*}    {texlibtheorem}
\tcolorboxenvironment{lemma*}      {texlibtheorem}
\tcolorboxenvironment{corollary*}  {texlibtheorem}
\tcolorboxenvironment{conjecture*} {texlibtheorem}
\tcolorboxenvironment{proposition*}{texlibproposition}
\tcolorboxenvironment{definition*} {texlibdefinition}
\tcolorboxenvironment{convention*} {texlibdefinition}
\tcolorboxenvironment{procedure*}  {texlibprocedure}
\tcolorboxenvironment{challenge*}  {texlibquestion}
\tcolorboxenvironment{exercise*} {texlibexample}
\tcolorboxenvironment{example*}  {texlibexample}
\tcolorboxenvironment{notation*} {texlibnote}
\tcolorboxenvironment{question*}   {texlibquestion}
\tcolorboxenvironment{recall*}     {texlibnote}
% (remark* deliberately left as plain inline, no rule/tint)

% ==============================================================================
% 6b. CONTEXT-SENSITIVE ENUMERATE LABELS
% ==============================================================================
% Top-level enumerate uses bold roman numerals (i., ii., ...) inside the
% bold-titled theorem environments, and emphasised (italic) roman numerals
% everywhere else -- ordinary body text plus the remark-style environments
% (remark / question / recall), whose titles are not bold.
%
% A boolean is raised at the start of each bold-titled environment via
% etoolbox's \AtBeginEnvironment.  Because a LaTeX environment forms a group,
% the flag reverts automatically at \end{...}, so a list sitting outside the
% box falls back to the \emph branch.  The flag is read when each label is
% typeset, so one bare \begin{enumerate} adapts to its surrounding context.
%
% The four-letter aliases (defn, conv, exer, exam, notn, chal, ...) call the
% real environments internally, so hooking the real names below is sufficient.
\newif\if@didactic@thmenum
\@didactic@thmenumfalse
\setlist[enumerate,1]{%
	label = {\if@didactic@thmenum\textbf{\roman*.}\else\emph{\roman*.}\fi},
	ref   = \roman*,
}
\newcommand{\@didactic@enumbold}[1]{\AtBeginEnvironment{#1}{\@didactic@thmenumtrue}}
% amsthm plain style (theorem family):
\@didactic@enumbold{theorem}
\@didactic@enumbold{corollary}
\@didactic@enumbold{lemma}
\@didactic@enumbold{conjecture}
\@didactic@enumbold{proposition}
% amsthm definition style (definition family):
\@didactic@enumbold{definition}
\@didactic@enumbold{convention}
\@didactic@enumbold{procedure}
\@didactic@enumbold{challenge}
\@didactic@enumbold{exercise}
\@didactic@enumbold{example}
\@didactic@enumbold{notation}
% remark, question, recall intentionally excluded -- they keep \emph labels.

% ==============================================================================
% 7. SOLUTION ENVIRONMENT  (minimal style: matches the colored-rule aesthetic)
% ==============================================================================
% Behaviour:
%   - \ifsolutions (set by 'solutions = true' or 'instructor = true'):
%       thin green left rule + 2% tint + inline "Solution." label
%   - otherwise (default, 'solutions = false', or 'student = true'):
%       dashed thin grey left rule outlining a fixed-height blank box
\NewTColorBox{solution}{ O{3cm} }{
	enhanced, breakable,
	sharp corners, frame hidden,
	boxrule=0pt,
	left=8pt, right=4pt, top=4pt, bottom=4pt,
	before skip=10pt, after skip=10pt,
	code={
		\ifsolutions
			\tcbset{
				colback=green!3!white,
				borderline west={1.5pt}{-6pt}{green!50!black},
				before upper={\textbf{Solution.}\par\smallskip},
			}
		\else
			\tcbset{
				height=#1,
				upperbox=invisible,
				colback=white,
				borderline west={0.5pt}{-6pt}{black!40, dash pattern=on 3pt off 2pt},
			}
		\fi
	}
}

% \answer  --  inline answer prefix for use inside the question env (always visible)
% Ends the current paragraph, inserts a blank line of vertical space (\bigskip,
% roughly one baseline), prints "Answer." in italics, and yields a space so
% the answer text continues inline. Usage:
%   \begin{question}
%       What is X?
%       \answer X is ...
%   \end{question}
\newcommand{\answer}{\par\bigskip\noindent\textit{Answer.}\space}

% ==============================================================================
% 7.5. FOUR-LETTER ENVIRONMENT ALIASES
% ==============================================================================
% Compact synonyms that let authors write e.g. \begin{defn}...\end{defn}
% as a drop-in synonym for \begin{definition}...\end{definition}.
%
% IMPLEMENTATION NOTE.  These cannot be \let-aliases of \definition /
% \enddefinition (etc.).  The theorem-family environments above are wrapped via
% \tcolorboxenvironment, which installs \BeforeBeginEnvironment /
% \AfterEndEnvironment hooks keyed by the environment NAME string.  Those hooks
% only fire when LaTeX sees \begin{definition} / \end{definition}; a \let copy
% executes the bare amsthm theorem macros and bypasses the tcolorbox entirely.
% So each alias is a thin \NewDocumentEnvironment that internally calls
% \begin{<real>} ... \end{<real>}, which lets the hooks fire and the box
% appear.  The optional [<note>] argument that amsthm theorems accept is
% passed through unchanged.
\NewDocumentEnvironment{defn}{o}
  {\IfNoValueTF{#1}{\begin{definition}}{\begin{definition}[#1]}}
  {\end{definition}}
\NewDocumentEnvironment{conv}{o}
  {\IfNoValueTF{#1}{\begin{convention}}{\begin{convention}[#1]}}
  {\end{convention}}
\NewDocumentEnvironment{ques}{o}
  {\IfNoValueTF{#1}{\begin{question}}{\begin{question}[#1]}}
  {\end{question}}
\NewDocumentEnvironment{exer}{o}
  {\IfNoValueTF{#1}{\begin{exercise}}{\begin{exercise}[#1]}}
  {\end{exercise}}
\NewDocumentEnvironment{exam}{o}
  {\IfNoValueTF{#1}{\begin{example}}{\begin{example}[#1]}}
  {\end{example}}
\NewDocumentEnvironment{notn}{o}
  {\IfNoValueTF{#1}{\begin{notation}}{\begin{notation}[#1]}}
  {\end{notation}}
\NewDocumentEnvironment{chal}{o}
  {\IfNoValueTF{#1}{\begin{challenge}}{\begin{challenge}[#1]}}
  {\end{challenge}}
% Starred (unnumbered) synonyms, mirroring the starred theorem environments in
% section 6 -- same \begin{<real>*} indirection so the tcolorbox hooks fire, and
% the same passthrough of the optional [<note>] argument. (No \soln*: the
% solution box has no unnumbered variant.)
\NewDocumentEnvironment{defn*}{o}
  {\IfNoValueTF{#1}{\begin{definition*}}{\begin{definition*}[#1]}}
  {\end{definition*}}
\NewDocumentEnvironment{conv*}{o}
  {\IfNoValueTF{#1}{\begin{convention*}}{\begin{convention*}[#1]}}
  {\end{convention*}}
\NewDocumentEnvironment{ques*}{o}
  {\IfNoValueTF{#1}{\begin{question*}}{\begin{question*}[#1]}}
  {\end{question*}}
\NewDocumentEnvironment{exer*}{o}
  {\IfNoValueTF{#1}{\begin{exercise*}}{\begin{exercise*}[#1]}}
  {\end{exercise*}}
\NewDocumentEnvironment{exam*}{o}
  {\IfNoValueTF{#1}{\begin{example*}}{\begin{example*}[#1]}}
  {\end{example*}}
\NewDocumentEnvironment{notn*}{o}
  {\IfNoValueTF{#1}{\begin{notation*}}{\begin{notation*}[#1]}}
  {\end{notation*}}
\NewDocumentEnvironment{chal*}{o}
  {\IfNoValueTF{#1}{\begin{challenge*}}{\begin{challenge*}[#1]}}
  {\end{challenge*}}
% \solution is built with \NewTColorBox (not \tcolorboxenvironment), so the
% box machinery lives directly inside the \solution / \endsolution macros and
% a \let-alias would in principle work.  We use the same wrapper pattern for
% consistency and to pass the optional [<height>] argument through cleanly.
\NewDocumentEnvironment{soln}{O{3cm}}
  {\begin{solution}[#1]}
  {\end{solution}}

% ==============================================================================
% 8. MATH UTILITIES
% ==============================================================================
% Math macros (\mbb, \abs, \lrp, \dd, \deriv, \inte, \todo, ...) are provided
% by texlib-mathutils.sty, loaded transitively via basic-utilities.sty above.

% Section/subsection numbering is enabled. Each section file overrides
% \thesection to be its textbook label (e.g., \renewcommand{\thesection}{A.7}),
% so subsections then auto-number A.7.1, A.7.2, ... and theorems become A.7.1, A.7.2.
\setcounter{secnumdepth}{2}

% \labeledsection{label}{title} -- one-line wrapper for the
% "set \thesection, then start the section" pattern used by section files
% whose number does not follow the chapter's auto-numbering scheme
% (e.g. textbook labels like R.1, A.7, 3.5/4.5).
%
% Example:
%   \labeledsection{R.1}{Real Numbers and Order of Operations}
% is equivalent to:
%   \section{Real Numbers and Order of Operations}
\NewDocumentCommand{\labeledsection}{m m}{%
	\renewcommand{\thesection}{#1}%
	\section{#2}%
}

% TOC spacing & font: bold entries; 3em column for the (label-shaped) section number
\setlength{\cftsecnumwidth}{3em}
\setlength{\cftsubsecnumwidth}{4em}
\setlength{\cftsecindent}{0pt}
\setlength{\cftsubsecindent}{3em}
\renewcommand{\cftsecfont}{\bfseries}
\renewcommand{\cftsecpagefont}{\bfseries}
\renewcommand{\cftsubsecfont}{\bfseries}
\renewcommand{\cftsubsecpagefont}{\bfseries}

\endinput
