% report-card.cls
% Per-Student Report Card Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{report-card}[2026/05/07 v1.0 Per-Student Report Cards (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[report-date={May 2026}, brand-color=003366]{report-card}
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
% texlib-mathutils, graphicx, tikz/pgfplots, hyperref + canonical hypersetup)
% plus heavy-class extras (siunitx, caption, tasks, extra tikz libraries).
\RequirePackage{basic-utilities}
\captionsetup{skip=3pt}  % runtime override of caption's default vskip
\RequirePackage{adjustbox, changepage, comment}
\RequirePackage[shortlabels]{enumitem}
\RequirePackage{fancyhdr, lastpage}
\RequirePackage{needspace}
\RequirePackage{booktabs, colortbl, multirow, makecell}
\RequirePackage{tocloft}
\RequirePackage{course-metadata}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}


% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\tl_new:N \g__rc_report_date_tl
\tl_new:N \g__rc_brand_color_tl
\tl_new:N \g__rc_accent_color_tl
\tl_new:N \g__rc_disclaimer_tl
\tl_new:N \g__rc_signature_tl

\tl_gset:Nn \g__rc_brand_color_tl  { 003366 }     % UNR navy by default
\tl_gset:Nn \g__rc_accent_color_tl { 808080 }     % silver
\tl_gset:Nn \g__rc_disclaimer_tl {
	\textit{Disclaimer:~ This~document~is~an~estimate~based~on~current~records.~
	Official~grades~are~determined~by~the~specific~policies~in~the~syllabus.~
	I~also~make~mistakes,~please~keep~that~in~mind.}
}

\keys_define:nn { meta } {
	report-date    .tl_gset:N = \g__rc_report_date_tl,
	brand-color    .tl_gset:N = \g__rc_brand_color_tl,
	accent-color   .tl_gset:N = \g__rc_accent_color_tl,
	rc-disclaimer  .tl_gset:N = \g__rc_disclaimer_tl,
	rc-signature   .tl_gset:N = \g__rc_signature_tl,
	% Backward-compat aliases
	disclaimer     .tl_gset:N = \g__rc_disclaimer_tl,
	signature      .tl_gset:N = \g__rc_signature_tl,
}

\NewExpandableDocumentCommand{\GetReportDate} {}{ \tl_use:N \g__rc_report_date_tl }
\NewExpandableDocumentCommand{\GetDisclaimer} {}{ \tl_use:N \g__rc_disclaimer_tl }
\NewExpandableDocumentCommand{\GetSignature}  {}{
	\tl_if_empty:NTF \g__rc_signature_tl
		{ \GetInstructor }
		{ \tl_use:N \g__rc_signature_tl }
}

\AtBeginDocument{
	\exp_args:Nx \definecolor { rc@brand  } { HTML } { \tl_use:N \g__rc_brand_color_tl  }
	\exp_args:Nx \definecolor { rc@accent } { HTML } { \tl_use:N \g__rc_accent_color_tl }
}

\ExplSyntaxOff

% \disclaimer{...} -- content-setter for the boilerplate disclaimer prose, which
% is too long to ride in the class option list; lets a document override the
% default without a raw \metasetup. Routes through the rc-disclaimer key (the
% bare `disclaimer` key alias keeps working independently).
\NewDocumentCommand{\disclaimer}{ +m }{ \metasetup{ rc-disclaimer = {#1} } }

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
% 4. PAGE LAYOUT
% ==============================================================================
\RequirePackage{texlib-footer}   % shared footer: Course | page X of Y | Institution
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = course short + title  C = (none)  R = term.
\SetTeXLibHeader{\bfseries\GetCourseShort\ \GetCourseTitle}{}{\GetTerm}
\SetTeXLibFooter
\TeXLibRuleBleed                  % symmetric rule length, matching didactic

% ==============================================================================
% 5. TITLE BLOCKS
% ==============================================================================
% \maketitle: course-level cover page (no student name).
% \studenttitle{Name}: per-student cover (called via the reportcard env).
\renewcommand{\maketitle}{%
	\begin{center}
		{\huge \GetCourseShort\ \GetCourseTitle\ Report Cards} \\
		\vspace{8pt}
		{\Large \GetReportDate}
	\end{center}
	\newpage
}
\NewDocumentCommand{\studenttitle}{ m }{%
	\begin{center}
		{\huge #1 Report Card} \\
		\vspace{8pt}
		{\LARGE \GetCourseShort\ \GetCourseTitle} \\
		\vspace{8pt}
		{\Large \GetReportDate}
	\end{center}
	\newpage
	\null
	\newpage
}

% \begin{reportcard}{Student Name} ... \end{reportcard}
%   Wraps each student section: emits the title page, the boilerplate
%   disclaimer, and a trailing \newpage when closed.
\NewDocumentEnvironment{reportcard}{ m }
{%
	\studenttitle{#1}
	\GetDisclaimer\par\medskip
}
{%
	\newpage
}

% ==============================================================================
% 6. GRADE-BREAKDOWN TABLE
% ==============================================================================
% \gradebreakdown{ rows in tabular form using & and \\ }{total-row}
%
% Example:
%   \gradebreakdown{
%       Homework Avg. & 15\% & 92.1\% & +13.8 \\
%       Quiz Avg.     & 10\% & 67.5\% & +6.8  \\
%       \midrule
%       Exam 1        & 10\% & 31\%   & +3.1  \\
%   }{75\% (+15\% E.C.) & \fbox{\textbf{59.4\%}} & 44.5}
\NewDocumentCommand{\gradebreakdown}{ +m m }{%
	\begin{center}
		\renewcommand{\arraystretch}{1.25}
		\arrayrulecolor{rc@brand}
		\begin{tabular}{l c c r}
			\toprule
			\textbf{Category} & \textbf{Weight} & \textbf{Your Score} & \textbf{Points Earned} \\
			\midrule\midrule
			#1
			\midrule\midrule
			\rowcolor{rc@brand!10} \textbf{Current Total} & #2 \\
			\bottomrule
		\end{tabular}
	\end{center}%
}

% ==============================================================================
% 7. STANDING BAR — visual progress indicator
% ==============================================================================
% \standingbar{current-points}{passing-grade-x-coord}{c-grade}{b-grade}{a-grade}
% Coordinates: 0..12.5 representing 0%..100%; current-points is in the same scale.
\NewDocumentCommand{\standingbar}{ m m m m m }{%
	\begin{center}
		\begin{tikzpicture}
			% Light fill to indicate full available range
			\fill[fill=rc@brand!30, rounded corners] (0,0) rectangle (12.5,1.5);
			% Current standing (solid)
			\fill[fill=rc@brand, rounded corners] (0,0) rectangle (#1,1.5);
			% Tick marks every 10%
			\foreach \x in {1.25,2.5,3.75,5.0,6.25,7.5,8.75,10,11.25}{%
				\draw[thin,white] (\x, 0) -- (\x, 0.2);%
			}%
			% Grade thresholds
			\draw[thick, black] (#2, 1.5) -- (#2, -0.5) node[below] {D (60)};
			\draw[thick, black] (#3, 1.5) -- (#3, -0.5) node[below] {C (70)};
			\draw[thick, black] (#4, 1.5) -- (#4, -0.5) node[below] {B (80)};
			\draw[thick, black] (#5, 1.5) -- (#5, -0.5) node[below] {A (90)};
			% Frame
			\draw[thick, black, rounded corners] (0,0) rectangle (12.5,1.5);
		\end{tikzpicture}
	\end{center}%
}

% ==============================================================================
% 8. SCENARIOS TABLE — "What you need on the final"
% ==============================================================================
% \scenarios{ rows: outcome & letter & required-final \\ ... }
\NewDocumentCommand{\scenarios}{ +m }{%
	\begin{center}
		\renewcommand{\arraystretch}{1.25}
		\arrayrulecolor{rc@brand}
		\begin{tabular}{l c c}
			\toprule
			\textbf{Outcome} & \textbf{Required Letter Grade} &
			\textbf{Your Required Final Exam Score} \\
			\midrule\midrule
			#1
			\bottomrule
		\end{tabular}
	\end{center}%
}

% ==============================================================================
% 9. SIGN-OFF
% ==============================================================================
\NewDocumentCommand{\signoff}{ +m }{%
	#1\par\medskip
	\noindent Sincerely, \\
	\GetSignature
}

\endinput
