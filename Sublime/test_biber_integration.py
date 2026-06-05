#!/usr/bin/env python3
"""
End-to-end integration test for texlib_builder.py's biber + rerun logic.

Unlike test_texlib_builder.py (which simulates engine output), this drives the
REAL builder coroutine against REAL pdflatex/lualatex + biber on a self-
contained biblatex fixture, and asserts the actual multi-pass behavior:

  * a fresh build runs biber and settles to a PDF with NO undefined references,
  * an unchanged rebuild SKIPS biber (the .bcf-hash cache hit) in one pass,
  * editing the .bib makes biber run again.

The builder's commands() is pure orchestration -- it yields (command, message)
pairs and reads its rerun/biber decisions from self.out and the on-disk
.bcf/.bbl/.texlibhash. So we drive the coroutine and actually execute each
yielded command with subprocess, feeding the real captured output back in. That
exercises _biber_needed / _biber_is_current / _needs_another_run for real.

The fixture uses only standard packages (biblatex) in a clean temp directory,
so no TEXINPUTS / junction is needed. If pdflatex or biber is absent the whole
test soft-skips with exit 0 (matching smoke_test.py's degrade-don't-fail rule).

Run:  python test_biber_integration.py     (exit code: 0 ok/skipped, 1 failure)
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import types

# --- Refuse to run inside Sublime (same guard as test_texlib_builder.py) -----
if "sublime" in sys.modules:
    print("test_biber_integration.py is a standalone test, not a plugin.")
    raise SystemExit


# --- Stub LaTeXTools' PdfBuilder and import the real builder -----------------
class _StubPdfBuilder:
    def __init__(self, *a, **k):
        self._displayed = ""

    def display(self, msg):
        self._displayed += str(msg)


def _install_stub():
    for name in (
        "LaTeXTools",
        "LaTeXTools.plugins",
        "LaTeXTools.plugins.builder",
        "LaTeXTools.plugins.builder.pdf_builder",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["LaTeXTools.plugins.builder.pdf_builder"].PdfBuilder = _StubPdfBuilder


_install_stub()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from texlib_builder import TexlibBuilder  # noqa: E402


# --- Tiny result tracker -----------------------------------------------------
_PASS = 0
_FAIL = 0


def check(label, condition, detail=""):
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


# --- Fixture -----------------------------------------------------------------
REFS_BIB = r"""@article{knuth1984,
  author  = {Donald E. Knuth},
  title   = {Literate Programming},
  journal = {The Computer Journal},
  volume  = {27},
  number  = {2},
  pages   = {97--111},
  year    = {1984},
}
"""

# A forward \ref (undefined on pass 1 -> forces a cross-ref rerun) plus a \cite
# (forces biber). Exercises the full run -> biber -> run -> run path.
DOC_TEX = r"""\documentclass{article}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}
\begin{document}
A forward reference to section~\ref{sec:end} and a citation~\cite{knuth1984}.
\section{Start}\label{sec:start}
\section{End}\label{sec:end}
\printbibliography
\end{document}
"""

UNDEFINED_MARKERS = (
    "There were undefined references",
    "Citation '" "knuth1984' undefined",  # split to avoid matching this comment
    "Citation `knuth1984' undefined",
)


def run_build(tex_dir, engine):
    """Drive the real builder coroutine, executing each yielded command.

    Returns dict with: heads (first token per command), passes (list of engine
    outputs in order), final (last engine output), and the raw command list.
    """
    b = TexlibBuilder()
    b.tex_root = os.path.join(tex_dir, "doc.tex")
    b.tex_name = "doc.tex"
    b.base_name = "doc"
    b.tex_dir = tex_dir
    b.engine = engine
    b.options = []
    b.aux_directory = ""  # build in place; .bcf/.bbl/.texlibhash live in tex_dir
    b.out = ""

    heads, passes, raw = [], [], []
    gen = b.commands()
    try:
        item = next(gen)
        while True:
            cmd, _msg = item
            raw.append(cmd)
            heads.append(cmd[0])
            proc = subprocess.run(
                cmd, cwd=tex_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            if cmd[0] != "biber":
                passes.append(out)
            b.out = out
            item = gen.send(proc.returncode)
    except StopIteration:
        pass
    return {
        "heads": heads,
        "passes": passes,
        "final": passes[-1] if passes else "",
        "raw": raw,
    }


def main():
    print("TeXLib biber integration test\n")

    # Prefer pdflatex (fast, no font setup); biblatex+biber is engine-agnostic.
    engine = "pdflatex" if shutil.which("pdflatex") else (
        "lualatex" if shutil.which("lualatex") else None)
    if not engine or not shutil.which("biber"):
        print("  SKIP  pdflatex/lualatex or biber not found -- integration test "
              "soft-skipped (this is fine on a bare environment).")
        return 0

    tex_dir = tempfile.mkdtemp(prefix="texlib_biber_it_")
    try:
        with open(os.path.join(tex_dir, "doc.tex"), "w", encoding="utf-8") as fh:
            fh.write(DOC_TEX)
        with open(os.path.join(tex_dir, "refs.bib"), "w", encoding="utf-8") as fh:
            fh.write(REFS_BIB)

        pdf = os.path.join(tex_dir, "doc.pdf")
        hashfile = os.path.join(tex_dir, "doc.bcf.texlibhash")

        # --- Build 1: fresh -> biber runs, settles, no undefined refs ---------
        t0 = time.monotonic()
        r1 = run_build(tex_dir, engine)
        dt1 = time.monotonic() - t0
        print(f"  build 1 ({dt1:.1f}s): {r1['heads']}")
        check("build 1: biber was invoked", "biber" in r1["heads"], r1["heads"])
        check("build 1: produced a PDF", os.path.exists(pdf))
        check("build 1: recorded the .bcf hash cache", os.path.exists(hashfile))
        check("build 1: final pass has NO undefined references",
              all(m not in r1["final"] for m in UNDEFINED_MARKERS),
              "\n".join(line for line in r1["final"].splitlines()
                        if "undefined" in line.lower()))

        # --- Build 2: unchanged -> biber SKIPPED, single pass -----------------
        t0 = time.monotonic()
        r2 = run_build(tex_dir, engine)
        dt2 = time.monotonic() - t0
        print(f"  build 2 ({dt2:.1f}s): {r2['heads']}")
        check("build 2: biber was SKIPPED (cache hit)",
              "biber" not in r2["heads"], r2["heads"])
        check("build 2: single engine pass",
              r2["heads"].count(engine) == 1, r2["heads"])
        check("build 2: still no undefined references",
              all(m not in r2["final"] for m in UNDEFINED_MARKERS), r2["final"][:400])

        # --- Build 3: edit the .bib -> biber runs again -----------------------
        with open(os.path.join(tex_dir, "refs.bib"), "w", encoding="utf-8") as fh:
            fh.write(REFS_BIB.replace("Literate Programming",
                                      "Literate Programming (Revised)"))
        r3 = run_build(tex_dir, engine)
        print(f"  build 3 (bib edited): {r3['heads']}")
        check("build 3: biber re-runs after .bib edit",
              "biber" in r3["heads"], r3["heads"])

        if dt2 and dt1:
            print(f"\n  note: unchanged rebuild {dt1/dt2:.1f}x faster "
                  f"({dt1:.1f}s -> {dt2:.1f}s) thanks to the biber skip.")
    finally:
        shutil.rmtree(tex_dir, ignore_errors=True)

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return _FAIL


if __name__ == "__main__":
    sys.exit(main())
