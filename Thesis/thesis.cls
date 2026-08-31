% thesis.cls — UNR accessible thesis / dissertation (TeXLib compatibility class)
% ============================================================================
% The class split in two: texlib-thesis.cls holds the institution-neutral
% machinery (the tagged-PDF stack, trivlist-free theorem environments, the
% MathML intent helper, front matter, degree/committee metadata) and
% Thesis/profiles/unr.tex holds the parts UNR's Graduate School dictates (the
% title page, the committee-approval page, the margin and spacing figures).
%
% This file exists so that split costs nothing. Every document that says
%
%     \documentclass{thesis}
%
% -- both shipped templates, the scenario pack, the builder test, and any real
% dissertation already written against it -- keeps working unchanged, on the
% same pages, with the same output. It is a two-line wrapper, not a second
% implementation: there is nothing here to drift.
%
% New documents should prefer
%
%     \documentclass[profile=unr]{texlib-thesis}
%
% which says what it means. `thesis' is also a name no library should really
% own -- it is exactly the kind of generic .cls name that collides with a
% user's own file, and it is unpublishable on CTAN -- so the long-run direction
% is for this wrapper to be the only thing still called that.
%
% Options pass straight through, so [twoside] and friends behave as before.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{thesis}[2026/08/25 v0.7.4 UNR thesis wrapper over texlib-thesis (TeXLib)]

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-thesis}}
\ProcessOptions\relax
\LoadClass[profile=unr]{texlib-thesis}

\endinput
