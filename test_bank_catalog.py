#!/usr/bin/env python3
r"""Real-build rendering check for bank.cls / \printbankcatalog (B1).

The plugin scan tests assert bank *metadata* (ids/attrs), but nothing verified
the catalog PDF actually RENDERS correctly -- which let a part-label regression
through ("0a. 0b." because a catalog has no active \question, so \thequestion is
0). This builds a real catalog of a multi-part problem and asserts:

  * the catalog builds and the problem stem + solution render (solutions are
    always shown in a catalog),
  * multi-part labels render self-containedly as "(a) (b)" -- NOT "0a 0b" and not
    depending on the unset question counter.

Soft-skips (exit 0) if lualatex or a poppler pdftotext is missing, matching the
other real-toolchain tests. Builds in its own temp dir.

Run:  python test_bank_catalog.py
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

BANK_TEX = (
    "\\begin{problem}{multipart-one}[topic=test]\n"
    "\tCompute CATSTEMNEEDLE, with sub-parts below.\n"
    "\t\\begin{parts}\n"
    "\t\t\\part[4] CATPARTONE first part text.\n"
    "\t\t\\part[2] CATPARTTWO second part text.\n"
    "\t\\end{parts}\n"
    "\t\\begin{solution}\n"
    "\tCATSOLNEEDLE is the worked solution.\n"
    "\t\\end{solution}\n"
    "\\end{problem}\n"
)
WRAPPER_TEX = (
    "\\documentclass{bank}\n"
    "\\begin{document}\n"
    "\\loadbank{bank.tex}\n"
    "\\printbankcatalog\n"
    "\\end{document}\n"
)

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


def _stage(tmp):
    """Copy the shared payload + Bank/bank.cls into the temp build dir (the
    comma-safe way -- no comma-bearing TEXINPUTS)."""
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            shutil.copy2(src, os.path.join(tmp, entry))
    shutil.copy2(os.path.join(TEXLIB_ROOT, "Bank", "bank.cls"),
                 os.path.join(tmp, "bank.cls"))


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    print("TeXLib bank.cls catalog render check\n")
    if not LUALATEX or not PDFTOTEXT:
        print("  SKIP  need lualatex + poppler pdftotext.")
        return 0

    tmp = tempfile.mkdtemp(prefix="texlib_bankcat_")
    try:
        with open(os.path.join(tmp, "bank.tex"), "w", encoding="utf-8") as fh:
            fh.write(BANK_TEX)
        with open(os.path.join(tmp, "catalog.tex"), "w", encoding="utf-8") as fh:
            fh.write(WRAPPER_TEX)
        _stage(tmp)

        env = os.environ.copy()
        # Files are all in cwd; prefer cwd for .sty/.cls AND the .lua engine, so
        # a TEXMFHOME install can't shadow the staged classes/engine.
        env["TEXINPUTS"] = ".;" + env.get("TEXINPUTS", "")
        env["LUAINPUTS"] = ".;" + env.get("LUAINPUTS", "")

        pdf = os.path.join(tmp, "catalog.pdf")
        rc = 0
        for _ in range(2):
            proc = subprocess.run(
                [LUALATEX, "-interaction=nonstopmode", "-halt-on-error",
                 "-shell-escape", "catalog.tex"],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180, env=env)
            rc = proc.returncode
        ok = rc == 0 and os.path.exists(pdf)
        check("catalog builds (bank.cls + \\printbankcatalog)", ok,
              "\n".join((proc.stdout or "").splitlines()[-8:]))
        if not ok:
            return 1

        text = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        text = re.sub(r"-\s*\n\s*", "", text)

        check("problem stem renders", "CATSTEMNEEDLE" in text)
        check("solution renders (catalog shows solutions)", "CATSOLNEEDLE" in text)
        check("both parts render", "CATPARTONE" in text and "CATPARTTWO" in text)
        # The regression: labels must be self-contained "(a)"/"(b)", never "0a"/"0b".
        check("part labels render as (a)/(b)",
              "(a)" in text and "(b)" in text, "expected (a) and (b) part labels")
        check("no '0a.'/'0b.' label (question-counter regression)",
              not re.search(r"\b0[a-c]\.", text),
              "found a 0<letter>. label -- \\partlabel leaked the unset \\thequestion")
        return 1 if _FAIL else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    rc = main()
    print("\n%d passed, %d failed" % (_PASS, _FAIL))
    sys.exit(rc)
