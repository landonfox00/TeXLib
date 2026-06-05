% bingo.cls
% Math Bingo Card Class — TeXLib unified style
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bingo}[2026/05/07 v1.1 Math Bingo Cards (TeXLib)]

% ==============================================================================
% 0. OPTIONS
% ==============================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[12pt]{article}

% ==============================================================================
% 1. PACKAGES
% ==============================================================================
\RequirePackage[margin=1in]{geometry}
\RequirePackage{xparse}
\RequirePackage{expl3}
\RequirePackage{etoolbox}
\RequirePackage{tikz}
\RequirePackage{amsmath, amssymb, amsfonts}

\RequirePackage{course-metadata}

% ==============================================================================
% 2. BUILD FLAGS — UNIFIED TeXLib CLI
% ==============================================================================
\RequirePackage{texlib-build}


% ==============================================================================
% 3. CLASS-LOCAL METADATA KEYS
% ==============================================================================
\newif\ifbingo@headers   \bingo@headerstrue
\newif\ifbingo@title     \bingo@titlefalse

\ExplSyntaxOn

\dim_new:N \g__bingo_cell_size_dim
\dim_gset:Nn \g__bingo_cell_size_dim { 2.8cm }

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

% ==============================================================================
% 4. PAGE STYLE — unified TeXLib footer with a per-card verification ID
% ==============================================================================
% Each card carries the shared TeXLib footer
%     LEFT = \GetCourse  |  CENTER = card ID  |  RIGHT = \GetInstitution
% with the standard 0.4pt footrule, but the center field replaces the usual
% "page X of Y" with a per-card verification identifier:
%
%     #<n> <bullet> <CODE>
%
% <n>    sequential copy number (#1, #2, ...) — lets the instructor count sheets.
% <CODE>6 uppercase hex digits of the MD5 checksum of this card's *ordered cell
%        contents* (every \bcell / \bcelltext / \labelcells entry, detokenized).
%
% The CODE is deterministic: the same arrangement of cells always yields the
% same CODE, and changing, adding, or reordering any cell changes it. To verify
% a physical sheet against the generated set, rebuild the card and confirm the
% printed CODE matches — a forged or photocopied sheet whose grid differs will
% carry a CODE that does not match its own layout. See \bingo@record /
% \bingo@finalise below.
%
% Cards are one-per-page by design (put \newpage between cards). If two cards
% share a page, the footer shows the last card's ID.

\RequirePackage{texlib-footer}   % shared L/C/R footer + 0.4pt footrule

% --- per-card content accumulator, counter, and ID --------------------------
\newcounter{bingocardno}
\newcommand{\bingo@content}{}     % running detokenized list of this card's cells
\newcommand{\bingo@cardid}{------}

% Engine-agnostic MD5 (pdflatex: \pdfmdfivesum; lualatex: \mdfivesum). Both
% return a 32-char uppercase hex string and are fully expandable.
\ifdefined\pdfmdfivesum
	\let\bingo@mdfive\pdfmdfivesum
\else
	\ifdefined\mdfivesum
		\let\bingo@mdfive\mdfivesum
	\else
		\def\bingo@mdfive#1{000000000000000000000000000000NO}% no primitive: degrade
	\fi
\fi

% Append a pre-expanded string to the accumulator (used for \labelcells, whose
% labels expand from \foreach variables).
\newcommand{\bingo@record@str}[1]{%
	\edef\bingo@tmp{\detokenize{#1};}%
	\expandafter\g@addto@macro\expandafter\bingo@content\expandafter{\bingo@tmp}%
}
% \bingo@record{col}{row}{content}: record one cell. The content is kept
% verbatim (detokenized, not evaluated) so math like \frac{d}{dx} is safe.
\newcommand{\bingo@record}[3]{%
	\edef\bingo@tmp{\detokenize{#1#2=#3};}%
	\expandafter\g@addto@macro\expandafter\bingo@content\expandafter{\bingo@tmp}%
}
% Grab the first six characters of the 32-char MD5 hex string.
\def\bingo@sixchars#1#2#3#4#5#6#7\relax{#1#2#3#4#5#6}
% Compute this card's ID from the accumulated cell contents.
\newcommand{\bingo@finalise}{%
	\edef\bingo@hash{\bingo@mdfive{\bingo@content}}%
	\xdef\bingo@cardid{\expandafter\bingo@sixchars\bingo@hash\relax}%
}

% --- install the header + footer --------------------------------------------
\newcommand{\bingo@footcenter}{\#\thebingocardno~\textbullet~\bingo@cardid}
\setlength{\headheight}{14pt}
\pagestyle{fancy}
\fancyhf{}
% Header: L = bingo title (e.g. "Exam 2 Bingo")  R = student name field
% (mirroring quiz/exam). Center is left empty -- the "Answer Key" indicator
% already lives in the body title block (\bingotitle).
\SetTeXLibHeader{\bfseries\GetBingoTitle}{}{Name:\ \underline{\hspace{2in}}}
\SetTeXLibFooter                    % L=\GetCourse | C (overridden) | R=\GetInstitution, 0.4pt rule
\fancyfoot[C]{\bingo@footcenter}    % override center: per-card verification ID
\TeXLibRuleBleed                    % symmetric rule length, matching didactic

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
	\bingo@record{#1}{#2}{#3}%
	\node at (\csname bingo@x@#1\endcsname, \csname bingo@y@#2\endcsname) {\Huge $#3$};%
}
% \bcelltext{col}{row}{content} — text-mode content
\newcommand{\bcelltext}[3]{%
	\bingo@record{#1}{#2}{#3}%
	\node at (\csname bingo@x@#1\endcsname, \csname bingo@y@#2\endcsname) {#3};%
}

% \begin{bingocard}[options] ... \end{bingocard}
\NewDocumentEnvironment{bingocard}{ O{} }
{%
	\stepcounter{bingocardno}%
	\gdef\bingo@content{}%
	\ifx\\#1\\\else\metasetup{#1}\fi
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
		\node at (2.5, 2.5) {\Huge $\GetBingoFreeSymbol$};%
}{%
	\end{tikzpicture}%
	\end{center}%
	\bingo@finalise
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
					\edef\bingo@lbl{\col\rw}\expandafter\bingo@record@str\expandafter{\bingo@lbl}%
					\node at ({\ci-0.5}, {5.5-\rw}) {\Huge \col\rw};%
				\fi
			\else
				\edef\bingo@lbl{\col\rw}\expandafter\bingo@record@str\expandafter{\bingo@lbl}%
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

\endinput
