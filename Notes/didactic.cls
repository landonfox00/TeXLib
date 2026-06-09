% didactic.cls
% UNR Lecture Notes Class -- TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{didactic}[2026/05/09 v3.1 UNR Lecture Notes (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[unit-number=3, unit-title={Limits}, instructor=true]{didactic}
% Any option containing "=" is a metadata key=value pair; every other option
% (11pt, twoside, ...) is forwarded to article. Metadata is applied at the end
% of section 3 (after coursemeta.tex loads, so document options win) by reading
% \@raw@classoptionslist directly — that list preserves spaces in values, which
% the \CurrentOption seen here does not. \DeclareOption* therefore only forwards
% the non-metadata options; the key=value ones still pass through it (a no-op)
% so the kernel marks them used. Safe because no base-class option uses key=value.
\DeclareOption*{%
	\@expandtwoargs\in@{=}{\CurrentOption}%
	\ifin@\else
		\PassOptionsToClass{\CurrentOption}{article}%
	\fi
}
\ProcessOptions\relax
\LoadClass[11pt]{article}

% A class-option value containing a comma (e.g. a date like {May 2, 2026}) is
% split by the kernel's option parser into a stray fragment with no "=", which
% would be reported as an "unused global option". The real values are consumed
% from \@raw@classoptionslist below, so discard those spurious leftovers.
\AtEndOfClass{\global\let\@unusedoptionlist\@empty}

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

% \overview{...} -- content-setter for the lecture's abstract prose. The overview
% is long-form text, so it cannot live in the class option list; this lets a
% document set it without a raw \metasetup call. Routes through the unit-overview
% key (overview is its backward-compat alias).
\NewDocumentCommand{\overview}{ +m }{ \metasetup{ unit-overview = {#1} } }

% Apply document metadata from the class option list now that the keys above and
% coursemeta.tex are loaded (so document options override coursemeta defaults).
% Read \@raw@classoptionslist, not \CurrentOption, to keep spaces in values.
\ExplSyntaxOn
\cs_if_exist:cT { @raw@classoptionslist } {
	\tl_set:Nv    \l_tmpa_tl    { @raw@classoptionslist }
	\clist_set:NV \l_tmpa_clist \l_tmpa_tl
	\clist_map_inline:Nn \l_tmpa_clist {
		\tl_if_in:nnT { #1 } { = } { \keys_set:nn { meta } { #1 } }
	}
}
\ExplSyntaxOff

% ==============================================================================
% 4. PAGE LAYOUT -- METADATA-DRIVEN HEADERS
% ==============================================================================
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = unit title  C = build badge  R = section. Shared mechanism;
% the badge wording is class-specific (lecture notes -> "Instructor Version").
\SetTeXLibBuildBadge{\ifsolutions Instructor Version\fi}
\SetTeXLibHeader{\bfseries\GetUnitTitle}{\TeXLibBuildBadge}{Section \thesection}
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
% texlib-theorems.sty; the \TeXLibTheorems enabler that binds environments to
% them lives in texlib-thmenv.sty. This class opts into the full taxonomy with
% section-based numbering and the four-letter aliases.
\RequirePackage{texlib-theorems}
\RequirePackage{texlib-thmenv}

% Problem-bank engine -- so didactic-class documents (e.g. exam-review
% handouts) can \getproblem{id} from the course's bank without each file
% needing its own \usepackage{texlib-problembank} + \loadbank boilerplate.
\RequirePackage{texlib-problembank}

% One declaration per environment (and its unnumbered `*` twin), each with the
% canonical TeXLib styling, section-based shared numbering (master counter:
% theorem), and the four-letter aliases (defn, conv, ques, exer, exam, notn,
% chal + their `*` forms). The catalog mapping each name to its amsthm style
% (plain/definition/remark) and tcolorbox style lives in texlib-thmenv.sty.
% `remark`/`remark*` stay plain inline (no box); `recall`/`notation` use the
% gray note rule.
\TeXLibTheorems[numbering=section, aliases=true]{
	theorem, corollary, lemma, conjecture, proposition,
	definition, convention, procedure, challenge,
	exercise, example, notation,
	remark, question, recall
}

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
% Shares the canonical TeXLib geometry (texlibbase: same rule width via
% \texlibrulewidth, same margin bleed/position as the theorem boxes). The
% green solved-rule and the dashed blank-answer rule are the same width and
% sit in the same place as every other TeXLib rule.
\NewTColorBox{solution}{ O{3cm} }{
	texlibbase,
	code={
		\ifsolutions
			\tcbset{
				colback=green!3!white,
				borderline west={\texlibrulewidth}{0pt}{green!50!black},
				before upper={\textbf{Solution.}\par\smallskip},
			}
		\else
			\tcbset{
				height=#1,
				upperbox=invisible,
				colback=white,
				borderline west={\texlibrulewidth}{0pt}{black!40, dash pattern=on 3pt off 2pt},
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
% 7.5. ENVIRONMENT ALIASES
% ==============================================================================
% The four-letter theorem synonyms (defn, conv, ques, exer, exam, notn, chal
% and their `*` twins) are generated by \TeXLibTheorems[aliases=true] in
% section 6 -- each a thin \NewDocumentEnvironment wrapping \begin{<real>} so
% the tcolorbox hooks (keyed by env name) still fire. Only the solution-box
% synonym is class-local, so it lives here.
%
% \solution is built with \NewTColorBox (not \tcolorboxenvironment), so the
% box machinery lives directly inside the \solution / \endsolution macros and
% a \let-alias would in principle work.  We use the same wrapper pattern for
% consistency and to pass the optional [<height>] argument through cleanly.
% (No \soln*: the solution box has no unnumbered variant.)
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

% ==============================================================================
% 9. PROBLEM-BANK AUTO-LOAD
% ==============================================================================
% Mirrored from autoexam.cls. didactic-class documents -- exam-review handouts,
% reference packets, etc. -- can \getproblem{id} pull from the course's bank
% without per-document boilerplate. The resolution order is identical to
% autoexam's so the same bank-path value works in both classes.
\AtBeginDocument{%
	\@ifundefined{GetBankPath}{}{%
		\edef\@tmpbankpath{\GetBankPath}%
		\ifx\@tmpbankpath\empty\else
			\IfFileExists{\@tmpbankpath}{%
				\loadbank{\@tmpbankpath}%
			}{%
				\@ifundefined{GetCourseMetaDir}{%
					\loadbank{\@tmpbankpath}%
				}{%
					\edef\@tmpbankresolved{\GetCourseMetaDir\@tmpbankpath}%
					\IfFileExists{\@tmpbankresolved}{%
						\loadbank{\@tmpbankresolved}%
					}{%
						\loadbank{\@tmpbankpath}%
					}%
				}%
			}%
		\fi
	}%
}

% ==============================================================================
% Structural hang: section/subsection headings, the TOC title, the bibliography
% heading, and the running header/footer all hang onto one outer left edge.
% Loaded LAST so its redefinitions land on top of the article defaults.
% ==============================================================================
\RequirePackage{texlib-sectionhang}

\endinput
