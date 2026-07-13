#!/usr/bin/env python3
"""
Real-build tests for course-metadata.sty's coursemeta.tex resolution — the two
behaviors the metadata fixture (tests/fixtures/Metadata) only exercises at
depth 0 and never at all:

  A1  DIRECTORY-WALK DEPTH. The engine walks `.`, `..`, `../..`, `../../..`
      (course-metadata.sty:232) for coursemeta.tex and records the prefix in
      \\GetCourseMetaDir. This builds a document TWO directories below a
      coursemeta.tex and asserts (a) a custom key minted in that coursemeta
      renders, (b) \\GetCourseMetaDir came back as "../../", and (c) a
      coursemeta-relative `preamble-file` (auto-loaded as
      \\GetCourseMetaDir+path) resolved from that depth. A broken walk finds no
      coursemeta and every marker vanishes.

  A2  CLASS-OPTION-OVER-COURSEMETA PRECEDENCE. Only asserted in comments
      (course-metadata.sty:83-88, :128); the classes apply \\@raw@classoptionslist
      metadata AFTER \\LoadCourseMeta so a document's class option wins. This sets
      a key in coursemeta.tex and overrides it with a class option, asserting the
      class-option value renders and the coursemeta value does NOT — for both a
      predefined key (course-title) and a custom (auto-vivified) key. Reverse the
      precedence and the coursemeta value leaks back.

Self-contained: the fixtures are written into a scratch tree (never touches
tests/fixtures/), and the shared .sty/.cls are COPIED into a comma-free _lib
dir there. That copy is deliberate — kpathsea cannot search a TEXINPUTS entry
containing a comma (the repo's OneDrive path has one), and the C:\\_texlibjunc
junction points at the LIVE checkout, not necessarily this one, so pointing
TEXINPUTS at the real root would compile against the wrong files.

Soft-skips (exit 0) if pdflatex or pdftotext is missing — matching the other
real-toolchain tests' degrade-don't-fail convention. -layout text extraction
works with either poppler's or xpdf's pdftotext (only -bbox needs poppler), so
any pdftotext on PATH is fine here.

Run:  python test_metadata_resolution.py     (exit 0 ok/skipped, 1 fail)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

TEXLIB_ROOT = os.path.dirname(os.path.abspath(__file__))

PDFLATEX = shutil.which("pdflatex")
PDFTOTEXT = shutil.which("pdftotext")

_PASS = 0
_FAIL = 0


def check(label, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def _copy_shared_into(lib: str) -> None:
    """Copy the TeXLib-root shared files (.sty/.lua/.cls) plus every module's
    .cls into `lib`, so a build pointed at `lib//` resolves them without going
    near the comma-containing repo root. Mirrors smoke_test.py's cwd-copy trick."""
    os.makedirs(lib, exist_ok=True)
    for entry in os.listdir(TEXLIB_ROOT):
        src = os.path.join(TEXLIB_ROOT, entry)
        if os.path.isfile(src) and entry.lower().endswith((".sty", ".lua", ".cls")):
            shutil.copy2(src, os.path.join(lib, entry))
    for entry in os.listdir(TEXLIB_ROOT):
        sub = os.path.join(TEXLIB_ROOT, entry)
        if not os.path.isdir(sub):
            continue
        for f in os.listdir(sub):
            if f.lower().endswith(".cls"):
                dest = os.path.join(lib, f)
                if not os.path.exists(dest):
                    shutil.copy2(os.path.join(sub, f), dest)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_text(lib: str, cwd: str, tex_name: str) -> str | None:
    """Compile tex_name with cwd=`cwd` and TEXINPUTS pointed at `lib`, then
    return the PDF's -layout text. None (with a printed log tail) on failure."""
    sep = ";" if os.name == "nt" else ":"
    env = os.environ.copy()
    env["TEXINPUTS"] = sep.join([".", lib.replace(os.sep, "/") + "//",
                                 env.get("TEXINPUTS", "")])
    jobname = os.path.splitext(tex_name)[0]
    try:
        r = subprocess.run(
            [PDFLATEX, "-interaction=nonstopmode", "-halt-on-error", tex_name],
            cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"        build error: {exc}")
        return None
    pdf = os.path.join(cwd, jobname + ".pdf")
    if r.returncode != 0 or not os.path.exists(pdf):
        tail = "\n".join((r.stdout or "").splitlines()[-15:])
        print(f"        build failed (rc={r.returncode}):\n{tail}")
        return None
    try:
        t = subprocess.run(
            [PDFTOTEXT, "-layout", pdf, "-"], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
        return t.stdout
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------------
# A1 — directory-walk depth + coursemeta-relative preamble-file resolution
# ---------------------------------------------------------------------------
def scenario_depth(lib: str, work: str) -> None:
    print("A1: directory-walk depth (document two dirs below coursemeta.tex)")
    # coursemeta.tex at the top; the compiling document two levels down.
    _write(os.path.join(work, "coursemeta.tex"), r"""
\MetaAllowCustomKeys
\metasetup{
  institution   = {Depth Test University},
  probe-key     = {DEPTHPROBEOK},
  preamble-file = {shared-preamble.tex},
}
""".lstrip())
    # A sibling of coursemeta.tex; the preamble-file key must resolve to it via
    # \GetCourseMetaDir even though the job runs two dirs below.
    _write(os.path.join(work, "shared-preamble.tex"),
           r"\newcommand{\PreambleMarker}{PREAMBLERESOLVEDOK}" + "\n")
    _write(os.path.join(work, "a", "b", "doc.tex"), r"""
\documentclass{article}
\usepackage{course-metadata}
\begin{document}
Probe:[\GetProbeKey]
Dir:[\GetCourseMetaDir]
Preamble:[\PreambleMarker]
\end{document}
""".lstrip())

    text = build_text(lib, os.path.join(work, "a", "b"), "doc.tex")
    if text is None:
        check("A1 build produced a PDF", False, "build/extract failed")
        return
    flat = "".join(text.split())   # join so pdftotext line wraps can't split a token
    check("custom key from a coursemeta 2 dirs up renders (walk found it)",
          "DEPTHPROBEOK" in flat, text)
    check("\\GetCourseMetaDir reports the 2-level prefix ../../",
          "Dir:[../../]" in flat, text)
    check("coursemeta-relative preamble-file resolved from depth 2",
          "PREAMBLERESOLVEDOK" in flat, text)


# ---------------------------------------------------------------------------
# A2 — class-option-over-coursemeta precedence
# ---------------------------------------------------------------------------
def scenario_precedence(lib: str, work: str) -> None:
    print("A2: class-option-over-coursemeta precedence")
    # coursemeta sets both keys to the LOSE value; the class options below must
    # override both (predefined course-title and an auto-vivified custom key).
    _write(os.path.join(work, "coursemeta.tex"), r"""
\MetaAllowCustomKeys
\metasetup{
  institution    = {Precedence Test University},
  instructor     = {Prof Example},
  course-subject = Math,
  course-number  = 101,
  course-title   = {COURSEMETALOSES},
  probe-key      = {COURSEMETALOSES},
}
""".lstrip())
    # didactic applies \@raw@classoptionslist metadata AFTER \LoadCourseMeta, so
    # the class options win. (article does not route class options to metadata;
    # a real class is required to exercise the documented precedence.)
    _write(os.path.join(work, "doc.tex"), r"""
\documentclass[course-title={CLASSTITLEWINS}, probe-key={CLASSPROBEWINS}]{didactic}
\begin{document}
Title:[\GetCourseTitle]
Probe:[\GetProbeKey]
\end{document}
""".lstrip())

    text = build_text(lib, work, "doc.tex")
    if text is None:
        check("A2 build produced a PDF", False, "build/extract failed")
        return
    flat = "".join(text.split())
    check("predefined key: class option overrides coursemeta course-title",
          "CLASSTITLEWINS" in flat, text)
    check("custom key: class option overrides coursemeta probe-key",
          "CLASSPROBEWINS" in flat, text)
    check("the overridden coursemeta value does NOT leak through",
          "COURSEMETALOSES" not in flat, text)


def main() -> int:
    print("TeXLib metadata resolution tests (course-metadata.sty)\n")
    if not PDFLATEX:
        print("  SKIP  pdflatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  pdftotext not found (content assertions need it).")
        return 0

    lib = tempfile.mkdtemp(prefix="texlib_meta_lib_")
    depth_work = tempfile.mkdtemp(prefix="texlib_meta_depth_")
    prec_work = tempfile.mkdtemp(prefix="texlib_meta_prec_")
    try:
        _copy_shared_into(lib)
        scenario_depth(lib, depth_work)
        scenario_precedence(lib, prec_work)
    finally:
        for d in (lib, depth_work, prec_work):
            shutil.rmtree(d, ignore_errors=True)

    print(f"\n{_PASS} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
