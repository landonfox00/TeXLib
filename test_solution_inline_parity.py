#!/usr/bin/env python3
r"""
Geometric parity of the inline key against its student copy (\ShowKeyInline).

The inline layout exists so a key page IS the student page with the answers
drawn into the blanks -- same pagination, same problem positions, nothing
displaced. {partsolution} has honored that since it was written (zero declared
height and depth, lowered one \baselineskip). The full-problem {solution} did
not: with no \ifsolinline branch it always emitted its two 10pt outer
separations and a full-size box, so every problem printed after one moved down
the page, and a long enough exam re-paginated the key outright.

Nothing caught that, because every other mode test asserts on TEXT -- and the
text is identical. Only the geometry moves. So this asserts geometry: build the
fixture twice, student and inline key, rasterize both, and require that every
dark pixel of the student page still has ink in the key. The key may ADD ink
(that is the answer); it may not move or lose any.

Not a reference-image test. Both PDFs are built by the same engine in the same
run and compared only against each other, so there is no golden image to drift
and nothing environment-specific -- unlike the local-only visual regression
aids, this is safe to gate on in CI.

Deliberate fixture details, both load-bearing:

  * `after` FOLLOWS the {solution} problem on the same page. A displaced box at
    the bottom of an otherwise empty page only eats its own stretch and leaves
    what is above it alone -- that shape scores 100% even on the unfixed
    library. It is the problem printed after the box that gets pushed.
  * every problem carries \workbox answer space. With no blank to draw into,
    the inline layout has nothing to preserve and the test passes vacuously;
    the `added by key` assertion below also guards that.

The cover is excluded on purpose: a key has to be identifiable as a key, and
the class prints a red "Solutions" badge under the date that reflows page 1.

Dependencies are poppler's pdftoppm and lualatex, nothing else -- the raster is
read as PGM with the standard library so CI needs no image package. Soft-skips
(exit 0) when a tool is missing, matching test_mode_effects.py.

Run:  python test_solution_inline_parity.py   (exit 0 ok/skipped, 1 on drift)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
LUALATEX = shutil.which("lualatex")
PDFTOPPM = shutil.which("pdftoppm")

DPI = 150
DARK = 128          # luminance at or below this counts as ink
TOL = 2             # px: a student pixel is preserved if the key has ink within
                    # this radius. Measured need: a glyph can land 1-2px off
                    # because the zero-height overlay still opens a line, and
                    # the edge pixels then cross the DARK cut (same line, same
                    # x, key luminance 136-188). Displacement -- what this test
                    # is for -- moves lines by tens of pixels, so no plausible
                    # regression hides under a 2px tolerance.
MIN_PRESERVED = 99.5
FIRST_PROBLEM_PAGE = 2

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

BANK_TEX = r"""\begin{problem}{whole}[topic=whole]
	Write $f(x) = 2x^{2} - 12x + 13$ in vertex form, then state the vertex.
	\workbox{4}
	\begin{solution}
		$f(x) = 2(x - 3)^{2} - 5$, so the vertex is $(3, -5)$.
	\end{solution}
\end{problem}

\begin{problem}{after}[topic=after]
	Solve $3^{x + 2} = 81$.
	\workbox{4}
	\begin{solution}
		$3^{x+2} = 3^{4}$, so $x = 2$.
	\end{solution}
\end{problem}

\begin{problem}{parts}[topic=parts]
	Give each domain in interval notation.
	\begin{parts}
		\ppart $g(x) = \sqrt{x - 2}$
			\begin{partsolution}
				Need $x - 2 \ge 0$, so $[2, \infty)$.
			\end{partsolution}
			\workbox{2}
		\ppart $h(x) = \dfrac{1}{x - 5}$
			\begin{partsolution}
				Everything but $x = 5$.
			\end{partsolution}
			\workbox{2}
	\end{parts}
\end{problem}
"""

EXAM_TEX = r"""\documentclass[exam-number=1, points=20]{autoexam}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem[10]{topic=whole}
	\problem[10]{topic=after}

	\newpage

	\problem[5,5]{topic=parts}
\end{problems}
\end{document}
"""


def log(msg: str) -> None:
    print(msg, flush=True)


def skip(reason: str) -> int:
    log(f"SKIP: {reason}")
    return 0


def _copy_build_inputs(tmp: str) -> None:
    """Copy the library into the build dir rather than pointing TEXINPUTS at a
    path that may contain a comma (mirrors test_mode_effects.py)."""
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


def rasterize(pdf: str, tag: str, tmp: str) -> list[str]:
    """Grayscale PGM, so the raster can be read with the standard library."""
    subprocess.run([PDFTOPPM, "-gray", "-r", str(DPI), pdf,
                    os.path.join(tmp, f"pg_{tag}")],
                   check=True, capture_output=True, timeout=300)
    return sorted(f for f in os.listdir(tmp)
                  if f.startswith(f"pg_{tag}-") and f.endswith(".pgm"))


def read_pgm(path: str) -> tuple[int, int, bytes]:
    """Minimal binary-PGM (P5) reader: magic, w, h, maxval, then the rows."""
    with open(path, "rb") as fh:
        data = fh.read()
    fields: list[bytes] = []
    i = 0
    while len(fields) < 4:
        while i < len(data) and data[i : i + 1].isspace():
            i += 1
        if data[i : i + 1] == b"#":
            while i < len(data) and data[i] != 0x0A:
                i += 1
            continue
        start = i
        while i < len(data) and not data[i : i + 1].isspace():
            i += 1
        fields.append(data[start:i])
    i += 1  # single whitespace byte after maxval
    if fields[0] != b"P5":
        raise RuntimeError(f"{path}: not a binary PGM ({fields[0]!r})")
    w, h = int(fields[1]), int(fields[2])
    return w, h, data[i : i + w * h]


def compare(student: str, key: str) -> tuple[int, int, int]:
    """-> (student ink, student ink with no key ink within TOL, ink added)."""
    w, h, sa = read_pgm(student)
    w2, h2, sb = read_pgm(key)
    if (w, h) != (w2, h2):
        raise RuntimeError(f"page size differs: {w}x{h} vs {w2}x{h2}")
    total = moved = 0
    for y in range(h):
        row = y * w
        for x in range(w):
            if sa[row + x] > DARK:
                continue
            total += 1
            hit = False
            for dy in range(-TOL, TOL + 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                base = yy * w
                lo, hi = max(0, x - TOL), min(w - 1, x + TOL)
                if any(sb[base + xx] <= DARK for xx in range(lo, hi + 1)):
                    hit = True
                    break
            if not hit:
                moved += 1
    added = sum(1 for i in range(w * h) if sb[i] <= DARK and sa[i] > DARK)
    return total, moved, added


def main() -> int:
    if LUALATEX is None:
        return skip("lualatex not found")
    if PDFTOPPM is None:
        return skip("pdftoppm not found")

    tmp = tempfile.mkdtemp(prefix="texlib_inlineparity_")
    failures: list[str] = []
    try:
        for name, content in (("coursemeta.tex", COURSEMETA_TEX),
                              ("bank.tex", BANK_TEX),
                              ("doc.tex", EXAM_TEX)):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        _copy_build_inputs(tmp)

        student_pdf = build(tmp, "student", "")
        key_pdf = build(tmp, "inlinekey",
                        r"\def\ShowSolutions{}\def\ShowKeyInline{}")

        a = rasterize(student_pdf, "a", tmp)
        b = rasterize(key_pdf, "b", tmp)
        log(f"student: {len(a)} page(s)   inline key: {len(b)} page(s)")
        if len(a) != len(b):
            failures.append(
                f"page count differs: student {len(a)}, inline key {len(b)} -- "
                "the key re-paginated, so the inline layout displaced something")
            return report(failures)

        for i, (pa, pb) in enumerate(zip(a, b), 1):
            if i < FIRST_PROBLEM_PAGE:
                log(f"  p{i}: cover, skipped (the key's \"Solutions\" badge "
                    "reflows it by design)")
                continue
            total, moved, added = compare(os.path.join(tmp, pa),
                                          os.path.join(tmp, pb))
            pct = 100.0 * (total - moved) / total if total else 100.0
            log(f"  p{i}: student ink {total:6d}  preserved {pct:6.2f}%  "
                f"moved {moved:5d}  added by key {added:6d}")
            if pct < MIN_PRESERVED:
                failures.append(
                    f"p{i}: only {pct:.2f}% of the student page survived in the "
                    f"inline key ({moved} px moved or lost) -- the key is not "
                    "geometrically identical to its student copy")
            if added == 0:
                failures.append(
                    f"p{i}: the inline key added no ink -- the solution did not "
                    "render, so parity on this page is vacuous")
        return report(failures)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        log(f"SKIP: build environment failed -- {type(exc).__name__}: {exc}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def report(failures: list[str]) -> int:
    if failures:
        log("")
        for f in failures:
            log(f"FAIL: {f}")
        return 1
    log("OK: the inline key is geometrically identical to its student copy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
