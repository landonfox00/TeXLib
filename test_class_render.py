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


def _poppler_pdftotext():
    for cand in (shutil.which("pdftotext"),
                 r"C:\texlive\2025\bin\windows\pdftotext.exe"):
        if not cand:
            continue
        try:
            p = subprocess.run([cand, "-v"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if "poppler" in ((p.stdout or "") + (p.stderr or "")).lower():
            return cand
    return None


PDFTOTEXT = _poppler_pdftotext()

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


def build(doc, module_cls, macro=""):
    """Build `doc` (a didactic/pset document string) after staging the shared
    payload + the given class. Returns normalized -layout text, or (None, err)."""
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
        shutil.copy2(os.path.join(TEXLIB_ROOT, *module_cls.split("/")),
                     os.path.join(tmp, os.path.basename(module_cls)))

        arg = f"{macro}\\input{{doc.tex}}" if macro else "doc.tex"
        rc = 0
        for _ in range(2):
            proc = subprocess.run(
                [PDFLATEX, "-interaction=nonstopmode", "-halt-on-error",
                 "-jobname=doc", arg],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120)
            rc = proc.returncode
        pdf = os.path.join(tmp, "doc.pdf")
        if rc != 0 or not os.path.exists(pdf):
            return None, "\n".join((proc.stdout or "").splitlines()[-8:])
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

    return 1 if _FAIL else 0


if __name__ == "__main__":
    rc = main()
    print("\n%d passed, %d failed" % (_PASS, _FAIL))
    sys.exit(rc)
