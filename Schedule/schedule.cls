% schedule.cls
% UNR Course Schedule Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{schedule}[2026/08/25 v0.7.3 UNR Course Schedule (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[landscape=true, lecture-caps={1.0,1.0}, quiz-days=T]{schedule}
% Any option containing "=" is a metadata key=value pair; every other option is
% forwarded to article. Metadata is applied at the end of section 5 (after
% coursemeta.tex loads, so document options win) by reading
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
\LoadClass{article}

% A class-option value containing a comma (e.g. lecture-caps={1.0, 1.0}) is split
% by the kernel's option parser into a stray fragment with no "=", which would be
% reported as an "unused global option". The real values are consumed from
% \@raw@classoptionslist below, so discard those spurious leftovers.
\AtEndOfClass{\global\let\@unusedoptionlist\@empty}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage{geometry}
\RequirePackage{fontspec}
\RequirePackage{xcolor}
% The calendar grid is a tabularray longtblr: it page-breaks like longtable but
% colors cells natively (\SetCell{bg=...}), avoiding the longtable+colortbl
% empty-\special{} artifact that made LuaLaTeX log "Non-PDF special ignored!".
\RequirePackage{tabularray}
% Suppress longtblr's cross-page "(Continued)" head and "Continued on next page"
% foot: the grid reads as one continuous calendar (the header row already
% repeats via rowhead), and dropping them reclaims the vertical space they'd
% consume at each break — which keeps a long schedule paginating as tightly as
% the old xltabular did. The contfoot's `empty` template drops the foot outright;
% the conthead's `empty` template is a no-op in this tabularray release, so we
% blank its text macro instead (\AtBeginDocument, after tabularray sets it).
\SetTblrTemplate{contfoot}{empty}
\AtBeginDocument{\def\tblrcontheadname{}}
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{etoolbox}
\RequirePackage{xstring}
\RequirePackage{luacode}
\RequirePackage{lastpage}
\RequirePackage{fancyhdr}

\RequirePackage{course-metadata}

% hyperref (hidelinks: no coloured boxes, this is a print-first class) so the PDF
% carries a document title. Without it the central \TeXLibDeclareDocTitle hook in
% course-metadata.sty has no \hypersetup to feed -- a blank viewer tab normally,
% and PDF/UA clause 8.11.1 in an accessible build. (Schedule still fails other
% clauses from its calendar structure, so this does not make it conform on its
% own, but it removes 8.11.1 and titles the normal PDF.)
\RequirePackage[hidelinks]{hyperref}

% PDF document title (PDF/UA clause 8.11.1) -- see course-metadata.sty.
\TeXLibDeclareDocTitle{\GetCourse\space\GetTerm\space Tentative Schedule}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}

% Publishable: the builder clones the built PDF to the coded
% "<SUBJECT> <number>.<section>_<term>_<LastName>_Schedule.pdf" and to
% "Tentative Schedule.pdf", and drops a "<course> <term> Schedule" desktop
% shortcut. See the publish sidecar in course-metadata.sty. The generic name
% matches the document title declared above, and is one of the two names
% package_for_lms.py bundles.
%
% The [Schedule] coded-suffix is required, not decorative: the unsuffixed coded
% name is reserved for the syllabus, which must match the Math & Stat Office
% submission convention verbatim. Without it both classes in a course clone to
% one filename and the later build wins.
\TeXLibDeclarePublishable[Schedule]{schedule}{Tentative Schedule}{Schedule}


% ==============================================================================
% 3. PAGE LAYOUT
% ==============================================================================
\AtBeginDocument{
	\pagestyle{fancy}
	\fancyhf{}
	\renewcommand{\headrulewidth}{0pt}
	\setlength{\headwidth}{\textwidth}
	\cfoot{\thepage\ of \pageref{LastPage}}
}

% ==============================================================================
% 4. LUA BRIDGE
% ==============================================================================
% LuaLaTeX only — the calendar grid is built by a Lua engine. Under a non-Lua
% engine, fail with a clear instruction instead of a cryptic \directlua error.
\ifdefined\directlua
\directlua{
	local function load_safe(name)
		local cls_path = kpse.find_file("schedule.cls")
		local sep = string.char(92)
		local base_dir = cls_path and cls_path:match("(.*[/" .. sep .. "])") or ""
		local path = kpse.find_file(name, "lua")
		if not path then
			path = base_dir .. name
			if not lfs.attributes(path) then
				path = base_dir .. "../" .. name
				if not lfs.attributes(path) then path = name end
			end
		end
		dofile(path)
	end
	load_safe("date.lua")
	load_safe("calendar.lua")
	load_safe("schedule.lua")
}
\else
	\ClassError{schedule}{The schedule class requires LuaLaTeX}{%
		schedule builds its calendar through a Lua engine (\string\directlua),
		which only exists under LuaLaTeX. Compile this document with lualatex.}%
\fi

% ==============================================================================
% 5. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\clist_new:N \g__sched_lecture_caps_clist
\clist_new:N \g__sched_quiz_days_clist
\clist_new:N \g__sched_recitation_days_clist
\clist_new:N \g__sched_exam_days_clist
\bool_new:N  \g__sched_landscape_bool
\bool_new:N  \g__sched_monthpages_bool
\bool_new:N  \g__sched_boxgrid_bool

\keys_define:nn { meta } {
	lecture-caps     .clist_gset:N = \g__sched_lecture_caps_clist,
	quiz-days        .clist_gset:N = \g__sched_quiz_days_clist,
	recitation-days  .clist_gset:N = \g__sched_recitation_days_clist,

	% exam-days = F  ->  \exam places on the next day in this set instead of the
	% next lecture day. For a course whose exams sit in a recitation or lab
	% section rather than in lecture: topics still flow across the lecture
	% columns, but an exam jumps to the next matching day. Unset (the default)
	% keeps the historic behaviour of placing exams on lecture days.
	exam-days        .clist_gset:N = \g__sched_exam_days_clist,

	% month-pages = true  ->  one table per calendar month, each on its own
	% page, with month-boundary weeks repeated so every month shows full weeks.
	% Default (false / key omitted) keeps the term as one continuous table.
	month-pages   .bool_gset:N = \g__sched_monthpages_bool,

	% box-grid = true  ->  render the calendar as stacked box rows (\schedrow /
	% \schedcell) instead of an xltabular.  Both look the same, but the box grid
	% ships each cell's content eagerly during normal box construction, so
	% SyncTeX attributes every cell to its own grid-file line — which is what
	% makes double-click inverse search land on the directive that produced the
	% cell (see the SyncTeX writeup in schedule.lua's render_grid).  xltabular
	% defers shipout to its output routine, collapsing every cell's attribution
	% to one line, so inverse search cannot work per-cell under it.  Default
	% (false) keeps the historical xltabular rendering.
	box-grid      .bool_gset:N = \g__sched_boxgrid_bool,

	landscape     .code:n = {
		\str_if_eq:nnTF { #1 } { true }
			{
				\bool_gset_true:N \g__sched_landscape_bool
				\geometry{ landscape, margin=0.5in, includefoot }
			}
			{
				\bool_gset_false:N \g__sched_landscape_bool
				\geometry{ portrait,  margin=0.5in, includefoot }
			}
	},

	portrait      .code:n = {
		\str_if_eq:nnT { #1 } { true } {
			\bool_gset_false:N \g__sched_landscape_bool
			\geometry{ portrait,  margin=0.5in, includefoot }
		}
	},
}

\NewExpandableDocumentCommand{\GetLectureCaps}{}{
	\clist_use:Nn \g__sched_lecture_caps_clist {,}
}
\NewExpandableDocumentCommand{\GetQuizDays}{}{
	\clist_use:Nn \g__sched_quiz_days_clist {,}
}
\NewExpandableDocumentCommand{\GetRecitationDays}{}{
	\clist_use:Nn \g__sched_recitation_days_clist {,}
}
\NewExpandableDocumentCommand{\GetExamDays}{}{
	\clist_use:Nn \g__sched_exam_days_clist {,}
}

% Expands to the Lua literal `true`/`false` for the month-pages flag, so the
% \end{schedule} hook can pass it straight into render_grid(...).
\NewExpandableDocumentCommand{\GetMonthPagesFlag}{}{
	\bool_if:NTF \g__sched_monthpages_bool { true } { false }
}

% Same, for the box-grid flag — second argument to render_grid(...).
\NewExpandableDocumentCommand{\GetBoxGridFlag}{}{
	\bool_if:NTF \g__sched_boxgrid_bool { true } { false }
}

% Apply document metadata from the class option list now that the keys above and
% coursemeta.tex are loaded (so document options override coursemeta defaults).
\MetaApplyClassOptions

% ACCESSIBLE: force the box-grid renderer on. The default xltabular (tabularray)
% calendar cannot be tagged -- tabularray rebuilds the galley below the structure
% layer, so its cells produce a deeply mis-nested tree (hundreds of P-P/P-Part/
% StructTreeRoot-* violations). The box grid draws the same calendar from stacked
% \hbox rows that tag cleanly (paired with the \tagstructbegin{Sect} wrapper in
% the schedule environment). This overrides box-grid=false; a normal build keeps
% whatever the user chose. Tradeoff: the box grid shows the day-name header only
% on the first page of a continuous grid (month-pages repeats it per month).
\cs_if_exist:NT \TeXLibAccessibleMode
	{ \bool_gset_true:N \g__sched_boxgrid_bool }

\ExplSyntaxOff

% ==============================================================================
% 6. BOX-GRID RENDERER (opt-in: box-grid = true)
% ==============================================================================
% An alternative to the xltabular calendar that draws the SAME grid out of
% stacked box "rows" instead of a table.  Motivation is SyncTeX inverse search:
% xltabular (via longtable) defers real box shipout to its output routine, by
% which point every cell's raw SyncTeX line has collapsed to the grid file's
% last line, so double-clicking any calendar cell in the PDF cannot resolve to
% the directive that produced it.  A box grid ships each cell during ordinary
% box construction, so SyncTeX records each cell against its own grid-file line
% and the .schedmap rewrite (see schedule.lua) can repoint clicks at the user's
% source.  Trade-off: this hand-rolls what xltabular gives for free; the Lua
% engine drives it (schedule.lua's render_grid box-grid branch), so the class
% only supplies the drawing macros.  Page-break placement works (rows are atomic
% \hboxes, so TeX breaks cleanly between them and never splits a row), but the
% day-name header is emitted once at the top of each page-GROUP, not once per
% physical page: a single continuous grid (month-pages off) that overflows onto
% a second page shows no header on the continuation.  In month-pages mode each
% month is its own group with its own header, so a multi-page schedule in that
% mode gets a header on every page — the recommended pairing.
%
% Layout model: each row is ONE \hbox placed in the main vertical list with
% \offinterlineskip active, so fixed-height framed cells butt with no gap and a
% row is atomic across page breaks (TeX never breaks inside an \hbox).  The
% components must NOT meet that \hbox on their raw minipage baselines: a
% [t][h][*] minipage's baseline sits at its first line, so a cell whose date is
% \fbox'd (month starts) rode ~\fboxsep higher than its neighbours, the
% [c]-centred week label rode lower than both, and every row's bounding box
% absorbed the spread as dead space between rows.  \sched@topalign therefore
% re-baselines every framed component to one uniform profile — height = the
% full frame, depth = 0 — so content differences cannot move a frame: tops
% align, bottoms align, and a row's bounding box is exactly its frames.
% Adjacent cells kern back by \fboxrule so shared vertical borders draw once;
% the Lua emitter kerns the same amount vertically between rows.
\newlength{\schedcellw}
\newlength{\schedlabelw}
\newlength{\schedrowh}
\newlength{\schedpad}
\newlength{\schedheadh}
\newlength{\scheddividergap}
\setlength{\schedlabelw}{3.7em}   % WEEK column width (fits the bold WEEK header
                                  % word, which sizes the xltabular `c` column too)
\setlength{\schedrowh}{4.75em}    % fixed cell/row height (matches the historical
                                  % xltabular week-label \parbox[t][4.75em] size)
\setlength{\schedpad}{5pt}        % inner horizontal cell padding (~\tabcolsep)
\setlength{\schedheadh}{1.9em}    % header-row inner height (framed total tracks
                                  % the xltabular header's 2.65em strut)
\setlength{\scheddividergap}{1.5pt}% white gap inside the WEEK||days double rule

% \sched@topalign{inner-height}{framed material}: the re-baseliner described
% above.  The frame's total height is fixed by construction (#1 + fboxsep/rule
% padding), so raising the box by (total - \ht) pins its TOP at that total
% above the baseline and its bottom exactly on it: ht = total, dp = 0 for
% every component, regardless of what the first line inside happens to be.
\newsavebox{\sched@box}
\newcommand{\sched@topalign}[2]{%
	\sbox{\sched@box}{#2}%
	\raisebox{\dimexpr#1+2\fboxsep+2\fboxrule-\ht\sched@box\relax}{\usebox{\sched@box}}}

% \SchedSetCols{n}: compute \schedcellw for n equal day columns.  Each framed
% component is 2(\fboxsep+\fboxrule) wider than its minipage, the divider gap
% adds \scheddividergap, and the n-1 inter-cell kerns give back \fboxrule each;
% collecting terms leaves the constants below.  Called by render_grid before
% emitting rows (the active-column count is only known to the Lua engine).
\newcommand{\SchedSetCols}[1]{%
	\setlength{\schedcellw}{\dimexpr(\textwidth-\schedlabelw-\scheddividergap
		-2\fboxsep-3\fboxrule
		-#1\dimexpr2\fboxsep+\fboxrule\relax)/#1\relax}%
}

% \schedcell{color}{content}: a fixed-height, full-bleed-colored, framed day
% cell.  content is set \footnotesize in a top-aligned padded minipage.
\newcommand{\schedcell}[2]{%
	\sched@topalign{\schedrowh}{\fcolorbox{black}{#1}{\hspace{\schedpad}%
		\begin{minipage}[t][\schedrowh][t]{\dimexpr\schedcellw-2\schedpad\relax}%
			\footnotesize #2%
		\end{minipage}%
		\hspace{\schedpad}}}}

% \schedlabel{n}: the WEEK-column cell (week number, vertically centered).
\newcommand{\schedlabel}[1]{%
	\sched@topalign{\schedrowh}{\fcolorbox{black}{white}{%
		\begin{minipage}[t][\schedrowh][c]{\schedlabelw}\centering\textbf{#1}\end{minipage}}}}

% \scheddivider: the doubled vertical rule between the WEEK column and the days
% (mirrors xltabular's `c ||`).  The two rules are the label's right border and
% the first day cell's left border with \scheddividergap of white between — no
% box of its own (the old framed-strut divider carried \fboxsep of padding and
% read as a fat white channel).  The emitter follows it with \kern-\fboxrule
% (the standard border-overlap kern), compensated here.
\newcommand{\scheddivider}{\kern\dimexpr\scheddividergap+\fboxrule\relax}

% \schedheadcell{width}{text}: a short (single-line) header cell.
\newcommand{\schedheadcell}[2]{%
	\sched@topalign{\schedheadh}{\fcolorbox{black}{white}{%
		\begin{minipage}[t][\schedheadh][c]{#1}\centering\textbf{#2}\end{minipage}}}}

% ==============================================================================
% 7. SCHEDULE ENVIRONMENT
% ==============================================================================
% \maketitle / \scheduletitle render the standard banner. Call \maketitle
% (or \scheduletitle) explicitly in the document body when you want the
% banner; the schedule environment no longer emits it on its own, so a
% document can run the grid title-less (e.g. when the title lives elsewhere).
\newcommand{\scheduletitle}{%
	\noindent
	{\LARGE \GetCourseSubject\ \GetCourseNumber\ \GetCourseTitle\ Tentative\ Schedule
		\hfill \GetSeason \space \GetYear}\par
	% Section line is rendered only if course-section is set to a non-empty value
	% in coursemeta.tex. To omit it for a course without a section number, either
	% leave the key out of coursemeta.tex entirely or set it to empty
	% (course-section = ,).
	\IfMetaSet{course-section}{%
		\vspace{0.5em}%
		\noindent{\Large Section\ \GetCourseSection}\par
	}{}%
	\vspace{1em}
}
\renewcommand{\maketitle}{\scheduletitle}

\NewDocumentEnvironment{schedule}{ }
{
	\directlua{
		init_scheduler(
			"\GetStartDate",
			"\GetEndDate",
			"\GetLectureDays",
			"\GetRecitationDays",
			"\GetQuizDays",
			"\GetLectureCaps",
			"\GetYear",
			"\GetExamDays"
		)
	}

	% ----- Schedule directives -----
	\RenewDocumentCommand{\section}{ O{1.0} m }{
		\directlua{ L_section(nil, "\luaescapestring{##2}", "\luaescapestring{##1}") }
	}
	\NewDocumentCommand{\topic}{ O{1.0} m }{
		\directlua{ L_topic(nil, "\luaescapestring{##2}", "\luaescapestring{##1}") }
	}
	\NewDocumentCommand{\holiday}{ m o m }{
		\directlua{ L_holiday("\luaescapestring{##1}",
								"\IfValueT{##2}{##2}",
								"\luaescapestring{##3}") }
	}
	\NewDocumentCommand{\noquiz}{ m }{
		\directlua{ L_skip_quiz("\luaescapestring{##1}") }
	}
	\NewDocumentCommand{\quiz}{ O{} }{
		\directlua{ L_quiz("\luaescapestring{##1}") }
	}
	\NewDocumentCommand{\note}{ o m }{
		\directlua{ L_meta("\luaescapestring{##2}",
							"\IfValueT{##1}{##1}",
							"bottom", "") }
	}

	% Convenience aliases
	\NewDocumentCommand{\syllabus}{ }{
		\directlua{ L_topic(nil, "Syllabus", 1.0) }
	}
	\NewDocumentCommand{\examreview}{ O{1.0} }{
		\directlua{ L_exam_review("\luaescapestring{##1}") }
	}
	% \exam  | \exam[noquiz]  | \exam[length=1.5, noquiz]
	\NewDocumentCommand{\exam}{ O{} }{
		\directlua{ L_exam("\luaescapestring{##1}") }
	}
	\NewDocumentCommand{\finalreview}{ O{1.0} }{
		\directlua{ L_topic(nil, "Final~Review", "\luaescapestring{##1}") }
	}
	% \finalsweek[Start-Date][Duration]
	\NewDocumentCommand{\finalsweek}{ O{} O{5} }{
		\directlua{
			L_finals_week(
				"\luaescapestring{##1}",
				"\luaescapestring{\GetFinalDate}",
				"\luaescapestring{\GetFinalTime}",
				"\luaescapestring{##2}"
			)
		}
	}
	\NewDocumentCommand{\winterbreak}{ O{Winter~Break} }{
		\directlua{ L_winterbreak_auto("\luaescapestring{##1}") }
	}
	\NewDocumentCommand{\debugdate}{ }{ \directlua{ L_debug_cursor() } }
}
{
	% ACCESSIBLE: wrap the grid in an explicit structure element. The box-grid
	% renderer (forced on earlier) draws each week as a bare \hbox in the vertical
	% list; bare boxes don't engage LaTeX's block/paragraph tagging, so their
	% cell structure (Div/text) orphans as a direct child of StructTreeRoot
	% instead of nesting under the document's single <Document> element -- failing
	% PDF/UA 8.2.5.2 (one Document) and the Table 5 StructTreeRoot-* rules. An
	% explicit <Sect> opened here (a proper child of <Document>) re-parents every
	% row under it. Gated: \tagstructbegin exists only under \DocumentMetadata.
	\ifdefined\TeXLibAccessibleMode\tagstructbegin{tag=Sect}\fi
	\directlua{ render_grid(\GetMonthPagesFlag, \GetBoxGridFlag) }
	\ifdefined\TeXLibAccessibleMode\tagstructend\fi
}

\endinput
