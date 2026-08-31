%% autoexam.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-autoexam.cls. `autoexam' is too generic a name for a
%% library to claim: it collides with a user's own autoexam.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{autoexam} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-autoexam} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{autoexam}[2026/08/25 v0.7.4 autoexam wrapper over texlib-autoexam (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-autoexam}}
\ProcessOptions\relax
\LoadClass{texlib-autoexam}
\endinput
