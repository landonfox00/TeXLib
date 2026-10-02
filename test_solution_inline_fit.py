#!/usr/bin/env python3
r"""
The inline key makes room for a solution taller than its answer space.

The inline layout draws each solution as a zero-size overlay, so a key page is
its student page with the answers in the blanks (test_solution_inline_parity.py
guards that). Nothing bounded the overlay: a solution taller than the blank it
was drawn into printed over the next question. texlib_keyfit.lua now checks
each finished page and, where a solution is short of room, raises the space
after it and takes the difference from the page's other answer spaces.

Three pages, three behaviours:

  * FITS    -- the solution is shorter than its blank. The page must come out
               exactly as the student copy: the problem after it does not move.
  * SHORT   -- a seven-line solution in a blank a few points tall, with a second
               problem below it on the same page. Without the fit pass the
               solution's last line prints BELOW the next problem's stem. With
               it, every line of the solution is above that stem, the stem has
               moved down, and the page count is unchanged.
  * NOROOM  -- a solution taller than the whole page. Nothing can make room; the
               build must say so in the log rather than fail quietly.

Asserted on word positions from poppler's `pdftotext -bbox`, since the point is
where things are printed and the text is the same in every case. Soft-skips
(exit 0) without lualatex or a poppler pdftotext, like the other real-build
tests.

Run:  python test_solution_inline_fit.py   (exit 0 ok/skipped, 1 on a failure)
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


def _find_poppler_pdftotext() -> str | None:
    """poppler's pdftotext. The one beside lualatex is tried first: TeX Live
    ships poppler's, while Git for Windows puts xpdf's ahead of it on PATH."""
    candidates = []
    if LUALATEX:
        ext = ".exe" if os.name == "nt" else ""
        candidates.append(os.path.join(os.path.dirname(LUALATEX), "pdftotext" + ext))
    which = shutil.which("pdftotext")
    if which:
        candidates.append(which)
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

TALL_LINES = "\n".join(
    rf"		Line {n} of a long worked solution. TALLLINE{n}\par" for n in range(1, 8))
HUGE_LINES = "\n".join(
    rf"		Line {n} of a solution no page can hold. HUGELINE\par" for n in range(1, 90))

BANK_TEX = r"""\begin{problem}{fits}[topic=fits]
	FITSSTEM Evaluate $2 + 2$.
	\begin{solution}
		FITSANSWER $4$.
	\end{solution}
\end{problem}

\begin{problem}{fitsafter}[topic=fitsafter]
	FITSAFTERSTEM Evaluate $3 + 3$.
	\begin{solution}
		$6$.
	\end{solution}
\end{problem}

\begin{problem}{short}[topic=short]
	SHORTSTEM Expand $(x + 1)^{7}$.
	\begin{solution}
""" + TALL_LINES + r"""
		TALLEND
	\end{solution}
\end{problem}

\begin{problem}{shortafter}[topic=shortafter]
	SHORTAFTERSTEM Evaluate $5 + 5$.
	\begin{solution}
		$10$.
	\end{solution}
\end{problem}

\begin{problem}{noroom}[topic=noroom]
	NOROOMSTEM State everything.
	\begin{solution}
""" + HUGE_LINES + r"""
	\end{solution}
\end{problem}
"""

# The second optional argument of \problem is the stretch of the answer space
# after it. 0.02 against 4 leaves `short` a blank a few points tall.
EXAM_TEX = r"""\documentclass[exam-number=1, points=50]{autoexam}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem[10][2]{topic=fits}
	\problem[10][2]{topic=fitsafter}

	\newpage

	\problem[10][0.02]{topic=short}
	\problem[10][4]{topic=shortafter}

	\newpage

	\problem[10][1]{topic=noroom}
\end{problems}
\end{document}
"""

WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')


def log(msg: str) -> None:
    print(msg, flush=True)


def _copy_build_inputs(tmp: str) -> None:
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            shutil.copy2(src, os.path.join(tmp, entry))
    exams = os.path.join(TEXLIB_ROOT, "Exams")
    for entry in os.listdir(exams):
        src = os.path.join(exams, entry)
        if os.path.isfile(src) and not entry.lower().endswith(".md"):
            dest = os.path.join(tmp, entry)
            if not os.path.exists(dest):
                shutil.copy2(src, dest)


def build(tmp: str, jobname: str, macro: str, timeout: int = 300) -> str:
    arg = f"{macro}\\input{{doc.tex}}" if macro else "doc.tex"
    cmd = [LUALATEX, "-interaction=nonstopmode", "-halt-on-error",
           "-shell-escape", f"-jobname={jobname}", arg]
    proc = None
    for _ in range(2):
        proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    pdf = os.path.join(tmp, f"{jobname}.pdf")
    if proc.returncode != 0 or not os.path.exists(pdf):
        tail = "\n".join((proc.stdout or "").splitlines()[-10:])
        raise RuntimeError(f"{jobname}: lualatex exit={proc.returncode}\n{tail}")
    return pdf


def words(pdf: str) -> list[dict[str, tuple[float, float]]]:
    """Per page: token -> (yMin of its first occurrence, yMax of its last)."""
    xml = subprocess.run([PDFTOTEXT, "-bbox", pdf, "-"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace",
                         timeout=120).stdout
    pages = []
    for chunk in xml.split("<page ")[1:]:
        found: dict[str, tuple[float, float]] = {}
        for _x0, y0, _x1, y1, text in WORD_RE.findall(chunk):
            top, bottom = float(y0), float(y1)
            if text in found:
                found[text] = (min(found[text][0], top), max(found[text][1], bottom))
            else:
                found[text] = (top, bottom)
        pages.append(found)
    return pages


def main() -> int:
    if LUALATEX is None:
        log("SKIP: lualatex not found")
        return 0
    if PDFTOTEXT is None:
        log("SKIP: no poppler-flavored pdftotext")
        return 0

    tmp = tempfile.mkdtemp(prefix="texlib_inlinefit_")
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        log(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    try:
        for name, content in (("coursemeta.tex", COURSEMETA_TEX),
                              ("bank.tex", BANK_TEX), ("doc.tex", EXAM_TEX)):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        _copy_build_inputs(tmp)

        student = words(build(tmp, "student", ""))
        key = words(build(tmp, "inlinekey", r"\def\ShowKeyInline{}"))
        with open(os.path.join(tmp, "inlinekey.log"), encoding="utf-8",
                  errors="replace") as fh:
            keylog = fh.read()

        check("the key has the student copy's page count",
              len(key) == len(student), f"student {len(student)}, key {len(key)}")
        if len(key) != len(student) or len(key) < 4:
            return report(failures)

        # Page indices: 0 is the cover, then the three problem pages.
        s_fit, k_fit = student[1], key[1]
        check("FITS: the solution is on the page", "FITSANSWER" in k_fit)
        if "FITSAFTERSTEM" in s_fit and "FITSAFTERSTEM" in k_fit:
            moved = abs(k_fit["FITSAFTERSTEM"][0] - s_fit["FITSAFTERSTEM"][0])
            check("FITS: the problem after a solution that fits does not move",
                  moved < 0.05, f"moved {moved:.2f}pt")
        else:
            check("FITS: the following stem is on the page", False)

        s_sh, k_sh = student[2], key[2]
        needed = ("TALLEND", "SHORTAFTERSTEM")
        if all(t in k_sh for t in needed) and "SHORTAFTERSTEM" in s_sh:
            tall_bottom = k_sh["TALLEND"][1]
            after_top = k_sh["SHORTAFTERSTEM"][0]
            check("SHORT: the whole solution is above the next problem",
                  tall_bottom < after_top,
                  f"solution ends at y={tall_bottom:.1f}, next stem starts at "
                  f"y={after_top:.1f} -- the solution is printed over it")
            pushed = after_top - s_sh["SHORTAFTERSTEM"][0]
            check("SHORT: the next problem moved down to make the room",
                  pushed > 20, f"moved {pushed:.1f}pt")
            first = k_sh.get("TALLLINE1")
            check("SHORT: the solution starts under its own stem",
                  first is not None and first[0] > k_sh["SHORTSTEM"][1] - 2)
        else:
            check("SHORT: solution and following stem are on the page", False,
                  f"key page tokens: {sorted(t for t in k_sh if t.isupper())[:12]}")
        check("SHORT: the log records the room made",
              "made room for 1 tall solution(s)" in keylog)

        check("NOROOM: a solution no page can hold is reported",
              "cannot hold its solutions" in keylog)
        return report(failures)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        log(f"FAIL: build environment failed -- {type(exc).__name__}: {exc}")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def report(failures: list[str]) -> int:
    if failures:
        log("")
        for f in failures:
            log(f"FAIL: {f}")
        return 1
    log("OK: the inline key makes room where a solution needs it, and only there")
    return 0


if __name__ == "__main__":
    sys.exit(main())
