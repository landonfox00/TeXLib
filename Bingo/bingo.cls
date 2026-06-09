% bingo.cls
% Math Bingo Card Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bingo}[2026/05/07 v1.1 Math Bingo Cards (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
% Per-document metadata may be passed in the class option list, e.g.
%   \documentclass[bingo-title={Exam 2 Bingo}, show-title=true]{bingo}
% Any option containing "=" is a metadata key=value pair (applied at the end of
% section 3, after coursemeta.tex loads, so document options win); every other
% option (11pt, ...) is forwarded to article. Metadata is read from
% \@raw@classoptionslist so values keep their spaces. \DeclareOption* only
% forwards the non-metadata options; the key=value ones pass through it (a no-op)
% so the kernel marks them used. Safe because no base-class option uses key=value.
\DeclareOption*{%
	\@expandtwoargs\in@{=}{\CurrentOption}%
	\ifin@\else
		\PassOptionsToClass{\CurrentOption}{article}%
	\fi
}
\ProcessOptions\relax
\LoadClass[11pt]{article}

% A class-option value containing a comma (e.g. institution={..., Reno}) is split
% by the kernel's option parser into a stray fragment with no "=", which would be
% reported as an "unused global option". The real values are consumed from
% \@raw@classoptionslist below, so discard those spurious leftovers.
\AtEndOfClass{\global\let\@unusedoptionlist\@empty}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage[margin=1in]{geometry}     % 1in, matching the other TeXLib classes
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{etoolbox}
\RequirePackage{tikz}
\RequirePackage{graphicx}                 % \scalebox for fit-to-cell
\RequirePackage{amsmath, amssymb, amsfonts}

\RequirePackage{course-metadata}

% Shared document-instructions mechanism (inline / file / default, file > inline
% > default). \TeXLibDeclareInstructions{bingo} below mints \GetBingoInstructions,
% \IfBingoInstructions{File,Inline}, and \bingo@input@userinstructions.
\RequirePackage{texlib-instructions}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}

% Randomization + cell-list engine (LuaLaTeX only). \directlua loads the
% sibling bingo.lua via kpathsea so the Lua keeps normal file syntax.
\directlua{ dofile(kpse.find_file("bingo.lua")) }


% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\newif\ifbingo@headers       \bingo@headerstrue
\newif\ifbingo@title         \bingo@titlefalse
\newif\ifbingo@instructions  \bingo@instructionsfalse

\ExplSyntaxOn

\dim_new:N \g__bingo_cell_size_dim
\dim_gset:Nn \g__bingo_cell_size_dim { 3.1cm }   % 5 cells fit inside 1in margins

\tl_new:N \g__bingo_free_symbol_tl
\tl_gset:Nn \g__bingo_free_symbol_tl { \star }

% Running-header title (e.g. "Exam 2 Bingo"); set per document via
% \meta{bingo-title={...}}. Defaults to a bare "Bingo".
\tl_new:N \g__bingo_title_tl
\tl_gset:Nn \g__bingo_title_tl { Bingo }

\keys_define:nn { meta } {
	cell-size      .code:n  = { \dim_gset:Nn \g__bingo_cell_size_dim { #1 } },
	free-symbol    .tl_gset:N = \g__bingo_free_symbol_tl,
	bingo-title    .tl_gset:N = \g__bingo_title_tl,
	show-headers   .choice:,
	show-headers / true   .code:n = { \bingo@headerstrue  },
	show-headers / false  .code:n = { \bingo@headersfalse },
	show-title     .choice:,
	show-title  / true    .code:n = { \bingo@titletrue  },
	show-title  / false   .code:n = { \bingo@titlefalse },
	show-instructions  .choice:,
	show-instructions / true   .code:n = { \bingo@instructionstrue  },
	show-instructions / false  .code:n = { \bingo@instructionsfalse },
}

\NewExpandableDocumentCommand{\GetBingoTitle}{}{
	\tl_use:N \g__bingo_title_tl
}
\NewExpandableDocumentCommand{\GetBingoFreeSymbol}{}{
	\tl_use:N \g__bingo_free_symbol_tl
}
\NewExpandableDocumentCommand{\GetBingoCellSize}{}{
	\dim_use:N \g__bingo_cell_size_dim
}

\ExplSyntaxOff

% Instructions: mints the bingo-instructions inline key, \GetBingoInstructions,
% \IfBingoInstructions{File,Inline}, and \bingo@input@userinstructions (default
% file bingo-instructions.tex). bingo-instructions-file lives in
% course-metadata.sty (set per document via \meta or course-wide in coursemeta.tex).
\TeXLibDeclareInstructions{bingo}

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

% Per-card environment options: \begin{bingocard}[copies=30, randomize, seed=181]
% (classic keyval — plain catcodes, so the @-named state below is reachable.)
\RequirePackage{keyval}
\newcount\bingo@copies
\newcount\bingo@seed
\newif\ifbingo@randomize
\newif\ifbingo@keepfree
\define@key{bingo@card}{copies}{\bingo@copies=#1\relax}
\define@key{bingo@card}{randomize}[true]{\csname bingo@randomize#1\endcsname}
% keepfree (default on): when randomizing, always place \free if it is in the
% pool, so every card has a free space (it still lands at a random cell).
\define@key{bingo@card}{keepfree}[true]{\csname bingo@keepfree#1\endcsname}
% seed (default 0): a reshuffle salt. The randomization is fixed across builds;
% changing seed deals a new (still build-stable) set from the same pool.
\define@key{bingo@card}{seed}{\bingo@seed=#1\relax}
\newcommand{\BingoCardSetup}[1]{%
	\bingo@copies=1 \bingo@seed=0 \bingo@randomizefalse \bingo@keepfreetrue
	\setkeys{bingo@card}{#1}%
}

% ==============================================================================
% 4. PAGE STYLE — unified TeXLib footer with a per-card verification ID
% ==============================================================================
% Each card carries the shared TeXLib footer (LEFT = \GetCourse, RIGHT =
% \GetInstitution, 0.4pt rule). The center field shows the card's sequential
% number, which is ALSO its random seed (see \bingo@onecard) — so one number
% both orders the sheets and regenerates the card. Cards are one-per-page by
% design (put \newpage between cards).

\RequirePackage{texlib-footer}   % shared L/C/R footer + 0.4pt footrule

\newcounter{bingocardno}

% --- install the header + footer --------------------------------------------
% center = card number (blank on non-card pages like the instructions cover,
% where no card has been emitted yet so the counter is still 0)
\newcommand{\bingo@footcenter}{\ifnum\value{bingocardno}>0 \thebingocardno\fi}
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = bingo title (e.g. "Exam 2 Bingo")  R = student name field
% (mirroring quiz/exam). Center is left empty -- the "Answer Key" indicator
% already lives in the body title block (\bingotitle).
\SetTeXLibHeader{\bfseries\GetBingoTitle}{}{Name:\ \underline{\hspace{2in}}}
\SetTeXLibFooter                    % L=\GetCourse | C (overridden) | R=\GetInstitution, 0.4pt rule
\fancyfoot[C]{\bingo@footcenter}    % override center: card / page number
\TeXLibRuleBleed                    % symmetric rule length, matching the other classes

% ==============================================================================
% 5. BINGO CARD ENVIRONMENT
% ==============================================================================
% Coordinate convention (origin = bottom-left of grid)
%   columns: B=0.5, I=1.5, N=2.5, G=3.5, O=4.5
%   rows:    row 1 = top  (y = 4.5)
%            row 5 = bot  (y = 0.5)
%   Free space at (N, 3) → centre cell (2.5, 2.5)
\expandafter\def\csname bingo@x@B\endcsname{0.5}
\expandafter\def\csname bingo@x@I\endcsname{1.5}
\expandafter\def\csname bingo@x@N\endcsname{2.5}
\expandafter\def\csname bingo@x@G\endcsname{3.5}
\expandafter\def\csname bingo@x@O\endcsname{4.5}
\expandafter\def\csname bingo@y@1\endcsname{4.5}
\expandafter\def\csname bingo@y@2\endcsname{3.5}
\expandafter\def\csname bingo@y@3\endcsname{2.5}
\expandafter\def\csname bingo@y@4\endcsname{1.5}
\expandafter\def\csname bingo@y@5\endcsname{0.5}

% \bcell{col}{row}{content} — math-mode content
\newcommand{\bcell}[3]{%
	\node at (\csname bingo@x@#1\endcsname, \csname bingo@y@#2\endcsname) {\Huge $#3$};%
}
% \bcelltext{col}{row}{content} — text-mode content
\newcommand{\bcelltext}[3]{%
	\node at (\csname bingo@x@#1\endcsname, \csname bingo@y@#2\endcsname) {#3};%
}

% --- grid-body engine --------------------------------------------------------
% \free is an ordinary bank token rendering the free symbol; it shuffles and
% samples like any other entry — there is no reserved centre cell.
\newcommand{\free}{\GetBingoFreeSymbol}

\ExplSyntaxOn
\box_new:N \l__bingo_cell_box
\fp_new:N  \l__bingo_fit_fp
\dim_new:N \l__bingo_avail_dim

% \bingoplacecell{x}{y}{content}: a tikz node whose math content is typeset at a
% fixed large base size, then shrunk (aspect-preserving) only if it overflows
% the cell. Single symbols stay big and uniform; fat expressions scale down. If
% it would shrink past the legibility floor we error instead of printing a
% sliver. Names use no @ so the Lua engine can print the call at document catcodes.
\cs_new_protected:Npn \bingoplacecell #1#2#3 {
	\node ~ at ~ ( #1 , #2 ) ~ { \__bingo_fit:n {#3} } ;
}
\cs_new_protected:Npn \__bingo_fit:n #1 {
	\hbox_set:Nn \l__bingo_cell_box { \Huge $ \displaystyle #1 $ }
	\dim_set:Nn \l__bingo_avail_dim { \g__bingo_cell_size_dim - 8mm }
	\fp_set:Nn \l__bingo_fit_fp {
		min( 1 ,
			\dim_to_fp:n { \l__bingo_avail_dim } / \dim_to_fp:n { \box_wd:N \l__bingo_cell_box } ,
			\dim_to_fp:n { \l__bingo_avail_dim } / \dim_to_fp:n { \box_ht:N \l__bingo_cell_box + \box_dp:N \l__bingo_cell_box }
		)
	}
	\fp_compare:nNnTF { \l__bingo_fit_fp } < { 0.40 } {
		\msg_error:nnee { bingo } { cell-too-big }
			{ \tl_to_str:n {#1} }
			{ \fp_eval:n { round( 100 * \l__bingo_fit_fp ) } }
	}{
		\scalebox { \fp_to_decimal:N \l__bingo_fit_fp } { \box_use:N \l__bingo_cell_box }
	}
}
\msg_new:nnn { bingo } { cell-too-big }
	{ Cell~"#1"~is~too~large~to~fit~(needs~#2~percent~of~full~size).~
	  Shorten~it,~split~the~bank,~or~raise~cell-size. }
\ExplSyntaxOff

% \begin{bingocard}[copies=N, randomize, seed=K] <grid body> \end{bingocard}
% Cells are separated by & and \\ — lay the body out as a 5x5 grid; it is read
% as a flat ordered list. With `randomize`, the list is shuffled (and sampled to
% 25 if longer) per copy, seeded by the card's sequential number (plus the
% optional seed salt) — fixed across builds. A body that calls \labelcells or
% \bcell is routed to the legacy renderer (older documents).
\newif\ifbingo@commas   % true => split the body on commas (pools); false => & \\
\NewDocumentEnvironment{bingocard}{ O{} +b }
{%
	\BingoCardSetup{#1}%
	\bingo@commasfalse                 % inline cards are a 5x5 grid (& and \\)
	\def\bingo@bodyraw{#2}%
	\edef\bingo@body{\detokenize{#2}}%
	\bingo@docopies
}{}

\newcommand{\bingo@docopies}{%
	\count255=1
	\loop\ifnum\count255<\numexpr\bingo@copies+1\relax
		\bingo@onecard
		\ifnum\count255<\bingo@copies\relax\newpage\fi
		\advance\count255 by 1
	\repeat
}

% \bingo@onecard: draw one full card. Its seed is its own sequential number,
% so the footer number both labels and regenerates the card.
\newcommand{\bingo@onecard}{%
	\stepcounter{bingocardno}%
	\ifbingo@instructions\bingo@cardinstructions\fi  % pinned just below the header
	\vspace*{\fill}%                    centre the grid in the space beneath
	\ifbingo@title\bingotitle\fi
	\begin{center}%
	\begin{tikzpicture}[x=\GetBingoCellSize, y=\GetBingoCellSize]%
		\foreach \i in {0,1,2,3,4}{%
			\foreach \j in {0,1,2,3,4}{%
				\draw[thick] (\i,\j) rectangle (\i+1,\j+1);%
			}%
		}%
		\ifbingo@headers
			\node at (0.5, 5.3) {\textbf{B}};%
			\node at (1.5, 5.3) {\textbf{I}};%
			\node at (2.5, 5.3) {\textbf{N}};%
			\node at (3.5, 5.3) {\textbf{G}};%
			\node at (4.5, 5.3) {\textbf{O}};%
		\fi
		\bingo@dispatch
	\end{tikzpicture}%
	\end{center}%
	\vspace*{\fill}%
}

% The Lua engine parses the body, decides legacy-vs-grid, and prints the cells.
% Legacy bodies (\labelcells / \bcell) are re-emitted verbatim plus the auto
% free centre; grid bodies are split, optionally shuffled, and placed.
\newcommand{\bingo@dispatch}{%
	\directlua{ bingo.render(
		"\luaescapestring{\bingo@body}",
		\ifbingo@randomize true\else false\fi,
		\the\value{bingocardno},
		\the\bingo@seed,
		\ifbingo@keepfree true\else false\fi,
		\ifbingo@commas true\else false\fi) }%
}

% --- named pools: declare once, stamp out cards without a body ---------------
% \bingobank[name]{ <comma-separated entries> } stores a pool (default name
% "default"); usable in the preamble. Entries are a plain list (any length, one
% per line is tidy); an entry that itself contains a top-level comma must be
% braced. \bingocards[options] emits cards from a pool (bank=<name>, default
% "default") with no body. This is the reuse path: one pool, many randomized sets.
\NewDocumentCommand{\bingobank}{ O{default} +m }{%
	\expandafter\xdef\csname bingo@storedbank@#1\endcsname{\detokenize{#2}}%
}

\define@key{bingo@card}{bank}{\def\bingo@bankname{#1}}
\NewDocumentCommand{\bingocards}{ O{} }{%
	\def\bingo@bankname{default}%
	\BingoCardSetup{#1}%
	\bingo@commastrue                  % pools are a comma-separated list
	\expandafter\ifx\csname bingo@storedbank@\bingo@bankname\endcsname\relax
		\PackageError{bingo}{No bingo bank named "\bingo@bankname"}%
			{Declare it first with \string\begin{bingobank}[\bingo@bankname]...\string\end{bingobank}.}%
	\else
		\expandafter\let\expandafter\bingo@body\csname bingo@storedbank@\bingo@bankname\endcsname
		\def\bingo@bodyraw{}%
		\bingo@docopies
	\fi
}

% ==============================================================================
% 6. LABELED CELLS (exam-bingo style — Math 181 Su25)
% ==============================================================================
% Inside a bingocard, call \labelcells to fill all 24 (non-free) cells with
% their B1..O5 grid label. Free space remains the configured symbol.
\newcommand{\labelcells}{%
	\foreach \col/\ci in {B/1, I/2, N/3, G/4, O/5}{%
		\foreach \rw in {1,2,3,4,5}{%
			\ifnum\rw=3
				\ifnum\ci=3\else
					\node at ({\ci-0.5}, {5.5-\rw}) {\Huge \col\rw};%
				\fi
			\else
				\node at ({\ci-0.5}, {5.5-\rw}) {\Huge \col\rw};%
			\fi
		}%
	}%
}

% \bingolegend{rows} — 5-column tabular for label→expression key
\NewDocumentCommand{\bingolegend}{ +m }{%
	\begin{normalsize}%
		\renewcommand{\arraystretch}{2.8}%
		\setlength{\tabcolsep}{1.25em}%
		\begin{tabular}{l|l|l|l|l}#1\end{tabular}%
	\end{normalsize}%
}

% ==============================================================================
% 7. AUTO TITLE BLOCK
% ==============================================================================
\newcommand{\bingotitle}{%
	\begin{center}
		{\Large \bfseries \GetCourse}\par
		\vspace{0.2em}
		{\large \GetTerm}\par
		\ifkey\vspace{0.2em}\textit{Answer~Key}\par\fi
		\vspace{0.6em}
	\end{center}%
}

% \maketitle is the unified TeXLib title-block command. For bingo it just
% emits the standard banner once (typically at the top of the document,
% before any \bingocard). To repeat the title above each card, set
% \meta{show-title=true}.
\renewcommand{\maketitle}{\bingotitle}

% ==============================================================================
% 8. INSTRUCTIONS  (mirrors quiz.cls: file > inline > default, boxed)
% ==============================================================================
% \bingoinstructions emits a how-to-play block — typically once, on a cover page
% before \bingocards. Resolution (via texlib-instructions): a
% \meta{bingo-instructions-file=...} (input verbatim, controls its own layout)
% overrides \meta{bingo-instructions={...}} (boxed inline text), which overrides
% the default wording in bingo-instructions.tex. The default is a real file so
% SyncTeX inverse search (double-click in the PDF) jumps to its source.

% \bingoinstructions — a standalone how-to-play block (title + box), e.g. on a
% cover page before \bingocards.
\newcommand{\bingoinstructions}{%
	\IfBingoInstructionsFile{%
		% File content controls its own layout (no automatic box around it).
		\begin{center}{\LARGE \GetBingoTitle}\end{center}%
		\bingo@input@userinstructions
	}{%
		\begin{center}{\LARGE \GetBingoTitle}\par\medskip
			\TeXLibInstructionsBox{\TeXLibInstructionsInlineOrDefault{bingo}}\end{center}%
	}%
}

% The per-card block (no big title — the running header already shows it),
% emitted above each grid when show-instructions=true.
\newcommand{\bingo@cardinstructions}{\TeXLibInstructions{bingo}}

\endinput
