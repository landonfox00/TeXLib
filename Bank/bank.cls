%% bank.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-bank.cls. `bank' is too generic a name for a
%% library to claim: it collides with a user's own bank.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{bank} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-bank} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bank}[2026/08/25 v0.7.4 bank wrapper over texlib-bank (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-bank}}
\ProcessOptions\relax
\LoadClass{texlib-bank}
\endinput
