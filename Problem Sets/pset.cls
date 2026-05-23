% pset.cls
% UNR Problem-Set / Homework Class — TeXLib unified style
%
% Designed to fill the gap between autoexam (heavy: randomized, versioned)
% and didactic (lecture notes). Use this for assignment sheets where you
% want both the problem-with-parts machinery of an exam AND the embedded
% definitions/theorems/examples of a notes file.
%
% Build modes:
%   * Default                 — clean problem set (solution boxes invisible).
%   * \StudentMode            — clean problem set + watermarked blank space
%                                inside each \begin{solution} box for
%                                handwriting.
%   * \ShowKey or
%     \ShowSolutions          — answer-key build: solutions visible.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{pset}[2026/05/08 v1.0 UNR Problem Sets (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[11pt]{article}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage[T1]{fontenc}
\RequirePackage{lmodern}
\RequirePackage[margin=1in]{geometry}
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{etoolbox}
\RequirePackage{basic-utilities}    % shared math macros, tikz config, tasks (grid layout)
\RequirePackage{calc, adjustbox, changepage, needspace}
\RequirePackage[shortlabels]{enumitem}
\RequirePackage{fancyhdr, lastpage}
\RequirePackage{tocloft, multirow}
\RequirePackage[many]{tcolorbox}
\RequirePackage{amsmath, amssymb, amsthm, mathtools}
\RequirePackage{cancel}
\RequirePackage{graphicx}
\RequirePackage{tikz, pgfplots}
\pgfplotsset{compat=1.18}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric,
				datavisualization, fit, calc, backgrounds}
\RequirePackage{hyperref}
\hypersetup{colorlinks=true, urlcolor=blue, linkcolor=black, citecolor=black}
\RequirePackage[capitalise,nameinlink]{cleveref}

\RequirePackage{xstring}            % for \IfInteger in problem's optional arg
\RequirePackage{course-metadata}

% Bibliography: biblatex with the biber backend. Loaded last so it can hook
% into hyperref/cleveref/amsmath. The \printreferences command below is a
% \maketitle-style wrapper that prints the cited references with a clean
% section heading; place it near the bottom of the document.
%
% Documents supply their bib file via \addbibresource{...} (typically in
% the course's preamble.tex). Citations use the normal biblatex \cite, e.g.
% \cite[1.2]{beardsley} renders as "[Bea21, 1.2]" under the alphabetic style.
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
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}

% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\tl_new:N \g__pset_number_tl
\tl_new:N \g__pset_title_tl
\tl_new:N \g__pset_due_tl
\tl_new:N \g__pset_instructions_tl

\keys_define:nn { meta } {
	pset-number       .tl_gset:N = \g__pset_number_tl,
	pset-title        .tl_gset:N = \g__pset_title_tl,
	pset-due          .tl_gset:N = \g__pset_due_tl,
	pset-instructions .tl_gset:N = \g__pset_instructions_tl,
	% Bare keys also accepted (no risk of cross-class collision because
	% no other class defines `pset-due`, etc.; the bare `number`/`title`
	% already collide with didactic, so we only namespace those.)
	due               .tl_gset:N = \g__pset_due_tl,
}

\NewExpandableDocumentCommand{\GetPsetNumber}{}{ \tl_use:N \g__pset_number_tl }
\NewExpandableDocumentCommand{\GetPsetDue}{}{ \tl_use:N \g__pset_due_tl }
\NewExpandableDocumentCommand{\GetPsetTitle}{}{
	\tl_if_empty:NTF \g__pset_title_tl
		{ Problem~Set~\GetPsetNumber }
		{ \tl_use:N \g__pset_title_tl }
}
\NewExpandableDocumentCommand{\GetPsetInstructions}{}{
	\tl_if_empty:NTF \g__pset_instructions_tl
		{ Show~all~work~for~full~credit.~ Box~or~circle~final~answers.~
			Late~submissions~lose~10\%~per~day. }
		{ \tl_use:N \g__pset_instructions_tl }
}

\ExplSyntaxOff

% ==============================================================================
% 4. PAGE LAYOUT — METADATA-DRIVEN HEADERS
% ==============================================================================
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\bfseries \GetPsetTitle}
\fancyhead[R]{\GetCourse}
\fancyfoot[L]{\GetTerm}
\fancyfoot[C]{\thepage\ of \pageref{LastPage}}
\fancyfoot[R]{\ifkey \textit{Answer Key} \else \GetInstructor \fi}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}

% Title-page style: same footer as the regular `fancy` style, but the
% header and its rule are suppressed so the title block sits at the top
% of page 1 cleanly. Applied automatically by \maketitle below; users who
% want the header back on page 1 can call \thispagestyle{fancy} after it.
\fancypagestyle{firstpage}{%
	\fancyhf{}%
	\fancyfoot[L]{\GetTerm}%
	\fancyfoot[C]{\thepage\ of \pageref{LastPage}}%
	\fancyfoot[R]{\ifkey \textit{Answer Key} \else \GetInstructor \fi}%
	\renewcommand{\headrulewidth}{0pt}%
	\renewcommand{\footrulewidth}{0.4pt}%
}

% ==============================================================================
% 5. TITLE BLOCK
% ==============================================================================
\renewcommand{\maketitle}{%
	\thispagestyle{firstpage}%
	\begin{center}
		{\LARGE \bfseries \GetPsetTitle} \\[0.4em]
		{\Large \GetCourse \space\textendash\space \GetTerm} \\[0.2em]
		\ifkey \textit{Answer Key} \\[0.4em] \fi
		\ifx\\\GetPsetDue\\\else
			\textbf{Due:}\ \GetPsetDue \\[0.4em]
		\fi
		\ifstudent
			{\small Name:\ \underline{\hspace{6cm}}}
		\fi
	\end{center}
	\medskip
	\noindent\fbox{\fbox{\parbox{\dimexpr\textwidth-2\fboxsep-2\fboxrule\relax}{%
		\centering\footnotesize \GetPsetInstructions
	}}}
	\medskip
}

% ==============================================================================
% 6. PROBLEM ENVIRONMENT (top-level numbered problems)
% ==============================================================================
% \begin{problem}[<points>] ... \end{problem}
%
% Auto-numbers; optional argument prints "(<points> points)" inline.
\newcounter{problem}
\renewcommand{\theproblem}{\arabic{problem}}

% Optional argument is dual-purpose:
%   numeric  ->  "(N points)"           (e.g. \begin{problem}[10])
%   text     ->  small italic "(<text>)" (e.g. \begin{problem}[Beardsley Wk1 \#1])
\NewDocumentEnvironment{problem}{ o }
{%
	\par\medskip
	\refstepcounter{problem}%
	\noindent\textbf{Problem \theproblem.}%
	\IfValueT{#1}{%
		\IfInteger{#1}{%
			\ \textit{(#1 points)}%
		}{%
			\ {\small\textit{(#1)}}%
		}%
	}\space\ignorespaces
}{%
	\par\medskip
}

% \begin{parts} \part ... \part ... \end{parts}
% Use inside (or outside) a problem.  Labelled (a), (b), (c), ...
%
% Notes:
%   1. article.cls defines \part as a top-level sectioning command. We
%      locally rebind \part to \item inside the parts env so the natural
%      syntax works without colliding with the sectioning command outside.
%   2. basic-utilities.sty defines `parts` via \newlist (labels: bold "a.").
%      pset.cls overrides that here to use "(a)" labels and the \part
%      shorthand, so we MUST use \renewenvironment -- \newenvironment would
%      raise "Command \parts already defined" and silently leave the
%      upstream definition in place.
\renewenvironment{parts}
	{\begin{enumerate}[label=\textbf{(\alph*)}, leftmargin=*,
						topsep=2pt, parsep=2pt]%
		\let\part\item}
	{\end{enumerate}}

% ==============================================================================
% 7. THEOREM-LIKE ENVIRONMENTS (boxed via tcolorbox, shared TeXLib styling)
% ==============================================================================
% The tcolorbox styles live in texlib-theorems.sty. As of the May 2026
% consolidation pass, pset uses the canonical TeXLib colored-thin-rule look
% (the old sharp-black-frame `psetstyle` is retired). This class keeps its
% own \newtheorem taxonomy and flat numbering.
\RequirePackage{texlib-theorems}

\theoremstyle{plain}
\newtheorem{theorem}{Theorem}
\newtheorem{definition}[theorem]{Definition}
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{proposition}[theorem]{Proposition}
\newtheorem{lemma}[theorem]{Lemma}

\theoremstyle{remark}
\newtheorem{example}[theorem]{Example}
\newtheorem{remark}[theorem]{Remark}
\newtheorem{note}[theorem]{Note}
\newtheorem{recall}[theorem]{Recall}

% Bind each boxed environment to a shared style. remark/note/recall are
% deliberately left as plain inline theorems (no box), matching didactic.
\tcolorboxenvironment{theorem}{texlibtheorem}
\tcolorboxenvironment{definition}{texlibdefinition}
\tcolorboxenvironment{corollary}{texlibtheorem}
\tcolorboxenvironment{proposition}{texlibproposition}
\tcolorboxenvironment{lemma}{texlibtheorem}
\tcolorboxenvironment{example}{texlibexample}

% ==============================================================================
% 8. SOLUTION ENVIRONMENT — gated on \ShowKey/\ShowSolutions/\StudentMode
% ==============================================================================
% \begin{solution}[<student-blank-height>] ... \end{solution}
%
% Behaviour:
%   * \ShowKey OR \ShowSolutions  → body visible, blue-tinted
%   * \StudentMode                → blank box of <height>, watermarked
%   * default                     → no box at all (body discarded)
%
% Implementation: in default mode we redefine `solution` to be a
% body-discarding environment via the `comment` package, replacing
% the tcolorbox version. This keeps the box completely off the page
% (no spacing artifacts).
\NewTColorBox{solution}{ O{3cm} }{
	enhanced, breakable,
	colback=white, colframe=black,
	title={\textbf{Solution:}},
	code={
		\ifsolutions
			\tcbset{ colback=blue!5, colframe=blue!40!black }
		\else
			\ifkey
				\tcbset{ colback=blue!5, colframe=blue!40!black }
			\else
				\ifstudent
					\tcbset{
						height=#1,
						upperbox=invisible,
						watermark text={\textit{Show your work here}},
						watermark color=black!10
					}
				\fi
			\fi
		\fi
	}
}

\RequirePackage{comment}
\AtBeginDocument{%
	\ifsolutions\else
		\ifkey\else
			\ifstudent\else
				% Default mode: discard solution bodies entirely.
				\let\solution\@undefined
				\let\endsolution\@undefined
				\excludecomment{solution}%
			\fi
		\fi
	\fi
}

% ==============================================================================
% 9. HINT ENVIRONMENT — always visible, lighter than a solution
% ==============================================================================
% \begin{hint} ... \end{hint}
\NewTColorBox{hint}{ }{
	enhanced, breakable,
	colback=yellow!5, colframe=yellow!40!black,
	boxrule=0.4pt, sharp corners,
	title={\textbf{Hint:}},
	fonttitle=\small,
	before skip=8pt, after skip=8pt
}

% ==============================================================================
% 10. READINGS ENVIRONMENT — bold "Readings" header + indented list, no box
% ==============================================================================
% Use under a day-subsection (or anywhere) to list assigned readings.
%
%   \begin{readings}
%       \item Leinster §1.1–1.2.
%       \item Riehl, \emph{Category Theory in Context}, §1.1.
%   \end{readings}
%
% Lightweight on purpose: bold header, en-dash bullets, tight vertical
% spacing.  Always visible regardless of build mode.
\newenvironment{readings}
	{%
		\par\addvspace{6pt}%
		\noindent{\bfseries Readings.}\par\nopagebreak
		\begin{itemize}[leftmargin=2em, topsep=2pt, parsep=2pt,
						itemsep=2pt, label={\textendash}]%
	}
	{%
		\end{itemize}\addvspace{4pt}%
	}

% ==============================================================================
% 11. MATH UTILITIES
% ==============================================================================
% Math macros (\mbb, \abs, \lrp, \dd, \deriv, \inte, \todo, ...) are provided
% by texlib-mathutils.sty, loaded transitively via basic-utilities.sty above.

\endinput
