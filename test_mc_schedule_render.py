#!/usr/bin/env python3
r"""Real-build render checks for the MC answer-key (correctness) and the schedule
calendar grid (content) -- the last two eyeball-only visual surfaces.

  * MC answer key: an exam multiple-choice problem whose CORRECT option
    (\cchoice) is the THIRD choice. The key must mark "Answer: C" (the real
    correct choice), NOT "Answer: A" -- a key that marks the wrong choice is the
    worst kind of silent bug. Also asserts all choices + the solution render.
  * Schedule grid: a semester schedule must actually render its calendar content
    -- weekday headers, a \holiday label + its "No Class" cell, and the weekly
    Quiz / Exam markers -- not an empty or mislabeled grid.

Both are lualatex classes, so LUAINPUTS is pinned to the staged tree (a TEXMFHOME
install would otherwise shadow the engines -- the same hazard the synctex test
hit). Soft-skips (exit 0) without lualatex / poppler pdftotext.

Run:  python test_mc_schedule_render.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
LUALATEX = shutil.which("lualatex")


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
              r" course-title={Calculus I}, course-section=1001,"
              r" start-date=8-24, end-date=12-8, final-date=12-15,"
              r" final-time={9:45-11:45am}, lecture-days=MWF,"
              r" lecture-times={9:00-9:50am}, exam1-date={Sep 19, 2026}}" "\n")

MC_BANK = r"""\begin{problem}{mc-c}[topic=mc]
	Which value equals MCSTEMNEEDLE?
	\begin{choices}
		\choice WRONGA distractor.
		\choice WRONGB distractor.
		\cchoice RIGHTC correct one.
		\choice WRONGD distractor.
	\end{choices}
	\begin{solution} MCSOLNEEDLE because RIGHTC. \end{solution}
\end{problem}
"""
MC_EXAM = r"""\documentclass[exam-number=1]{autoexam}
\loadbank{mcbank.tex}
\begin{document}\maketitle
\begin{mcproblems}\problem{topic=mc}\end{mcproblems}
\end{document}
"""

SCHEDULE_DOC = r"""\documentclass[landscape=true, quiz-days=F]{schedule}
\begin{document}\maketitle
\begin{schedule}
	\holiday{9-7}{Labor Day}
	% Enough lecture days to span past Labor Day (Mon of week 3) so its cell
	% renders -- the grid only draws weeks it has content for.
	\section{2.1}
	\section{2.2}
	\section[2]{2.3}
	\section{2.5}
	\examreview
	\exam
	\section{2.7}
	\section{3.1}
\end{schedule}
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


def _stage(tmp, module_dirs):
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            shutil.copy2(src, os.path.join(tmp, entry))
    for md in module_dirs:
        mdir = os.path.join(TEXLIB_ROOT, md)
        for entry in os.listdir(mdir):
            src = os.path.join(mdir, entry)
            if not os.path.isfile(src):
                continue
            low = entry.lower()
            if (low.endswith("-template.tex") or entry in ("bank.tex",)
                    or low.endswith(".md") or low.startswith("test_")):
                continue
            if low.endswith((".sty", ".cls", ".lua", ".tex")):
                dest = os.path.join(tmp, entry)
                if not os.path.exists(dest):
                    shutil.copy2(src, dest)


def build(files, module_dirs, macro=""):
    tmp = tempfile.mkdtemp(prefix="texlib_mcsched_")
    try:
        for name, content in files:
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        with open(os.path.join(tmp, "coursemeta.tex"), "w", encoding="utf-8") as fh:
            fh.write(COURSEMETA)
        _stage(tmp, module_dirs)

        env = os.environ.copy()
        env["TEXINPUTS"] = ".;" + env.get("TEXINPUTS", "")
        env["LUAINPUTS"] = ".;" + env.get("LUAINPUTS", "")

        arg = f"{macro}\\input{{doc.tex}}" if macro else "doc.tex"
        rc = 0
        for _ in range(2):
            proc = subprocess.run(
                [LUALATEX, "-interaction=nonstopmode", "-halt-on-error",
                 "-shell-escape", "-jobname=doc", arg],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180, env=env)
            rc = proc.returncode
        pdf = os.path.join(tmp, "doc.pdf")
        if rc != 0 or not os.path.exists(pdf):
            return None, "\n".join((proc.stdout or "").splitlines()[-8:])
        text = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        return re.sub(r"[ \t]+", " ", text), ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    print("TeXLib MC answer-key + schedule grid render checks\n")
    if not LUALATEX or not PDFTOTEXT:
        print("  SKIP  need lualatex + poppler pdftotext.")
        return 0

    # --- MC answer key marks the CORRECT choice -----------------------------
    print("=== MC answer key: correct choice = C (\\cchoice at position 3) ===")
    text, err = build([("mcbank.tex", MC_BANK), ("doc.tex", MC_EXAM)],
                      ["Exams"], macro=r"\def\ShowSolutions{}")
    if text is None:
        check("MC exam builds (solutions)", False, err)
    else:
        check("MC exam builds (solutions)", True)
        check("all four choices render (A–D)",
              all(f"{c}. WRONG" in text or f"{c}. RIGHT" in text
                  for c in ["A", "B", "C", "D"]), text[:300])
        check("key marks the CORRECT answer: 'Answer: C'", "Answer: C" in text,
              "expected the \\cchoice (3rd) to be marked C")
        check("key does NOT mark 'Answer: A' (would be the wrong choice)",
              "Answer: A" not in text, "the key marked the wrong option")
        check("solution renders next to the key", "MCSOLNEEDLE" in text)

    # --- Schedule grid renders its calendar content -------------------------
    print("\n=== Schedule grid: headers + holiday + markers ===")
    text, err = build([("doc.tex", SCHEDULE_DOC)], ["Schedule"])
    if text is None:
        check("schedule builds", False, err)
    else:
        check("schedule builds", True)
        check("grid is non-empty", len(text.strip()) > 200)
        check("weekday header renders (FRI column)", "FRI" in text.upper(),
              "no weekday header found")
        check("holiday label renders ('Labor Day')", "Labor Day" in text)
        check("holiday cell shows 'No Class'", "No Class" in text)
        check("weekly quiz marker renders ('Quiz')", "Quiz" in text)
        check("exam marker renders ('Exam')", "Exam" in text)

    return 1 if _FAIL else 0


if __name__ == "__main__":
    rc = main()
    print("\n%d passed, %d failed" % (_PASS, _FAIL))
    sys.exit(rc)
