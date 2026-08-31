%% schedule.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-schedule.cls. `schedule' is too generic a name for a
%% library to claim: it collides with a user's own schedule.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{schedule} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-schedule} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{schedule}[2026/08/25 v0.7.4 schedule wrapper over texlib-schedule (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-schedule}}
\ProcessOptions\relax
\LoadClass{texlib-schedule}
\endinput
