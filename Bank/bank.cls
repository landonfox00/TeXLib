% bank.cls
% TeXLib problem-bank catalog / preview class.
% =============================================================================
% A standalone class for a thin PREVIEW WRAPPER that loads a bare-fragment bank
% and catalogs it -- NOT the class of the bank data file itself (a bank file must
% stay a bare fragment with no \documentclass so \loadbank can \input it into a
% quiz/exam; a nested \documentclass would break every \loadbank).
%
% Typical use (this is what "TeXLib: Bank Preview" generates for you):
%   %% !TeX program = lualatex
%   \documentclass{bank}
%   \begin{document}
%     \loadbank{bank}
%     \printbankcatalog
%   \end{document}
%
% bank.cls loads the same problem/solution rendering stack the assessment classes
% use (texlib-problembank + texlib-solutions), so \printbankcatalog typesets each
% problem exactly as an exam would -- but with a clean catalog page style instead
% of exam furniture (no name field, no running exam header). This subsumes the
% Sublime builder's old synthesized-quiz preview harness with a first-class class.
%
% ENGINE: lualatex (loads texlib-problembank -> \directlua problem_engine.lua).
% =============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bank}[2026/07/11 v1.0 TeXLib problem-bank catalog/preview]

% Forward every class option to exam (bank carries no options of its own).
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{exam}}
\ProcessOptions\relax
\LoadClass[11pt]{exam}

% A class-option value containing a comma splits into a stray "unused option";
% discard those leftovers (same guard as quiz.cls).
\AtEndOfClass{\global\let\@unusedoptionlist\@empty}

% Shared assessment setup (texlib-corepkg, texlib-build, course-metadata, common
% aux packages, unified problem/part labels) -- identical to quiz/autoexam.
\RequirePackage{texlib-assessment}

% The problem-bank engine + LaTeX glue: \loadbank, \begin{problem}, \getproblem,
% \printbankcatalog, ... (loads problem_engine.lua via \directlua).
\RequirePackage{texlib-problembank}

% Shared {solution} box + MC key frame, so cataloged problems render their
% solutions/answers the same way an answer key would.
\RequirePackage{texlib-solutions}

% Theorem environments + item formatting (a bank problem may use \encircle etc.).
\RequirePackage{texlib-thmenv}
\TeXLibStarredThms
\RequirePackage{texlib-itemfmt}

% Figures, matching the other classes.
\NewDocumentCommand{\fig}{ O{} m }{%
	\begin{figure}[!h]
		\centering
		\includegraphics[width=0.5\textwidth, height=0.35\textwidth,
							keepaspectratio, alt={#2}, #1]{Figures/#2}
	\end{figure}%
}

% Catalog page style: plain page numbers, no exam name-field / running furniture.
% (The exam class's \pagestyle{headandfoot} is replaced; the catalog is a
% reference listing, not a printable exam.)
\pagestyle{plain}

% Part labels: texlib-assessment sets \partlabel to \thequestion\thepartno. (e.g.
% "1a."), but a catalog has no active \question, so \thequestion is 0 and parts
% would render "0a. 0b.". Each catalog problem is already numbered ("1. <id>"),
% so label its parts self-containedly as "(a) (b)" -- no dependency on the unset
% question counter.
\AtBeginDocument{\renewcommand{\partlabel}{\textbf{(\thepartno)}}}

% A bank preview does NOT auto-load the coursemeta bank: the wrapper \loadbank's
% the bank it wants explicitly, and auto-loading would list unrelated problems.
% (quiz/autoexam auto-load via \pbank@load@coursebank; bank deliberately does not.)

% Catalog title. \bankcataloghead can be redefined by a wrapper; by default it
% names the course (if coursemeta resolved) and labels the listing.
\providecommand{\bankcataloghead}{%
	\begin{center}
		{\LARGE\bfseries Problem Bank Catalog}\par
		\vspace{0.3em}
		{\normalsize\itshape
			\GetCourse\ \GetCourseTitle\ — solutions shown for instructor perusal}\par
	\end{center}
	\vspace{0.5em}
}
\renewcommand{\maketitle}{\bankcataloghead}

% Course-metadata aliases come from course-metadata.sty.
\endinput
