% quiz.cls
% UNR In-Class Quiz Class — TeXLib unified style (subclass of exam.cls)
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{quiz}[2026/05/07 v1.0 UNR In-Class Quizzes (TeXLib)]

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{exam}}
\ProcessOptions\relax
\LoadClass[11pt]{exam}

% Shared assessment setup (texlib-corepkg, texlib-build, course-metadata, the
% common aux packages, and the unified problem/part labels). Shared with autoexam.
\RequirePackage{texlib-assessment}

% quiz-only packages. enumitem is intentionally absent: it conflicts with
% exam.cls's \list redefinition (used by questions/parts).
\RequirePackage{adjustbox}
\RequirePackage{tocloft}

% Provided by texlib-build (loaded via texlib-assessment): \ifsolutions, \ifkey,
% \ifrubric, \ifdraft, \ifstudent, \ifinstructor and the matching CLI toggles.

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
% Inline instruction text (set via \meta{quiz-instructions={...}}); empty by
% default — the default wording now lives in quiz-instructions.tex so it can be
% a SyncTeX inverse-search target (see \maketitle below).
\NewExpandableDocumentCommand{\GetQuizInstructions}{}{
	\tl_use:N \g__quiz_instructions_tl
}
\NewExpandableDocumentCommand{\GetQuizInstructionsFile}{}{
	\tl_use:N \g__quiz_instructions_file_tl
}
% \IfQuizInstructionsFile{true}{false} — branch on whether a file was set.
\NewDocumentCommand{\IfQuizInstructionsFile}{ +m +m }{
	\tl_if_empty:NTF \g__quiz_instructions_file_tl { #2 } { #1 }
}
% \IfQuizInstructionsInline{true}{false} — branch on whether inline text was set.
\NewDocumentCommand{\IfQuizInstructionsInline}{ +m +m }{
	\tl_if_empty:NTF \g__quiz_instructions_tl { #2 } { #1 }
}

\ExplSyntaxOff

% Default boxed instructions are \input from a real file so SyncTeX inverse
% search (double-click in the PDF) jumps to the instruction source, mirroring
% autoexam's autoexam-instructions.tex.  Used only when the document sets
% neither quiz-instructions-file nor an inline quiz-instructions.
\newcommand{\@quiz@instructions@file}{quiz-instructions}

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

% Theorem environments come from texlib-thmenv.sty (shared with autoexam.cls).
\RequirePackage{texlib-thmenv}

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
				% Inline text typesets directly; the default wording is \input
				% from quiz-instructions.tex so double-clicking it in the PDF
				% lands on that source (inverse search).
				\IfQuizInstructionsInline
					{\GetQuizInstructions}%
					{\input{\@quiz@instructions@file}}%
			}}}%
		\end{center}
	}%
}

% Course-metadata aliases (\theCourse, \theCourseNumber, \theCourseTitle,
% \theCourseSection, \theSeason, \theYear, \theTerm, \theSchool, ...) are
% provided by course-metadata.sty.  Quiz-specific aliases stay here.
\providecommand{\theQuizNumber}{\GetQuizNumber}
\providecommand{\theTitle}{\GetQuizTitle}

\endinput
