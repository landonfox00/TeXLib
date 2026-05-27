% schedule.cls
% UNR Course Schedule Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{schedule}[2026/05/07 v5.0 UNR Course Schedule (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass{article}

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

% Default getter for fields some courses don't set
\providecommand{\GetRecitationDays}{}

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

% ==============================================================================
% 5. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\ExplSyntaxOn

\clist_new:N \g__sched_lecture_caps_clist
\clist_new:N \g__sched_quiz_days_clist
\bool_new:N  \g__sched_landscape_bool

\keys_define:nn { meta } {
	lecture-caps  .clist_gset:N = \g__sched_lecture_caps_clist,
	quiz-days     .clist_gset:N = \g__sched_quiz_days_clist,

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

\ExplSyntaxOff

% ==============================================================================
% 6. SCHEDULE ENVIRONMENT
% ==============================================================================
% \maketitle / \scheduletitle render the standard banner. The schedule env
% calls \scheduletitle automatically, so existing documents are unchanged;
% \maketitle provides the unified TeXLib entry point.
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

	\scheduletitle

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
	\directlua{ render_grid() }
}

\endinput
