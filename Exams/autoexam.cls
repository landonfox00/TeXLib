\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{autoexam}[2025/02/13 AutoExam Class (Merged)]

% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[exam-number=5, exam-date={May 2, 2026}]{autoexam}
% Any option containing "=" is a metadata key=value pair (applied below, once the
% exam-meta keys and coursemeta have loaded, so document options win); every
% other option is forwarded to the base exam class. Metadata is read from
% \@raw@classoptionslist so values keep their spaces. \DeclareOption* only
% forwards the non-metadata options; the key=value ones pass through it (a no-op)
% so the kernel marks them used. Safe because no exam-class option uses key=value.
\DeclareOption*{%
	\@expandtwoargs\in@{=}{\CurrentOption}%
	\ifin@\else
		\PassOptionsToClass{\CurrentOption}{exam}%
	\fi
}
\ProcessOptions\relax

% Load the base class
\LoadClass[11pt]{exam}

% A class-option value containing a comma (e.g. exam-date={May 2, 2026}) is split
% by the kernel's option parser into a stray fragment ("2026") with no "=", which
% would be reported as an "unused global option". The real values are consumed
% from \@raw@classoptionslist below, so discard those spurious leftovers.
\AtEndOfClass{\global\let\@unusedoptionlist\@empty}

% Shared assessment setup (texlib-corepkg, texlib-build, course-metadata, the
% common aux packages, and the unified problem/part labels). Shared with quiz.
\RequirePackage{texlib-assessment}

% Shared document-instructions mechanism (inline / file / default, file > inline
% > default). \TeXLibDeclareInstructions[autoexam-instructions]{exam} below mints
% \GetExamInstructions, \IfExamInstructions{File,Inline}, and
% \exam@input@userinstructions.
\RequirePackage{texlib-instructions}

% autoexam-only packages. enumitem is intentionally absent: it patches \list and
% breaks exam.cls's questions/parts.
\RequirePackage[export]{adjustbox}
\RequirePackage{subfigure}
\RequirePackage[subfigure]{tocloft}
\RequirePackage{array}
\RequirePackage{multirow}
\RequirePackage{multicol}
\RequirePackage[many]{tcolorbox}    % minimal-style solution box (matches didactic)
\RequirePackage{environ}            % capturing solution bodies

% Extra TikZ libraries (corepkg already loads arrows.meta/positioning/shapes.geometric)
\usetikzlibrary{datavisualization, datavisualization.formats.functions}

% In multi-version documents the exam class defines question@N / part@N@M labels
% once per version.  The LaTeX kernel reads \jobname.aux BEFORE \AtBeginDocument
% hooks fire, so we must redefine \@newl@bel here (at class-load time) — not in
% a hook — to suppress the "multiply defined" warnings during aux reading.
\def\@newl@bel#1#2#3{\global\@namedef{#1@#2}{#3}}
%
% Suppress the "Label(s) may have changed. Rerun." oscillation.  Because each
% version overwrites the same label names (question@N, part@N@M …), \@testdef
% always sees a mismatch between consecutive intermediate overwrites even when
% the aux is fully stable.  Exam documents never use \ref / \pageref, so the
% cross-reference change-detection provided by \@testdef is meaningless here.
\def\@testdef#1#2#3{}

% Hyperref setup is provided by texlib-corepkg.sty.

% SIUnitX Setup (only when package is available)
\ifdefined\sisetup
\sisetup{
	table-number-alignment=center,
	mode=math
}
\fi

% texlib-build (loaded via texlib-assessment) provides \ifsolutions, \ifkey,
% \ifrubric, \ifdraft, \ifstudent, \ifinstructor and the matching command-line
% toggles.

% Backward-compat aliases for autoexam's internal naming. Existing logic
% (and downstream documents) using \if@autoexam@rubric / \@autoexam@rubrictrue
% continues to work; new code should use \ifrubric / \rubrics.
\let\if@autoexam@rubric\ifrubric
\let\@autoexam@rubrictrue\rubrictrue
\let\@autoexam@rubricfalse\rubricfalse

% Versioning is autoexam-specific (not part of texlib-build).
\newif\if@autoexam@versioned
\@autoexam@versionedfalse

% Handle Versions
\ifdefined\Version
	\newcommand{\theExamVersion}{\Version}
\else
	\newcommand{\theExamVersion}{A} % Default for editing
\fi

% \examversions{A, B, C}
%   Declares the exam versions for this document.
%   - Standalone mode (no Python builder): the class loops over all versions
%     in a single compilation, producing a collated PDF.
%   - Builder mode (\def\Version{A} passed on the command line): the class
%     runs only the specified version (builder handles parallelism).
%   The Python builder also parses this command via regex to discover versions.
\def\@autoexam@versions{}  % empty = edit/single-version mode
\newcommand{\examversions}[1]{%
	\def\@autoexam@versions{#1}%
	\@autoexam@versionedtrue%           % mark that explicit versions were declared
	\directlua{texlib.set_autoexam_versions('\luaescapestring{#1}')}%
	\typeout{AutoExam: Detected Versions: #1}%
}
\let\versions\examversions              % \versions is the preferred short alias

% Source-level toggles \solutions, \keys, \rubrics, \drafts, \studentmode,
% \instructormode are provided by texlib-build (loaded above).

% texlib-problembank.sty loads problem_engine.lua and defines the shared
% machinery: \setvar/\setrng/\calcvar/\get, \pick* commands, \getlist/\geti/
% \foreachpick, \begin{problem} environment,
% \getproblem (+ aliases), \ppart, \@problem@item, \importproblem, and
% \providecommand defaults for \workbox and \autoexam@problem@sep.  Quiz.cls
% requires the same package; keeping the LaTeX glue in one place ensures the
% two classes can't drift.  See texlib-problembank.sty for the full API.
\RequirePackage{texlib-problembank}

% \begin{problems} ... \end{problems}
%   The environment itself is defined once in texlib-problembank.sty (shared
%   with quiz.cls).  autoexam supplies its page policy through the two hooks the
%   shared environment calls:
%
%   \problems@begin@hook (on entry):
%     - a single-use guard (warns if {problems} is opened twice in one version)
%     - \clearpage, then resets the page counter to 1 so Q1 lands on "page 1"
%     - restores the problem-style first-page and running header/footer slots
%
%   \problems@end@hook (on exit):
%     - places \label{@lastqpage} on the last problem page (read by the "X of N"
%       footer once \blankpage ships that page)
%
%   The shared environment handles the parts common to both classes: the
%   inter-problem separator flag, the \newpage patch, opening {questions}, and
%   swapping \problem <-> \@problem@item.

% \@problems@lastver: the \theExamVersion under which {problems} was last
% opened.  Empty until first use; consulted by the single-use guard below.
\gdef\@problems@lastver{}

\renewcommand{\problems@begin@hook}{%
	% ---- single-use guard ----------------------------------------------------
	% {problems} resets the page counter and issues \clearpage on entry, so it
	% is designed to wrap the entire problem section ONCE per version.  Opening
	% it again under the same version orphans the preceding heading onto its own
	% page and restarts the "X of N" footer.  Compare against \theExamVersion so
	% the per-version replay of a correct multi-version exam stays silent (the
	% engine re-inputs the body once per version, each with a new \theExamVersion).
	\edef\@problems@curver{\theExamVersion}%
	\ifx\@problems@curver\@problems@lastver
		\ClassWarning{autoexam}{%
			Two or more {problems} environments in version
			"\@problems@curver".\MessageBreak
			{problems} is single-use: it issues \string\clearpage\space and
			resets the\MessageBreak
			page counter on entry, orphaning any preceding heading and\MessageBreak
			restarting the page footer.  Use ONE {problems} block with\MessageBreak
			\string\section* / \string\subsection* headings inside it and
			\string\newpage\MessageBreak
			between groups (see template.tex or Math 127 exam1.tex).\MessageBreak
			Reported%
		}%
	\else
		\global\let\@problems@lastver\@problems@curver
	\fi
	% ---- ship any pending page (e.g. pre-problem scratch page from \blankpage) -
	\clearpage
	% ---- page counter & header/footer ----------------------------------------
	\setcounter{page}{1}%
	% Q1 is "page 1" and receives the first-page style (\@fullhead / \@fullfoot).
	% Restore those slots to match the running header so Q1 looks identical to
	% every subsequent problem page.
	%
	% IMPORTANT: this hook runs inside the {problems} environment group, so a
	% plain \def here is LOCAL and reverts when \end{problems} closes the group.
	% The last problem page and the \scorepage both ship AFTER the group closes,
	% so their headers/footers must be set with \global (\gdef / \global\def).
	% First-page slots (\@lhead etc.) are only needed for Q1, which ships via
	% the first \newpage inside the group, so local \def is fine there.
	\def\@lhead{\bfseries\GetExamTitle}%
	\def\@chead{}%
	\def\@rhead{\GetTermSection}%
	\global\@headruletrue%
	\def\@cfoot{%
		\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
	}%
	% Running slots for Q2+ — MUST be global so they survive \end{problems}.
	\gdef\run@chead{}%
	\global\def\run@cfoot{%
		\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
	}%
}

\renewcommand{\problems@end@hook}{%
	% Place the label on the last problem page.  \blankpage (which follows) ships
	% that page via \clearpage, recording the correct page number for "X of N".
	\label{@lastqpage}%
}

% \loadbank is provided by texlib-problembank.sty.  Multi-version mode is
% handled by the engine's pbank_suppress_redirect flag, set by
% autoexam_run_versions before the version loop iterates.

% \shufflepages
%   Declared in the PREAMBLE alongside \examversions.  When present, the Lua
%   version loop reorders the questions inside \begin{problems}...\end{problems}
%   independently per version (seeded by that version) and writes a per-version
%   temp file before TeX processes any tokens.  The shuffle is SECTION-AWARE:
%   \section / \section* headers are hard boundaries kept in their original
%   order with the header fixed at the top, and questions are permuted only
%   within their own section.  The per-page question counts you authored (the
%   \newpage layout) are preserved, and \extracredit stays last.  No exam-body
%   changes are needed — author one canonical order and let each version shuffle.
\newcommand{\shufflepages}{%
	\directlua{texlib.set_autoexam_shuffle_pages()}%
}

% Multiple-choice option shuffling (used with \shufflepages).  Authors write the
% exam-class \begin{choices}/\begin{oneparchoices} with \choice/\CorrectChoice;
% the Lua shuffler reorders the options per version (\CorrectChoice travels with
% its option, so the key auto-follows).  These definitions make the pinning
% markers compile in EVERY build mode (with or without shuffle):
%   \fixedchoice            -- an option the shuffler pins in place ("None of
%                              the above"); renders exactly like \choice.
%   \begin{choices}[fixed]  -- keep this block in authored order (ordered
%                              numeric answers); the [..] tag is read by the
%                              shuffler and ignored at render time.
\newcommand{\fixedchoice}{\choice}
\let\@ax@choices\choices            \let\@ax@endchoices\endchoices
\renewenvironment{choices}[1][]{\@ax@choices}{\@ax@endchoices}
\@ifundefined{oneparchoices}{}{%
	\let\@ax@opc\oneparchoices      \let\@ax@endopc\endoneparchoices
	\renewenvironment{oneparchoices}[1][]{\@ax@opc}{\@ax@endopc}%
}

% \byversion{A content}{B content}{C content}
%   Three-version convenience: typesets the argument matching the current
%   \theExamVersion (A/B/C).  Versioning is NOT limited to three — the version
%   loop, \shufflepages, and seeding all handle any number of versions.  This
%   command is just the 3-arg shorthand; for a version beyond C it falls back to
%   the A argument (its question ORDER still varies via \shufflepages).  For
%   version-specific content at any number of versions, use \vercase.
\long\def\@byv@A#1#2#3{#1}
\long\def\@byv@B#1#2#3{#2}
\long\def\@byv@C#1#2#3{#3}
\newcommand{\byversion}[3]{%
	\ifcsname @byv@\theExamVersion\endcsname
		\csname @byv@\theExamVersion\endcsname{#1}{#2}{#3}%
	\else
		#1%
	\fi
}
% \vercase{ver}{content}
%   Typeset content only when the current version equals ver (any version label).
%   Composes for any number of versions:
%     \vercase{A}{...}\vercase{B}{...}\vercase{D}{...}
\newcommand{\vercase}[2]{%
	\edef\@vc@cur{\theExamVersion}%
	\edef\@vc@want{#1}%
	\ifx\@vc@cur\@vc@want #2\fi
}

% \importproblem is provided by texlib-problembank.sty.

% --- Initialization ---

% Seed the per-version RNG, then auto-load any course-level bank (the bank
% resolution itself is shared — see \pbank@load@coursebank in texlib-problembank).
\AtBeginDocument{%
	\directlua{texlib.set_exam_seed('\theExamVersion')}%
	\pbank@load@coursebank
}

% Version loop hook — fires at the very end of \begin{document} setup,
% just before TeX would start reading the document body from the source file.
% Sprints all version bodies + \enddocument onto the input stack so the
% source body is never processed directly.
\AddToHook{begindocument/end}{%
	% Unconditional: the Lua function checks #autoexam_versions == 0 and
	% returns immediately when no versions are declared.  Keeping the TeX
	% side conditional-free avoids an open \ifx on the stack when Lua
	% sprints \enddocument, which would otherwise produce a benign but
	% confusing "incomplete \ifx" warning.
	\directlua{texlib.autoexam_run_versions()}%
}

% ---------------------------------------------------------------------------
% Internal rubric-overlay machinery
%
% \rubric{pts}{text}  (two-argument, defined in section 7d) appends a rubric
% item to one of two accumulators depending on which environment is active:
%   \@partsol@rubric  — items collected inside {partsolution}
%   \@sol@rubric      — items collected inside {solution}
%
% The accumulators hold \@rubricline{pts}{text} tokens; they are emitted into
% a 4.5 cm right-side overlay box that has zero declared height/depth so the
% solution content below is not displaced.
%
% Flags \if@in@partsolution and \if@in@solution let \rubric know which
% accumulator to use without redefining itself.
% ---------------------------------------------------------------------------

\newif\if@in@partsolution  \@in@partsolutionfalse
\newif\if@in@solution      \@in@solutionfalse

\newbox\@partsol@box
\newbox\@sol@box
\gdef\@partsol@rubric{}
\gdef\@sol@rubric{}

\newlength{\rubricboxwidth}
\setlength{\rubricboxwidth}{4.5cm}

% \@rubricline{pts}{text}  — renders one aligned rubric item inside the box.
%   [1 pt] / [N pts] label in a fixed 1.4 cm makebox, then the description.
\newcommand{\@rubricline}[2]{%
	\noindent
	\makebox[1.4cm][l]{%
		\textbf{\textcolor{teal!80!black}{%
			[#1\,\ifnum#1=1 pt\else pts\fi]}}}%
	#2\par\smallskip
}

% \@emit@rubric@overlay{accumulator-macro}
%   Emits the right-side rubric overlay box.  Zero height/depth so the
%   solution content below is not pushed down.  Uses \hfill\llap so the
%   box's right edge sits exactly at \textwidth.
\newcommand{\@emit@rubric@overlay}[1]{%
	\hfill
	\llap{%
		\raisebox{0pt}[0pt][0pt]{%
			\setlength{\fboxsep}{4pt}%
			\colorbox{teal!8}{%
				\begin{minipage}[t]{\dimexpr\rubricboxwidth-8pt\relax}%
					\raggedright\small\sffamily
					\vspace{2pt}%
					\textbf{\textcolor{teal!80!black}{Rubric:}}\\[0.25em]%
					#1%
				\end{minipage}%
			}%
		}%
	}%
}

% {solution}  — full-problem solution block.
%   When \ifsolutions is true the block is displayed in blue with a
%   "Solution:" header and any \rubric items overlaid on the right.
%   When false the content is silently discarded.
%
%   The body is collected into \@sol@box so that \rubric{}{} calls inside
%   can populate \@sol@rubric before the header line is emitted.
%   Collecting without \color{blue} and applying it during \unvbox avoids
%   colour-stack inconsistencies across the vbox boundary.
%
%   The {solution} wrapper is only emitted by the Lua engine when
%   p.solution contains non-whitespace content (see problem_engine.lua),
%   so the header never appears for multi-part problems whose bank entry
%   ends with a bare \solution marker.
\let\solution\relax
\let\endsolution\relax
\newenvironment{solution}{%
	\ifsolutions
		\par
		\gdef\@sol@rubric{}%
		\@in@solutiontrue
		\setbox\@sol@box\vbox\bgroup
			\hsize\textwidth
	\else
		\setbox\z@\vbox\bgroup
	\fi
}{%
	\ifsolutions
		\egroup
		\@in@solutionfalse
		\begin{tcolorbox}[
			enhanced, breakable, sharp corners, frame hidden,
			boxrule=0pt,
			left=8pt, right=4pt, top=4pt, bottom=4pt,
			before skip=10pt, after skip=10pt,
			colback=green!3!white,
			borderline west={1.5pt}{-6pt}{green!50!black},
		]%
			\noindent\textbf{Solution.}%
			\if@autoexam@rubric
				\ifx\@sol@rubric\@empty\else
					\@emit@rubric@overlay{\@sol@rubric}%
				\fi
			\fi
			\par\smallskip
			\unvbox\@sol@box
		\end{tcolorbox}
	\else
		\egroup
	\fi
}

% {partsolution}  — inline per-part solution, placed directly after \ppart.
%   Shown in blue with a "Solution:" header when \ifsolutions is true;
%   silently discarded otherwise.  \rubric{}{} items are overlaid on the
%   right at the same height as the header.
\newenvironment{partsolution}{%
	\ifsolutions
		\par\smallskip
		\gdef\@partsol@rubric{}%
		\@in@partsolutiontrue
		\setbox\@partsol@box\vbox\bgroup
			\hsize\textwidth
	\else
		\setbox\z@\vbox\bgroup
	\fi
}{%
	\ifsolutions
		\egroup
		\@in@partsolutionfalse
		% Inline style (no tcolorbox -- avoids breakage inside exam-class 'parts').
		% Green prose with bold "Solution." inline header, matching didactic's accent color.
		\noindent\textbf{Solution.}%
		\if@autoexam@rubric
			\ifx\@partsol@rubric\@empty\else
				\@emit@rubric@overlay{\@partsol@rubric}%
			\fi
		\fi
		\par
		{\color{green!40!black}\unvbox\@partsol@box}%
		\normalcolor\par\smallskip
	\else
		\egroup
	\fi
}

% PDF Split Signal (For the Builder)
\newwrite\splitfile
\newcommand{\SplitPdfHere}{%
	\immediate\openout\splitfile=\jobname.spl%
	\immediate\write\splitfile{split_page=\thepage}%
	\immediate\closeout\splitfile%
}

% Minimal Key Generation (Writes to .key file)
\newwrite\keyfile
\immediate\openout\keyfile=\jobname.key

\newcommand{\key}[1]{%
	\immediate\write\keyfile{Q\thequestion: #1}%
	\ifsolutions
		\par\noindent\fbox{\textbf{Key:} #1}
	\fi
}

% Horizontal Separator
\newcommand{\qsep}{%
	\par\vspace{1em}
	\begingroup
		\noindent\hspace*{-\@totalleftmargin}%
		\rule{\textwidth}{0.4pt}% 
	\endgroup
	\par\vspace{1em}
}

% Smart Nested Columns
\newif\ifinparts
\inpartsfalse
\newcounter{global_partno_storage}
\newcounter{tracker_question_no}
\setcounter{tracker_question_no}{-1}

\let\oldparts\parts
\let\endoldparts\endparts

\RenewDocumentEnvironment{parts}{}{%
	\oldparts\inpartstrue
	\ifnum\value{question}=\value{tracker_question_no}
		\ifnum\value{global_partno_storage}>0
			\setcounter{partno}{\value{global_partno_storage}}%
		\fi
	\else
		\setcounter{global_partno_storage}{0}%
		\setcounter{tracker_question_no}{\value{question}}%
	\fi
}{%
	\setcounter{global_partno_storage}{\value{partno}}%
	\endoldparts\inpartsfalse
}

\DeclareDocumentEnvironment{cols}{O{2}}{%
	\par 
	\setlength{\columnseprule}{0pt}
	\setlength{\columnsep}{3em}
	\ifinparts
		\setcounter{global_partno_storage}{\value{partno}}%
	\fi
	\begin{multicols}{#1}
		\ifinparts
			\renewcommand{\partshook}{%
				\setlength{\leftmargin}{0.0em}%
				\setlength{\labelsep}{0.3em}%
				\setlength{\labelwidth}{1.2em}%
			}
			\begin{parts}
		\else
		\fi
}{%
		\ifinparts
			\end{parts}
		\else
		\fi
	\end{multicols}
}

% \splitpage{col1}{col2}
%   Side-by-side two-column layout.  \part items in each column are sequentially
%   labelled across both columns: parts in col1 are (a), (b), …; parts in col2
%   continue as (c), (d), … because the {parts} counter-tracking mechanism
%   (global_partno_storage) carries state across the two internal {parts} calls.
%
%   Usage (inside a \question or \problem body):
%     \splitpage{
%         \part First problem...
%         \part Second problem...
%     }{
%         \part Third problem...
%         \part Fourth problem...
%     }
%
%   Content without \part items (e.g., side-by-side TikZ grids) also works:
%   the empty {parts} wrapper adds negligible overhead.
%
%   Note: \splitpage is a question-level construct.  Nesting it inside an
%   existing {parts} environment is not supported.
\NewDocumentCommand{\splitpage}{+m +m}{%
	\par\noindent
	\begin{minipage}[t]{0.48\linewidth}%
		\renewcommand{\partshook}{%
			\setlength{\leftmargin}{\leftmarginii}%  match standard nested-list indent
			\setlength{\labelsep}{0.5em}%
			\setlength{\labelwidth}{1.5em}%
		}%
		\begin{parts}%
			#1%
		\end{parts}%
	\end{minipage}%
	\hfill
	\begin{minipage}[t]{0.48\linewidth}%
		\renewcommand{\partshook}{%
			\setlength{\leftmargin}{\leftmarginii}%  match standard nested-list indent
			\setlength{\labelsep}{0.5em}%
			\setlength{\labelwidth}{1.5em}%
		}%
		\begin{parts}%
			#2%
		\end{parts}%
	\end{minipage}%
	\par
}

% --- Document-specific metadata ---
% Storage lives in expl3 tls set by the meta keys below; read via the
% \GetExamNumber / \GetExamDate / \GetExamPostscript getters (defined with the
% keys).  The legacy \theExamNumber / \theExamDate / \thePS names survive as
% deprecated \let aliases of those getters.

% Course-metadata aliases (\theCourseNumber, \theCourseTitle, \theCourseSection,
% \theSeason, \theYear, \theSchool, ...) are provided by course-metadata.sty
% as \providecommand's, so individual documents may \renewcommand them.
% \questionlabel / \partlabel are set in texlib-assessment (shared with quiz).

% Top-level enumerate: bold lowercase-roman labels (i., ii., iii., ...).
% enumitem is intentionally NOT loaded in this class (see section 1 — it
% patches \list and breaks exam.cls's questions/parts), so we set the kernel
% label and counter macros directly.  \theenumi is switched to roman too, so
% any \ref to an enumerate item matches the printed label.
\renewcommand{\theenumi}{\roman{enumi}}
\renewcommand{\labelenumi}{\textbf{\theenumi.}}

% Custom Macros
% Math macros (\mbb, \mrm, \dd, \todo, plus \abs, \lrp, \deriv, \inte, ...)
% are provided by texlib-mathutils.sty (transitively via texlib-corepkg).
% \encircle (and \extracredit, available if needed) come from texlib-itemfmt.
\RequirePackage{texlib-itemfmt}

% Theorem environments come from texlib-thmenv.sty (shared with quiz.cls):
% the lightweight unboxed `thm* / defn* / cor* / ...` family.
\RequirePackage{texlib-thmenv}
\TeXLibStarredThms

% Instructions: mints the exam-instructions inline key, \GetExamInstructions,
% \IfExamInstructions{File,Inline}, and \exam@input@userinstructions (default
% file autoexam-instructions.tex). exam-instructions-file lives in
% course-metadata.sty (set per exam via \meta or course-wide in coursemeta.tex).
\TeXLibDeclareInstructions[autoexam-instructions]{exam}

% Exam metadata is set via the unified \meta{...} command, sharing the
% same keys family as every other TeXLib class. Use \meta{exam-number=5,
% exam-date=May 2 2026, ...} in the preamble. The legacy \examsetup{...}
% command remains supported as a thin alias that prefixes bare keys with
% "exam-" so old documents continue to work.
\ExplSyntaxOn
\tl_new:N \g__autoexam_number_tl
\tl_new:N \g__autoexam_title_tl
\tl_new:N \g__autoexam_date_tl
\tl_new:N \g__autoexam_postscript_tl
\keys_define:nn { meta } {
	exam-number             .tl_gset:N = \g__autoexam_number_tl,
	exam-title              .tl_gset:N = \g__autoexam_title_tl,
	exam-date               .tl_gset:N = \g__autoexam_date_tl,
	exam-postscript         .tl_gset:N = \g__autoexam_postscript_tl,
	% exam-instructions-file lives in course-metadata.sty (so a course can set it
	% course-wide); the bare `instructions-file` alias below writes the same store.
	% Backward-compat aliases (bare names available via \examsetup or \meta)
	number                  .tl_gset:N = \g__autoexam_number_tl,
	title                   .tl_gset:N = \g__autoexam_title_tl,
	date                    .tl_gset:N = \g__autoexam_date_tl,
	ps                      .tl_gset:N = \g__autoexam_postscript_tl,
	instructions-file       .tl_gset:c = { g__meta_exam-instructions-file_tl },
}
% Canonical expandable getters (the \Get... convention shared with every other
% TeXLib class).  Number/date keep autoexam's historical \todo default when
% unset; postscript defaults to empty.
\NewExpandableDocumentCommand{\GetExamNumber}{}{
	\tl_if_empty:NTF \g__autoexam_number_tl { \todo } { \tl_use:N \g__autoexam_number_tl }
}
\NewExpandableDocumentCommand{\GetExamDate}{}{
	\tl_if_empty:NTF \g__autoexam_date_tl { \todo } { \tl_use:N \g__autoexam_date_tl }
}
\NewExpandableDocumentCommand{\GetExamPostscript}{}{ \tl_use:N \g__autoexam_postscript_tl }
% \GetExamTitle -- left-header title; defaults to "Exam <n>" (cf. \GetPsetTitle
% -> "Problem Set <n>", \GetQuizTitle -> "Quiz <n>"), overridable via exam-title.
\NewExpandableDocumentCommand{\GetExamTitle}{}{
	\tl_if_empty:NTF \g__autoexam_title_tl
		{ Exam~\GetExamNumber }
		{ \tl_use:N \g__autoexam_title_tl }
}

% Apply document metadata from the class option list now that the exam-meta keys
% above and coursemeta.tex are loaded (so document options override coursemeta).
% Read \@raw@classoptionslist, not \CurrentOption, to keep spaces in values.
\cs_if_exist:cT { @raw@classoptionslist } {
	\tl_set:Nv    \l_tmpa_tl    { @raw@classoptionslist }
	\clist_set:NV \l_tmpa_clist \l_tmpa_tl
	\clist_map_inline:Nn \l_tmpa_clist {
		\tl_if_in:nnT { #1 } { = } { \keys_set:nn { meta } { #1 } }
	}
}
\ExplSyntaxOff

% Deprecated aliases: \theExamNumber / \theExamDate / \thePS were the storage
% and the public names before the \Get... normalization.  Kept as thin
% expandable aliases so existing exam documents that reference them keep
% rendering.  New code should use \GetExamNumber / \GetExamDate /
% \GetExamPostscript.
\let\theExamNumber\GetExamNumber
\let\theExamDate\GetExamDate
\let\thePS\GetExamPostscript

% \examsetup{...}: backward-compat alias for \meta{...}. Old exam files
% can keep using \examsetup{number=5, date=May 2 2026, ps=...}; these
% bare keys forward to the meta family above.
\NewDocumentCommand{\examsetup}{+m}{\metasetup{#1}}

% \autoexam@problem@sep — full-width rule inserted between consecutive problems
%   within a page group (i.e., problems not separated by \newpage).
%   Emitted automatically by \problem via the Lua engine for all but the first
%   problem on each page.  Redefine to change the separator style.
% Override the default \par\medskip from texlib-problembank.sty with a
% full-width rule between consecutive problems on the same page.
\renewcommand{\autoexam@problem@sep}{%
	\par\vspace{1em}%
	\noindent\hspace*{-\@totalleftmargin}\rule{\linewidth}{0.4pt}%
	\par\vspace{1em}%
}

% \blankpage — outputs one scratch-work leaf.
%
% Ships the current page (problem page or previous scratch page) via \clearpage,
% then starts a new leaf with "Scratch Work" in the center header and a blank
% center footer.  Use after \maketitle and/or after \end{problems}:
%   \maketitle
%   \blankpage          % pre-problem scratch page
%   \begin{problems}
%     …
%   \end{problems}
%   \blankpage          % post-problem scratch pages
%   \blankpage
%
% \end{problems} places \label{@lastqpage} on the last problem page; the first
% \blankpage that follows ships it (recording the correct page number for the
% "X of N" footer) before starting the scratch leaf.
\newcommand{\blankpage}{%
	\clearpage
	\def\run@chead{Scratch Work}%   % center header on scratch leaves
	\def\run@cfoot{}%               % no page number on scratch leaves
	\null
}

% \graph[options]{xmin}{xmax}{ymin}{ymax}
%   Draws a coordinate-plane grid: dashed help lines, axis arrows with labels,
%   and tick marks at every integer.  One TikZ unit = 1 cm, so the axis ranges
%   map directly to physical dimensions (e.g. \graph{-3}{3}{-3}{3} produces a
%   6 cm × 6 cm picture).
%
%   Options (key=value, comma-separated in the optional argument):
%     grid = true | false  — toggle dashed grid lines (default: true)
%
%   Examples:
%     \graph{-3}{3}{-3}{3}             % 6×6 blank unit grid (default)
%     \graph[grid=false]{-4}{4}{-2}{2} % axes and ticks only, no grid
%
%   Typical use with \splitpage for side-by-side graph problems:
%     \splitpage{
%         \part $y = 2^x - 1$  \par\centering\graph{-3}{3}{-3}{3}
%     }{
%         \part $y = \log_2(x+2)$  \par\centering\graph{-3}{3}{-3}{3}
%     }
\newif\if@autoexam@graph@grid
\@autoexam@graph@gridtrue   % default: show grid
\def\@autoexam@graph@scale{0.9}  % default scale (fits inside \splitpage minipage)

\pgfkeys{
	/autoexam/graph/grid/.is if       = @autoexam@graph@grid,
	/autoexam/graph/grid/.default     = true,
	/autoexam/graph/scale/.store in   = \@autoexam@graph@scale,
	/autoexam/graph/scale/.default    = 0.9,
}

\NewDocumentCommand{\graph}{O{} m m m m}{%
	% Reset per-call defaults, then parse caller's options.
	\@autoexam@graph@gridtrue
	\def\@autoexam@graph@scale{0.9}%
	\pgfqkeys{/autoexam/graph}{#1}%
	\begin{tikzpicture}[scale=\@autoexam@graph@scale]%
		% Dashed help lines
		\if@autoexam@graph@grid
			\draw[help lines, color=black!40, dashed] (#2,#4) grid (#3,#5);
		\fi
		% x-axis with rightward arrow
		\draw[->,thick] ({#2-0.35},0) -- ({#3+0.35},0) node[right]{$x$};
		% y-axis with upward arrow
		\draw[->,thick] (0,{#4-0.35}) -- (0,{#5+0.35}) node[above]{$y$};
		% Tick marks at each integer on the x-axis
		\foreach \tick in {#2,...,#3} {%
			\draw[thin] (\tick, 2pt) -- (\tick, -2pt);
		}%
		% Tick marks at each integer on the y-axis
		\foreach \tick in {#4,...,#5} {%
			\draw[thin] (2pt, \tick) -- (-2pt, \tick);
		}%
	\end{tikzpicture}%
}

% \workbox{n}  — proportional answer space, equivalent to \vspace{\stretch{n}}.
%   Semantically marks an intentional student answer area.  The stretch factor n
%   is distributed across the page exactly as \vspace{\stretch{n}} would be —
%   there is no visible difference for students.
%
%   The abstraction pays off in rubric/solution builds: \rubric annotations can
%   accompany each \workbox to give graders per-step point guidance without
%   cluttering the blank exam layout.
%
%   Example:
%     \question[10] Solve $3^{x+2} = 81$.
%     \workbox{3}
%     \rubric{5}{convert $81=3^4$}
%     \rubric{5}{solve $x=2$}
% Override the always-on default from texlib-problembank.sty so a solution
% (key) build does not pad each problem with stretchy answer space.
\RenewDocumentCommand{\workbox}{m}{%
	\ifsolutions\else
		\vspace{\stretch{#1}}%
	\fi
}

% \rubric{pts}{text}  — adds one grading criterion shown only when the
%   ShowRubric flag is set (\rubrics in preamble or \def\ShowRubric{1}).
%
%   Each call appends one \@rubricline{pts}{text} item to the accumulator
%   of the currently active solution environment:
%     • inside {partsolution}  → \@partsol@rubric
%     • inside {solution}      → \@sol@rubric
%   Items are emitted as a right-side overlay box with zero height so the
%   solution text is not displaced (see \@emit@rubric@overlay above).
%
%   Multiple calls accumulate:
%     \rubric{1}{expand numerator}
%     \rubric{1}{simplify using exponent rules}
%
%   Works anywhere before first use because the check is at execution time.
\NewDocumentCommand{\rubric}{mm}{%
	\if@autoexam@rubric
		\if@in@partsolution
			\expandafter\gdef\expandafter\@partsol@rubric\expandafter{%
				\@partsol@rubric\@rubricline{#1}{#2}}%
		\else
			\if@in@solution
				\expandafter\gdef\expandafter\@sol@rubric\expandafter{%
					\@sol@rubric\@rubricline{#1}{#2}}%
			\fi
		\fi
	\fi
}

% \begin{commonerrors}...\end{commonerrors}
%   Block of common student errors shown only in rubric builds.
%   Use \item for each error.  Content is suppressed (collected into a
%   discarded box) when ShowRubric is off, so it adds no overhead to student
%   PDFs.  Does not support verbatim content inside the hidden branch.
%
%   Example:
%     \begin{commonerrors}
%         \item Forgetting to rewrite the base before equating exponents.
%         \item Sign error when solving $3 - x = 4$.
%     \end{commonerrors}
\newenvironment{commonerrors}{%
	\if@autoexam@rubric
		\par\smallskip
		\noindent\textcolor{red!80!black}{\small\sffamily\textbf{Common Errors:}}%
		\begin{itemize}\small\sffamily
	\else
		\setbox\z@\vbox\bgroup
	\fi
}{%
	\if@autoexam@rubric
		\end{itemize}\smallskip
	\else
		\egroup
	\fi
}

% \scorepage[max_rows]  — auto-generated instructor score sheet.
%   Place after \maketitle (before \blankpage and \begin{problems}).
%   Point data is read directly from the \problem calls in the document
%   via a Lua prescan that runs at \AtBeginDocument time.
%   The page is generated correctly on the first compilation pass.
%
%   Optional argument max_rows (default 20): maximum number of table rows
%   per page.  When the table exceeds this limit, the current page is closed
%   and a "Score Summary (cont.)" page begins automatically.  Problems are
%   never split mid-entry; breaks happen only between questions.
%   Example: \scorepage[12]  — force a new continuation page after 12 rows.
%
%   Layout: centered "Score Summary" title, "Instructor Use Only" banner,
%   then a 5-column table (Page | Problem | Part | Points | Score) with one
%   row per part for multi-part questions, or a single "---" row for
%   single-part questions.  A grand Total row closes the final page.

\NewDocumentCommand{\scorepage}{O{20}}{%
	\directlua{texlib.autoexam_scorepage(#1)}%
}

% texlib-pagestyle.sty bundles \pagestyle{headandfoot} + first-page-footer
% rule + running head/foot rules into one call.  Identical boilerplate is
% used by quiz.cls.
\RequirePackage{texlib-pagestyle}
\SetTeXLibExamRules
% Center footer shows "X of N" where N = last problem page via \label{@lastqpage}
% (placed by \blankpage on first call).  Falls back to \numpages until that label
% exists, and for exams without \blankpage at the end.
% Footer L: full course name via the shared \GetCourse ("Math 181 Calculus I").
\firstpagefooter{\GetCourse}{%
	\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
}{\GetInstitution}
\runningheader{\bfseries\GetExamTitle}{}{\GetTermSection}
\runningfooter{\GetCourse}{%
	\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
}{\GetInstitution}

\renewcommand{\maketitle}{%
	% ---- suppress header/footer on the title page ----------------------------
	% Reset page counter to 1 so the exam class's headandfoot style always uses
	% the first-page header slots on the cover page.  The style checks
	% \value{page}==1 at OUTPUT time; without this reset, versions B/C land on
	% page 7, 15, … and the exam class falls through to the running slots
	% (\run@chead), which may still hold "Scratch Work" from the previous
	% version's \blankpage.  \begin{problems} resets the counter again to 1, so
	% Q1 is always page 1 of the problem section.
	\setcounter{page}{1}%
	% Clear first-page header slots so nothing appears above the title block.
	\def\@lhead{}\def\@chead{}\def\@rhead{}%
	\@headrulefalse%
	% Clear center footer to prevent page-number bleed from the previous version's
	% \begin{problems} (which sets \@cfoot to the "X of N" formula).
	\def\@cfoot{}%
	\thispagestyle{headandfoot}%
	% ---- title block ---------------------------------------------------------
	\begin{center}
		\huge Exam \GetExamNumber \\
		\LARGE Math \theCourseNumber\ \theCourseTitle \\
		\vspace{0.1em}
		\large \GetExamDate
		% Build-mode label: shown in red when solutions and/or rubrics are on.
		\ifsolutions
			\if@autoexam@rubric
				\\ \large\textcolor{red}{\textbf{Solutions and Rubrics}}%
			\else
				\\ \large\textcolor{red}{\textbf{Solutions}}%
			\fi
		\else
			\if@autoexam@rubric
				\\ \large\textcolor{red}{\textbf{Rubrics}}%
			\fi
		\fi

		\vspace{1em}

		% Version circle: only shown when \versions/\examversions was declared.
		\if@autoexam@versioned
			{\Large Version \encircle{\theExamVersion}}%
		\fi
		\vfill

		% Instructions: a user-set exam-instructions-file controls its own layout
		% (no box); inline text and the default autoexam-instructions.tex are boxed.
		\IfExamInstructionsFile{%
			\exam@input@userinstructions
		}{%
			\fbox{\fbox{\parbox{\dimexpr\linewidth-4\fboxsep-4\fboxrule\relax}{%
				\noindent{\large\bf Instructions:}
				\TeXLibInstructionsInlineOrDefault{exam}%
			}}}%
		}%
		\vfill

		Name: \underline{\hspace{4in}}
		\vfill

		\ifthenelse{\equal{}{\GetExamPostscript}}%
			{}%
			{\textit{\GetExamPostscript}}%
	\end{center}
	% Title page is complete.  The user adds \blankpage after \maketitle to produce
	% a pre-problem scratch leaf.  \blankpage ships this page via \clearpage, sets
	% scratch style, and outputs \null.  \begin{problems} then resets the page
	% counter and restores problem headers.
}