% syllabus.cls
% UNR Course Syllabus Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{syllabus}[2026/05/07 v2.0 UNR Course Syllabus (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[office={NLLC 146F}, office-hours={MWF 2-3pm}]{syllabus}
% Any option containing "=" is a metadata key=value pair; every other option
% (11pt, twoside, ...) is forwarded to article. Metadata is applied at the end
% of section 4 (after coursemeta.tex loads, so document options win) by reading
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

% Instructor-contact and scheduling fields — email / instructor-email, office,
% office-hours, organizer, class-time, class-time-alt, short-title / syllabus-title
% — are course-wide keys defined in course-metadata.sty (v8.2+). A course may set
% them once in coursemeta.tex as defaults; a document's class options still
% override (this class re-applies its option list after coursemeta loads). We read
% the shared \GetEmail / \GetOffice / ... getters and the \g__meta_short-title_tl
% store via the composite accessors below.

% Composite accessors for the default info table. Each is fully expandable and
% yields nothing when its underlying field(s) are unset, so the info-table
% emptiness filter (expansion + \tl_if_blank) drops the entry and reflows.
\NewExpandableDocumentCommand{\GetInstructorOrOrganizer}{}{
	\tl_if_empty:cTF { g__meta_instructor_tl }
		{ \GetOrganizer }
		{ \GetInstructor }
}
% Class meeting time: an explicit class-time wins (with an optional alternate
% appended); otherwise fall back to the coursemeta lecture pattern
% (lecture-days + lecture-times) so a course need not repeat it here. Expands to
% nothing when none are set, and the info-table filter then drops the row.
\NewExpandableDocumentCommand{\GetClassTimeFull}{}{
	\tl_if_empty:cTF { g__meta_class-time_tl }
		{
			\tl_if_empty:cTF { g__meta_lecture-days_tl }
				{ \GetLectureTimes }
				{ \GetLectureDays
				  \tl_if_empty:cF { g__meta_lecture-times_tl } { ~\GetLectureTimes } }
		}
		{
			\GetClassTime
			\tl_if_empty:cF { g__meta_class-time-alt_tl } { ~/~\GetClassTimeAlt }
		}
}
\NewExpandableDocumentCommand{\GetEmailLinked}{}{
	\tl_if_empty:cF { g__meta_email_tl } { \href{mailto:\GetEmail}{\GetEmail} }
}

\NewExpandableDocumentCommand{\GetShortTitle}   {}{
	\tl_if_empty:cTF { g__meta_short-title_tl }
		{ \GetCourse }
		{ \tl_use:c { g__meta_short-title_tl } }
}
% \GetSyllabusTitle -- canonical \Get<class>Title name (mirrors \GetPsetTitle,
% \GetUnitTitle, ...); \GetShortTitle is kept as the original alias.
\NewExpandableDocumentCommand{\GetSyllabusTitle}{}{
	\tl_if_empty:cTF { g__meta_short-title_tl }
		{ \GetCourse }
		{ \tl_use:c { g__meta_short-title_tl } }
}

\NewDocumentCommand{\IfSyllSet}{ m +m +m } {
	\tl_if_empty:cTF { g__syll_#1_tl } { #3 } { #2 }
}

\ExplSyntaxOff

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
% 5. PAGE LAYOUT
% ==============================================================================
\RequirePackage{texlib-footer}   % shared footer: Course | page X of Y | Institution
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = syllabus title  C = (none)  R = term + section.
\SetTeXLibHeader{\bfseries\GetSyllabusTitle}{}{\GetTermSection}
\SetTeXLibFooter                  % L = \GetCourse (shared default)
% Rule bleed comes from texlib-sectionhang's [LR] offset (loaded at the end of
% this class), so \TeXLibRuleBleed must NOT also be called.

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
% The course-info table under the title is fully customizable via
% \setsyllabusinfo. An entry whose value expands to empty is dropped and the
% remaining entries reflow into the grid; if every value is empty the whole
% framed block -- rules included -- is suppressed.
\ExplSyntaxOn

\seq_new:N \g__syll_info_seq
\seq_new:N \g__syll_info_kept_seq
\int_new:N \g__syll_info_cols_int

\keys_define:nn { syll / info } {
	columns .int_gset:N = \g__syll_info_cols_int,
}

% \setsyllabusinfo[columns=N]{ \syllabusentry{Label}{Value} ... } redefines the
% info table. \syllabusentry is live only inside this argument; labels and values
% are stored unexpanded and the values are evaluated at \maketitle time. Each
% call resets columns to the default of 2 unless [columns=N] overrides it.
\NewDocumentCommand{\setsyllabusinfo}{ O{} +m }{
	\seq_gclear:N \g__syll_info_seq
	\int_gset:Nn \g__syll_info_cols_int { 2 }
	\keys_set:nn { syll / info } { #1 }
	\group_begin:
		\cs_set:Npn \syllabusentry ##1 ##2 {
			\seq_gput_right:Nn \g__syll_info_seq { { ##1 } { ##2 } }
		}
		#2
	\group_end:
}

% Keep only entries whose value is non-empty.  The test expands the value with
% \protected@edef, not a raw e-expansion: that fully expands the (expandable)
% \Get... accessors -- so an unset field reads as blank -- while leaving robust
% commands like \href intact instead of executing them mid-test.
\cs_new_eq:Nc \__syll_protected_edef:N { protected@edef }
\tl_new:N \l__syll_probe_tl
\cs_new_protected:Npn \__syll_filter_info: {
	\seq_gclear:N \g__syll_info_kept_seq
	\seq_map_inline:Nn \g__syll_info_seq { \__syll_filter_one:nn ##1 }
}
\cs_new_protected:Npn \__syll_filter_one:nn #1 #2 {
	\__syll_protected_edef:N \l__syll_probe_tl { #2 }
	\tl_if_blank:VF \l__syll_probe_tl
		{ \seq_gput_right:Nn \g__syll_info_kept_seq { { #1 } { #2 } } }
}

\tl_new:N  \l__syll_pre_tl
\tl_new:N  \l__syll_rows_tl
\tl_new:N  \l__syll_table_tl
\int_new:N \l__syll_cols_int
\int_new:N \l__syll_n_int

\cs_new:Npn \__syll_cell:nn #1 #2 { \textbf{#1:} & #2 }

% Pad a partial final row out to a full set of column pairs (two empty tabular
% columns per missing entry) so the alignment never ends ragged.
\cs_new_protected:Npn \__syll_pad_row:n #1 {
	\int_set:Nn \l_tmpa_int { \int_mod:nn { #1 } { \l__syll_cols_int } }
	\int_step_inline:nn { 2 * ( \l__syll_cols_int - \l_tmpa_int ) }
		{ \tl_put_right:Nn \l__syll_rows_tl { & } }
}

% Assemble \l__syll_table_tl: \begin{tabular}{<spec>} <rows> \end{tabular} for the
% kept entries laid out in \g__syll_info_cols_int columns of label/value pairs.
\cs_new_protected:Npn \__syll_build_table: {
	\int_set:Nn \l__syll_cols_int { \g__syll_info_cols_int }
	\int_compare:nNnT { \l__syll_cols_int } < { 1 }
		{ \int_set:Nn \l__syll_cols_int { 1 } }
	\int_set:Nn \l__syll_n_int { \seq_count:N \g__syll_info_kept_seq }
	% column spec: @{}ll@{\hspace{3em}}ll...@{}
	\tl_clear:N \l__syll_pre_tl
	\tl_put_right:Nn \l__syll_pre_tl { @{} }
	\int_step_inline:nn { \l__syll_cols_int } {
		\int_compare:nNnT { ##1 } > { 1 }
			{ \tl_put_right:Nn \l__syll_pre_tl { @{\hspace{3em}} } }
		\tl_put_right:Nn \l__syll_pre_tl { ll }
	}
	\tl_put_right:Nn \l__syll_pre_tl { @{} }
	% rows: a \\ closes each full row; a partial final row is padded first
	\tl_clear:N \l__syll_rows_tl
	\seq_map_indexed_inline:Nn \g__syll_info_kept_seq {
		\tl_put_right:Nn \l__syll_rows_tl { \__syll_cell:nn ##2 }
		\int_compare:nNnTF { \int_mod:nn { ##1 } { \l__syll_cols_int } } = { 0 }
			{ \tl_put_right:Nn \l__syll_rows_tl { \\ } }
			{
				\int_compare:nNnTF { ##1 } = { \l__syll_n_int }
					{ \__syll_pad_row:n { ##1 }
					  \tl_put_right:Nn \l__syll_rows_tl { \\ } }
					{ \tl_put_right:Nn \l__syll_rows_tl { & } }
			}
	}
	\tl_set:Ne \l__syll_table_tl {
		\exp_not:N \begin { tabular } { \exp_not:V \l__syll_pre_tl }
			\exp_not:V \l__syll_rows_tl
		\exp_not:N \end { tabular }
	}
}

% Bridges to the expl3 logic above, with all-letter names so the typesetting
% wrapper (\syllabusinfotable) can stay in normal catcodes -- markup like
% \begin{center} misbehaves if tokenized under \ExplSyntaxOn (ignored spaces).
\NewDocumentCommand{\syllInfoCompute}{}{
	\__syll_filter_info:
	\seq_if_empty:NF \g__syll_info_kept_seq { \__syll_build_table: }
}
\NewDocumentCommand{\syllInfoIfPresent}{ +m }{
	\seq_if_empty:NF \g__syll_info_kept_seq { #1 }
}
\NewExpandableDocumentCommand{\syllInfoTable}{}{ \tl_use:N \l__syll_table_tl }

\ExplSyntaxOff

% Emit the framed info block, or nothing at all if no entry has a value. The
% inter-element newlines (spaces) below are load-bearing: inside center they let
% the rules and minipage stack vertically. Ending those lines with % would glue
% all three onto one overfull line.
\newcommand{\syllabusinfotable}{%
	\syllInfoCompute
	\syllInfoIfPresent{%
		\vspace{-0.98cm}
		\begin{center}
			\rule{6.5in}{0.4pt}
			\begin{minipage}[t]{0.8\textwidth}
			\renewcommand{\arraystretch}{1.0}%
			\syllInfoTable
			\end{minipage}
			\rule{6.5in}{0.4pt}
		\end{center}
		\vspace{-0.55cm}
	}%
}

% Built-in default: reproduces the historical 3x2 grid (Instructor/Time,
% Email/Classroom, Office/Office Hours). Instructor falls back to Organizer
% (relabelled) when unset; an alternate class time is appended to Time. Override
% by calling \setsyllabusinfo in the preamble.
\setsyllabusinfo{
	\syllabusentry{\IfMetaSet{instructor}{Instructor}{Organizer}}{\GetInstructorOrOrganizer}
	\syllabusentry{Time}{\GetClassTimeFull}
	\syllabusentry{Email}{\GetEmailLinked}
	\syllabusentry{Classroom}{\GetCourseRoom}
	\syllabusentry{Office}{\GetOffice}
	\syllabusentry{Office Hours}{\GetOfficeHours}
}

\renewcommand{\maketitle}{%
	\thispagestyle{plain}%
	\begin{center}
		{\LARGE \GetCourse} \\[0.2cm]
		% Section line renders only if course-section is set to a non-empty
		% value. For courses without a section number, leave course-section
		% out of coursemeta.tex (and don't call \coursesection{...}).
		\IfMetaSet{course-section}{%
			{\Large Section\ \GetCourseSection} \\[0.15cm]
		}{}%
		{\large \GetTerm}
	\end{center}
	\syllabusinfotable
	\setlength{\unitlength}{1in}
	\renewcommand{\arraystretch}{2}
}

% ==============================================================================
% 7. SECTION COMMAND
% ==============================================================================
% The bold run-in title hangs onto the shared structural-hang line
% (\texlibsectionhang, from texlib-sectionhang loaded at the end of this
% class); the syllabus body text that follows stays at the normal margin.
\newcommand{\syllabussection}[1]{%
	\vskip.15in
	\noindent\hspace*{-\texlibsectionhang}\textbf{#1.}%
}

% Section shortcuts: common syllabus headings as one-word commands. Each emits
% \syllabussection{<standard title>}, so body prose follows exactly as with
% \syllabussection; an optional argument overrides the title, e.g.
% \academicintegrity[Academic Honesty]. \texlib@syllsec{\cmd}{Title} mints one.
\newcommand{\texlib@syllsec}[2]{%
	\NewDocumentCommand{#1}{o}{\syllabussection{\IfValueTF{##1}{##1}{#2}}}%
}
\texlib@syllsec{\coursedescription} {Course Description}
\texlib@syllsec{\prerequisites}     {Prerequisites}
\texlib@syllsec{\requiredmaterials} {Required Materials}
\texlib@syllsec{\learningoutcomes}  {Learning Outcomes}
\texlib@syllsec{\grading}           {Grading}
\texlib@syllsec{\courseschedule}    {Course Schedule}
\texlib@syllsec{\examschedule}      {Exam Schedule}
\texlib@syllsec{\officehours}       {Office Hours}
\texlib@syllsec{\communication}     {Communication}
\texlib@syllsec{\attendancepolicy}  {Attendance Policy}
\texlib@syllsec{\latework}          {Late and Make-up Work}
\texlib@syllsec{\academicintegrity} {Academic Integrity}
\texlib@syllsec{\accommodations}    {Accommodations}
\texlib@syllsec{\academicsupport}   {Academic Support}
\texlib@syllsec{\wellness}          {Student Wellness}
\texlib@syllsec{\inclusivity}       {Inclusivity}
\texlib@syllsec{\technology}        {Technology Requirements}
\texlib@syllsec{\titleix}           {Title IX}
\let\communications\communication   % plural alias for \communication

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

% ------------------------------------------------------------------------------
% \examdatetable -- exam-date table driven by coursemeta
% ------------------------------------------------------------------------------
% Builds a two-column "Exam | Date" table from the coursemeta exam<N>-date keys
% (exam1-date .. exam5-date) plus final-date. Only assessments whose date is set
% appear; if none are set, the command produces nothing. Single-sources exam
% dates with autoexam (which reads the same exam<N>-date keys), so a reschedule
% edits one place.
\ExplSyntaxOn
\tl_new:N \l__syll_examrows_tl
\NewDocumentCommand{\examdatetable}{}{
	\tl_clear:N \l__syll_examrows_tl
	\clist_map_inline:nn { 1, 2, 3, 4, 5 } {
		\tl_if_exist:cT { g__meta_exam ##1 -date_tl } {
			\tl_if_empty:cF { g__meta_exam ##1 -date_tl } {
				\tl_put_right:Nn \l__syll_examrows_tl
					{ Exam~##1 & \tl_use:c { g__meta_exam ##1 -date_tl } \\ \hline }
			}
		}
	}
	% final-date is stored as M-D for the schedule; render it human-readable so it
	% matches the free-form exam<N>-date rows above (e.g. "Dec 15, 2026").
	\tl_if_empty:cF { g__meta_final-date_tl } {
		\tl_put_right:Nn \l__syll_examrows_tl
			{ Final~Exam & \MetaHumanMonthDay{\GetFinalDate} \\ \hline }
	}
	\tl_if_empty:NF \l__syll_examrows_tl {
		\begin { tabular } { | c | c | }
			\hline
			Exam & Date \\
			\hline \hline
			\tl_use:N \l__syll_examrows_tl
		\end { tabular }
	}
}
\ExplSyntaxOff

% ==============================================================================
% Structural hang: \syllabussection titles (via the \hspace above), any raw
% \section-family headings, and the running header/footer all hang onto one
% outer left edge. Loaded LAST so its redefinitions land on top of the article
% defaults.
% ==============================================================================
\RequirePackage{texlib-sectionhang}

\endinput
