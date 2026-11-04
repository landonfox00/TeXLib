#!/usr/bin/env python3
r"""
A tagged {cols} sets its parts in two columns, as the normal copy does.

{cols} wraps its parts in multicols in every build. Until v0.7.4 an accessible
build skipped the multicols and set the parts in one column, and the comment
above the environment in Exams/texlib-autoexam.cls keeps that guard for a
toolchain whose multicol breaks under tagging. A tagged exam set in one column
conforms to PDF/UA-2 as well as one set in two: veraPDF validates the structure
tree and does not read where the text sits. `smoke_test.py --accessible` builds
examples/fixtures/Exams/cols-test.tex tagged and runs veraPDF on it, and that
check passes with the guard restored. This one fails.

It builds the fixture twice, staged in smoke_test.build_one's order: a normal
copy, and a tagged copy with the prefix the accessible gate injects
(accessible_macro_for in texlib_buildspec.py). It reads each copy's word boxes
with `pdftotext -bbox` and asserts, for each copy:

  * pdfinfo reports the tagged copy as tagged and the normal copy as untagged,
    so two untagged builds cannot pass as the pair;
  * each of the four part markers is on the page once;
  * parts a and b start at least MIN_GAP pt to the left of parts c and d.

The normal copy is the control. If it fails, the fixture or {cols} itself has
stopped setting two columns; if the tagged copy alone fails, tagging lost them.

Measured on TeX Live 2026 (multicol v2.0b, tagpdf 1.0e), 2026-10-08: parts a
and b start at x = 166.61 pt and parts c and d at 407.28 pt in the normal copy,
164.79 pt and 405.46 pt in the tagged copy, 240.67 pt apart in both. With the
guard restored the tagged copy sets all four at 164.79 pt.

The two copies are compared by column and never by coordinate. The text after a
part's "(2 points)" starts 1.82 pt further left in the tagged copy, by design:
in an accessible build texlib-assessment.sty prints the points itself and
follows them with an interword space, where exam.cls follows them with
\enspace.

Needs lualatex and poppler's pdftotext and pdfinfo. Soft-skips (exit 0) when
lualatex or pdftotext is missing, like the other real-build tests, and skips
the tagged/untagged assertions when pdfinfo is. accessible.yml checks for both
poppler tools before it runs this.

Run:  python test_cols_tagged_layout.py   (exit 0 ok/skipped, 1 on a failure)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEXLIB_ROOT, "Sublime", "texlib"))
sys.path.insert(0, os.path.join(TEXLIB_ROOT, "Sublime"))
import texlib_buildspec as _spec  # noqa: E402
from _testkit import find_poppler  # noqa: E402

LUALATEX = shutil.which("lualatex")
# find_poppler and not shutil.which: under Git Bash the first pdftotext on PATH
# is Git's xpdf build, which has no -bbox and prints its usage text instead.
PDFTOTEXT = find_poppler("pdftotext")
PDFINFO = find_poppler("pdfinfo")

FIXTURE_DIR = os.path.join(TEXLIB_ROOT, "examples", "fixtures", "Exams")
FIXTURE = "cols-test.tex"
CLASS_HOME = os.path.join(TEXLIB_ROOT, "Exams")

# The word that opens each part's text, by the column the fixture sets it in:
# multicols fills the left column first, so a and b are left and c and d right.
LEFT = ("COLSPARTAMARK", "COLSPARTBMARK")
RIGHT = ("COLSPARTCMARK", "COLSPARTDMARK")

# PDF points. The columns start 240.67 pt apart; one column puts all four
# markers at one x, so any threshold between the two separates them.
MIN_GAP = 72.0

WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="[\d.]+"[^>]*>([^<]*)</word>')


def log(msg: str) -> None:
    print(msg, flush=True)


def skip(reason: str) -> int:
    log(f"SKIP: {reason}")
    return 0


def stage(tmp: str) -> None:
    """Fill the build directory in smoke_test.build_one's order: the fixture's
    own directory first, then the class's home module, then the shared files at
    the root. A file already there is never overwritten, so the fixture
    directory wins a name clash here as it does in the gate."""
    for src_dir in (FIXTURE_DIR, CLASS_HOME):
        for entry in os.listdir(src_dir):
            src, dest = os.path.join(src_dir, entry), os.path.join(tmp, entry)
            if os.path.isfile(src) and not os.path.exists(dest):
                shutil.copy2(src, dest)
    for entry in os.listdir(TEXLIB_ROOT):
        src, dest = os.path.join(TEXLIB_ROOT, entry), os.path.join(tmp, entry)
        if (os.path.isfile(src) and not os.path.exists(dest)
                and entry.lower().endswith((".sty", ".lua", ".cls"))):
            shutil.copy2(src, dest)


def build(tmp: str, jobname: str, prefix: str, timeout: int = 300) -> str:
    """Two passes that ran -> the PDF's path. The jobname is pinned because
    \\DocumentMetadata opens a support file before the \\input runs, and LuaTeX
    would name the output after that file."""
    arg = f"{prefix}\\input{{{FIXTURE}}}" if prefix else FIXTURE
    cmd = [LUALATEX, "-interaction=nonstopmode", "-halt-on-error",
           "-shell-escape", f"--jobname={jobname}", arg]
    passes = attempts = 0
    out, code = "", 0
    while passes < 2 and attempts < 5:
        attempts += 1
        proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout)
        out, code = proc.stdout or "", proc.returncode
        # On Windows luaotfload's cache probe can lose a race with another
        # engine and end the run before LaTeX starts. Nothing was typeset, so
        # it is not a pass and not this document's failure.
        if _spec.luaotfload_cache_aborted(out):
            continue
        if code != 0:
            break
        passes += 1
    pdf = os.path.join(tmp, f"{jobname}.pdf")
    if passes < 2 or not os.path.exists(pdf):
        tail = "\n".join(out.splitlines()[-12:])
        raise RuntimeError(f"{jobname}: lualatex exit={code}\n{tail}")
    return pdf


def is_tagged(pdf: str) -> bool:
    """pdfinfo's `Tagged:' line, which reads /MarkInfo /Marked."""
    proc = subprocess.run([PDFINFO, pdf], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60)
    found = re.search(r"^Tagged:\s*(\w+)", proc.stdout or "", re.MULTILINE)
    if found is None:
        raise RuntimeError(f"pdfinfo printed no Tagged line for {pdf}")
    return found.group(1) == "yes"


def marker_x(pdf: str) -> dict[str, list[float]]:
    """-> {marker: [xMin of each word that is exactly that marker]}."""
    proc = subprocess.run([PDFTOTEXT, "-bbox", pdf, "-"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=60)
    found: dict[str, list[float]] = {m: [] for m in LEFT + RIGHT}
    for x_min, word in WORD_RE.findall(proc.stdout or ""):
        if word in found:
            found[word].append(float(x_min))
    return found


def main() -> int:
    if LUALATEX is None:
        return skip("lualatex not found")
    if PDFTOTEXT is None:
        return skip("no poppler pdftotext (-bbox support) found")
    if PDFINFO is None:
        log("SKIP (tagged/untagged assertions): no poppler pdfinfo found")

    tmp = tempfile.mkdtemp(prefix="texlib_colslayout_")
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        log(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    try:
        stage(tmp)
        tagging = _spec.accessible_macro_for(os.path.join(tmp, FIXTURE))
        for copy, prefix in (("normal", ""), ("tagged", tagging)):
            log(f"{copy} copy")
            pdf = build(tmp, copy, prefix)

            if PDFINFO is not None:
                want = copy == "tagged"
                check(f"{copy}: the PDF is {'tagged' if want else 'untagged'}",
                      is_tagged(pdf) == want)

            xs = marker_x(pdf)
            counts = ", ".join(f"{m} x{len(xs[m])}" for m in LEFT + RIGHT)
            once = all(len(xs[m]) == 1 for m in LEFT + RIGHT)
            check(f"{copy}: prints each of the four parts once", once, counts)
            if not once:
                continue

            left = [xs[m][0] for m in LEFT]
            right = [xs[m][0] for m in RIGHT]
            where = ("a {:.2f}, b {:.2f}, c {:.2f}, d {:.2f} pt"
                     .format(*left, *right))
            log(f"    parts start at x = {where}")
            gap = min(right) - max(left)
            check(f"{copy}: parts a and b stand left of parts c and d",
                  gap >= MIN_GAP,
                  f"{where}; the columns are {gap:.2f} pt apart, "
                  f"expected at least {MIN_GAP:.0f}")
        return report(failures)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        # A tagged {cols} that stops building lands here, so this is a failure
        # and never a skip.
        log(f"FAIL: could not build or read a copy -- "
            f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def report(failures: list[str]) -> int:
    if failures:
        log("")
        for f in failures:
            log(f"FAIL: {f}")
        return 1
    log("OK: {cols} sets two columns in the normal and in the tagged copy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
