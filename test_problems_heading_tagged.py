#!/usr/bin/env python3
r"""
A \section* inside {problems} builds clean when tagged, sits outside the
question list in the structure tree, and is drawn where the normal copy draws
it.

A review sheet heads its runs of problems with headings of its own:

    \begin{problems}*
        \section*{Chapter 5: Review of Integration}
        \problem[][3]{...}

pbank_emit_section replays each heading where it stood, which is inside the
exam-class {questions} list. A tagged build of Math 182's exam reviews logged
"Something's wrong--perhaps a missing \item", "Missing number, treated as
zero" and "Illegal unit of measure" at \end{problems}, and tagpdf's "The
number of automatic begin (80) and end (81) text para hooks differ", once per
tagged copy. A heading before a section's first problem does that. A heading
between problems logs nothing, but its <Sect> is a child of the list's <L> and
every item after it a child of an <LI>, which veraPDF reports as ISO 32005
Table 5 L-Sect and LI-LI (25 failed checks on the Exam 1 review). The PDFs were
written all the same, and the normal copy was never affected.

A tagged build now opens the list at the first problem after a section's start
or a heading and closes it ahead of each heading (texlib-problembank.sty,
\pbank@qlist@open and \pbank@qlist@close). This builds one exam with tagging
off and on and asserts:

  * no TeX error in either log. Neither run uses -halt-on-error, because a
    nonstopmode run recovers from these errors and still writes its PDF.
  * veraPDF, flavour ua2: no failed check on the tagged copy.
  * no <L> has a <Sect> child and no <LI> an <LI> child, read off the
    structure tree with pypdf, so it is still asserted without veraPDF.
  * each heading, and each of "Problem 1." to "Problem 6.", is printed once in
    each copy and at the same page, x and y in both. The normal copy draws the
    heading inside the list, moved right by the list's left margin and spaced
    by the list's \parsep, \itemsep and \topsep, which the tagged copy
    reproduces outside it. The numbers also show that closing and reopening
    the list carries the question number across.

The document has a heading first in a starred section, one between two
problems on a page (so the rule between problems is due as the list reopens),
one after a \newpage, one between problems of a section with its own "Part"
heading, and one last in that section. The section's \extracredit is deferred
to its end, after that last heading, so the bonus is what reopens the list.

Soft-skips (exit 0) without lualatex, and skips the veraPDF, pypdf or pdftotext
assertions when that tool is missing, like the other real-build tests.

Run:  python test_problems_heading_tagged.py   (exit 0 ok/skipped, 1 on a failure)
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

try:
    import pypdf
except ImportError:  # pragma: no cover - optional dependency
    pypdf = None

LUALATEX = shutil.which("lualatex")
VERAPDF = _spec.find_verapdf()
# find_poppler and not shutil.which: under Git Bash the first pdftotext on PATH
# is Git's xpdf build, which has no -bbox and prints its usage text instead.
PDFTOTEXT = find_poppler("pdftotext")

BANK_TEX = r"""
\begin{problem}{one}[topic=a]
	ONESTEM Evaluate $1 + 1$.
\end{problem}
\begin{problem}{two}[topic=a]
	TWOSTEM Evaluate $2 + 2$.
\end{problem}
\begin{problem}{three}[topic=a]
	THREESTEM Evaluate $3 + 3$.
\end{problem}
\begin{problem}{four}[topic=a]
	FOURSTEM Evaluate $4 + 4$.
\end{problem}
\begin{problem}{five}[topic=b]
	FIVESTEM Evaluate $5 + 5$.
\end{problem}
\begin{problem}{six}[topic=b]
	SIXSTEM Evaluate $6 + 6$.
\end{problem}
"""

EXAM_TEX = r"""\documentclass[exam-number=1]{autoexam}
\loadbank{bank.tex}
\begin{document}
\begin{problems}*
	\section*{HEADFIRST opens the section}
	\problem[][1]{one}
	\problem[][1]{two}
	\section*{HEADMID between two problems}
	\problem[][1]{three}
	\newpage
	\section*{HEADPAGE after a page break}
	\problem[][1]{four}
\end{problems}
\begin{problems}
	\problem[4]{five}
	\section*{HEADPART in a section with its own heading}
	\problem[4]{six}
	\extracredit[2]{BONUSSTEM Evaluate $7 + 7$.}
	\section*{HEADBONUS over the bonus problem}
\end{problems}
\end{document}
"""

HEADINGS = ("HEADFIRST", "HEADMID", "HEADPAGE", "HEADPART", "HEADBONUS")
# Words located like the headings: the bonus problem's stem.
OTHER_MARKS = ("BONUSSTEM",)

# PDF points. The tagged copy reproduces the list's margin and spacing, so
# anything past rounding is a different position. Without the \hspace* the
# tagged headings stood 19.40 pt left of the normal ones, and without the
# spacing a heading or problem after one stood 4.48 pt (the list's \parsep)
# off.
TOLERANCE = 0.5

FAILED_RULE_RE = re.compile(
    r'<rule specification="[^"]*" clause="([^"]+)" testNumber="\d+" '
    r'status="failed" failedChecks="(\d+)"')
CHECKS_RE = re.compile(r'passedChecks="(\d+)" failedChecks="(\d+)"')
PAGE_RE = re.compile(r"<page [^>]*>(.*?)</page>", re.S)
WORD_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>([^<]*)</word>')


def log(msg: str) -> None:
    print(msg, flush=True)


def stage(tmp: str) -> None:
    """The library's root files and the Exams module, then the document. A
    copy rather than TEXINPUTS, which cannot hold a path with a comma."""
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
    for name, text in (("bank.tex", BANK_TEX), ("doc.tex", EXAM_TEX)):
        with open(os.path.join(tmp, name), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(text)


def build(tmp: str, jobname: str, tagged: bool,
          timeout: int = 300) -> tuple[str, list[str]]:
    """-> (pdf path, the log's error lines from the last pass)."""
    prefix = _spec.ACCESSIBLE_MACRO if tagged else ""
    cmd = [LUALATEX, "-interaction=nonstopmode", "-shell-escape",
           f"-jobname={jobname}", f"{prefix}\\input{{doc.tex}}"]
    # Two passes that RAN. On Windows luaotfload's cache probe can lose a race
    # with another engine and end the run before LaTeX starts, and a tagged PDF
    # from a single pass can fail veraPDF on its last page.
    passes = attempts = 0
    while passes < 2 and attempts < 5:
        attempts += 1
        proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        if not _spec.luaotfload_cache_aborted(proc.stdout):
            passes += 1
    pdf = os.path.join(tmp, f"{jobname}.pdf")
    if not os.path.exists(pdf):
        raise RuntimeError(f"{jobname}: no PDF")
    with open(os.path.join(tmp, f"{jobname}.log"), encoding="utf-8",
              errors="replace") as fh:
        errors = [ln.rstrip() for ln in fh if ln.startswith("! ")]
    return pdf, errors


def verapdf(pdf: str) -> tuple[int, list[str]]:
    """-> (failed checks, ["<clause> x<checks>", ...]). veraPDF exits 1 for a
    non-conforming file; only an exit above 1 is a tool error."""
    proc = subprocess.run(_spec.verapdf_report_cmd(VERAPDF, pdf, "xml"),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=300)
    out = proc.stdout or ""
    counts = CHECKS_RE.search(out)
    if proc.returncode > 1 or counts is None:
        raise RuntimeError(f"veraPDF exit {proc.returncode}: {out.strip()[:200]}")
    rules = [f"{clause} x{n}" for clause, n in FAILED_RULE_RE.findall(out)]
    return int(counts.group(2)), rules


def _obj(x):
    return x.get_object() if hasattr(x, "get_object") else x


def _role(elem) -> str:
    """The standard structure type an element resolves to through /RoleMapNS:
    the LaTeX tagging code writes names of its own ("list", "item")."""
    name, ns = elem.get("/S"), elem.get("/NS")
    for _ in range(8):
        ns = _obj(ns)
        if ns is None:
            break
        target = _obj((_obj(ns.get("/RoleMapNS")) or {}).get(name))
        if target is None:
            break
        if isinstance(target, list):
            name, ns = target[0], target[1]
        else:
            name, ns = target, None
    return str(name).lstrip("/")


def misplaced_children(pdf: str) -> list[str]:
    """-> one "<parent> > <child>" per <L> with a <Sect> child or <LI> with an
    <LI> child."""
    reader = pypdf.PdfReader(pdf)
    root = _obj(reader.trailer["/Root"].get("/StructTreeRoot"))
    if root is None:
        raise RuntimeError("the tagged PDF has no structure tree")

    def children(node):
        kids = _obj(node.get("/K"))
        if kids is None:
            return []
        kids = kids if isinstance(kids, list) else [kids]
        # Marked-content ids are integers, and marked-content and object
        # references are dictionaries with no /S.
        return [k for k in map(_obj, kids)
                if hasattr(k, "get") and k.get("/S") is not None]

    bad: list[str] = []
    pending = children(root)
    while pending:
        elem = pending.pop()
        kids = children(elem)
        parent = _role(elem)
        for kid in kids:
            child = _role(kid)
            if (parent, child) in (("L", "Sect"), ("LI", "LI")):
                bad.append(f"{parent} > {child}")
        pending.extend(kids)
    return bad


Word = tuple[int, float, float, str]   # (page, xMin, yMin, text)


def words(pdf: str) -> list[Word]:
    """-> every word, in reading order."""
    proc = subprocess.run([PDFTOTEXT, "-bbox", pdf, "-"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=60)
    found = []
    for page, body in enumerate(PAGE_RE.findall(proc.stdout or ""), 1):
        for x_min, y_min, word in WORD_RE.findall(body):
            found.append((page, float(x_min), float(y_min), word))
    return found


def landmarks(found: list[Word]) -> dict[str, list[tuple[int, float, float]]]:
    """-> {name: [(page, x, y), ...]} for each heading and for each problem
    label, named "Problem <n>" (autoexam prints "Problem 3.")."""
    marks: dict[str, list[tuple[int, float, float]]] = {}
    for i, (page, x, y, word) in enumerate(found):
        if word in HEADINGS or word in OTHER_MARKS:
            name = word
        elif word == "Problem" and i + 1 < len(found):
            name = "Problem " + found[i + 1][3].rstrip(".")
        else:
            continue
        marks.setdefault(name, []).append((page, x, y))
    return marks


def main() -> int:
    if LUALATEX is None:
        log("SKIP: lualatex not found")
        return 0
    if VERAPDF is None:
        log("SKIP (veraPDF assertions): veraPDF not found")
    if pypdf is None:
        log("SKIP (structure assertions): pypdf not importable")
    if PDFTOTEXT is None:
        log("SKIP (layout assertions): no poppler pdftotext (-bbox) found")

    tmp = tempfile.mkdtemp(prefix="texlib_problemsheading_")
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        log(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    try:
        stage(tmp)
        pdfs: dict[str, str] = {}
        for copy, tagged in (("normal", False), ("tagged", True)):
            log(f"{copy} copy")
            pdf, errors = build(tmp, copy, tagged)
            pdfs[copy] = pdf
            check(f"{copy}: no TeX error", not errors, "; ".join(errors[:4]))

        tagged = pdfs["tagged"]
        if VERAPDF is not None:
            failed, rules = verapdf(tagged)
            check("tagged: veraPDF ua2 reports no failed check", failed == 0,
                  f"{failed} failed: {', '.join(rules)}")
        if pypdf is not None:
            bad = misplaced_children(tagged)
            check("tagged: no heading inside a list, no item inside an item",
                  not bad, ", ".join(sorted(set(bad))) + f" ({len(bad)})")

        if PDFTOTEXT is not None:
            marks = {copy: landmarks(words(pdf)) for copy, pdf in pdfs.items()}
            want = (list(HEADINGS) + list(OTHER_MARKS)
                    + [f"Problem {n}" for n in range(1, 7)])
            for copy in ("normal", "tagged"):
                counts = ", ".join(f"{m} x{len(marks[copy].get(m, []))}"
                                   for m in want)
                check(f"{copy}: prints each heading, problems 1 to 6 and "
                      f"the bonus once",
                      all(len(marks[copy].get(m, [])) == 1 for m in want),
                      counts)
            for m in want:
                if (len(marks["normal"].get(m, [])) != 1
                        or len(marks["tagged"].get(m, [])) != 1):
                    continue
                (pn, xn, yn), = marks["normal"][m]
                (pt, xt, yt), = marks["tagged"][m]
                where = (f"normal p{pn} ({xn:.2f}, {yn:.2f}), "
                         f"tagged p{pt} ({xt:.2f}, {yt:.2f})")
                log(f"    {m}: {where}")
                check(f"{m}: at the same place in both copies",
                      pn == pt and abs(xn - xt) <= TOLERANCE
                      and abs(yn - yt) <= TOLERANCE, where)
        return report(failures)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
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
    log("OK: headings inside {problems} build clean tagged, outside the list, "
        "where the normal copy draws them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
