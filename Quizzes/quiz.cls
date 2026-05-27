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
% Core bundle: fontenc/lmodern/geometry, expl3/xparse/ifthen/etoolbox, xcolor,
% amsmath/amssymb/amsthm/mathtools, texlib-mathutils, graphicx, tikz/pgfplots
% (with compat=1.18 + standard library set), hyperref + canonical hypersetup.
\RequirePackage{texlib-corepkg}

% Class-specific packages
\RequirePackage{adjustbox, changepage, comment}
% NOTE: enumitem is intentionally NOT loaded at the top level — it is known to
% conflict with exam.cls's redefinition of \list (used by `questions`/`parts`).
% Quizzes that need enumitem-style lists may load it locally.
\RequirePackage{lastpage}
\RequirePackage{needspace}
\RequirePackage{cancel}
\RequirePackage{pdfpages}
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
% 4. PROBLEM-BANK ENGINE (shared with autoexam.cls)
% ==============================================================================
% texlib-problembank.sty loads problem_engine.lua and defines the shared
% problem-bank LaTeX glue (\setvar, \setrng, \pick*, \getproblem,
% \begin{problem}, \ppart, \@problem@item, \importproblem, ...).  Quizzes
% have no versioning, so the engine's set_exam_seed() is never called and
% math.random falls back to its default seed — fine for in-class quizzes
% that don't need reproducible per-version values.  See
% texlib-problembank.sty for the full API.
\RequirePackage{texlib-problembank}

% \loadbank is provided by texlib-problembank.sty (the redirect activates
% automatically; quizzes are always single-version so pbank_suppress_redirect
% never trips).

\newenvironment{problems}{%
	\directlua{pbank_first_on_page = true}%
	\let\@problems@saved@newpage\newpage
	\renewcommand{\newpage}{%
		\@problems@saved@newpage
		\directlua{pbank_first_on_page = true}%
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
% Theorem environments come from texlib-thmenv.sty (shared with autoexam.cls).
\RequirePackage{texlib-thmenv}

% ==============================================================================
% 7. ANSWER FORMATTING
% ==============================================================================
\renewcommand{\questionlabel}{\textbf{\arabic{question}.}}
\renewcommand{\partlabel}{\textbf{\alph{partno}.}}

% \encircle and \extracredit come from texlib-itemfmt.sty.
\RequirePackage{texlib-itemfmt}

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
% texlib-pagestyle.sty bundles \pagestyle{headandfoot} + first-page-footer
% rule + running head/foot rules into \SetTeXLibExamRules.  Quiz adds the
% first-page header rule on top (its title page carries a name field).
\RequirePackage{texlib-pagestyle}
% \title is auto-derived from metadata.
\AtBeginDocument{%
	\title{\LARGE \GetQuizTitle}%
	\SetTeXLibExamRules
	\firstpageheadrule
	\firstpageheader{\GetCourse}{}{Name:\ \underline{\hspace{2.5in}}}%
	\firstpagefooter{Section\ \GetCourseSection}{}{\GetInstitution}%
	\runningheader{\GetCourse}{}{Name:\ \underline{\hspace{2.5in}}}%
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
% 11. BACKWARD-COMPAT \the* ALIASES (quiz-specific only)
% ==============================================================================
% Course-metadata aliases (\theCourse, \theCourseNumber, \theCourseTitle,
% \theCourseSection, \theSeason, \theYear, \theTerm, \theSchool, ...) are
% provided by course-metadata.sty.  Quiz-specific aliases stay here.
\providecommand{\theQuizNumber}{\GetQuizNumber}
\providecommand{\theTitle}{\GetQuizTitle}

\endinput
