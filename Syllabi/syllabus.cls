%% syllabus.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-syllabus.cls. `syllabus' is too generic a name for a
%% library to claim: it collides with a user's own syllabus.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{syllabus} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-syllabus} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{syllabus}[2026/08/31 v0.8.0 syllabus wrapper over texlib-syllabus (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-syllabus}}
\ProcessOptions\relax
\LoadClass{texlib-syllabus}
\endinput
