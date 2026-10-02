#!/usr/bin/env python3
r"""
A tagged key builds without TeX errors, and keeps the compact layout.

Two things, both invisible in an ordinary build and both silent in the PDF.

  * A solution whose body ENDS IN A DISPLAY. The body is collected into a box,
    and a closing brace ends its last paragraph without the \par token, so the
    tagging code's end-of-paragraph hook never ran. For a body ending in running
    text the next \par outside closed the structure; for one ending in \[ ... \]
    nothing did, and tagpdf stopped with "there is no open structure on the
    stack". A {partsolution} like that raised twelve errors in a tagged key in
    either layout; a {solution} raised two in the inline layout. Both render
    branches now end the body with a real \par in an accessible build.

  * \keylayout{inline} in a tagged build. The tagged twin of a key stays
    compact: it is read through its structure, and the inline overlay's box
    costs a key of whole-problem solutions four PDF/UA-2 rules. Asserted by
    building the tagged key with and without the preference and requiring every
    word at the same position in both.

The engine exits 0 after recovering from these errors in nonstopmode, so the
log is what is read. Soft-skips (exit 0) without lualatex or a poppler
pdftotext, like the other real-build tests.

Run:  python test_solution_tagged_key.py   (exit 0 ok/skipped, 1 on a failure)
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

# What the builder injects for a tagged build (ACCESSIBLE_MACRO in
# Sublime/texlib/texlib_buildspec.py), with mathml-AF alone: SE adds nothing to
# what is tested here and is the half with an upstream abort.
TAGGED = (r"\DocumentMetadata{lang=en,tagging=on,"
          r"tagging-setup={math/setup={mathml-AF},table/header-rows=1},"
          r"pdfstandard={ua-2,a-4f}}\def\TeXLibAccessibleMode{}")


def _find_poppler_pdftotext() -> str | None:
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

BANK_TEX = r"""\begin{problem}{whole}[topic=whole]
	Factor $x^{2} - 4$.

	\begin{solution}
		A difference of squares:
		\[
			x^{2} - 4 = (x - 2)(x + 2).
		\]
	\end{solution}
\end{problem}

\begin{problem}{parts}[topic=parts]
	Factor each.
	\begin{parts}
		\ppart $x^{2} - 9$
			\begin{partsolution}
				A difference of squares:
				\[
					x^{2} - 9 = (x - 3)(x + 3).
				\]
			\end{partsolution}
			\workbox{1}
		\ppart $x^{2} - 1$
			\begin{partsolution}
				$(x - 1)(x + 1)$.
			\end{partsolution}
			\workbox{1}
	\end{parts}
\end{problem}

\begin{problem}{after}[topic=after]
	AFTERSTEM Evaluate $1 + 1$.

	\begin{solution}
		$2$.
	\end{solution}
\end{problem}
"""

EXAM_TEX = r"""\documentclass[exam-number=1, points=24]{autoexam}
%%LAYOUT%%
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{problems}
	\problem[10]{topic=whole}
	\problem[2,2]{topic=parts}
	\problem[10]{topic=after}
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


def build(tmp: str, jobname: str, doc: str, macro: str,
          timeout: int = 300) -> tuple[str, list[str]]:
    """-> (pdf path, the log's error lines). No -halt-on-error: the point is to
    count what a nonstopmode build recovers from and reports only in its log."""
    cmd = [LUALATEX, "-interaction=nonstopmode", "-shell-escape",
           f"-jobname={jobname}", f"{macro}\\input{{{doc}}}"]
    for _ in range(2):
        subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    pdf = os.path.join(tmp, f"{jobname}.pdf")
    if not os.path.exists(pdf):
        raise RuntimeError(f"{jobname}: no PDF")
    with open(os.path.join(tmp, f"{jobname}.log"), encoding="utf-8",
              errors="replace") as fh:
        errors = [ln.rstrip() for ln in fh if ln.startswith("! ")]
    return pdf, errors


def positions(pdf: str) -> list[tuple[str, str, str]]:
    xml = subprocess.run([PDFTOTEXT, "-bbox", pdf, "-"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace",
                         timeout=120).stdout
    return [(text, x0, y0) for x0, y0, _x1, _y1, text in WORD_RE.findall(xml)]


def main() -> int:
    if LUALATEX is None:
        log("SKIP: lualatex not found")
        return 0
    if PDFTOTEXT is None:
        log("SKIP: no poppler-flavored pdftotext")
        return 0

    tmp = tempfile.mkdtemp(prefix="texlib_taggedkey_")
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        log(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    try:
        files = (("coursemeta.tex", COURSEMETA_TEX), ("bank.tex", BANK_TEX),
                 ("doc.tex", EXAM_TEX.replace("%%LAYOUT%%", "")),
                 ("doc_kl.tex", EXAM_TEX.replace("%%LAYOUT%%", r"\keylayout{inline}")))
        for name, content in files:
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        _copy_build_inputs(tmp)

        compact, e_compact = build(tmp, "compact", "doc.tex",
                                   TAGGED + r"\def\ShowKey{}")
        check("tagged key, compact layout: no TeX errors", not e_compact,
              "; ".join(e_compact[:3]))

        _inline, e_inline = build(tmp, "inline", "doc.tex",
                                  TAGGED + r"\def\ShowKeyInline{}")
        check("tagged key, inline layout asked for outright: no TeX errors",
              not e_inline, "; ".join(e_inline[:3]))

        pref, e_pref = build(tmp, "pref", "doc_kl.tex",
                             TAGGED + r"\def\ShowKey{}")
        check(r"tagged key under \keylayout{inline}: no TeX errors", not e_pref,
              "; ".join(e_pref[:3]))
        a, b = positions(compact), positions(pref)
        check(r"tagged key under \keylayout{inline} is the compact key",
              bool(a) and a == b,
              f"{sum(1 for x, y in zip(a, b) if x != y)} of {len(a)} words differ"
              if len(a) == len(b) else f"{len(a)} words against {len(b)}")
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
    log("OK: a tagged key builds clean and stays compact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
