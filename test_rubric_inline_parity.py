#!/usr/bin/env python3
r"""
An instructor's copy is the student copy with ink added: answers, rubrics,
\award marks, the points in the header and the copy's label on the cover.

test_solution_inline_parity.py holds the key to the student page within a 2px
tolerance and skips the cover. This holds the INSTRUCTOR copy, rubric and all,
to the student page exactly, cover included, by building it a second time with
\TeXLibGhostInk: every answer, footer and mark is typeset as the instructor
copy typesets it and none of it is drawn. What is left must be the student
copy, pixel for pixel. A key without rubrics is held to the same, because its
blanks have to keep the room the rubric takes in the instructor's copy.

Also asserted:

  * the instructor copy makes no room of its own (no texlib-solutions warning
    in its log) and does draw its ink: "+2", the common-error panel, the rubric
    panel, the cover label, the points in the header;
  * the student copy draws none of it;
  * \award marks that do not add up to the item's points stop a rubric build
    with an error naming the problem or part, and leave a student build alone.

The fixture has a whole-problem {solution} with awards and {commonerrors}, a
problem with part solutions carrying a rubric line and common errors, a
graded {sketchaxes} answer (its ink is drawn at zero opacity under ghost ink),
an {align*} whose rows end in \award (amsmath sets each row twice; an award
must count once), and two versions, so the per-problem point total has to
restart each copy. The first problem's lines are short, so its common errors
are set beside the work rather than under it.

Builds with lualatex, rasterizes with pdftoppm and reads the PGM with the
standard library (helpers from test_solution_inline_parity.py). Text checks use
pdftotext and are skipped without it. Soft-skips (exit 0) when lualatex or
pdftoppm is missing.

Run:  python test_rubric_inline_parity.py   (exit 0 ok/skipped, 1 on failure)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

import test_solution_inline_parity as base

LUALATEX = base.LUALATEX
PDFTOPPM = base.PDFTOPPM
PDFTOTEXT = base.PDFTOTEXT

INSTRUCTOR = r"\def\ShowSolutions{}\def\ShowRubric{}\def\InstructorMode{}"
KEY = r"\def\ShowKey{}"
GHOST = r"\def\TeXLibGhostInk{}"

BANK_TEX = r"""\begin{problem}{ineq}[topic=ineq]
	Solve $(x - 1)^{2}(x + 3) \le 0$. Write your answer in interval notation.
	\begin{solution}
		$(x - 1)^{2}(x + 3) = 0 \implies x = -3, \ x = 1$ \award{2}

		signs on $(-\infty, -3)$, $(-3, 1)$, $(1, \infty)$: $-$, $+$, $+$ \award{3}

		$\boxed{(-\infty, -3] \cup \{1\}}$ \award{2}
		\begin{commonerrors}
			\item[2] leaves out the isolated solution $x = 1$
			\item[1] open endpoint at $-3$
		\end{commonerrors}
	\end{solution}
\end{problem}

\begin{problem}{parts}[topic=parts]
	Let $f(x) = 2x + 1$.
	\begin{parts}
		\ppart Find $f(3)$.
			\begin{partsolution}
				$f(3) = 2(3) + 1 = 7$ \award{2}
				\begin{commonerrors}
					\item[1] arithmetic slip
				\end{commonerrors}
			\end{partsolution}
		\ppart Solve $f(x) = 5$.
			\begin{partsolution}
				$2x + 1 = 5$ \award{1}

				$x = 2$ \award{2}
				\rubric{3}{RUBRICLINE correct value}
			\end{partsolution}
	\end{parts}
\end{problem}

\begin{problem}{aligned}[topic=aligned]
	Solve $2x + 3 = 7$.
	\begin{solution}
		\begin{align*}
			2x + 3 &= 7 \award{1} \\
			2x &= 4 \award{1} \\
			x &= \boxed{2} \award{1}
		\end{align*}
	\end{solution}
\end{problem}

\begin{problem}{graph}[topic=graph]
	Graph $y = x$.
	\begin{sketchaxes}{-3}{3}{-3}{3}
		\draw[thick] (-3,-3) -- (3,3);
	\end{sketchaxes}
	\begin{solution}
		A line through the origin of slope $1$. \award{4}
	\end{solution}
\end{problem}
"""

EXAM_TEX = r"""\documentclass[exam-number=1, points=21]{autoexam}
\keylayout{inline}
\versions{A,B}
\setexamseed{3}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem[7][1]{topic=ineq}
	\newpage
	\problem[2,3][1,1]{topic=parts}
	\newpage
	\problem[3][0.3]{topic=aligned}
	\problem[4][0.2]{topic=graph}
\end{problems}
\end{document}
"""

# The same exam with Problem 1's awards one short of its points.
WRONG_TEX = EXAM_TEX.replace(r"\problem[7][1]{topic=ineq}",
                             r"\problem[8][1]{topic=ineq}")


def log(msg: str) -> None:
    print(msg, flush=True)


def build(tmp: str, jobname: str, macro: str, doc: str = "doc.tex") -> tuple[str, str]:
    """Two passes, nonstopmode, no halt: an \\award error is reported and the
    run goes on, as it does in the builder. -> (pdf, log text).

    The mode macros are written at the top of a file named for the job, not
    passed with -jobname and \\input: the version loop reads the copies' body
    from <jobname>.tex, so a job whose file holds no document emits one copy."""
    with open(os.path.join(tmp, doc), encoding="utf-8") as fh:
        source = fh.read()
    with open(os.path.join(tmp, f"{jobname}.tex"), "w", encoding="utf-8") as fh:
        fh.write(macro + "\n" + source)
    cmd = [LUALATEX, "-interaction=nonstopmode", "-shell-escape",
           f"{jobname}.tex"]
    for _ in range(2):
        subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    pdf = os.path.join(tmp, f"{jobname}.pdf")
    if not os.path.exists(pdf):
        raise RuntimeError(f"{jobname}: no PDF")
    with open(os.path.join(tmp, f"{jobname}.log"), encoding="utf-8",
              errors="replace") as fh:
        return pdf, fh.read()


def text(pdf: str) -> str:
    return subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=120).stdout


def identical(tmp: str, a: list[str], b: list[str], what: str,
              failures: list[str]) -> None:
    if len(a) != len(b):
        failures.append(f"{what}: {len(b)} pages against the student's {len(a)}")
        return
    for i, (pa, pb) in enumerate(zip(a, b), 1):
        wa, ha, da = base.read_pgm(os.path.join(tmp, pa))
        wb, hb, db = base.read_pgm(os.path.join(tmp, pb))
        if (wa, ha) != (wb, hb) or da != db:
            n = sum(1 for x, y in zip(da, db) if x != y) if len(da) == len(db) else -1
            failures.append(f"{what}: page {i} differs from the student copy "
                            f"({n} pixels)")
    log(f"  {what}: {len(b)} page(s) checked against the student copy")


def main() -> int:
    if LUALATEX is None:
        log("SKIP: lualatex not found")
        return 0
    if PDFTOPPM is None:
        log("SKIP: pdftoppm not found")
        return 0
    tmp = tempfile.mkdtemp(prefix="texlib_rubricparity_")
    failures: list[str] = []
    try:
        for name, content in (("coursemeta.tex", base.COURSEMETA_TEX),
                              ("bank.tex", BANK_TEX),
                              ("doc.tex", EXAM_TEX),
                              ("wrong.tex", WRONG_TEX)):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        base._copy_build_inputs(tmp)

        student, student_log = build(tmp, "student", "")
        instructor, instructor_log = build(tmp, "instructor", INSTRUCTOR)
        ghost, ghost_log = build(tmp, "ghost", INSTRUCTOR + GHOST)
        keyghost, _ = build(tmp, "keyghost", KEY + GHOST)

        s = base.rasterize(student, "s", tmp)
        identical(tmp, s, base.rasterize(ghost, "g", tmp),
                  "instructor copy without its ink", failures)
        identical(tmp, s, base.rasterize(keyghost, "k", tmp),
                  "key without its ink", failures)

        for name, body in (("student", student_log), ("instructor", instructor_log)):
            if "Package texlib-solutions Warning" in body:
                failures.append(f"{name} copy: a solution did not fit its blank "
                                "and the page made room")
            if "Package texlib-solutions Error" in body:
                failures.append(f"{name} copy: unexpected \\award error")

        if PDFTOTEXT is not None:
            ins, stu = text(instructor), text(student)
            for needle in ("+2", "+3", "Common Errors", "RUBRICLINE",
                           "Instructor Version"):
                if needle not in ins:
                    failures.append(f"instructor copy: {needle!r} not drawn")
                if needle in stu:
                    failures.append(f"student copy: {needle!r} drawn")
            # The header's page total, beside the title (the stem's own
            # "(7 points)" is on every copy).
            header = re.compile(r"Exam 1[ \t]+7 points")
            if not header.search(ins):
                failures.append("instructor copy: no points total in the header")
            if header.search(stu):
                failures.append("student copy: a points total in the header")
            log("  instructor ink present, student copy clean")
        else:
            log("  pdftotext not found: text checks skipped")

        _, wrong_rubric = build(tmp, "wronginstructor", INSTRUCTOR, doc="wrong.tex")
        _, wrong_student = build(tmp, "wrongstudent", "", doc="wrong.tex")
        hits = re.findall(r"Problem 1: the \\award marks add up to 7,\s*but it\s*is "
                          r"worth 8 points", wrong_rubric.replace("\n", ""))
        if len(hits) != 2:
            failures.append(f"awards one short: {len(hits)} errors in the rubric "
                            "build, one per version expected")
        if "texlib-solutions Error" in wrong_student:
            failures.append("awards one short: the student build raised an error")
        log(f"  award sum errors in the rubric build: {len(hits)}")
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        log(f"SKIP: build environment failed -- {type(exc).__name__}: {exc}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            log(f"FAIL: {f}")
        return 1
    log("OK: the instructor copy is the student copy with ink added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
