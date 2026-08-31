%% pset.cls -- compatibility wrapper (TeXLib)
%% ============================================================================
%% The class moved to texlib-pset.cls. `pset' is too generic a name for a
%% library to claim: it collides with a user's own pset.cls sitting next to
%% their document, and CTAN will not allocate it.
%%
%% This wrapper exists so the rename costs nothing. Every document that says
%% \documentclass{pset} keeps working, unchanged, with identical output.
%% Prefer \documentclass{texlib-pset} in new documents.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{pset}[2026/08/31 v0.8.0 pset wrapper over texlib-pset (TeXLib)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{texlib-pset}}
\ProcessOptions\relax
\LoadClass{texlib-pset}
\endinput
