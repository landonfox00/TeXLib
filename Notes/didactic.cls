%% didactic.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-didactic.cls. `didactic' is too generic a name for a
%% library to claim: it collides with a user's own didactic.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{didactic} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-didactic} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{didactic}[2026/08/31 v0.8.0 didactic wrapper over texlib-didactic (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-didactic}}
\ProcessOptions\relax
\LoadClass{texlib-didactic}
\endinput
