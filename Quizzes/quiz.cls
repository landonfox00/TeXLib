%% quiz.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-quiz.cls. `quiz' is too generic a name for a
%% library to claim: it collides with a user's own quiz.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{quiz} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-quiz} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{quiz}[2026/08/31 v0.8.0 quiz wrapper over texlib-quiz (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-quiz}}
\ProcessOptions\relax
\LoadClass{texlib-quiz}
\endinput
