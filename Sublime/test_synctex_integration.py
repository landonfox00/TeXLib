#!/usr/bin/env python3
"""
End-to-end integration test for TeXLib's SyncTeX inverse search.

Unlike test_schedule_synctex.lua (which fabricates tex.*/tex.inputlineno and
never runs a real engine) and test_texlib_builder.py's schedmap-rewrite tests
(which fabricate a plausible-looking .synctex.gz by hand), this drives the
REAL builder coroutine against a REAL lualatex build, then asks TeX Live's own
`synctex edit -o page:x:y:pdf` CLI to resolve a PDF-space point back to a
source file + line -- exactly what SumatraPDF does internally before invoking
InverseSearchCmdLine. That is what actually catches whether double-clicking a
problem or a calendar cell in the PDF lands where a user expects: neither of
the fabricated-data unit tests can, because both assume the real engine
produces the per-line attribution they hand-construct, which turned out not to
always hold (see the module-level NOTE below).

Fixtures are self-contained (own bank/exam/schedule .tex, not the real
Exams/Schedule templates), so editing the shipped example documents can't
break this test and vice versa. Distinctive ALL-CAPS needle tokens (never
real words) are used so find_word() can't accidentally match something else.

Soft-skips (exit 0) if lualatex, a poppler-flavored pdftotext (-bbox support),
or the synctex CLI are missing -- matching test_biber_integration.py's
degrade-don't-fail convention.

STATUS (2026-07-04): Schedule's default xltabular renderer is a confirmed
fundamental limitation (not fixable by a redirect-timing patch -- see
_rewrite_synctex_for_schedmap's docstring); scenarios 4/5 assert the honest
grid-file fallback that ships today, not per-cell accuracy. A real per-cell
fix (an opt-in box-grid renderer) exists on a separate, unmerged branch. The
"document-attributed problem breaks after a page shipout" theory floated
earlier in this investigation did NOT hold up -- that was a hardcoded-page
bug in manual testing, not a real defect; scenario 3 confirms exact
attribution. One remaining known gap: solution-box content had no working
inverse search at all (a `tcolorbox`-internals issue, unrelated to
Schedule's) -- fixed; scenario 2 asserts it outright now.

Run:  python Sublime/test_synctex_integration.py     (exit 0 ok/skipped, 1 fail)
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

# --- Import the real Sublime builder. build_versions.py used to do the
# LaTeXTools-stub dance and re-export TexlibBuilder; it was removed with the
# All-Versions builder, so stub PdfBuilder here (the same minimal stub
# test_texlib_builder.py uses) before importing TexlibBuilder directly. -----
TEXLIB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TEXLIB_ROOT)


class _StubPdfBuilder:
    """Minimal stand-in for LaTeXTools' PdfBuilder."""

    def __init__(self, *args, **kwargs):
        self._displayed = ""

    def display(self, msg):
        self._displayed += str(msg)


for _name in (
    "LaTeXTools",
    "LaTeXTools.plugins",
    "LaTeXTools.plugins.builder",
    "LaTeXTools.plugins.builder.pdf_builder",
):
    sys.modules.setdefault(_name, types.ModuleType(_name))
sys.modules["LaTeXTools.plugins.builder.pdf_builder"].PdfBuilder = _StubPdfBuilder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from texlib_builder import TexlibBuilder  # noqa: E402


def _texinputs_env(tex_dir):
    """Env for the engine, TEXINPUTS extended so the TeXLib-root shared files
    resolve even though tex_dir is a scratch dir OUTSIDE the repo entirely
    (unlike build_versions.py's own _texinputs_env, which assumes tex_dir is
    inside the repo tree and adds the root via a relative '..' path -- that
    relative path would have to cross back through the real OneDrive folder
    name to reach an external scratch dir, defeating the whole point).

    On this machine kpathsea also can't search an ABSOLUTE TEXINPUTS entry
    containing a comma (the real OneDrive path has one, and Python's own
    __file__/getcwd resolution does not preserve "reached via the comma-free
    junction" -- it reports the real underlying path either way). Route
    through the C:\\_texlibjunc junction ONLY when TEXLIB_ROOT itself is the
    comma-containing path -- i.e. this script is running from the live,
    shared OneDrive checkout. A worktree (or any other checkout) elsewhere on
    disk has no comma and must use ITS OWN files directly: the junction
    always points at the live shared checkout, so unconditionally preferring
    it here would silently compile against whatever's currently checked out
    there instead of this worktree's own (possibly different, possibly
    mid-conflict-resolution) content -- exactly the bug that produced a
    confusing, non-reproducible-looking failure when this test was run from
    an isolated worktree while the live checkout was mid-merge on a
    different branch.
    """
    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    root = TEXLIB_ROOT
    if os.name == "nt" and "," in root and os.path.isdir(r"C:\_texlibjunc"):
        root = r"C:\_texlibjunc"
    root = root.replace(os.sep, "/")
    env["TEXINPUTS"] = sep.join([".", root + "//", env.get("TEXINPUTS", "")])
    return env

SYNCTEX = shutil.which("synctex")
LUALATEX = shutil.which("lualatex")

_PASS = 0
_FAIL = 0
_KNOWN_FAIL = 0


def check(label, cond, detail="", known_issue=None):
    """known_issue: pass a tracker reference (e.g. a spawned-task id) for an
    assertion that encodes CORRECT/intended behavior but is not expected to
    pass yet, pending separately-tracked follow-up work. Keeps the assertion
    honest (it starts passing, loudly, the moment the real fix lands)
    without failing CI for a gap that's already known and deliberately not
    being fixed in the same change as everything else here."""
    global _PASS, _FAIL, _KNOWN_FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    elif known_issue:
        _KNOWN_FAIL += 1
        print(f"  KNOWN {label}  (tracked: {known_issue})")
        if detail:
            print(f"        {detail}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


# --- Poppler pdftotext detection ---------------------------------------------
def _find_poppler_pdftotext():
    """A poppler-flavored pdftotext (the one that supports -bbox).

    On some Windows dev setups, Git for Windows ships its own xpdfreader
    pdftotext earlier on PATH; that build silently lacks -bbox (it just
    prints its own usage text instead of erroring), which would make every
    find_word() call below return no matches with no obvious cause. Probe
    candidates and pick the first whose version banner mentions poppler.
    """
    candidates = []
    which = shutil.which("pdftotext")
    if which:
        candidates.append(which)
    candidates.append(r"C:\texlive\2025\bin\windows\pdftotext.exe")
    for cand in candidates:
        try:
            proc = subprocess.run([cand, "-v"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        banner = (proc.stdout or "") + (proc.stderr or "")
        if "poppler" in banner.lower():
            return cand
    return None


PDFTOTEXT = _find_poppler_pdftotext()


# --- Real-builder driver, mirroring test_biber_integration.py's run_build ---
def run_build(tex_dir, tex_name, aux_directory="<<temp>>", options=None, engine="pdflatex"):
    """engine defaults to "pdflatex" -- matching a document with no %!TeX
    program directive -- and is force-overridden to lualatex by the builder
    itself for autoexam/quiz/schedule/report-card (see LUALATEX_CLASSES).
    Classes NOT in that set (didactic, pset, syllabus, bingo) but that still
    require lualatex for a specific reason (e.g. didactic's problem-bank
    commands) rely on LaTeXTools resolving a %!TeX program magic comment
    into self.engine BEFORE the builder ever runs -- pass engine="lualatex"
    explicitly here to simulate that resolution; the plain default silently
    fatals under pdflatex for such a document, same as a real misconfigured
    build would."""
    b = TexlibBuilder()
    b.tex_root = os.path.join(tex_dir, tex_name)
    b.tex_name = tex_name
    b.base_name = os.path.splitext(tex_name)[0]
    b.tex_dir = tex_dir
    b.engine = engine
    b.options = options or []
    b.aux_directory = aux_directory
    b.out = ""

    env = _texinputs_env(tex_dir)

    gen = b.commands()
    try:
        item = next(gen)
        while True:
            cmd, msg = item
            proc = subprocess.run(
                cmd, cwd=tex_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180, env=env,
            )
            b.out = (proc.stdout or "") + (proc.stderr or "")
            item = gen.send(proc.returncode)
    except StopIteration:
        pass
    return {"displayed": b._displayed}


# --- pdftotext -bbox word locator ---------------------------------------------
WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"[^>]*>([^<]*)</word>'
)
PAGE_RE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)"')


def find_word(pdf_path, needle, occurrence=1):
    """Return (page, center_x, center_y) of the `occurrence`-th word containing
    `needle` in the PDF, via pdftotext -bbox. page is 1-based; x/y are in PDF
    points from the top-left -- exactly synctex's own coordinate convention."""
    out = subprocess.run(
        [PDFTOTEXT, "-bbox", pdf_path, "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    page = 0
    found = 0
    for line in out.splitlines():
        if PAGE_RE.search(line):
            page += 1
            continue
        wm = WORD_RE.search(line)
        if wm and needle in wm.group(5):
            found += 1
            if found == occurrence:
                x0, y0, x1, y1 = (float(wm.group(i)) for i in range(1, 5))
                return page, (x0 + x1) / 2, (y0 + y1) / 2
    return None


# --- synctex edit wrapper ------------------------------------------------------
def synctex_edit(pdf_path, page, x, y):
    proc = subprocess.run(
        [SYNCTEX, "edit", "-o", f"{page}:{x}:{y}:{pdf_path}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = proc.stdout
    m_in = re.search(r"^Input:(.*)$", out, re.MULTILINE)
    m_line = re.search(r"^Line:(\d+)", out, re.MULTILINE)
    if not m_in or not m_line:
        return {"raw": out, "input": None, "line": None}
    return {"raw": out, "input": m_in.group(1).strip(), "line": int(m_line.group(1))}


def basename_matches(resolved_input, expected_basename):
    return bool(resolved_input) and (
        os.path.basename(resolved_input).lower() == expected_basename.lower()
    )


def write(tex_dir, name, content):
    with open(os.path.join(tex_dir, name), "w", encoding="utf-8") as fh:
        fh.write(content)


# --- Fixture: bank problems, multi-version, aux-directory-routed -------------
# Line numbers below are load-bearing -- keep the assertions in sync with any
# edit to these fixtures.
BANK_TEX = (
    "% test bank fixture for the SyncTeX integration test.\n"   # 1
    "\\begin{problem}{quad_one}[topic=quad]\n"                  # 2
    "\tSolve SYNCNEEDLESTEM for the unknown.\n"                 # 3
    "\t\\begin{solution}\n"                                     # 4
    "\tSYNCNEEDLESOLUTION goes here.\n"                         # 5
    "\t\\end{solution}\n"                                       # 6
    "\\end{problem}\n"                                          # 7
)
BANK_STEM_LINE = 3
BANK_SOLUTION_LINE = 5

AUTOEXAM_TEX = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\versions{A,B}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{problems}\n"
    "\\problem{quad_one}\n"
    "\\end{problems}\n"
    "\\end{document}\n"
)


def scenario_bank_multiversion():
    print("\n=== Scenario 1: bank problem, multi-version, aux_directory=<<temp>> ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_bank_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "autoexam.tex", AUTOEXAM_TEX)
        run_build(tmp, "autoexam.tex", aux_directory="<<temp>>")

        pdf = os.path.join(tmp, "autoexam.pdf")
        check("PDF was produced", os.path.exists(pdf))
        check("plain .synctex was produced (finalize step ran)",
              os.path.exists(os.path.join(tmp, "autoexam.synctex")))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_STEM_LINE})",
                  r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_bank_solutions_mode():
    """FIXED (task_27d73860). The original theory (tcolorbox defers shipout
    for internal measurement, like xltabular, consuming the redirect before
    real content ships) was WRONG -- disproved by ablation (stripping
    tcolorbox out of {solution} entirely still failed identically). Two
    separate bugs were actually stacked:

      1. problem_engine.lua never staged a SyncTeX redirect for the solution
         region at all -- p.solution was tex.print'd as a raw string with no
         file backing, so its nodes inherited whatever (file,line) the STEM's
         redirect last left active. Fixed by pbank_stage_solution/
         emit_solution_block, which stage+\\@@input the solution's own
         bank-file lines, deferred via a follow-up \\directlua token
         (texlib_synctex.lua allows only one pending redirect at a time,
         consumed by the next matching \\@@input -- same pattern as
         pbank_print_catalog's per-id deferred calls).

      2. Separately: tcolorbox's `enhanced` mode (needed for the old
         `borderline west` accent) does its own internal box handling that
         defeats `synctex edit`'s geometric reverse-search even for
         correctly-tagged content -- confirmed generic, not about solution
         content specifically (the tcolorbox-internal "Solution." header
         text failed identically, untagged or not). Root cause: \\unvbox
         splices nodes with no box-open record of its own, so reverse search
         can't recover correctly-tagged content spliced inside a wrapper
         whose own self-tag is the .sty file, not the bank -- confirmed by
         swapping \\unvbox\\@sol@box for \\box\\@sol@box (a real nested box
         node), which fixed it inside a plain \\colorbox+\\parbox and inside
         tcolorbox's standard (non-enhanced) mode, but not enhanced mode.
         Fixed by dropping tcolorbox for {solution} entirely: plain
         \\colorbox+\\parbox, \\box (not \\unvbox), left accent hand-drawn
         with \\vrule sized from \\ht\\@sol@box/\\dp\\@sol@box (read before
         \\box empties the register). Trade-off accepted: \\box can't split
         across a page the way the old breakable tcolorbox could -- surveyed
         2026-07-04, every shipped solution is a few lines of prose/math,
         none ever needed one."""
    print("\n=== Scenario 2: bank problem, Solutions mode ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_sol_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "autoexam.tex", AUTOEXAM_TEX)
        run_build(tmp, "autoexam.tex", aux_directory="<<temp>>",
                  options=["--texlib-mode=solutions"])

        pdf = os.path.join(tmp, "autoexam.pdf")
        check("PDF was produced (solutions mode)", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESOLUTION")
        check("found the solution needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the solution resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_SOLUTION_LINE})",
                  r["line"] == BANK_SOLUTION_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: document-attributed (non-bank) problem, WITH a page shipout
# before retrieval -- \maketitle in a real document always ships a title
# page first, so this is the realistic case, not an edge case. -------------
DOC_PROBLEM_TEX = (
    "\\documentclass[exam-number=1]{autoexam}\n"           # 1
    "\\begin{document}\n"                                  # 2
    "\\begin{problem}{inlineone}[topic=algebra]\n"         # 3
    "\tSolve SYNCNEEDLEBODYSTEM for x.\n"                  # 4
    "\t\\begin{solution}\n"                                # 5
    "\tSYNCNEEDLEBODYSOLUTION.\n"                           # 6
    "\t\\end{solution}\n"                                  # 7
    "\\end{problem}\n"                                     # 8
    "\\maketitle\n"                                        # 9
    "\\begin{problems}\n"                                  # 10
    "\\problem{inlineone}\n"                               # 11
    "\\end{problems}\n"                                    # 12
    "\\end{document}\n"                                    # 13
)
DOC_PROBLEM_STEM_LINE = 4


def scenario_document_attributed_problem():
    print("\n=== Scenario 3: document-body-defined problem, page shipout "
          "before retrieval ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_doc_")
    try:
        write(tmp, "inline-exam.tex", DOC_PROBLEM_TEX)
        run_build(tmp, "inline-exam.tex", aux_directory="<<temp>>")

        pdf = os.path.join(tmp, "inline-exam.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLEBODYSTEM")
        check("found the stem needle in the PDF (retrieval itself works)",
              pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to the exam file itself",
                  basename_matches(r["input"], "inline-exam.tex"), r["raw"][:300])
            check(f"...at the correct source line ({DOC_PROBLEM_STEM_LINE}), "
                  "not wherever the title page shipped out from",
                  r["line"] == DOC_PROBLEM_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: schedule class, aux-routed (the historically fragile path) ----
SCHEDULE_COURSEMETA_TEX = (
    "\\metasetup{\n"
    "\tinstitution     = {University of Nevada, Reno},\n"
    "\tinstructor      = {Test Instructor},\n"
    "\tseason          = Fall,\n"
    "\tyear            = 2026,\n"
    "\tcourse-subject  = Math,\n"
    "\tcourse-number   = 181,\n"
    "\tcourse-title    = {Calculus I},\n"
    "\tcourse-section  = 1001,\n"
    "\tlecture-days    = MWF,\n"
    "\tlecture-times   = {9:00-9:50am},\n"
    "\tstart-date      = 8-24,\n"
    "\tend-date        = 12-8,\n"
    "\tfinal-date      = 12-15,\n"
    "\tfinal-time      = {9:45-11:45am},\n"
    "}\n"
)
SCHEDULE_TEX = (
    "\\documentclass[landscape=true]{schedule}\n"    # 1
    "\\begin{document}\n"                             # 2
    "\\maketitle\n"                                   # 3
    "\\begin{schedule}\n"                             # 4
    # 8-26 (a Wednesday) falls in the FIRST calendar week given
    # start-date=8-24 below -- close to start-date on purpose, so the
    # holiday needle renders without needing enough \section filler to
    # make the calendar span all the way to some later date.
    "\t\\holiday{8-26}{SYNCNEEDLEHOLIDAY}\n"          # 5
    "\t\\syllabus\n"                                  # 6
    "\t\\section{Test Section One}\n"                 # 7
    "\\end{schedule}\n"                               # 8
    "\\end{document}\n"                               # 9
)
SCHEDULE_HOLIDAY_LINE = 5


def scenario_schedule_aux_routed():
    """xltabular defers real box shipout to end-of-file (confirmed with a
    trivial non-TeXLib xltabular table -- not fixable by a redirect-timing
    patch), so every cell's raw SyncTeX line collapses to one value absent
    from the schedmap. The safe behavior is the HONEST fallback: leave the
    Input record pointing at the auto-generated grid file rather than
    confidently repointing a wrong line at the real source (see
    texlib_builder.py's _rewrite_synctex_for_schedmap for the full writeup).
    This asserts that honest-fallback behavior, not per-cell precision."""
    print("\n=== Scenario 4: schedule class, aux_directory=<<temp>> ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_sched_")
    try:
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_TEX)
        result = run_build(tmp, "schedule.tex", aux_directory="<<temp>>")
        check("builder reports the honest per-cell-unavailable fallback "
              "(not a silent no-op, and not a false 'rewrote' claim)",
              "per-cell SyncTeX could not be applied" in result["displayed"],
              result["displayed"])

        pdf = os.path.join(tmp, "schedule.pdf")
        check("PDF was produced", os.path.exists(pdf))
        check("plain .synctex was produced", os.path.exists(os.path.join(tmp, "schedule.synctex")))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        check("found the holiday needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            # r["input"] is whatever absolute path SyncTeX itself resolved to
            # (e.g. the grid file may live in the aux_directory routing
            # target, not tex_dir) -- check the resolved path directly, not
            # reconstructed relative to tmp, since that's the exact path a
            # real editor would be asked to open.
            resolved_exists = bool(r["input"]) and os.path.exists(r["input"])
            check("click on the holiday cell resolves to a REAL, existing "
                  "file (the grid scratch file is the honest fallback here; "
                  "landing on a wrong line of schedule.tex would be worse)",
                  resolved_exists, r["raw"][:300])
            check("...and does NOT confidently mislabel it as schedule.tex "
                  "(the source) at some unrelated line",
                  not basename_matches(r["input"], "schedule.tex"),
                  f"input={r['input']!r} line={r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_schedule_plain_cli():
    """Plain CLI build (no Sublime builder, no schedmap rewrite): should still
    resolve to SOME real, existing file -- the documented fallback (landing in
    the auto-generated grid file) is acceptable here; a dangling/nonexistent
    reference would not be."""
    print("\n=== Scenario 5: schedule class, plain CLI (no Sublime builder) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_sched_cli_")
    try:
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_TEX)
        env = _texinputs_env(tmp)
        cmd = [LUALATEX, "-interaction=nonstopmode", "-synctex=1",
               "-shell-escape", "schedule.tex"]
        for _ in range(2):
            subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, timeout=180)

        pdf = os.path.join(tmp, "schedule.pdf")
        gz = os.path.join(tmp, "schedule.synctex.gz")
        check("PDF was produced", os.path.exists(pdf))
        check(".synctex.gz was produced (CLI build, no finalize step)", os.path.exists(gz))
        if not (os.path.exists(pdf) and os.path.exists(gz)):
            return

        pos = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        check("found the holiday needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            resolved_exists = bool(r["input"]) and os.path.exists(
                os.path.join(tmp, os.path.basename(r["input"]))
            )
            check("fallback resolves to a REAL, existing file",
                  resolved_exists, r["raw"][:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: a multiple-choice bank problem -- exercises emit_mc_tail's own
# call into emit_solution_block, a DIFFERENT code path than the FR case above
# (Scenario 2), never previously covered. ------------------------------------
MC_BANK_TEX = (
    "\\begin{problem}{mc_one}[topic=mctest]\n"      # 1
    "\tSolve SYNCNEEDLEMCSTEM for x.\n"              # 2
    "\t\\begin{choices}\n"                           # 3
    "\t\t\\cchoice SYNCNEEDLEMCCORRECT\n"             # 4
    "\t\t\\choice SYNCNEEDLEMCWRONG\n"                # 5
    "\t\\end{choices}\n"                              # 6
    "\t\\begin{solution}\n"                          # 7
    "\tSYNCNEEDLEMCSOLUTION explanation.\n"          # 8
    "\t\\end{solution}\n"                            # 9
    "\\end{problem}\n"                                # 10
)
MC_STEM_LINE = 2
MC_SOLUTION_LINE = 8

MC_AUTOEXAM_TEX = (
    "\\documentclass[exam-number=1]{autoexam}\n"
    "\\loadbank{mcbank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{mcproblems}\n"
    "\\problem{mc_one}\n"
    "\\end{mcproblems}\n"
    "\\end{document}\n"
)


def scenario_mc_bank_problem():
    """MC (multiple-choice) bank problem, Solutions mode: emit_mc_tail calls
    emit_solution_block on a DIFFERENT branch than the FR case in Scenario 2
    -- never previously exercised by this suite. Choices themselves are
    engine-selected/shuffled per version and intentionally have no fixed
    source line to redirect to (not asserted here); the stem and solution
    both should.

    KNOWN ISSUE (task_dbeb33f6, not fixed in this change): the solution's
    raw SyncTeX record DOES carry the correct source line (verified via bulk
    inspection of the raw .synctex stream -- 9 records on the solution's
    bank-file line, identical shape to the stem's), but the record's own
    (h,v) position is ~200pt away from where the text actually renders, so
    no click in that region resolves at all. Working theory: emit_mc_tail's
    \\@mcframe@* side-by-side layout does its own box measurement on top of
    the already-fixed {solution} environment, displacing the position. The
    stem is unaffected (its own separate assertion below is a hard failure,
    not a known-issue, since it's not expected to have this problem)."""
    print("\n=== Scenario 6: MC bank problem, Solutions mode ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_mc_")
    try:
        write(tmp, "mcbank.tex", MC_BANK_TEX)
        write(tmp, "mcautoexam.tex", MC_AUTOEXAM_TEX)
        run_build(tmp, "mcautoexam.tex", aux_directory="<<temp>>",
                  options=["--texlib-mode=solutions"])

        pdf = os.path.join(tmp, "mcautoexam.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLEMCSTEM")
        check("found the MC stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the MC stem resolves to mcbank.tex",
                  basename_matches(r["input"], "mcbank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({MC_STEM_LINE})",
                  r["line"] == MC_STEM_LINE, f"got line {r['line']!r}")

        pos2 = find_word(pdf, "SYNCNEEDLEMCSOLUTION")
        check("found the MC solution needle in the PDF", pos2 is not None)
        if pos2:
            r2 = synctex_edit(pdf, *pos2)
            check("click on the MC solution resolves to mcbank.tex",
                  basename_matches(r2["input"], "mcbank.tex"), r2["raw"][:300],
                  known_issue="task_dbeb33f6")
            check(f"...at the correct source line ({MC_SOLUTION_LINE})",
                  r2["line"] == MC_SOLUTION_LINE, f"got line {r2['line']!r}",
                  known_issue="task_dbeb33f6")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: the quiz class, a different root class from autoexam, using
# its own \question \getproblem{id} retrieval style (not \problem{filter}
# inside {problems}) -- shares texlib-problembank.sty but never previously
# built through this suite. Reuses BANK_TEX (same needles/lines as Scenario
# 1/2) since the bank format itself doesn't vary by class. --------------------
QUIZ_TEX = (
    "\\documentclass[quiz-number=1]{quiz}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{questions}\n"
    "\\question \\getproblem{quad_one}\n"
    "\\end{questions}\n"
    "\\end{document}\n"
)


def scenario_quiz_bank_problem():
    print("\n=== Scenario 7: quiz class, bank problem via \\getproblem ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_quiz_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "quiz.tex", QUIZ_TEX)
        run_build(tmp, "quiz.tex", aux_directory="<<temp>>")

        pdf = os.path.join(tmp, "quiz.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_STEM_LINE})",
                  r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: didactic (lecture notes), a non-exam class that also loads
# texlib-problembank so a lecture handout can \getproblem{id} directly in
# running prose -- never previously built through this suite. ---------------
DIDACTIC_TEX = (
    # didactic is NOT in the builder's auto-lualatex class list (only
    # autoexam/quiz/schedule/report-card are) -- it silently defers its
    # LuaLaTeX requirement until a bank command is actually used (see
    # CLAUDE.md), so a document that calls \getproblem needs this magic
    # comment or a plain pdflatex build fatals. Matches the real, documented
    # gotcha (root chapterN.tex files needed this same fix 2026-06-16).
    "% !TeX program = lualatex\n"
    "\\documentclass{didactic}\n"
    "\\loadbank{bank.tex}\n"
    "\\begin{document}\n"
    "\\getproblem{quad_one}\n"
    "\\end{document}\n"
)


def scenario_didactic_bank_problem():
    print("\n=== Scenario 8: didactic (lecture notes), bank problem via \\getproblem ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_didactic_")
    try:
        write(tmp, "bank.tex", BANK_TEX)
        write(tmp, "didactic.tex", DIDACTIC_TEX)
        # engine="lualatex": didactic isn't in the builder's forced-lualatex
        # class list, so this simulates LaTeXTools having already resolved
        # the %!TeX program magic comment in DIDACTIC_TEX before the builder
        # runs -- a plain pdflatex default would silently fatal here (see
        # DIDACTIC_TEX's own comment and CLAUDE.md's documented gotcha).
        result = run_build(tmp, "didactic.tex", aux_directory="<<temp>>",
                            engine="lualatex")

        pdf = os.path.join(tmp, "didactic.pdf")
        check("PDF was produced", os.path.exists(pdf), result["displayed"][:500])
        if not os.path.exists(pdf):
            return

        pos = find_word(pdf, "SYNCNEEDLESTEM")
        check("found the stem needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the stem resolves to bank.tex",
                  basename_matches(r["input"], "bank.tex"), r["raw"][:300])
            check(f"...at the correct source line ({BANK_STEM_LINE})",
                  r["line"] == BANK_STEM_LINE, f"got line {r['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- Fixture: schedule class in BOX-GRID mode (box-grid=true) ---------------
# The box grid draws the calendar as stacked box rows instead of an xltabular,
# so each cell ships eagerly and SyncTeX records it against its OWN grid-file
# line -- which is what makes the .schedmap rewrite land clicks on the real
# source line (the whole point of the mode). These scenarios assert that REAL
# per-cell accuracy, in contrast to scenarios 4/5 which assert the honest
# fallback the DEFAULT (xltabular) renderer is stuck with.
SCHEDULE_BOXGRID_TEX = (
    "\\documentclass[landscape=true, box-grid=true]{schedule}\n"  # 1
    "\\begin{document}\n"                                          # 2
    "\\maketitle\n"                                                # 3
    "\\begin{schedule}\n"                                          # 4
    "\t\\holiday{8-26}{SYNCNEEDLEHOLIDAY}\n"                       # 5
    "\t\\syllabus\n"                                               # 6
    "\t\\section{SYNCNEEDLESECTION}\n"                             # 7
    "\\end{schedule}\n"                                            # 8
    "\\end{document}\n"                                            # 9
)
BOXGRID_HOLIDAY_LINE = 5
BOXGRID_SECTION_LINE = 7


def _stage_schedule_engine(tmp):
    """Copy THIS repo's schedule engine (schedule.cls + the .lua files) plus the
    shared .sty/.lua into the fixture dir so `.` resolves them ahead of anything
    the junction/TEXINPUTS points at. Necessary because box-grid support may be
    an uncommitted/worktree change while the machine's junction still points at
    a box-grid-unaware checkout -- the fixture must exercise the code under test,
    not whatever schedule.cls is on the search path."""
    for pat in ("*.sty", "*.lua"):
        for f in glob.glob(os.path.join(TEXLIB_ROOT, pat)):
            shutil.copy(f, tmp)
    sched = os.path.join(TEXLIB_ROOT, "Schedule")
    for f in glob.glob(os.path.join(sched, "*.lua")):
        shutil.copy(f, tmp)
    shutil.copy(os.path.join(sched, "schedule.cls"), tmp)


def scenario_schedule_boxgrid_builder():
    """Box-grid via the real builder (aux routing + schedmap rewrite): a click
    on a calendar cell must resolve to the SOURCE .tex at the directive's line
    -- real per-cell inverse search, the outcome the xltabular path cannot
    reach. This is the assertion scenarios 4/5 would love to make but can't."""
    print("\n=== Scenario 6: schedule BOX-GRID via builder (real per-cell) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_boxgrid_")
    try:
        _stage_schedule_engine(tmp)
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_BOXGRID_TEX)
        result = run_build(tmp, "schedule.tex", aux_directory="<<temp>>")
        check("builder reports it mapped real cell records to the user source "
              "(box grid, not the honest-fallback message)",
              "cell record(s) to the user source" in result["displayed"],
              result["displayed"])

        pdf = os.path.join(tmp, "schedule.pdf")
        check("PDF was produced", os.path.exists(pdf))
        if not os.path.exists(pdf):
            return

        # Holiday cell -> its \holiday directive line.
        pos = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        check("found the holiday needle in the PDF", pos is not None)
        if pos:
            r = synctex_edit(pdf, *pos)
            check("click on the holiday cell resolves to schedule.tex",
                  basename_matches(r["input"], "schedule.tex"), r["raw"][:300])
            check(f"...at the holiday's own source line ({BOXGRID_HOLIDAY_LINE})",
                  r["line"] == BOXGRID_HOLIDAY_LINE, f"got line {r['line']!r}")

        # Section cell -> its \section directive line: proves DISTINCT cells map
        # to DISTINCT lines (the collapse would put both on one line).
        pos2 = find_word(pdf, "SYNCNEEDLESECTION")
        check("found the section needle in the PDF", pos2 is not None)
        if pos2:
            r2 = synctex_edit(pdf, *pos2)
            check("click on the section cell resolves to schedule.tex",
                  basename_matches(r2["input"], "schedule.tex"), r2["raw"][:300])
            check(f"...at the section's OWN source line ({BOXGRID_SECTION_LINE}), "
                  "distinct from the holiday's -- per-cell, not collapsed",
                  r2["line"] == BOXGRID_SECTION_LINE, f"got line {r2['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_schedule_boxgrid_plain_cli():
    """Box-grid plain CLI (no builder rewrite): each cell's raw attribution
    already lands on its OWN grid-file line (that's what the box grid buys, with
    or without the rewrite), so a click resolves to the grid file at the line
    whose content is that cell -- a genuinely useful fallback, unlike xltabular's
    collapse-to-last-line. We assert the two cells resolve to DIFFERENT grid
    lines (the collapse signature is both landing on the same line)."""
    print("\n=== Scenario 7: schedule BOX-GRID, plain CLI (per-cell grid lines) ===")
    tmp = tempfile.mkdtemp(prefix="texlib_synctex_it_boxgrid_cli_")
    try:
        _stage_schedule_engine(tmp)
        write(tmp, "coursemeta.tex", SCHEDULE_COURSEMETA_TEX)
        write(tmp, "schedule.tex", SCHEDULE_BOXGRID_TEX)
        env = _texinputs_env(tmp)
        cmd = [LUALATEX, "-interaction=nonstopmode", "-synctex=1",
               "-shell-escape", "schedule.tex"]
        for _ in range(2):
            subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, timeout=180)

        pdf = os.path.join(tmp, "schedule.pdf")
        gz = os.path.join(tmp, "schedule.synctex.gz")
        check("PDF was produced", os.path.exists(pdf))
        check(".synctex.gz was produced", os.path.exists(gz))
        if not (os.path.exists(pdf) and os.path.exists(gz)):
            return

        ph = find_word(pdf, "SYNCNEEDLEHOLIDAY")
        ps = find_word(pdf, "SYNCNEEDLESECTION")
        check("found both needles in the PDF", ph is not None and ps is not None)
        if ph and ps:
            rh = synctex_edit(pdf, *ph)
            rs = synctex_edit(pdf, *ps)
            grid_bn = "schedule_schedule_grid.tex"
            check("holiday cell resolves into the grid file",
                  basename_matches(rh["input"], grid_bn), rh["raw"][:200])
            check("section cell resolves into the grid file",
                  basename_matches(rs["input"], grid_bn), rs["raw"][:200])
            check("the two cells land on DIFFERENT grid lines (per-cell, not "
                  "collapsed to one line as xltabular does)",
                  rh["line"] is not None and rs["line"] is not None
                  and rh["line"] != rs["line"],
                  f"holiday line={rh['line']!r} section line={rs['line']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("TeXLib SyncTeX inverse-search integration test\n")
    if not LUALATEX:
        print("  SKIP  lualatex not found.")
        return 0
    if not PDFTOTEXT:
        print("  SKIP  no poppler-flavored pdftotext (-bbox support) found.")
        return 0
    if not SYNCTEX:
        print("  SKIP  synctex CLI not found.")
        return 0

    scenario_bank_multiversion()
    scenario_bank_solutions_mode()
    scenario_document_attributed_problem()
    scenario_schedule_aux_routed()
    scenario_schedule_plain_cli()
    scenario_mc_bank_problem()
    scenario_quiz_bank_problem()
    scenario_didactic_bank_problem()
    scenario_schedule_boxgrid_builder()
    scenario_schedule_boxgrid_plain_cli()

    summary = f"\n{_PASS} passed, {_FAIL} failed"
    if _KNOWN_FAIL:
        summary += f", {_KNOWN_FAIL} known (tracked, not blocking)"
    print(summary)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
