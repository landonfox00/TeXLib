%% bingo.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-bingo.cls. `bingo' is too generic a name for a
%% library to claim: it collides with a user's own bingo.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{bingo} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-bingo} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bingo}[2026/08/25 v0.7.4 bingo wrapper over texlib-bingo (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-bingo}}
\ProcessOptions\relax
\LoadClass{texlib-bingo}
\endinput
