% syllabus.cls
% UNR Course Syllabus Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{syllabus}[2026/05/07 v2.0 UNR Course Syllabus (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[11pt]{article}

% Pre-declare xcolor options so dvipsnames stays effective regardless of
% which package pulls xcolor in first.
\PassOptionsToPackage{dvipsnames}{xcolor}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage[margin=1in]{geometry}
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{etoolbox}
\RequirePackage{xstring}
\RequirePackage{graphicx}
\RequirePackage{fancyhdr, lastpage, enumitem, makecell, qrcode}
\RequirePackage{xcolor}
\RequirePackage[colorlinks,pdfusetitle,
				urlcolor=darkblue, citecolor=darkblue, linkcolor=darkred,
				bookmarksnumbered, plainpages=false]{hyperref}

\RequirePackage{course-metadata}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}


% ==============================================================================
% 3. COLORS & LIST DEFAULTS
% ==============================================================================
\definecolor{darkblue}{rgb}{0,0,.6}
\definecolor{darkred}{rgb}{.7,0,0}
\definecolor{darkgreen}{rgb}{0,.6,0}

\setlist{noitemsep, topsep=2pt, parsep=0pt, partopsep=0pt}

% ==============================================================================
% 4. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\tl_new:N \g__syll_email_tl
\tl_new:N \g__syll_office_tl
\tl_new:N \g__syll_office_hours_tl
\tl_new:N \g__syll_organizer_tl
\tl_new:N \g__syll_class_time_tl
\tl_new:N \g__syll_class_time_alt_tl
\tl_new:N \g__syll_short_title_tl

\keys_define:nn { meta } {
	email              .tl_gset:N = \g__syll_email_tl,    % legacy alias
	instructor-email   .tl_gset:N = \g__syll_email_tl,
	office          .tl_gset:N = \g__syll_office_tl,
	office-hours    .tl_gset:N = \g__syll_office_hours_tl,
	organizer       .tl_gset:N = \g__syll_organizer_tl,
	class-time      .tl_gset:N = \g__syll_class_time_tl,
	class-time-alt  .tl_gset:N = \g__syll_class_time_alt_tl,
	short-title     .tl_gset:N = \g__syll_short_title_tl,
}

\NewExpandableDocumentCommand{\GetEmail}        {}{ \tl_use:N \g__syll_email_tl }
\NewExpandableDocumentCommand{\GetOffice}       {}{ \tl_use:N \g__syll_office_tl }
\NewExpandableDocumentCommand{\GetOfficeHours}  {}{ \tl_use:N \g__syll_office_hours_tl }
\NewExpandableDocumentCommand{\GetOrganizer}    {}{ \tl_use:N \g__syll_organizer_tl }
\NewExpandableDocumentCommand{\GetClassTime}    {}{ \tl_use:N \g__syll_class_time_tl }
\NewExpandableDocumentCommand{\GetClassTimeAlt} {}{ \tl_use:N \g__syll_class_time_alt_tl }
\NewExpandableDocumentCommand{\GetShortTitle}   {}{
	\tl_if_empty:NTF \g__syll_short_title_tl
		{ \GetCourse }
		{ \tl_use:N \g__syll_short_title_tl }
}

\NewDocumentCommand{\IfSyllSet}{ m +m +m } {
	\tl_if_empty:cTF { g__syll_#1_tl } { #3 } { #2 }
}

\ExplSyntaxOff

% Backward-compat shims for older syllabi using command-style metadata.
\newcommand{\coursetitle}[1]{\metasetup{course-title={#1}}}
\newcommand{\courseshort}[1]{\metasetup{short-title={#1}}}
\newcommand{\coursesection}[1]{\metasetup{course-section={#1}}}
\newcommand{\semester}[1]{\metasetup{term={#1}}}
\newcommand{\instructor}[1]{\metasetup{instructor={#1}}}
\newcommand{\email}[1]{\metasetup{email={#1}}}
\newcommand{\office}[1]{\metasetup{office={#1}}}
\newcommand{\officehours}[1]{\metasetup{office-hours={#1}}}
\newcommand{\classroom}[1]{\metasetup{course-room={#1}}}
\newcommand{\organizer}[1]{\metasetup{organizer={#1}}}
\NewDocumentCommand{\classtime}{ O{} m }{%
	\metasetup{class-time={#2}}%
	\IfValueT{#1}{\metasetup{class-time-alt={#1}}}%
}

% ==============================================================================
% 5. PAGE LAYOUT
% ==============================================================================
\RequirePackage{texlib-footer}   % shared footer: Course | page X of Y | Institution
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = short title  C = (none)  R = term.
\SetTeXLibHeader{\bfseries\GetShortTitle}{}{\GetTerm}
\SetTeXLibFooter
\TeXLibRuleBleed                  % symmetric rule length, matching didactic

% Title page (\maketitle uses \thispagestyle{plain}): keep the shared footer,
% suppress the header + its rule.
\fancypagestyle{plain}{%
	\fancyhf{}%
	\SetTeXLibFooter
	\renewcommand{\headrulewidth}{0pt}%
}

\renewcommand{\thefootnote}{\fnsymbol{footnote}}

% ==============================================================================
% 6. TITLE BLOCK
% ==============================================================================
\renewcommand{\maketitle}{%
	\thispagestyle{plain}%
	\begin{center}
		{\LARGE \GetCourseTitle} \\[0.2cm]
		% Section line renders only if course-section is set to a non-empty
		% value. For courses without a section number, leave course-section
		% out of coursemeta.tex (and don't call \coursesection{...}).
		\IfMetaSet{course-section}{%
			{\Large Section\ \GetCourseSection} \\[0.15cm]
		}{}%
		{\large \GetTerm}
	\end{center}
	\vspace{-0.98cm}
	\begin{center}
		\rule{6.5in}{0.4pt}
		\begin{minipage}[t]{0.8\textwidth}
		\begin{tabular}{llcccll}
			\IfMetaSet{instructor}{%
				\textbf{Instructor:} & \GetInstructor & & & &
				\IfSyllSet{organizer}{\textbf{Organizer:} & \GetOrganizer}{%
					\IfSyllSet{class_time}{\textbf{Time:} & \GetClassTime}{}}
			}{%
				\IfSyllSet{organizer}{& & & & & \textbf{Organizer:} & \GetOrganizer}{%
					\IfSyllSet{class_time}{& & & & & \textbf{Time:} & \GetClassTime}{}}
			} \\
			\IfSyllSet{email}{%
				\textbf{Email:} & \href{mailto:\GetEmail}{\GetEmail} & & & &
				\IfSyllSet{organizer}{%
					\IfSyllSet{class_time}{\textbf{Time:} & \GetClassTime}{}}{%
					\IfMetaSet{course-room}{\textbf{Classroom:} & \GetCourseRoom}{}}
			}{& & & & & &} \\
			\IfSyllSet{class_time_alt}{ & & & & & & \GetClassTimeAlt \\ }{}
			\IfSyllSet{office}{%
				\textbf{Office:} & \GetOffice & & & &
				\IfMetaSet{course-room}{\textbf{Classroom:} & \GetCourseRoom}{}
			}{%
				\IfMetaSet{course-room}{& & & & & \textbf{Classroom:} & \GetCourseRoom}{}
			}%
			% NB: the `\\` separator now lives INSIDE the office_hours
			% conditional. If office_hours isn't set the previous row is the
			% last visible row, no trailing `\\`, and the tabular doesn't end
			% with a blank row before \end{tabular}.
			\IfSyllSet{office_hours}{\\ & & & & & \textbf{Office Hours:} & \GetOfficeHours}{}
		\end{tabular}
		\end{minipage}
		\rule{6.5in}{0.4pt}
	\end{center}
	\vspace{-0.55cm}
	\setlength{\unitlength}{1in}
	\renewcommand{\arraystretch}{2}
}

% ==============================================================================
% 7. SECTION COMMAND
% ==============================================================================
\newcommand{\syllabussection}[1]{%
	\vskip.15in
	\noindent\textbf{#1.}%
}

% ==============================================================================
% 8. GRADE TABLES
% ==============================================================================
% Usage: the rows in #1 / #2 are separated by `\\ \hline`; the LAST row is
% written bare (no trailing `\\ \hline`) and these macros close the table.
% The closing `\\ \hline` below supplies the last row's terminator plus the
% bottom rule -- writing it as bare `\hline` would land mid-row and trigger
% "! Misplaced \noalign." A last row that *does* end with `\\` still compiles
% (it just adds a blank trailing row), so the macros tolerate both styles.
\newcommand{\gradecategories}[1]{%
	\begin{tabular}{|c|c|}
		\hline
		Category & Total Grade \\
		\hline\hline
		#1
		\\ \hline
	\end{tabular}%
}

\newcommand{\gradescale}[1]{%
	\begin{tabular}{|c|c|}
		\hline
		Grade Letter & Grade Range (\%) \\
		\hline\hline
		#1
		\\ \hline
	\end{tabular}%
}

\newcommand{\gradetables}[2]{%
	\begin{center}
		\gradecategories{#1}
		\hskip 0.5in
		\gradescale{#2}
	\end{center}
}

\endinput
