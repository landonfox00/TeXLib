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
\MetaApplyClassOptions

% ==============================================================================
% 4. PAGE LAYOUT -- METADATA-DRIVEN HEADERS
% ==============================================================================
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = unit title  C = build badge  R = current (sub)section. Shared
% mechanism; the badge wording is class-specific (lecture notes -> "Instructor
% Version").
\SetTeXLibBuildBadge{\ifsolutions Instructor Version\fi}
\SetTeXLibHeader{\bfseries\GetUnitTitle}{\TeXLibBuildBadge}{\rightmark}
% Right header tracks the current (sub)section: number + full title, e.g.
% "2.1 Differentiation Rules". Every level routes its number+title into
% \rightmark, so the header reflects whichever (sub)section is in effect at the
% top of the page. Subsubsections are unnumbered at the class default
% (secnumdepth=2 below), so only a numbered one updates the mark -- otherwise an
% unnumbered subsubsection would show a bogus "2.1.0" instead of leaving its
% parent subsection showing. Raise secnumdepth to 3 to get "2.1.4 <title>" in
% both the header and the document body.
\renewcommand{\sectionmark}[1]{\markright{\thesection\ #1}}
\renewcommand{\subsectionmark}[1]{\markright{\thesubsection\ #1}}
\renewcommand{\subsubsectionmark}[1]{%
	\ifnum\c@secnumdepth>\tw@ \markright{\thesubsubsection\ #1}\fi}
% tocloft marks the TOC pages \MakeUppercase{\contentsname} ("CONTENTS");
% every other mark in this header is title-case, so drop the uppercasing.
\renewcommand{\cftmarktoc}{\@mkboth{\contentsname}{\contentsname}}
% Footer is the shared TeXLib layout (course | page | institution)
\SetTeXLibFooter

% Title page (first page of lecture notes): no header, no header rule.
% Shared footer remains in place.
\TeXLibFooterOnlyPagestyle{titlepage}
% tocloft stamps the first TOC page \thispagestyle{plain} (bare centered page
% number, no shared footer). Inside \maketitle the titlepage stamp fires later
% and wins, but a \tableofcontents called after \maketitle re-stamps page 1
% plain and silently drops the footer -- route tocloft to titlepage instead.
\tocloftpagestyle{titlepage}

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
\RequirePackage{texlib-callouts}   % shared {hint} + {readings} callout envs

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
% C1: the whole boxed taxonomy in one call, unified across the classes (adds
% `note` to didactic's set; the full list now lives once in texlib-thmenv.sty).
\TeXLibAllTheorems[numbering=section, aliases=true]

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
% 7. SOLUTION / ANSWER REGION ENVIRONMENTS  (label + gate + write-space)
% ==============================================================================
% Design paradigm (why an ENVIRONMENT, not a command):
%   A region that must be SHOWN or HIDDEN, and that reserves student write-space
%   equal to its own body, has to know where its content ends -- so it is a
%   delimited environment (\begin..\end), never a bare lead-in command. The
%   always-visible inline lead-ins (\solution \answer \pf, section 7b) are the
%   command half of the pair: one-shot typographic labels with no gated region.
%
% Behaviour of the box:
%   - shown  (instructor build, or gating disabled, or starred \begin{solution}*):
%       thin green left rule + 2% tint + bold "\@sol@label" header, real body.
%   - gated  (default student build):
%       real body is captured and DISCARDED (never ships), replaced by a dashed
%       thin grey left rule around a blank write-box of height [#1].
% Both boxes are breakable, so a tall box splits to fill a page bottom and
% continues on the next page rather than jumping whole and leaving a gap. The
% blank box gets its height from breakable filler lines (\@sol@blankfill), not
% a fixed tcolorbox height, precisely so it CAN split. Shares the canonical
% TeXLib geometry (texlibbase: same rule width via \texlibrulewidth, same
% margin bleed/position as the theorem boxes).
%
% Customisation knobs (document-level, letter-only so they are usable in .tex):
%   \gatesolutionfalse  -- make {solution}/{answer} ALWAYS show the real body
%                          (ungated), regardless of build mode. \gatesolutiontrue
%                          restores the default (blank space for students).
%   \begin{solution}* / \begin{answer}*  -- force-show this one instance.
% The header text is swapped per role via \@sol@label ({answer} sets "Answer.").
\newif\ifgatesolution  \gatesolutiontrue   % gated (blank for students) by default
\newif\if@sol@show                         % scratch: does THIS instance show its body?
\newcommand{\@sol@label}{Solution.}        % header text; {answer} overrides to "Answer."

% Two inner boxes: the shown (green) solution and the blank (dashed) answer
% space. Both inherit texlibbase, so both are breakable.
\NewTColorBox{@sol@shown}{}{
	texlibbase,
	colback=green!3!white,
	borderline west={\texlibrulewidth}{0pt}{green!50!black},
	before upper={\textbf{\@sol@label}\par\smallskip},
}
\NewTColorBox{@sol@blank}{}{
	texlibbase,
	colback=white,
	borderline west={\texlibrulewidth}{0pt}{black!40, dash pattern=on 3pt off 2pt},
}
% Reserve #1 of blank writing space as one zero-width strut per line with a
% \par (a legal page-break point) between each. Two properties matter together:
% the \par breakpoints let the enclosing breakable box SPLIT to fill a page
% bottom and continue on the next (a fixed tcolorbox `height`, or one tall
% \rule, is a single rigid block with no interior breakpoint and just jumps);
% and the height comes from STRUTS (real boxes), not interline glue -- glue is
% discarded at a page break, so a glue-based filler's carried-over portion
% collapses to nothing on the next page. \raggedright suppresses the underfull
% warning each zero-width line would otherwise raise.
\newcommand{\@sol@blankfill}[1]{%
	\par\raggedright
	\setlength{\@tempdima}{#1}%
	\@whiledim\@tempdima>\baselineskip\do{%
		\rule{\z@}{\baselineskip}\par
		\addtolength{\@tempdima}{-\baselineskip}%
	}%
	\rule{\z@}{\@tempdima}\par
}
% Show the real body when ANY of: this instance is starred (#1), gating is
% disabled (\ifgatesolution false), or this is an instructor build
% (\ifsolutions). Otherwise capture and DISCARD the real body (so a student
% build never ships the answer, even invisibly) and emit a dashed breakable
% blank box of height #2 to write in.
\NewDocumentEnvironment{solution}{ s O{3cm} }
{%
	\IfBooleanTF{#1}{\@sol@showtrue}{%
		\ifgatesolution
			\ifsolutions \@sol@showtrue \else \@sol@showfalse \fi
		\else
			\@sol@showtrue
		\fi}%
	\if@sol@show
		\begin{@sol@shown}%
	\else
		\setbox\z@\vbox\bgroup
	\fi
}{%
	\if@sol@show
		\end{@sol@shown}%
	\else
		\egroup
		\begin{@sol@blank}\@sol@blankfill{#2}\end{@sol@blank}%
	\fi
}

% ==============================================================================
% 7.5. REGION ALIASES  ({soln}, {answer}, {ans})
% ==============================================================================
% Thin wrappers over {solution}: each forwards the star and the optional
% [<height>]. {answer}/{ans} relabel the header to "Answer." (a shorter default
% height, since a short-answer key needs less write-space than a full solution)
% and are otherwise identical -- they gate and reserve space exactly like
% {solution}. The relabel is scoped by the environment group, so it reverts at
% \end. Naming: the region-answer form is the ENVIRONMENT \begin{answer}; the
% always-visible inline label is the COMMAND \answer (section 7b). The two never
% collide because \answer-the-command only exists (via \let) inside a worked
% environment, where it locally shadows the environment name; in open text
% \begin{answer} is the box. (No `*'-twin theorem semantics here -- the `s' is
% the force-show star, matching {solution}*.)
\NewDocumentEnvironment{soln}{ s O{3cm} }
  {\IfBooleanTF{#1}{\begin{solution}*[#2]}{\begin{solution}[#2]}}
  {\end{solution}}
\NewDocumentEnvironment{answer}{ s O{1.5cm} }
  {\renewcommand{\@sol@label}{Answer.}%
   \IfBooleanTF{#1}{\begin{solution}*[#2]}{\begin{solution}[#2]}}
  {\end{solution}}
\NewDocumentEnvironment{ans}{ s O{1.5cm} }
  {\IfBooleanTF{#1}{\begin{answer}*[#2]}{\begin{answer}[#2]}}
  {\end{answer}}

% ==============================================================================
% 7b. INLINE WORKED LEAD-INS  (\solution \answer \ans \pf)  + challenge gating
% ==============================================================================
% The COMMAND half of the pair. texlib-thmenv.sty binds these four lead-ins
% (\let to always-visible italic "Solution." / "Answer." / "Proof." labels)
% inside every worked-shaped env -- example, exercise, question, challenge --
% via \AtBeginEnvironment{<env>}{\texlib@bind@worked}. A worked solution is
% exposition, so the DEFAULT is always-visible.
%
% didactic then makes the two ASSESSMENT-shaped members gate. In `challenge'
% and `exercise' a lead-in is a spoiler: it should reach the instructor build
% but not the student handout. So here we re-bind the four lead-ins in just
% those two envs to a gated form -- shown under \ifsolutions, otherwise opening
% a \vbox that swallows the rest of the environment body (the \AtEndEnvironment
% hook closes it), so no worked text ships. `example' and `question' are left
% at the always-visible binding (a worked example is exposition; a question's
% short \answer is a visible prompt).
%
% These \AtBeginEnvironment hooks are registered AFTER \TeXLibAllTheorems (sec.
% 6) has registered \texlib@bind@worked, so at \begin they fire second and win.
%
% Knob: \gateworkedfalse turns the gating off (lead-ins stay always-visible in
% challenge/exercise too); \gateworkedtrue (default) restores it.
\newif\ifgateworked  \gateworkedtrue
\newif\if@wrk@gateopen

% A gated lead-in. #1 is the visible label macro (from texlib-thmenv.sty). In an
% instructor build it prints the label inline; otherwise it opens ONE discard
% vbox (guarded by the flag so a second lead-in in the same env does not nest a
% second box) that captures everything up to \end.
\newcommand{\texlib@wrk@lead}[1]{%
	\ifsolutions
		#1%
	\else
		\if@wrk@gateopen\else \@wrk@gateopentrue \setbox\z@\vbox\bgroup \fi
	\fi}
% Closes the discard vbox if a gated lead-in opened one. Runs as the last tokens
% of the environment body, i.e. still inside that vbox, so \egroup balances it.
\newcommand{\texlib@wrk@close}{\if@wrk@gateopen \egroup \@wrk@gateopenfalse \fi}
% Re-bind the four lead-ins to their gated form (only when gating is enabled).
\newcommand{\texlib@wrk@gatebind}{%
	\ifgateworked
		\def\solution{\texlib@wrk@lead{\texlib@inline@solution}}%
		\def\answer  {\texlib@wrk@lead{\texlib@inline@answer}}%
		\def\ans     {\texlib@wrk@lead{\texlib@inline@answer}}%
		\def\pf      {\texlib@wrk@lead{\texlib@inline@proof}}%
	\fi}
\AtBeginEnvironment{challenge} {\texlib@wrk@gatebind}
\AtBeginEnvironment{challenge*}{\texlib@wrk@gatebind}
\AtBeginEnvironment{exercise}  {\texlib@wrk@gatebind}
\AtBeginEnvironment{exercise*} {\texlib@wrk@gatebind}
\AtEndEnvironment{challenge}   {\texlib@wrk@close}
\AtEndEnvironment{challenge*}  {\texlib@wrk@close}
\AtEndEnvironment{exercise}    {\texlib@wrk@close}
\AtEndEnvironment{exercise*}   {\texlib@wrk@close}

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
