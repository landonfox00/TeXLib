#!/usr/bin/env python3
r"""
Build-mode leakage guard, parametrized across the assessment classes (C3).

smoke_test.py builds every module under each mode but checks EXPECT_TEXT by
module, so `--default` and `--solutions` are asserted against the identical token
list -- nothing there verifies that a flag GATES content: a flag silently
becoming a no-op, or a solution/answer/rubric LEAKING into a student copy (a
FERPA-adjacent failure), passes that suite untouched.

This closes that hole with a differential, mode-keyed REAL build, now for all
three assessment classes in ONE parametrized file (was exam-only):

  * autoexam + quiz -- share the bank + {problems}/{mcproblems} structure and the
    shared texlib-solutions box, so they reuse one fixture (one free-response
    problem with a \begin{solution}, one multiple-choice problem with choices + a
    \rubric). Asserts the solution tokens, the MC correct-answer badge, and the
    \rubric overlay each appear only under the right flag.
  * pset -- its own fixture ({problem} + a gated {solution} box). Asserts the
    solution tokens appear only when shown and that StudentMode emits the blank
    "Show your work here" answer box instead of the answer.

Flags are injected the way the builder injects them (\def\Show...{} before
\input), exercising the real compile-time path. Soft-skips (exit 0) if lualatex
or a poppler-flavored pdftotext is missing. Every build runs in its own temp dir.

Run:  python test_mode_effects.py    (exit 0 ok/skipped, 1 on a leak/no-op)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
LUALATEX = shutil.which("lualatex")


# --- Poppler pdftotext detection (mirrors test_synctex_integration.py) --------
def _find_poppler_pdftotext() -> str | None:
    candidates: list[str] = []
    which = shutil.which("pdftotext")
    if which:
        candidates.append(which)
    candidates.append(r"C:\texlive\2025\bin\windows\pdftotext.exe")
    for cand in candidates:
        try:
            proc = subprocess.run([cand, "-v"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if "poppler" in ((proc.stdout or "") + (proc.stderr or "")).lower():
            return cand
    return None


PDFTOTEXT = _find_poppler_pdftotext()


# --- Shared fixture pieces ----------------------------------------------------
COURSEMETA_TEX = r"""\metasetup{
	institution     = {University of Nevada, Reno},
	instructor      = {Test Instructor},
	season          = Fall,
	year            = 2026,
	course-subject  = Math,
	course-number   = 181,
	course-title    = {Calculus I},
	course-section  = 1001,
	course-room     = {DMSC 100},
	lecture-days    = MWF,
	lecture-times   = {9:00-9:50am},
	start-date      = 8-24,
	end-date        = 12-8,
	final-date      = 12-15,
	final-time      = {9:45-11:45am},
	exam1-date      = {Sep 19, 2026},
}
"""

# One FR (with \begin{solution} + \rubric) and one MC (choices + \rubric), for
# the bank-driven exam/quiz fixture.
BANK_TEX = r"""\begin{problem}{fr-one}[topic=fr]
	Evaluate STEMANCHORFR.
	\begin{solution}
	SOLLEAKFR is the answer.
	\rubric{4}{RUBRICLEAKFR criterion}
	\end{solution}
\end{problem}

\begin{problem}{mc-one}[topic=mc]
	Which is STEMANCHORMC?
	\begin{choices}
		\cchoice CHOICEVISIBLEA
		\choice CHOICEVISIBLEB
		\choice CHOICEVISIBLEC
	\end{choices}
	\begin{solution}
	SOLLEAKMC explains it.
	\rubric{2}{RUBRICLEAKMC criterion}
	\end{solution}
\end{problem}
"""

EXAM_TEX = r"""\documentclass[exam-number=1]{autoexam}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem{topic=fr}
\end{problems}
\begin{mcproblems}
	\problem{topic=mc}
\end{mcproblems}
\end{document}
"""

# Quiz shares the bank + section structure; quiz auto-loads the sibling bank.tex
# at \begin{document}, so the fixture does NOT \loadbank (that would double-load).
QUIZ_TEX = r"""\documentclass{quiz}
\begin{document}
\maketitle
\begin{problems}
	\problem{topic=fr}
\end{problems}
\begin{mcproblems}
	\problem{topic=mc}
\end{mcproblems}
\end{document}
"""

# pset: its own structure. A {problem} with a gated {solution}; no MC, no bank.
PSET_TEX = r"""\documentclass{pset}
\begin{document}
\begin{problem}
	Evaluate STEMANCHORFR.
	\begin{solution}
	SOLLEAKFR is the answer.
	\end{solution}
\end{problem}
\end{document}
"""

STEM_NEEDLES_MC = ["STEMANCHORFR", "STEMANCHORMC"]
STEM_NEEDLES_FR = ["STEMANCHORFR"]
SOLUTION_NEEDLES = ["SOLLEAKFR", "SOLLEAKMC"]
SOLUTION_NEEDLES_FR = ["SOLLEAKFR"]
RUBRIC_NEEDLES = ["RUBRICLEAKFR", "RUBRICLEAKMC"]
ANSWER_BADGE_RE = re.compile(r"Answer:\s*[A-E]\b")
STUDENT_BOX_RE = re.compile(r"Show your work here")


# --- Per-class mode tables ----------------------------------------------------
# checks: which signals to assert -- sol (solution tokens), ans (MC badge),
# rub (rubric overlay), blank (pset student answer box present).
EXAM_QUIZ_MODES = [
    ("default",   "",                 dict(sol=False, ans=False, rub=False)),
    ("StudentMode", r"\def\StudentMode{}", dict(sol=False, ans=False, rub=False)),
    ("ShowKey",   r"\def\ShowKey{}",   dict(sol=True,  ans=True,  rub=False)),
    ("ShowSolutions", r"\def\ShowSolutions{}", dict(sol=True, ans=True, rub=False)),
    ("ShowSolutions+ShowRubric", r"\def\ShowSolutions{}\def\ShowRubric{}",
     dict(sol=True, ans=True, rub=True)),
    ("ShowRubric", r"\def\ShowRubric{}", dict(sol=False, ans=False, rub=False)),
]

PSET_MODES = [
    ("default",     "",                    dict(sol=False, blank=False)),
    ("StudentMode", r"\def\StudentMode{}", dict(sol=False, blank=True)),
    ("ShowKey",     r"\def\ShowKey{}",     dict(sol=True,  blank=False)),
    ("ShowSolutions", r"\def\ShowSolutions{}", dict(sol=True, blank=False)),
]

CLASSES = [
    dict(name="autoexam", module_dir="Exams", doc=EXAM_TEX, with_bank=True,
         skip=("autoexam-template.tex", "bank.tex"), modes=EXAM_QUIZ_MODES,
         stems=STEM_NEEDLES_MC, sols=SOLUTION_NEEDLES, kind="examquiz"),
    dict(name="quiz", module_dir="Quizzes", doc=QUIZ_TEX, with_bank=True,
         skip=("quiz-template.tex", "bank.tex"), modes=EXAM_QUIZ_MODES,
         stems=STEM_NEEDLES_MC, sols=SOLUTION_NEEDLES, kind="examquiz"),
    dict(name="pset", module_dir="Problem Sets", doc=PSET_TEX, with_bank=False,
         skip=("pset-template.tex",), modes=PSET_MODES,
         stems=STEM_NEEDLES_FR, sols=SOLUTION_NEEDLES_FR, kind="pset"),
]


# --- Pass/fail bookkeeping ----------------------------------------------------
_PASS = 0
_FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def _norm(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _copy_build_inputs(tmp: str, module_dir: str, skip: tuple) -> None:
    """Populate the isolated build dir the comma-safe way (copy shared files into
    cwd rather than adding the comma-bearing OneDrive path to TEXINPUTS)."""
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            dest = os.path.join(tmp, entry)
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
    mod = os.path.join(TEXLIB_ROOT, module_dir)
    for entry in os.listdir(mod):
        src = os.path.join(mod, entry)
        if not os.path.isfile(src):
            continue
        if entry in skip or entry.lower().endswith(".md"):
            continue
        dest = os.path.join(tmp, entry)
        if not os.path.exists(dest):
            shutil.copy2(src, dest)


def build(cfg: dict, macro: str, timeout: int = 180) -> tuple[str | None, str]:
    tmp = tempfile.mkdtemp(prefix="texlib_modefx_")
    try:
        files = [("coursemeta.tex", COURSEMETA_TEX), ("doc.tex", cfg["doc"])]
        if cfg["with_bank"]:
            files.append(("bank.tex", BANK_TEX))
        for name, content in files:
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        _copy_build_inputs(tmp, cfg["module_dir"], cfg["skip"])

        arg = f"{macro}\\input{{doc.tex}}" if macro else "doc.tex"
        cmd = [LUALATEX, "-interaction=nonstopmode", "-halt-on-error",
               "-shell-escape", "-jobname=doc", arg]
        rc = 0
        for _ in range(2):
            proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            rc = proc.returncode
        pdf = os.path.join(tmp, "doc.pdf")
        if rc != 0 or not os.path.exists(pdf):
            tail = "\n".join((proc.stdout or "").splitlines()[-8:])
            return None, f"lualatex exit={rc}, pdf={'yes' if os.path.exists(pdf) else 'no'}\n{tail}"
        raw = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=60).stdout
        return _norm(raw or ""), ""
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mismatch(kind: str, needles: list[str], text: str, expected: bool) -> str:
    present = [n for n in needles if n in text]
    if expected:
        return f"expected {kind} shown, missing: {[n for n in needles if n not in text]}"
    return f"LEAK: {kind} appeared in a build that must hide it: {present}"


def run_class(cfg: dict) -> None:
    print(f"\n#### class: {cfg['name']} ####")
    for label, macro, expect in cfg["modes"]:
        print(f"=== {cfg['name']} / {label} ({macro or 'no flags'}) ===")
        text, err = build(cfg, macro)
        if text is None:
            check(f"[{cfg['name']}/{label}] builds + extracts", False, err)
            continue
        stems_ok = all(n in text for n in cfg["stems"])
        check(f"[{cfg['name']}/{label}] fixture rendered (stems present)", stems_ok,
              "stem anchors missing -- build or extraction broken")
        if not stems_ok:
            continue

        sol = any(n in text for n in cfg["sols"])
        check(f"[{cfg['name']}/{label}] solution {'present' if expect['sol'] else 'absent'}",
              sol == expect["sol"], _mismatch("solution", cfg["sols"], text, expect["sol"]))

        if cfg["kind"] == "examquiz":
            ans = bool(ANSWER_BADGE_RE.search(text))
            check(f"[{cfg['name']}/{label}] MC answer letter {'present' if expect['ans'] else 'absent'}",
                  ans == expect["ans"],
                  f"badge {'matched' if ans else 'no match'}, expected {expect['ans']}")
            rub = any(n in text for n in RUBRIC_NEEDLES)
            check(f"[{cfg['name']}/{label}] rubric {'present' if expect['rub'] else 'absent'}",
                  rub == expect["rub"], _mismatch("rubric", RUBRIC_NEEDLES, text, expect["rub"]))
        else:  # pset: check the StudentMode blank answer box
            blank = bool(STUDENT_BOX_RE.search(text))
            check(f"[{cfg['name']}/{label}] student blank box {'present' if expect['blank'] else 'absent'}",
                  blank == expect["blank"],
                  f"'Show your work here' {'found' if blank else 'absent'}, expected {expect['blank']}")
        print()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    print("TeXLib build-mode leakage guard (exam / quiz / pset)\n")
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext.")
        return 0
    for cfg in CLASSES:
        run_class(cfg)
    print(f"\n{_PASS} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
