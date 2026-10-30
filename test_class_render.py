#!/usr/bin/env python3
r"""Real-build render checks for the boxed-theorem taxonomy (C1) and the shared
solution-box header (C2).

The mode-effects guard proves the solution BODY gates correctly, and the plugin
tests cover scan logic -- but nothing asserted that the theorem environments,
their short aliases, and the shared solution header actually RENDER correctly
(labels + a shared counter that numbers). That is the same class of gap that let
the bank part-label "0a/0b" bug through. This builds real documents and asserts:

  * didactic: canonical envs render "Theorem 1.1 / Lemma 1.2 / ..." with a
    SECTION-based SHARED counter (a broken counter would misnumber, like 0a/0b);
  * short aliases resolve to the correct environment -- an aliases-ONLY document
    still renders Theorem / Corollary / Lemma / Definition / Proposition labels
    (so \thm -> Theorem, \cor -> Corollary, ...);
  * pset: flat numbering + the shared solution box renders the "Solution." header
    (the C2 \texlibsolheader macro) in a shown solution.

Soft-skips (exit 0) without pdflatex / poppler pdftotext. Builds in temp dirs.

Run:  python test_class_render.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
PDFLATEX = shutil.which("pdflatex")


# The poppler lookup is declared once, in Sublime/texlib/texlib_buildspec.py.
sys.path.insert(0, os.path.join(TEXLIB_ROOT, "Sublime", "texlib"))
from texlib_buildspec import find_poppler  # noqa: E402

PDFTOTEXT = find_poppler()

COURSEMETA = (r"\metasetup{institution={Test U}, instructor={T}, season=Fall,"
              r" year=2026, course-subject=Math, course-number=181,"
              r" course-title={Calculus I}}" "\n")

# didactic: canonical envs, section-based shared counter.
DIDACTIC_LABELS = r"""\documentclass{didactic}
\begin{document}
\section{Foundations}
\begin{theorem} bounded monotone converges. \end{theorem}
\begin{lemma} convergent implies bounded. \end{lemma}
\begin{corollary} it follows. \end{corollary}
\begin{definition} a Cauchy sequence. \end{definition}
\begin{example} the sequence one over n. \end{example}
\end{document}
"""

# didactic: ONLY aliases -- the labels below can only come from the aliases.
DIDACTIC_ALIASES = r"""\documentclass{didactic}
\begin{document}
\section{Aliased}
\begin{thm} ATHM via thm. \end{thm}
\begin{cor} ACOR via cor. \end{cor}
\begin{lem} ALEM via lem. \end{lem}
\begin{defn} ADEF via defn. \end{defn}
\begin{prop} APROP via prop. \end{prop}
\end{document}
"""

# pset: flat numbering + an alias theorem + a shown solution (C2 header).
PSET_DOC = r"""\documentclass{pset}
\begin{document}
\begin{thm} PSETTHM statement. \end{thm}
\begin{problem}
	Evaluate the limit.
	\begin{solution}
	PSETSOLBODY the worked answer.
	\end{solution}
\end{problem}
\end{document}
"""

# Six defects found by the 2026-10-30 audit, each a one-page document. The
# course-subject class option overrides coursemeta's "Math", so the cover must
# read STAT; \rubrics is the source-level twin of \ShowRubric.
EXAM_COVER = r"""\documentclass[course-subject=STAT, exam-number=1]{autoexam}
\rubrics
\begin{document}\maketitle\end{document}
"""
PSET_NO_DUE = r"""\documentclass{pset}
\begin{document}\maketitle PSETNODUE\end{document}
"""
PSET_DUE = r"""\documentclass[pset-due={Oct 31}]{pset}
\begin{document}\maketitle PSETDUE\end{document}
"""
SYLL_IFSET = r"""\documentclass[class-time={MWF 9}]{syllabus}
\begin{document}
SET=[\IfSyllSet{class_time}{yes}{no}][\IfSyllSet{office_hours}{yes}{no}]
\end{document}
"""
DRAFT_SOURCE = r"""\documentclass{didactic}
\drafts
\begin{document}Body text.\end{document}
"""
PLAIN_NOTES = r"""\documentclass{didactic}
\begin{document}Body text.\end{document}
"""
TIKZEXT_LUA = r"""\documentclass{article}
\usepackage{texlib-tikzexternal}
\begin{document}TIKZEXTLOADS\end{document}
"""

LUALATEX = shutil.which("lualatex")
PDFTOPPM = shutil.which("pdftoppm")

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


def _ink(pdf):
    """Inked pixels on page 1 at 20 dpi. The draft watermark is rotated 45
    degrees, and pdftotext cannot be relied on to extract rotated text. It is
    also only 12% grey, so anything short of white counts as ink."""
    out = subprocess.run([PDFTOPPM, "-r", "20", "-gray", "-f", "1", "-l", "1",
                          pdf], capture_output=True).stdout
    # Binary PGM: "P5", width, height, maxval, then one byte per pixel.
    fields = out.split(maxsplit=4)
    return sum(1 for b in fields[4] if b < 250) if len(fields) == 5 else -1


def build(doc, module_cls, macro="", engine=None, ink=False):
    """Build `doc` (a document string) after staging the shared payload + the
    given class. Returns normalized -layout text, or (None, err). With
    ink=True the text is replaced by the dark-pixel count of page 1."""
    tmp = tempfile.mkdtemp(prefix="texlib_clsrender_")
    try:
        with open(os.path.join(tmp, "doc.tex"), "w", encoding="utf-8") as fh:
            fh.write(doc)
        with open(os.path.join(tmp, "coursemeta.tex"), "w", encoding="utf-8") as fh:
            fh.write(COURSEMETA)
        for entry in os.listdir(TEXLIB_ROOT):
            src = os.path.join(TEXLIB_ROOT, entry)
            if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
                shutil.copy2(src, os.path.join(tmp, entry))
        # Copy the class's whole module directory, not just the named .cls.
        # Since the texlib- rename the bare name is a two-line wrapper around
        # texlib-<name>.cls, so staging it alone gives a build that dies at the
        # wrapper's own \endinput -- the real class is not there. The sibling
        # .lua engines in the same directory were always needed too; naming one
        # file only ever worked because the classes that need them were not
        # exercised here.
        module_dir = os.path.join(TEXLIB_ROOT,
                                  os.path.dirname(module_cls.replace("/", os.sep)))
        # Its .tex files too: pset and autoexam \input a default instructions
        # file (pset-instructions.tex, autoexam-instructions.tex) from there.
        for entry in os.listdir(module_dir):
            src = os.path.join(module_dir, entry)
            dst = os.path.join(tmp, entry)
            if (os.path.isfile(src) and not os.path.exists(dst)
                    and entry.lower().endswith((".sty", ".lua", ".cls", ".tex"))):
                shutil.copy2(src, dst)

        arg = f"{macro}\\input{{doc.tex}}" if macro else "doc.tex"
        rc = 0
        for _ in range(2):
            proc = subprocess.run(
                [engine or PDFLATEX, "-interaction=nonstopmode", "-halt-on-error",
                 "-jobname=doc", arg],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120)
            rc = proc.returncode
        pdf = os.path.join(tmp, "doc.pdf")
        if rc != 0 or not os.path.exists(pdf):
            return None, "\n".join((proc.stdout or "").splitlines()[-8:])
        if ink:
            return _ink(pdf), ""
        text = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        return re.sub(r"\s+", " ", text), ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    print("TeXLib class render checks (C1 theorems / aliases / numbering, C2 header)\n")
    if not PDFLATEX or not PDFTOTEXT:
        print("  SKIP  need pdflatex + poppler pdftotext.")
        return 0

    # --- C1: canonical labels + section-based shared counter ----------------
    print("=== didactic: labels + shared section counter ===")
    text, err = build(DIDACTIC_LABELS, "Notes/didactic.cls")
    if text is None:
        check("didactic labels doc builds", False, err)
    else:
        check("didactic labels doc builds", True)
        for lbl, num in [("Theorem", "1.1"), ("Lemma", "1.2"),
                         ("Corollary", "1.3"), ("Definition", "1.4"),
                         ("Example", "1.5")]:
            check(f"{lbl} renders at shared-counter {num}",
                  f"{lbl} {num}" in text, f"missing '{lbl} {num}' in: {text[:200]}")

    # --- C1: aliases resolve to the correct environment ---------------------
    print("\n=== didactic: aliases-only -> correct labels ===")
    text, err = build(DIDACTIC_ALIASES, "Notes/didactic.cls")
    if text is None:
        check("didactic aliases doc builds", False, err)
    else:
        check("didactic aliases doc builds", True)
        for alias, lbl in [("thm", "Theorem"), ("cor", "Corollary"),
                           ("lem", "Lemma"), ("defn", "Definition"),
                           ("prop", "Proposition")]:
            check(f"\\{alias} -> {lbl} label renders", lbl in text,
                  f"'{lbl}' absent (alias \\{alias} did not map correctly)")

    # --- pset: flat numbering + C2 solution header --------------------------
    print("\n=== pset: alias theorem + shared solution header (C2) ===")
    text, err = build(PSET_DOC, "Problem Sets/pset.cls", macro=r"\def\ShowSolutions{}")
    if text is None:
        check("pset doc builds (solutions mode)", False, err)
    else:
        check("pset doc builds (solutions mode)", True)
        check("\\thm alias renders a Theorem in pset", "Theorem" in text)
        check("pset theorem numbers flat (Theorem 1, not 1.1)",
              "Theorem 1" in text and "Theorem 1.1" not in text,
              "expected flat 'Theorem 1'")
        check("C2 shared solution header 'Solution.' renders",
              "Solution." in text and "PSETSOLBODY" in text,
              "solution header or body missing")

    # --- accessibility: \fig alt-text hook compiles (all three forms) -------
    print("\n=== \\fig alt-text (accessibility hook) compiles ===")
    figdoc = ("\\documentclass{didactic}\n"
              "\\renewcommand{\\figdir}{}\n"  # example-image ships with TeX Live
              "\\begin{document}\n"
              "\\fig[A parabola]{example-image}\n"        # alt from caption
              "\\fig[][alt={explicit alt}]{example-image}\n"  # explicit override
              "\\fig{example-image}\n"                     # alt falls back to filename
              "\\end{document}\n")
    text, err = build(figdoc, "Notes/didactic.cls")
    check("didactic \\fig with alt-text (caption / explicit / filename) compiles",
          text is not None, err)

    # --- metadata and build switches the 2026-10-30 audit found unwired -----
    print("\n=== pset due line, \\IfSyllSet, source-level \\drafts ===")
    text, err = build(PSET_NO_DUE, "Problem Sets/pset.cls")
    check("pset with no due date prints no 'Due:' line",
          text is not None and "PSETNODUE" in text and "Due:" not in text,
          err or (text or "")[:200])
    text, err = build(PSET_DUE, "Problem Sets/pset.cls")
    check("pset with pset-due prints 'Due: Oct 31'",
          text is not None and "Due: Oct 31" in text, err or (text or "")[:200])
    text, err = build(SYLL_IFSET, "Syllabi/syllabus.cls")
    check("\\IfSyllSet answers from coursemeta (set: yes, unset: no)",
          text is not None and "SET=[yes][no]" in text, err or (text or "")[:200])
    if PDFTOPPM:
        plain, err1 = build(PLAIN_NOTES, "Notes/didactic.cls", ink=True)
        drafted, err2 = build(DRAFT_SOURCE, "Notes/didactic.cls", ink=True)
        ok = plain is not None and drafted is not None and drafted > 2 * plain > 0
        check("\\drafts in the preamble draws the DRAFT watermark", ok,
              err1 or err2 or f"dark pixels: plain {plain}, \\drafts {drafted}")
    else:
        print("  SKIP  \\drafts watermark: needs poppler pdftoppm")

    if LUALATEX:
        print("\n=== autoexam cover, tikzexternal under LuaLaTeX ===")
        text, err = build(EXAM_COVER, "Exams/autoexam.cls",
                          macro=r"\def\ShowKey{}", engine=LUALATEX)
        if text is None:
            check("autoexam cover doc builds", False, err)
        else:
            check("exam cover names the course subject (STAT 181, not Math 181)",
                  "STAT 181" in text and "Math 181" not in text, text[:200])
            check("source-level \\rubrics reaches the key cover",
                  "Solutions and Rubrics" in text, text[:200])
        text, err = build(TIKZEXT_LUA, "texlib-tikzexternal.sty", engine=LUALATEX)
        check("texlib-tikzexternal loads under LuaLaTeX",
              text is not None and "TIKZEXTLOADS" in text, err)
    else:
        print("  SKIP  autoexam / tikzexternal checks: need lualatex")

    return 1 if _FAIL else 0


if __name__ == "__main__":
    rc = main()
    print("\n%d passed, %d failed" % (_PASS, _FAIL))
    sys.exit(rc)
