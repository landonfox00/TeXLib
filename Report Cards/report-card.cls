%% report-card.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-report-card.cls. `report-card' is too generic a name for a
%% library to claim: it collides with a user's own report-card.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{report-card} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-report-card} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{report-card}[2026/08/31 v0.8.0 report-card wrapper over texlib-report-card (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-report-card}}
\ProcessOptions\relax
\LoadClass{texlib-report-card}
\endinput
