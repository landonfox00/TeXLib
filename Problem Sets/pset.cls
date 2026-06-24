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
% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[pset-number=3, pset-title={Weekly Set}, due=2026-06-15]{pset}
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
% caption, tasks, extra tikz libraries).
\RequirePackage{basic-utilities}
\RequirePackage{calc, adjustbox, changepage, needspace}
\RequirePackage[shortlabels]{enumitem}
\RequirePackage{fancyhdr, lastpage}
\RequirePackage{tocloft, multirow}
\RequirePackage[many]{tcolorbox}
\RequirePackage{cancel}
\RequirePackage[capitalise,nameinlink]{cleveref}
\RequirePackage{xstring}            % for \IfInteger in problem's optional arg
\RequirePackage{course-metadata}

% Shared document-instructions mechanism (inline / file / default, file > inline
% > default). \TeXLibDeclareInstructions{pset} below mints \GetPsetInstructions,
% \IfPsetInstructions{File,Inline}, and \pset@input@userinstructions.
\RequirePackage{texlib-instructions}

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

\keys_define:nn { meta } {
	pset-number       .tl_gset:N = \g__pset_number_tl,
	pset-title        .tl_gset:N = \g__pset_title_tl,
	pset-due          .tl_gset:N = \g__pset_due_tl,
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

\ExplSyntaxOff

% Instructions: mints the pset-instructions inline key, \GetPsetInstructions,
% \IfPsetInstructions{File,Inline}, and \pset@input@userinstructions. The default
% wording now lives in pset-instructions.tex (so it is a SyncTeX inverse-search
% target); pset-instructions-file lives in course-metadata.sty (set per set via
% \meta or course-wide in coursemeta.tex).
\TeXLibDeclareInstructions{pset}

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
% 4. PAGE LAYOUT — METADATA-DRIVEN HEADERS
% ==============================================================================
\RequirePackage{texlib-footer}   % shared footer: Course | page X of Y | Institution
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = pset title  C = build badge  R = term + section. (R was \GetCourse,
% which duplicated the footer-left course; term/section removes that redundancy.)
\SetTeXLibBuildBadge{\ifkey Answer Key\fi}
\SetTeXLibHeader{\bfseries\GetPsetTitle}{\TeXLibBuildBadge}{\GetTermSection}
\SetTeXLibFooter
% Rule bleed comes from texlib-sectionhang's [LR] offset (loaded at the end of
% this class), so \TeXLibRuleBleed must NOT also be called.

% Title-page style: same footer as the regular `fancy` style, but the
% header and its rule are suppressed so the title block sits at the top
% of page 1 cleanly. Applied automatically by \maketitle below; users who
% want the header back on page 1 can call \thispagestyle{fancy} after it.
\fancypagestyle{firstpage}{%
	\fancyhf{}%
	\SetTeXLibFooter
	\renewcommand{\headrulewidth}{0pt}%
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
	% Instructions: a user-set pset-instructions-file controls its own layout (no
	% box); inline text and the default pset-instructions.tex are boxed.
	\IfPsetInstructionsFile{%
		\pset@input@userinstructions
	}{%
		\noindent\fbox{\fbox{\parbox{\dimexpr\textwidth-2\fboxsep-2\fboxrule\relax}{%
			\centering\footnotesize \TeXLibInstructionsInlineOrDefault{pset}%
		}}}%
	}%
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

% Top-level enumerate: bold lowercase-roman labels (i., ii., iii., ...).
% The `parts` environment above sets its own inline label, so it is
% unaffected; only a bare \begin{enumerate} picks this up.  ref=\roman*
% keeps \cref output (e.g. "item ii") consistent with the printed label.
\setlist[enumerate,1]{label=\textbf{\roman*.}, ref=\roman*}

% ==============================================================================
% 7. THEOREM-LIKE ENVIRONMENTS (boxed via tcolorbox, shared TeXLib styling)
% ==============================================================================
% The tcolorbox styles live in texlib-theorems.sty; the \TeXLibTheorems enabler
% that binds environments to them lives in texlib-thmenv.sty. As of the May 2026
% consolidation pass, pset uses the canonical TeXLib colored-thin-rule look (the
% old sharp-black-frame `psetstyle` is retired). This class opts into a subset
% of the shared taxonomy with FLAT numbering (one shared counter, not section-
% based) and no four-letter aliases.
\RequirePackage{texlib-theorems}
\RequirePackage{texlib-thmenv}

% One declaration per environment (and its unnumbered `*` twin), each with the
% canonical TeXLib styling and a flat shared counter (master: theorem). The
% catalog (env -> amsthm style + tcolorbox style) lives in texlib-thmenv.sty,
% so `definition` is definition-style and `example` definition-style here too,
% matching didactic. note/recall carry the gray note rule; remark stays plain
% inline (no box). (note* is also defined, guarded, in the Category Theory
% preamble; its \ifcsname check skips that copy when this one is present.)
\TeXLibTheorems[numbering=flat]{
	theorem, definition, corollary, proposition, lemma,
	example, remark, note, recall
}

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
% Shares the canonical TeXLib geometry (texlibbase): the green solved-rule and
% the dashed blank-answer rule are the same width (\texlibrulewidth) and sit in
% the same margin position as every other TeXLib rule, and match didactic's
% solution box. The full-frame blue "Solution:" title box is retired.
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
			\ifkey
				\tcbset{
					colback=green!3!white,
					borderline west={\texlibrulewidth}{0pt}{green!50!black},
					before upper={\textbf{Solution.}\par\smallskip},
				}
			\else
				\ifstudent
					\tcbset{
						height=#1,
						upperbox=invisible,
						colback=white,
						borderline west={\texlibrulewidth}{0pt}{black!40, dash pattern=on 3pt off 2pt},
						watermark text={\textit{Show your work here}},
						watermark color=black!10,
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
% Left-rule aesthetic (texlibbase: same width/position as every TeXLib rule),
% keeping hint's existing yellow identity. The inline "Hint." label replaces
% the old full-frame title bar.
\NewTColorBox{hint}{ }{
	texlibbase,
	colback=yellow!4!white,
	borderline west={\texlibrulewidth}{0pt}{yellow!55!black},
	before upper={\textbf{Hint.}\par\smallskip},
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

% ==============================================================================
% Structural hang: section/subsection headings, the TOC title, the bibliography
% heading, and the running header/footer all hang onto one outer left edge.
% Loaded LAST so its redefinitions land on top of the article defaults.
% ==============================================================================
\RequirePackage{texlib-sectionhang}

\endinput
