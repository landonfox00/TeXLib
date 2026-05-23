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

\keys_define:nn { meta } {
	cell-size      .code:n  = { \dim_gset:Nn \g__bingo_cell_size_dim { #1 } },
	free-symbol    .tl_gset:N = \g__bingo_free_symbol_tl,
	show-headers   .choice:,
	show-headers / true   .code:n = { \bingo@headerstrue  },
	show-headers / false  .code:n = { \bingo@headersfalse },
	show-title     .choice:,
	show-title  / true    .code:n = { \bingo@titletrue  },
	show-title  / false   .code:n = { \bingo@titlefalse },
}

\NewExpandableDocumentCommand{\GetBingoFreeSymbol}{}{
	\tl_use:N \g__bingo_free_symbol_tl
}
\NewExpandableDocumentCommand{\GetBingoCellSize}{}{
	\dim_use:N \g__bingo_cell_size_dim
}

\ExplSyntaxOff

% ==============================================================================
% 4. PAGE STYLE
% ==============================================================================
\pagestyle{empty}

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

% \begin{bingocard}[options] ... \end{bingocard}
\NewDocumentEnvironment{bingocard}{ O{} }
{%
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

\endinput
