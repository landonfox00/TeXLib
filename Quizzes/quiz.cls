% quiz.cls
% UNR In-Class Quiz Class — TeXLib unified style (subclass of exam.cls)
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{quiz}[2026/05/07 v1.0 UNR In-Class Quizzes (TeXLib)]

% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[quiz-number=3, quiz-title={Pop Quiz}]{quiz}
% Any option containing "=" is a metadata key=value pair; every other option is
% forwarded to exam. Metadata is applied below (after the quiz keys and
% coursemeta load, so document options win) by reading \@raw@classoptionslist
% directly — that list preserves spaces in values, unlike the \CurrentOption
% seen here. \DeclareOption* only forwards the non-metadata options; the
% key=value ones still pass through it (a no-op) so the kernel marks them used.
% Safe because no base-class option uses key=value form.
\DeclareOption*{%
	\@expandtwoargs\in@{=}{\CurrentOption}%
	\ifin@\else
		\PassOptionsToClass{\CurrentOption}{exam}%
	\fi
}
\ProcessOptions\relax
\LoadClass[11pt]{exam}

% A class-option value containing a comma (e.g. a date like {May 2, 2026}) is
% split by the kernel's option parser into a stray fragment with no "=", which
% would be reported as an "unused global option". The real values are consumed
% from \@raw@classoptionslist below, so discard those spurious leftovers.
\AtEndOfClass{\global\let\@unusedoptionlist\@empty}

% Shared assessment setup (texlib-corepkg, texlib-build, course-metadata, the
% common aux packages, and the unified problem/part labels). Shared with autoexam.
\RequirePackage{texlib-assessment}

% Shared document-instructions mechanism (inline / file / default, file > inline
% > default). \TeXLibDeclareInstructions{quiz} below mints \GetQuizInstructions,
% \IfQuizInstructions{File,Inline}, and \quiz@input@userinstructions.
\RequirePackage{texlib-instructions}

% quiz-only packages. enumitem is intentionally absent: it conflicts with
% exam.cls's \list redefinition (used by questions/parts).
\RequirePackage{adjustbox}
\RequirePackage{tocloft}

% Provided by texlib-build (loaded via texlib-assessment): \ifsolutions, \ifkey,
% \ifrubric, \ifdraft, \ifstudent, \ifinstructor and the matching CLI toggles.

\ExplSyntaxOn

\tl_new:N \g__quiz_number_tl
\tl_new:N \g__quiz_title_tl

\keys_define:nn { meta } {
	quiz-number             .tl_gset:N = \g__quiz_number_tl,
	quiz-title              .tl_gset:N = \g__quiz_title_tl,
}

\NewExpandableDocumentCommand{\GetQuizNumber}{}{ \tl_use:N \g__quiz_number_tl }
\NewExpandableDocumentCommand{\GetQuizTitle}{}{
	\tl_if_empty:NTF \g__quiz_title_tl
		{ Quiz~\GetQuizNumber }
		{ \tl_use:N \g__quiz_title_tl }
}

\ExplSyntaxOff

% Instructions: mints the quiz-instructions inline key, \GetQuizInstructions,
% \IfQuizInstructions{File,Inline}, and \quiz@input@userinstructions (default
% file quiz-instructions.tex). quiz-instructions-file lives in course-metadata.sty
% (set per quiz via \meta or course-wide in coursemeta.tex).
\TeXLibDeclareInstructions{quiz}

% Apply document metadata from the class option list now that the quiz keys
% above and coursemeta.tex are loaded (so document options override coursemeta).
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

% texlib-problembank.sty loads problem_engine.lua and defines the shared
% problem-bank LaTeX glue (\setvar, \setrng, \pick*, \getproblem,
% \begin{problem}, \ppart, \@problem@item, \importproblem, ...).  Quizzes
% have no versioning, so the engine's set_exam_seed() is never called and
% math.random falls back to its default seed — fine for in-class quizzes
% that don't need reproducible per-version values.  See
% texlib-problembank.sty for the full API.
\RequirePackage{texlib-problembank}

% \loadbank is provided by texlib-problembank.sty. A coursemeta bank-path and a
% sibling bank.tex are auto-loaded below (shared resolution, see
% \pbank@load@coursebank), so per-quiz \loadbank is usually unnecessary. Quizzes
% set no RNG seed (single-version by design), so the hook is just the bank load.
\AtBeginDocument{\pbank@load@coursebank}

% \begin{problems} is provided by texlib-problembank.sty (shared with
% autoexam.cls).  Quizzes need no page-section setup, so the shared
% \problems@begin@hook / \problems@end@hook are left at their no-op defaults:
% the environment simply wraps {questions} and enables the \problem item
% command.  (autoexam fills those hooks with \clearpage, a page-counter reset,
% header/footer slots, and a single-use guard — none of which quizzes want.)

% Math macros (\mbb, \abs, \lrp, \dd, \deriv, \inte, \todo, ...) are provided
% by texlib-mathutils.sty, loaded in section 1 above.

% Theorem environments come from texlib-thmenv.sty (shared with autoexam.cls):
% the lightweight unboxed `thm* / defn* / cor* / ...` family.
\RequirePackage{texlib-thmenv}
\TeXLibStarredThms

% \questionlabel / \partlabel are set in texlib-assessment (shared with autoexam).

% \encircle and \extracredit come from texlib-itemfmt.sty.
\RequirePackage{texlib-itemfmt}

\NewDocumentCommand{\fig}{ O{} m }{%
	\begin{figure}[!h]
		\centering
		\includegraphics[width=0.5\textwidth, height=0.35\textwidth,
							keepaspectratio, #1]{Figures/#2}
	\end{figure}%
}

% texlib-pagestyle.sty bundles \pagestyle{headandfoot} + first-page-footer
% rule + running head/foot rules into \SetTeXLibExamRules.  Quiz adds the
% first-page header rule on top (its title page carries a name field).
\RequirePackage{texlib-pagestyle}
\RequirePackage{lastpage}    % \pageref{LastPage} for the shared "X of Y" footer
% \title is auto-derived from metadata.
\AtBeginDocument{%
	\title{\LARGE \GetQuizTitle}%
	\SetTeXLibExamRules
	\firstpageheadrule
	% First page omits the left title -- the large "Quiz <n>" heading sits just
	% below it. Running pages carry \GetQuizTitle on the left instead.
	\firstpageheader{}{}{Name:\ \underline{\hspace{2.5in}}}%
	% Footer L: full course name via the shared \GetCourse ("Math 181 Calculus I").
	\firstpagefooter{\GetCourse}{\thepage\ of \pageref{LastPage}}{\GetInstitution}%
	\runningheader{\bfseries\GetQuizTitle}{}{Name:\ \underline{\hspace{2.5in}}}%
	\runningfooter{\GetCourse}{\thepage\ of \pageref{LastPage}}{\GetInstitution}%
}

\renewcommand{\maketitle}{%
	% Instructions: file overrides inline text overrides default.
	% File content controls its own layout (no automatic box around it).
	\IfQuizInstructionsFile{%
		\begin{center}
			{\LARGE \GetQuizTitle}%
			\ifkey\par\vspace{0.4em}\textit{Answer~Key}\fi
		\end{center}
		\quiz@input@userinstructions
	}{%
		\begin{center}
			{\LARGE \GetQuizTitle}%
			\ifkey\par\vspace{0.4em}\textit{Answer~Key}\fi
			\par\medskip
			% Inline text typesets directly; the default wording is \input from
			% quiz-instructions.tex so double-clicking it in the PDF lands on that
			% source (inverse search).
			\TeXLibInstructionsBox{\TeXLibInstructionsInlineOrDefault{quiz}}%
		\end{center}
	}%
}

% Course-metadata aliases (\theCourse, \theCourseNumber, \theCourseTitle,
% \theCourseSection, \theSeason, \theYear, \theTerm, \theSchool, ...) are
% provided by course-metadata.sty.  Quiz-specific aliases stay here.
\providecommand{\theQuizNumber}{\GetQuizNumber}
\providecommand{\theTitle}{\GetQuizTitle}

\endinput
