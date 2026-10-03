#!/usr/bin/env python3
r"""
A tagged key conforms to PDF/UA-2, part solutions included, and reads each
solution's header before its answer.

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

A key is also read for the ORDER of each solution, which veraPDF does not
check. Both solution environments typeset the body before the header, and a
structure element lists its children in the order they were created, so the
tree used to have the answer and then "Solution." while the page drew the
header above the answer. Every solution a key shows is asserted to be one <Div>
that reads "Solution." and then the answer. The `solutions' key is built once
more with \texlibpartsolheader emptied, and there a part solution's <Div>
starts at its answer. The assertion needs the text under each structure
element, which is the text of its marked-content sequences. pypdf's
extract_text() returns a page's text with no marked-content ids, so
marked_text() walks each page's content stream itself and decodes the strings
with the font's /ToUnicode map. pdfminer would do the same and is not a
dependency of this repository.

Every copy is read for the rubric as well. A whole-problem {solution} sets its
rubric in the footer under the answer, and the instructor copy used to print it
a second time, on the "Solution." line: the call the footer had replaced came
back in a merge, and the page then had three rubric boxes for the fixture's two
rubrics. Each rubric line is asserted to be printed once by the copy that shows
rubrics and by no other copy.

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

# For the order of a solution: what \texlibsolheader prints, and the copy whose
# part solutions have no header line.
HEADER = "Solution."
NO_HEADER_COPY = "solutions-noheader"
# What a copy that shows rubrics prints of them, and how many times: the
# heading once for each of the two solutions that carry a rubric (a part
# solution and a whole-problem one), and each of their lines once. Compared
# with the white space taken out, because a label's thin space is a kern and a
# text extractor may or may not report it as a space.
RUBRIC_TEXT = (("Rubric:", 2),
               ("[1pt]namesthepattern", 1), ("[1pt]factors", 1),
               ("[5pts]namesthepattern", 1), ("[5pts]factors", 1))

# The four tagged copies a build of this exam can produce: (name, the macro the
# builder injects for it, whether it shows solutions). The student copy is the
# base compile, which injects nothing. `solutions-inline' is the inline layout
# asked for outright.
COPIES = (
    ("student", "", False),
    ("solutions", _build.VARIANT_MACROS["solutions"], True),
    ("solutions-inline", _build.VARIANT_MACROS["solutions-inline"], True),
    ("instructor", _build.VARIANT_MACROS["instructor"], True),
    # A fifth, which no build of this exam produces: the `solutions' key of a
    # document that empties \texlibpartsolheader. texlib-corepkg sets that
    # hook with \providecommand, so a definition made before the class stands.
    (NO_HEADER_COPY,
     _build.VARIANT_MACROS["solutions"] + r"\def\texlibpartsolheader{}", True),
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


_BFCHAR_RE = re.compile(r"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE_RE = re.compile(r"beginbfrange(.*?)endbfrange", re.S)
_HEX_RE = re.compile(r"<([0-9A-Fa-f\s]*)>")
_RANGE_RE = re.compile(
    r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:\[(.*?)\]|<([0-9A-Fa-f]+)>)", re.S)


def _utf16(hexdigits: str) -> str:
    return bytes.fromhex(hexdigits).decode("utf-16-be", "replace")


def _tounicode(font) -> dict[int, str] | None:
    """A font's /ToUnicode CMap as {character code: text}, or None when the
    font has none. Both forms a CMap can take are read: single codes (bfchar)
    and ranges (bfrange), a range giving either its first target or a list."""
    cmap = _obj(font.get("/ToUnicode"))
    if cmap is None:
        return None
    data = cmap.get_data().decode("latin-1")
    table: dict[int, str] = {}
    for block in _BFCHAR_RE.findall(data):
        codes = _HEX_RE.findall(block)
        for code, target in zip(codes[0::2], codes[1::2]):
            table[int(code, 16)] = _utf16(target)
    for block in _BFRANGE_RE.findall(data):
        for low, high, targets, first in _RANGE_RE.findall(block):
            low, high = int(low, 16), int(high, 16)
            if first:
                for offset in range(high - low + 1):
                    table[low + offset] = _utf16(
                        format(int(first, 16) + offset, f"0{len(first)}x"))
            else:
                for offset, target in enumerate(_HEX_RE.findall(targets)):
                    table[low + offset] = _utf16(target)
    return table


def marked_text(reader) -> dict[tuple[int, int], str]:
    """-> {(page's object number, MCID): the text shown in that marked-content
    sequence}.

    A page's content stream brackets each tagged run of text between
    `/Tag <</MCID n>> BDC' and `EMC', and the structure tree refers to the run
    by its page and that number. Text shown outside such a sequence, or in one
    with no MCID (an artifact), is dropped."""
    out: dict[tuple[int, int], list[str]] = {}
    for page in reader.pages:
        contents = page.get_contents()
        if contents is None:
            continue
        number = page.indirect_reference.idnum
        fonts = {}
        resources = _obj(page.get("/Resources")) or {}
        for name, font in (_obj(resources.get("/Font")) or {}).items():
            font = _obj(font)
            # A composite font (what LuaTeX embeds for OpenType) is addressed
            # by two-byte codes, a simple font by one.
            fonts[name] = (_tounicode(font), 2 if font.get("/Subtype") == "/Type0" else 1)
        table, width = None, 1
        open_mcids: list[int | None] = []
        for operands, operator in contents.operations:
            if operator == b"BDC":
                props = _obj(operands[1]) if len(operands) > 1 else None
                mcid = props.get("/MCID") if hasattr(props, "get") else None
                open_mcids.append(None if mcid is None else int(mcid))
            elif operator == b"BMC":
                open_mcids.append(None)
            elif operator == b"EMC":
                if open_mcids:
                    open_mcids.pop()
            elif operator == b"Tf":
                table, width = fonts.get(operands[0], (None, 1))
            elif operator in (b"Tj", b"TJ", b"'", b'"'):
                if not open_mcids or open_mcids[-1] is None:
                    continue
                shown = operands[-1]
                for piece in shown if isinstance(shown, list) else [shown]:
                    raw = getattr(piece, "original_bytes", None)
                    if raw is None:      # a number: TJ's spacing adjustment
                        continue
                    if table is None:
                        text = raw.decode("latin-1")
                    else:
                        text = "".join(
                            table.get(int.from_bytes(raw[i:i + width], "big"), "?")
                            for i in range(0, len(raw), width))
                    out.setdefault((number, open_mcids[-1]), []).append(text)
    return {key: "".join(pieces) for key, pieces in out.items()}


def solution_groups(reader) -> dict[str, str]:
    """-> for each solution word, the text of the innermost <Div> that holds
    it, read in the order of the structure tree and with white space removed;
    "" for a word that no <Div> holds.

    The order of the tree is the order a screen reader reads in. It is not the
    order of the page's content stream, and for a solution the two used to
    disagree."""
    root = _obj(reader.trailer["/Root"].get("/StructTreeRoot"))
    if root is None:
        raise RuntimeError("the PDF has no structure tree")
    text = marked_text(reader)
    divs: list[str] = []

    def page_of(node, inherited):
        ref = node.raw_get("/Pg") if "/Pg" in node else None
        return getattr(ref, "idnum", inherited)

    def read(elem, page) -> str:
        page = page_of(elem, page)
        kids = _obj(elem.get("/K"))
        if kids is None:
            return ""
        pieces = []
        for kid in map(_obj, kids if isinstance(kids, list) else [kids]):
            if isinstance(kid, int):
                pieces.append(text.get((page, int(kid)), ""))
            elif not hasattr(kid, "get"):
                continue
            elif kid.get("/S") is not None:
                pieces.append(read(kid, page))
            elif kid.get("/Type") == "/MCR":
                pieces.append(text.get((page_of(kid, page), int(kid["/MCID"])), ""))
        whole = "".join("".join(pieces).split())
        if elem.get("/S") is not None and _role(elem) == "Div":
            divs.append(whole)
        return whole

    read(root, None)
    groups = {}
    for word in SOLUTION_WORDS:
        holding = [div for div in divs if word in div]
        groups[word] = min(holding, key=len) if holding else ""
    return groups


def rubric_misprints(reader, shown: bool) -> list[str]:
    """-> one line for each piece of RUBRIC_TEXT that the pages do not print
    the right number of times: as often as RUBRIC_TEXT says in a copy that
    shows rubrics, and never in a copy that does not."""
    squeezed = "".join(
        "".join(pg.extract_text() or "" for pg in reader.pages).split())
    wrong = []
    for piece, times in RUBRIC_TEXT:
        want = times if shown else 0
        found = squeezed.count(piece)
        if found != want:
            wrong.append(f"{piece!r} is printed {found} times, not {want}")
    return wrong


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
                if is_key:
                    # One <Div> to a solution, the header its first words. In
                    # the copy whose part solutions have no header line, a part
                    # solution (the PARTSOL words) starts at its answer.
                    groups = solution_groups(reader)
                    misread = []
                    for word, group in groups.items():
                        bare = copy == NO_HEADER_COPY and word.startswith("PARTSOL")
                        alone = sum(w in group for w in SOLUTION_WORDS) == 1
                        if not (alone and group.startswith(word if bare else HEADER)):
                            misread.append(f"{word} is in no <Div>" if not group else
                                           f"{word}'s <Div> reads {group[:48]!r}")
                    check(f"{copy}: each solution is one element, header first",
                          not misread, "; ".join(misread))
                # The rubric: once where rubrics are shown, which is the copy
                # whose macro raises \ShowRubric, and nowhere else.
                shows_rubric = r"\ShowRubric" in macro
                wrong = rubric_misprints(reader, shows_rubric)
                check(f"{copy}: " + ("prints each rubric line once" if shows_rubric
                                     else "prints no rubric"),
                      not wrong, "; ".join(wrong))

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
    log("OK: the tagged student copy and all four tagged keys conform")
    return 0


if __name__ == "__main__":
    sys.exit(main())
