\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{autoexam}[2025/02/13 AutoExam Class (Merged)]

% Pass any options to the base exam class
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{exam}}
\ProcessOptions\relax

% Load the base class
\LoadClass[11pt]{exam}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage[T1]{fontenc}
\RequirePackage{lmodern}
\RequirePackage[margin=1in]{geometry}
\RequirePackage{xparse}
\RequirePackage{ifthen}
\RequirePackage[export]{adjustbox}
\RequirePackage{changepage}
\RequirePackage{comment}
% enumitem removed — known incompatibility with exam.cls (exam.cls defines
% questions/parts as list environments; enumitem patches \list and breaks them)
\RequirePackage{graphicx}
\RequirePackage{lastpage}
\RequirePackage{needspace}
\RequirePackage{subfigure}
\RequirePackage{xcolor}
\RequirePackage{amsmath, amssymb, amsthm, mathtools}
\RequirePackage{cancel}           % \cancel{} for crossing out terms in solutions
% \RequirePackage{siunitx}  % unavailable on test server
\RequirePackage{pdfpages}
\RequirePackage[subfigure]{tocloft}
\RequirePackage{tikz, pgfplots}
\RequirePackage{hyperref}
% \RequirePackage{luacode} % Essential for the engine  % replaced by dofile in test env
\RequirePackage{array}
\RequirePackage{multirow}
\RequirePackage{multicol}
\RequirePackage{etoolbox}
\RequirePackage[many]{tcolorbox}    % minimal-style solution box (matches didactic)
\RequirePackage{environ} % For capturing solution bodies
\RequirePackage{texlib-mathutils}  % \mbb, \abs, \lrp, \dd, \deriv, \inte, \todo, ...
\RequirePackage{course-metadata} % Auto-loads coursemeta.tex from ancestor dirs

% ==============================================================================
% 2. CONFIGURATION & SETUP
% ==============================================================================

% TikZ & PGFPlots
\pgfplotsset{compat=1.18}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric}
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

% Hyperref Setup
\hypersetup{
	colorlinks=true,
	urlcolor=blue,    % URLs stay blue (useful in syllabi, course sheets, etc.)
	linkcolor=black,  % internal cross-references: invisible in print, still clickable
	citecolor=black   % citations likewise
}

% SIUnitX Setup (only when package is available)
\ifdefined\sisetup
\sisetup{
	table-number-alignment=center,
	mode=math
}
\fi

% ==============================================================================
% 3. BUILD MODES & FLAGS
% ==============================================================================
% Adopt the unified TeXLib build-flag CLI. \ifsolutions, \ifkey, \ifrubric,
% \ifdraft, \ifstudent, \ifinstructor and the matching \Show.../\StudentMode
% command-line toggles are all defined here.
\RequirePackage{texlib-build}

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
	\directlua{set_autoexam_versions('\luaescapestring{#1}')}%
	\typeout{AutoExam: Detected Versions: #1}%
}
\let\versions\examversions              % \versions is the preferred short alias

% Source-level toggles \solutions, \keys, \rubrics, \drafts, \studentmode,
% \instructormode are provided by texlib-build (loaded above).

% ==============================================================================
% 4. LUA ENGINE (Randomization, Math, Scopes)
% ==============================================================================
% Locates autoexam_engine.lua across three possible layouts:
%   (1) installed in a TEXMF tree              → kpse with the "lua" format
%   (2) sitting next to autoexam.cls           → legacy per-module copy
%   (3) at the TeXLib root, one level up       → current canonical layout
% The cwd fallback covers the edge case where the engine sits next to the
% .tex file being built (e.g. a standalone test).
% NOTE: no Lua `--` line comments inside this \directlua block. TeX collapses
% the newlines into spaces before Lua sees the chunk, so a `--` comment would
% swallow the rest of the code. Keep explanations in TeX `%` comments above.
\directlua{
	local function load_engine(name)
		local cls_path = kpse.find_file("autoexam.cls")
		local base_dir = cls_path and cls_path:match("(.*[/\\])") or ""
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
}%

% ==============================================================================
% LaTeX Interfaces for Lua
% ==============================================================================

% --- Variable Management ---

% \setvar{name}{value}  — store a named value
\newcommand{\setvar}[2]{\directlua{set_var('#1', #2)}}

% \setrng{name}{min}{max}  — store a single random integer in [min, max]
\newcommand{\setrng}[3]{\directlua{set_rng('#1', #2, #3)}}

% \calcvar{name}{lua-expr}  — compute an expression using stored vars
\newcommand{\calcvar}[2]{\directlua{calc_var('#1', '#2')}}

% \get{name}  — retrieve and typeset a stored value
\newcommand{\get}[1]{\directlua{get_var('#1')}}

% --- Randomization: Pick from List ---

% \picklist{name}{n}{a, b, c, ...}  — pick n items WITHOUT replacement
% NOTE: list items must not contain commas themselves.
\NewDocumentCommand{\picklist}{m m m}{%
	\directlua{pick_from_list('\luaescapestring{#1}', #2, '\luaescapestring{#3}')}%
}

% \picklistr{name}{n}{a, b, c, ...}  — pick n items WITH replacement
\NewDocumentCommand{\picklistr}{m m m}{%
	\directlua{pick_from_list_r('\luaescapestring{#1}', #2, '\luaescapestring{#3}')}%
}

% --- Randomization: Pick from Range ---

% \pickrange{name}{n}{min}{max}  — pick n distinct integers from [min, max]
\NewDocumentCommand{\pickrange}{m m m m}{%
	\directlua{pick_from_range('\luaescapestring{#1}', #2, #3, #4)}%
}

% \pickranger{name}{n}{min}{max}  — pick n integers from [min, max] with replacement
\NewDocumentCommand{\pickranger}{m m m m}{%
	\directlua{pick_from_range_r('\luaescapestring{#1}', #2, #3, #4)}%
}

% --- Retrieval Helpers ---

% \getlist{name}  — typeset all picked values, comma-separated
\NewDocumentCommand{\getlist}{m}{%
	\directlua{get_list('\luaescapestring{#1}')}%
}

% \geti{name}{i}  — typeset the i-th picked value (1-indexed)
\NewDocumentCommand{\geti}{m m}{%
	\directlua{get_var('\luaescapestring{#1}_' .. #2)}%
}

% \foreachpick[sep]{name}{code}  — iterate over picked values;
%   \currentpick is set to each value before {code} is executed.
%   Optional [sep] is inserted between items (default: comma-space).
\NewDocumentCommand{\foreachpick}{O{,\space} m +m}{%
	\directlua{
		local count = tonumber(tostring(vars['\luaescapestring{#2}_count'])) or 0
		for i = 1, count do
			local v = vars['\luaescapestring{#2}_' .. i]
			if v ~= nil then
				tex.sprint('\\def\\currentpick{' .. tostring(v) .. '}')
				tex.sprint('\luaescapestring{\unexpanded{#3}}')
				if i < count then
					tex.sprint('\luaescapestring{\unexpanded{#1}}')
				end
			end
		end
	}%
}

% --- Problem Bank ---

% \newproblem{id}{meta}{content}[solution]
%   Define a problem in the database. The solution argument is optional;
%   if omitted, the problem has no solution shown in key/solution builds.
%   May be called in the document preamble, inside a bank file, or in the
%   document body. Redefining an existing ID overwrites it with a warning.
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

% \dupproblem — deprecated alias for \newproblem (four mandatory args)
\NewDocumentCommand{\dupproblem}{m m +m +m}{%
	\directlua{define_problem(
		'\luaescapestring{#1}',
		'\luaescapestring{#2}',
		'\luaescapestring{\unexpanded{#3}}',
		'\luaescapestring{\unexpanded{#4}}'
	)}%
}

% \getproblem{query}  — unified retrieve/query command.
%   Plain id:      \getproblem{linear_eq}
%   Key=val query: \getproblem{topic=algebra, diff=hard}
%   If no '=' is found the whole string is treated as a problem id.
%   Multiple key=value pairs are ANDed; one random match is typeset.
%   On no match: emits a visible placeholder and a log warning.
\NewDocumentCommand{\getproblem}{m}{%
	\directlua{get_problem('\luaescapestring{#1}')}%
}

% Backward-compat aliases
\let\useproblem\getproblem
\NewDocumentCommand{\reqproblem}{m}{\getproblem{#1}}

% \begin{problem}{id}[key=val, key=val, ...]
%   Define a problem in the bank.  Produces no output at definition time.
%   Everything before the first \solution token in the body is the problem
%   content; everything after is the solution.  Void setup commands
%   (\setrng, \calcvar, etc.) may appear anywhere in the body.
%
%   Implementation notes:
%     - \Collect@Body (from environ) intercepts the body without opening a
%       nested environment, avoiding LaTeX's env-stack mismatch error.
%     - \unexpanded{#1} prevents expansion of \solution and setup commands
%       when the body is passed to \luaescapestring for Lua storage.
%     - define_problem_from_env() splits the resulting string on \solution.

% Internal callback: receives the full collected body as #1.
\long\def\@problem@collect@done#1{%
	\directlua{define_problem_from_env(
		'\luaescapestring{\@problem@id}',
		'\luaescapestring{\@problem@meta}',
		'\luaescapestring{\unexpanded{#1}}'
	)}%
}

% Scan the optional [meta] argument then start body collection.
\def\@problem@scan{%
	\@ifnextchar[%
		{\@problem@getmeta}%
		{\def\@problem@meta{}\Collect@Body\@problem@collect@done}%
}
\def\@problem@getmeta[#1]{%
	\def\@problem@meta{#1}%
	\Collect@Body\@problem@collect@done
}

% Public environment: \begin{problem}{id}[meta] ... \end{problem}
\newenvironment{problem}[1]{%
	\def\@problem@id{#1}%
	% Record the bank-file line number NOW (before \Collect@Body reads ahead to
	% \end{problem}).  By the time define_problem_from_env() runs, \inputlineno
	% has advanced to the \end{problem} line, so we snapshot it here instead.
	\directlua{autoexam_problem_start_line = tex.inputlineno}%
	\@problem@scan
}{%
	% End-code is empty; \Collect@Body handles everything at \end{problem}.
}

% --- problems environment + \problem item command ---
%
% LaTeX naming note: \begin{problem} (definition environment) uses \problem
% as its begin-code, so a global \problem item command would shadow it.
% Solution: define the item command once under \@problem@item, then let
% \begin{problems} locally swap \problem <-> \@problem@item and restore on exit.
%   - \begin{problem}{id}[meta] works everywhere OUTSIDE {problems}
%   - \problem[pts][stretch]{filter} works INSIDE {problems}

% \ppart — problem-part item for use inside \begin{problem} bodies.
%   Always delegates to exam class's \part (the list-item command inside
%   \begin{parts}).  When the enclosing \problem item carries per-part
%   point values (e.g. \problem[2,3]{id}), each \ppart call automatically
%   injects the corresponding point annotation via the Lua part-index state.
\NewDocumentCommand{\ppart}{}{\directlua{autoexam_inject_part()}}

% \@problem@item[points][stretch]{filter}
%   The actual item command implementation — defined once at class load.
%   #1 = points  (optional, default empty = no point label)
%             Single value: annotates the \question (e.g. \problem[5]{id})
%             Comma-sep:    distributed to \ppart calls (e.g. \problem[2,3]{id})
%   #2 = stretch (optional, default 1 = \vspace{\stretch{1}} after body)
%             Per-part stretch is not yet supported; first value is used.
%   #3 = filter  (mandatory, forwarded verbatim to get_problem)
%
%   All token output (\question, problem content, stretch) is generated inside
%   Lua via tex.print, avoiding pre-tokenized-token interactions with the
%   comment package's \excludecomment catcode scanner.
\NewDocumentCommand{\@problem@item}{O{} O{1} m}{%
	\directlua{autoexam_problem_item(
		'\luaescapestring{#1}',
		'\luaescapestring{#2}',
		'\luaescapestring{#3}'
	)}%
}

% \begin{problems} ... \end{problems}
%   Drop-in replacement for {questions} that accepts \problem items.
%   The {questions} environment is preserved for backward compat.
%
%   On entry:
%     - resets the page counter to 1 so Q1 lands on page 1
%     - restores first-page and running header/footer slots (problem style)
%     - initialises the inter-problem separator state (first on page = no rule)
%     - patches \newpage to also reset the separator flag
%
%   On exit:
%     - places \label{@lastqpage} on the last problem page (read by the "X of N"
%       footer once \blankpage ships that page)
\newenvironment{problems}{%
	% ---- ship any pending page (e.g. pre-problem scratch page from \blankpage) -
	\clearpage
	% ---- page counter & header/footer ----------------------------------------
	\setcounter{page}{1}%
	% Q1 is "page 1" and receives the first-page style (\@fullhead / \@fullfoot).
	% Restore those slots to match the running header so Q1 looks identical to
	% every subsequent problem page.
	%
	% IMPORTANT: \begin{problems} opens a LaTeX environment group (\begingroup).
	% Any \def here is LOCAL and reverts when \end{problems} closes the group.
	% The last problem page and the \scorepage both ship AFTER the group closes,
	% so their headers/footers must be set with \global (\gdef / \global\def).
	% First-page slots (\@lhead etc.) are only needed for Q1, which ships via
	% the first \newpage inside the group, so local \def is fine there.
	\def\@lhead{Math \theCourseNumber\ \theCourseTitle}%
	\def\@chead{}%
	\def\@rhead{Exam \theExamNumber}%
	\global\@headruletrue%
	\def\@cfoot{%
		\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
	}%
	% Running slots for Q2+ — MUST be global so they survive \end{problems}.
	\gdef\run@chead{}%
	\global\def\run@cfoot{%
		\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
	}%
	% ---- inter-problem separator ---------------------------------------------
	% First problem on each page gets no rule; subsequent problems get a rule above.
	\directlua{autoexam_first_on_page = true}%
	% Patch \newpage so crossing a page boundary resets the "first on page" flag.
	\let\@problems@saved@newpage\newpage
	\renewcommand{\newpage}{%
		\@problems@saved@newpage
		\directlua{autoexam_first_on_page = true}%
	}%
	% ---- start questions list -----------------------------------------------
	\begin{questions}%
	\let\@saved@problem\problem
	\let\problem\@problem@item
}{%
	\let\problem\@saved@problem
	\let\newpage\@problems@saved@newpage
	\end{questions}%
	% Place the label on the last problem page.  \blankpage (which follows) ships
	% that page via \clearpage, recording the correct page number for "X of N".
	\label{@lastqpage}%
}

% \loadbank{path}  — explicitly load a problem bank file.
%
% Implementation note (2026-05): the engine ships an optional bank-file
% SyncTeX-redirect path (typeset_problem → \csname @@input\endcsname bank.tex
% per problem, intercepted by an open_read_file callback so SyncTeX
% attributes typeset nodes to the bank file directly).  That path is gated
% on source_map[id].file being non-empty, which previously was set by
% \loadbank calling autoexam_set_bankfile() before \input.
%
% In multi-version mode this redirect interacts badly with LuaTeX's input
% stack: each problem typeset performs its own \@@input of the bank file,
% and after ~15 problems the run aborts with a "TeX capacity exceeded"
% error.  The engine's own attempt to raise the limit
% (texconfig.max_in_open = 127 at the top of autoexam_engine.lua) is a no-op
% because texconfig is only consulted during LuaTeX initialisation, well
% before \directlua{dofile(...)} fires at class load.
%
% Workaround: do not record the bank-file path here.  source_map[id].file
% stays empty for every problem defined inside the bank file, so
% typeset_problem() always uses the per-problem-tempfile fallback (jobname
% _prob_<id>.tex), which has none of the input-stack problems.  SyncTeX
% inverse search then lands on the per-problem temp file rather than the
% bank file itself — acceptable for normal authoring workflows, and the
% .srcmap mechanism remains available for future builder-side fix-ups.
\NewDocumentCommand{\loadbank}{m}{%
	\input{#1}%
}

% \shufflepages
%   Declared in the PREAMBLE alongside \examversions.  When present, the Lua
%   version loop splits the \begin{problems}...\end{problems} body on each
%   top-level \newpage (treating them as page-group separators), shuffles the
%   groups independently per version using that version's RNG seed, and writes
%   a per-version temp file before TeX processes any tokens.  No changes to
%   the exam body are needed — \newpage continues to serve as the separator
%   exactly as it did before.
\newcommand{\shufflepages}{%
	\directlua{set_autoexam_shuffle_pages()}%
}

% \byversion{A content}{B content}{C content}
%   Selects and typesets the argument matching the current \theExamVersion.
%   Uses \csname dispatch to avoid \ifx long-macro comparison pitfalls.
\long\def\@byv@A#1#2#3{#1}
\long\def\@byv@B#1#2#3{#2}
\long\def\@byv@C#1#2#3{#3}
\newcommand{\byversion}[3]{%
	\csname @byv@\theExamVersion\endcsname{#1}{#2}{#3}%
}

% \importproblem{path}{overrides}  — import a standalone problem file with
%   Lua variable overrides (e.g. {a=5, b=10}) in an isolated scope.
\newcommand{\importproblem}[2]{%
	\begingroup
	\directlua{push_scope()}
	\directlua{
		for pair in string.gmatch("#2", "([^,]+)") do
			local key, val = string.match(pair, "([^=]+)=(.+)")
			if key and val then
				key = key:gsub("^%s*(.-)%s*$", "%1")
				val = val:gsub("^%s*(.-)%s*$", "%1")
				if tonumber(val) then set_var(key, tonumber(val))
				else set_var(key, val) end
			end
		end
	}
	\input{#1}
	\directlua{pop_scope()}
	\endgroup
}

% --- Initialization ---

% Seed RNG and auto-load any course-level banks at document start.
\AtBeginDocument{%
	\directlua{set_exam_seed('\theExamVersion')}%
	% Auto-load bank declared in coursemeta.tex (bank-path key).
	\@ifundefined{GetBankPath}{}{%
		\edef\@tmpbankpath{\GetBankPath}%
		\ifx\@tmpbankpath\empty\else
			\loadbank{\@tmpbankpath}%
		\fi
	}%
	% Auto-load bank.tex from the document's own directory, if present.
	\IfFileExists{bank.tex}{\loadbank{bank.tex}}{}%
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
	\directlua{autoexam_run_versions()}%
}

% ==============================================================================
% 5. ENVIRONMENTS (Solution & Key)
% ==============================================================================

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
%   p.solution contains non-whitespace content (see autoexam_engine.lua),
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

% ==============================================================================
% 6. SMART COLUMNS & SEPARATORS (Your Original Logic)
% ==============================================================================

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

% ==============================================================================
% 7. METADATA & CUSTOM COMMANDS
% ==============================================================================

% --- Document-specific metadata: set via \renewcommand in each .tex file ---
\newcommand{\theExamNumber}{\todo}
\newcommand{\theExamDate}{\todo}
\newcommand{\thePS}{}              % Optional postscript shown on title page

% --- Course metadata: auto-populated from coursemeta.tex via course-metadata.sty ---
% These \the* aliases preserve backward compatibility with existing documents
% that use \renewcommand to override them; new documents need not touch them.
\newcommand{\theCourseNumber}{\GetCourseNumber}
\newcommand{\theCourseTitle}{\GetCourseTitle}
\newcommand{\theCourseSection}{\GetCourseSection}
\newcommand{\theSeason}{\GetSeason}
\newcommand{\theYear}{\GetYear}
\newcommand{\theSchool}{\GetInstitution}

\renewcommand{\questionlabel}{\textbf{Problem \thequestion.}}
\renewcommand{\partlabel}{\textbf{\thequestion\thepartno.}}

% Top-level enumerate: bold lowercase-roman labels (i., ii., iii., ...).
% enumitem is intentionally NOT loaded in this class (see section 1 — it
% patches \list and breaks exam.cls's questions/parts), so we set the kernel
% label and counter macros directly.  \theenumi is switched to roman too, so
% any \ref to an enumerate item matches the printed label.
\renewcommand{\theenumi}{\roman{enumi}}
\renewcommand{\labelenumi}{\textbf{\theenumi.}}

% Custom Macros
% Math macros (\mbb, \mrm, \dd, \todo, plus \abs, \lrp, \deriv, \inte, ...)
% are provided by texlib-mathutils.sty, loaded in section 1 above.
\newcommand\encircle[1]{\tikz[baseline=(X.base)] \node (X) [draw, shape=circle, inner sep=0] {\strut #1};}

% Theorem Environments
\newtheorem*{thm*}{Theorem}
\newtheorem*{defn*}{Definition}
\newtheorem*{ex*}{Example}
% (Added generic ones, add others as needed)

% ==============================================================================
% 7b. EXAM SETUP INTERFACE
% ==============================================================================

% \@autoexam@instructions@file: path (without .tex) of the instructions file
%   loaded into the cover-page box.  Override via \examsetup{instructions-file=…}
%   or in coursemeta.tex.
\newcommand{\@autoexam@instructions@file}{autoexam-instructions}
% \autoexam@load@instructions: inputs the instructions file.
\newcommand{\autoexam@load@instructions}{\input{\@autoexam@instructions@file}}

% Exam metadata is set via the unified \meta{...} command, sharing the
% same keys family as every other TeXLib class. Use \meta{exam-number=5,
% exam-date=May 2 2026, ...} in the preamble. The legacy \examsetup{...}
% command remains supported as a thin alias that prefixes bare keys with
% "exam-" so old documents continue to work.
\ExplSyntaxOn
\keys_define:nn { meta } {
	exam-number             .code:n = { \renewcommand{\theExamNumber}{#1} },
	exam-date               .code:n = { \renewcommand{\theExamDate}{#1}   },
	exam-postscript         .code:n = { \renewcommand{\thePS}{#1}         },
	exam-instructions-file  .code:n = { \renewcommand{\@autoexam@instructions@file}{#1} },
	% Backward-compat aliases (bare names available via \examsetup or \meta)
	number                  .code:n = { \renewcommand{\theExamNumber}{#1} },
	date                    .code:n = { \renewcommand{\theExamDate}{#1}   },
	ps                      .code:n = { \renewcommand{\thePS}{#1}         },
	instructions-file       .code:n = { \renewcommand{\@autoexam@instructions@file}{#1} },
}
\ExplSyntaxOff

% \examsetup{...}: backward-compat alias for \meta{...}. Old exam files
% can keep using \examsetup{number=5, date=May 2 2026, ps=...}; these
% bare keys forward to the meta family above.
\NewDocumentCommand{\examsetup}{+m}{\metasetup{#1}}

% \autoexam@problem@sep — full-width rule inserted between consecutive problems
%   within a page group (i.e., problems not separated by \newpage).
%   Emitted automatically by \problem via the Lua engine for all but the first
%   problem on each page.  Redefine to change the separator style.
\newcommand{\autoexam@problem@sep}{%
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

% ==============================================================================
% 7c. GRAPH COMMAND
% ==============================================================================

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

% ==============================================================================
% 7d. RUBRIC & WORKBOX SYSTEM
% ==============================================================================

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
\NewDocumentCommand{\workbox}{m}{%
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

% ==============================================================================
% 7e. SCORE PAGE
% ==============================================================================

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
	\directlua{autoexam_scorepage(#1)}%
}

% ==============================================================================
% 8. PAGE LAYOUT & TITLE PAGE (Your Original Logic)
% ==============================================================================
\pagestyle{headandfoot}
\firstpagefootrule
\firstpagefooter{Section \theCourseSection}{}{\theSchool}
\runningheader{Math \theCourseNumber\ \theCourseTitle}{}{Exam \theExamNumber}
\runningheadrule
\runningfootrule
% Center footer shows "X of N" where N = last problem page via \label{@lastqpage}
% (placed by \blankpage on first call).  Falls back to \numpages until that label
% exists, and for exams without \blankpage at the end.
\runningfooter{Section \theCourseSection}{%
	\thepage\ of\ \@ifundefined{r@@lastqpage}{\numpages}{\pageref*{@lastqpage}}%
}{\theSchool}

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
		\huge Exam \theExamNumber \\
		\LARGE Math \theCourseNumber\ \theCourseTitle \\
		\vspace{0.1em}
		\large \theExamDate
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

		\fbox{\fbox{\parbox{\dimexpr\linewidth-4\fboxsep-4\fboxrule\relax}{%
			\noindent{\large\bf Instructions:}
			\autoexam@load@instructions
		}}}
		\vfill

		Name: \underline{\hspace{4in}}
		\vfill

		\ifthenelse{\equal{}{\thePS}}%
			{}%
			{\textit{\thePS}}%
	\end{center}
	% Title page is complete.  The user adds \blankpage after \maketitle to produce
	% a pre-problem scratch leaf.  \blankpage ships this page via \clearpage, sets
	% scratch style, and outputs \null.  \begin{problems} then resets the page
	% counter and restores problem headers.
}