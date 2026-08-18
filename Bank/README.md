# Bank — problem-bank catalog / preview class

`bank.cls` is a standalone class for a thin **preview wrapper** that loads a
bare-fragment problem bank and catalogs it with `\printbankcatalog`: a browsable
listing of every problem (running number, id, `[attrs]`, full stem, and solution
shown for instructor perusal).

```latex
%% !TeX program = lualatex
\documentclass{bank}
\begin{document}
  \loadbank{problem-bank}   % a bare \begin{problem} fragment (the same file exams \loadbank)
  \printbankcatalog         % or \printbankcatalog[topic=limits] to list one topic
\end{document}
```

**Naming:** the library's own sample fragments are `problem-bank.tex`, not
`bank.tex`. A bare `bank.tex` is still auto-discovered as a sibling — every
existing course folder uses it and nothing needs migrating — but the generic
name is what let the library's sample shadow a course's own bank, so new banks
should prefer `problem-bank.tex`. The classes and the Python tooling probe
`problem-bank.tex` first, `bank.tex` second.

**Important:** `\documentclass{bank}` goes on the *wrapper*, never on the bank
data file — a bank file must stay a bare fragment (no `\documentclass`) so
`\loadbank` can `\input` it into a quiz/exam. `bank-template.tex` is that wrapper.

`bank.cls` loads the same problem/solution rendering stack the assessment classes
use (`texlib-problembank` + `texlib-solutions`), so catalog problems typeset
exactly as an exam would, but with a clean catalog page style. It is the
first-class replacement for the Sublime builder's old synthesized-quiz preview
harness, and backs **TeXLib: Bank Preview** in the Sublime plugin.

**Engine:** lualatex (loads the `\directlua` problem engine).
