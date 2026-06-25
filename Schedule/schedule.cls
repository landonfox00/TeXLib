% schedule.cls
% UNR Course Schedule Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{schedule}[2026/05/07 v5.0 UNR Course Schedule (TeXLib)]

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
\RequirePackage{xltabular}
\RequirePackage{colortbl}
\RequirePackage{multirow}
\RequirePackage{booktabs}
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{etoolbox}
\RequirePackage{xstring}
\RequirePackage{luacode}
\RequirePackage{lastpage}
\RequirePackage{fancyhdr}

\RequirePackage{course-metadata}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}


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
		local base_dir = cls_path and cls_path:match("(.*[/\\])") or ""
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
\bool_new:N  \g__sched_landscape_bool
\bool_new:N  \g__sched_monthpages_bool

\keys_define:nn { meta } {
	lecture-caps     .clist_gset:N = \g__sched_lecture_caps_clist,
	quiz-days        .clist_gset:N = \g__sched_quiz_days_clist,
	recitation-days  .clist_gset:N = \g__sched_recitation_days_clist,

	% month-pages = true  ->  one table per calendar month, each on its own
	% page, with month-boundary weeks repeated so every month shows full weeks.
	% Default (false / key omitted) keeps the term as one continuous table.
	month-pages   .bool_gset:N = \g__sched_monthpages_bool,

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

% Expands to the Lua literal `true`/`false` for the month-pages flag, so the
% \end{schedule} hook can pass it straight into render_grid(...).
\NewExpandableDocumentCommand{\GetMonthPagesFlag}{}{
	\bool_if:NTF \g__sched_monthpages_bool { true } { false }
}

% Apply document metadata from the class option list now that the keys above and
% coursemeta.tex are loaded (so document options override coursemeta defaults).
% Read \@raw@classoptionslist, not \CurrentOption, to keep spaces in values.
\cs_if_exist:cT { @raw@classoptionslist } {
	\tl_set:Nv    \l_tmpa_tl    { @raw@classoptionslist }
	\clist_set:NV \l_tmpa_clist \l_tmpa_tl
	\clist_map_inline:Nn \l_tmpa_clist {
		\tl_if_in:nnT { #1 } { = } { \keys_set:nn { meta } { #1 } }
	}
}

\ExplSyntaxOff

% ==============================================================================
% 6. SCHEDULE ENVIRONMENT
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
			"\GetYear"
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
	\directlua{ render_grid(\GetMonthPagesFlag) }
}

\endinput
