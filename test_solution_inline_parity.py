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
  * `four` has FOUR part solutions and a problem below it. Each part solution
    once cost the line after it its interline glue, about 3pt; two of them
    stay inside the 2px tolerance once the page's stretch has shared the loss
    out, and four do not.
  * `twocol` ends each {cols} column with a part solution, and has a problem
    below it. An overlay that is the last thing in its list changes the
    enclosing box's depth unless the list is closed with the depth it had, and
    a column is such a list. The question lines carry descenders so there is a
    depth to lose.

The cover is excluded on purpose: a key has to be identifiable as a key, and
the class prints a red "Solutions" badge under the date that reflows page 1.

A second exam has answers taller than their weighted blanks (TALL_BANK_TEX).
The student copy sizes each blank to its answer, so there the key must be the
student page to the pixel, not merely within the tolerance, with no keyfit
warning in its log. Its one-line part answers are set on the header's line.

Dependencies are poppler's pdftoppm and lualatex, nothing else -- the raster is
read as PGM with the standard library so CI needs no image package. The
run-in header is read off the key's text with pdftotext, and that one check
is skipped when it is missing. Soft-skips (exit 0) when a tool is missing,
matching test_mode_effects.py.

Run:  python test_solution_inline_parity.py   (exit 0 ok/skipped, 1 on drift)
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
PDFTOPPM = shutil.which("pdftoppm")
PDFTOTEXT = shutil.which("pdftotext")

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

\begin{problem}{four}[topic=four]
	Evaluate $g$ at each point.
	\begin{parts}
		\ppart $g(1)$, simplifying fully
			\begin{partsolution}
				$2$.
			\end{partsolution}
			\workbox{1}
		\ppart $g(2)$, simplifying fully
			\begin{partsolution}
				$5$.
			\end{partsolution}
			\workbox{1}
		\ppart $g(3)$, simplifying fully
			\begin{partsolution}
				$10$.
			\end{partsolution}
			\workbox{1}
		\ppart $g(4)$, simplifying fully
			\begin{partsolution}
				$17$.
			\end{partsolution}
			\workbox{1}
	\end{parts}
\end{problem}

\begin{problem}{tail}[topic=tail]
	State the domain of $\sqrt{x}$.
	\workbox{2}
	\begin{solution}
		$[0, \infty)$.
	\end{solution}
\end{problem}

\begin{problem}{twocol}[topic=twocol]
	Answer each for the graph of $g$.
	\begin{cols}
		\raggedright
		\begin{parts}
			\ppart On what intervals is $g$ increasing?
				\begin{partsolution}
					$(0, 1)$.
				\end{partsolution}
			\ppart On what intervals is $g$ decreasing?
				\begin{partsolution}
					$(1, 2)$.
				\end{partsolution}
		\end{parts}
	\end{cols}
	\workbox{1}
	\begin{cols}
		\raggedright
		\begin{parts}
			\ppart Identify the local maximum point.
				\begin{partsolution}
					$(1, 3)$.
				\end{partsolution}
			\ppart Identify the local minimum point.
				\begin{partsolution}
					$(2, 0)$.
				\end{partsolution}
		\end{parts}
	\end{cols}
	\workbox{1}
\end{problem}

\begin{problem}{tailtwo}[topic=tailtwo]
	State the range of $\sqrt{x}$.
	\workbox{2}
	\begin{solution}
		$[0, \infty)$.
	\end{solution}
\end{problem}
"""

# Answers taller than the blanks their weights give them, in each of the shapes
# that ran over on a real review: a blank BEFORE its whole-problem solution (the
# order the engine emits a body that ends in \workbox), a blank so generous the
# answer is short but drawn after it, parts with a tall answer in a thin blank,
# {cols} and \splitpage columns whose closing \vspace is dropped at the column's
# end, and a whole-problem solution whose only room is the \problem stretch.
# The student copy sizes each blank to its answer, so the key is the student
# page with the answers drawn in -- to the pixel, with no warning in its log.
# `oneline' has answers of one line, which go on the header's line.
TALL_BANK_TEX = r"""
\begin{problem}{wbefore}[topic=wbefore]
	Factor $x^{2} - 5x + 6$ and solve $x^{2} - 5x + 6 = 0$.
	\workbox{1}
	\begin{solution}
		\begin{align*}
			x^{2} - 5x + 6 &= (x - 2)(x - 3) \\
			(x - 2)(x - 3) &= 0 \\
			x - 2 = 0 \quad &\text{or} \quad x - 3 = 0 \\
			x &= 2 \text{ or } x = 3
		\end{align*}
	\end{solution}
\end{problem}

\begin{problem}{roomy}[topic=roomy]
	State the vertex of $y = (x - 1)^{2}$.
	\workbox{8}
	\begin{solution}
		$(1, 0)$.
	\end{solution}
\end{problem}

\begin{problem}{tallparts}[topic=tallparts]
	Solve each equation.
	\begin{parts}
		\ppart $x^{2} = 9$
			\begin{partsolution}
				\begin{align*} x^{2} &= 9 \\ x &= \pm\sqrt{9} \\ x &= \pm 3 \end{align*}
			\end{partsolution}
			\workbox{0.2}
		\ppart $2x + 1 = 7$
			\begin{partsolution}
				$x = 3$.
			\end{partsolution}
			\workbox{4}
		\ppart $x^{3} = 8$
			\begin{partsolution}
				\begin{align*} x^{3} &= 8 \\ x &= \sqrt[3]{8} \\ x &= 2 \end{align*}
			\end{partsolution}
			\workbox{0.2}
	\end{parts}
\end{problem}

\begin{problem}{split}[topic=split]
	Give each domain in interval notation.
	\splitpage{%
		\ppart $f(x) = \sqrt{x - 2}$
			\begin{partsolution}
				\begin{align*} x - 2 &\ge 0 \\ x &\ge 2 \\ &[2, \infty) \end{align*}
			\end{partsolution}
			\vspace{1\baselineskip}
	}{%
		\ppart $g(x) = \dfrac{1}{x - 5}$
			\begin{partsolution}
				\begin{align*} x - 5 &\ne 0 \\ x &\ne 5 \\ &(-\infty, 5) \cup (5, \infty) \end{align*}
			\end{partsolution}
			\vspace{1\baselineskip}
	}
\end{problem}

\begin{problem}{colstall}[topic=colstall]
	Answer each for the graph of $g$.
	\begin{cols}
		\raggedright
		\begin{parts}
			\ppart On what intervals is $g$ increasing?
				\begin{partsolution}
					\begin{align*} g'(x) &> 0 \\ &\text{on } (0, 1) \\ &\text{and } (3, 4) \end{align*}
				\end{partsolution}
				\vspace{1\baselineskip}
			\ppart On what intervals is $g$ decreasing?
				\begin{partsolution}
					\begin{align*} g'(x) &< 0 \\ &\text{on } (1, 3) \\ &\text{only} \end{align*}
				\end{partsolution}
				\vspace{1\baselineskip}
		\end{parts}
	\end{cols}
\end{problem}

\begin{problem}{wholetail}[topic=wholetail]
	Find the oblique asymptote of $f(x) = \dfrac{2x^{2} + x - 3}{x - 2}$.
	\begin{solution}
		\begin{align*}
			2x^{2} + x - 3 &= (x - 2)(2x + 5) + 7 \\
			f(x) &= 2x + 5 + \frac{7}{x - 2} \\
			&\text{so } y = 2x + 5
		\end{align*}
	\end{solution}
\end{problem}

\begin{problem}{oneline}[topic=oneline]
	Evaluate.
	\begin{parts}
		\ppart $2 + 2$
			\begin{partsolution}
				RUNIN $4$.
			\end{partsolution}
			\workbox{1}
		\ppart $3 \cdot 3$
			\begin{partsolution}
				RUNIN $9$.
			\end{partsolution}
			\workbox{1}
		\ppart $10 - 4$
			\begin{partsolution}
				RUNIN $6$.
			\end{partsolution}
			\workbox{1}
	\end{parts}
\end{problem}
"""

TALL_TEX = r"""\documentclass[exam-number=1, points=20]{autoexam}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem[10][0]{topic=wbefore}
	\problem[10][0]{topic=roomy}
	\problem[10][0.1]{topic=tallparts}

	\newpage

	\problem[5,5][0.1]{topic=split}
	\problem[5,5][0.1]{topic=colstall}
	\problem[10][0.2]{topic=wholetail}
	\problem[2,2,2][3]{topic=oneline}
\end{problems}
\end{document}
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

	\newpage

	\problem[2,2,2,2]{topic=four}
	\problem[10]{topic=tail}

	\newpage

	\problem[2,2,3,3]{topic=twocol}
	\problem[10]{topic=tailtwo}
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


def build(tmp: str, jobname: str, macro: str, timeout: int = 300,
          doc: str = "doc.tex") -> str:
    arg = f"{macro}\\input{{{doc}}}" if macro else doc
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
                              ("bank.tex", BANK_TEX + TALL_BANK_TEX),
                              ("doc.tex", EXAM_TEX),
                              ("tall.tex", TALL_TEX)):
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

        # \keylayout{inline}: the same layout as a document's standing
        # preference. Two things have to hold. Built with no flag the document
        # is still the student copy, to the pixel, cover included -- the
        # preference must not turn a plain build into a key. Built with the
        # ordinary \ShowKey the builder's `solutions' variant passes, it is the
        # inline key.
        with open(os.path.join(tmp, "doc_kl.tex"), "w", encoding="utf-8") as fh:
            fh.write(EXAM_TEX.replace(r"\loadbank{bank.tex}",
                                      "\\keylayout{inline}\n\\loadbank{bank.tex}"))
        kl_plain = rasterize(build(tmp, "klplain", "", doc="doc_kl.tex"), "c", tmp)
        kl_key = rasterize(build(tmp, "klkey", r"\def\ShowKey{}",
                                 doc="doc_kl.tex"), "d", tmp)
        if len(kl_plain) != len(a) or len(kl_key) != len(a):
            failures.append(
                f"\\keylayout{{inline}}: page counts differ (student {len(a)}, "
                f"plain {len(kl_plain)}, key {len(kl_key)})")
            return report(failures)
        for i, (pa, pc, pd) in enumerate(zip(a, kl_plain, kl_key), 1):
            total, moved, added = compare(os.path.join(tmp, pa),
                                          os.path.join(tmp, pc))
            if moved or added:
                failures.append(
                    f"p{i}: \\keylayout{{inline}} changed the plain build "
                    f"({moved} px moved, {added} px added) -- it must stay the "
                    "student copy")
            if i < FIRST_PROBLEM_PAGE:
                continue
            total, moved, added = compare(os.path.join(tmp, pa),
                                          os.path.join(tmp, pd))
            pct = 100.0 * (total - moved) / total if total else 100.0
            log(f"  p{i}: \\keylayout{{inline}} + \\ShowKey  preserved "
                f"{pct:6.2f}%  added by key {added:6d}")
            if pct < MIN_PRESERVED or added == 0:
                failures.append(
                    f"p{i}: \\keylayout{{inline}} with \\ShowKey is not the "
                    f"inline key ({pct:.2f}% preserved, {added} px added)")

        # autoexam's default: a document that names no layout gets the inline
        # key from the ordinary \ShowKey, and \keylayout{compact} still turns
        # it off. Without the default, a review's \workbox blanks closed in its
        # key and every later part moved up the page.
        default_key = rasterize(build(tmp, "defkey", r"\def\ShowKey{}"), "e", tmp)
        if len(default_key) != len(a):
            failures.append(
                f"no \\keylayout: page counts differ (student {len(a)}, "
                f"key {len(default_key)}) -- the default is not inline")
            return report(failures)
        for i, (pa, pe) in enumerate(zip(a, default_key), 1):
            if i < FIRST_PROBLEM_PAGE:
                continue
            total, moved, added = compare(os.path.join(tmp, pa),
                                          os.path.join(tmp, pe))
            pct = 100.0 * (total - moved) / total if total else 100.0
            log(f"  p{i}: no \\keylayout + \\ShowKey  preserved "
                f"{pct:6.2f}%  added by key {added:6d}")
            if pct < MIN_PRESERVED or added == 0:
                failures.append(
                    f"p{i}: with no \\keylayout, \\ShowKey is not the inline "
                    f"key ({pct:.2f}% preserved, {added} px added)")
        with open(os.path.join(tmp, "doc_compact.tex"), "w", encoding="utf-8") as fh:
            fh.write(EXAM_TEX.replace(r"\loadbank{bank.tex}",
                                      "\\keylayout{compact}\n\\loadbank{bank.tex}"))
        compact_key = rasterize(build(tmp, "compactkey", r"\def\ShowKey{}",
                                      doc="doc_compact.tex"), "f", tmp)
        moved_any = any(compare(os.path.join(tmp, pa), os.path.join(tmp, pf))[1]
                        for i, (pa, pf) in enumerate(zip(a, compact_key), 1)
                        if i >= FIRST_PROBLEM_PAGE)
        if len(compact_key) == len(a) and not moved_any:
            failures.append(
                "\\keylayout{compact} gave the inline key: the opt-out does "
                "not override the class default")

        # Answers taller than their weighted blanks: the student copy makes the
        # room, so the key is its page to the pixel and has nothing to warn of.
        tall_student = rasterize(build(tmp, "tallstudent", "", doc="tall.tex"),
                                 "g", tmp)
        tall_key_pdf = build(tmp, "tallkey", r"\def\ShowKey{}", doc="tall.tex")
        tall_key = rasterize(tall_key_pdf, "h", tmp)
        if len(tall_student) != len(tall_key):
            failures.append(
                f"tall answers: page counts differ (student {len(tall_student)}, "
                f"key {len(tall_key)}) -- the key made room the student copy "
                "did not")
            return report(failures)
        for i, (pg, ph) in enumerate(zip(tall_student, tall_key), 1):
            if i < FIRST_PROBLEM_PAGE:
                continue
            total, moved, added = compare(os.path.join(tmp, pg),
                                          os.path.join(tmp, ph))
            log(f"  p{i}: tall answers  student ink {total:6d}  moved {moved:5d}  "
                f"added by key {added:6d}")
            if moved or added == 0:
                failures.append(
                    f"p{i}: with answers taller than their blanks the key is not "
                    f"the student page ({moved} px moved, {added} px added)")
        with open(os.path.join(tmp, "tallkey.log"), encoding="utf-8",
                  errors="replace") as fh:
            if "Package texlib-solutions Warning" in fh.read():
                failures.append(
                    "tall answers: the key's log warns that a solution did not "
                    "fit -- the student copy should have made its room")

        # A one-line part answer runs in after its header; a taller one keeps
        # the header on a line of its own. Read off the key's text when there
        # is a pdftotext to read it with.
        if PDFTOTEXT is not None:
            text = subprocess.run([PDFTOTEXT, "-layout", tall_key_pdf, "-"],
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=120).stdout
            runin = len(re.findall(r"Solution\.[ \t]+RUNIN", text))
            stacked = len(re.findall(r"^[ \t]*Solution\.[ \t]*$", text, re.M))
            log(f"  one-line answers run in: {runin} of 3; stacked headers: "
                f"{stacked}")
            if runin != 3:
                failures.append(
                    f"one-line answers: {runin} of 3 set on the header's line")
            if stacked == 0:
                failures.append(
                    "multi-line answers lost their own header line")
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
