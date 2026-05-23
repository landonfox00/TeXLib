% quiz.cls
% UNR In-Class Quiz Class — TeXLib unified style (subclass of exam.cls)
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{quiz}[2026/05/07 v1.0 UNR In-Class Quizzes (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{exam}}
\ProcessOptions\relax
\LoadClass[11pt]{exam}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage[T1]{fontenc}
\RequirePackage{lmodern}
\RequirePackage[margin=1in]{geometry}
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{ifthen}
\RequirePackage{etoolbox}
\RequirePackage{adjustbox, changepage, comment}
% NOTE: enumitem is intentionally NOT loaded at the top level — it is known to
% conflict with exam.cls's redefinition of \list (used by `questions`/`parts`).
% Quizzes that need enumitem-style lists may load it locally.
\RequirePackage{graphicx}
\RequirePackage{lastpage}
\RequirePackage{needspace}
\RequirePackage{xcolor}
\RequirePackage{amsmath, amssymb, amsthm, mathtools}
\RequirePackage{texlib-mathutils}  % \mbb, \abs, \lrp, \dd, \deriv, \inte, \todo, ...
\RequirePackage{cancel}
\RequirePackage{pdfpages}
\RequirePackage{tocloft}
\RequirePackage{tikz, pgfplots}
\pgfplotsset{compat=1.18}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric}

\RequirePackage{hyperref}
\hypersetup{colorlinks=true, urlcolor=blue, linkcolor=black, citecolor=black}

\RequirePackage{course-metadata}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}


% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\tl_new:N \g__quiz_number_tl
\tl_new:N \g__quiz_title_tl
\tl_new:N \g__quiz_instructions_tl
\tl_new:N \g__quiz_instructions_file_tl

\keys_define:nn { meta } {
	quiz-number             .tl_gset:N = \g__quiz_number_tl,
	quiz-title              .tl_gset:N = \g__quiz_title_tl,
	quiz-instructions       .tl_gset:N = \g__quiz_instructions_tl,
	quiz-instructions-file  .tl_gset:N = \g__quiz_instructions_file_tl,
}

\NewExpandableDocumentCommand{\GetQuizNumber}{}{ \tl_use:N \g__quiz_number_tl }
\NewExpandableDocumentCommand{\GetQuizTitle}{}{
	\tl_if_empty:NTF \g__quiz_title_tl
		{ Quiz~\GetQuizNumber }
		{ \tl_use:N \g__quiz_title_tl }
}
\NewExpandableDocumentCommand{\GetQuizInstructions}{}{
	\tl_if_empty:NTF \g__quiz_instructions_tl
		{ Notes~or~other~aids~are~not~allowed.~ Calculators~of~any~kind~are~not~permitted.~
			To~receive~full~credit,~you~must~show~all~of~your~work.~ Write~your~answers~in~
			the~space~provided,~and~box~or~circle~all~final~answers. }
		{ \tl_use:N \g__quiz_instructions_tl }
}
\NewExpandableDocumentCommand{\GetQuizInstructionsFile}{}{
	\tl_use:N \g__quiz_instructions_file_tl
}
% \IfQuizInstructionsFile{true}{false} — branch on whether a file was set.
\NewDocumentCommand{\IfQuizInstructionsFile}{ +m +m }{
	\tl_if_empty:NTF \g__quiz_instructions_file_tl { #2 } { #1 }
}

\ExplSyntaxOff

% ==============================================================================
% 4. PROBLEM BANK & LUA ENGINE (shared with autoexam)
% ==============================================================================
% Loads autoexam_engine.lua so quizzes can use the same problem-bank workflow
% as exams: define problems with \newproblem / \begin{problem}, store them
% in a file loaded via \loadbank, then retrieve them inside the questions
% environment with \getproblem{id} or \getproblem{key=val, ...}.
%
% Randomization helpers (\setrng, \picklist, \pickrange, ...) are also
% available even though quizzes don't have versioning. Use them to vary
% numerical values across reuses of the same quiz.
%
% Locates autoexam_engine.lua across three possible layouts (mirrors the
% loader in autoexam.cls so both classes resolve the same canonical file):
%   (1) installed in a TEXMF tree              → kpse with the "lua" format
%   (2) sitting next to quiz.cls               → legacy per-module copy
%   (3) at the TeXLib root, one level up       → current canonical layout
% The cwd fallback covers standalone test layouts.
% NOTE: no Lua `--` line comments inside this \directlua block. TeX collapses
% the newlines into spaces before Lua sees the chunk, so a `--` comment would
% swallow the rest of the code. Keep explanations in TeX `%` comments above.
\directlua{
	local function load_engine(name)
		local cls_path = kpse.find_file("quiz.cls")
		local base_dir = cls_path and cls_path:match("(.*[/\\\\])") or ""
		local path = kpse.find_file(name, "lua")
		if not path or not lfs.attributes(path) then
			path = base_dir .. name
			if not lfs.attributes(path) then
				path = base_dir .. "../" .. name
				if not lfs.attributes(path) then
					path = name
				end
			end
		end
		dofile(path)
	end
	load_engine("autoexam_engine.lua")
}

% --- Variable management ---
\newcommand{\setvar}[2]{\directlua{set_var('#1', #2)}}
\newcommand{\setrng}[3]{\directlua{set_rng('#1', #2, #3)}}
\newcommand{\calcvar}[2]{\directlua{calc_var('#1', '#2')}}
\newcommand{\get}[1]{\directlua{get_var('#1')}}

% --- Pick from list / range ---
\NewDocumentCommand{\picklist}{m m m}{%
	\directlua{pick_from_list('\luaescapestring{#1}', #2, '\luaescapestring{#3}')}%
}
\NewDocumentCommand{\picklistr}{m m m}{%
	\directlua{pick_from_list_r('\luaescapestring{#1}', #2, '\luaescapestring{#3}')}%
}
\NewDocumentCommand{\pickrange}{m m m m}{%
	\directlua{pick_from_range('\luaescapestring{#1}', #2, #3, #4)}%
}
\NewDocumentCommand{\pickranger}{m m m m}{%
	\directlua{pick_from_range_r('\luaescapestring{#1}', #2, #3, #4)}%
}

% --- Retrieval helpers ---
\NewDocumentCommand{\getlist}{m}{\directlua{get_list('\luaescapestring{#1}')}}
\NewDocumentCommand{\geti}{m m}{\directlua{get_var('\luaescapestring{#1}_' .. #2)}}

% --- Bank: define problems ---
% \newproblem{id}{meta}{content}[solution]
\NewDocumentCommand{\newproblem}{m m +m +o}{%
	\IfNoValueTF{#4}{%
		\directlua{define_problem(
			'\luaescapestring{#1}',
			'\luaescapestring{#2}',
			'\luaescapestring{\unexpanded{#3}}',
			''
		)}%
	}{%
		\directlua{define_problem(
			'\luaescapestring{#1}',
			'\luaescapestring{#2}',
			'\luaescapestring{\unexpanded{#3}}',
			'\luaescapestring{\unexpanded{#4}}'
		)}%
	}%
}

% \begin{problem}{id}[meta] ... \solution ... \end{problem}
\RequirePackage{environ}
\long\def\@problem@collect@done#1{%
	\directlua{define_problem_from_env(
		'\luaescapestring{\@problem@id}',
		'\luaescapestring{\@problem@meta}',
		'\luaescapestring{\unexpanded{#1}}'
	)}%
}
\def\@problem@scan{%
	\@ifnextchar[%
		{\@problem@getmeta}%
		{\def\@problem@meta{}\Collect@Body\@problem@collect@done}%
}
\def\@problem@getmeta[#1]{%
	\def\@problem@meta{#1}%
	\Collect@Body\@problem@collect@done
}
\newenvironment{problem}[1]{%
	\def\@problem@id{#1}%
	\directlua{autoexam_problem_start_line = tex.inputlineno}%
	\@problem@scan
}{}

% --- Bank: retrieve problems ---
% \getproblem{query} — id or key=val, key=val
\NewDocumentCommand{\getproblem}{m}{%
	\directlua{get_problem('\luaescapestring{#1}')}%
}
\let\useproblem\getproblem
\NewDocumentCommand{\reqproblem}{m}{\getproblem{#1}}

% --- Bank: load bank file ---
\NewDocumentCommand{\loadbank}{m}{%
	\directlua{autoexam_set_bankfile('\luaescapestring{#1}')}%
	\input{#1}%
}

% --- Bank: smart-columns problems environment + \problem item command ---
% Adapted from autoexam.cls.  Inside \begin{problems}...\end{problems},
% \problem[points][stretch]{filter} retrieves a problem from the bank and
% typesets it as a numbered \question. Without the points argument, no
% point label is added to the heading.
%
%   \problem{id}                 — retrieve by id
%   \problem[5]{id}              — with 5-point heading
%   \problem[2,3]{id}            — distributed to \ppart calls
%   \problem{topic=algebra}      — random key=value match
%
% \ppart — part item for use inside problem bodies.  Auto-injects
% per-part points when the enclosing \problem carries a comma-separated
% list (e.g., \problem[2,3]{id}).
\NewDocumentCommand{\ppart}{}{\directlua{autoexam_inject_part()}}

\NewDocumentCommand{\@problem@item}{O{} O{1} m}{%
	\directlua{autoexam_problem_item(
		'\luaescapestring{#1}',
		'\luaescapestring{#2}',
		'\luaescapestring{#3}'
	)}%
}

% \workbox{n}: reserved blank space below a problem (engine emits this).
% In quiz, this is the natural \vspace{\stretch{n}} stretchy spacing.
\providecommand{\workbox}[1]{\vspace{\stretch{#1}}}

% \autoexam@problem@sep: separator between consecutive problems on the
% same page (engine emits this for problems 2+ on each page). For quiz,
% a \par with light vertical space is plenty.
\providecommand{\autoexam@problem@sep}{\par\medskip}

\newenvironment{problems}{%
	\directlua{autoexam_first_on_page = true}%
	\let\@problems@saved@newpage\newpage
	\renewcommand{\newpage}{%
		\@problems@saved@newpage
		\directlua{autoexam_first_on_page = true}%
	}%
	\begin{questions}%
	\let\@saved@problem\problem
	\let\problem\@problem@item
}{%
	\let\problem\@saved@problem
	\let\newpage\@problems@saved@newpage
	\end{questions}%
}

% ==============================================================================
% 5. MATH UTILITIES
% ==============================================================================
% Math macros (\mbb, \abs, \lrp, \dd, \deriv, \inte, \todo, ...) are provided
% by texlib-mathutils.sty, loaded in section 1 above.

% ==============================================================================
% 6. UNSTARRED THEOREM-LIKE ENVIRONMENTS
% ==============================================================================
\newtheorem*{thm*}{Theorem}
\newtheorem*{defn*}{Definition}
\newtheorem*{cor*}{Corollary}
\newtheorem*{prop*}{Proposition}
\newtheorem*{lem*}{Lemma}
\newtheorem*{conj*}{Conjecture}
\newtheorem*{ques*}{Question}
\newtheorem*{prob*}{Problem}
\newtheorem*{exam*}{Example}
\newtheorem*{notn*}{Notation}
\theoremstyle{remark}
\newtheorem*{rmk*}{Remark}
\newtheorem*{recall*}{Recall}
\newtheorem*{case*}{Case}
\newtheorem*{desiderata*}{Desiderata}

% ==============================================================================
% 7. ANSWER FORMATTING
% ==============================================================================
\renewcommand{\questionlabel}{\textbf{\arabic{question}.}}
\renewcommand{\partlabel}{\textbf{\alph{partno}.}}

\newcommand\encircle[1]{%
	\tikz[baseline=(X.base)]
	\node (X) [draw, shape=circle, inner sep=0] {\strut #1};%
}

\NewDocumentCommand{\extracredit}{ o +m }{%
	\stepcounter{question}%
	\item[\textbf{\thequestion.}]%
	\IfValueTF{#1}
		{(\textbf{Extra Credit}, #1 points)~}
		{(\textbf{Extra Credit})~}%
	#2
}

% ==============================================================================
% 8. FIGURE WRAPPER
% ==============================================================================
\NewDocumentCommand{\fig}{ O{} m }{%
	\begin{figure}[!h]
		\centering
		\includegraphics[width=0.5\textwidth, height=0.35\textwidth,
							keepaspectratio, #1]{Figures/#2}
	\end{figure}%
}

% ==============================================================================
% 9. HEADER / FOOTER
% ==============================================================================
% \title is auto-derived from metadata.
\AtBeginDocument{%
	\title{\LARGE \GetQuizTitle}%
	\pagestyle{headandfoot}%
	\firstpageheader{\GetCourse}{}{Name:\ \underline{\hspace{2.5in}}}%
	\firstpageheadrule
	\firstpagefooter{Section\ \GetCourseSection}{}{\GetInstitution}%
	\firstpagefootrule
	\runningheader{\GetCourse}{}{Name:\ \underline{\hspace{2.5in}}}%
	\runningheadrule
	\runningfootrule
	\runningfooter{Section\ \GetCourseSection}{}{\GetInstitution}%
}

% ==============================================================================
% 10. TITLE BLOCK
% ==============================================================================
\renewcommand{\maketitle}{%
	% Instructions: file overrides inline text overrides default.
	% File content controls its own layout (no automatic box around it).
	\IfQuizInstructionsFile{%
		\begin{center}
			{\LARGE \GetQuizTitle}%
			\ifkey\par\vspace{0.4em}\textit{Answer~Key}\fi
		\end{center}
		\input{\GetQuizInstructionsFile}%
	}{%
		\begin{center}
			{\LARGE \GetQuizTitle}%
			\ifkey\par\vspace{0.4em}\textit{Answer~Key}\fi
			\par\medskip
			\fbox{\fbox{\parbox{6.25in}{%
				\centering\footnotesize
				\GetQuizInstructions
			}}}%
		\end{center}
	}%
}

% ==============================================================================
% 11. BACKWARD-COMPAT \the* ALIASES
% ==============================================================================
% Existing quiz files use \theQuizNumber, \theCourseTitle, etc. via \renewcommand.
% Provide them as aliases over the metadata getters.
\providecommand{\theQuizNumber}{\GetQuizNumber}
\providecommand{\theTitle}{\GetQuizTitle}
\providecommand{\theCourseNumber}{\GetCourseNumber}
\providecommand{\theCourseTitle}{\GetCourseTitle}
\providecommand{\theCourse}{\GetCourse}
\providecommand{\theCourseSection}{\GetCourseSection}
\providecommand{\theSeason}{\GetSeason}
\providecommand{\theYear}{\GetYear}
\providecommand{\theTerm}{\GetTerm}
\providecommand{\theSchool}{\GetInstitution}

\endinput
