#!/usr/bin/env python3
r"""
A tagged key conforms to PDF/UA-2, part solutions included.

Every shown {partsolution} used to cost a tagged key five failed checks, and
nothing reported it. The frame around a solution (the tint and the left accent)
is a \parbox, and it is assembled in a box register with no paragraph open. The
kernel's \parbox tagging assumes one is: it ended the innermost open structure,
which inside the exam-class {parts} list is the part's <LBody>, and the frame's
<Div> and the paragraph after it became children of the <LI>. veraPDF reports
that as ISO 32005 Table 5 LI-P (two checks), LI-Part, P-P and P-Part. The
inline layout did the same for a whole-problem {solution}. The frame is tagged
as an artifact now (\texlib@acc@artifactbegin in texlib-solutions.sty).

Three things kept it out of sight:

  * `smoke_test.py --accessible` builds each document's default copy, and a
    hidden solution is typeset into a discarded box with tagging suspended.
  * The builder writes its veraPDF report for the base tagged copy only.
  * No template or fixture in this repository uses {partsolution}.

So this builds one exam four ways with tagging on (the student copy and the
`solutions', `solutions-inline' and `instructor' variants, with the macros the
builder injects) and asserts, for each:

  * no TeX error in the log. The engine exits 0 after recovering from one.
  * veraPDF, flavour ua2: no failed check.
  * every list item is a label and then a body. This is the defect itself, read
    off the structure tree with pypdf, so it is still asserted on a machine
    with no veraPDF.
  * a key carries the solutions' text and the student copy does not, so a
    build that stops showing solutions cannot pass as a key.

The fixture's solutions end in running text on purpose. A body that ends in a
display or a list is a separate defect with its own fixes (the missing \par
before the box closes: PR #182 for a hidden solution, PR #281 for a shown one),
and it fails on the student copy too.

Soft-skips (exit 0) without lualatex, and skips the veraPDF or the pypdf
assertions when that tool is missing, like the other real-build tests. veraPDF
is found with find_verapdf(), since its installer does not put it on PATH.

Run:  python test_solution_tagged_conformance.py   (exit 0 ok/skipped, 1 on a failure)
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
import texlib_build as _build  # noqa: E402
import texlib_buildspec as _spec  # noqa: E402

LUALATEX = shutil.which("lualatex")
VERAPDF = _spec.find_verapdf()
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# The four tagged copies a build of this exam can produce: (name, the macro the
# builder injects for it, whether it shows solutions). The student copy is the
# base compile, which injects nothing. `solutions-inline' is the inline layout
# asked for outright.
COPIES = (
    ("student", "", False),
    ("solutions", _build.VARIANT_MACROS["solutions"], True),
    ("solutions-inline", _build.VARIANT_MACROS["solutions-inline"], True),
    ("instructor", _build.VARIANT_MACROS["instructor"], True),
)

# One word per solution, and one the student copy prints as well.
SOLUTION_WORDS = ("PARTSOLA", "PARTSOLB", "PARTSOLC", "WHOLESOL", "AFTERSOL", "CHOICESOL")
QUESTION_WORD = "TRAILING"

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

# The part solutions are the subject: one with rubric lines (the instructor copy
# sets them in a minipage under the answer), one of two paragraphs, and one
# followed by more of its part, which the defect also moved out of the <LBody>.
# The whole-problem solutions cover the same frame at problem level, in the
# side-by-side multiple-choice key as well.
BANK_TEX = r"""\begin{problem}{choice}[topic=choice]
	Which is $2 + 2$?
	\begin{choices}
		\choice $3$
		\CorrectChoice $4$
		\choice $5$
		\choice $6$
	\end{choices}
	\begin{solution}
		CHOICESOL $2 + 2 = 4$.
	\end{solution}
\end{problem}

\begin{problem}{parts}[topic=parts]
	Factor each.
	\begin{parts}
		\ppart $x^{2} - 9$
			\begin{partsolution}
				PARTSOLA $(x - 3)(x + 3)$.
				\rubric{1}{names the pattern}
				\rubric{1}{factors}
			\end{partsolution}
			\workbox{1}
		\ppart $x^{2} - 1$
			\begin{partsolution}
				PARTSOLB $(x - 1)(x + 1)$.

				A second paragraph of the same answer.
			\end{partsolution}
			\workbox{1}
		\ppart $x^{2} - 4$
			\begin{partsolution}
				PARTSOLC $(x - 2)(x + 2)$.
			\end{partsolution}
			TRAILING the part goes on after its answer.
			\workbox{1}
	\end{parts}
\end{problem}

\begin{problem}{whole}[topic=whole]
	Factor $x^{2} - 16$.

	\begin{solution}
		WHOLESOL $(x - 4)(x + 4)$.
		\rubric{5}{names the pattern}
		\rubric{5}{factors}
	\end{solution}
\end{problem}

\begin{problem}{after}[topic=after]
	Evaluate $1 + 1$.

	\begin{solution}
		AFTERSOL $2$.
	\end{solution}
\end{problem}
"""

EXAM_TEX = r"""\documentclass[exam-number=1, points=30]{autoexam}
\loadbank{bank.tex}
\begin{document}
\maketitle
\begin{mcproblems}
	\problem[4]{topic=choice}
\end{mcproblems}
\begin{problems}
	\problem[2,2,2]{topic=parts}
	\problem[10]{topic=whole}
	\problem[10]{topic=after}
\end{problems}
\end{document}
"""

FAILED_RULE_RE = re.compile(
    r'<rule specification="[^"]*" clause="([^"]+)" testNumber="\d+" '
    r'status="failed" failedChecks="(\d+)"')
CHECKS_RE = re.compile(r'passedChecks="(\d+)" failedChecks="(\d+)"')


def log(msg: str) -> None:
    print(msg, flush=True)


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


def build(tmp: str, jobname: str, macro: str, timeout: int = 300) -> tuple[str, list[str]]:
    """-> (pdf path, the log's error lines). No -halt-on-error: a nonstopmode
    build recovers from a tagging error, exits 0 and reports it only in its
    log, and that log is what is read here."""
    cmd = [LUALATEX, "-interaction=nonstopmode", "-shell-escape",
           f"-jobname={jobname}",
           f"{_spec.ACCESSIBLE_MACRO}{macro}\\input{{doc.tex}}"]
    # Two passes that RAN. On Windows luaotfload's cache probe can lose a race
    # with another engine and end the run before LaTeX starts, and a tagged PDF
    # from a single pass can fail veraPDF on its last page (tagpdf numbers the
    # parent tree from the previous pass's page count).
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


def verapdf(pdf: str) -> tuple[int, int, list[str]]:
    """-> (passed checks, failed checks, ["<clause> x<checks>", ...]).

    veraPDF exits 0 for a conforming file and 1 for a non-conforming one, and
    writes a report either way; only an exit above 1 is a tool error."""
    proc = subprocess.run(_spec.verapdf_report_cmd(VERAPDF, pdf, "xml"),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=300)
    out = proc.stdout or ""
    counts = CHECKS_RE.search(out)
    if proc.returncode > 1 or counts is None:
        raise RuntimeError(
            f"veraPDF exit {proc.returncode}: {out.strip()[:200]}")
    rules = [f"{clause} x{n}" for clause, n in FAILED_RULE_RE.findall(out)]
    return int(counts.group(1)), int(counts.group(2)), rules


def _obj(x):
    return x.get_object() if hasattr(x, "get_object") else x


def _role(elem) -> str:
    """The standard structure type an element resolves to. The LaTeX tagging
    code writes names of its own ("item", "itembody") in a namespace whose
    /RoleMapNS maps each to a standard type."""
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


def list_items(reader) -> list[list[str]]:
    """-> the child structure types of every <LI>, in document order."""
    root = _obj(reader.trailer["/Root"].get("/StructTreeRoot"))
    if root is None:
        raise RuntimeError("the PDF has no structure tree")

    def children(node):
        kids = _obj(node.get("/K"))
        if kids is None:
            return []
        kids = kids if isinstance(kids, list) else [kids]
        # Marked-content ids are integers; marked-content and object
        # references are dictionaries with no /S.
        return [k for k in map(_obj, kids)
                if hasattr(k, "get") and k.get("/S") is not None]

    items: list[list[str]] = []
    pending = list(reversed(children(root)))
    while pending:
        elem = pending.pop()
        kids = children(elem)
        if _role(elem) == "LI":
            items.append([_role(k) for k in kids])
        pending.extend(reversed(kids))
    return items


def main() -> int:
    if LUALATEX is None:
        log("SKIP: lualatex not found")
        return 0
    if VERAPDF is None and PdfReader is None:
        log("SKIP: neither veraPDF nor pypdf found")
        return 0
    if VERAPDF is None:
        log("SKIP (veraPDF assertions): veraPDF not found")
    if PdfReader is None:
        log("SKIP (structure and text assertions): pypdf not installed")

    tmp = tempfile.mkdtemp(prefix="texlib_taggedconf_")
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

        for copy, macro, is_key in COPIES:
            log(f"tagged {copy} copy")
            pdf, errors = build(tmp, copy.replace("-", "_"), macro)
            check(f"{copy}: no TeX errors", not errors, "; ".join(errors[:3]))

            if VERAPDF is not None:
                passed, failed, rules = verapdf(pdf)
                check(f"{copy}: PDF/UA-2, no failed checks",
                      failed == 0 and passed > 0,
                      f"{failed} failed checks ({', '.join(rules)})" if failed
                      else "veraPDF ran no checks")

            if PdfReader is not None:
                reader = PdfReader(pdf)
                items = list_items(reader)
                bad = [(i, kids) for i, kids in enumerate(items, 1)
                       if kids != ["Lbl", "LBody"]]
                check(f"{copy}: every list item is a label and a body",
                      bool(items) and not bad,
                      "; ".join(f"item {i} of {len(items)} holds {', '.join(kids) or 'nothing'}"
                                for i, kids in bad[:4]) if bad
                      else "no list items found")

                text = "\n".join(pg.extract_text() or "" for pg in reader.pages)
                shown = [w for w in SOLUTION_WORDS if w in text]
                if is_key:
                    missing = [w for w in SOLUTION_WORDS if w not in text]
                    check(f"{copy}: shows every solution", not missing,
                          f"missing {', '.join(missing)}")
                else:
                    check(f"{copy}: shows no solution", not shown,
                          f"shows {', '.join(shown)}")
                check(f"{copy}: prints the questions", QUESTION_WORD in text)
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
    log("OK: the tagged student copy and all three tagged keys conform")
    return 0


if __name__ == "__main__":
    sys.exit(main())
