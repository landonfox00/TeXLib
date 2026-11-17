#!/usr/bin/env python3
r"""Solution and answer labels number themselves within a problem.

A lone lead-in or {solution} box is labeled "Solution." / "Answer." /
"Proof."; two or more of one kind in one problem are labeled "Solution 1.",
"Solution 2.", ... in document order. The totals go through the .aux, so the
labels settle on the second pass, like a cross-reference. This builds real
documents and reads the labels back with pdftotext:

  * didactic, default build: inline \solution / \answer / \ans / \pf in
    {example}s (each kind counted apart, \answer and \ans together), and
    force-shown {solution}* / {answer}* boxes, numbered per worked environment
    and restarting at the next one. The first pass is checked too: every label
    is unnumbered until the totals exist.
  * pset, solutions build: {solution} boxes numbered per {problem}.
  * quiz, solutions build: {solution} boxes numbered per \question.
  * autoexam, two versions, dual build (each student copy, then its key): the
    same per question, and a question's count starts again in the next copy,
    where the question numbers repeat.

The smoke fixture examples/fixtures/Notes/solution-numbering.tex asserts the
didactic labels on every push to main; this file adds the classes and the
first pass. Soft-skips (exit 0) without pdflatex, lualatex or a poppler
pdftotext.

Run:  python test_solution_numbering.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
PDFLATEX = shutil.which("pdflatex")
LUALATEX = shutil.which("lualatex")

sys.path.insert(0, os.path.join(TEXLIB_ROOT, "Sublime", "texlib"))
from texlib_buildspec import find_poppler  # noqa: E402

PDFTOTEXT = find_poppler()

COURSEMETA = (r"\metasetup{institution={Test U}, instructor={T}, season=Fall,"
              r" year=2026, course-subject=Math, course-number=181,"
              r" course-title={Calculus I}}" "\n")

FIXTURE = os.path.join(TEXLIB_ROOT, "examples", "fixtures", "Notes",
                       "solution-numbering.tex")

PSET_DOC = r"""\documentclass{pset}
\begin{document}
\begin{problem}
	First problem.
	\begin{solution} PSETTWOA \end{solution}
	\begin{solution} PSETTWOB \end{solution}
\end{problem}
\begin{problem}
	Second problem.
	\begin{solution} PSETONE \end{solution}
\end{problem}
\end{document}
"""

QUIZ_DOC = r"""\documentclass{quiz}
\begin{document}
\begin{questions}
\question First question.
	\begin{solution} QUIZTWOA \end{solution}
	\begin{solution} QUIZTWOB \end{solution}
\question Second question.
	\begin{solution} QUIZONE \end{solution}
\end{questions}
\end{document}
"""

EXAM_DOC = r"""\documentclass[exam-number=1]{autoexam}
\versions{A,B}
\begin{document}
\begin{questions}
\question First question.
	\begin{solution} EXAMTWOA \end{solution}
	\begin{solution} EXAMTWOB \end{solution}
\question Second question.
	\begin{solution} EXAMONE \end{solution}
\end{questions}
\end{document}
"""

_PASS = 0
_FAIL = 0


def check(label, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail)


def build(doc, module, engine, macro="", passes=2):
    """Build `doc` with the shared payload and `module`'s files staged beside
    it. Returns the PDF text, whitespace collapsed, or (None, error)."""
    tmp = tempfile.mkdtemp(prefix="texlib_solnum_")
    try:
        with open(os.path.join(tmp, "doc.tex"), "w", encoding="utf-8") as fh:
            fh.write(doc)
        with open(os.path.join(tmp, "coursemeta.tex"), "w", encoding="utf-8") as fh:
            fh.write(COURSEMETA)
        for entry in os.listdir(TEXLIB_ROOT):
            src = os.path.join(TEXLIB_ROOT, entry)
            if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
                shutil.copy2(src, os.path.join(tmp, entry))
        # The whole module directory: the bare class name is a wrapper around
        # texlib-<name>.cls, and the classes \input default instruction files.
        module_dir = os.path.join(TEXLIB_ROOT, module)
        for entry in os.listdir(module_dir):
            src = os.path.join(module_dir, entry)
            dst = os.path.join(tmp, entry)
            if (os.path.isfile(src) and not os.path.exists(dst)
                    and entry.lower().endswith((".sty", ".lua", ".cls", ".tex"))
                    and "template" not in entry and entry != "bank.tex"):
                shutil.copy2(src, dst)
        arg = f"{macro}\\input{{doc.tex}}" if macro else "doc.tex"
        cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", "-jobname=doc"]
        if engine == LUALATEX:
            cmd.append("-shell-escape")
        proc = None
        for _ in range(passes):
            proc = subprocess.run(cmd + [arg], cwd=tmp, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=300)
        pdf = os.path.join(tmp, "doc.pdf")
        if proc.returncode != 0 or not os.path.exists(pdf):
            return None, "\n".join((proc.stdout or "").splitlines()[-10:])
        text = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        return re.sub(r"\s+", " ", text), ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def expect_labels(where, text, pairs, absent=()):
    """Each (label, marker) pair must appear as "<label> <marker>"."""
    for label, marker in pairs:
        check(f"[{where}] {label} {marker}", f"{label} {marker}" in text,
              f"no '{label} {marker}' in: ...{text[:400]}")
    for needle in absent:
        check(f"[{where}] no '{needle}'", needle not in text,
              f"'{needle}' appeared")


# The didactic fixture's labels after the second pass, and after the first.
DIDACTIC_SETTLED = [
    ("Solution.", "LONESOLMARK"),
    ("Solution 1.", "TWOSOLAMARK"), ("Solution 2.", "TWOSOLBMARK"),
    ("Solution.", "MIXSOLMARK"),
    ("Answer 1.", "MIXANSAMARK"), ("Answer 2.", "MIXANSBMARK"),
    ("Proof.", "MIXPFMARK"),
    ("Solution 1.", "BOXAMARK"), ("Solution 2.", "BOXBMARK"),
    ("Answer.", "BOXANSMARK"),
    ("Solution.", "BOXRESTARTMARK"),
]
DIDACTIC_FIRST_PASS = [
    ("Solution.", "TWOSOLAMARK"), ("Solution.", "TWOSOLBMARK"),
    ("Answer.", "MIXANSAMARK"), ("Answer.", "MIXANSBMARK"),
    ("Solution.", "BOXAMARK"), ("Solution.", "BOXBMARK"),
]


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    print("TeXLib solution auto-numbering checks\n")
    if not (PDFLATEX and LUALATEX and PDFTOTEXT):
        print("  SKIP  need pdflatex, lualatex and poppler pdftotext.")
        return 0

    with open(FIXTURE, encoding="utf-8") as fh:
        didactic = fh.read()

    print("=== didactic: inline lead-ins and boxes, second pass ===")
    text, err = build(didactic, "Notes", PDFLATEX)
    check("didactic fixture builds", text is not None, err)
    if text is not None:
        expect_labels("didactic", text, DIDACTIC_SETTLED,
                      absent=("Solution 3.", "Proof 1.", "Answer 3."))

    print("\n=== didactic: first pass, nothing numbered yet ===")
    text, err = build(didactic, "Notes", PDFLATEX, passes=1)
    check("didactic fixture builds in one pass", text is not None, err)
    if text is not None:
        expect_labels("didactic pass 1", text, DIDACTIC_FIRST_PASS,
                      absent=("Solution 1.", "Answer 1."))

    print("\n=== pset: boxes numbered per {problem} ===")
    text, err = build(PSET_DOC, "Problem Sets", PDFLATEX, r"\def\ShowSolutions{}")
    check("pset builds", text is not None, err)
    if text is not None:
        expect_labels("pset", text, [("Solution 1.", "PSETTWOA"),
                                     ("Solution 2.", "PSETTWOB"),
                                     ("Solution.", "PSETONE")],
                      absent=("Solution 3.",))

    print("\n=== quiz: boxes numbered per \\question ===")
    text, err = build(QUIZ_DOC, "Quizzes", LUALATEX, r"\def\ShowKey{}")
    check("quiz builds", text is not None, err)
    if text is not None:
        expect_labels("quiz", text, [("Solution 1.", "QUIZTWOA"),
                                     ("Solution 2.", "QUIZTWOB"),
                                     ("Solution.", "QUIZONE")],
                      absent=("Solution 3.",))

    print("\n=== autoexam: per \\question, restarting in each copy ===")
    # \ShowSolutions is the dual build: A, A's key, B, B's key in one PDF. The
    # student copies step the count too, and print no header.
    text, err = build(EXAM_DOC, "Exams", LUALATEX, r"\def\ShowSolutions{}")
    check("autoexam builds", text is not None, err)
    if text is not None:
        expect_labels("autoexam", text, [("Solution 1.", "EXAMTWOA"),
                                         ("Solution 2.", "EXAMTWOB"),
                                         ("Solution.", "EXAMONE")],
                      absent=("Solution 3.", "Solution 4."))
        for marker, label in (("EXAMTWOA", "Solution 1."),
                              ("EXAMONE", "Solution.")):
            n = text.count(f"{label} {marker}")
            check(f"[autoexam] '{label} {marker}' in both copies", n == 2,
                  f"found {n} times, expected 2")

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
