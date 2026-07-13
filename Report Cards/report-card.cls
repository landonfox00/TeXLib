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
\RequirePackage{adjustbox, changepage}
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
% 2b. GRADEBOOK ENGINE — Lua bridge for \gradebook (section 10)
% ==============================================================================
% report_card_engine.lua reads a report-view CSV and emits one \rcRenderStudent
% call per student. Located via kpse (installed tree), then next to this .cls
% (canonical layout), then the cwd (standalone). LuaLaTeX only; a non-Lua engine
% leaves \rc@lua as a clear error so merely loading the class still works.
\ifdefined\directlua
	\directlua{
		local function rc_load(name)
			local path = kpse.find_file(name, "lua")
			if path and lfs.attributes(path) then dofile(path) return end
			local cls = kpse.find_file("report-card.cls")
			local dir = cls and cls:match("(.*[/\\])") or ""
			path = dir .. name
			if lfs.attributes(path) then dofile(path) return end
			dofile(name)
		end
		rc_load("report_card_engine.lua")
	}%
	\newcommand{\rc@lua}[1]{\directlua{#1}}%
\else
	\newcommand{\rc@lua}[1]{%
		\ClassError{report-card}%
			{The \string\gradebook\space command requires LuaLaTeX}%
			{\string\gradebook\space drives a Lua engine through
			 \string\directlua, which only exists under LuaLaTeX. Compile this
			 document with lualatex.}%
	}%
\fi


% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\tl_new:N \g__rc_report_date_tl
\tl_new:N \g__rc_brand_color_tl
\tl_new:N \g__rc_accent_color_tl
\tl_new:N \g__rc_disclaimer_tl
\tl_new:N \g__rc_signature_tl
\tl_new:N \g__rc_title_tl

\tl_gset:Nn \g__rc_brand_color_tl  { 003366 }     % UNR navy by default
\tl_gset:Nn \g__rc_accent_color_tl { 808080 }     % silver
\tl_gset:Nn \g__rc_disclaimer_tl {
	\textit{Disclaimer:~ This~document~is~an~estimate~based~on~current~records.~
	Official~grades~are~determined~by~the~specific~policies~in~the~syllabus.~
	I~also~make~mistakes,~please~keep~that~in~mind.}
}

\keys_define:nn { meta } {
	report-date      .tl_gset:N = \g__rc_report_date_tl,
	report-card-title .tl_gset:N = \g__rc_title_tl,
	brand-color    .tl_gset:N = \g__rc_brand_color_tl,
	accent-color   .tl_gset:N = \g__rc_accent_color_tl,
	rc-disclaimer  .tl_gset:N = \g__rc_disclaimer_tl,
	rc-signature   .tl_gset:N = \g__rc_signature_tl,
	% Backward-compat aliases
	disclaimer     .tl_gset:N = \g__rc_disclaimer_tl,
	signature      .tl_gset:N = \g__rc_signature_tl,
}

\NewExpandableDocumentCommand{\GetReportDate} {}{ \tl_use:N \g__rc_report_date_tl }
\NewExpandableDocumentCommand{\GetReportCardTitle}{}{
	\tl_if_empty:NTF \g__rc_title_tl
		{ \GetCourseShort\ \GetCourseTitle }
		{ \tl_use:N \g__rc_title_tl }
}
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
\MetaApplyClassOptions

% ==============================================================================
% 4. PAGE LAYOUT
% ==============================================================================
\RequirePackage{texlib-footer}   % shared footer: Course | page X of Y | Institution
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = report-card title  C = (none)  R = term + section.
\SetTeXLibHeader{\bfseries\GetReportCardTitle}{}{\GetTermSection}
\SetTeXLibFooter
% Rule bleed comes from texlib-sectionhang's [LR] offset (loaded at the end of
% this class), so \TeXLibRuleBleed must NOT also be called.

% Title-page style: same footer as `fancy`, but header + rule suppressed so the
% \maketitle block sits cleanly at the top of page 1 (matches pset/syllabus).
\TeXLibFooterOnlyPagestyle{firstpage}

% ==============================================================================
% 5. TITLE BLOCKS
% ==============================================================================
% \maketitle: course-level cover page (no student name).
% \studenttitle{Name}: per-student cover (called via the reportcard env).
\renewcommand{\maketitle}{%
	\thispagestyle{firstpage}%
	\begin{center}
		{\LARGE \bfseries Report Cards} \\[0.4em]
		{\Large \GetCourse \space\textendash\space \GetTerm} \\[0.2em]
		{\large \GetReportDate}
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

% ==============================================================================
% 10. GRADEBOOK-DRIVEN RENDERING
% ==============================================================================
% \gradebook{report-view.csv} reads one row per student and renders a full
% report card for each — exactly one cover per student — via \rcRenderStudent.
% All grade math lives in the gradebook sheet; the engine only formats values.

% Letter-grade cutoffs (used for the standing-bar thresholds and the scenario
% "Required Letter Grade" column). The scenario "what you need" cells themselves
% come pre-computed from the sheet.
\newcommand{\rc@cut@a}{90}
\newcommand{\rc@cut@b}{80}
\newcommand{\rc@cut@c}{70}
\newcommand{\rc@cut@d}{60}

% Default sign-off body (override per document with \renewcommand if desired).
\newcommand{\rc@default@signoff}{%
	Thank you for attending my course! I wish you a successful academic and
	professional career.%
}

% Per-student cover — the \maketitle title card, specialised with the name.
% One \newpage (no trailing blank), so each student gets precisely one cover.
\NewDocumentCommand{\rc@cover}{ m }{%
	\thispagestyle{firstpage}%
	\begin{center}
		{\LARGE \bfseries #1} \\[0.4em]
		{\Large \GetReportCardTitle\ Report Card} \\[0.2em]
		{\large \GetTerm \quad \GetReportDate}
	\end{center}
	\newpage
}

% Standing bar from a running percentage: maps 0..100% onto the 0..12.5 axis
% (×0.125) and places the cutoff thresholds. tikz evaluates the coordinate
% expressions, so the arithmetic happens at draw time.
\NewDocumentCommand{\rc@standingfromtotal}{ m }{%
	\standingbar{#1*0.125}{\rc@cut@d*0.125}{\rc@cut@c*0.125}%
		{\rc@cut@b*0.125}{\rc@cut@a*0.125}%
}

% \rcRenderStudent{name}{current-total%}{current-points}{breakdown-body}%
%                 {total-row}{scenarios-body}
% Emitted by the Lua engine, once per student. Owns all layout and prose; the
% arguments are pure data.
\NewDocumentCommand{\rcRenderStudent}{ m m m +m m +m }{%
	\rc@cover{#1}%
	\GetDisclaimer\par\medskip
	\section*{Current Grade Calculation}
	Based on the syllabus, here is your current grade breakdown prior to the
	Final Exam.
	\gradebreakdown{#4}{#5}
	\section*{Visual Standing}
	\rc@standingfromtotal{#2}
	\section*{Final Exam Scenarios}
	Based on your current standing of \textbf{#3 points}, here is what you must
	score on the Final Exam to achieve each letter grade.
	\scenarios{#6}
	\signoff{\rc@default@signoff}%
	\newpage
}

% Core: render every student in the report-view CSV at <path>.
\NewDocumentCommand{\rc@gradebook@render}{ m }{%
	\rc@lua{rc_set_cutoffs(\rc@cut@a, \rc@cut@b, \rc@cut@c, \rc@cut@d)}%
	\rc@lua{rc_read_gradebook('\luaescapestring{#1}')}%
}

% Map a trailing .xlsx to .csv. The class reads the CSV the builder exports
% from the gradebook workbook, so a coursemeta gradebook-path pointing at the
% .xlsx source of truth still resolves to the readable .csv.
\def\rc@chopxlsx#1.xlsx#2\@nil{#1.csv}
% \in@ does not expand its argument, so feed it the expanded candidate.
\newcommand{\rc@mapcand}{\expandafter\rc@mapcand@\expandafter{\rc@gb@cand}}
\def\rc@mapcand@#1{%
	\in@{.xlsx}{#1}%
	\ifin@ \edef\rc@gb@cand{\rc@chopxlsx#1\@nil}\fi
}

\newcommand{\rc@gb@missing}{%
	\ClassWarning{report-card}{%
		No~gradebook~found~(looked~for~`\rc@gb@cand').~Set~gradebook-path~in~
		coursemeta,~place~a~gradebook.csv~beside~the~document,~or~call~
		\string\gradebook[path]}%
}

% \rc@load@coursegradebook — resolve the gradebook path from coursemeta's
% gradebook-path (falling back to a sibling gradebook.csv) and render it. Tries
% the path literally first, then relative to the coursemeta directory (so a
% document below coursemeta finds a course-level gradebook), mirroring the
% problem-bank \pbank@load@coursebank resolution.
\newcommand{\rc@load@coursegradebook}{%
	\@ifundefined{GetGradebookPath}%
		{\def\rc@gb@cand{gradebook.csv}}%
		{\edef\rc@gb@cand{\GetGradebookPath}%
		 \ifx\rc@gb@cand\empty \def\rc@gb@cand{gradebook.csv}\fi}%
	\rc@mapcand
	\IfFileExists{\rc@gb@cand}%
		{\rc@gradebook@render{\rc@gb@cand}}%
		{\@ifundefined{GetCourseMetaDir}%
			{\rc@gb@missing}%
			{\edef\rc@gb@resolved{\GetCourseMetaDir\rc@gb@cand}%
			 \IfFileExists{\rc@gb@resolved}%
				{\rc@gradebook@render{\rc@gb@resolved}}%
				{\rc@gb@missing}}}%
}

% \gradebook[path] — render a report-view CSV.
%   \gradebook[file.csv]  explicit path
%   \gradebook            path from coursemeta gradebook-path, else a sibling
%                         gradebook.csv (an .xlsx value maps to its .csv)
\NewDocumentCommand{\gradebook}{ o }{%
	\IfValueTF{#1}{\rc@gradebook@render{#1}}{\rc@load@coursegradebook}%
}

% ==============================================================================
% Structural hang: section headings (the per-student \section* blocks), the TOC
% title, and the running header/footer all hang onto one outer left edge.
% Loaded LAST so its redefinitions land on top of the article defaults.
% ==============================================================================
\RequirePackage{texlib-sectionhang}

\endinput
