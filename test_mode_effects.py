#!/usr/bin/env python3
"""
Build-mode leakage guard: prove the assessment flags actually CHANGE output.

smoke_test.py builds every module under each mode (\\StudentMode, \\ShowKey,
\\ShowSolutions, \\ShowRubric) but checks EXPECT_TEXT/EXPECT_ABSENT by module
only -- so `Exams --default` and `Exams --solutions` are asserted against the
identical token list. Nothing there verifies that a flag gates content: a flag
silently becoming a no-op -- or, worse, a solution/answer/rubric LEAKING into a
student copy (a FERPA-adjacent failure) -- passes that suite untouched.

This test closes that hole with a differential, mode-keyed real build. It
compiles ONE self-contained autoexam fixture (one free-response problem with a
\\begin{solution}, one multiple-choice problem with choices + a \\rubric) once
per flag combination, extracts the rendered text, and asserts that each build
flag reveals exactly what it should and nothing it shouldn't:

  * a solution token is ABSENT from every student-facing build and PRESENT once
    solutions are shown,
  * the multiple-choice correct-answer badge (the boxed answer LETTER after
    "Answer:") is ABSENT from a student build and PRESENT in the answers build,
  * a \\rubric token overlays only when rubrics are shown, and never otherwise.

The flags are injected the way the builder injects them -- \\def\\Show...{} on the
command line before \\input -- so this exercises the real compile-time path, not
a source-level \\solutions in the document.

IMPORTANT (autoexam specifics, verified empirically 2026-07-10): for the exam
class the answer key is produced by \\ShowSolutions (which drives the class's
student+instructor dual-copy loop and sets \\ifsolutions for the instructor
copy). \\ShowKey sets \\ifkey, but autoexam.cls never consults \\ifkey, so
\\def\\ShowKey{} is a NO-OP for this class and yields a student-identical body.
The {solution}/{partsolution} boxes, the side-by-side multiple-choice key, and
the \\rubric overlay (all in texlib-solutions.sty) gate on \\ifsolutions, not
\\ifkey. The mode table below pins that reality: if \\ShowKey is ever wired to
reveal answers for exams, the ShowKey row starts failing and asks to be updated.

Soft-skips (exit 0) if lualatex or a poppler-flavored pdftotext is missing,
matching test_synctex_integration.py / test_biber_integration.py's
degrade-don't-fail convention. Every build runs in its own temp dir (all aux
lands there and is removed), so nothing touches the real module folders.

Run:  python test_mode_effects.py     (exit 0 ok/skipped, 1 on a leak/no-op)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
EXAMS_DIR = os.path.join(TEXLIB_ROOT, "Exams")

LUALATEX = shutil.which("lualatex")


# --- Poppler pdftotext detection (mirrors test_synctex_integration.py) --------
def _find_poppler_pdftotext() -> str | None:
    """A poppler-flavored pdftotext, NOT Git-for-Windows' xpdfreader build.

    On some Windows dev setups Git ships its own xpdf pdftotext earlier on PATH;
    it silently mangles layout differently from poppler. Probe candidates and
    pick the first whose version banner mentions poppler, so a green local run
    means the same thing as the poppler-utils CI container.
    """
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


# --- Fixture: metadata from examples/Math181-Fall2026/, one FR + one MC --------
# Distinctive ALL-CAPS needles (never real words) so a substring match can't
# collide with boilerplate. STEMANCHOR* render in EVERY build (a sanity anchor
# that the doc typeset and extraction works); SOLLEAK*/RUBRICLEAK* are the
# leakage tokens that must appear only when their flag is set.
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

# No \versions: default/student builds are a single student copy (nothing to
# leak from), while \ShowSolutions drives the class's dual student+instructor
# loop so the instructor copy carries the revealed content.
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

STEM_NEEDLES = ["STEMANCHORFR", "STEMANCHORMC"]
SOLUTION_NEEDLES = ["SOLLEAKFR", "SOLLEAKMC"]
RUBRIC_NEEDLES = ["RUBRICLEAKFR", "RUBRICLEAKMC"]
# The correct-answer badge is the boxed answer LETTER printed after "Answer:"
# in an instructor build; a student build prints "Answer:" then a blank rule
# (no letter). \cchoice is authored first and the fixture never \shuffle-s, so
# the correct option is A -- but any A-E after "Answer:" means "the key letter
# was revealed", which is the leakage-relevant signal.
ANSWER_BADGE_RE = re.compile(r"Answer:\s*[A-E]\b")


# --- Mode table: (label, injected macros, expected reveals) -------------------
# sol = solution tokens shown, ans = MC answer letter shown, rub = rubric shown.
MODES = [
    ("default",                 "",
     dict(sol=False, ans=False, rub=False)),
    ("StudentMode",             r"\def\StudentMode{}",
     dict(sol=False, ans=False, rub=False)),
    # \ShowKey is a no-op for autoexam (see module docstring); pins that reality.
    ("ShowKey",                 r"\def\ShowKey{}",
     dict(sol=False, ans=False, rub=False)),
    ("ShowSolutions",           r"\def\ShowSolutions{}",
     dict(sol=True,  ans=True,  rub=False)),
    ("ShowSolutions+ShowRubric", r"\def\ShowSolutions{}\def\ShowRubric{}",
     dict(sol=True,  ans=True,  rub=True)),
    # \ShowRubric alone reveals nothing: the rubric overlays inside a SHOWN
    # solution, so with solutions hidden there is no box to overlay onto.
    ("ShowRubric",              r"\def\ShowRubric{}",
     dict(sol=False, ans=False, rub=False)),
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


# --- Build + extract ----------------------------------------------------------
def _norm(text: str) -> str:
    """Extraction-proof the text: join words TeX hyphenated across a line break
    (the narrow 4.5cm rubric overlay wraps 'RUBRICLEAKFR' as 'RUBRICLEAK-\\nFR'),
    then collapse remaining whitespace so a needle survives -layout column
    padding."""
    text = re.sub(r"-\s*\n\s*", "", text)   # dehyphenate line breaks first
    text = re.sub(r"\s+", " ", text)        # then flatten remaining whitespace
    return text


def _copy_build_inputs(tmp: str) -> None:
    """Populate an isolated build dir the comma-safe way (a TEXINPUTS entry with
    a comma -- the OneDrive '...Nevada, Reno...' path has one -- is silently
    unsearchable by kpathsea, so we copy shared files into cwd instead, mirroring
    smoke_test.py). Fixture files are written by the caller first and win."""
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            dest = os.path.join(tmp, entry)
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
    # The exam class and its default includes (autoexam-instructions.tex, ...),
    # skipping the shipped template/bank that the fixture replaces.
    for entry in os.listdir(EXAMS_DIR):
        src = os.path.join(EXAMS_DIR, entry)
        if not os.path.isfile(src):
            continue
        if entry in ("autoexam-template.tex", "bank.tex") or entry.lower().endswith(".md"):
            continue
        dest = os.path.join(tmp, entry)
        if not os.path.exists(dest):
            shutil.copy2(src, dest)


def build(macro: str, timeout: int = 180) -> tuple[str | None, str]:
    """Compile the fixture with `macro` injected before \\input. Returns
    (normalized_text, error). text is None if the build or extraction failed."""
    tmp = tempfile.mkdtemp(prefix="texlib_modefx_")
    try:
        for name, content in (("coursemeta.tex", COURSEMETA_TEX),
                              ("bank.tex", BANK_TEX),
                              ("exam.tex", EXAM_TEX)):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        _copy_build_inputs(tmp)

        arg = (f"{macro}\\input{{exam.tex}}") if macro else "exam.tex"
        cmd = [LUALATEX, "-interaction=nonstopmode", "-halt-on-error",
               "-shell-escape", "-jobname=exam", arg]
        # Two passes: the dual-copy version loop and \pageref{LastPage} settle on
        # the second run (as latexmk / the Sublime builder do).
        rc = 0
        for _ in range(2):
            proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            rc = proc.returncode
        pdf = os.path.join(tmp, "exam.pdf")
        if rc != 0 or not os.path.exists(pdf):
            return None, f"lualatex exit={rc}, pdf={'yes' if os.path.exists(pdf) else 'no'}"

        raw = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=60).stdout
        return _norm(raw or ""), ""
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    print("TeXLib build-mode leakage guard\n")
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext (avoiding Git's xpdf build).")
        return 0

    for label, macro, expect in MODES:
        print(f"=== mode: {label} ({macro or 'no flags'}) ===")
        text, err = build(macro)
        if text is None:
            check(f"[{label}] fixture builds + extracts", False, err)
            continue

        # Sanity anchor: if the stems didn't render, the build/extraction is
        # broken -- report THAT, so a broken toolchain isn't misread as a flag
        # correctly hiding content.
        stems_ok = all(n in text for n in STEM_NEEDLES)
        check(f"[{label}] fixture rendered (stems present)", stems_ok,
              "stem anchors missing -- build or pdftotext extraction is broken")
        if not stems_ok:
            continue

        sol = any(n in text for n in SOLUTION_NEEDLES)
        ans = bool(ANSWER_BADGE_RE.search(text))
        rub = any(n in text for n in RUBRIC_NEEDLES)

        # Solutions: leak (present when it must be absent) OR no-op (absent when
        # it must be present) both fail here.
        check(f"[{label}] solution tokens {'present' if expect['sol'] else 'absent'}",
              sol == expect["sol"],
              _mismatch("solution", SOLUTION_NEEDLES, text, expect["sol"]))
        # MC correct-answer badge.
        check(f"[{label}] MC answer letter {'present' if expect['ans'] else 'absent'}",
              ans == expect["ans"],
              f"ANSWER_BADGE_RE {'matched' if ans else 'no match'}, "
              f"expected {'match' if expect['ans'] else 'no match'}")
        # Rubric overlay.
        check(f"[{label}] rubric tokens {'present' if expect['rub'] else 'absent'}",
              rub == expect["rub"],
              _mismatch("rubric", RUBRIC_NEEDLES, text, expect["rub"]))
        print()

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


def _mismatch(kind: str, needles: list[str], text: str, expected: bool) -> str:
    present = [n for n in needles if n in text]
    if expected:
        return f"expected {kind} tokens shown, missing: {[n for n in needles if n not in text]}"
    return f"LEAK: {kind} tokens appeared in a build that must hide them: {present}"


if __name__ == "__main__":
    sys.exit(main())
